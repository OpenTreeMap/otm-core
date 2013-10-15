from django.conf import settings

from treemap.util import get_last_visited_instance


def global_settings(request):
    last_instance = get_last_visited_instance(request)
    if last_instance and last_instance.logo:
        logo_url = last_instance.logo.url
    else:
        logo_url = settings.STATIC_URL + "img/logo-beta.png"

    ctx = {'SITE_ROOT': settings.SITE_ROOT,
           'settings': settings,
           'last_instance': last_instance,
           'logo_url': logo_url}

    if hasattr(request, 'instance') and request.user.is_authenticated():
        ctx['instance_user'] = request.user.get_instance_user(request.instance)

    return ctx
