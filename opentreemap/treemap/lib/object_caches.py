# -*- coding: utf-8 -*-
from django.conf import settings

# For each instance, cache "adjunct" objects -- frequently-accessed objects
# which change rarely -- by storing them in local memory. Track cache validity
# via a database timestamp on each instance (instance.adjunct_timestamp).
# Check the timestamp before returning any object from the cache; if it's stale
# invalidate all adjunct objects for the instance.
#
# When an adjunct object is modified (saved to the db or deleted), invalidate
# the appropriate instance's cache and update its timestamp. The timestamp
# update will cause the change to propagate to any other servers.

_adjuncts = {}

# ------------------------------------------------------------------------
# Interface functions

def permissions(user, instance, model_name=None):
    if settings.USE_OBJECT_CACHES:
        return _get_adjuncts(instance).permissions(user, model_name)
    else:
        return _permissions_from_db(user, instance, model_name)


def role_permissions(role, instance=None, model_name=None):
    if settings.USE_OBJECT_CACHES:
        if not instance:
            instance = role.instance
        return _get_adjuncts(instance).role_permissions(role.id, model_name)
    else:
        return _role_permissions_from_db(role, model_name)


def clear_caches():
    global _adjuncts
    _adjuncts = {}

# These functions are called by post_save hooks defined elsewhere.
# (Defining them here with @receiver caused circular import problems.)

# Called on post_save of InstanceUser
def update_cached_role_for_instance_user(*args, **kwargs):
    if settings.USE_OBJECT_CACHES:
        instance_user = kwargs['instance']
        _invalidate_adjuncts(instance_user.instance)


# Called on post_save of FieldPermission
def on_field_permission_save_after(*args, **kwargs):
    if settings.USE_OBJECT_CACHES:
        field_permission = kwargs['instance']
        _invalidate_adjuncts(field_permission.instance)

# ------------------------------------------------------------------------
# Fetch info from database when not using cache

def _permissions_from_db(user, instance, model_name):
    if user is None or user.is_anonymous():
        role = instance.default_role
    else:
        role = user.get_role(instance)
    return _role_permissions_from_db(role, model_name)


def _role_permissions_from_db(role, model_name):
    if model_name:
        perms = role.fieldpermission_set.filter(model_name=model_name)
    else:
        perms = role.fieldpermission_set.all()
    return perms

# ------------------------------------------------------------------------
# Fetch info from cache

def _get_adjuncts(instance):
    adjuncts = _adjuncts.get(instance.id)
    if not adjuncts or adjuncts.timestamp < instance.adjuncts_timestamp:
        adjuncts = _InstanceAdjuncts(instance)
        _adjuncts[instance.id] = adjuncts
    return adjuncts


def _invalidate_adjuncts(instance):
    if instance.id in _adjuncts:
        del _adjuncts[instance.id]
    instance.adjuncts_timestamp += 1
    instance.save()


class _InstanceAdjuncts:
    def __init__(self, instance):
        self._instance = instance
        self._user_role_ids = {}
        self._permissions = {}
        self._udfs = {}
        self.timestamp = instance.adjuncts_timestamp

    def permissions(self, user, model_name):
        if not self._user_role_ids:
            self._load_roles()
        if user and user.id in self._user_role_ids:
            role_id = self._user_role_ids[user.id]
        else:
            role_id = self._user_role_ids[None]
        return self.role_permissions(role_id, model_name)

    def role_permissions(self, role_id, model_name):
        if not self._permissions:
            self._load_permissions()
        perms = self._permissions.get((role_id, model_name))
        return perms if perms else []

    def _load_roles(self):
        from treemap.models import InstanceUser

        for iu in InstanceUser.objects.filter(instance=self._instance):
            self._user_role_ids[iu.user_id] = iu.role_id

        self._user_role_ids[None] = self._instance.default_role_id

    def _load_permissions(self):
        from treemap.audit import FieldPermission
        for fp in FieldPermission.objects.filter(instance=self._instance):
            self._append_permission((fp.role_id, fp.model_name), fp)
            self._append_permission((fp.role_id, None), fp)

    def _append_permission(self, key, value):
        if key not in self._permissions:
            self._permissions[key] = []
        self._permissions[key].append(value)

