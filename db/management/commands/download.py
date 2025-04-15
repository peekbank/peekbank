import os
from django.core.management import BaseCommand
import requests
import os.path
import json
import errno
from pprint import pprint
import shutil as shutil
from tqdm import tqdm

from dotenv import load_dotenv


# file system error handeling would be nice (insufficient storage, io errors) but those are not a huge priority right now

load_dotenv()

BASE_OSF_URL = "https://api.osf.io/v2/nodes/pr6wu/files/osfstorage/"
PROGRESS_FILE = "osf_download_progress.json"


class Command(BaseCommand):
    help = "Downloads data from OSF"

    def add_arguments(self, parser):
        parser.add_argument(
            "--data_root", "-dr", help="Root directory to download files into"
        )
        parser.add_argument(
            "--datasets", "-ds", nargs="+", help="List of dataset names to download"
        )
        parser.add_argument(
            "--keep",
            "-k",
            action="store_true",
            help="Keep existing datasets, only redownload specified ones",
        )
        parser.add_argument(
            "--non-interactive",
            "-ni",
            action="store_true",
            help="Run in non-interactive mode without prompting for resuming of previously unfinished download",
        )

    def collect_page(self, url, payload, folders):
        r = requests.get(url, params=payload)
        response = json.loads(r.content.decode("utf-8"))
        folders.extend([folder for folder in response["data"]])
        return response["links"]["next"]

    def gather_folders(self):
        print("Gathering folders....")
        payload = {
            "sort": "name"
        }  # the osf api is broken and will return duplicates when this is missing
        folders = []
        current_link = self.collect_page(BASE_OSF_URL, payload, folders)

        with tqdm(desc="Collecting folder pages", unit="page") as pbar:
            while current_link is not None:
                current_link = self.collect_page(current_link, payload, folders)
                pbar.update(1)

        print("Found the following folders:")
        pprint([folder["attributes"]["materialized_path"] for folder in folders])
        print("\n")
        return folders

    def find_processed_folder(self, folder):
        print(
            "Checking processed_data subfolder for {}".format(
                folder["attributes"]["name"]
            )
        )
        # The empty string in os.path.join is to add a path separator to the end.
        r = requests.get(os.path.join(BASE_OSF_URL, folder["id"], ""))
        response_dict = json.loads(r.content.decode("utf-8"))
        for item in response_dict["data"]:
            if item["attributes"]["name"] == "processed_data":
                print("processed_data subfolder found!")
                return item

        print(f"no processed_data subfolder exists for {folder['attributes']['name']}")

    def download_processed_data(self, folder, data_root, progress_data):
        folder_path = folder["attributes"]["materialized_path"]
        dataset_name = folder_path.split("/")[1]
        print(f"Now downloading dataset: {dataset_name}")

        progress_data["in_progress"] = dataset_name
        self.save_progress(data_root, progress_data)

        r = requests.get(os.path.join(BASE_OSF_URL, folder["id"], ""))
        
        if not r.ok:
            print(f"Error fetching folder content: HTTP {r.status_code}")
            print(f"Response: {r.text[:200]}...")
            progress_data["in_progress"] = None
            progress_data["failed"].append(dataset_name)
            self.save_progress(data_root, progress_data)
            return False
        
        try:
            response_dict = json.loads(r.content.decode("utf-8"))
            items = response_dict["data"]
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing folder content: {e}")
            print(f"Response: {r.text[:200]}...")
            progress_data["in_progress"] = None
            progress_data["failed"].append(dataset_name)
            self.save_progress(data_root, progress_data)
            return False

        errors = []
        with tqdm(
            total=len(items), desc=f"Files of {dataset_name}", unit="file"
        ) as pbar:
            for item in items:
                if item:
                    materialized_path = item["attributes"]["materialized_path"]
                    file_path = os.path.join(data_root, *materialized_path.split("/"))
                    file_name = os.path.basename(materialized_path)

                    os.makedirs(os.path.dirname(file_path), exist_ok=True)

                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            r = requests.get(
                                item["links"]["download"], 
                                stream=True,
                            )
                            
                            if not r.ok:
                                error_msg = f"HTTP error {r.status_code} for {file_name}: {r.reason}"
                                if attempt < max_retries - 1:
                                    print(f"{error_msg}. Retrying ({attempt+1}/{max_retries})...")
                                    continue
                                else:
                                    errors.append(error_msg)
                                    break
                            
                            content_type = r.headers.get('content-type', '').lower()
                            if 'text/html' in content_type and any(ext in file_name.lower() for ext in ['.csv', '.json', '.txt', '.xlsx']):
                                error_msg = f"Error: Expected data file but got HTML for {file_name}"
                                print(error_msg)
                                if r.content and len(r.content) < 5000:
                                    content_preview = r.content.decode('utf-8', errors='ignore')[:500]
                                    if 'error' in content_preview.lower() or '<!doctype html' in content_preview.lower():
                                        print(f"Error content preview: {content_preview[:200]}...")
                                errors.append(error_msg)
                                break
                            
                            total_size = int(r.headers.get("content-length", 0))

                            if total_size > 1024 * 1024:
                                with open(file_path, "wb") as fd:
                                    with tqdm(
                                        total=total_size,
                                        unit="B",
                                        unit_scale=True,
                                        unit_divisor=1024,
                                        desc=f"Downloading {file_name}",
                                        leave=False,
                                    ) as file_pbar:
                                        for chunk in r.iter_content(chunk_size=4096):
                                            fd.write(chunk)
                                            file_pbar.update(len(chunk))
                            else:
                                content = r.content
                                with open(file_path, "wb") as fd:
                                    fd.write(content)
                                
                                if file_name.lower().endswith('.csv') and len(content) > 0:
                                    try:
                                        text_content = content.decode('utf-8', errors='ignore')
                                        if ('<!doctype html' in text_content.lower() or
                                            '<html' in text_content.lower() or
                                            '<title>' in text_content.lower()):
                                            error_msg = f"Warning: {file_name} appears to be HTML, not CSV"
                                            print(error_msg)
                                            errors.append(error_msg)
                                            error_path = file_path + ".error"
                                            with open(error_path, "wb") as err_fd:
                                                err_fd.write(content)
                                            print(f"Saved error content to {error_path}")
                                    except UnicodeDecodeError:
                                        pass
                            
                            break
                            
                        except requests.exceptions.RequestException as e:
                            error_msg = f"Request error for {file_name}: {str(e)}"
                            if attempt < max_retries - 1:
                                print(f"{error_msg}. Retrying ({attempt+1}/{max_retries})...")
                            else:
                                errors.append(error_msg)
                                print(error_msg)
                
                pbar.update(1)

        if errors:
            print(f"\nWarning: {len(errors)} errors occurred while downloading {dataset_name}:")
            for i, error in enumerate(errors[:5]):
                print(f"  {i+1}. {error}")
            if len(errors) > 5:
                print(f"  ...and {len(errors) - 5} more.")
            
            error_log = os.path.join(data_root, f"{dataset_name}_download_errors.log")
            with open(error_log, "w") as log:
                log.write(f"Download errors for {dataset_name}:\n")
                for error in errors:
                    log.write(f"- {error}\n")
            print(f"Detailed error log written to {error_log}")
            
            progress_data["in_progress"] = None
            progress_data["failed"].append(dataset_name)
            self.save_progress(data_root, progress_data)
            return False

        progress_data["completed"].append(dataset_name)
        progress_data["in_progress"] = None
        self.save_progress(data_root, progress_data)
        return True

    def load_progress(self, data_root):
        progress_path = os.path.join(data_root, PROGRESS_FILE)
        try:
            with open(progress_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            if isinstance(e, json.JSONDecodeError):
                print("Progress file is corrupted. Creating a new one.")
            return self.create_empty_progress()

    def create_empty_progress(self):
        return {"completed": [], "in_progress": None, "failed": []}

    def save_progress(self, data_root, progress_data):
        progress_path = os.path.join(data_root, PROGRESS_FILE)
        with open(progress_path, "w") as f:
            json.dump(progress_data, f, indent=2)

    def handle_unfinished_download(self, data_root, progress_data, non_interactive):
        unfinished_dataset = progress_data["in_progress"]
        failed_datasets = progress_data.get("failed", [])
        
        if unfinished_dataset:
            try:
                shutil.rmtree(os.path.join(data_root, unfinished_dataset))
            except FileNotFoundError:
                pass
        
        if non_interactive:
            if unfinished_dataset:
                print(f"Non-interactive mode: Deleting unfinished dataset {unfinished_dataset}")
            if failed_datasets:
                print(f"Non-interactive mode: Will retry {len(failed_datasets)} failed datasets: {', '.join(failed_datasets)}")
            return True
        
        prompt_parts = []
        
        if failed_datasets:
            prompt_parts.append(f"{len(failed_datasets)} previously failed datasets detected: {', '.join(failed_datasets)}.")
        
        prompt_parts.append("Do you want to continue from your previous download? (Y/n): ")
        response = input(" ".join(prompt_parts)).lower()
        
        if response == "" or response == "y" or response == "yes":
            if unfinished_dataset:
                print(f"Continuing previous download. Deleting unfinished dataset folder {unfinished_dataset}")
            if failed_datasets:
                print(f"Will retry failed datasets: {', '.join(failed_datasets)}")
            return True
        
        print("Starting fresh download")
        return False

    def handle(self, *args, **options):
        data_root = options.get("data_root")
        if not data_root:
            data_root = os.environ["OSF_DATA_PATH"]

        datasets = options.get("datasets")
        keep_existing = options.get("keep")
        non_interactive = options.get("non_interactive")

        print("Called download with target folder " + data_root)
        if datasets:
            print(f"Downloading these datasets: {', '.join(datasets)}")

        os.makedirs(data_root, exist_ok=True)

        progress_data = self.load_progress(data_root)
        continue_previous = False

        if progress_data["in_progress"] or progress_data["completed"] or progress_data.get("failed"):
            continue_previous = self.handle_unfinished_download(
                data_root, progress_data, non_interactive
            )

        if not continue_previous:
            progress_data = self.create_empty_progress()
            self.save_progress(data_root, progress_data)

            if keep_existing:
                print("Keeping existing datasets, only redownloading specified ones")
            else:
                print(f"Removing existing download data from {data_root}")
                try:
                    items = os.listdir(data_root)
                    for item in items:
                        if item == PROGRESS_FILE:
                            continue
                        item_path = os.path.join(data_root, item)
                        try:
                            if os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                            else:
                                os.remove(item_path)
                        except (FileNotFoundError, PermissionError) as e:
                            print(f"Warning: Could not remove {item_path}: {e}")
                    print(f"All data removed from {data_root}")
                except (FileNotFoundError, PermissionError) as e:
                    print(f"Warning: Could not access {data_root}: {e}")

        folders = self.gather_folders()

        if datasets:
            folders = [
                folder for folder in folders if folder["attributes"]["name"] in datasets
            ]
            print(f"Filtered to {len(folders)} datasets based on --datasets parameter")

        processed_list = []
        unprocessed_list = []
        skipped_list = []
        failed_list = []
        folder_map = {folder["attributes"]["name"]: folder for folder in folders}

        
        previously_failed = [dataset for dataset in progress_data.get("failed", []) 
                     if not datasets or dataset in datasets]
        if previously_failed and continue_previous:
            print(f"Will retry {len(previously_failed)} previously failed datasets: {', '.join(previously_failed)}")
            progress_data["failed"] = []
            self.save_progress(data_root, progress_data)

        if continue_previous and progress_data["completed"]:
            for completed_dataset in progress_data["completed"]:
                if completed_dataset in folder_map:
                    skipped_list.append(folder_map[completed_dataset])

            print(
                f"Previously downloaded datasets that will be skipped: {', '.join(progress_data['completed'])}"
            )

            folders_to_process = [
                folder
                for folder in folders
                if folder["attributes"]["name"] not in progress_data["completed"]
            ]
        else:
            folders_to_process = folders

        total_folders = len(folders_to_process) + len(skipped_list)

        with tqdm(
            total=total_folders, desc="Processing folders", unit="folder"
        ) as folder_pbar:
            for skipped_folder in skipped_list:
                folder_name = skipped_folder["attributes"]["name"]
                folder_pbar.update(1)

            for folder in folders_to_process:
                folder_name = folder["attributes"]["name"]

                # If --keep is specified, check if we should skip this folder
                if keep_existing and datasets and folder_name in datasets:
                    materialized_path = folder["attributes"]["materialized_path"]
                    folder_path = os.path.join(
                        data_root, *materialized_path.split("/"), "processed_data"
                    )

                    try:
                        shutil.rmtree(folder_path)
                        print(f"Removing existing data for {folder_name} to redownload")
                    except FileNotFoundError:
                        pass

                processed = self.find_processed_folder(folder)
                if processed:
                    success = self.download_processed_data(processed, data_root, progress_data)
                    if success:
                        processed_list.append(processed)
                    else:
                        failed_list.append(processed)
                else:
                    unprocessed_list.append(folder)

                tqdm.write("\n")
                folder_pbar.update(1)

        if len(skipped_list) > 0:
            print("\nSkipped these already downloaded folders:")
            pprint(
                [skipped["attributes"]["materialized_path"] for skipped in skipped_list]
            )

        print("\nDownloaded these processed folders:")
        pprint(
            [
                processed["attributes"]["materialized_path"]
                for processed in processed_list
            ]
        )
        
        if len(failed_list) > 0:
            print("\nThese folders failed to download:")
            pprint(
                [failed["attributes"]["materialized_path"] for failed in failed_list]
            )

        if len(unprocessed_list) > 0:
            print(
                "\nNothing downloaded for these corpora, most likely because they don't have processed_data subfolder."
            )
            pprint([folder["attributes"]["name"] for folder in unprocessed_list])

        # Only delete progress file if there are no failed datasets
        if not progress_data.get("failed", []):
            try:
                os.remove(os.path.join(data_root, PROGRESS_FILE))
                print("All downloads completed successfully, removing progress file.")
            except FileNotFoundError:
                pass
        else:
            failed_count = len(progress_data.get("failed", []))
            if failed_count > 0:
                print(f"\nKeeping progress file with {failed_count} failed datasets for next run.")
                print(f"Run the command again to retry downloading these datasets: {', '.join(progress_data.get('failed', []))}")