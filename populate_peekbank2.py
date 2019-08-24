import glob
import os
import json
import django
from django.db.models import Avg, Count, Sum
import pandas as pd
import db.models
from django.conf import settings
from collections import defaultdict

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

def CSV_to_Django(data_folder, schema, dataset_type, dependencies=None, optional=False):

    class_names = {
        "aoi_regions":"AOI_Region_Record",
        "datasets":"Dataset_Record",
        "subjects": "Subject_Record",
        "trials":"Trial_Record",
        "aoi_data":"AOI_Data_Record",
        "xy_data":"XY_Data_Record",   
    } # FIXME: read from the JSON

    
    csv_path = checkForPath(os.path.join(data_folder, dataset_type+'.csv'))      
    if csv_path is None:            
        if optional:
            print(os.path.join(data_folder, dataset_type+'.csv')+ ' is missing; allowing for now...')
            pass 
        else: 
            print(os.path.join(data_folder, dataset_type+'.csv')+ ' is missing; aborting.')
            raise ValueError() #FIXME -- need a way to abort further processing for this dataset from inside the function
    else:
        df = pd.read_csv(csv_path)
        df = df.where((pd.notnull(df)), None)        
        offset =  getattr(db.models, class_names[dataset_type]).objects.count()
        rdict = {}         

        for record in df.to_dict('records'):
            record_default = defaultdict(None,record)
        
            class_def = getDictsWithKeyForValue(schema, "model_class", class_names[dataset_type])[0]
            primary_key = [x for x in class_def['fields'] if 'primary_key' in x['options']][0]['field_name']
            payload = {}

            for field in class_def['fields']:
                if field['field_class'] == 'ForeignKey':
                    import pdb
                    pdb.set_trace()
                    raise NotImplementedError # FIXME: Django foreignkey nonsense
                else:
                    # check if is the table name
                    if field['field_name'] in record_default:
                        payload[field['field_name']] = record_default[field['field_name']]                        
                    elif (field['field_name'].split('_')[0]+'s' == dataset_type): #FIXME: temporary fix for Peekds outputing tables with id rather than <tablename>_id
                        payload[field['field_name']] = record_default['id']   
                    else:
                        import pdb
                        pdb.set_trace()
                        raise ValueError('No value found for field '+field['field_name'])
                        
                    # Add the offset to the primary key
                    payload[primary_key] += offset                    
            
            data_model = getattr(db.models, class_names[dataset_type])
            rdict[payload[primary_key]] = data_model(**payload)

        getattr(db.models, class_names[dataset_type]).objects.bulk_create(rdict.values())
        return(rdict)

            

def create_data_tables(processed_data_folders):
    
    schema = json.load(open(settings.SCHEMA_FILE))

    for data_folder in processed_data_folders:            
        
        aoi_regions = CSV_to_Django(data_folder, schema, 'aoi_regions', optional=True)
        datasets = CSV_to_Django(data_folder, schema, 'datasets')
        subjects = CSV_to_Django(data_folder, schema, 'subjects')
        trials = CSV_to_Django(data_folder, schema, 'trials', dependencies = {'datasets':dataset})
        aoi_data = CSV_to_Django(data_folder, schema, 'aoi_data', dependencies = {'subjects':subjects, 'trials':trials})
        xy_data = CSV_to_Django(data_folder, schema, 'xy_data', dependencies = {'subjects':subjects, 'trials':trials}, optional=True)
    

def process_peekbank_dirs(data_root):    
    all_dirs = [x[0] for x in os.walk(data_root)]
    processed_data_folders = [x for x in all_dirs if os.path.basename(x) == 'processed_data']

    # FIXME: return `results` which can be evaluated for errors
    create_data_tables(processed_data_folders)
    print('Completed processing!')
