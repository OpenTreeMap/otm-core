from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.gis.db import models


class ITreeRegion(models.Model):
    code = models.CharField(max_length=40)
    geometry = models.MultiPolygonField(srid=3857)

    objects = models.GeoManager()
