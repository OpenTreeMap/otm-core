# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf import settings
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D

from treemap.exceptions import HttpBadRequestException
from treemap.models import Instance, InstanceUser
from treemap.units import (get_units_if_convertible, get_digits_if_formattable,
                           get_conversion_factor)
from treemap.util import safe_get_model_class
from treemap.templatetags.form_extras import field_type_label_choices
from treemap.json_field import is_json_field_reference


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

        if max_instances not in xrange(1, 501):
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

    instances = Instance.objects.distance(point)\
        .filter(is_public=True)\
        .exclude(pk__in=user_instance_ids)\
        .filter(bounds__distance_lte=(point, D(m=distance)))\
        .order_by('distance')[0:max_instances]

    my_instances = Instance.objects.distance(point)\
        .filter(pk__in=user_instance_ids)\
        .filter(bounds__distance_lte=(point, D(m=distance)))\
        .order_by('distance')

    return {
        'nearby': [_instance_info_dict(instance)
                   for instance in instances],
        'personal': [_instance_info_dict(instance)
                     for instance in my_instances]
    }


def instance_info(request, instance):
    """
    Get all the info we need about a given instance

    If also includes info about the fields available for the
    instance. If a user has been specified the field info
    will be tailored to that user
    """
    user = request.user

    role = instance.default_role
    if user and not user.is_anonymous():
        instance_user = user.get_instance_user(instance)
        if instance_user:
            role = instance_user.role

    perms = {}

    collection_udfs = instance.userdefinedfielddefinition_set\
                              .filter(iscollection=True)
    collection_udf_dict = {"%s.%s" % (udf.model_type.lower(),
                                      udf.canonical_name): udf
                           for udf in collection_udfs}

    for fp in role.fieldpermission_set.all():
        model = fp.model_name.lower()
        field_key = '%s.%s' % (model, fp.field_name)
        if fp.allows_reads:
            if field_key in collection_udf_dict:
                choices = []
                data_type = collection_udf_dict[field_key].datatype
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

    info = _instance_info_dict(instance)
    info['fields'] = perms
    info['field_key_groups'] = instance.mobile_api_fields
    info['search'] = instance.mobile_search_fields

    public_config_keys = ['scss_variables']

    info['config'] = {x: instance.config[x]
                      for x in instance.config
                      if x in public_config_keys}

    if instance.logo:
        info['logoUrl'] = instance.logo.url

    return info


def _instance_info_dict(instance):
    center = instance.center
    center.transform(4326)
    bounds = instance.bounds
    bounds.transform(4326)
    extent = bounds.extent

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
                "keys": [
                    "energy",
                    "stormwater",
                    "airquality",
                    "co2",
                    "co2storage"
                ]
            }
        ]
    }
