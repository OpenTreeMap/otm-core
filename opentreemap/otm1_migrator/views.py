# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import csv

from django.conf import settings

from treemap.util import get_csv_response
from treemap.models import User

from models import OTM1UserRelic

# assumptions:
# * there are n userrelics and m users, such that n >= m
# * the user that exists in otm2 is the one with the latest last_login
# * this csv will have one record per userrelic,
#   for relics that have email occurrences greater than one,
#   not including the relic that matches the username that was chosen.

_EMAIL_TEMPLATE = """
Hi %(addressee)s,

Thanks for using %(site_name)s! \
We recently upgraded to the newest version \
of the OpenTreeMap software that powers the \
site ("OTM2"). We noticed there were multiple \
accounts created in the old site for your email, \
"%(email)s". This is not permitted in OTM2, so we \
have merged the activity of your multiple accounts \
onto one, "%(otm2_username)s". If you have any difficulty \
signing in, please contact us at %(contact_email)s.
"""


def render_email_body(user, instance):
    site_name = instance.name
    addressee = user.first_name or "%s user" % site_name
    return _EMAIL_TEMPLATE % {
        'addressee': addressee,
        'site_name': site_name,
        'email': user.email,
        'otm2_username': user.username,
        'contact_email': settings.SUPPORT_EMAIL_ADDRESS
    }


def dupl_user_csv(request, instance):
    duplicate_ids_query = """
    SELECT *
    FROM otm1_migrator_otm1userrelic
    WHERE email IN
    (SELECT email
     FROM otm1_migrator_otm1userrelic
     WHERE instance_id=%s
     GROUP BY email
     HAVING count(id) > 1)
    ORDER BY "email"
    """ % instance.pk

    duplicate_relics = OTM1UserRelic.objects.raw(duplicate_ids_query)
    relics = duplicate_relics

    response = get_csv_response('user_export.csv')

    writer = csv.DictWriter(response,
                            ['otm1_user_id',
                             'otm2_model_id',
                             'otm1_username',
                             'otm2_username',
                             'last_login',
                             'first_name',
                             'last_name',
                             'email',
                             'body'])
    writer.writeheader()

    for relic in relics:
        user = User.objects.get(pk=relic.otm2_model_id)
        if relic.otm1_username == user.username:
            continue
        assert relic.email.lower() == user.email.lower()
        row = {
            'otm1_user_id': relic.otm1_model_id,
            'otm2_model_id': user.pk,
            'otm1_username': relic.otm1_username,
            'last_login': user.last_login,
            'otm2_username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
        }
        body = render_email_body(user, instance)
        row['body'] = body
        writer.writerow(row)

    return response
