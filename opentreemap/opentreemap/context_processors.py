# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf import settings
from django.contrib.staticfiles import finders
from django.utils.translation import ugettext as trans

from treemap.util import get_last_visited_instance
from treemap.models import InstanceUser


def global_settings(request):
    last_instance = get_last_visited_instance(request)
    if hasattr(request, 'user') and request.user.is_authenticated():
        last_effective_instance_user =\
            request.user.get_effective_instance_user(last_instance)
    else:
        if hasattr(request, 'instance'):
            instance = request.instance
            default_role = instance.default_role

            last_effective_instance_user = InstanceUser(
                role=default_role, instance=instance)
        else:
            last_effective_instance_user = None

    if hasattr(request, 'instance') and request.instance.logo:
        logo_url = request.instance.logo.url
    else:
        logo_url = settings.STATIC_URL + "img/logo-beta.png"

    try:
        comment_file_path = finders.find('version.txt')
        with open(comment_file_path, 'r') as f:
            header_comment = f.read()
    except:
        header_comment = "Version information not available\n"

    ctx = {
        'SITE_ROOT': settings.SITE_ROOT,
        'settings': settings,
        'last_instance': last_instance,
        'last_effective_instance_user': last_effective_instance_user,
        'logo_url': logo_url,
        'header_comment': header_comment,
        'term': _get_terms(request)
    }

    return ctx


REPLACEABLE_TERMS = {
    'Resource': trans('Resource'),
    'Resources': trans('Resources'),
    }


def _get_terms(request):
    terms = {}
    if hasattr(request, 'instance'):
        config = request.instance.config
        for term, translation in REPLACEABLE_TERMS.iteritems():
            replacement = config.get('terms.' + term, translation)
            terms[term] = replacement
            terms[term.lower()] = replacement.lower()
    return terms
