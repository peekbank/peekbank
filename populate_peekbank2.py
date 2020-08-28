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

def CSV_to_Django(data_folder, schema, dataset_type, offsets, dependencies=None, optional=False):

    class_names = dict([(x['table'],x['model_class']) for x in schema])
    table_names = dict([(x['model_class'],x['table']) for x in schema])

    csv_path = checkForPath(os.path.join(data_folder, dataset_type+'.csv'))      
    if csv_path is None:            
        if optional:
            print(os.path.join(data_folder, dataset_type+'.csv')+ ' is missing; allowing for now...')
            pass 
        else: 
            print(os.path.join(data_folder, dataset_type+'.csv')+ ' is missing; aborting.')
            raise ValueError() #FIXME -- need a way to abort further processing for this dataset from inside the function
    else:
        print('Processing '+csv_path+'...')
        df = pd.read_csv(csv_path)
        df = df.where((pd.notnull(df)), None) # replace nans with Nones        
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
                    
                else:
                    # check if is the table name
                    if field['field_name'] in record_default:
                        #print('Populating '+dataset_type+'.'+field['field_name']+' normally...')
                        payload[field['field_name']] = record_default[field['field_name']]
                    else:
                        import pdb
                        pdb.set_trace()
                        raise ValueError('No value found for field '+field['field_name'])
                        
            # Add the offset to the primary key            
            payload[primary_key] += offsets[primary_key]                    
            
            data_model = getattr(db.models, class_names[dataset_type])
            rdict[payload[primary_key]] = data_model(**payload)

        getattr(db.models, class_names[dataset_type]).objects.bulk_create(rdict.values(), batch_size = 1000)
        return(rdict)

            

def create_data_tables(processed_data_folders, schema):    

    for data_folder in processed_data_folders:                    

        # check if we need to process it
        dataset_name = pd.read_csv(os.path.join(data_folder, 'datasets.csv')).iloc[0].dataset_name

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

        aoi_region_sets = CSV_to_Django(data_folder, schema, 'aoi_region_sets', offsets, optional=True)
        datasets = CSV_to_Django(data_folder, schema, 'datasets', offsets)
        subjects = CSV_to_Django(data_folder, schema, 'subjects', offsets, dependencies={'datasets':datasets})
        administrations = CSV_to_Django(data_folder, schema, 'administrations', offsets, dependencies = {'subjects':subjects, 'datasets':datasets})
        stimuli = CSV_to_Django(data_folder, schema, 'stimuli', offsets, dependencies = {'datasets':datasets})
        trials = CSV_to_Django(data_folder, schema, 'trials', offsets, dependencies = {'datasets':datasets, "aoi_region_sets": aoi_region_sets, 'stimuli':stimuli})
        aoi_timepoints = CSV_to_Django(data_folder, schema, 'aoi_timepoints', offsets, dependencies = {'subjects':subjects, 'trials':trials, 'administrations': administrations})
        xy_timepoints = CSV_to_Django(data_folder, schema, 'xy_timepoints', offsets, dependencies = {'subjects':subjects, 'trials':trials, 'administrations': administrations}, optional=True)
    

def process_peekbank_dirs(data_root):    
    schema = json.load(open(settings.SCHEMA_FILE))

    all_dirs = [x[0] for x in os.walk(data_root)]
    print(all_dirs)
    processed_data_folders = [x for x in all_dirs if os.path.basename(x) == 'processed_data']

    # FIXME: return `results` which can be evaluated for errors
    create_data_tables(processed_data_folders, schema)
    print('Completed processing!')
