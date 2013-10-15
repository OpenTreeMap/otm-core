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
from treemap.features import feature_enabled

from json_field import JSONField

URL_NAME_PATTERN = r'[a-z]+[a-z0-9\-]*'


def reserved_name_validator(name):
    if name in settings.RESERVED_INSTANCE_URL_NAMES:
        raise ValidationError(trans('%(instancename)s is a reserved name and '
                                    'cannot be used') % {'instancename': name})


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
                trans('Must start with a lowercase letter '
                      'and may only contain lowercase '
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

    itree_region_default = models.CharField(max_length=20, null=True,
                                            blank=True)

    objects = models.GeoManager()

    def __unicode__(self):
        return self.name

    def _make_config_property(prop, default=None):
        def get_config(self):
            return self.config.get(prop, default)

        def set_config(self, value):
            self.config[prop] = value

        return property(get_config, set_config)

    advanced_search_fields = _make_config_property('advanced_search_fields',
                                                   {'standard': [],
                                                    'missing': []})

    date_format = _make_config_property('date_format',
                                        settings.DATE_FORMAT)

    short_date_format = _make_config_property('short_date_format',
                                              settings.SHORT_DATE_FORMAT)

    scss_variables = _make_config_property('scss_variables')

    @property
    def extent_as_json(self):
        boundary = self.bounds.boundary
        xmin, ymin, xmax, ymax = boundary.extent

        return json.dumps({'xmin': xmin, 'ymin': ymin,
                           'xmax': xmax, 'ymax': ymax})

    @property
    def center(self):
        return self.bounds.centroid

    @property
    def geo_rev_hash(self):
        return hashlib.md5(str(self.geo_rev)).hexdigest()

    @property
    def center_lat_lng(self):
        return self.center.transform(4326, clone=True)

    @property
    def scss_query_string(self):
        scss_vars = ({k: val for k, val in self.scss_variables.items() if val}
                     if self.scss_variables else {})
        return urlencode(scss_vars)

    def is_accessible_by(self, user):
        try:
            if self.is_public:
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
        return feature_enabled(self, feature)

    def save(self, *args, **kwargs):
        self.full_clean()
        super(Instance, self).save(*args, **kwargs)
