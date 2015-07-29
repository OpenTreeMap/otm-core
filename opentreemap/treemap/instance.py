# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.gis.db import models
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import RegexValidator
from django.conf import settings
from django.db.models import F
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext_noop

import hashlib
import json
from urllib import urlencode

from treemap.DotDict import DotDict
from treemap.species import SPECIES
from treemap.species.codes import ITREE_REGIONS
from treemap.json_field import JSONField
from treemap.lib.object_caches import udf_defs
from treemap.species.codes import (species_codes_for_regions,
                                   all_species_codes, ITREE_REGION_CHOICES)

URL_NAME_PATTERN = r'[a-zA-Z]+[a-zA-Z0-9\-]*'

DEFAULT_MOBILE_SEARCH_FIELDS = {
    'standard': [{'search_type': 'SPECIES',
                  'identifier': 'species.id',
                  'label': 'Species'},
                 {'search_type': 'RANGE',
                  'identifier': 'tree.diameter',
                  'label': 'Diameter'},
                 {'search_type': 'RANGE',
                  'identifier': 'tree.height',
                  'label': 'Height'}],
    'missing': [{'identifier': 'species.id',
                 'label': 'Missing Species'},
                {'identifier': 'tree.diameter',
                 'label': 'Missing Diameter'},
                {'identifier': 'mapFeaturePhoto.id',
                 'label': 'Missing Photo'}]
}

DEFAULT_MOBILE_API_FIELDS = (
    {'header': ugettext_noop('Tree Information'),
     'model': 'tree',
     'field_keys': ['tree.species', 'tree.diameter',
                    'tree.height', 'tree.date_planted']},
    {'header': ugettext_noop('Planting Site Information'),
     'model': 'plot',
     'field_keys': ['plot.width', 'plot.length']},
    {'header': ugettext_noop('Stewardship'),
     'collection_udf_keys': ['plot.udf:Stewardship', 'tree.udf:Stewardship'],
     'sort_key': 'Date'}
)

API_FIELD_ERRORS = {
    'no_field_groups': _('Must be a non-empty list'),

    'group_has_no_header': _(
        'Every mobile field group must have a non-empty header'),

    'group_has_no_keys': _(
        'All mobile field groups must have either a "field_keys" or '
        '"collection_udf_keys" containing a non-empty list'),

    'group_has_both_keys': _(
        'Mobile field groups cannot contain both "field_keys" and '
        '"collection_udf_keys" properties'),

    'group_has_no_sort_key': _(
        'Collection field groups must have a non-empty "sort_key" property '
        'defined'),

    'group_has_missing_cudf': _(
        'Collection field groups can only contain existing custom collection '
        'fields'),

    'group_has_invalid_sort_key': _(
        'The "sort_key" property of a collection field group must be the name '
        'of a field on present on every collection field in the group'),

    'duplicate_fields': _('Fields cannot be specified more than once'),

    'group_missing_model': _(
        'Normal field groups need a model property of either "tree" or "plot"'
    ),

    'group_invalid_model': _(
        'Normal field groups can only have keys that match their "model"'
    ),

    'missing_field': _(
        'Normal field groups may only contain existing fields. If you specify '
        'a custom field, it cannot be a collection field'),
}


def reserved_name_validator(name):
    if name.lower() in [
            r.lower() for r in settings.RESERVED_INSTANCE_URL_NAMES]:
        raise ValidationError(_('%(instancename)s is a reserved name and '
                                'cannot be used') % {'instancename': name})


def create_udf(instance, model, udfc_name):
    from treemap.udf import UserDefinedFieldDefinition
    from treemap.util import safe_get_model_class

    clz = safe_get_model_class(model)
    udfc_settings = clz.udf_settings[udfc_name]
    udfc, __ = UserDefinedFieldDefinition.objects.get_or_create(
        instance_id=instance.pk,
        model_type=model,
        iscollection=udfc_settings.get('iscollection'),
        datatype=json.dumps(udfc_settings.get('defaults')),
        name=udfc_name)
    return udfc


def create_stewardship_udfs(instance):
    return [create_udf(instance, model, 'Stewardship')
            for model in ('Plot', 'Tree')]


def add_species_to_instance(instance):
    from treemap.models import Species

    region_codes = instance.itree_region_codes()
    if region_codes:
        # Add species from all of the instance's i-Tree regions
        species_codes = species_codes_for_regions(region_codes)
    else:
        # Add all species
        species_codes = all_species_codes()

    # Convert the list to a set for fast lookups
    species_code_set = set(species_codes)

    # Create and save a Species for each otm_code
    # Saving one by one is SLOW. It takes many seconds
    # to do the average species list of ~250 items.
    # Using bulk_create bypasses auditing but keeps
    # speed up.
    # TODO: bulk create audit records for species rows
    instance_species_list = []
    for species_dict in SPECIES:
        if species_dict['otm_code'] in species_code_set:
            species_dict['instance'] = instance
            instance_species_list.append(Species(**species_dict))
    Species.objects.bulk_create(instance_species_list)


class Instance(models.Model):
    """
    Each "Tree Map" is a single instance
    """
    name = models.CharField(max_length=255, unique=True)

    url_name = models.CharField(
        max_length=255, unique=True,
        validators=[
            reserved_name_validator,
            RegexValidator(
                r'^%s$' % URL_NAME_PATTERN,
                _('Must start with a letter and may only contain '
                  'letters, numbers, or dashes ("-")'),
                _('Invalid URL name'))
        ])

    """
    Basemap type     Basemap data
    ------------     -----------------
    Google           Google_API_Key
    Bing             Bing_API_Key
    TMS              TMS URL with {x},{y},{z}
    """
    basemap_type = models.CharField(max_length=255,
                                    choices=(("google", "Google"),
                                             ("bing", "Bing"),
                                             ("tms", "Tile Map Service")),
                                    default="google")
    basemap_data = models.CharField(max_length=255, null=True, blank=True)

    """
    The current database revision for the instance

    This revision is used to determine if tiles should be cached.
    In particular, the revision has *no* effect on the actual
    data.

    Generally we make tile requests like:
    http://tileserver/tile/{layer}/{rev}/{Z}/{Y}/{X}

    There is a database trigger that updates the
    revision whenever an edit to a geometry field is made
    so you don't have to worry about it.

    You should *not* edit this field.
    """
    geo_rev = models.IntegerField(default=1)

    eco_benefits_conversion = models.ForeignKey(
        'BenefitCurrencyConversion', null=True, blank=True)

    """ Center of the map when loading the instance """
    bounds = models.MultiPolygonField(srid=3857)

    """
    Override the center location (which is, by default,
    the centroid of "bounds"
    """
    center_override = models.PointField(srid=3857, null=True, blank=True)

    default_role = models.ForeignKey('Role', related_name='default_role')

    users = models.ManyToManyField('User', through='InstanceUser',
                                   null=True, blank=True)

    boundaries = models.ManyToManyField('Boundary', null=True, blank=True)

    """
    Config contains a bunch of config variables for a given instance
    these can be accessed via per-config properties such as
    `advanced_search_fields`. Note that it is a DotDict, and so supports
    get() with a dotted key and a default, e.g.
        instance.config.get('fruit.apple.type', 'delicious')
    as well as creating dotted keys when no keys in the path exist yet, e.g.
        instance.config = DotDict({})
        instance.config.fruit.apple.type = 'macoun'
    """
    config = JSONField(blank=True)

    is_public = models.BooleanField(default=False)

    logo = models.ImageField(upload_to='logos', null=True, blank=True)

    itree_region_default = models.CharField(
        max_length=20, null=True, blank=True, choices=ITREE_REGION_CHOICES)

    # Monotonically increasing number used to invalidate my InstanceAdjuncts
    adjuncts_timestamp = models.BigIntegerField(default=0)

    objects = models.GeoManager()

    def __unicode__(self):
        return self.name

    def _make_config_property(prop, default=None):
        def get_config(self):
            return self.config.get(prop, default)

        def set_config(self, value):
            self.config[prop] = value

        return property(get_config, set_config)

    date_format = _make_config_property('date_format',
                                        settings.DATE_FORMAT)

    short_date_format = _make_config_property('short_date_format',
                                              settings.SHORT_DATE_FORMAT)

    scss_variables = _make_config_property('scss_variables')

    map_feature_types = _make_config_property('map_feature_types', ['Plot'])

    mobile_search_fields = _make_config_property('mobile_search_fields',
                                                 DEFAULT_MOBILE_SEARCH_FIELDS)

    mobile_api_fields = _make_config_property('mobile_api_fields',
                                              DEFAULT_MOBILE_API_FIELDS)

    non_admins_can_export = models.BooleanField(default=True)

    @property
    def advanced_search_fields(self):
        # TODO pull from the config once users have a way to set search fields

        if not self.feature_enabled('advanced_search_filters'):
            return {'standard': [], 'missing': [], 'display': []}

        from treemap.models import MapFeature  # prevent circular import

        fields = {
            'standard': [
                {'identifier': 'tree.diameter', 'search_type': 'RANGE'},
                {'identifier': 'tree.date_planted', 'search_type': 'RANGE'},
                {'identifier': 'mapFeature.updated_at', 'search_type': 'RANGE'}
            ],
            'display': [
                {'model': 'Tree', 'label': 'Show trees'},
                {'model': 'EmptyPlot',
                 'label': 'Show empty planting sites'}
            ],
            'missing': [
                {'identifier': 'species.id',
                 'label': 'Show missing species',
                 'search_type': 'ISNULL',
                 'value': 'true'},
                {'identifier': 'tree.diameter',
                 'label': 'Show missing trunk diameter',
                 'search_type': 'ISNULL',
                 'value': 'true'},
                {'identifier': 'mapFeaturePhoto.id',
                 'label': 'Show missing photos',
                 'search_type': 'ISNULL',
                 'value': 'true'}
            ],
        }

        def make_display_filter(feature_name):
            Feature = MapFeature.get_subclass(feature_name)
            if hasattr(Feature, 'display_name_plural'):
                plural = Feature.display_name_plural
            else:
                plural = Feature.display_name + 's'
            return {
                'label': 'Show %s' % plural.lower(),
                'model': feature_name
            }

        fields['display'] += [make_display_filter(feature_name)
                              for feature_name in self.map_feature_types
                              if feature_name != 'Plot']

        # It makes styling easier if every field has an identifier
        num = 0
        for filters in fields.itervalues():
            for field in filters:
                field['id'] = "%s_%s" % (field.get('identifier', ''), num)
                num += 1

        return fields

    def get_udfc_search_fields(self, user):
        from treemap.models import InstanceUser
        from treemap.udf import UDFModel
        from treemap.util import to_object_name, leaf_models_of_class
        from treemap.lib.perms import udf_write_level, READ, WRITE

        try:
            iu = self.instanceuser_set.get(user__pk=user.pk)
        except InstanceUser.DoesNotExist:
            iu = None

        data = DotDict({'models': set(), 'udfc': {}})
        for clz in (leaf_models_of_class(UDFModel)):
            model_name = clz.__name__
            for k, v in clz.collection_udf_settings.items():
                udfds = (u for u in udf_defs(self, model_name) if u.name == k)
                for udfd in udfds:
                    if udf_write_level(iu, udfd) in (READ, WRITE):
                        nest_path = ('udfc.%s.models.%s' %
                                     (to_object_name(k),
                                      to_object_name(model_name)))
                        data[nest_path] = {
                            'udfd': udfd,
                            'fields': udfd.datatype_dict[0]['choices']
                        }
                        p = 'udfc.%s.' % to_object_name(k)
                        data[p + 'action_verb'] = v['action_verb']
                        data[p + 'range_field_key'] = v['range_field_key']
                        data[p + 'action_field_key'] = v['action_field_key']
                        data['models'] |= {clz}

        return data

    def editable_udf_models(self):
        from treemap.models import Tree, Plot
        from treemap.udf import UDFModel
        from treemap.util import leaf_models_of_class
        models = {clz for clz in leaf_models_of_class(UDFModel)
                  if clz.__name__ in self.map_feature_types
                  and getattr(clz, 'is_editable', False)}
        if Plot in models:
            models |= {Tree}
        return models

    @property
    def supports_resources(self):
        """
        Determine whether this instance has multiple map feature
        types (plots + "resources") or not.
        """
        n = len(self.map_feature_types)
        return n > 1

    @property
    def extent_as_json(self):
        boundary = self.bounds.boundary
        xmin, ymin, xmax, ymax = boundary.extent

        return json.dumps({'xmin': xmin, 'ymin': ymin,
                           'xmax': xmax, 'ymax': ymax})

    @property
    def bounds_as_geojson(self):
        boundary = self.bounds
        boundary.transform(4326)
        return boundary.json

    @property
    def center(self):
        return self.center_override or self.bounds.centroid

    @property
    def geo_rev_hash(self):
        return hashlib.md5(str(self.geo_rev)).hexdigest()

    @property
    def center_lat_lng(self):
        return self.center.transform(4326, clone=True)

    @property
    def factor_conversions(self):
        """
        Returns a dict for use in eco.py Benefits from eco_benefits_conversion
        """
        benefits_conversion = self.eco_benefits_conversion
        if benefits_conversion:
            return benefits_conversion.get_factor_conversions_config()
        else:
            return None

    @property
    def scss_query_string(self):
        scss_vars = ({k: val for k, val in self.scss_variables.items() if val}
                     if self.scss_variables else {})
        return urlencode(scss_vars)

    @property
    def static_page_names(self):
        from treemap.models import StaticPage  # prevent circular import

        built_in_names = StaticPage.built_in_names()

        custom_names = [page.name for page in
                        StaticPage.objects
                            .filter(instance=self)
                            .exclude(name__in=built_in_names)]

        names = built_in_names + custom_names

        return names

    @property
    def species_thumbprint(self):
        # Species autocomplete data lives in browser local storage.
        # It must be invalidated when a different instance is loaded,
        # or when the current instance's species are updated.
        #
        # To get a unique thumbprint across instances and species updates
        # we use the instance's latest species update time if available,
        # and otherwise its url name.
        from treemap.models import Species
        thumbprint = None
        my_species = Species.objects \
            .filter(instance_id=self.id) \
            .order_by('-updated_at')
        try:
            thumbprint = my_species[0].updated_at
        except IndexError:
            pass
        return "%s_%s" % (self.url_name, thumbprint)

    @property
    def boundary_thumbprint(self):
        # Boundary autocomplete data lives in browser local storage.
        # It must be invalidated when a different instance is loaded,
        # or when the current instance's species are updated.
        #
        # To get a unique thumbprint across instances and boundary updates
        # we use the latest boundary update time if available,
        # and otherwise the instance's url name.
        from treemap.models import Boundary
        thumbprint = None
        my_boundaries = Boundary.objects.order_by('-updated_at')
        try:
            thumbprint = my_boundaries[0].updated_at
        except IndexError:
            pass
        return "%s_%s" % (self.url_name, thumbprint)

    def update_geo_rev(self):
        qs = Instance.objects.filter(pk=self.id)

        # Use SQL increment in case self.geo_rev is stale
        qs.update(geo_rev=F('geo_rev') + 1)

        # Fetch updated value so callers will have it
        self.geo_rev = qs[0].geo_rev

    def itree_region_codes(self):
        from treemap.models import ITreeRegion

        if self.itree_region_default:
            region_codes = [self.itree_region_default]
        else:
            region_codes = ITreeRegion.objects \
                .filter(geometry__intersects=self.bounds) \
                .values_list('code', flat=True)

        return region_codes

    def itree_regions(self):
        from treemap.models import ITreeRegion  # prevent circular import
        if self.itree_region_default:
            codes = [self.itree_region_default]
        else:
            codes = (ITreeRegion
                     .objects
                     .filter(geometry__intersects=self.bounds)
                     .values_list('code', flat=True))

        return [(code, ITREE_REGIONS.get(code, {}).get('name'))
                for code in codes]

    def has_itree_region(self):
        return bool(self.itree_regions())

    def is_accessible_by(self, user):
        try:
            if self.is_public:
                return True

            # Extension point
            if hasattr(user, 'is_super_admin') and user.is_super_admin():
                return True

            # If a user is not logged in, trying to check
            # user=user raises a type error so I am checking
            # pk instead
            self.instanceuser_set.get(user__pk=user.pk)
            return True
        except ObjectDoesNotExist:
            return False

    def scope_model(self, model):
        qs = model.objects.filter(instance=self)
        return qs

    def feature_enabled(self, feature):
        # Delayed import to prevent circular imports
        from treemap.plugin import feature_enabled
        return feature_enabled(self, feature)

    def seed_with_dummy_default_role(self):
        """
        Instances need roles and roles needs instances... crazy stuff
        we're going to create the needed role below however, we'll temporarily
        use a 'dummy role'. The dummy role has no instance.
        """
        from treemap.audit import Role
        dummy_roles = Role.objects.filter(instance__isnull=True)
        if len(dummy_roles) == 0:
            dummy_role = Role.objects.create(name='empty', rep_thresh=0)
        else:
            dummy_role = dummy_roles[0]

        self.default_role = dummy_role

    def clean(self):
        # We need to work around a bit of a chicken/egg problem here
        # The default API fields reference Stewardship, but the Stewardship
        # UDFs won't exist when the instance is first created.
        # To work around this, we only validate when there is something in the
        # 'config' object, which ignores the default api fields
        if 'mobile_api_fields' in self.config:
            self._validate_mobile_api_fields()

    def _validate_mobile_api_fields(self):
        # Validate that:
        # 1) overall structure is correct
        # 2) each individual group has a header and collection or normal fields
        # 3) Collection UDF groups only contain collection UDFs
        # 4) Collection UDF groups have a 'sort_key', which is present on all
        #    fields for that group
        # 5) no field is referenced more than once
        # 6) all fields referenced exist

        # delayed import to avoid circular references
        from treemap.models import Plot, Tree

        def _truthy_of_type(item, types):
            return item and isinstance(item, types)

        field_groups = self.mobile_api_fields
        errors = set()

        scalar_udfs = {udef.full_name: udef for udef in udf_defs(self)
                       if not udef.iscollection}
        collection_udfs = {udef.full_name: udef for udef in udf_defs(self)
                           if udef.iscollection}

        if not _truthy_of_type(field_groups, (list, tuple)):
            raise ValidationError(
                {'mobile_api_fields': [API_FIELD_ERRORS['no_field_groups']]})

        for group in field_groups:
            if not _truthy_of_type(group.get('header'), basestring):
                errors.add(API_FIELD_ERRORS['group_has_no_header'])

            if ((not isinstance(group.get('collection_udf_keys'), list)
                 and not isinstance(group.get('field_keys'), list))):
                errors.add(API_FIELD_ERRORS['group_has_no_keys'])

            elif 'collection_udf_keys' in group and 'field_keys' in group:
                errors.add(API_FIELD_ERRORS['group_has_both_keys'])

            if isinstance(group.get('collection_udf_keys'), list):
                sort_key = group.get('sort_key')
                if not sort_key:
                    errors.add(API_FIELD_ERRORS['group_has_no_sort_key'])

                for key in group['collection_udf_keys']:
                    udef = collection_udfs.get(key)
                    if udef is None:
                        errors.add(API_FIELD_ERRORS['group_has_missing_cudf'])
                    elif sort_key not in udef.datatype_by_field:
                        errors.add(
                            API_FIELD_ERRORS['group_has_invalid_sort_key'])
            elif isinstance(group.get('field_keys'), list):
                if group.get('model') not in {'tree', 'plot'}:
                    errors.add(API_FIELD_ERRORS['group_missing_model'])
                else:
                    for key in group['field_keys']:
                        if not key.startswith(group['model']):
                            errors.add(API_FIELD_ERRORS['group_invalid_model'])

        if errors:
            raise ValidationError({'mobile_api_fields': list(errors)})

        scalar_fields = [key for group in field_groups
                         for key in group.get('field_keys', [])]
        collection_fields = [key for group in field_groups
                             for key in group.get('collection_udf_keys', [])]

        all_fields = scalar_fields + collection_fields

        if len(all_fields) != len(set(all_fields)):
            errors.add(API_FIELD_ERRORS['duplicate_fields'])

        for field in scalar_fields:
            model_name, name = field.split('.', 1)  # maxsplit of 1
            Model = Plot if model_name == 'plot' else Tree
            standard_fields = Model._meta.get_all_field_names()

            if ((name not in standard_fields and field not in scalar_udfs)):
                errors.add(API_FIELD_ERRORS['missing_field'])

        if errors:
            raise ValidationError({'mobile_api_fields': list(errors)})

    def save(self, *args, **kwargs):
        self.full_clean()

        self.url_name = self.url_name.lower()

        super(Instance, self).save(*args, **kwargs)
