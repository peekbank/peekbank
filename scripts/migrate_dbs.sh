#!/usr/bin/env bash

prev_host="54.212.226.192"
dump_dir="/home/ubuntu/db_dumps"

# get peekbank versions json file
wget https://raw.githubusercontent.com/peekbank/peekbank-website/refs/heads/master/peekbank.json

# iterate over supported versions and create dump for each one
cat peekbank.json | tail -n +5 | jq '.supported[]' | tr -d '"' | while read -r db_name; do
	echo "Creating mysql dump for database named: $db_name"
    mysqldump -v -u reader -pgazeofraccoons -h $prev_host --databases $db_name --quick --column-statistics=0 --single-transaction --no-tablespaces --add-drop-database > $dump_dir/$db_name.sql
done
