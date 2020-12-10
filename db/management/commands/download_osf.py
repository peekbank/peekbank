import os
from django.core.management import BaseCommand, CommandError
import osfclient as osf
import requests
import os.path
import json
import errno
from pathlib import Path
from pprint import pprint
from django.conf import settings
from pdb import set_trace as st


# TODO: Add error handling
# TODO: Multiprocessing?
# TODO: Fix the awful directory/paths (replace with tempdir/files?)
# TODO: Add tqdm for progress
# TODO: Graceful interrupt handling

# Visit this url to see what the json response will look like.
BASE_OSF_URL = 'https://api.osf.io/v2/nodes/pr6wu/files/osfstorage/'

class Command(BaseCommand):

    help = 'Downloads data from OSF'

    def add_arguments(self, parser):
        parser.add_argument('--data_root', help='Root directory where to download files')


    def gather_folders(self):
        print('Gathering folders....')
        payload = {'filter[kind]': 'folder'}
        folders = []
        current_link = self.collect_page(BASE_OSF_URL, payload, folders)
        while(current_link != None):
            current_link = self.collect_page(current_link, payload, folders)

        print("Found the following folders:")
        pprint([folder['attributes']['materialized_path'] for folder in folders])
        print("\n\n")
        return folders

    def collect_page(self, url, payload, folders):
        r = requests.get(url, params = payload)
        response = json.loads(r.content.decode('utf-8'))
        folders.extend([folder for folder in response['data']])
        return response['links']['next']


    def find_processed_folder(self, folder):
        print('Finding processed_data subfolder for {}'.format(folder['attributes']['name']))
        # The empty string in os.path.join is to add a path separator to the end. 
        r = requests.get(os.path.join(BASE_OSF_URL, folder['id'], ''))
        response_dict = json.loads(r.content.decode('utf-8'))
        for item in response_dict['data']:
            if item['attributes']['name'] == 'processed_data':
                print('processed_data subfolder found!')
                return item
        else:
            print('no processed_data subfolder exists for {}'.format(folder['attributes']['name']))

    def download_processed_data(self, folder, data_root):
        print('Downloading folder: {}'.format(folder['attributes']['materialized_path']))
        r = requests.get(os.path.join(BASE_OSF_URL, folder['id'], ''))
        response_dict = json.loads(r.content.decode('utf-8'))
        for item in response_dict['data']:
            if item:
                file_name = item['attributes']['name']
                materialized_path = item['attributes']['materialized_path']

                file_path = os.path.join(data_root, *materialized_path.split('/'))

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
        data_root = options.get('data_root')
        print('Called download_osf with data_root '+data_root)

        try:
            os.mkdir(data_root)
        except FileExistsError:
            print('Data directory already exists')

        print('Gathering folders...')
        folders = self.gather_folders()

        processed_list = []
        unprocessed_list = []
        for folder in folders:
            processed = self.find_processed_folder(folder)
            if processed:
                self.download_processed_data(processed, data_root)
                processed_list.append(processed)
            else:
                unprocessed_list.append(folder)
            print("\n\n")

        print('Found these processed folders')
        pprint([processed['attributes']['materialized_path'] for processed in processed_list])

        print('\n')

        print('Nothing downloaded for these corpora, most likely because they don\'t have processed_data subfolder.')
        pprint([folder['attributes']['name'] for folder in unprocessed_list])


