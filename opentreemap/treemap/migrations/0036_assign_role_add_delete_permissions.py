# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from django.db.models import Q


_WRITE_DIRECTLY = 3


def add_permission(apps, schema_editor):
    models = _get_main_models(apps)
    Role, __, __, ContentType = models

    authorizable_models = _get_authorizable_models(apps)
    model_untracked = {Model: _model_do_not_track(apps, Model)
                       for Model in authorizable_models}

    photo_add_permissions = {
        _get_model_hash(Model): _make_photo_permission('add', Model, models)
        for Model in authorizable_models}

    photo_delete_permissions = {
        _get_model_hash(Model): _make_photo_permission('delete', Model, models)
        for Model in authorizable_models}

    for role in Role.objects.filter(instance__isnull=False):
        _add_permissions_to_role(role, ContentType, authorizable_models,
                                 model_untracked,
                                 photo_add_permissions,
                                 photo_delete_permissions)


def _add_permissions_to_role(role, ContentType, authorizable_models,
                             model_untracked,
                             photo_add_permissions, photo_delete_permissions):
    role_permissions = set()

    for Model in authorizable_models:

        can_create, can_delete = _can_create_or_delete(
            model_untracked[Model], role, Model)

        add_permission, delete_permission = tuple(
            _get_model_perms(Model, ContentType))

        if can_create:
            role_permissions.add(add_permission)
            photo_permission = photo_add_permissions[_get_model_hash(Model)]
            if photo_permission:
                role_permissions.add(photo_permission)
        if can_delete:
            role_permissions.add(delete_permission)
            photo_permission = photo_delete_permissions[_get_model_hash(Model)]
            if photo_permission:
                role_permissions.add(photo_permission)

    role.instance_permissions.add(*role_permissions)


def remove_permission(apps, schema_editor):
    models = _get_main_models(apps)
    Role, Permission, MapFeaturePhoto, ContentType = models
    RolePermissionModel = Role.instance_permissions.through

    authorizable_models = _get_authorizable_models(apps)

    app_labels = {M._meta.app_label: [] for M in authorizable_models}
    for M in authorizable_models:
        app_labels[M._meta.app_label].append(M.__name__.lower())

    ct_query = reduce(lambda q1, q2: q1 | q2, [
        Q(app_label=label, model__in=app_models)
        for label, app_models in app_labels.iteritems()])

    photo_query = Q(app_label='treemap', model='mapfeaturephoto')

    all_permissions = Permission.objects.filter(
        content_type__in=ContentType.objects.filter(ct_query | photo_query))
    rpms = RolePermissionModel.objects.filter(permission__in=all_permissions)

    non_photo_permissions = all_permissions.filter(
        content_type__in=ContentType.objects.filter(ct_query))

    # role_{add,delete}_models contain (role, model) pairs for models
    # on which the old field permissions must be restored to the roles.
    # They include Tree and TreePhoto because there always was
    # a field permission setup for them,
    # but exclude MapFeaturePhoto because that previously was not managed
    # per subclass of MapFeature.
    role_delete_models = _get_role_model_action_perms(
        apps, rpms, non_photo_permissions, 'delete')
    # if it's deletable, it's creatable
    role_add_models = _get_role_model_action_perms(
        apps, rpms, non_photo_permissions, 'add') - role_delete_models

    artificial_permissions = Permission.objects.filter(
        content_type__in=ContentType.objects.filter(photo_query)).exclude(
        codename__endswith='mapfeaturephoto')

    artificial_permissions_roles = {ar.role for ar in rpms.filter(
                                    permission__in=artificial_permissions)}

    FieldPermission = apps.get_model('treemap', 'FieldPermission')

    # Remove *all* permissions from roles
    rpms.delete()

    model_untracked = {Model: _model_do_not_track(apps, Model)
                       for Model in authorizable_models | {MapFeaturePhoto}}
    _restore_add_delete_field_permissions(
        FieldPermission, model_untracked,
        role_add_models, role_delete_models)

    _restore_photo_permissions(
        FieldPermission, MapFeaturePhoto, model_untracked,
        artificial_permissions, artificial_permissions_roles)

    # Remove artificial permissions themselves
    artificial_permissions.delete()


def _restore_photo_permissions(FieldPermission, MapFeaturePhoto,
                               model_untracked, artificial_permissions,
                               roles):
    _restore_add_delete_field_permissions(FieldPermission, model_untracked,
                                          set(),
                                          {(r, MapFeaturePhoto)
                                           for r in roles})


def _restore_add_delete_field_permissions(FieldPermission, model_untracked,
                                          role_add_models, role_delete_models):
    perms_to_recreate = []
    perms_to_update = []

    def record_perms(fieldnames_func):
        not_tracked = model_untracked[Model]
        fieldnames = fieldnames_func(not_tracked, Model)
        for name in fieldnames:
            fp = FieldPermission.objects.filter(
                model_name=Model.__name__,
                field_name=name,
                role=role,
                instance=role.instance).first()
            if fp is None:
                perms_to_recreate.append(FieldPermission(
                    model_name=Model.__name__,
                    field_name=name,
                    role=role,
                    instance=role.instance,
                    permission_level=_WRITE_DIRECTLY))
            elif fp.permission_level < _WRITE_DIRECTLY:
                perms_to_update.append(fp.id)

    for role, Model in role_add_models:
        record_perms(_fieldnames_required_for_create)

    for role, Model in role_delete_models:
        record_perms(_tracked_fields)

    FieldPermission.objects.bulk_create(perms_to_recreate)
    FieldPermission.objects.filter(id__in=perms_to_update).update(
        permission_level=_WRITE_DIRECTLY)


def _get_role_model_action_perms(apps, role_model_permissions, permissions,
                                 action):
    action_permissions = permissions.filter(codename__startswith=action)
    role_model_action_perms = role_model_permissions.filter(
        permission__in=action_permissions)

    get_model = lambda rmap: apps.get_model(
        rmap.permission.content_type.app_label,
        rmap.permission.content_type.model)
    return {(rmap.role, get_model(rmap))
            for rmap in role_model_action_perms}


def _get_model_perms(Model, ContentType):
    return ContentType.objects.get_for_model(Model)\
        .permission_set\
        .exclude(codename__startswith='change_')\
        .order_by('codename')


def _get_model_hash(Model):
    return '{}.{}'.format(Model._meta.app_label, Model.__name__)


def _can_create_or_delete(not_tracked, role, Model):
    field_permissions = role.fieldpermission_set.filter(
        model_name=Model.__name__,
        permission_level=_WRITE_DIRECTLY)

    required_for_create = _fieldnames_required_for_create(not_tracked, Model)
    can_create_permissions = field_permissions.filter(
        field_name__in=required_for_create)

    can_create = len(required_for_create) == can_create_permissions.count()

    tracked_fields = _tracked_fields(not_tracked, Model)
    can_delete_permissions = field_permissions.filter(
        field_name__in=tracked_fields)
    can_delete = len(tracked_fields) == can_delete_permissions.count()

    return (can_create, can_delete)


def _model_do_not_track(apps, Model):
    MapFeature = apps.get_model('treemap', 'MapFeature')
    MapFeaturePhoto = apps.get_model('treemap', 'MapFeaturePhoto')
    PolygonalMapFeature = apps.get_model('stormwater', 'PolygonalMapFeature')
    UserDefinedFieldDefinition = apps.get_model(
        'treemap', 'UserDefinedFieldDefinition')
    collection_udfs = UserDefinedFieldDefinition.objects.filter(
        model_type=Model.__name__, iscollection=True)
    no_track = {'instance', 'updated_at'}
    if issubclass(Model, MapFeature):
        no_track |= {'feature_type', 'mapfeature_ptr', 'hide_at_zoom'}
    if issubclass(Model, MapFeaturePhoto):
        no_track |= {'created_at', 'mapfeaturephoto_ptr'}
    if issubclass(Model, PolygonalMapFeature):
        no_track |= {'polygonalmapfeature_ptr'}
    # django doesn't find class UDFModel in treemap.
    if 'udfs' in [f.name for f in Model._meta.fields]:
        no_track |= {'udfs'} | {'udf:{}'.format(udfd.name)
                                for udfd in collection_udfs}
    return no_track


def _fieldnames_required_for_create(not_tracked, Model):
    return {field.name for field in Model._meta.fields
            if (not field.null and
                not field.blank and
                not field.primary_key and
                not field.name in not_tracked)}


def _tracked_fields(not_tracked, Model):
    return {field.name for field in Model._meta.fields
            if field.name not in not_tracked}


def _to_photo_codename(Model, action):
    return '{}_{}{}'.format(action, Model.__name__.lower(), 'photo')


def _make_photo_permission(action, Model, models):
    if Model.__name__ in {'Tree', 'Plot', 'TreePhoto'}:
        return None

    __, Permission, MapFeaturePhoto, ContentType = models

    # MapFeaturePhoto is not subclassed for each MapFeature leaf class,
    # so per-MapFeature-leaf permissions must be constructed.
    photo_content_type = ContentType.objects.get_for_model(MapFeaturePhoto)
    return Permission.objects.create(
        codename=_to_photo_codename(Model, action),
        name='Can {} {} photo'.format(action, Model._meta.verbose_name),
        content_type=photo_content_type)


def _get_main_models(apps):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Role = apps.get_model('treemap', 'Role')
    Permission = apps.get_model('auth', 'Permission')
    MapFeaturePhoto = apps.get_model('treemap', 'MapFeaturePhoto')
    return Role, Permission, MapFeaturePhoto, ContentType


def _all_subclasses(cls):
    subclasses = set(cls.__subclasses__())
    return subclasses | {clz for s in subclasses for clz in _all_subclasses(s)}


def _get_authorizable_models(apps):
    Tree = apps.get_model('treemap', 'Tree')
    TreePhoto = apps.get_model('treemap', 'TreePhoto')
    MapFeature = apps.get_model('treemap', 'MapFeature')
    all_models = set(apps.get_models()) & _all_subclasses(MapFeature)
    leaves = {s for s in all_models if not s.__subclasses__()}
    return leaves | {Tree, TreePhoto}


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0035_merge'),
        ('stormwater', '0010_stormwater_blank_true')
    ]

    operations = [
        migrations.RunPython(add_permission, remove_permission),
    ]
