# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import csv
import json

from datetime import datetime

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse
from django.templatetags.l10n import localize

from treemap.udf import DATETIME_FORMAT
from treemap.models import User, Audit


def users_csv(request, instance):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=user_export.csv;'
    response['Cache-Control'] = 'no-cache'

    # add BOM to support CSVs in MS Excel
    # http://en.wikipedia.org/wiki/Byte_order_mark
    response.write(u'\ufeff'.encode('utf8'))

    field_names = ['username', 'email', 'firstname', 'lastname', 'email_hash',
                   'allow_email_contact', 'role', 'created', 'organization',
                   'last_edit_model', 'last_edit_model_id',
                   'last_edit_instance_id', 'last_edit_field',
                   'last_edit_previous_value', 'last_edit_current_value',
                   'last_edit_user_id', 'last_edit_action',
                   'last_edit_requires_auth', 'last_edit_ref',
                   'last_edit_created']

    writer = csv.DictWriter(response, field_names)
    writer.writeheader()

    for user in _users_export(request, instance):
        writer.writerow(_user_as_dict(user, instance))

    return response


def users_json(request, instance):
    response = HttpResponse(content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename=user_export.json;'
    response['Cache-Control'] = 'no-cache'

    users_list = [_user_as_dict(user, instance)
                  for user in _users_export(request, instance)]

    response.write(json.dumps(users_list))

    return response


def _users_export(request, instance):
    users = User.objects.filter(instance=instance)\
                        .order_by('username')

    min_join_ts = request.REQUEST.get("minJoinDate")
    if min_join_ts:
        try:
            min_join_date = datetime.strptime(min_join_ts, DATETIME_FORMAT)
        except ValueError:
            raise ValidationError("minJoinDate %(ts)s not a valid timestamp"
                                  % {"ts": min_join_ts})

        iuser_ids = Audit.objects.filter(instance=instance)\
                                 .filter(model='InstanceUser')\
                                 .filter(created__gt=min_join_date)\
                                 .distinct('model_id')\
                                 .values_list('model_id', flat=True)

        users = users.filter(instanceuser__in=iuser_ids)

    min_edit_ts = request.REQUEST.get("minEditDate")
    if min_edit_ts:
        try:
            min_edit_date = datetime.strptime(min_edit_ts, DATETIME_FORMAT)
        except ValueError:
            raise ValidationError("minEditDate %(ts)s not a valid timestamp"
                                  % {"ts": min_edit_ts})

        user_ids = Audit.objects\
            .filter(instance=instance)\
            .filter(Q(created__gt=min_edit_date) |
                    Q(updated__gt=min_edit_date))\
            .distinct('user')\
            .values_list('user_id', flat=True)

        users = users.filter(id__in=user_ids)

    return users


def _user_as_dict(user, instance):
    iuser = user.get_instance_user(instance)
    role_name = None
    if iuser:
        role_name = iuser.role.name

    email = ''

    if user.allow_email_contact:
        email = user.email

    modeldata = {'username': user.username,
                 'email': email,
                 'email_hash': user.email_hash,
                 'organization': user.organization,
                 'firstname': user.firstname,
                 'lastname': user.lastname,
                 'allow_email_contact': str(user.allow_email_contact),
                 'created': str(user.created),
                 'role': role_name}

    last_edits = Audit.objects.filter(instance=instance,
                                      user=user)\
                              .order_by('-updated')[:1]

    if last_edits:
        last_edit = last_edits[0]

        modeldata.update({'last_edit_%s' % k: v
                          for (k, v) in last_edit.dict().iteritems()})

    return _sanitize_unicode_record(modeldata)


# https://github.com/azavea/django-queryset-csv/blob/
# master/djqscsv/djqscsv.py#L123
def _sanitize_unicode_record(record):

    def _sanitize_value(value):
        if isinstance(val, unicode):
            return value.encode("utf-8")
        else:
            return localize(value)

    obj = {}
    for key, val in record.iteritems():
        if val:
            obj[_sanitize_value(key)] = _sanitize_value(val)

    return obj
