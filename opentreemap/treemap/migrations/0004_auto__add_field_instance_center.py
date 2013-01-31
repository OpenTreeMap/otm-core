# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Instance.center'
        db.add_column(u'treemap_instance', 'center',
                      self.gf('django.contrib.gis.db.models.fields.PointField')(srid=3857, default='POINT(0 0)'),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'Instance.center'
        db.delete_column(u'treemap_instance', 'center')


    models = {
        u'treemap.instance': {
            'Meta': {'object_name': 'Instance'},
            'center': ('django.contrib.gis.db.models.fields.PointField', [], {'srid': '3857'}),
            'geo_rev': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        u'treemap.tree': {
            'Meta': {'object_name': 'Tree'},
            'geom': ('django.contrib.gis.db.models.fields.PointField', [], {'srid': '3857', 'db_column': "'the_geom_webmercator'"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"})
        }
    }

    complete_apps = ['treemap']