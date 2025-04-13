import os
import MySQLdb
import subprocess
from django.core.management.base import BaseCommand
from dotenv import load_dotenv


class Command(BaseCommand):
    help = "Exports all accessible databases to dump files for manual transfer"

    def add_arguments(self, parser):
        parser.add_argument(
            "--databases", "-dbs",
            nargs="+",
            help="Specific databases to export (default: all accessible)",
        )
        parser.add_argument(
            "-ni", "--non_interactive",
            action="store_true",
            help="Skip confirmation prompts and automatically proceed",
        )


    def handle(self, *args, **options):
        load_dotenv()

        specific_databases = options.get("databases")
        non_interactive = options.get("non_interactive", False)
        output_dir = os.environ.get("SQL_DUMP_PATH", "./peekbank-data/dumps")

        try:
            os.makedirs(output_dir, exist_ok=True)
            self.stdout.write(self.style.SUCCESS(f"Ensured output directory exists: {output_dir}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to create output directory {output_dir}: {str(e)}"))
            return

        local_host = os.environ.get("PEEKBANK_DB_HOST", "localhost")
        if local_host == "localhost":
            local_host = "127.0.0.1"  # Use IP to force TCP/IP
        local_port = int(os.environ.get("PEEKBANK_DB_PORT", "3306"))
        local_user = os.environ.get("PEEKBANK_DB_USER", "reader")
        local_password = os.environ.get("PEEKBANK_DB_PASSWORD", "")

        self.stdout.write(
            self.style.SUCCESS(
                f"Local database: {local_host}:{local_port} (user: {local_user})"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(f"Output directory: {output_dir}")
        )

        try:
            self.stdout.write("Connecting to local server...")
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

            local_cursor.execute("SHOW DATABASES")
            all_databases = [row[0] for row in local_cursor.fetchall()]

            # Filter out system databases
            system_dbs = ["information_schema", "mysql", "performance_schema", "sys"]
            databases = [db for db in all_databases if db not in system_dbs]

            if specific_databases:
                databases = [db for db in databases if db in specific_databases]

            accessible_databases = []
            for db in databases:
                try:
                    local_cursor.execute(f"USE `{db}`")
                    local_cursor.execute("SHOW TABLES")
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
                f"This will export {len(accessible_databases)} databases to {output_dir}. Continue? (Y/n): "
            ).lower() not in ("y", "yes", ""):
                self.stdout.write(self.style.WARNING("Operation cancelled."))
                return

            for db_name in accessible_databases:
                self.stdout.write(f"\nProcessing database: {db_name}")

                dump_file = os.path.join(output_dir, f"{db_name}_dump.sql")

                self.stdout.write(f"  Dumping database {db_name} to file...")

                dump_cmd = [
                    "mysqldump",
                    f"--host={local_host}",
                    f"--port={local_port}",
                    f"--user={local_user}",
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
                if local_password:
                    dump_env["MYSQL_PWD"] = local_password

                try:
                    with open(dump_file, "wb") as f:
                        result = subprocess.run(
                            dump_cmd, stdout=f, stderr=subprocess.PIPE, env=dump_env
                        )

                    if result.returncode != 0:
                        error_msg = result.stderr.decode()
                        self.stderr.write(
                            self.style.ERROR(f"  Error dumping {db_name}: {error_msg}")
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
                        self.style.SUCCESS(
                            f"  Successfully exported {db_name} to {dump_file}"
                        )
                    )

                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(f"  Error during export: {str(e)}")
                    )
                    if os.path.exists(dump_file):
                        os.remove(dump_file)

            local_cursor.close()
            local_conn.close()

            self.stdout.write(self.style.SUCCESS("\nDatabase export completed!"))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error: {str(e)}"))
            return