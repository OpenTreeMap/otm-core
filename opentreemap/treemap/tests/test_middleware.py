# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf import settings
from django.http import HttpResponseRedirect
from opentreemap.middleware import InternetExplorerRedirectMiddleware
from treemap.tests.base import OTMTestCase


class USER_AGENT_STRINGS:
    IE_6 = 'Mozilla/5.0 (compatible; MSIE 6.0; Windows NT 5.1)'
    IE_7 = 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)'
    IE_8 = 'Mozilla/5.0 (compatible; MSIE 8.0; Windows NT 6.0)'
    IE_9 = 'Mozilla/5.0 (Windows; U; MSIE 9.0; Windows NT 9.0)'
    IE_10 = 'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; Trident/6.0)'
    IE_11 = 'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; AS; rv:11.0)'
    FIREFOX_22 = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; ' +\
                 'rv:22.0) Gecko/20130328 Firefox/22.0'


class MockRequest():
    def __init__(self, http_user_agent=None, path_info='/', other_params=None):
        self.META = {
            'HTTP_USER_AGENT': http_user_agent,
            'PATH_INFO': path_info
        }
        if other_params:
            for k, v in other_params.items():
                self.META[k] = v


class InternetExplorerRedirectMiddlewareTests(OTMTestCase):

    def _request_with_agent(self, *args, **kwargs):
        req = MockRequest(*args, **kwargs)
        res = InternetExplorerRedirectMiddleware().process_request(req)
        return req, res

    def _assert_redirects(self, response, expected_url):
        self.assertTrue(isinstance(response, HttpResponseRedirect))
        self.assertEquals(expected_url, response["Location"])

    def test_detects_ie(self):
        req, __ = self._request_with_agent(USER_AGENT_STRINGS.IE_7)
        self.assertTrue(req.from_ie,
                        'Expected the middleware to set "from_ie" '
                        'to True for an IE connection string')

    def test_does_not_detect_ie(self):
        req, __ = self._request_with_agent(USER_AGENT_STRINGS.FIREFOX_22)
        self.assertFalse(req.from_ie,
                         'Expected the middleware to set "from_ie" '
                         'to False for a Firefox user agent string')
        self.assertIsNone(req.ie_version,
                          'Expected the middleware to set "ie_version" '
                          'to None')

    def test_sets_version_and_does_not_redirect_for_ie_11(self):
        req, res = self._request_with_agent(USER_AGENT_STRINGS.IE_11)
        self.assertIsNone(res, 'Expected the middleware to return a None '
                          'response (no redirect) for IE 11')
        self.assertEquals(11, req.ie_version, 'Expected the middleware to '
                          'set "ie_version" to 11')

    def test_sets_version_and_redirects_ie_10(self):
        req, res = self._request_with_agent(USER_AGENT_STRINGS.IE_10)
        self._assert_redirects(res,
                               settings.IE_VERSION_UNSUPPORTED_REDIRECT_PATH)
        self.assertEquals(10, req.ie_version, 'Expected the middleware to set '
                          '"ie_version" to 10')

    def test_sets_version_and_redirects_ie_9(self):
        req, res = self._request_with_agent(USER_AGENT_STRINGS.IE_9)
        self._assert_redirects(res,
                               settings.IE_VERSION_UNSUPPORTED_REDIRECT_PATH)
        self.assertEquals(9, req.ie_version, 'Expected the middleware to set '
                          '"ie_version" to 9')

    def test_sets_version_and_redirects_ie_8(self):
        req, res = self._request_with_agent(USER_AGENT_STRINGS.IE_8)
        self._assert_redirects(res,
                               settings.IE_VERSION_UNSUPPORTED_REDIRECT_PATH)
        self.assertEquals(8, req.ie_version, 'Expected the middleware to set '
                          '"ie_version" to 8')

    def test_sets_version_and_redirects_ie_7(self):
        req, res = self._request_with_agent(USER_AGENT_STRINGS.IE_7)
        self._assert_redirects(res,
                               settings.IE_VERSION_UNSUPPORTED_REDIRECT_PATH)
        self.assertEquals(7, req.ie_version, 'Expected the middleware to set '
                          '"ie_version" to 7')

    def test_sets_version_and_redirects_ie_6(self):
        req, res = self._request_with_agent(USER_AGENT_STRINGS.IE_6)
        self._assert_redirects(res,
                               settings.IE_VERSION_UNSUPPORTED_REDIRECT_PATH)
        self.assertEquals(6, req.ie_version, 'Expected the middleware to set '
                          '"ie_version" to 6')

    def test_detects_json_and_does_not_redirect(self):
        params = {'HTTP_ACCEPT': 'application/json;q=0.9,*/*;q=0.8'}
        # normally, ie 8 would redirect
        req, res = self._request_with_agent(USER_AGENT_STRINGS.IE_8,
                                            other_params=params)
        self.assertIsNone(res, 'Expected middleware to return None for JSON')
