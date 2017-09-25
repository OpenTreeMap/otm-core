from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from django import template
from treemap.json_field import get_attr_from_json_field
from treemap.lib import perms

register = template.Library()


def _get_color_from_config(config, name):
    color = config.get(name)
    if color:
        return '#' + color
    else:
        return ''


@register.filter
def primary_color(config):
    return _get_color_from_config(config, "scss_variables.primary-color")


@register.filter
def secondary_color(config):
    return _get_color_from_config(config, "scss_variables.secondary-color")


@register.filter
def feature_enabled(instance, feature):
    return instance.feature_enabled(feature)


@register.filter
def has_permission(instance_user, codename):
    return instance_user.role.has_permission(codename)


@register.filter
def plot_field_is_writable(thing, field):
    return perms.plot_is_writable(thing, field=field)


@register.filter
def instance_config(instance, field):
    if instance:
        return get_attr_from_json_field(instance, "config." + field)
    else:
        return None


@register.filter
def get_advanced_search_fields(instance, user):
    return instance.advanced_search_fields(user)


@register.filter
def get_udfc_search_fields(instance, user):
    return instance.get_udfc_search_fields(user)


@register.filter
def as_json(d):
    return json.dumps(d)

udf_write_level = register.filter(perms.udf_write_level)
map_feature_is_writable = register.filter(perms.map_feature_is_writable)
plot_is_writable = register.filter(perms.plot_is_writable)
is_deletable = register.filter(perms.is_deletable)
photo_is_deletable = register.filter(perms.photo_is_deletable)
is_read_or_write = register.filter(perms.is_read_or_write)
photo_is_addable = register.filter(perms.photo_is_addable)
any_resource_is_creatable = register.filter(perms.any_resource_is_creatable)
plot_is_creatable = register.filter(perms.plot_is_creatable)
