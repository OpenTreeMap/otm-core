# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'ITreeRegion'
        db.create_table(u'ecobenefits_itreeregion', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('code', self.gf('django.db.models.fields.CharField')(max_length=40)),
            ('geometry', self.gf('django.contrib.gis.db.models.fields.MultiPolygonField')(srid=3857)),
        ))
        db.send_create_signal(u'ecobenefits', ['ITreeRegion'])


    def backwards(self, orm):
        # Deleting model 'ITreeRegion'
        db.delete_table(u'ecobenefits_itreeregion')


    models = {
        u'ecobenefits.itreeregion': {
            'Meta': {'object_name': 'ITreeRegion'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'geometry': ('django.contrib.gis.db.models.fields.MultiPolygonField', [], {'srid': '3857'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        }
    }

    complete_apps = ['ecobenefits']