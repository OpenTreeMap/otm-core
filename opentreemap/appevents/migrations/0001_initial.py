# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'AppEvent'
        db.create_table(u'appevents_appevent', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('event_type', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('data', self.gf('treemap.json_field.JSONField')(blank=True)),
            ('triggered_at', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('handler_assigned_at', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('handled_by', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('handled_at', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('handler_succeeded', self.gf('django.db.models.fields.NullBooleanField')(null=True, blank=True)),
            ('handler_log', self.gf('django.db.models.fields.TextField')(blank=True)),
        ))
        db.send_create_signal(u'appevents', ['AppEvent'])


    def backwards(self, orm):
        # Deleting model 'AppEvent'
        db.delete_table(u'appevents_appevent')


    models = {
        u'appevents.appevent': {
            'Meta': {'object_name': 'AppEvent'},
            'data': ('treemap.json_field.JSONField', [], {'blank': 'True'}),
            'event_type': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'handled_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'handled_by': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'handler_assigned_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'handler_log': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'handler_succeeded': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'triggered_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['appevents']