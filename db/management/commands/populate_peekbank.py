import glob
import os
import json
import django
from django.db.models import Avg, Count, Sum
from django.db import reset_queries
import pandas as pd
import numpy as np
import db.models
import traceback
from django.conf import settings
from collections import defaultdict
from datetime import datetime

def checkForPath(path):
    if os.path.exists(path):
        print(path+ ' found!')
        return(path)
    else:
        return(None)

def getDictsWithKeyForValue(dict_list, key, value):
    rv = []
    for item in dict_list:
        if item[key] == value:
            rv.append(item)
    return rv

def CSV_to_Django(validate_only, bulk_args, data_folder, schema, dataset_type, offsets, dependencies=None, optional=False):

    class_names = dict([(x['table'],x['model_class']) for x in schema])
    table_names = dict([(x['model_class'],x['table']) for x in schema])

    csv_path = checkForPath(os.path.join(data_folder, dataset_type+'.csv'))
    if csv_path is None:
        if optional:
            print(os.path.join(data_folder, dataset_type+'.csv')+ ' is missing; allowing for now...')
            pass
        else:
            print(os.path.join(data_folder, dataset_type+'.csv')+ ' is missing; aborting.')
            raise ValueError(os.path.join(data_folder, dataset_type+'.csv')+ ' is missing; aborting.') #FIXME -- need a way to abort further processing for this dataset from inside the function
    else:
        print('Processing '+csv_path+'...')
        df = pd.read_csv(csv_path)        
        df = df.replace({np.nan:None})

        # need to make sure any JSON are cast as such here right here        

        class_def = getDictsWithKeyForValue(schema, "model_class", class_names[dataset_type])[0]
        primary_key = [x for x in class_def['fields'] if 'primary_key' in x['options']][0]['field_name']

        fields_in_csv = df.columns
        fields_required_by_schema = [x['field_name'] for x in class_def['fields']]

        missing_fields = set(fields_required_by_schema)  - set(fields_in_csv) 
        if len(missing_fields) > 0:
            raise ValueError('Fields are missing from '+csv_path+': '+'; '.join(missing_fields)) 
        
        extra_fields = set(fields_in_csv) - set(fields_required_by_schema)
        if len(extra_fields) > 0:
            raise ValueError('Extra fields found in '+csv_path+': '+'; '.join(extra_fields)) 
        rdict = {}        

        for record in df.to_dict('records'):
            record_default = defaultdict(None,record)

            
            payload = {}

            for field in class_def['fields']:                

                if field['field_class'] == 'ForeignKey':
                    #print('Populating '+dataset_type+'.'+field['field_name']+' as foreign key...')
                    # write the foreign key contents programatically
                    # import pdb
                    # pdb.set_trace()
                    data_model_for_fk = getattr(db.models, field['field_class'])

                    to_pk =  field['options']['to']
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
                            validate_aux_data( payload[field['field_name']])                        

                    # in most cases, just propagte the field
                    elif field['field_name'] in record_default:
                        #print('Populating '+dataset_type+'.'+field['field_name']+' normally...')
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
    for arg in bulk_args:
        getattr(db.models, arg[0]).objects.bulk_create(arg[1].values(), batch_size = 1000)



def create_data_tables(processed_data_folders, schema, validate_only):

    completion_reports = []

    for data_folder in processed_data_folders:

        completion_report = {} 
        # check if we need to process it
        dataset_df = pd.read_csv(os.path.join(data_folder, 'datasets.csv'))
        if not 'dataset_name' in  dataset_df.columns:
            # bail! We cannot do anything without this
            completion_report = {'dataset_name': 'No dataset name: '+data_folder}
            completion_report['aoi_region_sets'] = 'Cannot evaluate'
            completion_report['subjects'] = 'Cannot evaluate'
            completion_report['datasets'] = 'Cannot evaluate'
            completion_report['administrations'] = 'Cannot evaluate'
            completion_report['stimuli'] = 'Cannot evaluate'
            completion_report['trial_types'] = 'Cannot evaluate'
            completion_report['trials'] = 'Cannot evaluate'
            completion_report['aoi_timepoints'] = 'Cannot evaluate'
            completion_report['xy_timepoints'] = 'Cannot evaluate'

            completion_reports.append(completion_report)
            continue
                     
        else:
            dataset_name = dataset_df.iloc[0].dataset_name
            completion_report['dataset_name'] =  dataset_name
        
        dataset_model = getattr(db.models, 'Dataset')
        qs = dataset_model.objects.filter(dataset_name=dataset_name)
        if len(qs) > 0:
            print(dataset_name + ' is already in the database, skipping...')
            continue

        # pre-compute the offsets for all tables so that the indexing can be consistent
        # offsets: pk for each table -> offset value, dataset_id -> 59
        table_names = dict([(x['model_class'],x['table']) for x in schema])
        offsets = {}
        for class_name in table_names.keys():
            class_def = getDictsWithKeyForValue(schema, "model_class", class_name)[0]

            primary_key = [x for x in class_def['fields'] if 'primary_key' in x['options']][0]['field_name']
            offset_value = getattr(db.models, class_name).objects.count()
            offsets[primary_key] = offset_value

        bulk_args = []

        # >>> TODO: put the code below in an iterator that whines about what went wrong and continues to run the other import tasks (both within dataset and across datasets)        
        try:
            aoi_region_sets = CSV_to_Django(validate_only, bulk_args, data_folder, schema, 'aoi_region_sets', offsets, optional=True)
            completion_report['aoi_region_sets'] = 'passed'
            if aoi_region_sets is not None:
                completion_report['num_records_aoi_region_sets'] = len(aoi_region_sets)
            else: 
                completion_report['num_records_aoi_region_sets'] = 0

        except Exception as e:
            completion_report['aoi_region_sets'] = traceback.format_exc()
            completion_report['num_records_aoi_region_sets'] = 'Cannot evaluate'

        try:
            datasets = CSV_to_Django(validate_only, bulk_args, data_folder, schema, 'datasets', offsets)
            completion_report['datasets'] = 'passed'

            if datasets is not None:
                completion_report['num_records_datasets'] = len(datasets)
            else: 
                completion_report['num_records_datasets'] = 0

        except Exception as e:
            completion_report['datasets'] = traceback.format_exc()
            completion_report['num_records_datasets'] = 'Cannot evaluate'


        try:
            subjects = CSV_to_Django(validate_only,bulk_args, data_folder, schema, 'subjects', offsets, dependencies={'datasets':datasets})
            completion_report['subjects'] = 'passed'
            if subjects is not None:
                completion_report['num_records_subjects'] = len(subjects)
            else: 
                completion_report['num_records_subjects'] = 0

            
            completion_report['num_subjects_with_cdis'] = len(['cdi_responses' in x.subject_aux_data[0] for x in subjects.values() if x.subject_aux_data is not None])
                    
        except Exception as e:
            completion_report['subjects'] = traceback.format_exc()
            completion_report['num_records_subjects'] = 'Cannot evaluate'
        
        try:
            administrations = CSV_to_Django(validate_only, bulk_args, data_folder, schema, 'administrations', offsets, dependencies = {'subjects':subjects, 'datasets':datasets})            
            completion_report['administrations'] = 'passed'
            if administrations is not None:
                completion_report['num_records_administrations'] = len(administrations)
            else: 
                completion_report['num_records_administrations'] = 0                
                    
            completion_report['num_admins_with_cdis'] = len(['cdi_responses' in x.administration_aux_data[0] for x in administrations.values() if x.administration_aux_data is not None])


        except Exception as e:
            completion_report['administrations'] = traceback.format_exc()        
            completion_report['num_records_administrations'] = 'Cannot evaluate'

        try:
            stimuli = CSV_to_Django(validate_only,bulk_args, data_folder, schema, 'stimuli', offsets, dependencies = {'datasets':datasets})
            completion_report['stimuli'] = 'passed'
            if stimuli is not None:
                completion_report['num_records_stimuli'] = len(stimuli)
            else: 
                completion_report['num_records_stimuli'] = 0
                completion_report['num_records_stimuli'] = 'Cannot evaluate'

        except Exception as e:
            completion_report['stimuli'] = traceback.format_exc()
        
        try:
            trial_types = CSV_to_Django(validate_only, bulk_args, data_folder, schema, 'trial_types', offsets, dependencies = {'datasets':datasets, 'aoi_region_sets':aoi_region_sets, 'stimuli':stimuli})
            completion_report['trial_types'] = 'passed'
            if trial_types is not None:
                completion_report['num_records_trial_types'] = len(trial_types)
            else: 
                completion_report['num_records_trial_types'] = 0
        except Exception as e:
            completion_report['trial_types'] = traceback.format_exc()
            completion_report['num_records_trial_types'] = 'Cannot evaluate'
        
        try:
            trials = CSV_to_Django(validate_only,bulk_args, data_folder, schema, 'trials', offsets, dependencies = {'datasets':datasets, "aoi_region_sets": aoi_region_sets, 'stimuli':stimuli, 'trial_types':trial_types})
            completion_report['trials'] = 'passed'
            if trials is not None:
                completion_report['num_records_trials'] = len(trials)
            else: 
                completion_report['num_records_trials'] = 0

        except Exception as e:
            completion_report['trials'] = traceback.format_exc()
            completion_report['num_records_trials'] = 'Cannot evaluate'
        
        try:
            aoi_timepoints = CSV_to_Django(validate_only,bulk_args, data_folder, schema, 'aoi_timepoints', offsets, dependencies = {'subjects':subjects, 'trials':trials, 'administrations': administrations})
            completion_report['aoi_timepoints'] = 'passed'
            if aoi_timepoints is not None:
                completion_report['num_records_aoi_timepoints'] = len(aoi_timepoints)
            else: 
                completion_report['num_records_aoi_timepoints'] = 0

        except Exception as e:
            completion_report['aoi_timepoints'] = traceback.format_exc()
            completion_report['num_records_aoi_timepoints'] = 'Cannot evaluate'
        
        try:
            xy_timepoints = CSV_to_Django(validate_only,bulk_args, data_folder, schema, 'xy_timepoints', offsets, dependencies = {'subjects':subjects, 'trials':trials, 'administrations': administrations}, optional=True)
            completion_report['xy_timepoints'] = 'passed'
            if xy_timepoints is not None:
                completion_report['num_records_xy_timepoints'] = len(xy_timepoints)
            else: 
                completion_report['num_records_xy_timepoints'] = 0

        except Exception as e:
            completion_report['xy_timepoints'] = traceback.format_exc()
            completion_report['num_records_xy_timepoints'] = 'Cannot evaluate'
        
        if not validate_only:
            bulk_create_tables(bulk_args)
            reset_queries()
        else:
            print('Ran in validation mode, nothing written to the database.')

        completion_reports.append(completion_report)



    print('Generating a completion report...')
    completion_df = pd.DataFrame(completion_reports)
    if not os.path.exists('completion_reports'):
        os.makedirs('completion_reports')
    now = datetime.now()
    current_date_time = now.strftime("%Y-%m-%d-_%H_%M_%S")
    completion_df.to_csv(os.path.join('completion_reports','completion_report_'+current_date_time+'.csv'))


def process_peekbank_dirs(data_root, validate_only, dataset):
    
    schema = json.load(open(settings.SCHEMA_FILE))
    
    if not os.path.exists(data_root):
        raise ValueError('Path '+data_root+' does not exist. Make sure you are pointing to the correct directory.')

    if dataset is None:
        all_dirs = [x[0] for x in os.walk(data_root)]
    else:
        single_dataset_path = os.path.join(data_root, dataset)
        all_dirs = [x[0] for x in os.walk(single_dataset_path)]
    
    processed_data_folders = [x for x in all_dirs if os.path.basename(x) == 'processed_data']
    if len(processed_data_folders) == 0:
        import pdb
        pdb.set_trace()
        raise ValueError('No folders with processed data found. Do you have the right path?')    

    create_data_tables(processed_data_folders, schema, validate_only)
    print('Completed processing!')


def validate_aux_data(aux_json):
    # Written by Alvin Tan on 2/8/24
    if 'cdi_responses' in aux_json.keys():        
        for r in aux_json['cdi_responses']:            
            assert len(set(['instrument_type', 'age', 'rawscore', 'language']).difference(set(r.keys()))) == 0
            assert r['instrument_type'] in ['wgcomp', 'wgprod', 'wsprod']
            assert isinstance(r['age'], (int, float))
            assert isinstance(r['rawscore'], int)
            if 'percentile' in r.keys():
                assert isinstance(r['percentile'], (int, float))
            assert isinstance(r['language'], str)
    else:
        raise ValueError('Other JSON fields found: '+' '.join(aux_json.keys()))




        