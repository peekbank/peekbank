import glob
import os
#import logging
from django import db
from django.db.models import Avg, Count, Sum
from db.models import AOI_Coordinate_Record, Dataset_Record, Subject_Record, Trial_Record, AOI_Data_Record, XY_Data_Record, Admin
import pandas as pd

def checkForPath(path):
    if os.path.exists(path):
        print(path+ ' found!')
        return(path)
    else:
        print(path+ ' is missing, aborting....')
        return(None)

def process_peekbank_dirs(data_root):

    #multiprocessing.log_to_stderr()
    #pool = multiprocessing.Pool()

    #logger = multiprocessing.get_logger()
    #logger.setLevel(logging.INFO)
    
    results = []

    all_dirs = [x[0] for x in os.walk(data_root)]
    processed_data_folders = [x for x in all_dirs if os.path.basename(x) == 'processed_data']

    for data_folder in processed_data_folders:
        
        # make the
        # Look at CHILDES for an example of how the model gets populated

        # build out the dependency structure: dataset first
        dataset_csv_path = checkForPath(os.path.join(data_folder, 'dataset.csv'))
        if dataset_csv_path is None:
            continue
        else:            
            dataset_dict = pd.read_csv(dataset_csv_path).to_dict('records')[0]
        
            dataset = Dataset_Record.objects.create(           
            tracker = (dataset_dict['tracker'] if 'target_label' in dataset_dict else None),
            monitor_size_x = (dataset_dict['monitor_size_x'] if 'target_label' in dataset_dict else None),
            monitor_size_y = (dataset_dict['monitor_size_y'] if 'target_label' in dataset_dict else None),
            sample_rate = (dataset_dict['sample_rate'] if 'target_label' in dataset_dict else None))

        trials_csv_path = checkForPath(os.path.join(data_folder, 'trials.csv'))
        if trials_csv_path is None:
            continue
        else:

            trial_df = pd.read_csv(os.path.join(data_folder, 'trials.csv'))

            for trial_record in trial_df.to_dict('records'):      
                trial = Trial_Record.objects.create(                
                    dataset =  dataset,
                    target_side =  (trial_record['target_side'] if 'target_side' in trial_record else None),
                    target_label =  (trial_record['target_label'] if 'target_label' in trial_record else None),
                    distractor_label =  (trial_record['distractor_label'] if 'distractor_label' in trial_record else None),
                    target_image =  (trial_record['target_image'] if 'distractor_label' in trial_record else None),
                    distractor_image =  (trial_record['distractor_image'] if 'distractor_label' in trial_record else None),
                    full_phase =  (trial_record['full_phase'] if 'full_phase' in trial_record else None),
                    point_of_disambiguation =  (trial_record['point_of_disambiguation'] if 'point_of_disambiguation' in trial_record else 0) # FIXME: fail on NULL values once datasets are in the right shape
                )

        # FIXME
        # [ ] How to do the integer indexing across datasets


    # catch any exceptions thrown by child processes
    for result in results:
        try:
            result.get()
        except:
            traceback.print_exc()

    print('Completed processing!')