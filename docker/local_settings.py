EXTRA_UNMANAGED_APPS = ('django_extensions',)

STATIC_ROOT = '/usr/local/otm/static'
MEDIA_ROOT = '/usr/local/otm/media'

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'otm',
        'USER': 'otm',
        'PASSWORD': 'otm',
        'HOST': 'database',
        'PORT': '5432'
    }
}

CELERY_BROKER_URL = 'redis://redis:6379/'
CELERY_RESULT_BACKEND = 'redis://redis:6379/'

EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = '/usr/local/otm/emails'

ECO_SERVICE_URL = 'http://otm-ecoservice:13000'
