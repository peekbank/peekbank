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

        rdict = {}

        for record in df.to_dict('records'):
            record_default = defaultdict(None,record)

            class_def = getDictsWithKeyForValue(schema, "model_class", class_names[dataset_type])[0]
            primary_key = [x for x in class_def['fields'] if 'primary_key' in x['options']][0]['field_name']
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
                        try:
                            if fk_field in ('distractor_id', 'target_id'):
                                # special case where the pk of the destination/to table is different than the local key (trials -> stimulis)
                                fk_remap = "stimulus_id"
                            else:
                                fk_remap = fk_field

                            payload[fk_field] = dependencies[fk_to_table][record_default[fk_field] + offsets[fk_remap]]
                        except:
                            print('Foreign key indexing error! Go find Stephan')
                            import pdb
                            pdb.set_trace()
                            raise ValueError('Foreign key indexing error! Go find Stephan')

                else:
                    # cast any aux fields to JSON
                    if 'aux' in field['field_name'] and record_default[field['field_name']] is not None:
                        payload[field['field_name']] = json.loads(record_default[field['field_name']])
                        
                        if dataset_type == 'administrations':                                                        
                            [validate_cdi_json(x) for x in payload[field['field_name']]]
                            

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

        # check if we need to process it
        dataset_name = pd.read_csv(os.path.join(data_folder, 'datasets.csv')).iloc[0].dataset_name
        completion_report = {'dataset_name': dataset_name}

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
        except Exception as e:
            completion_report['aoi_region_sets'] = traceback.format_exc()

        try:
            datasets = CSV_to_Django(validate_only, bulk_args, data_folder, schema, 'datasets', offsets)
            completion_report['datasets'] = 'passed'
        except Exception as e:
            completion_report['datasets'] = traceback.format_exc()

        try:
            subjects = CSV_to_Django(validate_only,bulk_args, data_folder, schema, 'subjects', offsets, dependencies={'datasets':datasets})
            completion_report['subjects'] = 'passed'
                    
        except Exception as e:
            completion_report['subjects'] = traceback.format_exc()
        
        try:
            administrations = CSV_to_Django(validate_only, bulk_args, data_folder, schema, 'administrations', offsets, dependencies = {'subjects':subjects, 'datasets':datasets})            
            completion_report['administrations'] = 'passed'

        except Exception as e:
            completion_report['administrations'] = traceback.format_exc()        

        try:
            stimuli = CSV_to_Django(validate_only,bulk_args, data_folder, schema, 'stimuli', offsets, dependencies = {'datasets':datasets})
            completion_report['stimuli'] = 'passed'

        except Exception as e:
            completion_report['stimuli'] = traceback.format_exc()
        
        try:
            trial_types = CSV_to_Django(validate_only, bulk_args, data_folder, schema, 'trial_types', offsets, dependencies = {'datasets':datasets, 'aoi_region_sets':aoi_region_sets, 'stimuli':stimuli})
            completion_report['trial_types'] = 'passed'
        except Exception as e:
            completion_report['trial_types'] = traceback.format_exc()
        
        try:
            trials = CSV_to_Django(validate_only,bulk_args, data_folder, schema, 'trials', offsets, dependencies = {'datasets':datasets, "aoi_region_sets": aoi_region_sets, 'stimuli':stimuli, 'trial_types':trial_types})
            completion_report['trials'] = 'passed'
        except Exception as e:
            completion_report['trials'] = traceback.format_exc()
        
        try:
            aoi_timepoints = CSV_to_Django(validate_only,bulk_args, data_folder, schema, 'aoi_timepoints', offsets, dependencies = {'subjects':subjects, 'trials':trials, 'administrations': administrations})
            completion_report['aoi_timepoints'] = 'passed'
        except Exception as e:
            completion_report['aoi_timepoints'] = traceback.format_exc()
        
        try:
            xy_timepoints = CSV_to_Django(validate_only,bulk_args, data_folder, schema, 'xy_timepoints', offsets, dependencies = {'subjects':subjects, 'trials':trials, 'administrations': administrations}, optional=True)
            completion_report['xy_timepoints'] = 'passed'
        except Exception as e:
            completion_report['xy_timepoints'] = traceback.format_exc()
        
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
    current_date_time = now.strftime("%d-%m-%Y_%H_%M_%S")
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

    create_data_tables(processed_data_folders, schema, validate_only)
    print('Completed processing!')


def validate_cdi_json(cdi_json):
    print('Validating JSON')
    # Written by Alvin Tan on 2/8/24
    if 'cdi_responses' in cdi_json.keys():
        for r in cdi_json['cdi_responses']:
            assert len(set(['instrument_type', 'age', 'rawscore', 'language']).difference(set(r.keys()))) == 0
            assert r['instrument_type'] in ['wgcomp', 'wgprod', 'wsprod']
            assert isinstance(r['age'], (int, float))
            assert isinstance(r['rawscore'], int)
            if 'percentile' in r.keys():
                assert isinstance(r['percentile'], (int, float))
            assert isinstance(r['language'], str)