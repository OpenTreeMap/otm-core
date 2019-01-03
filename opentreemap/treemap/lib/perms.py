from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import inspect

from treemap.lib.object_caches import role_field_permissions

from django.contrib.gis.db.models import Field
from treemap.audit import Authorizable
from treemap.models import (InstanceUser, Role, Plot, Tree, TreePhoto,
                            MapFeaturePhoto)

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
    role = _get_role_from_related_object(role_related_obj)
    if role is None:
        return False

    if feature_name and not role.instance.feature_enabled(feature_name):
        return False

    perms = {perm for perm in
             role_field_permissions(role, role.instance, model_name)}

    # process args
    if field and fields:
        fields = set(fields) | {field}
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


def _get_role_from_related_object(role_related_obj):
    if isinstance(role_related_obj, InstanceUser):
        if _invalid_instanceuser(role_related_obj):
            # TODO: in udf_write_level below, we do
            # this same check, but instead of returning
            # None, we go forward by assigning role
            # to be the default role for the given instance.
            # here, we won't always have instance in scope,
            # but we should consider factoring udf_write_level
            # into this method and optionally taking an instance
            # so that one can go forward with the default role.
            return None
        else:
            return role_related_obj.role
    elif isinstance(role_related_obj, type(None)):
        # almost certainly this is being called with
        # last_effective_instance_user without checking
        # first if it is None. Since we haven't received
        # the instance along with it, we can't resolve
        # the default role, so perms must be blocked entirely.
        # this is not so bad, because this block is mostly
        # to prevent 500 errors.
        return None
    elif isinstance(role_related_obj, Role):
        return role_related_obj
    else:
        raise NotImplementedError("Please provide a condition for '%s'"
                                  % type(role_related_obj))


def _invalid_instanceuser(instanceuser):
    return (instanceuser is None or
            instanceuser == '' or
            instanceuser.user_id is None)


def is_read_or_write(perm_string):
    return perm_string in [READ, WRITE]


def _is_deletable(instanceuser, obj):
    # Have to ask if a specific user can delete a specific object
    # because even if the specific user's role cannot delete instances
    # of the object's class, the original creator of the object can,
    # if the Model sets `users_can_delete_own_creations` to `True`
    if _invalid_instanceuser(instanceuser):
        return False
    else:
        return obj.user_can_delete(instanceuser.user)


def is_deletable(instanceuser, obj):
    return _is_deletable(instanceuser, obj)


def photo_is_deletable(instanceuser, photo):
    # TreePhoto needs the version user_can_create and user_can_delete
    # defined in Authorizable, which is a base class for PendingAuditable,
    # which is one of the base classes for MapFeaturePhoto.
    #
    # MapFeaturePhoto, used as a leaf class, overrides these methods
    # in an incompatible way.
    #
    # So skip over the MapFeaturePhoto version by calling
    # MapFeaturePhoto's superclass.
    return _is_deletable(instanceuser, super(MapFeaturePhoto, photo))


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


def map_feature_is_writable(role_related_obj, model_obj, field=None):
    feature_is_writable = _allows_perm(role_related_obj,
                                       model_obj.__class__.__name__,
                                       perm_attr=ALLOWS_WRITES,
                                       predicate=any, field=field)
    tree_is_creatable = False
    tree_is_writable = False
    if (model_obj.__class__.__name__ == 'Plot' and field is None):
        tree_is_creatable = model_is_creatable(role_related_obj, Tree)
        tree_is_writable = _allows_perm(role_related_obj,
                                        'Tree',
                                        perm_attr=ALLOWS_WRITES,
                                        predicate=any)

    return feature_is_writable or tree_is_creatable or tree_is_writable


def plot_is_writable(role_related_obj, field=None):
    return _allows_perm(role_related_obj, 'Plot',
                        perm_attr=ALLOWS_WRITES,
                        predicate=any, field=field)


def plot_is_creatable(role_related_obj):
    return model_is_creatable(role_related_obj, Plot)


def tree_is_writable(role_related_obj, field=None):
    return _allows_perm(role_related_obj, 'Tree',
                        perm_attr=ALLOWS_WRITES,
                        predicate=any, field=field)


def model_is_creatable(role_related_obj, Model):
    role = _get_role_from_related_object(role_related_obj)
    if role is None:
        return False
    return role.can_create(Model)


def any_resource_is_creatable(role_related_obj):
    role = _get_role_from_related_object(role_related_obj)
    if role is None:
        return False

    return any(model_is_creatable(role, Model)
               for Model in role.instance.resource_classes)


def _get_associated_model_class(associated_model):
    if inspect.isclass(associated_model):
        clz = associated_model
    else:
        if callable(getattr(associated_model, 'cast_to_subtype', None)):
            associated_model = associated_model.cast_to_subtype()
        clz = associated_model.__class__ if \
            isinstance(associated_model, Authorizable) else associated_model
    return Tree if clz == Plot else clz


def photo_is_addable(role_related_obj, associated_model):
    '''
    photo_is_addable(role_related_obj, associated_model) returns
    True if a user possessing role_related_obj can add a photo
    to the associated_model, False otherwise.

    role_related_obj may be a role or an instance user.
    associated_model may be a model class or instance of a model.
    '''
    AssociatedClass = _get_associated_model_class(associated_model)
    PhotoClass = TreePhoto if AssociatedClass == Tree else MapFeaturePhoto
    codename = Role.permission_codename(AssociatedClass, 'add', photo=True)
    role = _get_role_from_related_object(role_related_obj)
    return role and role.has_permission(codename, PhotoClass) or False
