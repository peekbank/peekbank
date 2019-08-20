import glob
import os
#import logging
from django import db
from django.db.models import Avg, Count, Sum
from db.models import AOI_Coordinate_Record, Dataset_Record, Subject_Record, Trial_Record, AOI_Data_Record, XY_Data_Record, Admin

def process_peekbank_dirs(data_root):

    #multiprocessing.log_to_stderr()
    #pool = multiprocessing.Pool()

    #logger = multiprocessing.get_logger()
    #logger.setLevel(logging.INFO)
    
    results = []

    import pdb
    pdb.set_trace()

    all_dirs = [x[0] for x in os.walk(data_root)]
    processed_data_folders = [x for x in all_dirs if os.path.basename(x) == 'processed_data']

    for data_folder in processed_data_folders:


        # FIXME
        # [ ] How to do the integer indexing across datasets

        import pdb
        pdb.set_trace()


    # catch any exceptions thrown by child processes
    for result in results:
        try:
            result.get()
        except:
            traceback.print_exc()