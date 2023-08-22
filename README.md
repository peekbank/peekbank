# Peekbank

This repository contains a Django app that populates the peekbank database. A few notes:
- We use Django to enforce the database schema, build an object-relational model and then populate the database
- The workflows below involve pushing data to the `peekbank_dev` database, then copying that to named releases that will otherwise remain unchanged. `peekbank_dev` may change at any time

# Setting Up a New Server From Scratch

Follow these directions if you are setting up a new server (e.g., a new EC2 box) from scratch. Otherwise, jump down to "Update the Dev Database" for instructions on how to get into an existing installation and update the database with a newer version of the data. We provide the instructions here for setting up a new server because one might want to add this to an existing server (e.g., an image with Shiny on it) because the MySQL requirements are quite simple by comparison.

1. First, SSH onto the server. 
1. Make sure that you have mysql server installed. For a debian based OS, this is most likely as simple as running `sudo apt install mysql-server`. 
However, you will also need to figure out user accounts in the database with appropriate privileges. The `config.json` should give you 
some hints. Modify according to your environment.

1. Clone this repo into the user folder

1. Get the `config.json` file with database credentials and place them in the root of this repo. This includes Django settings and passwords and is not part of the repo because it has passwords etc.

1. Set up a virtual environment; by convention `peekbank-env`: `virtualenv peekbank-env -p python3`

1. Change python3 to a specific path if you want to use a specific Python installation. Then activate the venv: `source peekbank-env/bin/activate`

1. And you should see the venv name in your shell (peekbank-env). Then install the requirements to the venv: `pip3 install -r requirements.txt`

At this step, if you get an error related to missing `mysql_config` file, make sure that you install the package `libmysqlclient-dev` with `sudo apt install libmysqlclient-dev` (or something similar depending on your OS)

This server should be ready to run MySQL, so try updating the dev database as below!

# Update the Dev Database

When you want to update the database, you don't need to install anything new (i.e. MySQL or python libraries) -- all you need to do isget on the existing machine, load the appropriate virtual environment so that the system can see the right python libraries, download the fresh data, and then push that data to MySQL. In more detail:

1. `cd peekbank` to enter the peekbank folder

1. Activate the virtual environment: `source peekbank-env/bin/activate`

1. Download the most recent version of all of the files from OSF with the Django command: `python3 manage.py download_osf --data_root ../peekbank_data_osf`

1. `cd scripts` and run `./new_dev_db.sh.` This drops the existing database called `peekbank_dev` (if it exists), and creates a fresh one. Then it invokes Django migrations to enforce the correct schema, and invokes the Django populate command. This then runs a special Django management command that adds another table with the run length encoding. If a script whines about permissions, make sure it is executable with `chmod +x [filename]`.

Unless this errors out, you should be able to see the new data in the `peekbank_dev` database when this process finishes.

# Promote a Dev Database to Production

If the contents of `peekbank_dev` look good when inspected with an SQL client (and, when we have them, pass tests), you can promote the dev database to a named production database with `./dev_to_prod.sh`. Supply the new name to this script  (e.g., `./dev_to_prod.sh 2021.1`) , otherwise it will overwrite the default database `peekbank`. Note that this will overwrite an existing database of the same name, so be careful.

# Schema Specification

The `peekbank` application uses a JSON-specified representation of the schema, in `static/`. This same schema is used in three places:

1) by the `peekds` file readers, in order to parse and validate input files
2) by `models.py` in Django to establish the data model (i.e., Django object relational model) and to define migrations
3) by `populate_peekbank2.py` to populate the fields from CSVs output by peekds 
