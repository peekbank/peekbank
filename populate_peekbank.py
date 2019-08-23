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

    aoi_regions = {}
    datasets = {}
    subjects  = {}
    trials = {}
    aoi_data = {}
    xy_data = {}
    aoi_region_offset = dataset_offset = subject_offset = trial_offset = aoi_data_offset = xy_data_offset = 0   

    for data_folder in processed_data_folders: #this for loop needs to be inside the function to allow `continue` when a file is missing

        print('Building AOI region table') # no dependencies
        aoi_regions_csv_path = checkForPath(os.path.join(data_folder, 'aoi_regions.csv'))
        if aoi_regions_csv_path is None:
            print(os.path.join(data_folder, 'aoi_regions.csv')+ ' is missing; allowing for now')
            pass # FIXME: this should fail (continue to next) once the spec has been achieved on the reader; allowing for now
            #continue
        else:
            aoi_region_df = pd.read_csv(aoi_regions_csv_path)
            aoi_region_df = aoi_region_df.where((pd.notnull(aoi_region_df)), None)
            # offset = AOI_Coordinate_Record.objects.number_that_exist()            
            for aoi_region_record in aoi_region_df.to_dict('records'):
                aoi_region_id_with_offset = aoi_region_record['aoi_region_id'] + aoi_region_offset
                aoi_regions[aoi_region_id_with_offset] = db.models.AOI_Region_Record.objects.create(
                    # aoi_coordinates_id = offset + (aoi_coordinate_record['aoi_coordinates_id'] if 'aoi_coordinates_id' in aoi_coordinate_record else None),
                    aoi_region_id = aoi_region_id_with_offset,
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
            dataset_df = pd.read_csv(dataset_csv_path)
            dataset_df = dataset_df.where((pd.notnull(dataset_df)), None)
            for dataset_record in dataset_df.to_dict('records'):
                dataset_id_with_offset = dataset_record['dataset_id'] + dataset_offset
                datasets[dataset_id_with_offset] = db.models.Dataset_Record(
                    dataset_id  = dataset_id_with_offset,
                    lab_dataset_id  = (dataset_record['dataset_id'] if 'dataset_id' in dataset_record else None),
                    tracker = (dataset_record['tracker'] if 'target_label' in dataset_record else None),
                    monitor_size_x = (dataset_record['monitor_size_x'] if 'target_label' in dataset_record else None),
                    monitor_size_y = (dataset_record['monitor_size_y'] if 'target_label' in dataset_record else None),
                    sample_rate = (dataset_record['sample_rate'] if 'target_label' in dataset_record else None)            
                )
            db.models.Dataset_Record.objects.bulk_create(datasets.values())

        print('Building Subjects table') #no dependencies
        subjects_csv_path = checkForPath(os.path.join(data_folder, 'subjects.csv'))
        if subjects_csv_path is None:
            print(os.path.join(data_folder, 'subjects.csv')+ ' is missing, aborting....')
            continue
        else:
            subjects_df = pd.read_csv(subjects_csv_path)            
            subjects_df = subjects_df.where((pd.notnull(subjects_df)), None)
            for subject_record in subjects_df.to_dict('records'):
                subject_record_with_offset = subject_record['subject_id'] + subject_offset
                subjects[subject_record_with_offset] = db.models.Subject_Record(
                    subject_id = subject_record_with_offset,
                    lab_subject_id = (subject_record['lab_subject_id'] if 'lab_subject_id' in subject_record else None),
                    age = (subject_record['age'] if 'age' in subject_record else None),
                    sex = (subject_record['sex'] if 'sex' in subject_record else None)
                )
            db.models.Subject_Record.objects.bulk_create(subjects.values())

        print('Building Trials table') #depends on Datasets
        trials_csv_path = checkForPath(os.path.join(data_folder, 'trials.csv'))
        if trials_csv_path is None:
            print(os.path.join(data_folder, 'trials.csv')+ ' is missing, aborting....')
            continue
        else:
            trial_df = pd.read_csv(trials_csv_path)
            trial_df = trial_df.where((pd.notnull(trial_df)), None)
            for trial_record in trial_df.to_dict('records'):
                trial_id_with_offset = trial_record['trial_id'] + trial_offset
                trials[trial_id_with_offset] = db.models.Trial_Record(
                    trial_id = trial_id_with_offset,
                    lab_trial_id = (trial_record['trial_id'] if 'trial_id' in trial_record else None),
                    dataset =  datasets[trial_record['dataset_id'] + dataset_offset],
                    #dataset =  db.models.Dataset_Record.objects.get(dataset_id=trial_record['dataset_id']),
                    target_side =  (trial_record['target_side'] if 'target_side' in trial_record else None),
                    target_label =  (trial_record['target_label'] if 'target_label' in trial_record else None),
                    distractor_label =  (trial_record['distractor_label'] if 'distractor_label' in trial_record else None),
                    aoi_region = -1, #db.models.AOI_Region_Record.objects.get(aoi_region_id=trial_record['aoi_region_id']), # FIXME
                    target_image =  (trial_record['target_image'] if 'distractor_label' in trial_record else None),
                    full_phrase =  (trial_record['full_phrase'] if 'full_phrase' in trial_record else None),
                    point_of_disambiguation =  (trial_record['point_of_disambiguation'] if 'point_of_disambiguation' in trial_record else None), # FIXME: fail on NULL values once datasets are in the right shape
                    distractor_image =  (trial_record['distractor_image'] if 'distractor_label' in trial_record else None)
                )
            db.models.Trial_Record.objects.bulk_create(trials.values())
    

        print('Building AOI_data table') #depends on subjects, trials, aoi_coordinates
        aoi_data_csv_path = checkForPath(os.path.join(data_folder, 'aoi_data.csv'))
        if aoi_data_csv_path is None:
            print(os.path.join(data_folder, 'aoi_data.csv')+ ' is missing, aborting....')
            continue
        else: 
            aoi_data_df = pd.read_csv(aoi_data_csv_path)
            aoi_data_df = aoi_data_df.where((pd.notnull(aoi_data_df)), None)
            for aoi_data_record in aoi_data_df.to_dict('records'):
                aoi_data_id_with_offset = aoi_data_record['aoi_data_id'] + aoi_data_offset
                aoi_data[aoi_data_id_with_offset] = db.models.AOI_Data_Record(
                    aoi_data_id = aoi_data_id_with_offset,
                    #subject = db.models.Subject_Record.objects.get(subject_id=aoi_data_record['subject_id']),
                    subject = subjects[aoi_data_record['subject_id'] + subject_offset],
                    t = (aoi_data_record['t'] if 't' in aoi_data_record else None),
                    aoi = (aoi_data_record['aoi'] if 'aoi' in aoi_data_record else None),
                    trial = trials[aoi_data_record['trial_id'] + trial_offset]
                )
            db.models.AOI_Data_Record.objects.bulk_create(aoi_data.values(), batch_size=1000)

        print('Building xy_data table') #depends on trial and subject; optional
        xy_data_path = checkForPath(os.path.join(data_folder, 'xy_data.csv'))
        if xy_data_path is None:
            print(os.path.join(data_folder, 'aoi_data.csv')+ ' is missing, continuing (xy_data is optional)')
            pass # Some datasets don't have xy_data, so don't abort
        else:            
            for xy_data_record in pd.read_csv(xy_data_path).to_dict('records'):
                xy_data_id_with_offset = xy_data_record['xy_data_id'] + xy_data_offset
                xy_data[xy_data_id_with_offset] = db.models.XY_Data_Record(
                    xy_data_id = xy_data_id_with_offset,
                    x = (xy_data_record['x'] if 'x' in xy_data_record else None),
                    y = (xy_data_record['y'] if 'y' in xy_data_record else None),
                    #trial = db.models.Trial_Record.objects.get(trial_id=xy_data_record['trial_id']),
                    trial = trials[xy_data_record['trial_id'] + trial_offset],
                    #subject = db.models.Subject_Record.objects.get(subject_id=xy_data_record['subject_id']))
                    subject = subjects[xy_data_record['subject_id'] + subject_offset]
                )
            db.models.XY_Data_Record.objects.bulk_create(xy_data.values(), batch_size=1000)


        # FIXME: when does the admin table get updated? What is the verisoning system

        aoi_region_offset += len(aoi_regions)
        dataset_offset += len(datasets)
        subject_offset += len(subjects)
        trial_offset += len(trials)
        aoi_data_offset += len(aoi_data)
        xy_data_offset += len(xy_data)

        aoi_regions = {}
        datasets = {}
        subjects  = {}
        trials = {}
        aoi_data = {}
        xy_data = {}


        

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
