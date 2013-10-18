from django.conf import settings

from treemap.util import get_last_visited_instance


def global_settings(request):
    last_instance = get_last_visited_instance(request)
    last_effective_instance_user = request.user.get_effective_instance_user(
        last_instance)
    if hasattr(request, 'instance') and request.instance.logo:
        logo_url = request.instance.logo.url
    else:
        logo_url = settings.STATIC_URL + "img/logo-beta.png"

    ctx = {'SITE_ROOT': settings.SITE_ROOT,
           'settings': settings,
           'last_instance': last_instance,
           'last_effective_instance_user': last_effective_instance_user,
           'logo_url': logo_url}

    return ctx
