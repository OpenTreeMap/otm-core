from opentreemap.settings import *  # NOQA

# Use a faster password hasher for unit tests
# to improve performance
PASSWORD_HASHERS = (
    'django.contrib.auth.hashers.MD5PasswordHasher',
)

STATIC_URL = 'http://localhost:/static/'
