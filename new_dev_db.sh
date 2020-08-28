source ~/.profile
echo "Creating new database..."
cd static
cat new_dev_db.sql | mysql -u root -p"$ROOT_PASS" peekbank_dev
echo "Enforcing schema..."
cd ../
python manage.py migrate db
echo "Populating....."
python3 -m pdb -c c  manage.py populate_db --data_root /home/ubuntu/peekbank_data/



