# peekbank

This repository contains a Django app that populates the peekbank database.

# Installation

First get the `config.json` file with database credentials and place them in the root of this repo (which is a Django project)

Set up a virtual environment; by convention `peekbank-env.` 

`virtualenv peekbank-env -p python3`

Change python3 to a specific path if you want to use a specific Python installation. Then activate the venv:

`source peekbank-env/bin/activate`

And you should see the venv name in your shell (peekbank-env). Then install the requirements to the venv:

`pip3 install -r requirements.txt`

You should be ready to run the commands below.

# Clearing the database and resetting indices

From a SQL client:

```delete from admin;
delete from aoi_regions;
delete from aoi_data;
delete from datasets;
delete from subjects;
delete from trials;
delete from xy_data;
ALTER TABLE admin AUTO_INCREMENT = 1;
ALTER TABLE aoi_regions AUTO_INCREMENT = 1;
ALTER TABLE aoi_data AUTO_INCREMENT = 1;
ALTER TABLE datasets AUTO_INCREMENT = 1;
ALTER TABLE subjects AUTO_INCREMENT = 1;
ALTER TABLE trials AUTO_INCREMENT = 1;
ALTER TABLE xy_data AUTO_INCREMENT = 1
```

Or, to save yourself typing:

```delete from admin batch;
mysql <name-of-db> < static/clear_db_reset_indices.sql
```

# Generate the Database Tables

`python manage.py makemigrations db`
`python manage.py migrate db`

# Populating the Database

The database is populated using a Django management command:

`python3 manage.py populate_db --data_root <data root, with projects as the top-level folders>`

# Schema Specification

The `peekbank` application uses a JSON-specified representation of the schema, in `static/`. This same schema is used in three places:

1) by the `peekds` file readers to parse and validate input files
2) by `models.py` in Django to establish the data model and define migrations
3) by `populate_peekbank2.py` to populate the fields from CSVs output by peekds 

Foreign keys in the schema do not have `_id` at the end, because this is added by Django
