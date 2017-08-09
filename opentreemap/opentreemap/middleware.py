import re
from django.http import HttpResponseRedirect
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

import logging
logger = logging.getLogger(__name__)

# http://stackoverflow.com/a/30907476
_ie_version_regex = re.compile(r'(MSIE\s+|Trident.*rv[ :])([\d]+)')

CONTENT_TYPE_PASS_THROUGHS = ('application/json', 'text/csv')

REQUIRED_SETTINGS = ('IE_VERSION_MINIMUM',
                     'IE_VERSION_UNSUPPORTED_REDIRECT_PATH')
REQUIRED_SETTING_MSG = ('InternetExplorerRedirectMiddleware is loaded '
                        'but %s was not found in settings.')

REQUIRED_PARAMETERS = ('HTTP_USER_AGENT', 'PATH_INFO')
REQUIRED_PARAMETER_MSG = 'The request did not include %s'


# Reference: http://djangosnippets.org/snippets/510/
# Reference: http://djangosnippets.org/snippets/1147/
class InternetExplorerRedirectMiddleware(MiddlewareMixin):
    """
    Sets `from_ie` and `ie_version` on the request. If the `ie_version` is
    less than `settings.IE_VERSION_MINIMUM` the response redirects to
    `settings.IE_VERSION_UNSUPPORTED_REDIRECT_PATH`
    """

    def _parse_major_ie_version_from_user_agent(self, user_agent):
        search_result = _ie_version_regex.search(user_agent)
        if search_result:
            return int(search_result.groups()[1])
        else:
            return None

    def process_request(self, request):

        for value in CONTENT_TYPE_PASS_THROUGHS:
            if request.META.get('HTTP_ACCEPT', '').find(value) != -1:
                return None

        required_setting_msgs = [REQUIRED_SETTING_MSG % setting
                                 for setting in REQUIRED_SETTINGS
                                 if not hasattr(settings, setting)]

        required_parameter_msgs = [REQUIRED_PARAMETER_MSG % parameter
                                   for parameter in REQUIRED_PARAMETERS
                                   if parameter not in request.META]

        validation_msgs = required_setting_msgs + required_parameter_msgs

        if validation_msgs:
            for msg in validation_msgs:
                logger.warning(msg)
            return None

        request.ie_version = self._parse_major_ie_version_from_user_agent(
            request.META['HTTP_USER_AGENT'])
        if request.ie_version is not None:
            request.from_ie = True
            if request.ie_version < settings.IE_VERSION_MINIMUM:
                path = request.META['PATH_INFO']
                redirect_path = settings.IE_VERSION_UNSUPPORTED_REDIRECT_PATH
                if path != redirect_path:
                    return HttpResponseRedirect(redirect_path)
        else:
            request.from_ie = False
