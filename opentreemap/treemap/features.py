from django.conf import settings
from django.test.signals import setting_changed


#
# Load the feature_enabled backend from settings
# the default backend always returns true
#
def _feature_enabled_impl(instance, feature):
    return True

_feature_enabled = None


def _resolve_feature_function():
    fbf = settings.FEATURE_BACKEND_FUNCTION

    if fbf is None:
        feature_enabled = _feature_enabled_impl
    else:
        fbf = fbf.split('.')
        modulepath = '.'.join(fbf[:-1])
        fcn = fbf[-1]
        mod = __import__(modulepath, fromlist=[fcn])

        feature_enabled = getattr(mod, fcn)

    return feature_enabled


def feature_enabled(instance, feature):
    # Cache the function
    global _feature_enabled

    if _feature_enabled is None:
        _feature_enabled = _resolve_feature_function()

    return _feature_enabled(instance, feature)


def _reset_feature_fn(sender, setting, value, **kwargs):
    global _feature_enabled

    if setting == 'FEATURE_BACKEND_FUNCTION':
        _feature_enabled = None

setting_changed.connect(_reset_feature_fn)
