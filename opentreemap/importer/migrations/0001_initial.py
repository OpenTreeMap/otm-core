# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'SpeciesImportEvent'
        db.create_table(u'importer_speciesimportevent', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('file_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('errors', self.gf('django.db.models.fields.TextField')(default=u'')),
            ('field_order', self.gf('django.db.models.fields.TextField')(default=u'')),
            ('owner', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.User'])),
            ('instance', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Instance'])),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('completed', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('status', self.gf('django.db.models.fields.IntegerField')(default=1)),
            ('commited', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('max_diameter_conversion_factor', self.gf('django.db.models.fields.FloatField')(default=1.0)),
            ('max_tree_height_conversion_factor', self.gf('django.db.models.fields.FloatField')(default=1.0)),
        ))
        db.send_create_signal(u'importer', ['SpeciesImportEvent'])

        # Adding model 'TreeImportEvent'
        db.create_table(u'importer_treeimportevent', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('file_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('errors', self.gf('django.db.models.fields.TextField')(default=u'')),
            ('field_order', self.gf('django.db.models.fields.TextField')(default=u'')),
            ('owner', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.User'])),
            ('instance', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Instance'])),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('completed', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('status', self.gf('django.db.models.fields.IntegerField')(default=1)),
            ('commited', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('plot_length_conversion_factor', self.gf('django.db.models.fields.FloatField')(default=1.0)),
            ('plot_width_conversion_factor', self.gf('django.db.models.fields.FloatField')(default=1.0)),
            ('diameter_conversion_factor', self.gf('django.db.models.fields.FloatField')(default=1.0)),
            ('tree_height_conversion_factor', self.gf('django.db.models.fields.FloatField')(default=1.0)),
            ('canopy_height_conversion_factor', self.gf('django.db.models.fields.FloatField')(default=1.0)),
        ))
        db.send_create_signal(u'importer', ['TreeImportEvent'])

        # Adding model 'SpeciesImportRow'
        db.create_table(u'importer_speciesimportrow', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('data', self.gf('django.db.models.fields.TextField')()),
            ('idx', self.gf('django.db.models.fields.IntegerField')()),
            ('finished', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('errors', self.gf('django.db.models.fields.TextField')(default=u'')),
            ('status', self.gf('django.db.models.fields.IntegerField')(default=3)),
            ('species', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Species'], null=True, blank=True)),
            ('merged', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('import_event', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['importer.SpeciesImportEvent'])),
        ))
        db.send_create_signal(u'importer', ['SpeciesImportRow'])

        # Adding model 'TreeImportRow'
        db.create_table(u'importer_treeimportrow', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('data', self.gf('django.db.models.fields.TextField')()),
            ('idx', self.gf('django.db.models.fields.IntegerField')()),
            ('finished', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('errors', self.gf('django.db.models.fields.TextField')(default=u'')),
            ('status', self.gf('django.db.models.fields.IntegerField')(default=3)),
            ('plot', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Plot'], null=True, blank=True)),
            ('import_event', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['importer.TreeImportEvent'])),
        ))
        db.send_create_signal(u'importer', ['TreeImportRow'])


    def backwards(self, orm):
        # Deleting model 'SpeciesImportEvent'
        db.delete_table(u'importer_speciesimportevent')

        # Deleting model 'TreeImportEvent'
        db.delete_table(u'importer_treeimportevent')

        # Deleting model 'SpeciesImportRow'
        db.delete_table(u'importer_speciesimportrow')

        # Deleting model 'TreeImportRow'
        db.delete_table(u'importer_treeimportrow')


    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'importer.speciesimportevent': {
            'Meta': {'object_name': 'SpeciesImportEvent'},
            'commited': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'completed': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'errors': ('django.db.models.fields.TextField', [], {'default': "u''"}),
            'field_order': ('django.db.models.fields.TextField', [], {'default': "u''"}),
            'file_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"}),
            'max_diameter_conversion_factor': ('django.db.models.fields.FloatField', [], {'default': '1.0'}),
            'max_tree_height_conversion_factor': ('django.db.models.fields.FloatField', [], {'default': '1.0'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.User']"}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '1'})
        },
        u'importer.speciesimportrow': {
            'Meta': {'object_name': 'SpeciesImportRow'},
            'data': ('django.db.models.fields.TextField', [], {}),
            'errors': ('django.db.models.fields.TextField', [], {'default': "u''"}),
            'finished': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idx': ('django.db.models.fields.IntegerField', [], {}),
            'import_event': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['importer.SpeciesImportEvent']"}),
            'merged': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'species': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Species']", 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '3'})
        },
        u'importer.treeimportevent': {
            'Meta': {'object_name': 'TreeImportEvent'},
            'canopy_height_conversion_factor': ('django.db.models.fields.FloatField', [], {'default': '1.0'}),
            'commited': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'completed': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'diameter_conversion_factor': ('django.db.models.fields.FloatField', [], {'default': '1.0'}),
            'errors': ('django.db.models.fields.TextField', [], {'default': "u''"}),
            'field_order': ('django.db.models.fields.TextField', [], {'default': "u''"}),
            'file_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.User']"}),
            'plot_length_conversion_factor': ('django.db.models.fields.FloatField', [], {'default': '1.0'}),
            'plot_width_conversion_factor': ('django.db.models.fields.FloatField', [], {'default': '1.0'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'tree_height_conversion_factor': ('django.db.models.fields.FloatField', [], {'default': '1.0'})
        },
        u'importer.treeimportrow': {
            'Meta': {'object_name': 'TreeImportRow'},
            'data': ('django.db.models.fields.TextField', [], {}),
            'errors': ('django.db.models.fields.TextField', [], {'default': "u''"}),
            'finished': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idx': ('django.db.models.fields.IntegerField', [], {}),
            'import_event': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['importer.TreeImportEvent']"}),
            'plot': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Plot']", 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '3'})
        },
        u'treemap.benefitcurrencyconversion': {
            'Meta': {'object_name': 'BenefitCurrencyConversion'},
            'co2_lb_to_currency': ('django.db.models.fields.FloatField', [], {}),
            'currency_symbol': ('django.db.models.fields.CharField', [], {'max_length': '5'}),
            'electricity_kwh_to_currency': ('django.db.models.fields.FloatField', [], {}),
            'h20_gal_to_currency': ('django.db.models.fields.FloatField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'natural_gas_kbtu_to_currency': ('django.db.models.fields.FloatField', [], {}),
            'nox_lb_to_currency': ('django.db.models.fields.FloatField', [], {}),
            'o3_lb_to_currency': ('django.db.models.fields.FloatField', [], {}),
            'pm10_lb_to_currency': ('django.db.models.fields.FloatField', [], {}),
            'sox_lb_to_currency': ('django.db.models.fields.FloatField', [], {}),
            'voc_lb_to_currency': ('django.db.models.fields.FloatField', [], {})
        },
        u'treemap.boundary': {
            'Meta': {'object_name': 'Boundary'},
            'category': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'geom': ('django.contrib.gis.db.models.fields.MultiPolygonField', [], {'srid': '3857', 'db_column': "u'the_geom_webmercator'"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'sort_order': ('django.db.models.fields.IntegerField', [], {})
        },
        u'treemap.instance': {
            'Meta': {'object_name': 'Instance'},
            'adjuncts_timestamp': ('django.db.models.fields.BigIntegerField', [], {'default': '0'}),
            'basemap_data': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'basemap_type': ('django.db.models.fields.CharField', [], {'default': "u'google'", 'max_length': '255'}),
            'boundaries': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': u"orm['treemap.Boundary']", 'null': 'True', 'blank': 'True'}),
            'bounds': ('django.contrib.gis.db.models.fields.MultiPolygonField', [], {'srid': '3857'}),
            'center_override': ('django.contrib.gis.db.models.fields.PointField', [], {'srid': '3857', 'null': 'True', 'blank': 'True'}),
            'config': ('treemap.json_field.JSONField', [], {'blank': 'True'}),
            'default_role': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'default_role'", 'to': u"orm['treemap.Role']"}),
            'eco_benefits_conversion': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.BenefitCurrencyConversion']", 'null': 'True', 'blank': 'True'}),
            'geo_rev': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'itree_region_default': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'logo': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'url_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'users': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': u"orm['treemap.User']", 'null': 'True', 'through': u"orm['treemap.InstanceUser']", 'blank': 'True'})
        },
        u'treemap.instanceuser': {
            'Meta': {'unique_together': "((u'instance', u'user'),)", 'object_name': 'InstanceUser'},
            'admin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"}),
            'reputation': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'role': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Role']"}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.User']"})
        },
        u'treemap.mapfeature': {
            'Meta': {'object_name': 'MapFeature'},
            'address_city': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'address_street': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'address_zip': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True', 'blank': 'True'}),
            'feature_type': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'geom': ('django.contrib.gis.db.models.fields.PointField', [], {'srid': '3857', 'db_column': "u'the_geom_webmercator'"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"}),
            'readonly': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'udfs': (u'treemap.udf.UDFField', [], {'db_index': 'True', 'blank': 'True'})
        },
        u'treemap.plot': {
            'Meta': {'object_name': 'Plot', '_ormbases': [u'treemap.MapFeature']},
            'length': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            u'mapfeature_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['treemap.MapFeature']", 'unique': 'True', 'primary_key': 'True'}),
            'owner_orig_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'width': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'})
        },
        u'treemap.role': {
            'Meta': {'object_name': 'Role'},
            'default_permission': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']", 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'rep_thresh': ('django.db.models.fields.IntegerField', [], {})
        },
        u'treemap.species': {
            'Meta': {'object_name': 'Species'},
            'bloom_period': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'common_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'cultivar': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'fact_sheet': ('django.db.models.fields.URLField', [], {'max_length': '255', 'blank': 'True'}),
            'fall_conspicuous': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'flower_conspicuous': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'fruit_period': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'gender': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'genus': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"}),
            'max_dbh': ('django.db.models.fields.IntegerField', [], {'default': '200'}),
            'max_height': ('django.db.models.fields.IntegerField', [], {'default': '800'}),
            'native_status': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'other': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'otm_code': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'palatable_human': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'plant_guide': ('django.db.models.fields.URLField', [], {'max_length': '255', 'blank': 'True'}),
            'species': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'udfs': (u'treemap.udf.UDFField', [], {'db_index': 'True', 'blank': 'True'}),
            'wildlife_value': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'})
        },
        u'treemap.user': {
            'Meta': {'object_name': 'User'},
            'allow_email_contact': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Group']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '30', 'blank': 'True'}),
            'make_info_public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'organization': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'photo': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'thumbnail': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        }
    }

    complete_apps = ['importer']