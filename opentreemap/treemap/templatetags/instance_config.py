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


def _feature_allows_perm(instanceuser, model_name,
                         predicate, perm_attr, field=None):
    if instanceuser is None or instanceuser == '' \
       or instanceuser.user_id is None:
        return False
    else:
        perms = instanceuser.role.model_permissions(model_name).all()

        if field:
            perms = perms.filter(field_name=field)

        return predicate(getattr(perm, perm_attr) for perm in perms)


def _feature_allows_writes(instanceuser, model_name, predicate, field=None):
    return _feature_allows_perm(instanceuser, model_name,
                                predicate, 'allows_writes', field=field)


def _feature_allows_reads(instanceuser, model_name, predicate, field=None):
    return _feature_allows_perm(instanceuser, model_name,
                                predicate, 'allows_reads', field=field)


@register.filter
def is_deletable(instanceuser, obj):
    if instanceuser is None or instanceuser.user_id is None:
        return False
    else:
        return obj.user_can_delete(instanceuser.user)


@register.filter
def plot_is_writable(instanceuser, field=None):
    return _feature_allows_writes(instanceuser, 'Plot', predicate=any,
                                  field=field)


@register.filter
def is_read_or_write(perm_string):
    return perm_string in ["read", "write"]


@register.filter
def udf_write_level(instanceuser, udf):
    kwargs = {
        'instanceuser': instanceuser,
        'model_name': udf.model_type,
        'predicate': any,
        'field': 'udf:' + udf.name
    }
    if _feature_allows_writes(**kwargs):
        level = "write"
    elif _feature_allows_reads(**kwargs):
        level = "read"
    else:
        level = None

    return level


@register.filter
def plot_field_is_writable(instanceuser, field):
    return plot_is_writable(instanceuser, field=field)


@register.filter
def geom_is_writable(instanceuser, model_name):
    return _feature_allows_writes(instanceuser, model_name, predicate=any,
                                  field='geom')


@register.filter
def instance_config(instance, field):
    if instance:
        return get_attr_from_json_field(instance, "config." + field)
    else:
        return None
