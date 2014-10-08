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


def udf_defs(instance, model_name=None):
    if settings.USE_OBJECT_CACHES:
        return _get_adjuncts(instance).udf_defs(model_name)
    else:
        return _udf_defs_from_db(instance, model_name)


def clear_caches():
    global _adjuncts
    _adjuncts = {}


def invalidate_adjuncts(*args, **kwargs):
    # Called by 'save' and 'delete' signal handlers for adjunct objects
    if settings.USE_OBJECT_CACHES:
        adjunct_object = kwargs['instance']  # 'instance' is a Django term here
        instance = adjunct_object.instance
        if instance.id in _adjuncts:
            del _adjuncts[instance.id]
        instance.adjuncts_timestamp += 1
        instance.save()

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
    return list(perms)


def _udf_defs_from_db(instance, model_name):
    from treemap.udf import UserDefinedFieldDefinition
    defs = UserDefinedFieldDefinition.objects.filter(instance=instance)
    if model_name:
        defs = defs.filter(model_type=model_name)
    return list(defs)

# ------------------------------------------------------------------------
# Fetch info from cache


def _get_adjuncts(instance):
    adjuncts = _adjuncts.get(instance.id)
    if not adjuncts or adjuncts.timestamp < instance.adjuncts_timestamp:
        adjuncts = _InstanceAdjuncts(instance)
        _adjuncts[instance.id] = adjuncts
    return adjuncts


class _InstanceAdjuncts:
    def __init__(self, instance):
        self._instance = instance
        self._user_role_ids = {}
        self._permissions = {}
        self._udf_defs = {}
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

    def udf_defs(self, model_name):
        if not self._udf_defs:
            self._load_udf_defs()
        defs = self._udf_defs.get(model_name)
        return defs if defs else []

    def _load_roles(self):
        from treemap.models import InstanceUser

        for iu in InstanceUser.objects.filter(instance=self._instance):
            self._user_role_ids[iu.user_id] = iu.role_id

        self._user_role_ids[None] = self._instance.default_role_id

    def _load_permissions(self):
        from treemap.audit import FieldPermission
        for fp in FieldPermission.objects.filter(instance=self._instance):
            dict = self._permissions
            self._append_value(dict, (fp.role_id, fp.model_name), fp)
            self._append_value(dict, (fp.role_id, None), fp)

    def _append_value(self, dict, key, value):
        if key not in dict:
            dict[key] = []
        dict[key].append(value)

    def _load_udf_defs(self):
        from treemap.udf import UserDefinedFieldDefinition
        qs = UserDefinedFieldDefinition.objects.filter(instance=self._instance)
        for udfd in qs:
            self._append_value(self._udf_defs, udfd.model_type, udfd)
            # Add to the "None" key for looking up UDF defs without model name
            self._append_value(self._udf_defs, None, udfd)
