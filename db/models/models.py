from __future__ import unicode_literals

import django
from django.db.models import CASCADE, Model, CharField, ForeignKey, IntegerField, JSONField, DateField, TextField, FloatField, BooleanField
from django.conf import settings
from datetime import datetime
import json

field_classes = {
    "CharField": CharField,
    "ForeignKey": ForeignKey,
    "IntegerField": IntegerField,
    "DateField": DateField,
    "TextField": TextField,
    "FloatField": FloatField,
    "BooleanField": BooleanField,
    "JSONField": JSONField
}

def create_model(model_class, table, fields):

    print('Creating model for class ' + model_class)
    class Meta:
        app_label = 'db'
        db_table = table

    def process_option(option):
        if option == "None":
            return(None)
        if option == "datetime.now":
            return(datetime.now)
        return(option)

    attrs = {'__module__': 'models', 'Meta': Meta}
    for field in fields:
        field_name = field["field_name"]
        field_class = field_classes[field["field_class"]]
        options = {opt_name: process_option(opt_value) for opt_name, opt_value in field["options"].items()}
        if field["field_class"] == "ForeignKey":
            #special case for foreign keys to avoid appending _id
            options['db_column'] = field_name
            options['on_delete'] = CASCADE
        field_class_init = field_class(**options)
        attrs[field_name] = field_class_init

    model = type(model_class, (Model,), attrs)

    return(model)

def create_schema_models(schema_file) :

    schema = json.load(open(schema_file))

    for model_data in schema:
        model_class = model_data["model_class"]
        db_table = model_data["table"]
        fields = model_data["fields"]
        model = create_model(model_class, db_table, fields)
        globals()[model_class] = model

create_schema_models(settings.SCHEMA_FILE)
