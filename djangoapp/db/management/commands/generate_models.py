from __future__ import unicode_literals

from django.db.models import Model, CharField, ForeignKey, IntegerField, DateField, TextField, FloatField, BooleanField
from django.core.management import BaseCommand
from datetime import datetime
import json

field_classes = {
    "CharField": CharField,
    "ForeignKey": ForeignKey,
    "IntegerField": IntegerField,
    "DateField": DateField,
    "TextField": TextField,
    "FloatField": FloatField,
    "BooleanField": BooleanField
}

def create_model(model_class, table, fields):

    class Meta:
        app_label = 'db'
        db_table = table

    attrs = {'__module__': 'db.models', 'Meta': Meta}
    for field in fields:
        field_name = field["field_name"]
        field_class = field_classes[field["field_class"]]
        field_class_init = field_class(**field["options"])
        attrs[field_name] = field_class_init
    print(attrs)
    model = type(model_class, (Model,), attrs)
    print(model)
    return model


class Command(BaseCommand):

    schema = json.load(open('static/peekbank-schema.json'))

    for model_data in schema:
        model_class = model_data["model_class"]
        db_table = model_data["table"]
        fields = model_data["fields"]
        model = create_model(model_class, db_table, fields)
        globals()[model_class] = model
