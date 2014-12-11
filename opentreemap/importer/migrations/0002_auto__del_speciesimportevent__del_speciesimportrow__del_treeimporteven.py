# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting model 'SpeciesImportEvent'
        db.delete_table(u'importer_speciesimportevent')

        # Deleting model 'SpeciesImportRow'
        db.delete_table(u'importer_speciesimportrow')

        # Deleting model 'TreeImportEvent'
        db.delete_table(u'importer_treeimportevent')

        # Deleting model 'TreeImportRow'
        db.delete_table(u'importer_treeimportrow')


    def backwards(self, orm):
        # Adding model 'SpeciesImportEvent'
        db.create_table(u'importer_speciesimportevent', (
            ('status', self.gf('django.db.models.fields.IntegerField')(default=1)),
            ('file_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('completed', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('owner', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.User'])),
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('max_tree_height_conversion_factor', self.gf('django.db.models.fields.FloatField')(default=1.0)),
            ('field_order', self.gf('django.db.models.fields.TextField')(default=u'')),
            ('errors', self.gf('django.db.models.fields.TextField')(default=u'')),
            ('commited', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('max_diameter_conversion_factor', self.gf('django.db.models.fields.FloatField')(default=1.0)),
            ('instance', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Instance'])),
        ))
        db.send_create_signal(u'importer', ['SpeciesImportEvent'])

        # Adding model 'SpeciesImportRow'
        db.create_table(u'importer_speciesimportrow', (
            ('status', self.gf('django.db.models.fields.IntegerField')(default=3)),
            ('finished', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('errors', self.gf('django.db.models.fields.TextField')(default=u'')),
            ('idx', self.gf('django.db.models.fields.IntegerField')()),
            ('import_event', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['importer.SpeciesImportEvent'])),
            ('data', self.gf('django.db.models.fields.TextField')()),
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('merged', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('species', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Species'], null=True, blank=True)),
        ))
        db.send_create_signal(u'importer', ['SpeciesImportRow'])

        # Adding model 'TreeImportEvent'
        db.create_table(u'importer_treeimportevent', (
            ('status', self.gf('django.db.models.fields.IntegerField')(default=1)),
            ('field_order', self.gf('django.db.models.fields.TextField')(default=u'')),
            ('errors', self.gf('django.db.models.fields.TextField')(default=u'')),
            ('commited', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('file_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('completed', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('instance', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Instance'])),
            ('canopy_height_conversion_factor', self.gf('django.db.models.fields.FloatField')(default=1.0)),
            ('diameter_conversion_factor', self.gf('django.db.models.fields.FloatField')(default=1.0)),
            ('owner', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.User'])),
            ('tree_height_conversion_factor', self.gf('django.db.models.fields.FloatField')(default=1.0)),
            ('plot_length_conversion_factor', self.gf('django.db.models.fields.FloatField')(default=1.0)),
            ('plot_width_conversion_factor', self.gf('django.db.models.fields.FloatField')(default=1.0)),
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal(u'importer', ['TreeImportEvent'])

        # Adding model 'TreeImportRow'
        db.create_table(u'importer_treeimportrow', (
            ('status', self.gf('django.db.models.fields.IntegerField')(default=3)),
            ('plot', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Plot'], null=True, blank=True)),
            ('finished', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('errors', self.gf('django.db.models.fields.TextField')(default=u'')),
            ('idx', self.gf('django.db.models.fields.IntegerField')()),
            ('import_event', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['importer.TreeImportEvent'])),
            ('data', self.gf('django.db.models.fields.TextField')()),
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal(u'importer', ['TreeImportRow'])


    models = {
        
    }

    complete_apps = ['importer']