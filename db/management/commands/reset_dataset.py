import os
from django.conf import settings
from django.core.management import BaseCommand
from db.management.commands.populate_peekbank import process_peekbank_dirs
from db.models import *


#The class must be named Command, and subclass BaseCommand
class Command(BaseCommand):
    # Show this when the user types help
    help = "Reset and import a dataset into peekbank"

    def add_arguments(self, parser):
        parser.add_argument('-n', '--dataset_name', help='Name of dataset to add to database')

    # A command must define handle()
    def handle(self, *args, **options):
        dataset_name = options.get('dataset_name')
        print('Called reset_dataset with dataset_name ' + dataset_name)

        dataset_qs = Dataset.objects.filter(dataset_name=dataset_name)

        if not dataset_qs.exists():
            raise ValueError('Dataset ' + dataset_name + ' does not exist.')

        dataset_id = dataset_qs.get().pk

        # tables that have foreign keys to datasets
        trial_types = Trial_Type.objects.filter(dataset_id=dataset_id)
        administrations = Administration.objects.filter(dataset_id=dataset_id)
        stimuli = Stimulus.objects.filter(dataset_id=dataset_id)

        # foreign keyed to trial_types
        aoi_region_sets = AOI_Region_Set.objects.filter(aoi_region_set_id__in=trial_types.values('aoi_region_set_id'))
        trials = Trial.objects.filter(trial_type_id__in=trial_types.values('pk'))

        # foreign keyed to trials
        xy_timepoints = XY_Timepoint.objects.filter(trial_id__in=trials.values('pk'))
        aoi_timepoints = AOI_Timepoint.objects.filter(trial_id__in=trials.values('pk'))

        # foreign keyed to administrations
        subjects = Subject.objects.filter(subject_id__in=administrations.values('subject_id'))

        dataset_qs.delete() # deletes from datasets, trial_types, administrations, stimuli
        aoi_region_sets.delete()
        trials.delete()
        xy_timepoints.delete()
        aoi_timepoints.delete()
        subjects.delete()
