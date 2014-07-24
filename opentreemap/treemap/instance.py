# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.gis.db import models
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import RegexValidator
from django.conf import settings
from django.utils.translation import ugettext as trans

import hashlib
import json
from urllib import urlencode

from copy import deepcopy

from treemap.json_field import JSONField
from treemap.lib.object_caches import udf_defs
from treemap.species import ITREE_REGION_CHOICES

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
                {'identifier': 'treePhoto.id',
                 'label': 'Missing Photo'}]
}

DEFAULT_MOBILE_API_FIELDS = [
    {'header': trans('Tree Information'),
     'field_keys': ['tree.species', 'tree.diameter',
                    'tree.height', 'tree.date_planted']},
    {'header': trans('Planting Site Information'),
     'field_keys': ['plot.width', 'plot.length']},
    {'header': trans('Stewardship'),
     'collection_udf_keys': ['plot.udf:Stewardship', 'tree.udf:Stewardship'],
     'sort_key': 'Date'}
]

DEFAULT_TREE_STEWARDSHIP_CHOICES = [
    'Watered',
    'Pruned',
    'Mulched, Had Compost Added, or Soil Amended',
    'Cleared of Trash or Debris']

DEFAULT_PLOT_STEWARDSHIP_CHOICES = [
    'Enlarged',
    'Changed to Include a Guard',
    'Changed to Remove a Guard',
    'Filled with Herbaceous Plantings']

# Used for collection UDF search on the web
# if we come to support more udfcs, we can add them here.
UDFC_MODELS = ['Tree', 'Plot']
UDFC_NAMES = ['Stewardship', 'Alerts']


def reserved_name_validator(name):
    if name.lower() in [
            r.lower() for r in settings.RESERVED_INSTANCE_URL_NAMES]:
        raise ValidationError(trans('%(instancename)s is a reserved name and '
                                    'cannot be used') % {'instancename': name})


def create_stewardship_udfs(instance):
    from treemap.udf import UserDefinedFieldDefinition  # Circular import

    def create_udf(model, choices):
        return UserDefinedFieldDefinition.objects.create(
            instance_id=instance.pk,
            model_type=model,
            datatype=json.dumps([
                {'type': 'choice',
                 'choices': choices,
                 'name': 'Action'},
                {'type': 'date',
                 'name': 'Date'}]),
            iscollection=True,
            name='Stewardship')

    opts = (('Plot', DEFAULT_PLOT_STEWARDSHIP_CHOICES),
            ('Tree', DEFAULT_TREE_STEWARDSHIP_CHOICES))

    return [create_udf(model, choices) for model, choices in opts]


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
                trans('Must start with a letter and may only contain '
                      'letters, numbers, or dashes ("-")'),
                trans('Invalid URL name'))
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

    @property
    def advanced_search_fields(self):
        # TODO pull from the config once users have a way to set search fields

        if not self.feature_enabled('advanced_search_filters'):
            return {'standard': [], 'missing': [], 'display': [],
                    'udfc': self._get_udfc_search_fields()}

        from treemap.models import MapFeature  # prevent circular import

        fields = {
            'standard': [
                {'identifier': 'tree.diameter', 'search_type': 'RANGE'},
                {'identifier': 'tree.date_planted', 'search_type': 'RANGE'}
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

        fields['udfc'] = self._get_udfc_search_fields()

        return fields

    def _get_udfc_search_fields(self):
        from treemap.util import to_object_name

        empty_udfc = {to_object_name(n_k):
                      {to_object_name(m_k): {'fields': [], 'udfd': None}
                       for m_k in UDFC_MODELS}
                      for n_k in UDFC_NAMES}

        udfds = []
        for model_name in UDFC_MODELS:
            for udfd in udf_defs(self, model_name):
                if udfd.name in UDFC_NAMES:
                    udfds.append(udfd)

        udfc = deepcopy(empty_udfc)

        for udfd in udfds:
            udfd_info = {
                'udfd': udfd,
                'fields': udfd.datatype_dict[0]['choices']
            }
            name_dict = udfc[to_object_name(udfd.name)]
            name_dict[to_object_name(udfd.model_type)] = udfd_info

        return udfc

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

    def itree_region_codes(self):
        from treemap.models import ITreeRegion

        if self.itree_region_default:
            region_codes = [self.itree_region_default]
        else:
            region_codes = ITreeRegion.objects \
                .filter(geometry__intersects=self.bounds) \
                .values_list('code', flat=True)

        return region_codes

    def has_itree_region(self):
        from treemap.models import ITreeRegion  # prevent circular import
        intersecting_regions = (ITreeRegion
                                .objects
                                .filter(geometry__intersects=self.bounds))

        return bool(self.itree_region_default) or intersecting_regions.exists()

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

    def save(self, *args, **kwargs):
        self.full_clean()

        self.url_name = self.url_name.lower()

        super(Instance, self).save(*args, **kwargs)
