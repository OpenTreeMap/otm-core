from django.utils.translation import ugettext_lazy as trans


EXPORTS_NOT_ENABLED_CONTEXT = {
    'start_status': 'ERROR',
    'message': trans('Data exports are not enabled.')
}
