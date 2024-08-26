import os
from django.conf import settings
from django.core.management import BaseCommand
from django.db import connection


class Command(BaseCommand):

    def my_custom_sql(self):
        with connection.cursor() as cursor:
            cursor.execute(
            """
    DROP TABLE IF EXISTS aoi_timepoints_indexed;
    DROP TABLE IF EXISTS aoi_timepoints_rle;
    create table aoi_timepoints_indexed as
    select aoi_timepoints.*,
            (row_number() over (partition by administration_id, trial_id order by t_norm) -
             row_number() over (partition by administration_id, trial_id, aoi order by t_norm)
            ) as grp
    from aoi_timepoints;
    CREATE INDEX idx_administration_trial_aoi_grp ON aoi_timepoints_indexed (administration_id, trial_id, aoi, grp);
    create table aoi_timepoints_rle as
    select administration_id, trial_id, min(t_norm) as t_norm, aoi, count(*) as length
    from aoi_timepoints_indexed
    group by administration_id, trial_id, aoi, grp
    order by administration_id, trial_id, t_norm;
                    """
                    )

    def handle(self, *args, **options):
        self.my_custom_sql()



