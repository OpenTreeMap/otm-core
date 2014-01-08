# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf import settings
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D

from treemap.exceptions import HttpBadRequestException
from treemap.models import Instance, InstanceUser
from treemap.units import get_units_if_convertible, get_digits_if_formattable
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

    for fp in role.fieldpermission_set.all():
        model = fp.model_name.lower()
        if fp.allows_reads:
            if model not in perms:
                perms[model] = []

            if is_json_field_reference(fp.field_name):
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

            perms[model].append({
                'data_type': data_type,
                'choices': choices,
                'units': units,
                'digits': digits,
                'can_write': fp.allows_writes,
                'display_name': fp.display_field_name,
                'field_name': fp.field_name
            })

    info = _instance_info_dict(instance)
    info['fields'] = perms
    info['search'] = instance.advanced_search_fields

    return info


def _instance_info_dict(instance):
    center = instance.center
    center.transform(4326)

    info = {'geoRev': instance.geo_rev_hash,
            'id': instance.pk,
            'url': instance.url_name,
            'name': instance.name,
            'center': {'lat': center.y,
                       'lng': center.x},
            }
    if hasattr(instance, 'distance'):
        info['distance'] = instance.distance.km
