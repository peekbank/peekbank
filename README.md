# Peekbank

This repository contains a Django app that populates the peekbank database.

# Prerequisites

First get the `config.json` file with database credentials and place them in the root of this repo (which is a Django project)

Set up a virtual environment; by convention `peekbank-env.` 

`virtualenv peekbank-env -p python3`

Change python3 to a specific path if you want to use a specific Python installation. Then activate the venv:

`source peekbank-env/bin/activate`

And you should see the venv name in your shell (peekbank-env). Then install the requirements to the venv:

`pip3 install -r requirements.txt`

You should be ready to run the commands below.

# Streamlined Update

The general workflow is to run `./new_dev_db.sh` to drop an existing `peekbank_dev` database (if it exists), create a new one, invoke Django migrations to enforce the correct schema, and invoke the Django populate command.
If the results of this look good, you can  migrate changes to the dev database to production (`peekbank`) with `./dev_to_prod.sh` 
Before running either script for the first time, you need to make them executable with `chmod +x [filename]`.


# Piece-by-Piece Update

## Create Database

`create database peekbank_dev`

## Enforce the Schema

`python manage.py makemigrations db`
`python manage.py migrate db`

# Populate the Database

The database is populated using a Django management command:

`python3 manage.py populate_db --data_root <data root, with projects as the top-level folders>`

To drop into pdb on error, use `python3 -m pdb -c c manage.py populate_db --data_root <data root, with projects as the top-level folders>`

# Schema Specification

The `peekbank` application uses a JSON-specified representation of the schema, in `static/`. This same schema is used in three places:

1) by the `peekds` file readers, in order to parse and validate input files
2) by `models.py` in Django to establish the data model (i.e., Django object relational model) and to define migrations
3) by `populate_peekbank2.py` to populate the fields from CSVs output by peekds 
