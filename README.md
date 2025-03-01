# Peekbank

This repository contains a Django app that populates the peekbank database. A few notes:
- We use Django to enforce the database schema, build an object-relational model and then populate the database
- The workflows below involve pushing data to the `peekbank_dev` database, then copying that to named releases that will otherwise remain unchanged. `peekbank_dev` may change at any time

# Setting Up a New Server From Scratch

Follow these directions if you are setting up a new server (e.g., a new EC2 box) from scratch. Otherwise, jump down to "Update the Dev Database" for instructions on how to get into an existing installation and update the database with a newer version of the data. We provide the instructions here for setting up a new server because one might want to add this to an existing server (e.g., an image with Shiny on it) because the MySQL requirements are quite simple by comparison. You'll need a `config.json` file that's not checked into the github repo for security reasons.

1. First, SSH into the server. 
1. Make sure that you have mysql server and client installed. For a debian based OS (e.g. Ubuntu), this is most likely as simple as running `sudo apt update` and `sudo apt install mysql-server libmysqlclient-dev`.

1. Assign the root user the password in `config.json` as `PEEKBANK_DB_PASSWORD`:
`ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY $ROOT_PASS; FLUSH PRIVILEGES;`
Additionally, add the following line to the end of `~/.profile`, with the password as the string: `ROOT_PASS=""`

1. There may be other system requirements -- as of 2025-02-28, the server runs Ubuntu 24.04, the environment uses Python 3.12.3, and the other system requirements can be installed with: `sudo apt install pkg-config python3 python3-virtualenv python3-pip`).

1. Clone this repo into the user folder: `git clone https://github.com/peekbank/peekbank.git`

1. Place the `config.json` file with database credentials in the root of this repo.

1. Set up a virtual environment; by convention `peekbank-env`: `virtualenv peekbank-env -p python3` (change python3 if you want to use a different Python version/installation that your system default).

1. Then activate the venv: `source peekbank-env/bin/activate`

1. And you should see the venv name in your shell (peekbank-env). Then install the requirements to the venv: `pip3 install -r requirements.txt`

This server should be ready to run MySQL, so try updating the dev database as below!

To migrate existing databases on a previous server to the new one, run `scripts/migrate_dbs.sh` and `scripts/mount_dbs.sh` (this will create copies of all of the databases that are listed as "supported" in [this file](https://github.com/peekbank/peekbank-website/blob/master/peekbank.json)).

# Update the Dev Database

When you want to update the database, you don't need to install anything new (i.e. MySQL or python libraries) -- all you need to do isget on the existing machine, load the appropriate virtual environment so that the system can see the right python libraries, download the fresh data, and then push that data to MySQL. In more detail:

1. `cd peekbank` to enter the peekbank folder

1. Activate the virtual environment: `source peekbank-env/bin/activate`

1. Download the most recent version of all of the files from OSF with the Django command: `python3 manage.py download_osf --data_root ../peekbank_data_osf`

1. Right now there is a separate directory called `peekbank_data_testing` for adding a subset of datasets for testing (by copying them manually from `peekbank_data_osf`). The script in the next step looks at a folder called `peekbank_data`, which is either symlinked to the testing directory or to the output OSF directory (when you are ready to process all of the datasets). Change the symlink by deleting it with `rm` and then symlinking it with `ln -s <destination> <symlink name>`, e.g., `ln -s peekbank_data_osf peekbank_data` so that it runs all datasets OR `ln -s peekbank_data_testing peekbank_data` so that it only looks at the test datasets.
   
1. `cd scripts` and run `./new_dev_db.sh` This drops the existing database called `peekbank_dev` (if it exists), and creates a fresh one. Then it invokes Django migrations to enforce the correct schema, and invokes the Django populate command on whatever is in the `peekbank_data` directory. This then runs a special Django management command that adds another table with the run length encoding. If a script whines about permissions, make sure it is executable with `chmod +x [filename]`.

Unless this errors out, you should be able to see the new data in the `peekbank_dev` database when this process finishes.

# Promote a Dev Database to Production

If the contents of `peekbank_dev` look good when inspected with an SQL client (and, when we have them, pass tests), you can promote the dev database to a named production database with `./dev_to_prod.sh`. Supply the new name to this script  (e.g., `./dev_to_prod.sh 2021.1`) , otherwise it will overwrite the default database `peekbank`. Note that this will overwrite an existing database of the same name, so be careful.

# Schema Specification

The `peekbank` application uses a JSON-specified representation of the schema, in `static/`. This same schema is used in three places:

1) by the `peekds` file readers, in order to parse and validate input files
2) by `models.py` in Django to establish the data model (i.e., Django object relational model) and to define migrations
3) by `populate_peekbank2.py` to populate the fields from CSVs output by peekds 

# Validation Mode

The ingestion pipeline can also be used to check that data meets the requirements specified in the schema (without writing anything to the database) using the `--valdiate_only` flag. This is useful for checking the compliance of all datasets:

`python3 -m pdb -c c manage.py populate_db --data_root /home/ubuntu/peekbank_data --validate_only`

# Specifying a single dataset

The ingestion pipeline can be run on a single datset using the `--dataset` flag:

`python3 -m pdb -c c manage.py populate_db --data_root /home/ubuntu/peekbank_data --dataset swingley_aslin_2002`


