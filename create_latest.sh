#!/bin/bash

source .env
python manage.py download
python manage.py populate