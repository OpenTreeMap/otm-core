import os

# Django settings for opentreemap project.
OTM_VERSION = 'dev'
API_VERSION = 'v0.1'

FEATURE_BACKEND_FUNCTION = None
USER_ACTIVATION_FUNCTION = None

UITEST_CREATE_INSTANCE_FUNCTION = 'treemap.tests.make_instance'
UITEST_SETUP_FUNCTION = None

# This email is shown in various contact/error pages
# throughout the site
SUPPORT_EMAIL_ADDRESS = 'support@yoursite.com'
SYSTEM_USER_ID = -1

#
# URL to access eco benefit service
#
ECO_SERVICE_URL = 'http://localhost:13000'

# This should be the google analytics id without
# the 'GTM-' prefix
GOOGLE_ANALYTICS_ID = None

# Tree Key URL to use for help links of an instance doesn't provide
# one
DEFAULT_TREE_KEY_URL = 'http://www.arborday.org/trees/whatTree/'

# Storage backend config
# Uncomment the following to enable S3-backed storage:
# DEFAULT_FILE_STORAGE = 'storages.backends.s3boto.S3BotoStorage'
# AWS_ACCESS_KEY_ID = '...'
# AWS_SECRET_ACCESS_KEY = '...'
# AWS_STORAGE_BUCKET_NAME = '...'
AWS_HEADERS = {
    'Cache-Control': 'max-age=86400',
}

# Size is in bytes
MAXIMUM_IMAGE_SIZE = 20971520  # 20mb

# API distance check, in meters
MAP_CLICK_RADIUS = 100
# API instance distance default, in meters
NEARBY_INSTANCE_RADIUS = 100000

# Default nearby tree distance in meters
NEARBY_TREE_DISTANCE = 6.096  # 20ft

DEBUG = True
TEMPLATE_DEBUG = True
AUTH_USER_MODEL = 'treemap.User'
INTERNAL_IPS = ['127.0.0.1']

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

TEST_RUNNER = "treemap.tests.OTM2TestRunner"

OMGEO_SETTINGS = [[
    'omgeo.services.EsriWGS', {}
]]

# Set TILE_HOST to None if the tiler is running on the same host
# as this app. Otherwise, provide a Leaflet url template as described
# at http://leafletjs.com/reference.html#url-template
#
# Tile hosts must be serving tiles on a 'tile' endpoint
#
#   //host/tile/
#
TILE_HOST = None

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = 'America/Chicago'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Setting this to False will remove the jsi18n url configuration
USE_JS_I18N = False

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True
USE_THOUSAND_SEPARATOR = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Path to the Django Project root
# Current file is in opentreemap/opentreemap/settings, so go up 3
PROJECT_ROOT = os.path.abspath(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Path to the location of SCSS files, used for on-the-fly compilation to CSS
SCSS_ROOT = os.path.join(PROJECT_ROOT, 'treemap', 'css', 'sass')

# Entry point .scss file for on-the-fly compilation to CSS
SCSS_ENTRY = 'main'

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/var/www/example.com/media/"
MEDIA_ROOT = '/usr/local/otm/media'

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://example.com/media/", "http://media.example.com/"

# TODO: Media serving via ansible
MEDIA_URL = '/media/'

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/var/www/example.com/static/"
STATIC_ROOT = ''

# URL prefix for static files.
# Example: "http://example.com/static/", "http://static.example.com/"
STATIC_URL = '/static/'

# Root URL for the application
SITE_ROOT = '/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    # 'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'secret key'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    #'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    'apptemplates.Loader'
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'opentreemap.middleware.InternetExplorerRedirectMiddleware',
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'opentreemap.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'opentreemap.wsgi.application'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or
    # "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.static',
    'django.core.context_processors.tz',
    'django.contrib.messages.context_processors.messages',
    'django.core.context_processors.request',
    'opentreemap.context_processors.global_settings',
)

COMMENTS_APP = 'otm_comments'

# Necessary to prevent the underlying `django_comments` app
# from hiding all comments with `is_removed` set to true.
# We want to show these comments, with details masked to
# indicate that they were "hidden" by a moderator.
COMMENTS_HIDE_REMOVED = False


# APPS THAT ARE DEVELOPED IN CONJUNCTION WITH OTM2
# these are the apps we want to test by default using
# 'python manage.py test'
MANAGED_APPS = (
    'treemap',
    'geocode',
    'api',
    'exporter',
    'otm1_migrator',
    'otm_comments',
    'importer',
    'appevents',
    'stormwater',
)

UNMANAGED_APPS = (
    'threadedcomments',
    'django.contrib.comments',
    'registration',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'django.contrib.gis',
    'django.contrib.humanize',
    'django_hstore',
    'djcelery',
    'south',
)

I18N_APPS = (
    'treemap',
)

RESERVED_INSTANCE_URL_NAMES = (
    'geocode',
    'config',
    'users',
    'api',
    'accounts',
    'i18n',
    'not-available',
    'unsupported',
    'jsi18n',
    'admin'
)

# From the django-registration quickstart
# https://django-registration.readthedocs.org/en/latest/quickstart.html
#
# ACCOUNT_ACTIVATION_DAYS is the number of days users will have to activate
# their accounts after registering. If a user does not activate within
# that period, the account will remain permanently inactive and
# may be deleted by maintenance scripts provided in django-registration.
ACCOUNT_ACTIVATION_DAYS = 7

#
# Units and decimal digits for fields and eco values
#
# DISPLAY_DEFAULTS has the default unit to show in the UI
# STORAGE_UNITS is the unit the value will be stored/computed as,
# if different from DISPLAY_DEFAULTS
#
STORAGE_UNITS = {}
DISPLAY_DEFAULTS = {
    'plot': {
        'width':  {'units': 'in', 'digits': 1},
        'length': {'units': 'in', 'digits': 1},
    },
    'tree': {
        'diameter':      {'units': 'in', 'digits': 1},
        'height':        {'units': 'ft', 'digits': 1},
        'canopy_height': {'units': 'ft', 'digits': 1}
    },
    'eco': {
        'energy':     {'units': 'kwh/year', 'digits': 1},
        'stormwater': {'units': 'gal/year', 'digits': 1},
        'co2':        {'units': 'lbs/year', 'digits': 1},
        'co2storage': {'units': 'lbs', 'digits': 1},
        'airquality': {'units': 'lbs/year', 'digits': 1}
    }
}

# Time in ms for two clicks to be considered a double-click in some scenarios
DOUBLE_CLICK_INTERVAL = 300

# We have... issues on IE9 right now
# Disable it on production, but enable it in Debug mode
IE_VERSION_MINIMUM = 9 if DEBUG else 10

IE_VERSION_UNSUPPORTED_REDIRECT_PATH = '/unsupported'

USE_OBJECT_CACHES = True

BING_API_KEY = None
