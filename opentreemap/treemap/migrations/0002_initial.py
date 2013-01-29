# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Instance'
        db.create_table(u'treemap_instance', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal(u'treemap', ['Instance'])

        # Adding model 'Tree'
        db.create_table(u'treemap_tree', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('geom', self.gf('django.contrib.gis.db.models.fields.PointField')(srid=3857, db_column='the_geom_webmercator', null=True)),
            ('instance', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Instance'])),
        ))
        db.send_create_signal(u'treemap', ['Tree'])


    def backwards(self, orm):
        # Deleting model 'Instance'
        db.delete_table(u'treemap_instance')

        # Deleting model 'Tree'
        db.delete_table(u'treemap_tree')


    models = {
        u'treemap.instance': {
            'Meta': {'object_name': 'Instance'},
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
