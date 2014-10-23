# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf import settings
from django.db.models import Q
from django.test.signals import setting_changed
from django.dispatch import receiver

from treemap.lib import get_function_by_path

#
# Plugin functions allow python modules which are not part of the OTM2 core the
# the ability to override select functionality.
#
# For instance, feature_enabled is called in certain locations in OTM2 before
# showing a feature.  It's default implementation always returns True to enable
# the feature, but an outside python module can override this to selectively
# disable certain unwanted features.
#

_plugin_fn_dict = {}
_plugin_setting_dict = {}


def get_plugin_function(plugin_fn_setting, default_fn):
    """
    Gets a plugin function from an external python module, and wraps it
    so that it can be safely overridden for testing purposes.

    Implementors of plugin functions should ensure that their function's
    signature matches that of the default_fn

    plugin_fn_setting - A string in the Django settings specifiying the
                        module and function path
    default_fn - The function to call if plugin_fn_setting is not set
    """
    # cache the function
    _plugin_fn_dict[plugin_fn_setting] =\
        _resolve_plugin_function(plugin_fn_setting, default_fn)

    def wrapper(*args, **kwargs):
        plugin_fn = _plugin_fn_dict.get(plugin_fn_setting)
        if plugin_fn is None:
            plugin_fn = _resolve_plugin_function(plugin_fn_setting, default_fn)
            _plugin_fn_dict[plugin_fn_setting] = plugin_fn

        return plugin_fn(*args, **kwargs)

    return wrapper


def _resolve_plugin_function(fn_setting, default_fn):
    fn_path = getattr(settings, fn_setting, None)

    if fn_path is None:
        return default_fn

    return get_function_by_path(fn_path)


# Needed to support use of @override_settings in unit tests
@receiver(setting_changed)
def reset(sender, setting, value, **kwargs):
    if setting in _plugin_fn_dict:
        _plugin_fn_dict[setting] = None


feature_enabled = get_plugin_function('FEATURE_BACKEND_FUNCTION',
                                      lambda instance, feature: True)


# Should return True if an activation email should be sent on user creation
should_send_user_activation = get_plugin_function(
    'USER_ACTIVATION_FUNCTION',
    lambda request, username, email, password: True)


setup_for_ui_test = get_plugin_function('UITEST_SETUP_FUNCTION', lambda: None)


get_mobile_instances_filter = get_plugin_function('MOBILE_INSTANCES_FUNCTION',
                                                  lambda: Q())
