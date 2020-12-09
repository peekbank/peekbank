import os
from django.conf import settings
from django.core.management import BaseCommand
from db.management.commands.populate_peekbank import process_peekbank_dirs
from db.models import *
from django.apps import apps


#The class must be named Command, and subclass BaseCommand
class Command(BaseCommand):
    # Show this when the user types help
    help = "Reset all dataset in peekbank"

    # A command must define handle()
    def handle(self, *args, **options):
        dataset_name = options.get('dataset_name')
        print('Called reset_all_datasets')

        models = apps.all_models['db']
        for model_name, model_class in models.items():
            print('Deleting ' + model_name)
            model_class.objects.all().delete()
