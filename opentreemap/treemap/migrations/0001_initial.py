# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import re
import django.contrib.gis.db.models.fields
import django.contrib.postgres.fields.hstore
import treemap.json_field
import treemap.instance
import django.contrib.auth.models
import treemap.audit
import django.utils.timezone
from django.conf import settings
import treemap.udf
import django.core.validators
import treemap.units


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0006_require_contenttypes_0002'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(default=django.utils.timezone.now, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(help_text='Required. 30 characters or fewer. Letters, numbers and @/./+/-/_ characters', unique=True, max_length=30, verbose_name='username', validators=[django.core.validators.RegexValidator(re.compile('^[\\w.@+-]+$'), 'Enter a valid username.', 'invalid')])),
                ('email', models.EmailField(unique=True, max_length=75, verbose_name='email address', blank=True)),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('photo', models.ImageField(null=True, upload_to='users', blank=True)),
                ('thumbnail', models.ImageField(null=True, upload_to='users', blank=True)),
                ('first_name', models.CharField(default='', max_length=30, verbose_name='first name', blank=True)),
                ('last_name', models.CharField(default='', max_length=30, verbose_name='last name', blank=True)),
                ('organization', models.CharField(default='', max_length=255, blank=True)),
                ('make_info_public', models.BooleanField(default=False)),
                ('allow_email_contact', models.BooleanField(default=False)),
                ('groups', models.ManyToManyField(related_query_name='user', related_name='user_set', to='auth.Group', blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(related_query_name='user', related_name='user_set', to='auth.Permission', blank=True, help_text='Specific permissions for this user.', verbose_name='user permissions')),
            ],
            options={
                'abstract': False,
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
            },
            bases=(models.Model, treemap.audit.Auditable),
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='Audit',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('model', models.CharField(max_length=255, null=True, db_index=True)),
                ('model_id', models.IntegerField(null=True, db_index=True)),
                ('field', models.CharField(max_length=255, null=True)),
                ('previous_value', models.TextField(null=True)),
                ('current_value', models.TextField(null=True, db_index=True)),
                ('action', models.IntegerField()),
                ('requires_auth', models.BooleanField(default=False)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name='BenefitCurrencyConversion',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('currency_symbol', models.CharField(max_length=5)),
                ('electricity_kwh_to_currency', models.FloatField()),
                ('natural_gas_kbtu_to_currency', models.FloatField()),
                ('h20_gal_to_currency', models.FloatField()),
                ('co2_lb_to_currency', models.FloatField()),
                ('o3_lb_to_currency', models.FloatField()),
                ('nox_lb_to_currency', models.FloatField()),
                ('pm10_lb_to_currency', models.FloatField()),
                ('sox_lb_to_currency', models.FloatField()),
                ('voc_lb_to_currency', models.FloatField()),
            ],
            bases=(treemap.audit.Dictable, models.Model),
        ),
        migrations.CreateModel(
            name='Boundary',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('geom', django.contrib.gis.db.models.fields.MultiPolygonField(srid=3857, db_column='the_geom_webmercator')),
                ('name', models.CharField(max_length=255)),
                ('category', models.CharField(max_length=255)),
                ('sort_order', models.IntegerField()),
                ('updated_at', models.DateTimeField(db_index=True, auto_now=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Favorite',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='FieldPermission',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('model_name', models.CharField(max_length=255)),
                ('field_name', models.CharField(max_length=255)),
                ('permission_level', models.IntegerField(default=0, choices=[(0, 'None'), (1, 'Read Only'), (2, 'Write with Audit'), (3, 'Write Directly')])),
            ],
        ),
        migrations.CreateModel(
            name='Instance',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=255)),
                ('url_name', models.CharField(unique=True, max_length=255, validators=[treemap.instance.reserved_name_validator, django.core.validators.RegexValidator('^[a-zA-Z]+[a-zA-Z0-9\\-]*$', 'Must start with a letter and may only contain letters, numbers, or dashes ("-")', 'Invalid URL name')])),
                ('basemap_type', models.CharField(default='google', max_length=255, choices=[('google', 'Google'), ('bing', 'Bing'), ('tms', 'Tile Map Service')])),
                ('basemap_data', models.CharField(max_length=255, null=True, blank=True)),
                ('geo_rev', models.IntegerField(default=1)),
                ('bounds', django.contrib.gis.db.models.fields.MultiPolygonField(srid=3857)),
                ('center_override', django.contrib.gis.db.models.fields.PointField(srid=3857, null=True, blank=True)),
                ('config', treemap.json_field.JSONField(blank=True)),
                ('is_public', models.BooleanField(default=False)),
                ('logo', models.ImageField(null=True, upload_to='logos', blank=True)),
                ('itree_region_default', models.CharField(blank=True, max_length=20, null=True, choices=[(b'TpIntWBOI', b'Temperate Interior West'), (b'NoEastXXX', b'Northeast'), (b'CaNCCoJBK', b'Northern California Coast'), (b'InterWABQ', b'Interior West'), (b'InlEmpCLM', b'Inland Empire'), (b'LoMidWXXX', b'Lower Midwest'), (b'MidWstMSP', b'Midwest'), (b'NMtnPrFNL', b'North'), (b'PacfNWLOG', b'Pacific Northwest'), (b'PiedmtCLT', b'South'), (b'SoCalCSMA', b'Southern California Coast'), (b'GulfCoCHS', b'Coastal Plain'), (b'SWDsrtGDL', b'Southwest Desert'), (b'InlValMOD', b'Inland Valleys'), (b'CenFlaXXX', b'Central Florida'), (b'TropicPacXXX', b'Tropical')])),
                ('adjuncts_timestamp', models.BigIntegerField(default=0)),
                ('non_admins_can_export', models.BooleanField(default=True)),
                ('boundaries', models.ManyToManyField(to='treemap.Boundary', null=True, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='InstanceUser',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('reputation', models.IntegerField(default=0)),
                ('admin', models.BooleanField(default=False)),
                ('instance', models.ForeignKey(to='treemap.Instance')),
            ],
            bases=(treemap.audit.Auditable, models.Model),
        ),
        migrations.CreateModel(
            name='ITreeCodeOverride',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('itree_code', models.CharField(max_length=100)),
            ],
            bases=(models.Model, treemap.audit.Auditable),
        ),
        migrations.CreateModel(
            name='ITreeRegion',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', models.CharField(unique=True, max_length=40)),
                ('geometry', django.contrib.gis.db.models.fields.MultiPolygonField(srid=3857)),
            ],
        ),
        migrations.CreateModel(
            name='MapFeature',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('udfs', treemap.udf.UDFField(db_index=True, blank=True)),
                ('geom', django.contrib.gis.db.models.fields.PointField(srid=3857, db_column='the_geom_webmercator')),
                ('address_street', models.CharField(help_text='Address', max_length=255, null=True, blank=True)),
                ('address_city', models.CharField(help_text='City', max_length=255, null=True, blank=True)),
                ('address_zip', models.CharField(help_text='Postal Code', max_length=30, null=True, blank=True)),
                ('readonly', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(default=django.utils.timezone.now, help_text='Last Updated')),
                ('feature_type', models.CharField(max_length=255)),
            ],
            options={
                'abstract': False,
            },
            bases=(treemap.units.Convertible, treemap.audit.PendingAuditable, treemap.audit.UserTrackable, models.Model),
        ),
        migrations.CreateModel(
            name='MapFeaturePhoto',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('image', models.ImageField(upload_to='trees/%Y/%m/%d', editable=False)),
                ('thumbnail', models.ImageField(upload_to='trees_thumbs/%Y/%m/%d', editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            bases=(models.Model, treemap.audit.PendingAuditable),
        ),
        migrations.CreateModel(
            name='ReputationMetric',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('model_name', models.CharField(max_length=255)),
                ('action', models.CharField(max_length=255)),
                ('direct_write_score', models.IntegerField(null=True, blank=True)),
                ('approval_score', models.IntegerField(null=True, blank=True)),
                ('denial_score', models.IntegerField(null=True, blank=True)),
                ('instance', models.ForeignKey(to='treemap.Instance')),
            ],
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('default_permission', models.IntegerField(default=0, choices=[(0, 'None'), (1, 'Read Only'), (2, 'Write with Audit'), (3, 'Write Directly')])),
                ('rep_thresh', models.IntegerField()),
                ('instance', models.ForeignKey(blank=True, to='treemap.Instance', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Species',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('udfs', treemap.udf.UDFField(db_index=True, blank=True)),
                ('otm_code', models.CharField(max_length=255)),
                ('common_name', models.CharField(max_length=255)),
                ('genus', models.CharField(max_length=255)),
                ('species', models.CharField(max_length=255, blank=True)),
                ('cultivar', models.CharField(max_length=255, blank=True)),
                ('other_part_of_name', models.CharField(max_length=255, blank=True)),
                ('is_native', models.NullBooleanField()),
                ('flowering_period', models.CharField(max_length=255, blank=True)),
                ('fruit_or_nut_period', models.CharField(max_length=255, blank=True)),
                ('fall_conspicuous', models.NullBooleanField()),
                ('flower_conspicuous', models.NullBooleanField()),
                ('palatable_human', models.NullBooleanField()),
                ('has_wildlife_value', models.NullBooleanField()),
                ('fact_sheet_url', models.URLField(max_length=255, blank=True)),
                ('plant_guide_url', models.URLField(max_length=255, blank=True)),
                ('max_diameter', models.IntegerField(default=200)),
                ('max_height', models.IntegerField(default=800)),
                ('updated_at', models.DateTimeField(db_index=True, auto_now=True, null=True)),
                ('instance', models.ForeignKey(to='treemap.Instance')),
            ],
            options={
                'verbose_name_plural': 'Species',
            },
            bases=(treemap.audit.PendingAuditable, treemap.audit.UserTrackable, models.Model),
        ),
        migrations.CreateModel(
            name='StaticPage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100)),
                ('content', models.TextField()),
                ('instance', models.ForeignKey(to='treemap.Instance')),
            ],
        ),
        migrations.CreateModel(
            name='Tree',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('udfs', treemap.udf.UDFField(db_index=True, blank=True)),
                ('readonly', models.BooleanField(default=False)),
                ('diameter', models.FloatField(help_text='Tree Diameter', null=True, blank=True)),
                ('height', models.FloatField(help_text='Tree Height', null=True, blank=True)),
                ('canopy_height', models.FloatField(help_text='Canopy Height', null=True, blank=True)),
                ('date_planted', models.DateField(help_text='Date Planted', null=True, blank=True)),
                ('date_removed', models.DateField(help_text='Date Removed', null=True, blank=True)),
                ('instance', models.ForeignKey(to='treemap.Instance')),
                ('species', models.ForeignKey(blank=True, to='treemap.Species', help_text='Species', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(treemap.units.Convertible, treemap.audit.PendingAuditable, treemap.audit.UserTrackable, models.Model),
        ),
        migrations.CreateModel(
            name='UserDefinedCollectionValue',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('model_id', models.IntegerField()),
                ('data', django.contrib.postgres.fields.hstore.HStoreField()),
            ],
            bases=(treemap.audit.UserTrackable, models.Model),
        ),
        migrations.CreateModel(
            name='UserDefinedFieldDefinition',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('model_type', models.CharField(max_length=255)),
                ('datatype', models.TextField()),
                ('iscollection', models.BooleanField()),
                ('name', models.CharField(max_length=255)),
                ('instance', models.ForeignKey(to='treemap.Instance')),
            ],
        ),
        migrations.CreateModel(
            name='Plot',
            fields=[
                ('mapfeature_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='treemap.MapFeature')),
                ('width', models.FloatField(help_text='Plot Width', null=True, blank=True)),
                ('length', models.FloatField(help_text='Plot Length', null=True, blank=True)),
                ('owner_orig_id', models.CharField(max_length=255, null=True, blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('treemap.mapfeature',),
        ),
        migrations.CreateModel(
            name='TreePhoto',
            fields=[
                ('mapfeaturephoto_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='treemap.MapFeaturePhoto')),
                ('tree', models.ForeignKey(to='treemap.Tree')),
            ],
            bases=('treemap.mapfeaturephoto',),
        ),
        migrations.AddField(
            model_name='userdefinedcollectionvalue',
            name='field_definition',
            field=models.ForeignKey(to='treemap.UserDefinedFieldDefinition'),
        ),
        migrations.AddField(
            model_name='mapfeaturephoto',
            name='instance',
            field=models.ForeignKey(to='treemap.Instance'),
        ),
        migrations.AddField(
            model_name='mapfeaturephoto',
            name='map_feature',
            field=models.ForeignKey(to='treemap.MapFeature'),
        ),
        migrations.AddField(
            model_name='mapfeature',
            name='instance',
            field=models.ForeignKey(to='treemap.Instance'),
        ),
        migrations.AddField(
            model_name='itreecodeoverride',
            name='instance_species',
            field=models.ForeignKey(to='treemap.Species'),
        ),
        migrations.AddField(
            model_name='itreecodeoverride',
            name='region',
            field=models.ForeignKey(to='treemap.ITreeRegion'),
        ),
        migrations.AddField(
            model_name='instanceuser',
            name='role',
            field=models.ForeignKey(to='treemap.Role'),
        ),
        migrations.AddField(
            model_name='instanceuser',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='instance',
            name='default_role',
            field=models.ForeignKey(related_name='default_role', to='treemap.Role'),
        ),
        migrations.AddField(
            model_name='instance',
            name='eco_benefits_conversion',
            field=models.ForeignKey(blank=True, to='treemap.BenefitCurrencyConversion', null=True),
        ),
        migrations.AddField(
            model_name='instance',
            name='users',
            field=models.ManyToManyField(to=settings.AUTH_USER_MODEL, null=True, through='treemap.InstanceUser', blank=True),
        ),
        migrations.AddField(
            model_name='fieldpermission',
            name='instance',
            field=models.ForeignKey(to='treemap.Instance'),
        ),
        migrations.AddField(
            model_name='fieldpermission',
            name='role',
            field=models.ForeignKey(to='treemap.Role'),
        ),
        migrations.AddField(
            model_name='favorite',
            name='map_feature',
            field=models.ForeignKey(to='treemap.MapFeature'),
        ),
        migrations.AddField(
            model_name='favorite',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='audit',
            name='instance',
            field=models.ForeignKey(blank=True, to='treemap.Instance', null=True),
        ),
        migrations.AddField(
            model_name='audit',
            name='ref',
            field=models.ForeignKey(to='treemap.Audit', null=True),
        ),
        migrations.AddField(
            model_name='audit',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='tree',
            name='plot',
            field=models.ForeignKey(to='treemap.Plot'),
        ),
        migrations.AlterUniqueTogether(
            name='species',
            unique_together=set([('instance', 'common_name', 'genus', 'species', 'cultivar', 'other_part_of_name')]),
        ),
        migrations.AlterUniqueTogether(
            name='itreecodeoverride',
            unique_together=set([('instance_species', 'region')]),
        ),
        migrations.AlterUniqueTogether(
            name='instanceuser',
            unique_together=set([('instance', 'user')]),
        ),
        migrations.AlterUniqueTogether(
            name='fieldpermission',
            unique_together=set([('model_name', 'field_name', 'role', 'instance')]),
        ),
        migrations.AlterUniqueTogether(
            name='favorite',
            unique_together=set([('user', 'map_feature')]),
        ),
        migrations.AlterIndexTogether(
            name='audit',
            index_together=set([('instance', 'user', 'updated')]),
        ),
    ]
