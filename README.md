# Peekbank

This repository contains the containerized Peekbank database and the Django app that populates the db from the OSF data.
This repo is relevant to you if you want to make changes to Peekbank or want to run a local version of it.

If you just want to use the Peekbank data for analyses, either use our dedicated [peekbankr](https://github.com/peekbank/peekbankr) R package or connect directly to our hosted SQL database using the read-only access account:

```
Hostname: 34.210.173.143
Port: 3307
Adapter: MariaDB
Database: 2025.1 (or any of the supported versions)
Username: reader
Password: gazeofraccoons
```

[Supported versions of the PB database](https://peekbank.github.io/peekbank-website/peekbank.json)

# General Setup for both Development and Deployment

For a more streamlined development and deployment experience, we use [Docker](https://docs.docker.com/engine/install/). Install the latest version for your operating system ([Docker Desktop](https://www.docker.com/products/docker-desktop/) for local running/development and regular Docker for server deployments).

After cloning the repo, create a `.env` file with the following command:

```
cp .env.template .env
```

and fill it in according to the instructions in the file.

When working with the database, it might be useful to have a tool to view the contents. We recommend [DBeaver](https://dbeaver.io/download/)


# Deployment


To start up Peekbank, run this command in the project's root directory: 

```
docker compose up -d
```

The first time this command runs, it will take some time as the necessary containers will be built/pulled.
(If you run into "Permission denied" error messages when running the docker commands, refer to [this stackoverflow post](https://stackoverflow.com/questions/48957195/how-to-fix-docker-got-permission-denied-issue) to fix those.)


After the command concludes, the Peekbank container is ready and the database container should be running in the background.
The database will be accessible on your host machine on the port that was specified in the `.env` (3307 by default, so YOUR_IP_HERE:3307 will expose a MariaDB connection). If are running the Peekbank instance on a server, make sure the port is accessible to other machines (e.g. by setting your firewall rules or AWS security policies)

If you ever need to stop the database, run:
```
docker compose down
```

When updating Peekbank, pull the latest version from the repository using `git pull` and run the following commands in the project's root:

```
docker compose build
docker compose up -d
```



# Usage

## Importing Data from an existing Peekbank Instance

This section applies to you if you are migrating your Peekbank setup to a new server or want to mirror the hosted Peekbank to your local installation. If you want to pull in the imported data from the OSF, skip to the next section.
Peekbank offers two ways of getting existing data in: 

### Option 1: Remote

To import the data of another running Peekbank instance, run the following command in the project's root (if the data source is not our hosted Peekbank instance, replace the IP and port with your data source):

```
./pb mirror 34.210.173.143:3307
```

This command offers these optional arguments:
* `--databases`, `-dbs`: Specify one or more database versions to mirror (default: all accessible databases)
* `--non_interactive`, `-ni`: Skip confirmation prompts and automatically proceed

After the import finishes, your instance will contain all of the database versions of the remote source.

### Option 2: Using SQL dumps

If both instances are not running at the same time, you can dump the contents of the source instance into `.sql` files and ingest them with the target instance.

In the root of the source instance's directory, run this command:

```
./pb export 
```

These optional arguments can be specified:
* `--databases`, `-dbs`: Specify one or more databases to export (default: all accessible databases)
* `--non_interactive`, `-ni`: Skip confirmation prompts and automatically proceed

This command will dump the databses into `.sql` files in the  `./peekbank-data/dumps` directory on your source machine.


Next, move the `.sql` files to the `./peekbank-data/dumps` folder in your target instance and run this command:
```
./pb import
```

These optional arguments can be specified:
* `--databases`, `-dbs`: Specify one or more databases to import (default: all available dump files)
* `--non_interactive`, `-ni`: Skip confirmation prompts and automatically proceed

After the import finishes, your instance will contain all of the database versions of the source instance.

## Creating new Database Versions from the OSF Data

When creating a new database version (e.g. 2025.1) in Peekbank, the processed data on OSF flows through these stages:

`OSF` -1-> `Download Folder` -2-> `Staging Database` -3-> `Named Database Version`

### 1. Pulling Data from OSF

To get the latest datasets from OSF onto your machine/server for ingestion, run the following command:

```
./pb download
```

This command will, by default, wipe the download folder and download all datasets available on OSF. To customize any of this behavior, you can use these arguments:

* `--datasets`, `-ds`: Specify one or more dataset names to download from OSF. Only datasets matching these names will be downloaded.
* `--keep`, `-k`: Keep existing downloaded datasets and only download the specified ones. Without this flag, all existing data in the target directory will be removed before downloading.
* `--data_root`, `-dr`: Root directory to download files into. If not specified, the folder will default to `./peekbank-data/peekbank_data_osf`.
* `--non_interactive`, `-ni`: Run in non-interactive mode without prompting for resuming previously unfinished downloads. Unfinished downloads will be automatically deleted and restarted.

If a previous download was interrupted, the command will prompt you to optionally continue where it left off.

### 2. Getting Data into the Staging Database

Before pushing the data to a versioned database, we first put it into a staging database called `peekbank_dev` for testing and sanity checks.
Run this command to achieve this:

```
./pb populate
```

You can use these arguments:
* `--datasets`, `-ds`: Specify one or more dataset names to import into the database. Only datasets matching these names will be processed.
* `--keep`, `-k`: Keep existing database data and only overwrite the specified datasets. Without this flag, the database will be recreated from scratch.
* `--data_root`, `-dr`: Root directory where data files are located. If not specified, the folder will default to `./peekbank-data/peekbank_data_osf`.
* `--validate_only`, `-val`: Only validate the data without inserting it into the database. This generates the same completion report but doesn't modify the database.

You should be able to see the new data in the `peekbank_dev` database when this process finishes.
The command will also generate a completion report that shows the import status for each table type (subjects, administrations, trials, etc.) of each dataset.

Optionally, you can run both the download and population using (this supports the parameters that both of the other commands have):

```
./pb latest
```


### 3. Promoting the Staging Database to Production

If the contents of `peekbank_dev` look good when inspected with DBeaver, you can promote the dev database to a named production database using the following command.

```
./pb promote [new_version_name]
```

Note that this will overwrite an existing database of the same name, so be careful.


## Accessing the Peekbank Database

### DBeaver

You can check the database contents using DBeaver with these connection details:

```
Adapter: MariaDB
Server Host: 34.210.173.143 (our server, if you have your own setup, use your IP, or use localhost during development)
Port: 3307 (or whatever you specified in .env)
Database: peekbank_env (or any of the supported versions)
Username: reader
Password: gazeofraccoons
```

### PeekbankR

To connect to your instance using [peekbankr](https://github.com/peekbank/peekbankr), use the following command:
(Fill in the database name you want to connect to and the details of your instance)

```
library(peekbankr)

con <- connect_to_peekbank("peekbank_dev", host="34.210.173.143", port=3307)
```

You can then use this connection to access the data as per the [peekbankr](https://github.com/peekbank/peekbankr) documentation.

## Where is the Data on my Machine?

The automatically generated folder `./peekbank-data/` is mounted into the container, and all data generated by Peekbank lives there (downloaded OSF files, SQL dumps etc.).
The database files live in the automatically generated `./db-data`


## About the ./pb prefix

As the Peekbank Django app runs in a Docker container, we provide a `./pb` prefix to run commands in the container.

For one, it provides the shorthand commands we have seen in the usage suggestion. These map to specific commands in the container, as defined in [pb_aliases.conf](./pb_aliases.conf).
The prefix also allows you to execute arbitrary commands in the container, e.g.

```
./pb echo "In the container"
```
This helper is handy during development or when debugging a production deployment.

You can even go a step further and enter the container to run commands directly in there, using
```
./pb
```

You can later exit the container by running
```
exit
```

# Development

You can use the Docker commands from the [deployment section](#deployment) to build and run the container locally when testing small and medium sized changes to Peekbank. If the `DEV` variable is set to TRUE in the `.env` file, the `./pb` command prefix will automatically rebuild the container before execution.

If you want to make deeper changes (add new dependencies etc.), it makes sense to use Docker for the database and use a local Python environment to run the Django app. For this, you will need an installation of [Python 3.12](https://www.python.org/downloads/release/python-3120/).


Start the local development database via Docker by running
```
./run-local-db.sh
```
in the project's root. The MariaDB database will now be accessible on the port you specified in `.env` (3307 default).


Next, set up the virtual environment:

```
pip3 install virtualenv
```

```
virtualenv peekbank-env -p python3.12
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

Depending on your OS, you might also need to install various database utilities, as some of the Python packages depend on them. If you need to install any of these system dependencies, this step should provide you with suitable error messages pointing you toward the missing packages.

Every time you start up your shell for the first time, you will need to enter the virtual environment again to run Peekbank commands:

```
source peekbank-env/bin/activate
```

You can exit the virtual env by running
```
deactivate
```

Keep in mind that without the docker container, you will not need to use the `./pb` prefix for commands and cannot use the shorthands it provides. Check [pb_aliases.conf](./pb_aliases.conf) to see the commands that map to the shorthands that we defined above. 

# Backups

The Peekbank instance comes with a backup mechanism for two kinds of data:

* The versioned databases in Peekbank (in the form of .sql dumps)
* The raw and processed data on OSF

These backups can be created automatically by the instance or manually via the command line.

## Automated Backup for Deployment (Backup to AWS S3 Bucket)

To make the deployed Peekbank instance automatically upload backups to an S3 Bucket on AWS, first [set up an AWS S3 Bucket](https://aws.amazon.com/de/s3/). Next, comment out the marked line in the `.env` file and enter the credentials of the S3 Bucket in the fields below. The app will automatically back up the data at the intervall specified in the `.env` file.

## Manually Backing up Data

If you want to manually pull data from your hosted Peekbank instance, you can run

```
./pb backup --savelocal
```

which will create a zip with the backup data in the `./peekbank-data/backups`.

You can also use this command to locally download the data from a remote-hosted Peekbank instance (and the OSF repo) by running the following command with your details:

```
./pb backup --savelocal -c 34.210.173.143:3307
```
