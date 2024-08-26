# TODOs for this version
* fix permission setting for dev and prod db
* introduce a process to get a subset of data automatically (got deleted in the last calamity)
* test/fix promoting
* describe development db access with external tools
* clean up documentation
* Migrate the main server to this version

# Peekbank

This repository contains a Django app that populates the peekbank database. A few notes:
- We use Django to enforce the database schema, build an object-relational model and then populate the database
- The workflows below involve pushing data to the `peekbank_dev` database, then copying that to named releases that will otherwise remain unchanged. `peekbank_dev` may change at any time


# Setup

For a more streamlined deployment and developer experience, you can use peekbank via [Docker](https://docs.docker.com/engine/install/), so install it.

After cloning the repo, create an `.env` file with the following command:

```
cp .env.template .env
```

and fill it in according to the instructions.


# Development


To start the local develeopment database via docker, run 
```
./run-local-dn.sh
```
in the projects root.

Next, set up the virtual environment:

```
virtualenv peekbank-env -p python3
```

Activate it: 
```
source peekbank-env/bin/activate
```

You should now see the venv name in your shell (peekbank-env).
Next, install the required packages:
```
pip3 install -r requirements.txt
```


# Deployment (Setting Up a New Server From Scratch)

(TODO for both: how is the db connected to the outside world? There seems to be an undocumented link)

## With Docker:

In the repos root, run 

```
docker compose up -d
```

The first time this command runs, this will take some time.
After the command concludes, the database container should be running in the background and the peekbank container is ready.
If you ever need to stop the database, run:
```
docker compose down
```


To enter the peekbank container and use peekbank commands, use:

```
enter-peekbank-container.sh
```

You can exit the container by running
```
exit
```

When updating peekbank, run the following commands after pulling:

```
docker compose build
docker compose up -d
```

### Migrating the current setup to this docker setup

#### Using the preinstalled server with this repo

1. Collect the data from the config.json and .profile (rootpw for db here) and put them into the .env file on the server
2. Input the database hostname/credentials into the .env file so that the bash scripts target it correctly
3. The peekbank download data has been moved inside the peekbank folder by default - check if this causes problems with other things installed on the box

#### Fully switching over

1. Install docker on the machine
2. Move the data from the currently used MySQL data to the MariaDB container
3. Expose the DB container to the outside of the machine (either change the dockerfile in the repo, or use a reverse proxy etc.)


## Without Docker:

Follow these directions if you are setting up a new server (e.g., a new EC2 box) from scratch. Otherwise, jump down to "Update the Dev Database" for instructions on how to get into an existing installation and update the database with a newer version of the data. We provide the instructions here for setting up a new server because one might want to add this to an existing server (e.g., an image with Shiny on it) because the MySQL requirements are quite simple by comparison.

1. First, SSH onto the server. 
1. Make sure that you have mysql server installed. For a debian based OS, this is most likely as simple as running `sudo apt install mysql-server`. 
However, you will also need to figure out user accounts in the database with appropriate privileges. The `config.json` should give you 
some hints. Modify according to your environment.

1. Clone this repo into the user folder

1. Set up a virtual environment; by convention `peekbank-env`: `virtualenv peekbank-env -p python3`

1. Change python3 to a specific path if you want to use a specific Python installation. Then activate the venv: `source peekbank-env/bin/activate`

1. And you should see the venv name in your shell (peekbank-env). Then install the requirements to the venv: `pip3 install -r requirements.txt`

At this step, if you get an error related to missing `mysql_config` file, make sure that you install the package `libmysqlclient-dev` with `sudo apt install libmysqlclient-dev` (or something similar depending on your OS)

This server should be ready to run MySQL, so try updating the dev database as below!

In order to run peekbank commands, you now need to

1. `cd peekbank` to enter the peekbank folder

1. Activate the virtual environment: `source peekbank-env/bin/activate`

# Usage

## Update the Dev Database

When you want to update the database, you don't need to install anything new (i.e. MySQL or python libraries) -- all you need to do isget on the existing machine, load the appropriate virtual environment so that the system can see the right python libraries, download the fresh data, and then push that data to MySQL. In more detail:


1. Download the most recent version of all of the files from OSF with the Django command: `python3 manage.py download_osf`, which will put the data into `peekbank-data/peekbank_data_osf` by default. Use `--dataroot <dir>` to specify another directory.


1. Run `./scripts/new_dev_db.sh.` This drops the existing database called `peekbank_dev` (if it exists), and creates a fresh one. Then it invokes Django migrations to enforce the correct schema, and invokes the Django populate command on whatever is in the `peekbank_data_osf` directory (default). This then runs a special Django management command that adds another table with the run length encoding. (If you want to create a database with a subset of the datasets, create a new folder with the subset and specify it to the `new_dev_db.sh` script using the `--data_root <dir>` command line argument.)

Unless this script errors out, you should be able to see the new data in the `peekbank_dev` database when this process finishes.

## Promote a Dev Database to Production

If the contents of `peekbank_dev` look good when inspected with an SQL client (and, when we have them, pass tests), you can promote the dev database to a named production database with `./dev_to_prod.sh`. Supply the new name to this script  (e.g., `./dev_to_prod.sh 2021.1`) , otherwise it will overwrite the default database `peekbank`. Note that this will overwrite an existing database of the same name, so be careful.

## Schema Specification

The `peekbank` application uses a JSON-specified representation of the schema, in `static/`. This same schema is used in three places:

1) by the `peekds` file readers, in order to parse and validate input files
2) by `models.py` in Django to establish the data model (i.e., Django object relational model) and to define migrations
3) by `populate_peekbank2.py` to populate the fields from CSVs output by peekds 

## Validation Mode

The ingestion pipeline can also be used to check that data meets the requirements specified in the schema (without writing anything to the database) using the `--valdiate_only` flag. This is useful for checking the compliance of all datasets:

`python3 -m pdb -c c manage.py populate_db --data_root /home/ubuntu/peekbank_data --validate_only`

## Specifying a single dataset

The ingestion pipeline can be run on a single datset using the `--dataset` flag:

`python3 -m pdb -c c manage.py populate_db --data_root /home/ubuntu/peekbank_data --dataset swingley_aslin_2002`


