from django import template

from manage_treemap.views.roles import options_for_permission
from treemap.audit import FieldPermission
from treemap.lib.object_caches import role_field_permissions


register = template.Library()


@register.filter
def photo_permission_level(role):
    photo_perms = role_field_permissions(role, None, 'TreePhoto')

    if photo_perms:
        perm = min([p.permission_level for p in photo_perms])
    else:
        perm = FieldPermission.READ_ONLY

    label = dict(FieldPermission.choices)[perm]

    return perm, label


register.filter(options_for_permission)
