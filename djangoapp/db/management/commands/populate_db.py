import os
from django.conf import settings
from django.core.management import BaseCommand
from populate_peekbank import process_peekbank_dirs

#The class must be named Command, and subclass BaseCommand
class Command(BaseCommand):
    # Show this when the user types help
    help = "Populate Peekbank MySQL Database"

    def add_arguments(self, parser):
        parser.add_argument('--schema_file', help='File with schema JSON')
        parser.add_argument('--data_root', help='Root directory to add to database')

    # A command must define handle()
    def handle(self, *args, **options):
        print('Called populate_db with data_root '+options.get('data_root')+' and schema_file '+options.get('schema_file'))

        process_peekbank_dirs(options.get('data_root'), options.get('schema_file'))
