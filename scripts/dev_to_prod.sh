source ~/.profile
if [ "$1" == "" ] || [ $# -gt 1 ]; then
        NEW_VERSION_NAME="peekbank"
else
        NEW_VERSION_NAME="$1"
fi
echo "New Version Name: $NEW_VERSION_NAME";
echo "Making local copy of dev db..."
mysqldump -u root -p"$ROOT_PASS" peekbank_dev > peekbank_dev_dump.sql
echo "Recreating peekbank db..."
echo $(sed -e "s/peekbank/$NEW_VERSION_NAME/g" recreate_prod.sql) | mysql -u root -p"$ROOT_PASS"
echo "Populating version with dev data"
mysql -u root -p"$ROOT_PASS" ${NEW_VERSION_NAME} < peekbank_dev_dump.sql
