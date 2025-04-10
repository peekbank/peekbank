# Peekbank

This repository contains the containerized Peekbank database and the Django app that populates the db from the OSF data. This repo is relevant to you if you want to make changes to Peekbank or want to run a local version of it. If you just want to use the Peekbank data for analyses, either use our dedicated [peekbankr](https://github.com/peekbank/peekbankr) R package or connect directly to our hosted SQL database using the read-only access account:

```
Hostname: 34.210.173.143
Port: 3306
Adapter: MariaDB
Database: 2025.1 (or any of the supported versions)
Username: reader
Password: gazeofracoons
```

[Supported versions of the PB database](https://peekbank.github.io/peekbank-website/peekbank.json)

# General Setup for both Development and Deployment

For a more streamlined development and deployment experience, we use [Docker](https://docs.docker.com/engine/install/). Install the latest version for your operating system (Docker Desktop for local running/development and regular Docker for server deployments).

After cloning the repo, create an `.env` file with the following command:

```
cp .env.template .env
```

and fill it in according to the instructions in the file.

When working with the database, it might be useful to have a tool to view the contents. We reccomend [DBeaver](https://dbeaver.io/download/)

# Deployment


To start up peekbank, run this command in the projects repository 

```
docker compose up -d
```

The first time this command runs, it will take some time as the necessary containers will be built/pulled.
After the command concludes, the Peekbank container is ready and the database container should be running in the background.
The database will be accessible on your host machine on the port that was specified in the `.env` (3306 by default, so YOUR_IP_HERE:3306 will expose a MariaDB connection).

If you ever need to stop the database, run:
```
docker compose down
```

When updating peekbank, pull the latest version from the repository using `git pull` and run the following commands in the projects root:

```
docker compose build
docker compose up -d
```



# Usage



## Importing Data from an existing Peekbank
TODO
### Remote
TODO
### Using SQL dumps


### Pulling Data from OSF

TODO

```
./pb download
```

* `--datasets`, `-ds`: asdfsadfasdf
* `--keep`, `-k`: asdfsadfasdf
* `--data_root`, `-dr`: asdfsadfasdf
* `--non_interactive`, `-ni`: asdfsadfasdf

## Getting Data into the Staging Database

```
./pb populate
```

* `--datasets`, `-ds`: asdfsadfasdf
* `--keep`, `-k`: asdfsadfasdf
* `--data_root`, `-dr`: asdfsadfasdf
* `--validate_only`, `-val`: asdfsadfasdf


You should be able to see the new data in the `peekbank_dev` database when this process finishes.


```
./pb latest
```


## Promoting the Staging Database to Production

```
./pb promote [new_version_name]
```

TODO
If the contents of `peekbank_dev` look good when inspected with an SQL client (and, when we have them, pass tests), you can promote the dev database to a named production database with `./dev_to_prod.sh`. Supply the new name to this script  (e.g., `./dev_to_prod.sh 2021.1`) Note that this will overwrite an existing database of the same name, so be careful.

## Accessing the Peekbank Database

TODO

## Where is the Data on my Machine?

TODO



TODO: How to access the db (where to put)

## About the ./pb prefix

The 

```
./pb
```

You can exit the container by running
```
exit
```

# Development

You can use the Docker commands from the [deployment section](#deployment) to build and run the Peekbank container locally when testing smaller changes. This is a bit slower (as you need to exit, rebuild, and enter the container after every change) but saves you from having to install anything locally except for Docker.

For a faster development experience, it makes sense to use Docker for the database and use a local Python environment to run the Django app. For this, you will need an installation of [Python 3.12](https://www.python.org/downloads/release/python-3120/).


Start the local develeopment database via Docker by running
```
./run-local-db.sh
```
in the projects root. The MariaDB database will now be accessible on the port you specified in `.env` (3306 default).


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

You might also need to install various database utilities as some of the Python packages depend on them. If you need to install any of these system dependencies, this step should provide you with suitable error messages that point you towards the missing packages.

### Usage in development


```
source peekbank-env/bin/activate
```

You can exit the virtual env by running
```
deactivate
```