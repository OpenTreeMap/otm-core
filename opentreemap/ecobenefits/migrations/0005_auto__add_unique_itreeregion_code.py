# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding unique constraint on 'ITreeRegion', fields ['code']
        db.create_unique(u'ecobenefits_itreeregion', ['code'])


    def backwards(self, orm):
        # Removing unique constraint on 'ITreeRegion', fields ['code']
        db.delete_unique(u'ecobenefits_itreeregion', ['code'])


    models = {
        u'ecobenefits.itreeregion': {
            'Meta': {'object_name': 'ITreeRegion'},
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'}),
            'geometry': ('django.contrib.gis.db.models.fields.MultiPolygonField', [], {'srid': '3857'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        }
    }

    complete_apps = ['ecobenefits']