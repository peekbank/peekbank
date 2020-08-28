import os
from django.core.management import BaseCommand, CommandError
import osfclient as osf
import requests
import os.path
import json


# TODO: Add pagination support.
# TODO: Turn into a django management command!
# TODO: Just very, very, very ugly/shotgun code here :(
# TODO: Add error handling/

BASE_OSF_URL = 'https://api.osf.io/v2/nodes/pr6wu/files/osfstorage/'


class Command(BaseCommand):

    help = 'Downloads data from OSF'


    def gather_folders(self):
        payload = {'filter[kind]': 'folder'}
        r = requests.get(BASE_OSF_URL, params = payload)
        response = json.loads(r.content)
        return [folder for folder in response['data']]

    def find_processed_folder(self, folder):
        # The empty string in os.path.join is to add a path separator to the end. 
        r = requests.get(os.path.join(base_url, folder['id'], ''))
        response_dict = json.loads(r.content)
        for item in response_dict['data']:
            if item['attributes']['name'] == 'processed_data':
                return item

    def download_processed_data(self, folder):


        






#r = requests.get(my_dict['data'][0]['relationships']['files']['links']['related']['href'])


    def handle(self, *args, **options):
        self.stdout.write(json.loads(r.content))


if __name__ == "__main__":
    c = Command()
    folders = c.gather_folders()
    for folder in folders:
        check_and_download_folder(folder)




