
from django.db import models

class AoiTimepointsRle(models.Model):
    administration_id = models.IntegerField()
    trial_id = models.IntegerField()
    t_norm = models.IntegerField()
    aoi = models.CharField(max_length=255)
    length = models.BigIntegerField()
    
    class Meta:
        managed = False
        db_table = 'aoi_timepoints_rle'




