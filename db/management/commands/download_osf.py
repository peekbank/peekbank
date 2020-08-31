import os
from django.core.management import BaseCommand, CommandError
import osfclient as osf
import requests
import os.path
import json
import errno
from pathlib import Path

from django.conf import settings

from pdb import set_trace as st


# TODO: Add pagination support.
# TODO: Turn into a django management command!
# TODO: Just very, very, very ugly/shotgun code here :(
# TODO: Add error handling/
# TODO: Multiprocessing ??
# TODO: Fix the awful directory/paths (replace with tempdir/files?)

BASE_OSF_URL = 'https://api.osf.io/v2/nodes/pr6wu/files/osfstorage/'


TOP_LEVEL_DIRECTORY = os.path.abspath(os.path.join(settings.BASE_DIR, 'data'))

#TOP_LEVEL_DIRECTORY = os.path.abspath("/home/ubuntu/peekbank_data_osf")
#TOP_LEVEL_DIRECTORY = os.path.abspath(os.path.join(__file__, "../../../../data"))


class Command(BaseCommand):

    help = 'Downloads data from OSF'


    def gather_folders(self):
        print('Gathering folders....')
        payload = {'filter[kind]': 'folder'}
        r = requests.get(BASE_OSF_URL, params = payload)
        response = json.loads(r.content.decode('utf-8'))
        return [folder for folder in response['data']]

    def find_processed_folder(self, folder):
        print('Finding processed folders...')
        # The empty string in os.path.join is to add a path separator to the end. 
        r = requests.get(os.path.join(BASE_OSF_URL, folder['id'], ''))
        response_dict = json.loads(r.content.decode('utf-8'))
        for item in response_dict['data']:
            if item['attributes']['name'] == 'processed_data':
                return item

    def download_processed_data(self, folder):
        print('Downloading processed data...')
        r = requests.get(os.path.join(BASE_OSF_URL, folder['id'], ''))
        response_dict = json.loads(r.content.decode('utf-8'))
        for item in response_dict['data']:
            if item:
                file_name = item['attributes']['name']
                materialized_path = item['attributes']['materialized_path']
                #file_hashes = item['attributes']['extra']['hashes']


                # The real path at which this file will be saved
                file_path = os.path.join(TOP_LEVEL_DIRECTORY, *materialized_path.split('/'))

                if not os.path.exists(os.path.dirname(file_path)):
                    try:
                        os.makedirs(os.path.dirname(file_path))
                    except OSError as exc:
                        if exc.errno != errno.EEXIST:
                            raise

                r = requests.get(item['links']['download'])
                with open(file_path, 'wb') as fd:
                    fd.write(r.content)

                # hash_file = Path(file_path).with_suffix('.json')
                # with open(hash_file, 'w') as fd:
                #     json.dump(file_hashes, fd)
        
        return

#r = requests.get(my_dict['data'][0]['relationships']['files']['links']['related']['href'])

    def handle(self, *args, **options):  
        print('Handling...')      

        try:
            os.mkdir(TOP_LEVEL_DIRECTORY)

        except FileExistsError:
            print('Data directory already exists')



        print('Gathering folders from main script...')
        folders = self.gather_folders()


        for folder in folders:        
            processed = self.find_processed_folder(folder)
            if processed:
                self.download_processed_data(processed)








