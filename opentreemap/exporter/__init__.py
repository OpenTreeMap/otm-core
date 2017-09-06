from django.utils.translation import ugettext_lazy as _


EXPORTS_NOT_ENABLED_CONTEXT = {
    'start_status': 'ERROR',
    'message': _('Data exports are not enabled for this user.')
}


EXPORTS_FEATURE_DISABLED_CONTEXT = {
    'start_status': 'ERROR',
    'message': _('Data exports are not enabled for trial maps.')
}
