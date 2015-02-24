# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import collections

from django.core.exceptions import ValidationError
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import ugettext as trans
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect

from opentreemap.util import json_from_request, dotted_split

from treemap.decorators import get_instance_or_404
from treemap.images import save_image_from_request
from treemap.util import package_field_errors
from treemap.models import User, Favorite
from treemap.util import get_filterable_audit_models
from treemap.lib.user import get_audits, get_user_instances, get_audits_params
from treemap.lib.map_feature import title_for_map_feature

USER_PROFILE_FIELDS = collections.OrderedDict([
    ('first_name',
     {'label': trans('First Name'),
      'identifier': 'user.first_name',
      'visibility': 'public'}),
    ('last_name',
     {'label': trans('Last Name'),
      'identifier': 'user.last_name',
      'visibility': 'public'}),
    ('organization',
     {'label': trans('Organization'),
      'identifier': 'user.organization',
      'visibility': 'public'}),
    ('make_info_public',
     {'label': trans('Make Info Visible'),
      'identifier': 'user.make_info_public',
      'visibility': 'private',
      'template': "treemap/field/make_info_public_div.html"}),
    ('email',
     {'label': trans('Email'),
      'identifier': 'user.email',
      'visibility': 'private'}),
    ('allow_email_contact',
     {'label': trans('Email Updates'),
      'identifier': 'user.allow_email_contact',
      'visibility': 'private',
      'template': "treemap/field/email_subscription_div.html"})
])


def user_audits(request, username):
    user = get_object_or_404(User, username=username)
    instance_id = request.GET.get('instance_id', None)

    instance = (get_instance_or_404(pk=instance_id)
                if instance_id else None)

    (page, page_size, models, model_id,
     exclude_pending) = get_audits_params(request)

    return get_audits(request.user, instance, request.REQUEST, user,
                      models, model_id, page, page_size, exclude_pending)


def instance_user_audits(request, instance_url_name, username):
    instance = get_instance_or_404(url_name=instance_url_name)
    return HttpResponseRedirect(
        reverse('user_audits', kwargs={'username': username})
        + '?instance_id=%s' % instance.pk)


def update_user(request, user):
    new_values = json_from_request(request) or {}
    for key in new_values:
        try:
            model, field = dotted_split(key, 2, cls=ValueError)
            if model != 'user':
                raise ValidationError(
                    'All fields should be prefixed with "user."')
            if field not in USER_PROFILE_FIELDS:
                raise ValidationError(field + ' is not an updatable field')
        except ValueError:
            raise ValidationError('All fields should be prefixed with "user."')
        setattr(user, field, new_values[key])
    try:
        user.save()
        return {"ok": True}
    except ValidationError as ve:
        raise ValidationError(package_field_errors('user', ve))


def upload_user_photo(request, user):
    """
    Saves a user profile photo whose data is in the request.
    The callee or decorator is reponsible for ensuring request.user == user
    """
    user.photo, user.thumbnail = save_image_from_request(
        request, name_prefix="user-%s" % user.pk, thumb_size=(85, 85))
    user.save_with_user(request.user)

    return {'url': user.thumbnail.url}


def instance_user(request, instance_url_name, username):
    instance = get_instance_or_404(url_name=instance_url_name)
    url = reverse('user', kwargs={'username': username}) +\
        '?instance_id=%s' % instance.pk
    return HttpResponseRedirect(url)


def profile_to_user(request):
    if request.user and request.user.username:
        return HttpResponseRedirect('/users/%s/' % request.user.username)
    else:
        return HttpResponseRedirect(settings.LOGIN_URL)


def forgot_username(request):
    user_email = request.REQUEST['email']
    if not user_email:
        raise ValidationError({
            'user.email': [trans('Email field is required')]
        })

    users = User.objects.filter(email=user_email)

    # Don't reveal if we don't have that email, to prevent email harvesting
    if len(users) == 1:
        user = users[0]

        password_reset_url = request.build_absolute_uri(
            reverse('auth_password_reset'))

        subject = trans('Account Recovery')
        body = render_to_string('treemap/partials/forgot_username_email.txt',
                                {'user': user,
                                 'password_url': password_reset_url})

        user.email_user(subject, body, settings.DEFAULT_FROM_EMAIL)

    return {'email': user_email}


def _small_feature_photo_url(feature):
    if hasattr(feature, 'photos'):
        photos = feature.photos()
        if len(photos) > 0:
            return settings.MEDIA_URL + str(photos[0].thumbnail)
        else:
            return None
    else:
        return None


def user(request, username):
    user = get_object_or_404(User, username=username)
    instance_id = request.GET.get('instance_id', None)

    instance = (get_instance_or_404(pk=instance_id)
                if instance_id else None)

    query_vars = {'instance_id': instance_id} if instance_id else {}

    models = get_filterable_audit_models().values()
    audit_dict = get_audits(request.user, instance, query_vars,
                            user, models, 0, should_count=True)

    reputation = user.get_reputation(instance) if instance else None

    favorites_qs = Favorite.objects.filter(user=user).order_by('-created')
    favorites = [{
        'map_feature': f.map_feature,
        'title': title_for_map_feature(f.map_feature),
        'instance': f.map_feature.instance,
        'address': f.map_feature.address_full,
        'photo': _small_feature_photo_url(f.map_feature)
    } for f in favorites_qs]

    public_fields = []
    private_fields = []

    for field in USER_PROFILE_FIELDS.values():
        field_tuple = (field['label'], field['identifier'],
                       field.get('template', "treemap/field/div.html"))
        if field['visibility'] == 'public' and user.make_info_public is True:
            public_fields.append(field_tuple)
        else:
            private_fields.append(field_tuple)

    return {'user': user,
            'reputation': reputation,
            'instance_id': instance_id,
            'instances': get_user_instances(request.user, user, instance),
            'total_edits': audit_dict['total_count'],
            'audits': audit_dict['audits'],
            'next_page': audit_dict['next_page'],
            'public_fields': public_fields,
            'private_fields': private_fields,
            'favorites': favorites}
