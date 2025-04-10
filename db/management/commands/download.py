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


# we could do a lot more explicit error handeling in this file, but the resume functionality makes the thing robust against a lot of problems, so this is not a huge issue

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
            
        print(
            f"no processed_data subfolder exists for {folder['attributes']['name']}"
        )

    def download_processed_data(self, folder, data_root, progress_data):
        folder_path = folder["attributes"]["materialized_path"]
        dataset_name = folder_path.split("/")[1]
        print(f"Now downloading dataset: {dataset_name}")

        progress_data["in_progress"] = dataset_name
        self.save_progress(data_root, progress_data)

        r = requests.get(os.path.join(BASE_OSF_URL, folder["id"], ""))
        response_dict = json.loads(r.content.decode("utf-8"))
        items = response_dict["data"]

        with tqdm(
            total=len(items), desc=f"Files of {dataset_name}", unit="file"
        ) as pbar:
            for item in items:
                if item:
                    materialized_path = item["attributes"]["materialized_path"]
                    file_path = os.path.join(data_root, *materialized_path.split("/"))

                    os.makedirs(os.path.dirname(file_path), exist_ok=True)

                    r = requests.get(item["links"]["download"], stream=True)
                    total_size = int(r.headers.get("content-length", 0))

                    if total_size > 1024 * 1024:  # Only show progress for files > 1MB
                        file_name = os.path.basename(materialized_path)
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
                        with open(file_path, "wb") as fd:
                            fd.write(r.content)

                pbar.update(1)

        # Move dataset from in_progress to completed
        progress_data["completed"].append(dataset_name)
        progress_data["in_progress"] = None
        self.save_progress(data_root, progress_data)

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
        return {"completed": [], "in_progress": None}

    def save_progress(self, data_root, progress_data):
        progress_path = os.path.join(data_root, PROGRESS_FILE)
        with open(progress_path, "w") as f:
            json.dump(progress_data, f, indent=2)

    def handle_unfinished_download(self, data_root, progress_data, non_interactive):
        unfinished_dataset = progress_data["in_progress"]

        if not unfinished_dataset:
            return False

        try:
            shutil.rmtree(os.path.join(data_root, unfinished_dataset))
        except FileNotFoundError:
            pass

        if non_interactive:
            print(
                f"Non-interactive mode: Deleting unfinished dataset {unfinished_dataset}"
            )
            return False

        response = input(
            "Unfinished download detected. Do you want to continue from your previous download? (Y/n): "
        ).lower()

        if response == "" or response == "y" or response == "yes":
            print(
                f"Continuing previous download. Deleting unfinished dataset folder {unfinished_dataset}"
            )
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

        # Check for progress file and handle unfinished downloads
        progress_data = self.load_progress(data_root)
        continue_previous = False

        if progress_data["in_progress"] or progress_data["completed"]:
            continue_previous = self.handle_unfinished_download(
                data_root, progress_data, non_interactive
            )

        if not continue_previous:
            progress_data = self.create_empty_progress()

            if keep_existing:
                print("Keeping existing datasets, only redownloading specified ones")
            else:
                print(f"Removing existing download data from {data_root}")
                # Remove all existing data if --keep is not specified
                try:
                    items = os.listdir(data_root)
                    for item in items:
                        if item == PROGRESS_FILE:
                            continue  # Don't delete progress file yet
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

        if continue_previous and progress_data["completed"]:
            print(
                f"Skipping already downloaded datasets: {', '.join(progress_data['completed'])}"
            )
            folders = [
                folder
                for folder in folders
                if folder["attributes"]["name"] not in progress_data["completed"]
            ]

        with tqdm(
            total=len(folders), desc="Processing folders", unit="folder"
        ) as folder_pbar:
            for folder in folders:
                folder_name = folder["attributes"]["name"]

                # If --keep is specified, check if we should skip this folder
                if keep_existing and datasets and folder_name in datasets:
                    # Delete existing processed data for this dataset if it should be redownloaded
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
                    self.download_processed_data(processed, data_root, progress_data)
                    processed_list.append(processed)
                else:
                    unprocessed_list.append(folder)

                tqdm.write("\n")
                folder_pbar.update(1)

        print("\nDownloaded these processed folders:")
        pprint(
            [
                processed["attributes"]["materialized_path"]
                for processed in processed_list
            ]
        )

        if len(unprocessed_list) > 0:
            print(
                "\nNothing downloaded for these corpora, most likely because they don't have processed_data subfolder."
            )
            pprint([folder["attributes"]["name"] for folder in unprocessed_list])

        # Delete progress file when everything is done
        try:
            os.remove(os.path.join(data_root, PROGRESS_FILE))
        except FileNotFoundError:
            pass
