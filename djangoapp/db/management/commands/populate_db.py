import os
from django.conf import settings
from django.core.management import BaseCommand

#The class must be named Command, and subclass BaseCommand
class Command(BaseCommand):
    # Show this when the user types help
    help = "Populate Peekbank MySQL Database"

    # FIXME
    def add_arguments(self, parser):
        parser.add_argument('--example_arg', help='dummy arg example')

    # A command must define handle()
    def handle(self, *args, **options):
        print('Called populate_db')        
        example_arg = options.get("example_arg")


        print("Arg "+str(example_arg))    