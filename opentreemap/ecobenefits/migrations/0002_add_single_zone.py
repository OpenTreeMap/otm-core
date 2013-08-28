# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

from django.contrib.gis.geos import MultiPolygon, Polygon

class Migration(SchemaMigration):

    def forwards(self, orm):
        polygon = Polygon(((-15929819, 7113543),
                           (-15929819, 2814454),
                           (-7280294, 2814454),
                           (-15929819, 2814454),
                           (-15929819, 7113543)))

        mpolygon = MultiPolygon([polygon])

        orm['ecobenefits.ITreeRegion'].objects.get_or_create(
            code='PiedmtCLT',
            geometry=mpolygon)

    def backwards(self, orm):
        pass

    models = {
        u'ecobenefits.itreeregion': {
            'Meta': {'object_name': 'ITreeRegion'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'geometry': ('django.contrib.gis.db.models.fields.MultiPolygonField', [], {'srid': '3857'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        }
    }

    complete_apps = ['ecobenefits']
