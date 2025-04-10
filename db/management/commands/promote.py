from django.core.management.base import BaseCommand, CommandError
import os
import subprocess
from django.conf import settings
from dotenv import load_dotenv


class Command(BaseCommand):
    help = "Creates a clone of the development database with a new name"

    def add_arguments(self, parser):
        parser.add_argument(
            "new_version_name",
            help="Name for the new database version",
            required=True
        )

    def handle(self, *args, **options):
        load_dotenv()

        db_host = os.environ.get("PEEKBANK_DB_HOST", "localhost")
        db_port = os.environ.get("PEEKBANK_DB_PORT", "3306")
        db_rootpw = os.environ.get("PEEKBANK_DB_ROOTPW", "")
        source_db = os.environ.get("PEEKBANK_DB_NAME", "peekbank_dev")
        db_user = os.environ.get("PEEKBANK_DB_USER", "reader")

        # Get new database name
        new_version_name = options["new_version_name"]
        
        self.stdout.write(self.style.SUCCESS(f"New Version Name: {new_version_name}"))
        
        temp_dir = os.path.join(settings.BASE_DIR, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        dump_file = os.path.join(temp_dir, f"{source_db}_dump.sql")
        
        self.stdout.write(self.style.SUCCESS("Making local dump of dev db..."))
        try:
            mysqldump_cmd = [
                "mysqldump", 
                "-u", "root", 
                f"-p{db_rootpw}", 
                f"--host={db_host}", 
                f"--port={db_port}", 
                source_db
            ]
            
            with open(dump_file, "w") as f:
                subprocess.run(mysqldump_cmd, stdout=f, check=True)
        except subprocess.CalledProcessError as e:
            raise CommandError(f"Failed to dump database: {e}")
            
        recreate_sql = f"""
DROP DATABASE IF EXISTS `{new_version_name}`;
CREATE DATABASE `{new_version_name}`;
GRANT ALL PRIVILEGES ON `{new_version_name}`.* TO 'root'@'localhost';
GRANT SELECT ON `{new_version_name}`.* TO '{db_user}'@'%';
"""
        
        self.stdout.write(self.style.SUCCESS(f"Recreating peekbank db as {new_version_name}..."))
        
        mysql_cmd = [
            "mysql", 
            "-u", "root", 
            f"-p{db_rootpw}", 
            f"--host={db_host}", 
            f"--port={db_port}",
        ]
        
        try:
            process = subprocess.Popen(
                mysql_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = process.communicate(input=recreate_sql.encode())
            
            if process.returncode != 0:
                raise CommandError(f"Error executing SQL: {stderr.decode()}")
        except Exception as e:
            raise CommandError(f"Failed to create new database: {e}")
        
        self.stdout.write(self.style.SUCCESS(f"Populating {new_version_name} with dev data"))
        try:
            mysql_import_cmd = [
                "mysql", 
                "-u", "root", 
                f"-p{db_rootpw}", 
                f"--host={db_host}", 
                f"--port={db_port}", 
                new_version_name
            ]
            
            with open(dump_file, "r") as f:
                subprocess.run(mysql_import_cmd, stdin=f, check=True)
                
            try:
                os.remove(dump_file)
            except Exception:
                pass
            
        except subprocess.CalledProcessError as e:
            raise CommandError(f"Failed to import data into new database: {e}")
            
        self.stdout.write(
            self.style.SUCCESS(f"Successfully created {new_version_name} database from {source_db}")
        )