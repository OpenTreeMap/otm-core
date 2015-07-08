from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.gis.db.models import Field
from treemap.models import InstanceUser, Role

"""
Tools to assist in resolving permissions, specifically when the type of
the thing you are checking against can vary.

When it is simple enough to add a model.can_do_thing method to
models.py, you should do so. However, when the same permission logic
is being executed on varying types, like User, InstanceUser, Role, use
this module as a dispatching service.

It seems likely and beneficial that all permission checking move to
this module over time.

CAVEATS:
Perm checking is complicated by several factors. Helper methods live
on several models, and auxilary functions live in template_tags,
object_caches, and probably views in the multiple packages.
"""

WRITE = 'write'
READ = 'read'
ALLOWS_WRITES = 'allows_writes'
ALLOWS_READS = 'allows_reads'
PHOTO_PERM_FIELDS = frozenset({'image', 'thumbnail', 'id', 'map_feature'})


def _allows_perm(role_related_obj, model_name,
                 predicate, perm_attr,
                 field=None,
                 fields=None,
                 feature_name=None):
    """
    The main permission testing function. This function should
    be called from exported (non-underscore) helper functions.

    role_related_obj can be a Role or InstanceUser (Add more types as needed)

    model_name is a ProperCamelCase string name of the model to test.

    predicate is the function used to set the minimum requirement for
    present permissions to pass the current test. Should be any, all,
    or a custom value.

    perm_attr is the minimum permission value necessary to consider
    the perm present in this context. Should correspond to an attr
    on the FieldPermission class.

    field/fields is the fields to use in conjunction with predicate and
    perm_attr.
    Together they form a truth statement like:
    "all of {'image', 'thumbnail'} have ALLOWS_WRITES"
    "any of {'id', 'mapfeature'} have ALLOWS_READS"

    feature_name checks if this feature is enabled for this instance. While
    not exactly connected to permissions, it's convenient to check this here
    as well.
    """
    if isinstance(role_related_obj, InstanceUser):
        if _invalid_instanceuser(role_related_obj):
            # TODO: in udf_write_level below, we do
            # this same check, but instead of returning
            # false, we go forward by assigning role
            # to be the default role for the given instance.
            # here, we won't always have instance in scope,
            # but we should consider factoring udf_write_level
            # into this method and optionally taking an instance
            # so that one can go forward with the default role.
            return False
        else:
            role = role_related_obj.role
    elif isinstance(role_related_obj, type(None)):
        # almost certainly this is being called with
        # last_effective_instance_user without checking
        # first if it is None. Since we haven't received
        # the instance along with it, we can't resolve
        # the default role, so perms must be blocked entirely.
        # this is not so bad, because this block is mostly
        # to prevent 500 errors.
        return False
    elif isinstance(role_related_obj, Role):
        role = role_related_obj
    else:
        raise NotImplementedError("Please provide a condition for '%s'"
                                  % type(role_related_obj))

    if feature_name and not role.instance.feature_enabled(feature_name):
        return False

    perms = {perm for perm in role.model_permissions(model_name)}

    # process args
    if field and fields:
        raise ValueError("Cannot provide non-None values "
                         "to both 'field' and 'fields'. Pick One.")
    elif field and not fields:
        fields = {field}
    elif not fields:
        fields = set()

    # forcibly convert fields to a set of names (strings)
    # if they were passed in as objects.
    fields = {field.name if isinstance(field, Field) else field
              for field in fields}

    if fields:
        perms = {perm for perm in perms if perm.field_name in fields}

    perm_attrs = {getattr(perm, perm_attr) for perm in perms}

    # TODO: find a better way to support 'all'
    # this is a hack around a quirk, that all([]) == True.
    # Since all is such a common case, it's still nice to
    # support it out of the box.
    if predicate == all and not perm_attrs:
        return False
    else:
        return predicate(perm_attrs)


def _invalid_instanceuser(instanceuser):
    return (instanceuser is None or
            instanceuser == '' or
            instanceuser.user_id is None)


def is_read_or_write(perm_string):
    return perm_string in [READ, WRITE]


def is_deletable(instanceuser, obj):
    if _invalid_instanceuser(instanceuser):
        return False
    else:
        # TODO: factor this off user and roll it into
        # this module
        return obj.user_can_delete(instanceuser.user)


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
        'role_related_obj': role,
        'model_name': udf.model_type,
        'predicate': any,
        'field': 'udf:' + udf.name
    }

    if _allows_perm(perm_attr=ALLOWS_WRITES, **kwargs):
        level = WRITE
    elif _allows_perm(perm_attr=ALLOWS_READS, **kwargs):
        level = READ
    else:
        level = None

    return level


def plot_is_creatable(role_related_obj):
    from treemap.models import Plot
    return _allows_perm(role_related_obj, 'Plot',
                        perm_attr=ALLOWS_WRITES,
                        fields=Plot()._fields_required_for_create(),
                        feature_name='add_plot',
                        predicate=all)


def map_feature_is_writable(role_related_obj, model_obj, field=None):
    return _allows_perm(role_related_obj,
                        model_obj.__class__.__name__,
                        perm_attr=ALLOWS_WRITES,
                        predicate=any, field=field)


def map_feature_is_deletable(role_related_obj, model_obj):
    return _allows_perm(role_related_obj,
                        model_obj.__class__.__name__,
                        perm_attr=ALLOWS_WRITES,
                        predicate=all)


def plot_is_writable(role_related_obj, field=None):
    return _allows_perm(role_related_obj, 'Plot',
                        perm_attr=ALLOWS_WRITES,
                        predicate=any, field=field)


def geom_is_writable(instanceuser, model_name):
    return _allows_perm(instanceuser, model_name,
                        perm_attr=ALLOWS_WRITES,
                        predicate=any, field='geom')


def treephoto_is_writable(role_related_obj):
    return _allows_perm(role_related_obj, 'TreePhoto',
                        fields=PHOTO_PERM_FIELDS | {'tree'},
                        feature_name='tree_image_upload',
                        perm_attr=ALLOWS_WRITES,
                        predicate=all)


def mapfeaturephoto_is_writable(role_related_obj):
    return _allows_perm(role_related_obj, 'MapFeaturePhoto',
                        fields=PHOTO_PERM_FIELDS,
                        feature_name='tree_image_upload',
                        perm_attr=ALLOWS_WRITES,
                        predicate=all)
