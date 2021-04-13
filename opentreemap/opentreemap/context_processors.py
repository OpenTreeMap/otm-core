# -*- coding: utf-8 -*-


import copy
from datetime import datetime

from django.conf import settings
from django.contrib.staticfiles import finders
from django.utils.timezone import now
from django.utils.translation import ugettext as _

from opentreemap.util import request_is_embedded

from treemap.units import Convertible
from treemap.util import get_last_visited_instance, leaf_models_of_class
from treemap.models import InstanceUser


REPLACEABLE_TERMS = {
    'Resource': {'singular': _('Resource'),
                 'plural': _('Resources')}
}


def global_settings(request):
    last_instance = get_last_visited_instance(request)
    if hasattr(request, 'user') and request.user.is_authenticated:
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
        # config.get('terms') above populates the term context variable with
        # model terminology provided it has been customized for the treemap
        # instance, but fails to populate it with the default terminology. The
        # for loop below ensures that term is populated with model terminology
        # whether it has been customized or not.

        # Convertible is the base class where the terminology class property is
        # defined, so its leaf subclasses are the ones with default terminology
        # we might care about.

        # leaf_models_of_class uses recursive descent through the
        # clz.__subclasses__ attributes, but it only iterates through a total
        # of around ten nodes at present, so it is unlikely to be a performance
        # problem.
        for clz in leaf_models_of_class(Convertible):
            term.update({
                clz.__name__: clz.terminology(request.instance)})

    ctx = {
        'SITE_ROOT': settings.SITE_ROOT,
        'settings': settings,
        'last_instance': last_instance,
        'last_effective_instance_user': last_effective_instance_user,
        'logo_url': logo_url,
        'header_comment': header_comment,
        'term': term,
        'embed': request_is_embedded(request),
        'datepicker_start_date': datetime.min.replace(year=1900),
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
