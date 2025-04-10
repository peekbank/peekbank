#!/bin/bash

source .env

# Path to aliases file
ALIASES_FILE="./pb_aliases.conf"

# Check if the database is running
if [ -z `docker ps -q --no-trunc | grep $(docker-compose ps -q peekbank-db)` ]; then
  echo "The local database is not running, start it using ./run-local-db.sh"
  exit 1
fi

# If DEV is set to TRUE (case insensitive), rebuild the container first
if [[ $DEV = "TRUE" ]]; then
  echo "DEV mode is enabled. Rebuilding container before executing command..."
  docker-compose build peekbank-django
fi

# If we have at least one argument
if [ $# -gt 0 ]; then
  CMD="$1"

  shift
  
  # Check if the command is an alias
  if [ -f "$ALIASES_FILE" ]; then
    # Look for the alias in the aliases file
    ALIAS_CMD=$(grep "^$CMD=" "$ALIASES_FILE" | cut -d= -f2-)
    
    # If an alias was found, use it
    if [ -n "$ALIAS_CMD" ]; then
      # Construct the full command with the alias and remaining arguments
      FULL_CMD="$ALIAS_CMD $@"
      echo "Using alias: $CMD → $ALIAS_CMD"
    else
      # No alias found, use the original command and arguments
      FULL_CMD="$CMD $@"
    fi
  else
    # No aliases file, use the original command and arguments
    FULL_CMD="$CMD $@"
  fi
  
  # Run the command in the container
  docker-compose run --rm peekbank-django $FULL_CMD
else
  # No arguments, just run bash in the container
  docker-compose run --rm --entrypoint bash peekbank-django
fi