#!/bin/bash

source .env

# Check if the database is running
if [ -z `docker ps -q --no-trunc | grep $(docker-compose ps -q peekbank-db)` ]; then
  echo "The local database is not running, start it using ./run-local-db.sh"
  exit 1
fi

# If DEV is set to TRUE, rebuild the container first
if [ "$DEV" = "TRUE" ]; then
  echo "DEV mode is enabled. Rebuilding container before executing command..."
  docker-compose build peekbank-django
fi

# Run the command in the container
docker-compose run --rm peekbank-django "$@"