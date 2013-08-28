import re
from django.http import HttpResponseRedirect
from django.conf import settings

import logging
logger = logging.getLogger(__name__)

_ie_version_regex = re.compile(r'MSIE\s+([\d]+)')


# Reference: http://djangosnippets.org/snippets/510/
# Reference: http://djangosnippets.org/snippets/1147/
class InternetExplorerRedirectMiddleware:
    """
    Sets `from_ie` and `ie_version` on the request. If the `ie_version` is
    less than `settings.IE_VERSION_MINIMUM` the response redirects to
    `settings.IE_VERSION_UNSUPPORTED_REDIRECT_PATH`
    """

    def _parse_major_ie_version_from_user_agent(self, user_agent):
        search_result = _ie_version_regex.search(user_agent)
        if search_result:
            return int(search_result.groups()[0])
        else:
            return None

    def process_request(self, request):
        if not hasattr(settings, 'IE_VERSION_MINIMUM'):
            logger.warning('InternetExplorerRedirectMiddleware is loaded '
                           'but IE_VERSION_MINIMUM was not found in settings.')
            return None

        if not hasattr(settings, 'IE_VERSION_UNSUPPORTED_REDIRECT_PATH'):
            logger.warning('InternetExplorerRedirectMiddleware is loaded '
                           'but IE_VERSION_UNSUPPORTED_REDIRECT_PATH was '
                           'not found in settings.')
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
