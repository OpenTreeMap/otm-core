# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from copy import deepcopy

from treemap.models import NeighborhoodGroup
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.functional import Promise
from django.utils.translation import ugettext_lazy as _


def groups_update(request, instance):
    role_perms = json_from_request(request)
    _update_perms_from_object(role_perms, instance)
    return HttpResponse(_('Updated roles'))


def groups_list(request, instance):

    user_groups = []
    groups = NeighborhoodGroup.objects.all()

    for group in groups:
        for user in group.user_set.all():
            user_groups.append((group, user))

    return {
        'user_groups': user_groups,
        'instance': instance,
    }


@transaction.atomic
def groups_create(request, instance):
    params = json_from_request(request)

    group_name = params.get('name', None)

    if not group_name:
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
