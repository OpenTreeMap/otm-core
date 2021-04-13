# -*- coding: utf-8 -*-


from copy import deepcopy

from django.contrib.gis.db import models
from django.contrib.gis.db.models import Extent
from django.contrib.gis.gdal import SpatialReference
from django.contrib.gis.geos import MultiPolygon, Polygon, GEOSGeometry
from django.contrib.gis.geos.error import GEOSException
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import RegexValidator
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils.translation import ugettext_lazy as _

# these are all built-in directly to Django
from django.db.models import Manager as GeoManager

import hashlib
import json
from urllib.parse import urlencode

from opentreemap.util import extent_intersection, extent_as_json

from treemap.search_fields import (
    DEFAULT_MOBILE_SEARCH_FIELDS, DEFAULT_MOBILE_API_FIELDS,
    DEFAULT_WEB_DETAIL_FIELDS, DEFAULT_SEARCH_FIELDS, INSTANCE_FIELD_ERRORS,
    advanced_search_fields, get_udfc_search_fields)

from treemap.species import SPECIES
from treemap.json_field import JSONField
from treemap.lib.object_caches import udf_defs
from treemap.species.codes import (species_codes_for_regions,
                                   all_species_codes, ITREE_REGION_CHOICES)
from treemap.DotDict import DotDict

URL_NAME_PATTERN = r'[a-zA-Z]+[a-zA-Z0-9\-]*'

_DEFAULT_REV = 1


def reserved_name_validator(name):
    if name.lower() in [
            r.lower() for r in settings.RESERVED_INSTANCE_URL_NAMES]:
        raise ValidationError(_('%(instancename)s is a reserved name and '
                                'cannot be used') % {'instancename': name})


def get_or_create_udf(instance, model, udfc_name):
    from treemap.udf import UserDefinedFieldDefinition
    from treemap.util import safe_get_model_class

    clz = safe_get_model_class(model)
    udfc_settings = clz.udf_settings[udfc_name]
    kwargs = {
        'instance_id': instance.pk,
        'model_type': model,
        'iscollection': udfc_settings.get('iscollection'),
        'name': udfc_name,
    }
    try:
        udfc = UserDefinedFieldDefinition.objects.get(**kwargs)
    except UserDefinedFieldDefinition.DoesNotExist:
        kwargs['datatype'] = json.dumps(udfc_settings.get('defaults'))
        udfc = UserDefinedFieldDefinition.objects.create(**kwargs)
    return udfc


def create_stewardship_udfs(instance):
    return [get_or_create_udf(instance, model, 'Stewardship')
            for model in ('Plot', 'Tree')]


def add_species_to_instance(instance):
    from treemap.models import Species

    region_codes = [itr.code for itr in instance.itree_regions()]
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
            species_dict = deepcopy(species_dict)
            species_dict['instance'] = instance
            instance_species_list.append(Species(**species_dict))
    Species.objects.bulk_create(instance_species_list)


PERMISSION_VIEW_EXTERNAL_LINK = 'view_external_link'
PERMISSION_MODELING = 'modeling'


# Don't call this function directly, call plugin.get_instance_permission_spec()
def get_instance_permission_spec(instance=None):
    from treemap.audit import Role
    return [
        {
            'codename': PERMISSION_VIEW_EXTERNAL_LINK,
            'description': _('Can view "External Link" '
                             'of a tree or map feature'),
            'default_role_names': [Role.ADMINISTRATOR, Role.EDITOR],
            'label': _('Can View External Link')
        },
        {
            'codename': PERMISSION_MODELING,
            'description': _('Can access modeling page'),
            'default_role_names': [Role.ADMINISTRATOR],
            'label': _('Can Access Modeling')
        }
    ]


class InstanceBounds(models.Model):
    """ Center of the map when loading the instance """
    geom = models.MultiPolygonField(srid=3857)
    objects = GeoManager()

    @classmethod
    def create_from_point(cls, x, y, half_edge=50000):
        """Create as square using Web Mercator point and default edge 100km"""
        return cls.create_from_box(
            x - half_edge, y - half_edge,
            x + half_edge, y + half_edge
        )

    @classmethod
    def create_from_box(cls, x_min, y_min, x_max, y_max):
        """Create from box (Web Mercator coordinates)"""
        bounds = Polygon(((x_min, y_min),
                          (x_min, y_max),
                          (x_max, y_max),
                          (x_max, y_min),
                          (x_min, y_min)))
        bounds = MultiPolygon((bounds, ))
        return InstanceBounds.objects.create(geom=bounds)

    @classmethod
    def create_from_geojson(cls, geojson):
        """Create from GeoJSON (lon/lat coordinates)"""
        try:
            geojson_dict = json.loads(geojson)
        except ValueError as e:
            raise ValidationError(str(e))
        if geojson_dict['type'] != 'FeatureCollection':
            raise ValidationError('GeoJSON must contain a FeatureCollection')

        geoms = []
        web_mercator = SpatialReference(3857)

        def add_polygon(geom_dict):
            try:
                geom = GEOSGeometry(json.dumps(geom_dict), 4326)
            except GEOSException:
                raise ValidationError('GeoJSON is not valid')
            geom.transform(web_mercator)
            geoms.append(geom)

        for feature in geojson_dict['features']:
            geom_dict = feature['geometry']
            if geom_dict['type'] == 'Polygon':
                add_polygon(geom_dict)
            elif geom_dict['type'] == 'MultiPolygon':
                for polygon in geom_dict['coordinates']:
                    add_polygon({
                        'type': 'Polygon',
                        'coordinates': polygon
                    })
            else:
                raise ValidationError(
                    'GeoJSON features must be Polygons or MultiPolygons')

        bounds = MultiPolygon(geoms)
        if not bounds.valid:
            raise ValidationError(
                'GeoJSON is not valid: %s' % bounds.valid_reason)

        return InstanceBounds.objects.create(geom=bounds)

    def __str__(self):
        return "instance_id: %s" % self.instance.id


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
                                             ("esri", "ESRI"),
                                             ("tms", "Tile Map Service")),
                                    default="google")
    basemap_data = models.CharField(max_length=255, null=True, blank=True)

    """
    Revision fields are monotonically increasing counters, each
    incremented under differing conditions, all used to invalidate one
    of multiple caching layers, so that repeated requests for the same
    data may benefit from caching. Their respective values are part of
    all tile URLs and ecobenefit summaries.

    The "universal revision" is incremented whenever instance values that
    affect aggregates are changed *in any way*. When using a search filter,
    any field of MapFeature and Tree is a trigger for cache invalidation.
    Its value is part of all search tile URLs and search ecobenefit summary
    cache keys.

    The "geometry revision" is incremented whenever a map feature is
    modified in a way that would affect rendered tiles for non-search
    map rendering. Its value is part of all non-search tile URLs.

    The "ecobenefit revision" is incremented whenever a tree is
    modified in a way that would affect ecobenefit calculations.
    Its value is part of cache keys for non-search ecobenefit summaries.
    """
    geo_rev = models.IntegerField(default=_DEFAULT_REV)
    universal_rev = models.IntegerField(default=_DEFAULT_REV,
                                        null=True, blank=True)
    eco_rev = models.IntegerField(default=_DEFAULT_REV)

    eco_benefits_conversion = models.ForeignKey(
        'BenefitCurrencyConversion',
        on_delete=models.CASCADE,
        null=True, blank=True)

    """ Center of the map when loading the instance """
    bounds = models.OneToOneField(InstanceBounds,
                                  on_delete=models.CASCADE,
                                  null=True, blank=True)

    """
    Override the center location (which is, by default,
    the centroid of "bounds"
    """
    center_override = models.PointField(srid=3857, null=True, blank=True)

    default_role = models.ForeignKey('Role', on_delete=models.CASCADE, related_name='default_role')

    users = models.ManyToManyField('User', through='InstanceUser')

    boundaries = models.ManyToManyField('Boundary')

    """
    Config contains a bunch of configuration variables for a given instance,
    which can be accessed via properties such as `annual_rainfall_inches`.
    Note that it is a DotDict, and so supports get() with a dotted key and a
    default, e.g.
        instance.config.get('fruit.apple.type', 'delicious')
    as well as creating dotted keys when no keys in the path exist yet, e.g.
        instance.config = DotDict({})
        instance.config.fruit.apple.type = 'macoun'
    """
    config = JSONField(blank=True, default=DotDict)

    is_public = models.BooleanField(default=False)

    logo = models.ImageField(upload_to='logos', null=True, blank=True)

    itree_region_default = models.CharField(
        max_length=20, null=True, blank=True, choices=ITREE_REGION_CHOICES)

    # Monotonically increasing number used to invalidate my InstanceAdjuncts
    adjuncts_timestamp = models.BigIntegerField(default=0)

    """
    Flag indicating whether canopy data is available and should be displayed.
    """
    canopy_enabled = models.BooleanField(default=False)

    """
    The boundary category to be used for showing a choropleth canopy
    layer. max_length=255 matches Boundary.category
    """
    canopy_boundary_category = models.CharField(max_length=255, default='',
                                                blank=True)

    objects = GeoManager()

    def __str__(self):
        return self.name

    def _make_config_property(prop, default=None):
        def get_config(self):
            return self.config.get(prop, deepcopy(default))

        def set_config(self, value):
            self.config[prop] = value

        return property(get_config, set_config)

    date_format = _make_config_property('date_format',
                                        settings.DATE_FORMAT)

    short_date_format = _make_config_property('short_date_format',
                                              settings.SHORT_DATE_FORMAT)

    scss_variables = _make_config_property('scss_variables')

    _map_feature_types = _make_config_property('map_feature_types', ['Plot'])

    # Never access this property directly.
    # Use the map feature class methods, get_config and set_config_property
    map_feature_config = _make_config_property('map_feature_config', {})

    annual_rainfall_inches = _make_config_property('annual_rainfall_inches',
                                                   None)

    mobile_search_fields = _make_config_property('mobile_search_fields',
                                                 DEFAULT_MOBILE_SEARCH_FIELDS)

    mobile_api_fields = _make_config_property('mobile_api_fields',
                                              DEFAULT_MOBILE_API_FIELDS)

    web_detail_fields = _make_config_property('web_detail_fields',
                                              DEFAULT_WEB_DETAIL_FIELDS)

    search_config = _make_config_property('search_config',
                                          DEFAULT_SEARCH_FIELDS)

    custom_layers = _make_config_property('custom_layers', [])

    non_admins_can_export = models.BooleanField(default=True)

    @property
    def map_feature_types(self):
        """
        To update, use add_map_feature_types and remove_map_feature_types.
        """
        return self._map_feature_types

    def advanced_search_fields(self, user):
        return advanced_search_fields(self, user)

    def get_udfc_search_fields(self, user):
        return get_udfc_search_fields(self, user)

    def editable_udf_models(self):
        from treemap.plugin import feature_enabled
        from treemap.models import Tree, Plot
        from treemap.udf import UDFModel
        from treemap.util import leaf_models_of_class
        gsi_enabled = feature_enabled(self, 'green_infrastructure')

        core_models = {Tree, Plot}
        gsi_models = {clz for clz in leaf_models_of_class(UDFModel)
                      if gsi_enabled
                      and clz.__name__ in self.map_feature_types
                      and getattr(clz, 'is_editable', False)
                      and clz not in core_models}
        all_models = core_models | gsi_models

        return {'core': core_models, 'gsi': gsi_models, 'all': all_models}

    @property
    def collection_udfs(self):
        from treemap.udf import UserDefinedFieldDefinition
        return UserDefinedFieldDefinition.objects.filter(
            instance=self, iscollection=True)

    @property
    def has_resources(self):
        """
        Determine whether this instance has multiple map feature
        types (plots + "resources") or not.
        """
        n = len(self.map_feature_types)
        return n > 1

    @property
    def map_extent_as_json(self):
        feature_extent = self.mapfeature_set \
            .aggregate(Extent('geom'))['geom__extent']
        bounds_extent = self.bounds_extent

        if feature_extent is not None:
            intersection = extent_intersection(feature_extent, bounds_extent)
            return extent_as_json(intersection)

        return extent_as_json(bounds_extent)

    @property
    def bounds_extent(self):
        boundary = self.bounds.geom.boundary
        return boundary.extent

    @property
    def bounds_extent_as_json(self):
        return extent_as_json(self.bounds_extent)

    @property
    def bounds_as_geojson(self):
        boundary = self.bounds.geom
        boundary.transform(4326)
        return boundary.json

    @property
    def center(self):
        return self.center_override or self.bounds.geom.centroid

    @property
    def geo_rev_hash(self):
        return hashlib.md5(str(self.geo_rev).encode()).hexdigest()

    @property
    def universal_rev_hash(self):
        return hashlib.md5(str(self.universal_rev).encode()).hexdigest()

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
        scss_vars = ({k: val for k, val
                      in list(self.scss_variables.items()) if val}
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
        # we use the instance's url_name, latest species update time, and
        # species count (to handle deletions).
        #
        # Note: On 8/28/17, added a version to invalidate cache after changing
        # data included in scientific name
        from treemap.models import Species
        my_species = Species.objects \
            .filter(instance_id=self.id) \
            .order_by('-updated_at')
        version = 1
        if my_species.exists():
            return "%s_%s_%s_%s" % (
                self.url_name, my_species.count(), my_species[0].updated_at,
                version
            )
        else:
            return self.url_name

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

    @transaction.atomic
    def remove_map_feature_types(self, remove=None, keep=None):
        """
        remove_map_feature_types(self, remove=None, keep=None)

        Either remove the map feature types in the remove argument,
        or remove all but the types in the keep argument.
        The types to remove or keep is a list of map feature class names.

        Then remove map feature config for all removed map features,
        and save the instance!!!
        """
        from treemap.util import to_object_name
        if keep and remove:
            raise Exception('Invalid use of remove_map_features API: '
                            'pass arguments "keep" or "remove" but not both')
        elif keep:
            remaining_types = [name for name in self.map_feature_types
                               if name in keep]
        else:
            remaining_types = [class_name for class_name
                               in self.map_feature_types
                               if class_name not in remove]

        for class_name in self.map_feature_types:
            if class_name not in remaining_types:
                if class_name in self.search_config:
                    del self.search_config[class_name]
                if 'missing' in self.search_config:
                    self.search_config['missing'] = [
                        o for o in self.search_config['missing']
                        if not o.get('identifier', '').startswith(
                            to_object_name(class_name))]
                # TODO: delete from mobile_api_fields
                # non-plot mobile_api_fields are not currently
                # supported, but when they are added, they should
                # also be removed here.
        self._map_feature_types = remaining_types
        self.save()

    @transaction.atomic
    def add_map_feature_types(self, types):
        """
        add_map_feature_types(self, types)

        types is a list of map feature class names.

        Add these types to the instance config,
        save the instance!!!,
        and create udf rows for udfs that have settings defaults,
        if they don't already exist.
        """
        from treemap.models import MapFeature  # prevent circular import
        from treemap.audit import add_default_permissions

        classes = [MapFeature.get_subclass(type) for type in types]

        dups = set(types) & set(self.map_feature_types)
        if len(dups) > 0:
            raise ValidationError('Map feature types already added: %s' % dups)

        self._map_feature_types = list(self.map_feature_types) + list(types)
        self.save()

        for type, clz in zip(types, classes):
            settings = (getattr(clz, 'udf_settings', {}))
            for udfc_name, udfc_settings in list(settings.items()):
                if udfc_settings.get('defaults'):
                    get_or_create_udf(self, type, udfc_name)

        add_default_permissions(self, models=classes)

    @property
    def map_feature_classes(self):
        from treemap.models import MapFeature
        classes = {MapFeature.get_subclass(m)
                   for m in self.map_feature_types}
        return classes

    @property
    def resource_classes(self):
        from treemap.models import Plot
        return self.map_feature_classes - {Plot}

    def update_geo_rev(self):
        self.update_revs('geo_rev')

    def update_eco_rev(self):
        self.update_revs('eco_rev')

    def update_universal_rev(self):
        self.update_revs('universal_rev')

    def update_revs(self, *attrs):
        # Use SQL increment in case a value in attrs is stale
        qs = Instance.objects.filter(pk=self.id)
        qs.update(**{attr: F(attr) + 1 for attr in attrs})

        # Fetch updated value so callers will have it
        for attr in attrs:
            setattr(self, attr, getattr(qs[0], attr))

    def itree_regions(self, **extra_query):
        from treemap.models import ITreeRegion, ITreeRegionInMemory

        query = {'geometry__intersects': self.bounds.geom}
        query.update(extra_query)

        if self.itree_region_default:
            return [ITreeRegionInMemory(self.itree_region_default)]
        else:
            return ITreeRegion.objects.filter(**query)

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

    def plot_count(self):
        from treemap.ecocache import get_cached_plot_count
        from treemap.search import Filter
        all_plots_filter = Filter('', '', self)
        return get_cached_plot_count(all_plots_filter)

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
            self._validate_field_groups(self.mobile_api_fields,
                                        'mobile_api_fields')
        if 'web_detail_fields' in self.config:
            self._validate_field_groups(self.web_detail_fields,
                                        'web_detail_fields')

    def _validate_field_groups(self, field_groups, prop):
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

        def raise_errors(errors):
            message = {}
            message[prop] = list(errors)
            raise ValidationError(message)

        errors = set()

        scalar_udfs = {udef.full_name: udef for udef in udf_defs(self)
                       if not udef.iscollection}
        collection_udfs = {udef.full_name: udef for udef in udf_defs(self)
                           if udef.iscollection}

        if not _truthy_of_type(field_groups, (list, tuple)):
            raise_errors([INSTANCE_FIELD_ERRORS['no_field_groups']])

        for group in field_groups:
            if not _truthy_of_type(group.get('header'), str):
                errors.add(INSTANCE_FIELD_ERRORS['group_has_no_header'])

            if ((not isinstance(group.get('collection_udf_keys'), list)
                 and not isinstance(group.get('field_keys'), list))):
                errors.add(INSTANCE_FIELD_ERRORS['group_has_no_keys'])

            elif ((prop == 'mobile_api_fields' and
                   'collection_udf_keys' in group and 'field_keys' in group)):
                errors.add(INSTANCE_FIELD_ERRORS['group_has_both_keys'])

            if isinstance(group.get('collection_udf_keys'), list):
                sort_key = group.get('sort_key')
                if prop == 'mobile_api_fields' and not sort_key:
                    errors.add(INSTANCE_FIELD_ERRORS['group_has_no_sort_key'])

                for key in group['collection_udf_keys']:
                    udef = collection_udfs.get(key)
                    if udef is None:
                        errors.add(
                            INSTANCE_FIELD_ERRORS['group_has_missing_cudf'])
                    elif ((prop == 'mobile_api_fields' and
                           sort_key not in udef.datatype_by_field)):
                        errors.add(INSTANCE_FIELD_ERRORS['group_has_invalid_sort_key'])  # NOQA
            if isinstance(group.get('field_keys'), list):
                if group.get('model') not in {'tree', 'plot'}:
                    errors.add(INSTANCE_FIELD_ERRORS['group_missing_model'])
                else:
                    for key in group['field_keys']:
                        if not key.startswith(group['model']):
                            errors.add(
                                INSTANCE_FIELD_ERRORS['group_invalid_model'])

        if errors:
            raise_errors(errors)

        scalar_fields = [key for group in field_groups
                         for key in group.get('field_keys', [])]
        collection_fields = [key for group in field_groups
                             for key in group.get('collection_udf_keys', [])]

        all_fields = scalar_fields + collection_fields

        if len(all_fields) != len(set(all_fields)):
            errors.add(INSTANCE_FIELD_ERRORS['duplicate_fields'])

        for field in scalar_fields:
            model_name, name = field.split('.', 1)  # maxsplit of 1
            Model = Plot if model_name == 'plot' else Tree
            standard_fields = [
                f.name for f in Model._meta.get_fields()
                if not (f.many_to_one and f.related_model is None)
            ]

            if ((name not in standard_fields and field not in scalar_udfs)):
                errors.add(INSTANCE_FIELD_ERRORS['missing_field'])

        if errors:
            raise_errors(errors)

    def save(self, *args, **kwargs):
        self.full_clean()

        self.url_name = self.url_name.lower()

        super(Instance, self).save(*args, **kwargs)
