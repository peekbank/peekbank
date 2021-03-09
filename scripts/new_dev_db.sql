CREATE USER IF NOT EXISTS 'reader'@'%' IDENTIFIED BY 'gazeofraccoons';
DROP DATABASE IF EXISTS peekbank_dev;
CREATE DATABASE peekbank_dev;
GRANT ALL PRIVILEGES ON peekbank_dev.* TO 'root'@'localhost';
GRANT SELECT ON peekbank_dev.* TO 'reader'@'%';
