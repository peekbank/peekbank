import glob
import os
#import logging
import django
from django.db.models import Avg, Count, Sum
import pandas as pd
import db.models

def checkForPath(path):
    if os.path.exists(path):
        print(path+ ' found!')
        return(path)
    else:
        return(None)

def create_data_tables(processed_data_folders):

    for data_folder in processed_data_folders: #this for loop needs to be inside the function to allow `continue` when a file is missing


        print('Building AOI region table') # no dependencies
        aoi_regions_csv_path = checkForPath(os.path.join(data_folder, 'aoi_regions.csv'))
        if aoi_regions_csv_path is None:
            print(os.path.join(data_folder, 'aoi_regions.csv')+ ' is missing; allowing for now')
            pass # FIXME: this should fail (continue to next) once the spec has been achieved on the reader; allowing for now
            #continue
        else:
            aoi_region_df = pd.read_csv(aoi_regions_csv_path)
            # offset = AOI_Coordinate_Record.objects.number_that_exist()
            for aoi_region_record in aoi_region_df.to_dict('records'):
                aoi_region = db.models.AOI_Region_Record.objects.create(
                    # aoi_coordinates_id = offset + (aoi_coordinate_record['aoi_coordinates_id'] if 'aoi_coordinates_id' in aoi_coordinate_record else None),
                    aoi_region_id = (aoi_region_record['aoi_region_id'] if 'aoi_region_id' in aoi_region_record else None),
                    l_x_min = (aoi_region_record['l_x_min'] if 'l_x_min' in aoi_region_record else None),
                    l_x_max = (aoi_region_record['l_x_max'] if 'l_x_max' in aoi_region_record else None),
                    l_y_min = (aoi_region_record['l_y_min'] if 'l_y_min' in aoi_region_record else None),
                    l_y_max = (aoi_region_record['l_y_max'] if 'l_y_max' in aoi_region_record else None),
                    r_x_min = (aoi_region_record['r_x_min'] if 'r_x_min' in aoi_region_record else None),
                    r_x_max = (aoi_region_record['r_x_max'] if 'r_x_max' in aoi_region_record else None),
                    r_y_min = (aoi_region_record['r_y_min'] if 'r_y_min' in aoi_region_record else None),
                    r_y_max = (aoi_region_record['r_y_max'] if 'r_y_max' in aoi_region_record else None))

        print('Building Datasets table') # no dependencies
        dataset_csv_path = checkForPath(os.path.join(data_folder, 'datasets.csv'))
        if dataset_csv_path is None:
            print(os.path.join(data_folder, 'dataset.csv')+ ' is missing, aborting....')
            continue
        else:
            dataset_dict = pd.read_csv(dataset_csv_path).to_dict('records')[0]

            dataset = db.models.Dataset_Record.objects.create(
            dataset_id  = (dataset_dict['dataset_id'] if 'dataset_id' in dataset_dict else None),
            lab_dataset_id  = (dataset_dict['dataset_id'] if 'dataset_id' in dataset_dict else None),
            tracker = (dataset_dict['tracker'] if 'target_label' in dataset_dict else None),
            monitor_size_x = (dataset_dict['monitor_size_x'] if 'target_label' in dataset_dict else None),
            monitor_size_y = (dataset_dict['monitor_size_y'] if 'target_label' in dataset_dict else None),
            sample_rate = (dataset_dict['sample_rate'] if 'target_label' in dataset_dict else None))

        print('Building Subjects table') #no dependencies
        subjects_csv_path = checkForPath(os.path.join(data_folder, 'subjects.csv'))
        if subjects_csv_path is None:
            print(os.path.join(data_folder, 'subjects.csv')+ ' is missing, aborting....')
            continue
        else:
            subjects_df = pd.read_csv(subjects_csv_path)
            for subject_record in subjects_df.to_dict('records'):
                subject = db.models.Subject_Record.objects.create(
                    subject_id = (subject_record['subject_id'] if 'subject_id' in subject_record else None),
                    lab_subject_id = (subject_record['subject_id'] if 'subject_id' in subject_record else None),
                    age = (subject_record['age'] if 'age' in subject_record else None),
                    sex = (subject_record['sex'] if 'sex' in subject_record else None)),

        print('Building Trials table') #depends on Datasets
        trials_csv_path = checkForPath(os.path.join(data_folder, 'trials.csv'))
        if trials_csv_path is None:
            print(os.path.join(data_folder, 'trials.csv')+ ' is missing, aborting....')
            continue
        else:

            trial_df = pd.read_csv(trials_csv_path)
            trial_df = trial_df.where((pd.notnull(trial_df)), None)

            for trial_record in trial_df.to_dict('records'):
                trial = db.models.Trial_Record.objects.create(
                    trial_id = (trial_record['trial_id'] if 'trial_id' in trial_record else None),
                    lab_trial_id = (trial_record['trial_id'] if 'trial_id' in trial_record else None),
                    dataset =  db.models.Dataset_Record.objects.get(dataset_id=trial_record['dataset_id']),
                    target_side =  (trial_record['target_side'] if 'target_side' in trial_record else None),
                    target_label =  (trial_record['target_label'] if 'target_label' in trial_record else None),
                    distractor_label =  (trial_record['distractor_label'] if 'distractor_label' in trial_record else None),
                    aoi_region = -1, #db.models.AOI_Region_Record.objects.get(aoi_region_id=trial_record['aoi_region_id']), # FIXME
                    target_image =  (trial_record['target_image'] if 'distractor_label' in trial_record else None),
                    full_phrase =  (trial_record['full_phrase'] if 'full_phrase' in trial_record else None),
                    point_of_disambiguation =  (trial_record['point_of_disambiguation'] if 'point_of_disambiguation' in trial_record else None), # FIXME: fail on NULL values once datasets are in the right shape
                    distractor_image =  (trial_record['distractor_image'] if 'distractor_label' in trial_record else None)
                )

        print('Building AOI_data table') #depends on subjects, trials, aoi_coordinates
        aoi_data_csv_path = checkForPath(os.path.join(data_folder, 'aoi_data.csv'))
        if aoi_data_csv_path is None:
            print(os.path.join(data_folder, 'aoi_data.csv')+ ' is missing, aborting....')
            continue
        else:

            aoi_data_df = pd.read_csv(aoi_data_csv_path)

            for aoi_data_record in aoi_data_df.to_dict('records'):
                aoi_data = db.models.AOI_Data_Record.objects.create(
                    aoi_data_id = (aoi_data_record['aoi_data_id'] if 'aoi_data_id' in aoi_data_record else None),
                    subject = db.models.Subject_Record.objects.get(subject_id=aoi_data_record['subject_id']),
                    t = (aoi_data_record['t'] if 't' in aoi_data_record else None),
                    aoi = (aoi_data_record['aoi'] if 'aoi' in aoi_data_record else None),
                    trial = db.models.Trial_Record.objects.get(trial_id=aoi_data_record['trial_id']))

        print('Building xy_data table') #depends on trial and subject; optional
        xy_data_path = checkForPath(os.path.join(data_folder, 'aoi_data.csv'))
        if xy_data_path is None:
            print(os.path.join(data_folder, 'aoi_data.csv')+ ' is missing, continuing (xy_data is optional)')
            pass # Some datasets don't have xy_data, so don't abort
        else:

            xy_data_df = pd.read_csv(xy_data_path)

            for xy_data_record in xy_data_df.to_dict('records'):
                xy_data = db.models.XY_Data_Record.objects.create(
                    xy_data_id = (xy_data_record['xy_data_id'] if 'xy_data_id' in xy_data_record else None),
                    x = (xy_data_record['x'] if 'x' in xy_data_record else None),
                    y = (xy_data_record['y'] if 'y' in xy_data_record else None),
                    trial = db.models.Trial_Record.objects.get(trial_id=xy_data_record['trial_id']),
                    subject = db.models.Subject_Record.objects.get(subject_id=xy_data_record['subject_id']))


        # FIXME: when does the admin table get updated? What is the verisoning system

def process_peekbank_dirs(data_root):

    # create_schema_models(schema_file)

    # FIXME: Parallelize if possible as long as we can coordinate the indices
    #multiprocessing.log_to_stderr()
    #pool = multiprocessing.Pool()
    #logger = multiprocessing.get_logger()
    #logger.setLevel(logging.INFO)

    results = []

    all_dirs = [x[0] for x in os.walk(data_root)]
    processed_data_folders = [x for x in all_dirs if os.path.basename(x) == 'processed_data']

    # FIXME: return `results` which can be evaluated for errors
    create_data_tables(processed_data_folders)

    # catch any exceptions thrown by child processes
    for result in results:
        try:
            result.get()
        except:
            traceback.print_exc()

    print('Completed processing!')
