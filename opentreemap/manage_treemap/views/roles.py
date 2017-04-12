# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from copy import deepcopy

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.functional import Promise
from django.utils.translation import ugettext_lazy as _

from opentreemap.util import json_from_request, dotted_split

from treemap.audit import Role, FieldPermission, add_default_permissions
from treemap.instance import Instance
from treemap.models import Plot, Tree, MapFeature, TreePhoto, MapFeaturePhoto
from treemap.lib.object_caches import role_field_permissions
from treemap.plugin import get_instance_permission_spec

from manage_treemap.views import remove_udf_notification


WRITE_PERM = (_('Full Write Access'),
              FieldPermission.WRITE_DIRECTLY)
PEND_PERM = (_('Pending Write Access'),
             FieldPermission.WRITE_WITH_AUDIT)
READONLY_PERM = (_('Read Only'),
                 FieldPermission.READ_ONLY)
INVISIBLE_PERM = (_('Invisible'),
                  FieldPermission.NONE)

ALL_VISIBLE_PERMS = (WRITE_PERM,
                     # TODO: implement "pending"
                     # PEND_PERM,
                     READONLY_PERM)

ALL_PERMS = ALL_VISIBLE_PERMS + (INVISIBLE_PERM,)


def field_perm_models(instance):
    return {Tree} | {MapFeature.get_subclass(m)
                     for m in instance.map_feature_types}


def model_perm_models(instance):
    return {Instance, Tree, TreePhoto, MapFeaturePhoto} | {
        MapFeature.get_subclass(m) for m in instance.map_feature_types}


def options_for_permission(perm):
    # You can't hide plot id
    if perm.model_name == 'Plot' and perm.field_name == 'geom':
        return ALL_VISIBLE_PERMS
    else:
        return ALL_PERMS


@transaction.atomic
def _update_perms_from_object(role_perms, instance):
    RolePermissionModel = Role.instance_permissions.through
    valid_field_model_names = {m.__name__
                               for m in field_perm_models(instance)}
    valid_perm_models_by_name = {
        m.__name__: m for m in model_perm_models(instance)}
    roles_by_id = {role.pk:
                   role for role in Role.objects.filter(instance=instance)}
    field_perms = {(role, perm.full_name): perm
                   for role in roles_by_id.itervalues()
                   for perm in deepcopy(role_field_permissions(role))}

    input_role_ids = [int(role_id) for role_id in role_perms.iterkeys()]
    for role_id in input_role_ids:
        if role_id not in roles_by_id:
            raise ValidationError("Unrecognized role id [%s]" % role_id)
    input_roles = [roles_by_id[role_id] for role_id in input_role_ids]

    input_role_fields = zip(input_roles, [
        role_inputs['fields'] for role_inputs in role_perms.itervalues()])
    input_role_models = zip(input_roles, [
        role_inputs['models'] for role_inputs in role_perms.itervalues()])

    def validate_model_name(model_name, valid_names):
        if model_name not in valid_names:
            raise ValidationError(
                "model_name must be one of [%s], not %s" %
                (", ".join(valid_names), model_name))

    def validate_and_save_field_perm(role, field_perm):
        for model_field_name, perm_type in field_perm.iteritems():
            model_name, field_name = dotted_split(model_field_name, 2)
            validate_model_name(model_name, valid_field_model_names)

            field_perm = field_perms.get((role, model_field_name), None)

            create = field_perm is None
            if create:
                field_perm = FieldPermission.objects.create(
                    field_name=field_name,
                    model_name=model_name,
                    role=role,
                    instance=role.instance)

            perm_type = int(perm_type)
            if create or field_perm.permission_level != perm_type:
                valid_levels = [level
                                for __, level
                                in options_for_permission(field_perm)]

                if perm_type in valid_levels:
                    field_perm.permission_level = perm_type
                    field_perm.save()
                else:
                    raise Exception('Invalid field type '
                                    '(allowed %s, given %s)' %
                                    (valid_levels, perm_type))

                notifications = instance.config.get('udf_notifications', [])
                if field_perm.full_name in notifications:
                    remove_udf_notification(instance, field_perm.full_name)

    def get_and_validate_permission(codename, Model):
        app_config = Model._meta.app_config
        try:
            return Permission.objects.get_by_natural_key(
                codename, app_config.label, Model.__name__.lower())
        except ObjectDoesNotExist:
            raise ValidationError(
                '{} is not a valid codename for {}.{}'.format(
                    codename, app_config.models_module.__name__,
                    app_config.label))

    def validate_permission_assignment(codename, should_be_assigned, Model):
        if not isinstance(should_be_assigned, bool):
            app_config = Model._meta.app_config
            raise ValidationError(
                '{} is not a valid determination of whether to assign'
                '{} to {}.{}'.format(
                    should_be_assigned, codename,
                    app_config.models_module.__name__, app_config.label))

    def validate_and_save_model_perm(role, model_perm):
        unassign = []
        for model_perm_name, should_be_assigned in model_perm.iteritems():
            model_name, codename = dotted_split(model_perm_name, 2)
            validate_model_name(
                model_name, set(valid_perm_models_by_name.keys()))
            Model = valid_perm_models_by_name[model_name]
            permission = get_and_validate_permission(codename, Model)
            validate_permission_assignment(codename, should_be_assigned, Model)
            if should_be_assigned:
                RolePermissionModel.objects.get_or_create(
                    role=role, permission=permission)
            else:
                unassign.append({'role': role, 'permission': permission})
        if unassign:
            unassign_q = reduce(lambda q1, q2: q1 | q2,
                                [Q(**rpm) for rpm in unassign])
            RolePermissionModel.objects.filter(unassign_q).delete()

    for role, field_perm in input_role_fields:
        validate_and_save_field_perm(role, field_perm)

    for role, model_perm in input_role_models:
        validate_and_save_model_perm(role, model_perm)


def roles_update(request, instance):
    role_perms = json_from_request(request)
    _update_perms_from_object(role_perms, instance)
    return HttpResponse(_('Updated roles'))


def roles_list(request, instance):
    RolePermissionModel = Role.instance_permissions.through

    # We order roles by 'id' as a way for them to be ordered oldest to newest
    roles = Role.objects.filter(instance=instance).order_by('id')

    # Show Tree & Plot first, then sort any GSI models alphabetically
    models = [Tree, Plot] + sorted(
        field_perm_models(instance) - {Tree, Plot},
        key=lambda model: model.display_name(instance))

    model_permissions = {
        Model: Permission.objects.filter(
            Q(codename__startswith='add') |
            Q(codename__startswith='delete'),
            content_type=ContentType.objects.get_for_model(Model)).order_by(
            'codename')
        for Model in models}

    photo_code_name = lambda action, Model: '{}_{}photo'.format(
        action, Model.__name__.lower())

    photo_class_for_model = lambda Model: \
        TreePhoto if Model is Tree else MapFeaturePhoto

    model_photo_permissions = {
        Model: Permission.objects.filter(
            Q(codename=photo_code_name('add', Model)) |
            Q(codename=photo_code_name('delete', Model)),
            content_type=ContentType.objects.get_for_model(
                photo_class_for_model(Model)))
        for Model in models if Model != Plot}
    model_photo_permissions[Plot] = []

    def get_field_perms(role, Model):
        model_name = Model.__name__
        model_perms = [fp for fp in role_field_permissions(
            role, instance, model_name)
            if fp.field_name not in Model.bypasses_authorization]
        return sorted(model_perms, key=lambda p: p.field_name)

    def _get_role_model_perms(permissions, role, Model):
        return [{
            'label': p.name,
            'codename': '{}.{}'.format(Model.__name__, p.codename),
            'role': role,
            'has_permission': RolePermissionModel.objects.filter(
                role=role, permission=p).exists()
            } for p in permissions]

    def get_role_model_perms(role, Model):
        return _get_role_model_perms(
            model_permissions[Model], role, Model)

    def get_role_photo_perms(role, Model):
        return _get_role_model_perms(
            model_photo_permissions[Model], role, photo_class_for_model(Model))

    def get_instance_perms(roles):
        def translated(spec):
            return {k: unicode(v) if isinstance(v, Promise) else v
                    for k, v in spec.iteritems()}

        def combine(base_dict, additional_dict):
            combination = deepcopy(base_dict)
            combination.update(additional_dict)
            return combination

        role_instance_perms = [combine({'role': role}, {
            perm.codename: perm
            for perm in role.instance_permissions.all()})
            for role in roles]

        specs = sorted([translated(spec)
                       for spec in get_instance_permission_spec(instance)],
                       key=lambda spec: spec['label'])

        return [[combine(spec, {
            'codename': 'Instance.{}'.format(spec['codename']),
            'label': spec['label'],
            'description': spec['description'],
            'default_role_names': spec['default_role_names'],
            'has_permission': spec.get('codename') in instance_perms,
            'role': instance_perms['role']})
            for instance_perms in role_instance_perms]
            for spec in specs]

    def role_field_perms(Model):
        return zip(*[get_field_perms(role, Model) for role in roles])

    def role_model_perms(Model):
        return zip(*[get_role_model_perms(role, Model) for role in roles])

    def role_photo_perms(Model):
        return zip(*[get_role_photo_perms(role, Model) for role in roles])

    groups = [{
        'role_model_perms': role_model_perms(Model),
        'role_photo_perms': role_photo_perms(Model),
        'role_field_perms': role_field_perms(Model),
        'name': Model.display_name(instance),
        'model_name': Model.__name__
    } for Model in models]

    return {
        'instance_permissions': get_instance_perms(roles),
        'role_groups': groups,
        'roles': roles,
        'role_ids': ','.join([str(role.id) for role in roles]),
        'photo_permissions': ALL_VISIBLE_PERMS,
        'udf_notifications': instance.config.get('udf_notifications', [])
    }


@transaction.atomic
def roles_create(request, instance):
    params = json_from_request(request)

    role_name = params.get('name', None)

    if not role_name:
        return HttpResponseBadRequest(
            _("Must provide a name for the new role."))

    role, created = Role.objects.get_or_create(name=role_name,
                                               instance=instance,
                                               rep_thresh=0)

    if created is False:
        return HttpResponseBadRequest(
            _("A role with name '%(role_name)s' already exists") %
            {'role_name': role_name})

    add_default_permissions(instance, roles=[role])

    return roles_list(request, instance)
