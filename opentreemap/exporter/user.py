# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import csv
import json

from datetime import datetime

from contextlib import contextmanager

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.templatetags.l10n import localize

from treemap.udf import DATETIME_FORMAT
from treemap.models import User, Audit


def write_users(data_format, *args, **kwargs):
    fn = _write_users_csv if data_format == 'csv' else _write_users_json
    fn(*args, **kwargs)


def _write_users_csv(csv_obj, instance, min_join_ts=None, min_edit_ts=None):
    field_names = ['username', 'email', 'first_name',
                   'last_name', 'email_hash',
                   'allow_email_contact', 'role', 'created', 'organization',
                   'last_edit_model', 'last_edit_model_id',
                   'last_edit_instance_id', 'last_edit_field',
                   'last_edit_previous_value', 'last_edit_current_value',
                   'last_edit_user_id', 'last_edit_action',
                   'last_edit_requires_auth', 'last_edit_ref',
                   'last_edit_created']
    writer = csv.DictWriter(csv_obj, field_names)
    writer.writeheader()
    for user in _users_export(instance, min_join_ts, min_edit_ts):
        writer.writerow(_user_as_dict(user, instance))


def _write_users_json(json_obj, instance, min_join_ts=None, min_edit_ts=None):
    users = _users_export(instance, min_join_ts, min_edit_ts)
    users_list = [_user_as_dict(user, instance) for user in users]
    json_obj.write(json.dumps(users_list))


def _users_export(instance, min_join_ts, min_edit_ts):
    users = User.objects.filter(instance=instance)\
                        .order_by('username')

    if min_join_ts:
        with _date_filter(min_join_ts, 'minJoinDate') as min_join_date:
            iuser_ids = Audit.objects.filter(instance=instance)\
                                     .filter(model='InstanceUser')\
                                     .filter(created__gt=min_join_date)\
                                     .distinct('model_id')\
                                     .values_list('model_id', flat=True)
            users = users.filter(instanceuser__in=iuser_ids)

    if min_edit_ts:
        with _date_filter(min_edit_ts, 'minEditDate') as min_edit_date:
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
                 'organization': user.get_organization(),
                 'first_name': user.get_first_name(),
                 'last_name': user.get_last_name(),
                 'email': email,
                 'email_hash': user.email_hash,
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


@contextmanager
def _date_filter(timestamp, name):
    try:
        filter_date = datetime.strptime(timestamp, DATETIME_FORMAT)
    except ValueError:
        raise ValidationError("%(name)s %(ts)s not a valid timestamp"
                              % {"ts": timestamp, "name": name})
    yield filter_date
