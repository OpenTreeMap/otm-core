# -*- coding: utf-8 -*-


from django.urls import reverse


class UrlParams(object):
    def __init__(self, url_name, *url_args, **params):
        self._url = reverse(url_name, args=url_args) + '?'
        self._params = params

    def params(self, *keys):
        return self._param_string(keys, self._params)

    def url(self, *keys, **overrides):
        params = self._params
        if overrides:
            params = dict(list(params.items()) + list(overrides.items()))
            keys = list(params.keys())
        return self._url + self._param_string(keys, params)

    @staticmethod
    def _param_string(keys, params):
        return '&'.join(['%s=%s' % (key, params[key]) for key in keys])


def make_filter_context(urlizer, filter_value, option_data):
    # Set up context for the treemap/partials/filter_dropdown.html template.
    # "option_data" is a list of tuples specifying filter options; each tuple
    # is fed directly to make_filter_option().

    def make_filter_option(label, label_lower, param_dict):
        # "param_dict" contains key=value pairs defining this filter option.
        # The values become part of the option's URL query string, and are
        # also compared to the "filter_value" to determine if this is the
        # currently-selected option.
        url = urlizer.url('sort', **param_dict)
        return {
            'label': label,
            'label_lower': label_lower,
            'url': url,
            'selected': (param_dict == filter_value)
        }

    options = [make_filter_option(*data) for data in option_data]

    selected_options = [option for option in options if option['selected']]
    selected_option = selected_options[0] if selected_options else None

    return {
        'options': options,
        'selected_option': selected_option,
    }
