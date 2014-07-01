# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
from functools import wraps
from io import BytesIO

from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as trans

from registration.models import RegistrationProfile

from treemap.views import upload_user_photo
from treemap.models import User


REQ_FIELDS = {'email', 'username', 'password'}
ALL_FIELDS = REQ_FIELDS | {'organization', 'last_name', 'first_name',
                           'allow_email_contact', 'make_info_public'}


def update_profile_photo(request, user_id):
    user = get_object_or_404(User, pk=user_id)

    if user.pk != request.user.pk:
        return HttpResponseForbidden()

    return upload_user_photo(request, user)


def _context_dict_for_user(user):
    user_dict = user.as_dict()

    del user_dict['password']
    user_dict["status"] = "success"

    return user_dict


def user_info(request):
    return _context_dict_for_user(request.user)


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

    return _context_dict_for_user(user)


def create_user(request):
    data = json.loads(request.body)

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
        # BE WARNED - The iOS application relies on this error message string.
        # If you change this you WILL NEED TO ALTER CODE THERE AS WELL.
        return _conflict_response(trans('Email is already in use'))

    user = User(**data)

    # Needed to properly hash the password
    user.set_password(data['password'])
    user.active = True
    user.save()

    RegistrationProfile.objects.create_profile(user)

    return {'status': 'success', 'id': user.pk}


def transform_user_request(user_view_fn):
    """
    There was an issue with User first/last name fields being duplicated

    The issue was fixed in 3d2e95390c, but needs to be supported for API < 3
    """
    @wraps(user_view_fn)
    def wrapper(request, *args, **kwargs):
        if request.api_version < 3:
            body_dict = json.loads(request.body)

            if 'firstname' in body_dict:
                body_dict['first_name'] = body_dict.get('firstname', '')
                del body_dict['firstname']

            if 'lastname' in body_dict:
                body_dict['last_name'] = body_dict.get('lastname', '')
                del body_dict['lastname']

            body = json.dumps(body_dict)
            # You can't directly set a new request body
            # (http://stackoverflow.com/a/22745559)
            request._body = body
            request._stream = BytesIO(body)

        return user_view_fn(request, *args, **kwargs)

    return wrapper


def transform_user_response(user_view_fn):
    """
    There was an issue with User first/last name fields being duplicated

    The issue was fixed in 3d2e95390c, but needs to be supported for API < 3
    """
    @wraps(user_view_fn)
    def wrapper(request, *args, **kwargs):
        user_dict = user_view_fn(request, *args, **kwargs)

        if request.api_version < 3:
            user_dict['firstname'] = user_dict['first_name']
            user_dict['lastname'] = user_dict['last_name']

        return user_dict

    return wrapper
