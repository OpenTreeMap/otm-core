# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import copy

from django.conf import settings
from django.contrib.staticfiles import finders
from django.utils.timezone import now
from django.utils.translation import ugettext as _

from treemap.util import get_last_visited_instance
from treemap.models import InstanceUser


REPLACEABLE_TERMS = {
    'Resource': {'singular': _('Resource'),
                 'plural': _('Resources')}
}


def global_settings(request):
    last_instance = get_last_visited_instance(request)
    if hasattr(request, 'user') and request.user.is_authenticated():
        last_effective_instance_user =\
            request.user.get_effective_instance_user(last_instance)
        _update_last_seen(last_effective_instance_user)
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
        logo_url = settings.STATIC_URL + "img/logo.png"

    try:
        comment_file_path = finders.find('version.txt')
        with open(comment_file_path, 'r') as f:
            header_comment = f.read()
    except:
        header_comment = "Version information not available\n"

    term = copy.copy(REPLACEABLE_TERMS)
    if hasattr(request, 'instance'):
        term.update(request.instance.config.get('terms', {}))

    ctx = {
        'SITE_ROOT': settings.SITE_ROOT,
        'settings': settings,
        'last_instance': last_instance,
        'last_effective_instance_user': last_effective_instance_user,
        'logo_url': logo_url,
        'header_comment': header_comment,
        'term': term,
    }

    return ctx


def _update_last_seen(last_effective_instance_user):
    # Update the instance user's "last seen" date if necessary.
    # Done here instead of in middleware to avoid looking up
    # the request's InstanceUser again.
    iu = last_effective_instance_user
    today = now().date()
    if iu and iu.id and (not iu.last_seen or iu.last_seen < today):
        iu.last_seen = today
        iu.save_base()
