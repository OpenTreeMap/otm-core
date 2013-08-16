from django.conf import settings

from treemap.util import get_last_visited_instance


def global_settings(request):
    return {'SITE_ROOT':  settings.SITE_ROOT,
            'last_instance': get_last_visited_instance(request)}
