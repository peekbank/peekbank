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


# Generate the Database Tables

@MIKA FIXME: makemigrations

# Populating the Database

The database is populated using a Django management command:

`python3 manage.py populate_db --data_root <data root, with projects as the top-level folders>` @MIKA @STEPHAN FIXME: args

# Schema Specification

The `peekbank` application uses a JSON-specified representation of the schema, in `static/`. This same schema is used by the peekds file readers to parse and validate input files.
