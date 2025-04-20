import os
import MySQLdb
import subprocess
import datetime
import boto3
import zipfile
import shutil
import requests
import time
from django.core.management.base import BaseCommand
from dotenv import load_dotenv
from botocore.exceptions import ClientError
from tqdm import tqdm


class Command(BaseCommand):
    help = "Backup databases and OSF repository data to local storage or S3"

    def add_arguments(self, parser):
        parser.add_argument(
            "-c",
            "--connection",
            help="Remote database connection string in format host:port (if not specified, uses local database)",
        )
        parser.add_argument(
            "-sl",
            "--savelocal",
            action="store_true",
            help="Save backup files locally instead of uploading to S3",
        )
        parser.add_argument(
            "-i",
            "--interactive",
            action="store_true",
            help="Enable interactive mode with confirmation prompts (default is non-interactive)",
        )

        parser.add_argument(
            "--skiposf",
            action="store_true",
            help="Skip backing up OSF repository data (overrides BACKUP_OSF=true in .env)",
        )
        parser.add_argument(
            "--skipdb",
            action="store_true",
            help="Skip backing up databases (overrides BACKUP_DATABASE=true in .env)",
        )
        parser.add_argument(
            "--single",
            action="store_true",
            help="Download all OSF files individually without using ZIP archives for folders",
        )

    def handle(self, *args, **options):
        load_dotenv()

        perform_db = os.environ.get(
            "BACKUP_DATABASE", "true"
        ).upper() == "TRUE" and not options.get("skipdb", False)
        perform_osf = os.environ.get(
            "BACKUP_OSF", "true"
        ).upper() == "TRUE" and not options.get("skiposf", False)

        self.stdout.write(
            self.style.SUCCESS("Database backup will be performed")
            if perform_db
            else self.style.WARNING("Database backup will be skipped")
        )
        self.stdout.write(
            self.style.SUCCESS("OSF backup will be performed")
            if perform_osf
            else self.style.WARNING("OSF backup will be skipped")
        )

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        base_data_path = os.environ.get("PEEKBANK_DATA_PATH")
        if not base_data_path:
            self.stderr.write(
                self.style.ERROR("PEEKBANK_DATA_PATH environment variable not set.")
            )
            return
        if not os.path.exists(base_data_path):
            self.stderr.write(
                self.style.ERROR(
                    f"PEEKBANK_DATA_PATH '{base_data_path}' does not exist."
                )
            )
            return

        backup_dir = os.path.join(base_data_path, "backups")
        os.makedirs(backup_dir, exist_ok=True)

        if not self.check_disk_space(backup_dir,float(os.environ.get("MIN_FREE_SPACE_GB_BACKUP", "20"))):
            return

        # Create a unique backup folder for this run
        backup_folder = os.path.join(backup_dir, f"backup_{timestamp}")
        os.makedirs(backup_folder, exist_ok=True)

        connection = options.get("connection")
        save_local = options.get("savelocal", False)
        interactive = options.get("interactive", False)
        single_file_mode = options.get("single", False)

        if not perform_db and not perform_osf:
            self.stderr.write(
                self.style.ERROR(
                    "Both database and OSF backups are disabled (check .env variables BACKUP_DATABASE/BACKUP_OSF and --skipdb/--skiposf flags). Nothing to do."
                )
            )
            try:
                os.rmdir(backup_folder)
            except OSError as e:
                self.stderr.write(
                    self.style.WARNING(
                        f"Could not remove empty backup directory {backup_folder}: {e}"
                    )
                )
            return

        s3_bucket = os.environ.get("S3_BUCKET")
        s3_region = os.environ.get("S3_REGION", "us-east-1")
        s3_access_key = os.environ.get("S3_ACCESS_KEY")
        s3_secret_key = os.environ.get("S3_SECRET_KEY")
        s3_endpoint = os.environ.get("S3_ENDPOINT")
        keep_last = int(os.environ.get("BACKUP_KEEP_LAST", "3"))

        if not save_local and (not s3_bucket or not s3_access_key or not s3_secret_key):
            self.stderr.write(
                self.style.ERROR(
                    "S3 backup selected but environment variables S3_BUCKET, S3_ACCESS_KEY, "
                    "and S3_SECRET_KEY must be set. Use --savelocal to store backups locally."
                )
            )
            try:
                os.rmdir(backup_folder)
            except OSError as e:
                self.stderr.write(
                    self.style.WARNING(
                        f"Could not remove empty backup directory {backup_folder}: {e}"
                    )
                )
            return

        self.stdout.write(
            self.style.SUCCESS(f"Starting backup process at {datetime.datetime.now()}")
        )
        self.stdout.write(self.style.SUCCESS(f"Backup directory: {backup_folder}"))
        self.stdout.write(
            self.style.WARNING("Running in interactive mode.")
            if interactive
            else self.style.SUCCESS("Running in non-interactive mode.")
        )

        components_backed_up = []
        db_backup_successful = True
        osf_backup_successful = True

        if perform_db:
            db_backup_folder = os.path.join(backup_folder, "databases")
            os.makedirs(db_backup_folder, exist_ok=True)

            db_backup_successful = self.perform_database_backup(
                db_backup_folder, connection, interactive
            )
            if db_backup_successful:
                components_backed_up.append("databases")
            else:
                self.stderr.write(
                    self.style.ERROR("Database backup failed or was cancelled.")
                )

        if perform_osf:
            osf_backup_folder = os.path.join(backup_folder, "osf_data")
            os.makedirs(osf_backup_folder, exist_ok=True)

            osf_backup_successful = self.download_osf_repository(
                osf_backup_folder, interactive, single_file_mode
            )
            if osf_backup_successful:
                components_backed_up.append("OSF repository")
            else:
                self.stderr.write(
                    self.style.ERROR("OSF repository backup failed or was cancelled.")
                )

        if not components_backed_up and (
            not db_backup_successful or not osf_backup_successful
        ):
            self.stderr.write(
                self.style.ERROR(
                    "No components were successfully backed up. Exiting without creating archive."
                )
            )
            try:
                if os.path.exists(backup_folder) and os.listdir(backup_folder):
                    shutil.rmtree(backup_folder)
                elif os.path.exists(backup_folder):
                    os.rmdir(backup_folder)
            except OSError as e:
                self.stderr.write(
                    self.style.WARNING(
                        f"Could not remove backup directory {backup_folder}: {e}"
                    )
                )
            return

        self.stdout.write("Checking backup folder contents before archiving...")
        backup_zip_path = os.path.join(backup_dir, f"backup_{timestamp}.zip")
        zip_created = False

        try:
            # Check if backup_folder has content before zipping
            if not os.path.exists(backup_folder) or not os.listdir(backup_folder):
                self.stdout.write(
                    self.style.WARNING(
                        f"Backup folder '{backup_folder}' is empty or does not exist. Skipping archive creation."
                    )
                )
                if os.path.exists(backup_folder):
                    try:
                        os.rmdir(backup_folder)
                    except OSError as e:
                        self.stderr.write(
                            self.style.WARNING(
                                f"Could not remove empty backup directory {backup_folder}: {e}"
                            )
                        )
            else:
                self.stdout.write("Creating final backup archive...")
                with zipfile.ZipFile(
                    backup_zip_path, "w", zipfile.ZIP_DEFLATED
                ) as zipf:
                    for root, dirs, files in os.walk(backup_folder):
                        for file in files:
                            filepath = os.path.join(root, file)
                            arcname = os.path.relpath(filepath, backup_folder)
                            zipf.write(filepath, arcname)
                self.stdout.write(
                    self.style.SUCCESS(f"Backup archive created: {backup_zip_path}")
                )
                zip_created = True

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to create zip archive: {e}"))
            zip_created = False
            # Keep the folder with partial contents if zip fails
            self.stdout.write(
                self.style.WARNING(
                    f"Keeping backup folder contents at: {backup_folder}"
                )
            )
            if os.path.exists(backup_zip_path):
                try:
                    os.remove(backup_zip_path)
                except OSError as e_rm_zip:
                    self.stderr.write(
                        self.style.WARNING(
                            f"Could not remove partial zip file {backup_zip_path} after zip failure: {e_rm_zip}"
                        )
                    )

        upload_successful = True
        if not save_local:
            if not zip_created:
                self.stderr.write(
                    self.style.ERROR(
                        "Skipping S3 upload because backup zip file was not created."
                    )
                )
                upload_successful = False
            else:
                self.stdout.write("Uploading backup to S3...")
                try:
                    s3_client = boto3.client(
                        "s3",
                        region_name=s3_region,
                        aws_access_key_id=s3_access_key,
                        aws_secret_access_key=s3_secret_key,
                        endpoint_url=s3_endpoint,
                    )
                    self.manage_s3_backups(s3_client, s3_bucket, keep_last)
                    backup_key = f"peekbank_backup_{timestamp}.zip"
                    self.stdout.write(
                        f"Uploading {backup_zip_path} to s3://{s3_bucket}/{backup_key}"
                    )
                    s3_client.upload_file(backup_zip_path, s3_bucket, backup_key)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Backup uploaded to S3: s3://{s3_bucket}/{backup_key}"
                        )
                    )
                    self.stdout.write(
                        "Cleaning up local backup files after successful upload..."
                    )
                    try:
                        if os.path.exists(backup_folder):
                            shutil.rmtree(backup_folder)
                        if os.path.exists(backup_zip_path):
                            os.remove(backup_zip_path)
                    except OSError as e_clean:
                        self.stderr.write(
                            self.style.WARNING(
                                f"Error during local cleanup after S3 upload: {e_clean}"
                            )
                        )
                except ClientError as e:
                    self.stderr.write(self.style.ERROR(f"Failed to upload to S3: {e}"))
                    upload_successful = False
                    self.stdout.write(
                        self.style.WARNING(
                            f"Local backup files kept at: {backup_folder} and {backup_zip_path}"
                        )
                    )
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(
                            f"An error occurred during S3 operations or cleanup: {e}"
                        )
                    )
                    upload_successful = False
                    self.stdout.write(
                        self.style.WARNING(
                            f"Local backup files may remain at: {backup_folder} and {backup_zip_path}"
                        )
                    )

        elif save_local:
            if zip_created:
                self.stdout.write(
                    self.style.SUCCESS(f"Local backup saved at: {backup_zip_path}")
                )
                self.stdout.write("Cleaning up temporary backup folder...")
                try:
                    if os.path.exists(backup_folder):
                        shutil.rmtree(backup_folder)
                except OSError as e:
                    self.stderr.write(
                        self.style.WARNING(
                            f"Could not remove temporary backup folder {backup_folder}: {e}"
                        )
                    )
            else:
                if os.path.exists(backup_folder) and os.listdir(backup_folder):
                    self.stdout.write(
                        self.style.WARNING(
                            f"Local backup zip was not created. Raw backup folder kept at: {backup_folder}"
                        )
                    )
                else:
                    self.stderr.write(
                        self.style.ERROR(
                            "Local backup failed. No archive created and backup folder is empty or missing."
                        )
                    )

        final_success = not (
            (perform_db and not db_backup_successful)
            or (perform_osf and not osf_backup_successful)
            or (not save_local and zip_created and not upload_successful)
            or (
                os.path.exists(backup_folder)
                and not zip_created
                and os.listdir(backup_folder)
            )
        )

        final_status_style = self.style.SUCCESS if final_success else self.style.ERROR
        final_message = f"Backup process finished at {datetime.datetime.now()}."

        if components_backed_up:
            final_message += (
                f" Successfully backed up: {', '.join(components_backed_up)}."
            )
        elif perform_db or perform_osf:
            final_message += " No components were successfully backed up."
        else:
            final_message += " No backup components were selected to run."

        if perform_db and not db_backup_successful:
            final_message += " Database backup encountered errors."
        if perform_osf and not osf_backup_successful:
            final_message += " OSF backup encountered errors."

        if not save_local:
            if zip_created and upload_successful:
                final_message += " Upload to S3 successful."
            elif zip_created and not upload_successful:
                final_message += " Upload to S3 failed. Local files may have been kept."
            elif not zip_created:
                final_message += " S3 upload skipped (archive not created)."
        else:
            if zip_created:
                final_message += f" Backup saved locally to {backup_zip_path}."
            elif os.path.exists(backup_folder) and os.listdir(backup_folder):
                final_message += f" Archive creation failed; raw backup folder kept at {backup_folder}."
            else:
                final_message += (
                    " Local save failed (no archive created, backup folder empty)."
                )

        self.stdout.write(final_status_style(final_message))

    def check_disk_space(self, folder_path, required_bytes):
        """
        Check if there's enough disk space to write required_bytes to the folder_path.
        Uses MIN_FREE_SPACE_GB from .env if available. Returns True/False.
        """
        try:
            buffer_gb = 1
            buffer_bytes = buffer_gb * 1024 * 1024 * 1024

            # Check available disk space
            # Use the directory containing the target folder for disk usage check,
            # as the folder itself might not exist yet.
            check_path = (
                os.path.dirname(folder_path)
                if not os.path.exists(folder_path)
                else folder_path
            )
            # If dirname is empty (e.g., relative path in cwd), use cwd
            if not check_path:
                check_path = "."

            if not os.path.exists(check_path):
                self.stderr.write(
                    self.style.WARNING(
                        f"Cannot check disk space: Path '{check_path}' does not exist. Proceeding anyway."
                    )
                )
                return True

            _, _, free = shutil.disk_usage(check_path)

            needed_space = required_bytes + buffer_bytes

            if free < needed_space:
                self.stderr.write(
                    self.style.ERROR(
                        f"Not enough disk space to safely backup files. "
                        f"Required: {required_bytes / 1024 / 1024:.2f} MB + {buffer_gb:.1f} GB buffer, "
                        f"Available: {free / 1024 / 1024 / 1024:.2f} GB in '{check_path}'"
                    )
                )
                return False

            return True

        except Exception as e:
            self.stderr.write(
                self.style.WARNING(
                    f"Error checking disk space: {str(e)}. Proceeding anyway."
                )
            )
            return True

    def perform_database_backup(self, backup_folder, connection, interactive):
        self.stdout.write("Starting database backup...")
        overall_success = True

        if connection:
            try:
                host, port_str = connection.split(":")
                port = int(port_str)
                self.stdout.write(f"Using remote database at {host}:{port}")
            except ValueError:
                self.stderr.write(
                    self.style.ERROR(
                        f"Invalid connection string: {connection}. Format should be host:port"
                    )
                )
                return False
        else:
            host = os.environ.get("PEEKBANK_DB_HOST", "localhost")
            port = int(os.environ.get("PEEKBANK_DB_PORT", "3306"))
            self.stdout.write(f"Using configured database at {host}:{port}")

        user = os.environ.get("PEEKBANK_DB_USER")
        password = os.environ.get("PEEKBANK_DB_PASSWORD")

        if not user or not password:
            self.stderr.write(
                self.style.ERROR(
                    "Database user (PEEKBANK_DB_USER) or password (PEEKBANK_DB_PASSWORD) not set in environment."
                )
            )
            return False

        conn = None
        cursor = None
        try:
            self.stdout.write(f"Connecting to database server at {host}:{port}...")
            conn = MySQLdb.connect(
                host=host,
                port=port,
                user=user,
                passwd=password,
                charset="utf8mb4",
            )
            cursor = conn.cursor()

            cursor.execute("SHOW DATABASES")
            all_databases = [row[0] for row in cursor.fetchall()]

            system_dbs = [
                "information_schema",
                "mysql",
                "performance_schema",
                "sys",
                "peekbank_dev",
            ]
            databases = sorted([db for db in all_databases if db not in system_dbs])

            if not databases:
                self.stdout.write(
                    self.style.WARNING("No user databases found to backup.")
                )
                return True

            self.stdout.write(f"Found {len(databases)} databases to backup:")
            for db in databases:
                self.stdout.write(f"  - {db}")

            if interactive:
                confirm = input(
                    f"Proceed with backup of {len(databases)} databases? (Y/n): "
                )
                if confirm.lower() not in ("", "y", "yes"):
                    self.stdout.write(
                        self.style.WARNING("Database backup cancelled by user.")
                    )
                    return False

            for db_name in databases:
                self.stdout.write(f"Backing up database: {db_name}")
                dump_file = os.path.join(backup_folder, f"{db_name}_dump.sql")
                dump_file_gz = f"{dump_file}.gz"

                if os.path.exists(dump_file):
                    try:
                        os.remove(dump_file)
                    except OSError as e:
                        self.stderr.write(
                            self.style.WARNING(
                                f"Could not remove existing file {dump_file}: {e}"
                            )
                        )
                if os.path.exists(dump_file_gz):
                    try:
                        os.remove(dump_file_gz)
                    except OSError as e:
                        self.stderr.write(
                            self.style.WARNING(
                                f"Could not remove existing file {dump_file_gz}: {e}"
                            )
                        )

                dump_cmd = [
                    "mysqldump",
                    f"--host={host}",
                    f"--port={port}",
                    f"--user={user}",
                    "--skip-lock-tables",
                    "--no-tablespaces",
                    "--single-transaction",
                    "--skip-events",
                    "--skip-routines",
                    "--skip-triggers",
                    "--max-allowed-packet=1G",
                    # '--column-statistics=0', # Add if using MySQL 8+ and encountering issues
                    db_name,
                ]

                dump_env = os.environ.copy()
                dump_env["MYSQL_PWD"] = password

                process = None
                try:
                    with open(dump_file, "wb") as f_out:
                        process = subprocess.Popen(
                            dump_cmd,
                            stdout=f_out,
                            stderr=subprocess.PIPE,
                            env=dump_env,
                        )

                        try:
                            stdout_data, stderr_data = process.communicate(timeout=3600)
                            stderr_msg = stderr_data.decode(errors="replace").strip()

                            if process.returncode != 0:
                                self.stderr.write(
                                    self.style.ERROR(
                                        f"Error dumping {db_name} (return code {process.returncode}): {stderr_msg}"
                                    )
                                )
                                overall_success = False
                                continue

                            if stderr_msg:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f"mysqldump warnings for {db_name}: {stderr_msg}"
                                    )
                                )

                        except subprocess.TimeoutExpired:
                            self.stderr.write(
                                self.style.ERROR(
                                    f"mysqldump for {db_name} timed out after 3600 seconds. Terminating process."
                                )
                            )
                            try:
                                process.terminate()
                                time.sleep(2)
                                if process.poll() is None:
                                    process.kill()
                                    self.stderr.write(
                                        self.style.WARNING(
                                            f"mysqldump process for {db_name} killed forcefully."
                                        )
                                    )

                            except (
                                ProcessLookupError,
                                PermissionError,
                                AttributeError,
                            ) as kill_err:
                                self.stderr.write(
                                    self.style.WARNING(
                                        f"Could not terminate timed-out process {process.pid}: {kill_err}"
                                    )
                                )
                            overall_success = False
                            continue

                    if not os.path.exists(dump_file) or os.path.getsize(dump_file) == 0:
                        if process and process.returncode == 0:
                            self.stderr.write(
                                self.style.ERROR(
                                    f"mysqldump for {db_name} reported success but output file is missing or empty."
                                )
                            )

                        overall_success = False
                        if os.path.exists(dump_file):
                            try:
                                os.remove(dump_file)
                            except OSError as e:
                                self.stderr.write(
                                    self.style.WARNING(
                                        f"Could not remove empty dump file {dump_file}: {e}"
                                    )
                                )
                        continue

                    self.stdout.write(f"Compressing {dump_file}...")
                    compress_cmd = ["gzip", "-f", dump_file]
                    compress_proc = subprocess.run(
                        compress_cmd, capture_output=True, text=True, check=False
                    )  # check=False allows checking returncode manually

                    if compress_proc.returncode != 0:
                        self.stderr.write(
                            self.style.ERROR(
                                f"Failed to compress {dump_file} (return code {compress_proc.returncode}): {compress_proc.stderr}"
                            )
                        )
                        overall_success = False
                        self.stdout.write(
                            self.style.WARNING(f"Kept uncompressed file: {dump_file}")
                        )
                        continue
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Successfully backed up and compressed {db_name} to {dump_file_gz}"
                            )
                        )

                except FileNotFoundError as fnf_error:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Command not found during backup of {db_name}: {fnf_error}. Make sure mysqldump and gzip are installed and in the system PATH."
                        )
                    )
                    overall_success = False
                    return False
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Unexpected error during backup processing of {db_name}: {str(e)}"
                        )
                    )
                    if os.path.exists(dump_file) and not os.path.exists(dump_file_gz):
                        try:
                            os.remove(dump_file)
                        except OSError as e_rm:
                            self.stderr.write(
                                self.style.WARNING(
                                    f"Could not remove intermediate dump file {dump_file}: {e_rm}"
                                )
                            )
                    overall_success = False
                    continue

        except MySQLdb.Error as db_err:
            self.stderr.write(
                self.style.ERROR(f"Database connection or query error: {db_err}")
            )
            return False
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(
                    f"An unexpected error occurred during database backup setup: {str(e)}"
                )
            )
            return False
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            self.stdout.write("Database connection closed.")

        return overall_success

    def download_osf_repository(
        self, backup_folder, interactive, single_file_mode=False
    ):
        """
        Download the OSF repository using either:
        - Hybrid approach (default): Download raw_data and processed_data folders as ZIP archives, other files individually
        - Single file mode: Download all files individually without using ZIP archives (if single_file_mode=True)
        """
        method_str = "single file" if single_file_mode else "hybrid"
        self.stdout.write(f"Starting OSF repository backup ({method_str} method)...")

        if interactive:
            confirm = input(
                f"Proceed with backup of OSF repository using {method_str} approach? (Y/n): "
            )
            if confirm.lower() not in ("", "y", "yes"):
                self.stdout.write(
                    self.style.WARNING("OSF repository backup cancelled by user.")
                )
                return False

        osf_node_id = os.environ.get("OSF_NODE_ID", None)
        if not osf_node_id:
            self.stderr.write(
                self.style.ERROR("OSF_NODE_ID environment variable not set.")
            )
            return False
        base_url = f"https://api.osf.io/v2/nodes/{osf_node_id}/files/osfstorage/"

        session = requests.Session()

        stats = {
            "files_downloaded": 0,
            "directories_created": 0,
            "zips_downloaded": 0,
            "total_bytes": 0,
            "errors": 0,
        }

        def get_all_items(url, max_retries=10, retry_delay=10):
            """Fetch all items from a paginated API endpoint"""

            all_items = []
            next_url = url

            # Add query parameter for sorting because of weird osf bugs (the api will return incorrect listings if we don't do this)
            sort_param = "sort=name"
            if "?" in next_url:
                if "sort=" not in next_url:
                    next_url += f"&{sort_param}"
            else:
                next_url += f"?{sort_param}"

            while next_url:
                self.stdout.write(f"Fetching directory contents: {next_url}")

                content = None
                for attempt in range(1, max_retries + 1):
                    try:
                        response = session.get(next_url)
                        response.raise_for_status()
                        content = response.json()
                        break
                    except requests.exceptions.RequestException as e:
                        if attempt == max_retries:
                            self.stderr.write(
                                self.style.ERROR(
                                    f"Failed to access OSF API endpoint {next_url} after {max_retries} attempts: {str(e)}"
                                )
                            )
                            raise
                        self.stdout.write(
                            f"API retry attempt {attempt}/{max_retries} for {next_url} after error: {str(e)}. Waiting {retry_delay} seconds..."
                        )
                        time.sleep(retry_delay)

                if content is None:
                    return []

                if "data" in content and content["data"]:
                    for item in content["data"]:
                        attributes = item.get("attributes", {})
                        relationships = item.get("relationships", {})
                        links = item.get("links", {})

                        item_data = {
                            "name": attributes.get("name", "UnknownName"),
                            "kind": attributes.get("kind", ""),
                            "size": attributes.get("size"),
                            "id": item.get("id", ""),
                            "path": attributes.get("path", ""),
                            "materialized_path": attributes.get(
                                "materialized_path", ""
                            ),
                        }

                        # Add related files URL for folders
                        files_rel = (
                            relationships.get("files", {})
                            .get("links", {})
                            .get("related", {})
                        )
                        if files_rel and "href" in files_rel:
                            item_data["files_url"] = files_rel["href"]

                        # Add download URL for files
                        if "download" in links:
                            item_data["download_url"] = links["download"]

                        all_items.append(item_data)

                next_url = None
                if (
                    "links" in content
                    and "next" in content["links"]
                    and content["links"]["next"]
                ):
                    next_url = content["links"]["next"]

            return all_items

        def download_file(
            url, dest_path, expected_size=None, max_retries=10, retry_delay=10
        ):
            """Download a single file with retry logic and progress"""
            folder_path = os.path.dirname(dest_path)
            try:
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path, exist_ok=True)
                    stats["directories_created"] += 1
            except OSError as e:
                self.stderr.write(
                    self.style.ERROR(f"Failed to create directory {folder_path}: {e}")
                )
                stats["errors"] += 1
                return False

            for attempt in range(1, max_retries + 1):
                try:
                    with session.get(url, stream=True, timeout=3600) as response:
                        response.raise_for_status()
                        # Use Content-Length header, but fallback to expected_size if available
                        total_size = int(response.headers.get("content-length", 0))
                        if total_size == 0 and expected_size is not None:
                            total_size = expected_size

                        if not self.check_disk_space(backup_folder, total_size):
                            stats["errors"] += 1
                            return False

                        file_name = os.path.basename(dest_path)
                        size_mb = total_size / 1024 / 1024 if total_size else 0
                        self.stdout.write(
                            f"Downloading: {file_name} ({size_mb:.2f} MB)"
                        )

                        with (
                            open(dest_path, "wb") as f,
                            tqdm(
                                total=total_size,
                                unit="B",
                                unit_scale=True,
                                unit_divisor=1024,
                                desc=file_name,
                                leave=False,
                            ) as pbar,
                        ):
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    pbar.update(len(chunk))

                        actual_size = os.path.getsize(dest_path)
                        if total_size > 0 and actual_size != total_size:
                            self.stderr.write(
                                self.style.WARNING(
                                    f"Warning: Downloaded size mismatch for {file_name}. Expected {total_size}, got {actual_size} bytes."
                                )
                            )

                        stats["files_downloaded"] += 1
                        stats["total_bytes"] += actual_size
                        return True

                except requests.exceptions.RequestException as e:
                    if attempt == max_retries:
                        self.stderr.write(
                            self.style.ERROR(
                                f"Failed to download file {os.path.basename(dest_path)} after {max_retries} attempts: {str(e)}"
                            )
                        )
                        stats["errors"] += 1
                        if os.path.exists(dest_path):
                            try:
                                os.remove(dest_path)
                            except OSError as e_rm:
                                self.stderr.write(
                                    self.style.WARNING(
                                        f"Could not remove partial file {dest_path}: {e_rm}"
                                    )
                                )
                        return False
                    self.stdout.write(
                        f"Download retry attempt {attempt}/{max_retries} for {os.path.basename(dest_path)} after error: {str(e)}. Waiting {retry_delay} seconds..."
                    )
                    time.sleep(retry_delay)
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Unexpected error downloading file {os.path.basename(dest_path)}: {str(e)}"
                        )
                    )
                    stats["errors"] += 1
                    if os.path.exists(dest_path):
                        try:
                            os.remove(dest_path)
                        except OSError as e_rm:
                            self.stderr.write(
                                self.style.WARNING(
                                    f"Could not remove partial file {dest_path}: {e_rm}"
                                )
                            )
                    return False

            return False

        def download_folder_as_zip(
            folder_id, folder_name, local_path, max_retries=10, retry_delay=10
        ):
            """Download a specific OSF folder as a ZIP file"""
            zip_url = f"https://files.osf.io/v1/resources/{osf_node_id}/providers/osfstorage/{folder_id}/?zip="
            zip_dest_folder = os.path.dirname(local_path)
            zip_path = os.path.join(zip_dest_folder, f"{folder_name}.zip")

            try:
                if not os.path.exists(zip_dest_folder):
                    os.makedirs(zip_dest_folder, exist_ok=True)
            except OSError as e:
                self.stderr.write(
                    self.style.ERROR(
                        f"Failed to create directory {zip_dest_folder} for ZIP download: {e}"
                    )
                )
                stats["errors"] += 1
                return False

            self.stdout.write(
                f"Attempting to download folder '{folder_name}' as ZIP archive..."
            )

            for attempt in range(1, max_retries + 1):
                try:
                    with session.get(
                        zip_url, stream=True, timeout=3600
                    ) as response:  # Longer timeout for zipping
                        response.raise_for_status()
                        total_size = int(response.headers.get("content-length", 0))

                        if not self.check_disk_space(backup_folder, total_size):
                            stats["errors"] += 1
                            return False

                        size_mb = total_size / 1024 / 1024 if total_size else 0
                        self.stdout.write(
                            f"Downloading: {folder_name}.zip ({size_mb:.2f} MB)"
                        )

                        with (
                            open(zip_path, "wb") as f,
                            tqdm(
                                total=total_size,
                                unit="B",
                                unit_scale=True,
                                unit_divisor=1024,
                                desc=f"{folder_name}.zip",
                                leave=False,
                            ) as pbar,
                        ):
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    pbar.update(len(chunk))

                        actual_size = os.path.getsize(zip_path)
                        if total_size > 0 and actual_size != total_size:
                            self.stderr.write(
                                self.style.WARNING(
                                    f"Warning: Downloaded size mismatch for {folder_name}.zip. Expected {total_size}, got {actual_size} bytes."
                                )
                            )

                        stats["zips_downloaded"] += 1
                        stats["total_bytes"] += actual_size
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Successfully downloaded {folder_name}.zip to {zip_path}"
                            )
                        )
                        return True

                except requests.exceptions.RequestException as e:
                    if attempt == max_retries:
                        self.stderr.write(
                            self.style.ERROR(
                                f"Failed to download ZIP for {folder_name} after {max_retries} attempts: {str(e)}"
                            )
                        )
                        stats["errors"] += 1
                        if os.path.exists(zip_path):
                            try:
                                os.remove(zip_path)
                            except OSError as e_rm:
                                self.stderr.write(
                                    self.style.WARNING(
                                        f"Could not remove partial zip file {zip_path}: {e_rm}"
                                    )
                                )
                        return False
                    self.stdout.write(
                        f"ZIP download retry attempt {attempt}/{max_retries} for {folder_name} after error: {str(e)}. Waiting {retry_delay} seconds..."
                    )
                    time.sleep(retry_delay)
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Unexpected error downloading ZIP for {folder_name}: {str(e)}"
                        )
                    )
                    stats["errors"] += 1
                    if os.path.exists(zip_path):
                        try:
                            os.remove(zip_path)
                        except OSError as e_rm:
                            self.stderr.write(
                                self.style.WARNING(
                                    f"Could not remove partial zip file {zip_path}: {e_rm}"
                                )
                            )
                    return False

            return False

        def process_folder_contents(api_url, current_local_path):
            """
            Process items within a folder: download files, recurse into subfolders,
            or download specific folders as ZIPs based on single_file_mode and folder name.
            Returns True if processing completed without fatal errors for this level, False otherwise.
            """
            overall_success = True
            try:
                items = get_all_items(api_url)
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"Could not retrieve contents for {api_url}: {e}")
                )
                stats["errors"] += 1
                return False

            for item in items:
                item_name = item["name"]
                item_local_path = os.path.join(current_local_path, item_name)
                item_kind = item.get("kind")

                if item_kind == "folder":
                    should_zip = (
                        not single_file_mode
                        and item_name
                        in ["raw_data", "processed_data"]
                        and "id" in item
                        and item["id"]
                    )

                    if should_zip:
                        self.stdout.write(
                            f"Found folder '{item_name}' eligible for ZIP download."
                        )
                        success = download_folder_as_zip(
                            item["id"], item_name, item_local_path
                        )
                        if not success:
                            self.stderr.write(
                                self.style.WARNING(
                                    f"Failed to download '{item_name}' as ZIP. Skipping folder."
                                )
                            )
                            overall_success = False
                    else:
                        self.stdout.write(f"Processing subfolder: {item_name}")
                        try:
                            if not os.path.exists(item_local_path):
                                os.makedirs(item_local_path, exist_ok=True)
                                stats["directories_created"] += 1
                        except OSError as e:
                            self.stderr.write(
                                self.style.ERROR(
                                    f"Failed to create directory {item_local_path} for subfolder processing: {e}"
                                )
                            )
                            stats["errors"] += 1
                            overall_success = False
                            continue

                        if "files_url" in item:
                            success = process_folder_contents(
                                item["files_url"], item_local_path
                            )
                            if not success:
                                overall_success = (
                                    False
                                )
                        else:
                            self.stderr.write(
                                self.style.WARNING(
                                    f"Folder '{item_name}' has no 'files_url'. Cannot process contents."
                                )
                            )

                elif item_kind == "file":
                    if "download_url" in item:
                        success = download_file(
                            item["download_url"], item_local_path, item.get("size")
                        )
                        if not success:
                            overall_success = (
                                False
                            )
                    else:
                        self.stderr.write(
                            self.style.WARNING(
                                f"File '{item_name}' has no download URL. Skipping."
                            )
                        )

                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping unknown item kind '{item_kind}' for item '{item_name}'"
                        )
                    )

            return overall_success

        start_time = time.time()

        overall_osf_success = process_folder_contents(base_url, backup_folder)

        end_time = time.time()
        duration_minutes = (end_time - start_time) / 60

        if overall_osf_success and stats["errors"] == 0:
            result_style = self.style.SUCCESS
            completion_status = "completed successfully"
        else:
            result_style = (
                self.style.WARNING if overall_osf_success else self.style.ERROR
            )
            completion_status = (
                f"finished with {stats['errors']} error(s)"
                if stats["errors"] > 0
                else "failed"
            )

        if single_file_mode:
            summary = (
                f"OSF repository backup ({method_str} method) {completion_status} in {duration_minutes:.2f} minutes. "
                f"Downloaded {stats['files_downloaded']} individual files "
                f"({stats['total_bytes'] / 1024 / 1024:.2f} MB) "
                f"into {stats['directories_created']} directories."
            )
        else:
            summary = (
                f"OSF repository backup ({method_str} method) {completion_status} in {duration_minutes:.2f} minutes. "
                f"Downloaded {stats['files_downloaded']} individual files and "
                f"{stats['zips_downloaded']} folders as ZIPs "
                f"({stats['total_bytes'] / 1024 / 1024:.2f} MB). "
                f"Created {stats['directories_created']} directories (excluding zipped content)."
            )

        self.stdout.write(result_style(summary))

        return overall_osf_success


    def manage_s3_backups(self, s3_client, bucket, keep_last):
        if keep_last <= 0:
            self.stdout.write(
                self.style.WARNING(
                    "S3 backup retention (BACKUP_KEEP_LAST) is disabled or invalid (<=0). Skipping cleanup."
                )
            )
            return

        self.stdout.write(
            f"Managing S3 backups in bucket '{bucket}' (keeping last {keep_last})..."
        )
        prefix = "peekbank_backup_"

        try:
            paginator = s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

            backups = []
            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        if obj["Key"].startswith(prefix) and obj["Key"].endswith(
                            ".zip"
                        ):
                            backups.append(obj)

            if not backups:
                self.stdout.write(
                    f"No existing backups found in S3 with prefix '{prefix}'."
                )
                return
            
            backups.sort(key=lambda x: x["LastModified"])

            num_backups = len(backups)
            if num_backups > keep_last:
                num_to_delete = num_backups - keep_last
                backups_to_delete = backups[:num_to_delete]

                self.stdout.write(
                    f"Found {num_backups} backups. Will delete {num_to_delete} oldest backups."
                )

                keys_to_delete = [{"Key": obj["Key"]} for obj in backups_to_delete]

                for i in range(0, len(keys_to_delete), 1000):
                    chunk = keys_to_delete[i : i + 1000]
                    delete_payload = {"Objects": chunk}
                    self.stdout.write(f"Deleting batch of {len(chunk)} backups...")
                    response = s3_client.delete_objects(
                        Bucket=bucket, Delete=delete_payload
                    )

                    deleted_keys = [obj["Key"] for obj in response.get("Deleted", [])]
                    errors = response.get("Errors", [])

                    for key in deleted_keys:
                        self.stdout.write(f"Deleted old backup from S3: {key}")

                    if errors:
                        self.stderr.write(
                            self.style.WARNING("Errors occurred during S3 deletion:")
                        )
                        for error in errors:
                            self.stderr.write(
                                f"  - Key: {error['Key']}, Code: {error['Code']}, Message: {error['Message']}"
                            )
            else:
                self.stdout.write(
                    f"Found {num_backups} backups. No old backups to delete (keeping {keep_last})."
                )

        except ClientError as e:
            self.stderr.write(self.style.WARNING(f"Error managing S3 backups: {e}"))
        except Exception as e:
            self.stderr.write(
                self.style.WARNING(
                    f"An unexpected error occurred during S3 backup management: {e}"
                )
            )
