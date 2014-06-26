from django.test import TestCase
from django.test.utils import override_settings

_test_settings = {
    # Use a faster password hasher for unit tests to improve performance
    'PASSWORD_HASHERS': ('django.contrib.auth.hashers.MD5PasswordHasher',),

    'STATIC_URL': 'http://localhost:/static/',

    # Test authors shouldn't need to understand when to invalidate caches
    'USE_OBJECT_CACHES': False,
}


@override_settings(**_test_settings)
class OTMTestCase(TestCase):
    """
    Base class for OTM2 tests.
    """
    pass
