from django.conf import settings

from treemap.util import get_last_visited_instance


def global_settings(request):
    last_instance = get_last_visited_instance(request)
    if last_instance and last_instance.logo:
        logo_url = last_instance.logo.url
    else:
        logo_url = settings.STATIC_URL + "img/logo-main.svg"

    return {'SITE_ROOT': settings.SITE_ROOT,
            'settings': settings,
            'last_instance': last_instance,
            'logo_url': logo_url}
