from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django import template
from treemap.json_field import get_attr_from_json_field

register = template.Library()


def _get_color_from_config(config, name):
    color = config.get(name)
    if color:
        return '#' + color
    else:
        return ''


@register.filter
def primary_color(config):
    return _get_color_from_config(config,
                                  "scss_variables.primary-color")


@register.filter
def secondary_color(config):
    return _get_color_from_config(config,
                                  "scss_variables.secondary-color")


@register.filter
def feature_enabled(instance, feature):
    return instance.feature_enabled(feature)


@register.filter
def plot_field_is_writable(instanceuser, field):
    return plot_is_writable(instanceuser, field)


@register.filter
def plot_is_writable(instanceuser, field=None):
    if instanceuser is None or instanceuser == '':
        return False
    else:
        perms = instanceuser.role.plot_permissions.all()

        if field:
            perms = perms.filter(field_name=field)

        if len(perms) == 0:
            return False
        else:
            return perms[0].allows_writes


@register.filter
def instance_config(instance, field):
    if instance:
        return get_attr_from_json_field(instance, "config." + field)
    else:
        return None
