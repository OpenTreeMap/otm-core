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
MIDDLEWARE = ()
RESERVED_INSTANCE_URL_NAMES = ()
INSTALLED_APPS = ()

from opentreemap.settings.default_settings import *  # NOQA

EXTRA_URLS = (
    # Mount extra urls. These should be a
    # tuple of (url path, url module). Something like:
    #
    # ('/extra_api/', 'apiv2.urls),
    # ('/local/', 'local.urls)),
)

EXTRA_APPS = ()
EXTRA_MIDDLEWARE = ()
EXTRA_RESERVED_INSTANCE_URL_NAMES = ()
EXTRA_UI_TESTS = ()

EXTRA_DISPLAY_DEFAULTS = {}
EXTRA_STORAGE_UNITS = {}

from opentreemap.settings.local_settings import *  # NOQA

INSTALLED_APPS = EXTRA_APPS + INSTALLED_APPS
MIDDLEWARE = EXTRA_MIDDLEWARE + MIDDLEWARE
RESERVED_INSTANCE_URL_NAMES += EXTRA_RESERVED_INSTANCE_URL_NAMES

DISPLAY_DEFAULTS.update(EXTRA_DISPLAY_DEFAULTS)
STORAGE_UNITS.update(EXTRA_STORAGE_UNITS)
