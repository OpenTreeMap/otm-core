# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django_tinsel.utils import decorate as do
from django.shortcuts import render
from django.urls import reverse
from django.http import HttpResponse, HttpResponseRedirect
from treemap.decorators import instance_request
from django_tinsel.decorators import render_template
from functools import partial


a = partial(
    do,
    instance_request,
    #creates_instance_user,
    render_template('frontend/index.html')()
)


def get_map_view_context(request, instance):
    # the add tree link goes to this page with the query parameter m for mode
    return {
        "shouldAddTree": request.GET.get('m', '') == 'addTree'
    }

react_map_page = do(
    instance_request,
    #ensure_csrf_cookie,
    render_template('frontend/index.html'),
    get_map_view_context)


def index(request, instance):
    return HttpResponseRedirect(reverse('react_map', kwargs={'instance_url_name': instance.url_name}))


index_page = instance_request(index)
