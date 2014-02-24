# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as trans
from django.http import HttpResponse

from registration.models import RegistrationProfile

from treemap.models import User


def user_info(request):
    user_dict = request.user.as_dict()

    del user_dict['password']

    user_dict["status"] = "success"

    return user_dict


def _conflict_response(s):
    response = HttpResponse()
    response.status_code = 409
    response.content = s

    return response


def create_user(request):
    data = json.loads(request.body)

    if 'allow_email_contact' not in data:
        data['allow_email_contact'] = False

    req_fields = {'email', 'username', 'password', 'allow_email_contact'}
    all_fields = req_fields | {'organization', 'lastname', 'firstname'}

    errors = {}
    for field in req_fields:
        if field not in data:
            errors[field] = [trans('This field is required')]

    for inputfield in data:
        if inputfield not in all_fields:
            errors[inputfield] = [trans('Unrecognized field')]

    if errors:
        raise ValidationError(errors)

    dup_username = User.objects.filter(username=data['username'])
    dup_email = User.objects.filter(email=data['email'])

    if dup_username.exists():
        return _conflict_response(trans('Username is already in use'))
    if dup_email.exists():
        return _conflict_response(trans('Email is already in use'))

    user = User(**data)

    # Needed to properly hash the password
    user.set_password(data['password'])
    user.active = True
    user.save()

    RegistrationProfile.objects.create_profile(user)

    return {'status': 'success', 'id': user.pk}
