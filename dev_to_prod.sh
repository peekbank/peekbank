source ~/.profile
echo "Making local copy of dev db..."
cd static
mysqldump -u root -p"$ROOT_PASS" peekbank_dev > peekbank_dev_dump.sql
echo "Recreating peekbank db..."
cat recreate_prod.sql | mysql -u root -p"$ROOT_PASS" peekbank
echo "Populating peekbank db with dev data"
mysql -u root -p"$ROOT_PASS" peekbank < peekbank_dev_dump.sql
