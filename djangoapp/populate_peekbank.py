from django import db
from django.db.models import Avg, Count, Sum
from models import AOI_Coordinate_Record, Dataset_Record, Subject_Record, Trial_Record, AOI_Data_Record, XY_Data_Record, Admin

def process_peekbank_dirs(data_root):

    #multiprocessing.log_to_stderr()
    #pool = multiprocessing.Pool()

    logger = multiprocessing.get_logger()
    logger.setLevel(logging.INFO)
    
    results = []


    for data_folder in os.walk(data_root).next()[1]:

        # FIXME
        # [ ] How to do the integer indexing across datasets
        # [ ] 

        import pdb
        pdb.set_trace


    pool.close()

    # catch any exceptions thrown by child processes
    for result in results:
        try:
            result.get()
        except:
            traceback.print_exc()