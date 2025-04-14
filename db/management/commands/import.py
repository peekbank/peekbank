import os
import signal
import MySQLdb
import subprocess
import glob
import tempfile
import gc
from django.core.management.base import BaseCommand
from dotenv import load_dotenv


class Command(BaseCommand):
    help = "Imports database dump files after manual transfer"

    def add_arguments(self, parser):
        parser.add_argument(
            "--databases", "-dbs",
            nargs="+",
            help="Specific databases to import (default: all available dump files)",
        )
        parser.add_argument(
            "-ni", "--non_interactive",
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

        specific_databases = options.get("databases")
        non_interactive = options.get("non_interactive", False)
        chunk_size = options.get("chunk_size", 100 * 1024 * 1024)
        
        input_dir = os.environ.get("SQL_DUMP_PATH", "./peekbank-data/dumps")

        if not os.path.isdir(input_dir):
            self.stderr.write(
                self.style.ERROR(f"Input directory does not exist: {input_dir}")
            )
            return

        local_host = os.environ.get("PEEKBANK_DB_HOST", "localhost")
        if local_host == "localhost":
            local_host = "127.0.0.1"  # Use IP to force TCP/IP
        local_port = int(os.environ.get("PEEKBANK_DB_PORT", "3306"))
        local_user = "root" 
        local_password = os.environ.get("PEEKBANK_DB_ROOTPW", "")
        reader_user = os.environ.get("PEEKBANK_DB_USER", "reader")

        self.stdout.write(
            self.style.SUCCESS(
                f"Local database: {local_host}:{local_port} (user: {local_user})"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(f"Input directory: {input_dir}")
        )

        try:
            dump_files = glob.glob(os.path.join(input_dir, "*_dump.sql"))
            
            available_databases = []
            for dump_file in dump_files:
                db_name = os.path.basename(dump_file).replace("_dump.sql", "")
                available_databases.append((db_name, dump_file))
            
            if specific_databases:
                available_databases = [
                    (db, file) for db, file in available_databases 
                    if db in specific_databases
                ]

            if not available_databases:
                self.stdout.write(
                    self.style.ERROR(
                        "No database dump files found. Operation cancelled."
                    )
                )
                return

            self.stdout.write(
                self.style.SUCCESS(
                    f"Found {len(available_databases)} database dump files:"
                )
            )
            for db_name, dump_file in available_databases:
                self.stdout.write(f"  - {db_name} ({dump_file})")

            if not non_interactive and input(
                f"This will import {len(available_databases)} databases. Continue? (Y/n): "
            ).lower() not in ("y", "yes", ""):
                self.stdout.write(self.style.WARNING("Operation cancelled."))
                return

            # Process each database separately with fresh connections for each
            for db_name, dump_file in available_databases:
                self.stdout.write(f"\nProcessing database: {db_name}")

                if not os.path.exists(dump_file) or os.path.getsize(dump_file) == 0:
                    self.stderr.write(
                        self.style.ERROR(
                            f"  Error: Dump file for {db_name} is empty or missing. Skipping."
                        )
                    )
                    continue

                try:
                    # Create a fresh DB connection for each database
                    self.stdout.write("Connecting to local server as root...")
                    local_conn = MySQLdb.connect(
                        host=local_host,
                        port=local_port,
                        user=local_user,
                        passwd=local_password,
                        charset="utf8mb4",
                        connect_timeout=1200,
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

                    self.stdout.write("  Processing dump file to fix collation issues...")
            
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
                    
                    self.stdout.write(f"  Restoring to local database {db_name}...")

                    restore_cmd = [
                        "mysql",
                        f"--host={local_host}",
                        f"--port={local_port}",
                        f"--user={local_user}",
                        "--max_allowed_packet=1G",
                        "--net_buffer_length=1M",
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
                                        self.style.SUCCESS(f"  Successfully imported {db_name}")
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
                        except Exception as e:
                            self.stderr.write(
                                self.style.WARNING(f"  Could not remove temporary file: {str(e)}")
                            )
                        
        
                        gc.collect()
                        
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

            self.stdout.write(self.style.SUCCESS("\nDatabase import completed!"))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error: {str(e)}"))
            return