#!/bin/bash

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$parent_path"
source ../.env

data_root=${OSF_DATA_PATH}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --data_root)
        data_root="$2"
        shift # past argument
        shift # past value
        ;;
        *)    # unknown option
        shift # past argument
        ;;
    esac
done

echo "Creating new database..."
cat new_dev_db.sql | mysql --host "$PEEKBANK_DB_HOST" --port "$PEEKBANK_DB_PORT" -uroot -p"$PEEKBANK_DB_ROOTPW"
echo "Enforcing schema..."
cd ../
python manage.py makemigrations db
python manage.py migrate db
echo "Populating....."
python manage.py populate_db --data_root "$data_root"
python manage.py rle_custom_migration
