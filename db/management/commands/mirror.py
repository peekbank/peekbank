import os
import signal
import MySQLdb
import subprocess
import tempfile
import gc
from django.core.management.base import BaseCommand
from dotenv import load_dotenv


class Command(BaseCommand):
    help = "Mirrors all databases from a remote MariaDB server to the local server"

    def add_arguments(self, parser):
        parser.add_argument(
            "remote_connection",
            help="Remote database connection string in format host:port",
        )
        parser.add_argument(
            "--databases",
            nargs="+",
            help="Specific databases to mirror (default: all accessible)",
        )
        parser.add_argument(
            "-ni",
            "--non_interactive",
            action="store_true",
            help="Skip confirmation prompts and automatically proceed",
        )
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=100 * 1024 * 1024, 
            help="Process file in chunks of this size (in bytes)",
        )

    def handle(self, *args, **options):
        load_dotenv()

        remote_connection = options["remote_connection"]
        try:
            remote_host, remote_port = remote_connection.split(":")
            remote_port = int(remote_port)
        except ValueError:
            self.stderr.write(
                self.style.ERROR(
                    f"Invalid connection string: {remote_connection}. Format should be host:port"
                )
            )
            return

        specific_databases = options.get("databases")
        non_interactive = options.get("non_interactive", False)
        chunk_size = options.get("chunk_size", 100 * 1024 * 1024)

        remote_user = os.environ.get("PEEKBANK_DB_USER", "reader")
        remote_password = os.environ.get("PEEKBANK_DB_PASSWORD", "")

        local_host = os.environ.get("PEEKBANK_DB_HOST", "localhost")
        if local_host == "localhost":
            local_host = "127.0.0.1"  # Use IP to force TCP/IP
        local_port = int(os.environ.get("PEEKBANK_DB_PORT", "3306"))
        local_user = "root"
        local_password = os.environ.get("PEEKBANK_DB_ROOTPW", "")
        reader_user = os.environ.get("PEEKBANK_DB_USER", "reader")

        self.stdout.write(
            self.style.SUCCESS(
                f"Remote database: {remote_host}:{remote_port} (user: {remote_user})"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Local database: {local_host}:{local_port} (user: {local_user})"
            )
        )

        try:
            self.stdout.write("Connecting to remote server...")
            remote_conn = MySQLdb.connect(
                host=remote_host,
                port=remote_port,
                user=remote_user,
                passwd=remote_password,
                charset="utf8mb4",
                connect_timeout=1200,
                read_timeout=3600,
                write_timeout=3600,
            )

            remote_cursor = remote_conn.cursor()

            remote_cursor.execute("SHOW DATABASES")
            all_databases = [row[0] for row in remote_cursor.fetchall()]

            # Filter out system databases
            system_dbs = ["information_schema", "mysql", "performance_schema", "sys"]
            databases = [db for db in all_databases if db not in system_dbs]

            if specific_databases:
                databases = [db for db in databases if db in specific_databases]

            accessible_databases = []
            for db in databases:
                try:
                    remote_cursor.execute(f"USE `{db}`")
                    remote_cursor.execute("SHOW TABLES")
                    accessible_databases.append(db)
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"Skipping database {db}: {str(e)}")
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Found {len(accessible_databases)} accessible databases:"
                )
            )
            for db in accessible_databases:
                self.stdout.write(f"  - {db}")

            if not accessible_databases:
                self.stdout.write(
                    self.style.ERROR(
                        "No accessible databases found. Operation cancelled."
                    )
                )
                return

            if not non_interactive and input(
                f"This will delete and recreate {len(accessible_databases)} databases on your local server. Continue? (Y/n): "
            ).lower() not in ("y", "yes", ""):
                self.stdout.write(self.style.WARNING("Operation cancelled."))
                return

            # Process each database separately with fresh connections
            for db_name in accessible_databases:
                self.stdout.write(f"\nProcessing database: {db_name}")
                
                try:
                    # Create a fresh DB connection for each database
                    self.stdout.write("Connecting to local server as root...")
                    local_conn = MySQLdb.connect(
                        host=local_host,
                        port=local_port,
                        user=local_user,
                        passwd=local_password,
                        charset="utf8mb4",
                        connect_timeout=300,
                        read_timeout=3600,
                        write_timeout=3600,
                    )
                    local_cursor = local_conn.cursor()

                    self.stdout.write(
                        f"  Dropping local database {db_name} if it exists..."
                    )
                    local_cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")

                    self.stdout.write(f"  Creating database {db_name}...")
                    # collate to fix mysql -> mariadb migration
                    local_cursor.execute(
                        f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
                    )

                    self.stdout.write("  Granting select privileges to reader user...")
                    local_cursor.execute(
                        f"GRANT SELECT ON `{db_name}`.* TO '{reader_user}'@'%'"
                    )
                    
                    local_conn.commit()
                    local_cursor.close()
                    local_conn.close()

                    tmp_dir = os.environ.get("TMP_DATA_PATH")
                        
                    os.makedirs(tmp_dir, exist_ok=True)
                        
                    fd, dump_file = tempfile.mkstemp(
                        suffix=f"_{db_name}_dump.sql", dir=tmp_dir
                    )
                    os.close(fd)

                    self.stdout.write(f"  Dumping remote database {db_name} to file...")
                    
                    dump_cmd = [
                        "mysqldump",
                        f"--host={remote_host}",
                        f"--port={remote_port}",
                        f"--user={remote_user}",
                        "--skip-lock-tables",
                        "--no-tablespaces",
                        "--single-transaction",
                        "--skip-events",
                        "--skip-routines",
                        "--skip-triggers",
                        "--max-allowed-packet=1G", 
                        db_name,
                    ]

                    dump_env = os.environ.copy()
                    if remote_password:
                        dump_env["MYSQL_PWD"] = remote_password

                    try:
                        with open(dump_file, "wb") as f:
                            process = subprocess.Popen(
                                dump_cmd, 
                                stdout=f, 
                                stderr=subprocess.PIPE, 
                                env=dump_env,
                                start_new_session=True
                            )
                            
                            try:
                                _, stderr = process.communicate(timeout=3600)
                                
                                if process.returncode != 0:
                                    error_msg = stderr.decode(errors='replace')
                                    self.stderr.write(
                                        self.style.ERROR(f"  Error dumping {db_name}: {error_msg}")
                                    )
                                    continue
                            except subprocess.TimeoutExpired:
                                try:
                                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                                except (ProcessLookupError, PermissionError):
                                    pass
                                
                                self.stderr.write(
                                    self.style.ERROR(f"  Dump timed out after 3600 seconds")
                                )
                                continue

                        if os.path.getsize(dump_file) == 0:
                            self.stderr.write(
                                self.style.ERROR(
                                    f"  Error: Dump file for {db_name} is empty. Skipping."
                                )
                            )
                            os.remove(dump_file)
                            continue

                        self.stdout.write(
                            "  Processing dump file to fix collation issues..."
                        )
                        
                        with tempfile.NamedTemporaryFile(mode='w+', suffix='.sql', delete=False) as temp_f:
                            temp_file = temp_f.name
                            
                            with open(dump_file, 'r', encoding='utf-8', errors='replace') as src_f:
                                replacements = [
                                    ("utf8mb4_0900_ai_ci", "utf8mb4_general_ci"),
                                    ("utf8mb4_0900_as_ci", "utf8mb4_general_ci"),
                                    ("utf8mb4_0900_as_cs", "utf8mb4_general_ci"),
                                    ("utf8mb4_0900_bin", "utf8mb4_bin"),
                                    ("utf8mb4_ja_0900_as_cs", "utf8mb4_general_ci"),
                                    ("utf8mb4_ja_0900_as_cs_ks", "utf8mb4_general_ci"),
                                    ("utf8mb4_unicode_520_ci", "utf8mb4_unicode_ci"),
                                ]
                                
                                while True:
                                    chunk = src_f.read(chunk_size)
                                    if not chunk:
                                        break
                                    
                                    for old_collation, new_collation in replacements:
                                        chunk = chunk.replace(old_collation, new_collation)
                                    
                                    temp_f.write(chunk)
                                    
                                    del chunk
                                    gc.collect()
                        
                        # Use the processed file for restoration
                        self.stdout.write(f"  Restoring to local database {db_name}...")

                        restore_cmd = [
                            "mysql",
                            f"--host={local_host}",
                            f"--port={local_port}",
                            f"--user={local_user}",
                            "--net_buffer_length=1M",
                            "--max-allowed-packet=1G",
                            "--default-character-set=utf8mb4",
                            "--connect-timeout=3600",
                            db_name,
                        ]

                        restore_env = os.environ.copy()
                        if local_password:
                            restore_env["MYSQL_PWD"] = local_password

                        file_size_mb = os.path.getsize(temp_file) / (1024 * 1024)
                        self.stdout.write(f"  Import file size: {file_size_mb:.2f} MB")
                                            
                        timeout = max(1800, int(file_size_mb * 2))
                        self.stdout.write(f"  Using timeout of {timeout} seconds for import")

                        try:
                            with open(temp_file, "rb") as f:
                                process = subprocess.Popen(
                                    restore_cmd,
                                    stdin=f,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    env=restore_env,
                                    start_new_session=True
                                )
                                
                                try:
                                    stdout, stderr = process.communicate(timeout=timeout)
                                    
                                    if process.returncode != 0:
                                        error_message = stderr.decode(errors='replace')
                                        self.stdout.write("MySQL Error Output:")
                                        self.stdout.write(error_message[:1000] + "..." if len(error_message) > 1000 else error_message)
                                        self.stderr.write(
                                            self.style.ERROR(f"  Error restoring {db_name}")
                                        )
                                    else:
                                        self.stdout.write(
                                            self.style.SUCCESS(f"  Successfully transferred {db_name}")
                                        )
                                except subprocess.TimeoutExpired:
                                    try:
                                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                                    except (ProcessLookupError, PermissionError):
                                        pass
                                    
                                    self.stderr.write(
                                        self.style.ERROR(f"  Import timed out after {timeout} seconds")
                                    )
                        except Exception as e:
                            self.stderr.write(
                                self.style.ERROR(f"  Error during import subprocess: {str(e)}")
                            )
                        finally:
                            try:
                                if os.path.exists(temp_file):
                                    os.remove(temp_file)
                                if os.path.exists(dump_file):
                                    os.remove(dump_file)
                            except Exception as e:
                                self.stderr.write(
                                    self.style.WARNING(f"  Could not remove temporary file: {str(e)}")
                                )
                            
                            gc.collect()

                    except Exception as e:
                        self.stderr.write(
                            self.style.ERROR(f"  Error during transfer: {str(e)}")
                        )
                        if os.path.exists(dump_file):
                            try:
                                os.remove(dump_file)
                            except Exception:
                                pass
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(f"  Database operation error for {db_name}: {str(e)}")
                    )

            try:
                final_conn = MySQLdb.connect(
                    host=local_host,
                    port=local_port,
                    user=local_user,
                    passwd=local_password,
                    charset="utf8mb4",
                )
                final_cursor = final_conn.cursor()
                self.stdout.write("Flushing privileges...")
                final_cursor.execute("FLUSH PRIVILEGES")
                final_cursor.close()
                final_conn.close()
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"Error flushing privileges: {str(e)}")
                )

            remote_cursor.close()
            remote_conn.close()

            self.stdout.write(self.style.SUCCESS("\nDatabase mirroring completed!"))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error: {str(e)}"))
            return