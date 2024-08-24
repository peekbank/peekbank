#!/bin/bash

source .env
if [ -z `docker ps -q --no-trunc | grep $(docker-compose ps -q peekbank-db)` ]; then
  echo "The local database is not running, start it using ./run-local-db.sh"
else
  docker-compose run --rm --entrypoint bash peekbank-django
fi
