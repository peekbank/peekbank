FROM python:3.12-slim-bullseye

RUN apt update && apt-get install build-essential default-libmysqlclient-dev default-mysql-client pkg-config mariadb-client -y

WORKDIR /srv/peekbank

COPY requirements.txt .

RUN pip3 install -r requirements.txt

COPY . .

RUN mkdir -p /srv/peekbank/peekbank-data
