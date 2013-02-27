# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


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
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.User'])),
            ('action', self.gf('django.db.models.fields.IntegerField')()),
            ('requires_auth', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('ref_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Audit'], null=True)),
            ('created', self.gf('django.db.models.fields.DateField')(auto_now_add=True, blank=True)),
            ('updated', self.gf('django.db.models.fields.DateField')(auto_now=True, blank=True)),
        ))
        db.send_create_signal(u'treemap', ['Audit'])

        # Adding model 'User'
        db.create_table(u'treemap_user', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('password', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('last_login', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('is_superuser', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('username', self.gf('django.db.models.fields.CharField')(unique=True, max_length=30)),
            ('first_name', self.gf('django.db.models.fields.CharField')(max_length=30, blank=True)),
            ('last_name', self.gf('django.db.models.fields.CharField')(max_length=30, blank=True)),
            ('email', self.gf('django.db.models.fields.EmailField')(max_length=75, blank=True)),
            ('is_staff', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('date_joined', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
        ))
        db.send_create_signal(u'treemap', ['User'])

        # Adding M2M table for field groups on 'User'
        db.create_table(u'treemap_user_groups', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('user', models.ForeignKey(orm[u'treemap.user'], null=False)),
            ('group', models.ForeignKey(orm[u'auth.group'], null=False))
        ))
        db.create_unique(u'treemap_user_groups', ['user_id', 'group_id'])

        # Adding M2M table for field user_permissions on 'User'
        db.create_table(u'treemap_user_user_permissions', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('user', models.ForeignKey(orm[u'treemap.user'], null=False)),
            ('permission', models.ForeignKey(orm[u'auth.permission'], null=False))
        ))
        db.create_unique(u'treemap_user_user_permissions', ['user_id', 'permission_id'])

        # Adding model 'Instance'
        db.create_table(u'treemap_instance', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('geo_rev', self.gf('django.db.models.fields.IntegerField')(default=1)),
            ('center', self.gf('django.contrib.gis.db.models.fields.PointField')(srid=3857)),
        ))
        db.send_create_signal(u'treemap', ['Instance'])

        # Adding model 'Species'
        db.create_table(u'treemap_species', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('symbol', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('genus', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('species', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('cultivar_name', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('gender', self.gf('django.db.models.fields.CharField')(max_length=50, null=True, blank=True)),
            ('common_name', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('native_status', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('bloom_period', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('fruit_period', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
            ('fall_conspicuous', self.gf('django.db.models.fields.NullBooleanField')(null=True, blank=True)),
            ('flower_conspicuous', self.gf('django.db.models.fields.NullBooleanField')(null=True, blank=True)),
            ('palatable_human', self.gf('django.db.models.fields.NullBooleanField')(null=True, blank=True)),
            ('wildlife_value', self.gf('django.db.models.fields.NullBooleanField')(null=True, blank=True)),
            ('fact_sheet', self.gf('django.db.models.fields.URLField')(max_length=255, null=True, blank=True)),
            ('plant_guide', self.gf('django.db.models.fields.URLField')(max_length=255, null=True, blank=True)),
            ('max_dbh', self.gf('django.db.models.fields.IntegerField')(default=200)),
            ('max_height', self.gf('django.db.models.fields.IntegerField')(default=800)),
        ))
        db.send_create_signal(u'treemap', ['Species'])

        # Adding model 'InstanceSpecies'
        db.create_table(u'treemap_instancespecies', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('instance', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Instance'])),
            ('species', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Species'])),
            ('common_name', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, blank=True)),
        ))
        db.send_create_signal(u'treemap', ['InstanceSpecies'])

        # Adding model 'ImportEvent'
        db.create_table(u'treemap_importevent', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('imported_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.User'])),
            ('imported_on', self.gf('django.db.models.fields.DateField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal(u'treemap', ['ImportEvent'])

        # Adding model 'Plot'
        db.create_table(u'treemap_plot', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('instance', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Instance'])),
            ('geom', self.gf('django.contrib.gis.db.models.fields.PointField')(srid=3857, db_column='the_geom_webmercator')),
            ('width', self.gf('django.db.models.fields.FloatField')(null=True, blank=True)),
            ('length', self.gf('django.db.models.fields.FloatField')(null=True, blank=True)),
            ('address_street', self.gf('django.db.models.fields.CharField')(max_length=256, null=True, blank=True)),
            ('address_city', self.gf('django.db.models.fields.CharField')(max_length=256, null=True, blank=True)),
            ('address_zip', self.gf('django.db.models.fields.CharField')(max_length=30, null=True, blank=True)),
            ('created_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.User'])),
            ('import_event', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.ImportEvent'], null=True, blank=True)),
            ('owner_orig_id', self.gf('django.db.models.fields.CharField')(max_length=256, null=True, blank=True)),
            ('readonly', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'treemap', ['Plot'])

        # Adding model 'Tree'
        db.create_table(u'treemap_tree', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('instance', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Instance'])),
            ('plot', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Plot'])),
            ('species', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.Species'], null=True, blank=True)),
            ('created_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.User'])),
            ('import_event', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['treemap.ImportEvent'], null=True, blank=True)),
            ('readonly', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('diameter', self.gf('django.db.models.fields.FloatField')(null=True, blank=True)),
            ('height', self.gf('django.db.models.fields.FloatField')(null=True, blank=True)),
            ('canopy_height', self.gf('django.db.models.fields.FloatField')(null=True, blank=True)),
            ('date_planted', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
            ('date_removed', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'treemap', ['Tree'])

        # Adding model 'BoundaryZones'
        db.create_table(u'treemap_boundaryzones', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('geom', self.gf('django.contrib.gis.db.models.fields.MultiPolygonField')(srid=3857)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('category', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('sort_order', self.gf('django.db.models.fields.IntegerField')()),
        ))
        db.send_create_signal(u'treemap', ['BoundaryZones'])


    def backwards(self, orm):
        # Deleting model 'Audit'
        db.delete_table(u'treemap_audit')

        # Deleting model 'User'
        db.delete_table(u'treemap_user')

        # Removing M2M table for field groups on 'User'
        db.delete_table('treemap_user_groups')

        # Removing M2M table for field user_permissions on 'User'
        db.delete_table('treemap_user_user_permissions')

        # Deleting model 'Instance'
        db.delete_table(u'treemap_instance')

        # Deleting model 'Species'
        db.delete_table(u'treemap_species')

        # Deleting model 'InstanceSpecies'
        db.delete_table(u'treemap_instancespecies')

        # Deleting model 'ImportEvent'
        db.delete_table(u'treemap_importevent')

        # Deleting model 'Plot'
        db.delete_table(u'treemap_plot')

        # Deleting model 'Tree'
        db.delete_table(u'treemap_tree')

        # Deleting model 'BoundaryZones'
        db.delete_table(u'treemap_boundaryzones')


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
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.User']"})
        },
        u'treemap.boundaryzones': {
            'Meta': {'object_name': 'BoundaryZones'},
            'category': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'geom': ('django.contrib.gis.db.models.fields.MultiPolygonField', [], {'srid': '3857'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'sort_order': ('django.db.models.fields.IntegerField', [], {})
        },
        u'treemap.importevent': {
            'Meta': {'object_name': 'ImportEvent'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'imported_by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.User']"}),
            'imported_on': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'})
        },
        u'treemap.instance': {
            'Meta': {'object_name': 'Instance'},
            'center': ('django.contrib.gis.db.models.fields.PointField', [], {'srid': '3857'}),
            'geo_rev': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        u'treemap.instancespecies': {
            'Meta': {'object_name': 'InstanceSpecies'},
            'common_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"}),
            'species': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Species']"})
        },
        u'treemap.plot': {
            'Meta': {'object_name': 'Plot'},
            'address_city': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'blank': 'True'}),
            'address_street': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'blank': 'True'}),
            'address_zip': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True', 'blank': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.User']"}),
            'geom': ('django.contrib.gis.db.models.fields.PointField', [], {'srid': '3857', 'db_column': "'the_geom_webmercator'"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'import_event': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.ImportEvent']", 'null': 'True', 'blank': 'True'}),
            'length': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"}),
            'owner_orig_id': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'blank': 'True'}),
            'readonly': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'width': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'})
        },
        u'treemap.species': {
            'Meta': {'object_name': 'Species'},
            'bloom_period': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'common_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'cultivar_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'fact_sheet': ('django.db.models.fields.URLField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'fall_conspicuous': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'flower_conspicuous': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'fruit_period': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'gender': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'genus': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'max_dbh': ('django.db.models.fields.IntegerField', [], {'default': '200'}),
            'max_height': ('django.db.models.fields.IntegerField', [], {'default': '800'}),
            'native_status': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'palatable_human': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'plant_guide': ('django.db.models.fields.URLField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'species': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'symbol': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'wildlife_value': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'})
        },
        u'treemap.tree': {
            'Meta': {'object_name': 'Tree'},
            'canopy_height': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.User']"}),
            'date_planted': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date_removed': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'diameter': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'height': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'import_event': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.ImportEvent']", 'null': 'True', 'blank': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"}),
            'plot': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Plot']"}),
            'readonly': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'species': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Species']", 'null': 'True', 'blank': 'True'})
        },
        u'treemap.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        }
    }

    complete_apps = ['treemap']
