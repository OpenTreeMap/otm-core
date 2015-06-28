from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

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
def plot_field_is_writable(thing, field):
    return perms.plot_is_writable(thing, field=field)


@register.filter
def instance_config(instance, field):
    if instance:
        return get_attr_from_json_field(instance, "config." + field)
    else:
        return None

udf_write_level = register.filter(perms.udf_write_level)
geom_is_writable = register.filter(perms.geom_is_writable)
mapfeature_is_writable = register.filter(perms.map_feature_is_writable)
plot_is_writable = register.filter(perms.plot_is_writable)
is_deletable = register.filter(perms.is_deletable)
is_read_or_write = register.filter(perms.is_read_or_write)
treephoto_is_writable = register.filter(perms.treephoto_is_writable)
mapfeaturephoto_is_writable = register.filter(
    perms.mapfeaturephoto_is_writable)
