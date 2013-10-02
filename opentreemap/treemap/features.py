from django.conf import settings


#
# Load the feature_enabled backend from settings
# the default backend always returns true
#
def _feature_enabled(instance, feature):
    return True

fbf = settings.FEATURE_BACKEND_FUNCTION

if fbf is None:
    feature_enabled = _feature_enabled
else:
    fbf = fbf.split('.')
    modulepath = '.'.join(fbf[:-1])
    fcn = fbf[-1]
    mod = __import__(modulepath, fromlist=[fcn])

    feature_enabled = getattr(mod, fcn)
