# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
import copy
from functools import wraps

from django.db.models import Q

from django.conf import settings
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D

from treemap.exceptions import HttpBadRequestException
from treemap.lib.object_caches import role_permissions
from treemap.models import Instance, InstanceUser
from treemap.units import (get_units_if_convertible, get_digits_if_formattable,
                           get_conversion_factor)
from treemap.util import safe_get_model_class
from treemap.templatetags.form_extras import field_type_label_choices
from treemap.json_field import is_json_field_reference
from treemap.plugin import get_mobile_instances_filter
from treemap.ecobenefits import BenefitCategory

import treemap.lib.perms as perms_lib


def transform_instance_info_response(instance_view_fn):
    """
    Collection UDFs were added to the API in version 3

    They need to be removed in older versions of the API, to support clients
    which can not render collection UDFs
    """
    @wraps(instance_view_fn)
    def wrapper(request, *args, **kwargs):
        instance_info_dict = instance_view_fn(request, *args, **kwargs)

        if request.api_version < 3:
            instance_info_dict['field_key_groups'] =\
                [field_group for field_group
                 in instance_info_dict['field_key_groups']
                 if 'collection_udf_keys' not in field_group]

        return instance_info_dict

    return wrapper


def instances_closest_to_point(request, lat, lng):
    """
    Get all the info we need about instances near a given point
    Includes only public instances the user does not belong to.
    If a user has been specified instances that user belongs to will
    also be included in a separate list.

    Unlike instance_info, this does not return the field permissions for the
    instance
    """
    user = request.user
    user_instance_ids = []
    if user and not user.is_anonymous():
        user_instance_ids = InstanceUser.objects.filter(user=user)\
                                        .values_list('instance_id', flat=True)\
                                        .distinct()

    point = Point(float(lng), float(lat), srid=4326)

    try:
        max_instances = int(request.GET.get('max', '10'))

        if not (1 <= max_instances <= 500):
            raise ValueError()
    except ValueError:
        raise HttpBadRequestException(
            'The max parameter must be a number between 1 and 500')

    try:
        distance = float(request.GET.get(
            'distance', settings.NEARBY_INSTANCE_RADIUS))
    except ValueError:
        raise HttpBadRequestException(
            'The distance parameter must be a number')

    instances = Instance.objects \
                        .filter(get_mobile_instances_filter()) \
                        .distance(point) \
                        .order_by('distance')

    nearby_predicate = Q(bounds__distance_lte=(point, D(m=distance)))
    personal_predicate = Q(pk__in=user_instance_ids)

    return {
        'nearby': _contextify_instances(instances
                                        .filter(is_public=True)
                                        .filter(nearby_predicate)
                                        .exclude(personal_predicate)
                                        [0:max_instances]),
        'personal': _contextify_instances(instances.filter(personal_predicate))
    }


def instance_info(request, instance):
    """
    Get all the info we need about a given instance

    It also includes info about the fields available for the
    instance. If a user has been specified the field info
    will be tailored to that user
    """
    user = request.user

    role = instance.default_role
    if user and not user.is_anonymous():
        instance_user = user.get_instance_user(instance)
        if instance_user:
            role = instance_user.role

    collection_udfs = instance.userdefinedfielddefinition_set\
                              .filter(iscollection=True)
    collection_udf_dict = {"%s.%s" % (udf.model_type.lower(),
                                      udf.canonical_name): udf
                           for udf in collection_udfs}

    # collect perms for the given role/instance into a serializable
    # dictionary. If a field isn't at least readable, it doesn't
    # get sent over at all.
    perms = {}
    for fp in role_permissions(role, instance):
        model = fp.model_name.lower()
        field_key = '%s.%s' % (model, fp.field_name)
        if fp.allows_reads:
            if field_key in collection_udf_dict:
                choices = []
                data_type = json.loads(collection_udf_dict[field_key].datatype)
            elif is_json_field_reference(fp.field_name):
                choices = None
                data_type = "string"
            else:
                model_inst = safe_get_model_class(fp.model_name)(
                    instance=instance)
                data_type, _, choices = field_type_label_choices(
                    model_inst, fp.field_name, fp.display_field_name)

            digits = get_digits_if_formattable(
                instance, model, fp.field_name)

            units = get_units_if_convertible(
                instance, model, fp.field_name)

            factor = 1.0

            try:
                factor = get_conversion_factor(
                    instance, model, fp.field_name)
            except KeyError:
                pass

            perms[field_key] = {
                'data_type': data_type,
                'choices': choices,
                'units': units,
                'digits': digits,
                'canonical_units_factor': 1.0 / factor,
                'can_write': fp.allows_writes,
                'display_name': fp.display_field_name,
                'field_name': fp.field_name,
                'field_key': field_key,
                'is_collection': field_key in collection_udf_dict
            }

    def get_key_for_group(field_group):
        for key in ('collection_udf_keys', 'field_keys'):
            if key in field_group:
                return key
        return None

    # Remove fields from mobile_api_fields if they are not present in perms
    # (Generally because the user doesn't have read permissions)
    # If no fields are left in a group, remove the group
    mobile_api_fields = copy.deepcopy(instance.mobile_api_fields)

    for field_group in mobile_api_fields:
        key = get_key_for_group(field_group)
        if key:
            field_group[key] = [field for field in field_group[key]
                                if field in perms]

    readable_mobile_api_fields = [group for group in mobile_api_fields
                                  if group.get(get_key_for_group(group), None)]

    info = _instance_info_dict(instance)
    info['fields'] = perms
    info['field_key_groups'] = readable_mobile_api_fields
    info['search'] = instance.mobile_search_fields
    info['date_format'] = _unicode_dateformat(instance.date_format)
    info['short_date_format'] = _unicode_dateformat(instance.short_date_format)

    info['meta_perms'] = {
        'can_add_tree': perms_lib.plot_is_creatable(role),
        'can_edit_tree': perms_lib.plot_is_writable(role),
        'can_edit_tree_photo': perms_lib.treephoto_is_writable(role),
    }

    public_config_keys = ['scss_variables']

    info['config'] = {x: instance.config[x]
                      for x in instance.config
                      if x in public_config_keys}

    if instance.logo:
        info['logoUrl'] = instance.logo.url

    return info


def public_instances(request):
    return _contextify_instances(Instance.objects
                                 .filter(is_public=True)
                                 .filter(get_mobile_instances_filter()))


def _contextify_instances(instances):
    """ Converts instances to context dictionary"""
    return map(_instance_info_dict, instances)


def _instance_info_dict(instance):
    center = instance.center
    center.transform(4326)
    bounds = instance.bounds
    bounds.transform(4326)
    extent = bounds.extent
    p1 = Point(float(extent[0]), float(extent[1]), srid=4326)
    p2 = Point(float(extent[2]), float(extent[3]), srid=4326)
    p1.transform(3857)
    p2.transform(3857)
    extent_radius = p1.distance(p2) / 2

    info = {'geoRevHash': instance.geo_rev_hash,
            'id': instance.pk,
            'url': instance.url_name,
            'name': instance.name,
            'center': {'lat': center.y,
                       'lng': center.x},
            'extent': {'min_lng': extent[0],
                       'min_lat': extent[1],
                       'max_lng': extent[2],
                       'max_lat': extent[3]},
            'extent_radius': extent_radius,
            'eco': _instance_eco_dict(instance)
            }

    if hasattr(instance, 'distance'):
        info['distance'] = instance.distance.km

    return info


def _instance_eco_dict(instance):
    return {
        "supportsEcoBenefits": instance.has_itree_region(),

        # This is a list of eco benefit field sections. Currently, the
        # mobile apps only support tree benefits. The values defined
        # in this structure are used to pull benefit details from a
        # map feature dictionary. The benefit label, formatted
        # currency amount, etc. are all included with the map feature,
        # so the instance only needs to define the ordering of the keys.
        "benefits": [
            {
                "label": "Tree Benefits",
                # The tree benefits _are_ listed under "plot"
                "model": "plot",
                "keys": BenefitCategory.GROUPS,
            }
        ]
    }


def _unicode_dateformat(date_format):
    """
    Converts a Django DATE_FORMAT into a standard unicode date format (see
    http://www.unicode.org/reports/tr35/tr35-31/tr35-dates.html#Date_Format_Patterns)  # NOQA
    This is the format used by Java SimpleDateFormat and iOS NSDateFormatter

    Not an exhaustive conversion, but it suites our needs at the moment
    """
    conv_dict = {
        'j': 'd',
        'd': 'dd',
        'D': 'EEE',
        'l': 'EEEE',
        'n': 'M',
        'm': 'MM',
        'N': 'MMM',
        'M': 'MMM',
        'F': 'MMMM',
        'E': 'MMMM',  # Locale text mont,
        'y': 'yy',
        'Y': 'yyyy'
    }

    unicode_format = ''.join(conv_dict.get(ch, ch) for ch in date_format)

    return unicode_format
