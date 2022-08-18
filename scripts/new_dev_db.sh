source ~/.profile
echo "Creating new database..."
cat new_dev_db.sql | mysql -uroot -p"$ROOT_PASS"
echo "Enforcing schema..."
cd ../
python manage.py makemigrations db
python manage.py migrate db
echo "Populating....."
python3 -m pdb -c c manage.py populate_db --data_root /home/ubuntu/peekbank_data
python manage.py rle_custom_migration
