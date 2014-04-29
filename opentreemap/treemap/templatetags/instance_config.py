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


def _role_allows_perm(role, model_name, predicate,
                      perm_attr, field=None):
    perms = role.model_permissions(model_name).all()

    if field:
        perms = perms.filter(field_name=field)

    return predicate(getattr(perm, perm_attr) for perm in perms)


def _invalid_instanceuser(instanceuser):
    return (instanceuser is None or
            instanceuser == '' or
            instanceuser.user_id is None)


def _feature_allows_perm(instanceuser, model_name,
                         predicate, perm_attr, field=None):
    if _invalid_instanceuser(instanceuser):
        return False
    else:
        return _role_allows_perm(instanceuser.role, model_name,
                                 predicate, perm_attr, field)


@register.filter
def is_deletable(instanceuser, obj):
    if instanceuser is None or instanceuser.user_id is None:
        return False
    else:
        return obj.user_can_delete(instanceuser.user)


@register.filter
def plot_is_writable(instanceuser, field=None):
    return _feature_allows_perm(instanceuser, 'Plot',
                                perm_attr='allows_writes',
                                predicate=any, field=field)


@register.filter
def plot_field_is_writable(instanceuser, field):
    return plot_is_writable(instanceuser, field=field)


@register.filter
def geom_is_writable(instanceuser, model_name):
    return _feature_allows_perm(instanceuser, model_name,
                                perm_attr='allows_writes',
                                predicate=any, field='geom')


@register.filter
def is_read_or_write(perm_string):
    return perm_string in ["read", "write"]


@register.filter
def udf_write_level(instanceuser, udf):

    # required in case non-existent udf
    # is passed to this tag
    if udf is None:
        return None

    if _invalid_instanceuser(instanceuser):
        role = udf.instance.default_role
    else:
        role = instanceuser.role

    kwargs = {
        'role': role,
        'model_name': udf.model_type,
        'predicate': any,
        'field': 'udf:' + udf.name
    }

    if _role_allows_perm(perm_attr='allows_writes', **kwargs):
        level = "write"
    elif _role_allows_perm(perm_attr='allows_reads', **kwargs):
        level = "read"
    else:
        level = None

    return level


@register.filter
def instance_config(instance, field):
    if instance:
        return get_attr_from_json_field(instance, "config." + field)
    else:
        return None
