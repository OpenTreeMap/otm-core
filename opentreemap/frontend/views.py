# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import collections
from functools import partial

from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.http.request import QueryDict
from django_tinsel.decorators import route, render_template, username_matches_request_user
from django_tinsel.utils import decorate as do
from django.shortcuts import render, get_object_or_404
from django.utils.translation import ugettext as _
from django.urls import reverse

from treemap.decorators import get_instance_or_404, instance_request, login_or_401
from treemap.lib.user import get_audits, get_user_instances, get_audits_params
from treemap.models import User


def get_map_view_context(request, instance):
    # the add tree link goes to this page with the query parameter m for mode
    return {
        "shouldAddTree": request.GET.get('m', '') == 'addTree',
        "googleApiKey": settings.GOOGLE_MAPS_API_KEY
    }


def index(request, instance):
    return HttpResponseRedirect(reverse('react_map', kwargs={'instance_url_name': instance.url_name}))


index_page = instance_request(index)


def user_info(request, instance):
    user = request.user
    instance_id = request.GET.get('instance_id', None)

    instance = (get_instance_or_404(pk=instance_id)
                if instance_id else None)

    query_vars = QueryDict(mutable=True)
    if instance_id:
        query_vars['instance_id'] = instance_id

    audit_dict = get_audits(request.user, instance, query_vars,
                            user=user, should_count=True)

    reputation = user.get_reputation(instance) if instance else None

    public_fields = []
    private_fields = []

    return {'user': user,
            'its_me': user.id == request.user.id,
            'reputation': reputation,
            'instance_id': instance_id,
            'instances': get_user_instances(request.user, user, instance),
            'total_edits': audit_dict['total_count'],
            'audits': audit_dict['audits'],
    }


########
# Move this to a routes file
########
react_map_page = do(
    instance_request,
    #ensure_csrf_cookie,
    render_template('frontend/index.html'),
    get_map_view_context)


#user = route(
#    GET=do(
#        #username_matches_request_user,
#        render_template('treemap/user.html'),
#        user_info)
#    )

user_dashboard = route(
    GET=do(
        instance_request,
        #username_matches_request_user,
        login_or_401,
        render_template('frontend/account_dashboard.html'),
        user_info)
    )
