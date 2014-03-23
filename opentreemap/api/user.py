# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as trans

from registration.models import RegistrationProfile

from treemap.views import upload_user_photo
from treemap.models import User


REQ_FIELDS = {'email', 'username', 'password', 'allow_email_contact'}
ALL_FIELDS = REQ_FIELDS | {'organization', 'lastname', 'firstname'}


def update_profile_photo(request, user_id):
    user = get_object_or_404(User, pk=user_id)

    if user.pk != request.user.pk:
        return HttpResponseForbidden()

    return upload_user_photo(request, user)


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


def update_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)

    if user.pk != request.user.pk:
        return HttpResponseForbidden()

    data = json.loads(request.body)

    errors = {}
    for field in ALL_FIELDS:
        if field in data:
            if field in REQ_FIELDS and not field:
                errors[field] = [trans('This field cannot be empty')]
            else:
                if field == 'password':
                    user.set_password(data[field])
                else:
                    setattr(user, field, data[field])

    if errors:
        raise ValidationError(errors)
    else:
        user.save()

    return user


def create_user(request):
    data = json.loads(request.body)

    if 'allow_email_contact' not in data:
        data['allow_email_contact'] = False

    errors = {}
    for field in REQ_FIELDS:
        if field not in data:
            errors[field] = [trans('This field is required')]

    for inputfield in data:
        if inputfield not in ALL_FIELDS:
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
