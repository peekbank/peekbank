import os
import subprocess
import json
import traceback
from django.core.management.base import BaseCommand
from django.conf import settings
from dotenv import load_dotenv
from collections import defaultdict
import pandas as pd
import numpy as np
from django.db import reset_queries
from datetime import datetime
import db.models

from tqdm import tqdm



def getDictsWithKeyForValue(dict_list, key, value):
    rv = []
    for item in dict_list:
        if item[key] == value:
            rv.append(item)
    return rv


def CSV_to_Django(validate_only, bulk_args, data_folder, schema, dataset_type, offsets, dependencies=None, optional=False):
    class_names = dict([(x['table'],x['model_class']) for x in schema])
    table_names = dict([(x['model_class'],x['table']) for x in schema])

    csv_path = os.path.join(data_folder, f"{dataset_type}.csv")
    
    if not os.path.exists(csv_path):
        if optional:
            return None
        error_msg = f"{csv_path} is missing; aborting."
        print(error_msg)
        raise ValueError(error_msg)
    

    print('Processing '+dataset_type+'...')
    df = pd.read_csv(csv_path)        
    df = df.replace({np.nan:None})

    # need to make sure any JSON are cast as such here right here        

    class_def = getDictsWithKeyForValue(schema, "model_class", class_names[dataset_type])[0]
    primary_key = [x for x in class_def['fields'] if 'primary_key' in x['options']][0]['field_name']

    fields_required_by_schema = [x['field_name'] for x in class_def['fields']]

    missing_fields = set(fields_required_by_schema)  - set(df.columns) 
    if len(missing_fields) > 0:
        raise ValueError('Fields are missing from '+csv_path+': '+'; '.join(missing_fields)) 
    
    extra_fields = set(df.columns) - set(fields_required_by_schema)
    if len(extra_fields) > 0:
        raise ValueError('Extra fields found in '+csv_path+': '+'; '.join(extra_fields)) 
    rdict = {}

    # Find the maximum primary key value in the current table to avoid conflicts
    model_class = getattr(db.models, class_names[dataset_type])
    max_pk_value = 0
    try:
        max_pk_obj = model_class.objects.all().order_by(f'-{primary_key}').first()
        if max_pk_obj:
            max_pk_value = getattr(max_pk_obj, primary_key)
    except Exception as e:
        print(f"Error finding max primary key for {dataset_type}: {str(e)}")
    
    offsets[primary_key] +=  max_pk_value

    for record in df.to_dict('records'):
        record_default = defaultdict(None,record)
        
        payload = {}

        for field in class_def['fields']:                

            if field['field_class'] == 'ForeignKey':
                fk_to_table = table_names[field['options']['to']]
                fk_field = field['field_name']

                if dependencies[fk_to_table] is None:
                    # special case when a fk_to table does not exist, e.g. aoi_region_sets
                    payload[fk_field] = None
                else:
                    if fk_field in ('distractor_id', 'target_id'):
                        # special case where the pk of the destination/to table is different than the local key (trials -> stimulis)
                        fk_remap = "stimulus_id"
                    else:
                        fk_remap = fk_field

                    payload[fk_field] = dependencies[fk_to_table][record_default[fk_field] + offsets[fk_remap]]
                    
            else:                    
                # cast any aux fields to JSON
                if 'aux' in field['field_name'] and record_default[field['field_name']] is not None:
                    payload[field['field_name']] = json.loads(record_default[field['field_name']])
                    if dataset_type in ('administrations', 'subjects'):                            
                        validate_aux_data(payload[field['field_name']])                        

                # in most cases, just propagte the field
                elif field['field_name'] in record_default:
                    payload[field['field_name']] = record_default[field['field_name']]                    
                else:                    
                    # if it's in one of the aux's, populate the field with None
                    raise ValueError('No value found for field '+field['field_name']+". Make sure that this field is populated. Aborting processing this dataset.")

        # Add the offset to the primary key
        payload[primary_key] += offsets[primary_key]

        data_model = getattr(db.models, class_names[dataset_type])
        rdict[payload[primary_key]] = data_model(**payload)

    if not validate_only:
        bulk_args.append((class_names[dataset_type], rdict))
    
    return(rdict)


def bulk_create_tables(bulk_args):
    total_records = sum(len(rdict) for _, rdict in bulk_args)
    
    with tqdm(total=total_records, desc="Creating records", unit="record", leave=True) as pbar:
        for class_name, rdict in bulk_args:
            records = list(rdict.values())
            batch_size = 1000
            
            # Process in batches to update the progress bar
            for i in range(0, len(records), batch_size):
                batch = records[i:i+batch_size]
                getattr(db.models, class_name).objects.bulk_create(batch)
                
                pbar.update(min(batch_size, len(records) - i))


def validate_aux_data(aux_json):
    # maybe rethink this coupling in the future (move this to a schema so that the R validator already captures it)
    allowed_aux_data_properties = [
        "cdi_responses",
        "lang_measures",
        "lang_exposures",
        "full_phrase_language_non_iso",
        "native_language_non_iso",
        "lab_visit_num",
    ]
    extra_keys = set(aux_json.keys()) - set(allowed_aux_data_properties)

    if len(extra_keys) > 0:
        raise ValueError("Other JSON fields found: " + " ".join(extra_keys))

    if "cdi_responses" in aux_json.keys():
        for r in aux_json["cdi_responses"]:
            assert (
                len(
                    set(["instrument_type", "age", "rawscore", "language"]).difference(
                        set(r.keys())
                    )
                )
                == 0
            )
            assert r["instrument_type"] in ["wg", "ws", "wsshort", "wgshort"]
            assert isinstance(r["age"], (int, float))
            assert isinstance(r["rawscore"], int)
            if "percentile" in r.keys():
                assert isinstance(r["percentile"], (int, float))
            assert isinstance(r["language"], str)


def create_data_tables(processed_data_folders, schema, validate_only, keep):
    completion_reports = []

    for data_folder in tqdm(processed_data_folders, desc="Processing datasets", unit="dataset"):
        completion_report = {}
        # check if we need to process it
        dataset_df = pd.read_csv(os.path.join(data_folder, "datasets.csv"))
        if "dataset_name" not in dataset_df.columns:
            # bail! We cannot do anything without this
            completion_report = {"dataset_name": "No dataset name: " + data_folder}
            completion_report["aoi_region_sets"] = "Cannot evaluate"
            completion_report["subjects"] = "Cannot evaluate"
            completion_report["datasets"] = "Cannot evaluate"
            completion_report["administrations"] = "Cannot evaluate"
            completion_report["stimuli"] = "Cannot evaluate"
            completion_report["trial_types"] = "Cannot evaluate"
            completion_report["trials"] = "Cannot evaluate"
            completion_report["aoi_timepoints"] = "Cannot evaluate"
            completion_report["xy_timepoints"] = "Cannot evaluate"

            completion_reports.append(completion_report)
            continue

        else:
            dataset_name = dataset_df.iloc[0].dataset_name
            completion_report["dataset_name"] = dataset_name

        print(f"\n\nDataset: {dataset_name}")
        # pre-compute the offsets for all tables so that the indexing can be consistent
        # offsets: pk for each table -> offset value, dataset_id -> 59
        table_names = dict([(x["model_class"], x["table"]) for x in schema])
        offsets = {}
        for class_name in table_names.keys():
            class_def = getDictsWithKeyForValue(schema, "model_class", class_name)[0]

            primary_key = [
                x for x in class_def["fields"] if "primary_key" in x["options"]
            ][0]["field_name"]
            offset_value = getattr(db.models, class_name).objects.count()
            offsets[primary_key] = offset_value + (1 if keep else 0)

        bulk_args = []

        # >>> TODO: put the code below in an iterator that whines about what went wrong and continues to run the other import tasks (both within dataset and across datasets)
        try:
            aoi_region_sets = CSV_to_Django(
                validate_only,
                bulk_args,
                data_folder,
                schema,
                "aoi_region_sets",
                offsets,
                optional=True,
            )
            completion_report["aoi_region_sets"] = "passed"
            if aoi_region_sets is not None:
                completion_report["num_records_aoi_region_sets"] = len(aoi_region_sets)
            else:
                completion_report["num_records_aoi_region_sets"] = 0

        except Exception:
            completion_report["aoi_region_sets"] = traceback.format_exc()
            completion_report["num_records_aoi_region_sets"] = "Cannot evaluate"

        try:
            datasets = CSV_to_Django(
                validate_only, bulk_args, data_folder, schema, "datasets", offsets
            )
            completion_report["datasets"] = "passed"

            if datasets is not None:
                completion_report["num_records_datasets"] = len(datasets)
            else:
                completion_report["num_records_datasets"] = 0

        except Exception:
            completion_report["datasets"] = traceback.format_exc()
            completion_report["num_records_datasets"] = "Cannot evaluate"

        try:
            subjects = CSV_to_Django(
                validate_only,
                bulk_args,
                data_folder,
                schema,
                "subjects",
                offsets,
                dependencies={"datasets": datasets},
            )
            completion_report["subjects"] = "passed"
            if subjects is not None:
                completion_report["num_records_subjects"] = len(subjects)
            else:
                completion_report["num_records_subjects"] = 0

            completion_report["num_subjects_with_cdis"] = len(
                [
                    "cdi_responses" in x.subject_aux_data
                    for x in subjects.values()
                    if x.subject_aux_data is not None
                ]
            )

        except Exception:
            completion_report["subjects"] = traceback.format_exc()
            completion_report["num_records_subjects"] = "Cannot evaluate"

        try:
            administrations = CSV_to_Django(
                validate_only,
                bulk_args,
                data_folder,
                schema,
                "administrations",
                offsets,
                dependencies={"subjects": subjects, "datasets": datasets},
            )
            completion_report["administrations"] = "passed"
            if administrations is not None:
                completion_report["num_records_administrations"] = len(administrations)
            else:
                completion_report["num_records_administrations"] = 0

            completion_report["num_admins_with_cdis"] = len(
                [
                    "cdi_responses" in x.administration_aux_data[0]
                    for x in administrations.values()
                    if x.administration_aux_data is not None
                ]
            )

        except Exception:
            completion_report["administrations"] = traceback.format_exc()
            completion_report["num_records_administrations"] = "Cannot evaluate"

        try:
            stimuli = CSV_to_Django(
                validate_only,
                bulk_args,
                data_folder,
                schema,
                "stimuli",
                offsets,
                dependencies={"datasets": datasets},
            )
            completion_report["stimuli"] = "passed"
            if stimuli is not None:
                completion_report["num_records_stimuli"] = len(stimuli)
            else:
                completion_report["num_records_stimuli"] = 0
                completion_report["num_records_stimuli"] = "Cannot evaluate"

        except Exception:
            completion_report["stimuli"] = traceback.format_exc()

        try:
            trial_types = CSV_to_Django(
                validate_only,
                bulk_args,
                data_folder,
                schema,
                "trial_types",
                offsets,
                dependencies={
                    "datasets": datasets,
                    "aoi_region_sets": aoi_region_sets,
                    "stimuli": stimuli,
                },
            )
            completion_report["trial_types"] = "passed"
            if trial_types is not None:
                completion_report["num_records_trial_types"] = len(trial_types)
            else:
                completion_report["num_records_trial_types"] = 0
        except Exception:
            completion_report["trial_types"] = traceback.format_exc()
            completion_report["num_records_trial_types"] = "Cannot evaluate"

        try:
            trials = CSV_to_Django(
                validate_only,
                bulk_args,
                data_folder,
                schema,
                "trials",
                offsets,
                dependencies={
                    "datasets": datasets,
                    "aoi_region_sets": aoi_region_sets,
                    "stimuli": stimuli,
                    "trial_types": trial_types,
                },
            )
            completion_report["trials"] = "passed"
            if trials is not None:
                completion_report["num_records_trials"] = len(trials)
            else:
                completion_report["num_records_trials"] = 0

        except Exception:
            completion_report["trials"] = traceback.format_exc()
            completion_report["num_records_trials"] = "Cannot evaluate"

        try:
            aoi_timepoints = CSV_to_Django(
                validate_only,
                bulk_args,
                data_folder,
                schema,
                "aoi_timepoints",
                offsets,
                dependencies={
                    "subjects": subjects,
                    "trials": trials,
                    "administrations": administrations,
                },
            )
            completion_report["aoi_timepoints"] = "passed"
            if aoi_timepoints is not None:
                completion_report["num_records_aoi_timepoints"] = len(aoi_timepoints)
            else:
                completion_report["num_records_aoi_timepoints"] = 0

        except Exception:
            completion_report["aoi_timepoints"] = traceback.format_exc()
            completion_report["num_records_aoi_timepoints"] = "Cannot evaluate"

        try:
            xy_timepoints = CSV_to_Django(
                validate_only,
                bulk_args,
                data_folder,
                schema,
                "xy_timepoints",
                offsets,
                dependencies={
                    "subjects": subjects,
                    "trials": trials,
                    "administrations": administrations,
                },
                optional=True,
            )
            completion_report["xy_timepoints"] = "passed"
            if xy_timepoints is not None:
                completion_report["num_records_xy_timepoints"] = len(xy_timepoints)
            else:
                completion_report["num_records_xy_timepoints"] = 0

        except Exception:
            completion_report["xy_timepoints"] = traceback.format_exc()
            completion_report["num_records_xy_timepoints"] = "Cannot evaluate"

        if not validate_only:
            bulk_create_tables(bulk_args)
            reset_queries()
        else:
            print("Ran in validation mode, nothing written to the database.")

        completion_reports.append(completion_report)

    print("Generating a completion report...")
    completion_df = pd.DataFrame(completion_reports)

    load_dotenv()
    data_dir = "peekbank-data"
    if "PEEKBANK_DATA_PATH" in os.environ:
        data_dir = os.environ["PEEKBANK_DATA_PATH"]
    completion_dir = os.path.join(data_dir, "completion_reports")
    if not os.path.exists(completion_dir):
        os.makedirs(completion_dir)

    now = datetime.now()
    current_date_time = now.strftime("%Y-%m-%d-_%H_%M_%S")
    completion_df.to_csv(
        os.path.join(completion_dir, "completion_report_" + current_date_time + ".csv")
    )


def process_peekbank_dirs(data_root, validate_only, datasets=None, keep=False):
    schema = json.load(open(settings.SCHEMA_FILE))

    if not os.path.exists(data_root):
        raise ValueError(
            "Path "
            + data_root
            + " does not exist. Make sure you are pointing to the correct directory."
        )

    all_dirs = [x[0] for x in os.walk(data_root)]

    processed_data_folders = [
        x for x in all_dirs if os.path.basename(x) == "processed_data"
    ]
    if len(processed_data_folders) == 0:
        raise ValueError(
            "No folders with processed data found. Do you have the right path?"
        )

    if datasets:
        filtered_folders = []
        for folder in processed_data_folders:
            try:
                dataset_df = pd.read_csv(os.path.join(folder, "datasets.csv"))
                if "dataset_name" in dataset_df.columns:
                    dataset_name = dataset_df.iloc[0].dataset_name
                    if dataset_name in datasets:
                        filtered_folders.append(folder)
            except Exception as e:
                print(f"Error reading dataset info from {folder}: {str(e)}")
                continue

        processed_data_folders = filtered_folders

        if len(processed_data_folders) == 0:
            raise ValueError(
                f"No matching datasets found for the specified dataset names: {datasets}"
            )

    # If keep is True, we need to remove existing datasets before importing
    if keep and not validate_only and datasets:
        dataset_names_to_remove = []
        for folder in processed_data_folders:
            try:
                dataset_df = pd.read_csv(os.path.join(folder, "datasets.csv"))
                if "dataset_name" in dataset_df.columns:
                    dataset_name = dataset_df.iloc[0].dataset_name
                    dataset_names_to_remove.append(dataset_name)
            except Exception as e:
                print(f"Error reading dataset info for removal from {folder}: {str(e)}")
                continue

        for dataset_name in dataset_names_to_remove:
            try:
                dataset = db.models.Dataset.objects.filter(
                    dataset_name=dataset_name
                ).first()
                if dataset:
    
                    dataset_id = dataset.dataset_id

                    print(
                        f"Removing dataset {dataset_name} (ID: {dataset_id}) from database..."
                    )

                    # With ON DELETE CASCADE set up, this will automatically delete all related records
                    dataset.delete()

                    print(f"Dataset {dataset_name} successfully removed.")
            except Exception as e:
                print(f"Error removing dataset {dataset_name}: {str(e)}")
                continue

    create_data_tables(processed_data_folders, schema, validate_only, keep)
    print("Completed processing!")


class Command(BaseCommand):
    help = "Sets up a new Peekbank database and populates it with data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--data_root", help="Root directory where to find data files"
        )
        parser.add_argument(
            "-val",
            "--validate_only",
            action="store_true",
            help="Only validate the data, do not insert into database",
        )
        parser.add_argument(
            "--datasets",
            "-ds",
            nargs="+",
            help="List of dataset names to populate the db with",
        )
        parser.add_argument(
            "--keep",
            "-k",
            action="store_true",
            help="Keep existing datasets, only overwrite specified ones",
        )

    def handle(self, *args, **options):
        
        load_dotenv()

        data_root = options.get("data_root")
        if not data_root:
            data_root = os.environ.get("OSF_DATA_PATH")

        if not data_root:
            self.stderr.write(
                self.style.ERROR(
                    "No data_root specified and OSF_DATA_PATH environment variable not set"
                )
            )
            return

        progress_path = os.path.join(data_root, "osf_download_progress.json")
        if os.path.exists(progress_path):
            raise ValueError("Download of osf data is unfinished. Please complete the download first.")

        validate_only = options.get("validate_only", False)
        datasets = options.get("datasets", None)
        keep = options.get("keep", False)

        db_host = os.environ.get("PEEKBANK_DB_HOST", "localhost")
        db_port = os.environ.get("PEEKBANK_DB_PORT", "3306")
        db_rootpw = os.environ.get("PEEKBANK_DB_ROOTPW", "")
        db_name = os.environ.get("PEEKBANK_DB_NAME", "peekbank_dev")
        db_user = os.environ.get("PEEKBANK_DB_USER", "reader")
        db_password = os.environ.get("PEEKBANK_DB_PASSWORD", "gazeofraccoons")

        
        if validate_only or keep:
            self.stdout.write(self.style.SUCCESS("Keeping existing database..."))
        else:
            self.stdout.write(
                self.style.SUCCESS("Keeping existing database as requested...")
            )
           
            sql_script = f"""
    CREATE USER IF NOT EXISTS '{db_user}'@'%' IDENTIFIED BY '{db_password}';
    DROP DATABASE IF EXISTS {db_name};
    CREATE DATABASE {db_name};
    GRANT ALL PRIVILEGES ON {db_name}.* TO 'root'@'localhost';
    GRANT SELECT ON {db_name}.* TO '{db_user}'@'%';
    """

            self.stdout.write(self.style.SUCCESS("Creating new database..."))
            mysql_cmd = f"mysql --host {db_host} --port {db_port} -uroot -p{db_rootpw}"

            try:
                process = subprocess.Popen(
                    mysql_cmd.split(),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                _, stderr = process.communicate(input=sql_script.encode())

                if process.returncode != 0:
                    self.stderr.write(
                        self.style.ERROR(f"Error executing SQL: {stderr.decode()}")
                    )
                    return
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed to run SQL script: {e}"))
                return

            # Run migrations
            self.stdout.write(self.style.SUCCESS("Enforcing schema..."))
            try:
                subprocess.check_call(["python", "manage.py", "makemigrations", "db"])
                subprocess.check_call(["python", "manage.py", "migrate", "db"])
            except subprocess.CalledProcessError as e:
                self.stderr.write(self.style.ERROR(f"Migration failed: {e}"))
                return
        
        
        self.stdout.write(self.style.SUCCESS("Ingesting the data..."))

        try:
            process_peekbank_dirs(
                data_root, validate_only, datasets=datasets, keep=keep
            )

            if not validate_only:
                subprocess.check_call(["python", "manage.py", "rle_custom_migration"])
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Database population failed: {str(e)}"))
            return

        self.stdout.write(
            self.style.SUCCESS("Database setup and population completed successfully!")
        )
