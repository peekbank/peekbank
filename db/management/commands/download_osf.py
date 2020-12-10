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


# TODO: Add pagination support. WE DID IT HAHAHAHAHAHAHAHAHAAH
# TODO: Turn into a django management command! DONE ATAHAHFASHFAHSDHAHASHFASDFAHDSFH
# TODO: Just very, very, very ugly/shotgun code here :(
# TODO: Add error handling/
# TODO: Multiprocessing ??
# TODO: Fix the awful directory/paths (replace with tempdir/files?)
# TODO: add tqdm for progress
# TODO: Graceful interrupt handling


# Visit this url to see what the json response will look like.
BASE_OSF_URL = 'https://api.osf.io/v2/nodes/pr6wu/files/osfstorage/'



TOP_LEVEL_DIRECTORY = os.path.abspath("/home/sarp/ubuntu/peekbank_data_osf")


class Command(BaseCommand):

    help = 'Downloads data from OSF'


    def gather_folders(self):
        print('Gathering folders....')
        payload = {'filter[kind]': 'folder'}
        folders = []
        current_link = self.collect_page(BASE_OSF_URL, payload, folders)
        while(current_link != None):
            current_link = self.collect_page(current_link, payload, folders)

        print("Found the following folders:")
        print([folder['attributes']['materialized_path'] for folder in folders])

        return folders

    def collect_page(self, url, payload, folders):
        r = requests.get(url, params = payload)
        response = json.loads(r.content.decode('utf-8'))
        folders.extend([folder for folder in response['data']])
        return response['links']['next'] 


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
        print('Downloading folder: {}'.format(folder['attributes']['materialized_path']))
        r = requests.get(os.path.join(BASE_OSF_URL, folder['id'], ''))
        response_dict = json.loads(r.content.decode('utf-8'))
        for item in response_dict['data']:
            if item:
                file_name = item['attributes']['name']
                materialized_path = item['attributes']['materialized_path']

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
        
        return

    def handle(self, *args, **options):  
        print('Handling...')      

        try:
            os.mkdir(TOP_LEVEL_DIRECTORY)

        except FileExistsError:
            print('Data directory already exists')



        print('Gathering folders from main script...')
        folders = self.gather_folders()


        processed_list = []
        for folder in folders:        
            processed = self.find_processed_folder(folder)
            processed_list.append(processed)
            if processed:
                self.download_processed_data(processed)
        print('Found these processed folders')
        print(processed_list)









