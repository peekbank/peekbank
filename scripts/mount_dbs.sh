cd /home/ubuntu/db_dumps

# mount each sql dump in db
for db_dump in $(ls $dump_dir); do echo "Mounting $db_dump"; mysql -uroot -p"$ROOT_PASS" < $db_dump; done

# give reader user read access to all databases
mysql -uroot -p"$ROOT_PASS" -e "CREATE USER IF NOT EXISTS 'reader'@'%' IDENTIFIED BY 'gazeofraccoons'";
mysql -uroot -p"$ROOT_PASS" -e "GRANT SELECT ON *.* TO 'reader'@'%'; FLUSH PRIVILEGES;"
