import os
from django.core.management import BaseCommand, CommandError
import osfclient as osf
import requests
import os.path
import json
import errno
from pathlib import Path


# TODO: Add pagination support.
# TODO: Turn into a django management command!
# TODO: Just very, very, very ugly/shotgun code here :(
# TODO: Add error handling/
# TODO: Multiprocessing ??
# TODO: Fix the awful directory/paths (replace with tempdir/files?)

BASE_OSF_URL = 'https://api.osf.io/v2/nodes/pr6wu/files/osfstorage/'

TOP_LEVEL_DIRECTORY = os.path.abspath(os.path.join(__file__, "../../../../data"))


class Command(BaseCommand):

    help = 'Downloads data from OSF'


    def gather_folders(self):
        payload = {'filter[kind]': 'folder'}
        r = requests.get(BASE_OSF_URL, params = payload)
        response = json.loads(r.content)
        return [folder for folder in response['data']]

    def find_processed_folder(self, folder):
        # The empty string in os.path.join is to add a path separator to the end. 
        r = requests.get(os.path.join(BASE_OSF_URL, folder['id'], ''))
        response_dict = json.loads(r.content)
        for item in response_dict['data']:
            if item['attributes']['name'] == 'processed_data':
                return item

    def download_processed_data(self, folder):
        r = requests.get(os.path.join(BASE_OSF_URL, folder['id'], ''))
        response_dict = json.loads(r.content)
        for item in response_dict['data']:
            if item:
                file_name = item['attributes']['name']
                materialized_path = item['attributes']['materialized_path']
                file_hashes = item['attributes']['extra']['hashes']

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





        
        return


        






#r = requests.get(my_dict['data'][0]['relationships']['files']['links']['related']['href'])


    def handle(self, *args, **options):
        self.stdout.write(json.loads(r.content))


if __name__ == "__main__":

    try:
        os.mkdir(TOP_LEVEL_DIRECTORY)

    except FileExistsError:
        print('Data directory already exists')



    c = Command()
    folders = c.gather_folders()


    for folder in folders:
        processed = c.find_processed_folder(folder)
        c.download_processed_data(processed)






