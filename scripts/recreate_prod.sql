DROP DATABASE IF EXISTS peekbank;
CREATE DATABASE peekbank;
GRANT ALL PRIVILEGES ON peekbank.* TO 'root'@'localhost';
GRANT SELECT ON peekbank.* TO 'reader'@'%';
