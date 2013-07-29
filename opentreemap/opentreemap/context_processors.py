from django.conf import settings


def global_settings(request):
    return {'SITE_ROOT':  settings.SITE_ROOT}
