# -*- coding: utf-8 -*-
import datetime
from django.db.models import Count
from south.db import db
from south.v2 import DataMigration
from django.db import models

class Migration(DataMigration):

    # We want to add a uniqueness constraint on Species objects:
    #     (instance, common_name, genus, species, cultivar, other_part_of_name) should be unique.
    # But we have duplicates in our own data -- 6 cases where two OTM codes have the same species info.
    # For those 6 pairs we'll keep one and kill the other.
    # Luckily, no production instance has a tree or i-Tree code override pointing to one of the species we want to kill.

    def forwards(self, orm):
        pairs = {
            # kill_code: keep_code
            'AEFL': 'AEOC',
            'SO1': 'LYRA',
            'TITU': 'TITI2',
            'PLOR80': 'THOR',
            'SEBI5': 'CABI2',
            'FRPE_P': 'FRPE2',
            }
        codes_to_kill = pairs.keys()
        codes_to_keep = pairs.values()
        species_to_kill = orm.Species.objects.filter(otm_code__in=codes_to_kill)

        if species_to_kill.exists():
            n_to_kill = species_to_kill.count()
            n_to_keep = orm.Species.objects.filter(otm_code__in=codes_to_keep).count()
            n_killed = 0
            n_updated = 0
            for species in species_to_kill:
                code_to_keep = pairs[species.otm_code]
                species_to_keep = orm.Species.objects \
                    .filter(instance_id=species.instance_id, otm_code=code_to_keep)
                if species_to_keep.count() > 1:
                    raise Exception('Unexpected duplicate: %s in %s' % (code_to_keep, species.instance))
                if species_to_keep.exists():
                    # Delete the duplicate species
                    species.delete()
                    n_killed += 1
                else:
                    # Just change the OTM code so the species remains in the instance
                    species.otm_code = code_to_keep
                    species.save()
                    n_updated += 1

            n_to_kill_remaining = orm.Species.objects.filter(otm_code__in=codes_to_kill).count()
            n_to_keep_remaining = orm.Species.objects.filter(otm_code__in=codes_to_keep).count()

            if n_to_kill_remaining > 0:
                raise Exception('Failed to kill all desired species')
            if n_to_keep + n_updated != n_to_keep_remaining:
                raise Exception('Unexpected number of keeper species remaining')

            print('Removed duplicate species -- killed %s, updated %s' % (n_killed, n_updated))

    def backwards(self, orm):
        print('Species removed by this migration cannot be restored.')

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
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'current_value': ('django.db.models.fields.TextField', [], {'null': 'True', 'db_index': 'True'}),
            'field': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']", 'null': 'True', 'blank': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'model_id': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'db_index': 'True'}),
            'previous_value': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'ref': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Audit']", 'null': 'True'}),
            'requires_auth': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'db_index': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.User']"})
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
        u'treemap.fieldpermission': {
            'Meta': {'unique_together': "((u'model_name', u'field_name', u'role', u'instance'),)", 'object_name': 'FieldPermission'},
            'field_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"}),
            'model_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'permission_level': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'role': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Role']"})
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
        u'treemap.itreecodeoverride': {
            'Meta': {'unique_together': "((u'instance_species', u'region'),)", 'object_name': 'ITreeCodeOverride'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance_species': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Species']"}),
            'itree_code': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'region': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.ITreeRegion']"})
        },
        u'treemap.itreeregion': {
            'Meta': {'object_name': 'ITreeRegion'},
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'}),
            'geometry': ('django.contrib.gis.db.models.fields.MultiPolygonField', [], {'srid': '3857'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
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
        u'treemap.mapfeaturephoto': {
            'Meta': {'object_name': 'MapFeaturePhoto'},
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.files.ImageField', [], {'max_length': '100'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"}),
            'map_feature': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.MapFeature']"}),
            'thumbnail': ('django.db.models.fields.files.ImageField', [], {'max_length': '100'})
        },
        u'treemap.plot': {
            'Meta': {'object_name': 'Plot', '_ormbases': [u'treemap.MapFeature']},
            'length': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            u'mapfeature_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['treemap.MapFeature']", 'unique': 'True', 'primary_key': 'True'}),
            'owner_orig_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'width': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'})
        },
        u'treemap.reputationmetric': {
            'Meta': {'object_name': 'ReputationMetric'},
            'action': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'approval_score': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'denial_score': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'direct_write_score': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"}),
            'model_name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
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
            'common_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'cultivar': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'fact_sheet_url': ('django.db.models.fields.URLField', [], {'max_length': '255', 'blank': 'True'}),
            'fall_conspicuous': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'flower_conspicuous': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'flowering_period': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'fruit_or_nut_period': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'gender': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'genus': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'has_wildlife_value': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"}),
            'is_native': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'max_diameter': ('django.db.models.fields.IntegerField', [], {'default': '200'}),
            'max_height': ('django.db.models.fields.IntegerField', [], {'default': '800'}),
            'other_part_of_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'otm_code': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'palatable_human': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'plant_guide_url': ('django.db.models.fields.URLField', [], {'max_length': '255', 'blank': 'True'}),
            'species': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'udfs': (u'treemap.udf.UDFField', [], {'db_index': 'True', 'blank': 'True'})
        },
        u'treemap.staticpage': {
            'Meta': {'object_name': 'StaticPage'},
            'content': ('django.db.models.fields.TextField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'treemap.tree': {
            'Meta': {'object_name': 'Tree'},
            'canopy_height': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'date_planted': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'date_removed': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'diameter': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'height': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"}),
            'plot': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Plot']"}),
            'readonly': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'species': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Species']", 'null': 'True', 'blank': 'True'}),
            'udfs': (u'treemap.udf.UDFField', [], {'db_index': 'True', 'blank': 'True'})
        },
        u'treemap.treefavorite': {
            'Meta': {'unique_together': "((u'user', u'tree'),)", 'object_name': 'TreeFavorite'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'tree': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Tree']"}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.User']"})
        },
        u'treemap.treephoto': {
            'Meta': {'object_name': 'TreePhoto', '_ormbases': [u'treemap.MapFeaturePhoto']},
            u'mapfeaturephoto_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['treemap.MapFeaturePhoto']", 'unique': 'True', 'primary_key': 'True'}),
            'tree': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Tree']"})
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
        },
        u'treemap.userdefinedcollectionvalue': {
            'Meta': {'object_name': 'UserDefinedCollectionValue'},
            'data': (u'django_hstore.fields.DictionaryField', [], {}),
            'field_definition': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.UserDefinedFieldDefinition']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model_id': ('django.db.models.fields.IntegerField', [], {})
        },
        u'treemap.userdefinedfielddefinition': {
            'Meta': {'object_name': 'UserDefinedFieldDefinition'},
            'datatype': ('django.db.models.fields.TextField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['treemap.Instance']"}),
            'iscollection': ('django.db.models.fields.BooleanField', [], {}),
            'model_type': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        }
    }

    complete_apps = ['treemap']
    symmetrical = True
