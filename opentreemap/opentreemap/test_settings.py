from opentreemap.settings import *  # NOQA

# Use a faster password hasher for unit tests
# to improve performance
PASSWORD_HASHERS = (
    'django.contrib.auth.hashers.MD5PasswordHasher',
)

STATIC_URL = 'http://localhost:/static/'

# For session management use file backend instead of DB, to reduce extraneous
# transactions which can cause deadlock when UI test tearDown() truncates all
# tables.
SESSION_ENGINE = "django.contrib.sessions.backends.file"
