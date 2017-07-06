import urlparse

from django import template
from django.http.request import QueryDict
from django.utils.encoding import iri_to_uri

register = template.Library()


class UrlHelper(object):
    def __init__(self, full_path):
        url = urlparse.urlparse(full_path)
        self.path = url.path
        self.fragment = url.fragment
        self.query_dict = QueryDict(url.query, mutable=True)

    def update_query_data(self, **kwargs):
        for key, val in kwargs.iteritems():
            if hasattr(val, '__iter__'):
                self.query_dict.setlist(key, val)
            else:
                self.query_dict[key] = val

    def get_full_path(self, **kwargs):
        query_string = self.get_query_string(**kwargs)
        if query_string:
            query_string = '?' + query_string
        fragment = self.fragment and '#' + iri_to_uri(self.fragment) or ''

        return iri_to_uri(self.path) + query_string + fragment

    def get_query_string(self, **kwargs):
        return self.query_dict.urlencode(**kwargs)


@register.simple_tag
def add_params(url, **kwargs):
    url = UrlHelper(url)
    url.update_query_data(**kwargs)
    return url.get_full_path()
