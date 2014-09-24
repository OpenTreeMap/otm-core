# The purpose of this package is to provide fine-grained control
# over how settings are initialized and overridden
#
# file summary
# * ./__init__.py         - the canonical place to manage importing settings
# * ./default_settings.py - the canonical place to add new settings
# * ./local_settings.py   - the canonical place to override settings
#
# WARNING: !!! DO NOT ADD SETTINGS TO THIS FILE !!!
# WARNING: !!! USE THIS FILE EXCLUSIVELY TO MANAGE SETTING IMPORTS !!!

STORAGE_UNITS = {}
DISPLAY_DEFAULTS = {}
MIDDLEWARE_CLASSES = ()
RESERVED_INSTANCE_URL_NAMES = ()
MANAGED_APPS = ()
UNMANAGED_APPS = ()

from opentreemap.settings.default_settings import *  # NOQA

EXTRA_URLS = (
    # Mount extra urls. These should be a
    # tuple of (url path, url module). Something like:
    #
    # ('/extra_api/', 'apiv2.urls),
    # ('/local/', 'local.urls)),
)

EXTRA_MANAGED_APPS = ()
EXTRA_UNMANAGED_APPS = ()
EXTRA_MIDDLEWARE_CLASSES = ()
EXTRA_RESERVED_INSTANCE_URL_NAMES = ()
EXTRA_UI_TESTS = ()

EXTRA_DISPLAY_DEFAULTS = {}
EXTRA_STORAGE_UNITS = {}

from opentreemap.settings.local_settings import *  # NOQA

MANAGED_APPS = EXTRA_MANAGED_APPS + MANAGED_APPS
UNMANAGED_APPS = EXTRA_UNMANAGED_APPS + UNMANAGED_APPS
INSTALLED_APPS = MANAGED_APPS + UNMANAGED_APPS
MIDDLEWARE_CLASSES += EXTRA_MIDDLEWARE_CLASSES
RESERVED_INSTANCE_URL_NAMES += EXTRA_RESERVED_INSTANCE_URL_NAMES

DISPLAY_DEFAULTS.update(EXTRA_DISPLAY_DEFAULTS)
STORAGE_UNITS.update(EXTRA_STORAGE_UNITS)

# CELERY
# NOTE: BROKER_URL and CELERY_RESULT_BACKEND must be set
#       to a valid redis URL in local_settings.py
import djcelery
djcelery.setup_loader()
