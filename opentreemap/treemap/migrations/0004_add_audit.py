# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models
from django.contrib.gis.geos import Point

class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Audit'
        db.create_table(u'treemap_audit', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('model', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('model_id', self.gf('django.db.models.fields.IntegerField')(null=True)),
            ('instance', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Instance'])),
            ('field', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('previous_value', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('current_value', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('user', self.gf('django.db.models.fields.IntegerField')()),
            ('action', self.gf('django.db.models.fields.IntegerField')()),
            ('requires_auth', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ref_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Audit'], null=True)),
            ('created', self.gf('django.db.models.fields.DateField')(auto_now_add=True, blank=True)),
            ('updated', self.gf('django.db.models.fields.DateField')(auto_now=True, blank=True)),
        ))
        db.send_create_signal(u'treemap', ['Audit'])

        # Adding field 'Instance.center'
        db.add_column(u'treemap_instance', 'center',
                      self.gf('django.contrib.gis.db.models.fields.PointField')(srid=3857, default=Point(0,0)),
                      keep_default=False)

        # Adding field 'Tree.owner'
        db.add_column(u'treemap_tree', 'owner',
                      self.gf('django.db.models.fields.CharField')(default=1, max_length=200),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting model 'Audit'
        db.delete_table(u'treemap_audit')

        # Deleting field 'Instance.center'
        db.delete_column(u'treemap_instance', 'center')

        # Deleting field 'Tree.owner'
        db.delete_column(u'treemap_tree', 'owner')


    models = {
        u'treemap.audit': {
            'Meta': {'object_name': 'Audit'},
            'action': ('django.db.models.fields.IntegerField', [], {}),
            'created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'current_value': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'field': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'model_id': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'previous_value': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'ref_id': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Audit']", 'null': 'True'}),
            'requires_auth': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'updated': ('django.db.models.fields.DateField', [], {'auto_now': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.IntegerField', [], {})
        },
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
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"}),
            'owner': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        }
    }

    complete_apps = ['treemap']
