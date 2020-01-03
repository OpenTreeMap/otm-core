# -*- coding: utf-8 -*-




import re

from django.utils.translation import ugettext_lazy as _
from functools import reduce


# Utilities for external links
_valid_url_tokens = ['tree.id', 'planting_site.id', 'planting_site.custom_id']


def get_external_link_choice_pattern():
    return '|'.join([choice.replace('.', r'\.')
                     for choice in _valid_url_tokens])

_validation_pattern = r'''\#(?:   # starts with a hash
    (?P<valid>{{(?:{})}}) |       # valid group is braced, filled by format
    (?P<invalid>{{.*?}})          # anything else braced is invalid
    )
    '''.format(get_external_link_choice_pattern())

_validator_re = re.compile(_validation_pattern, re.VERBOSE | re.IGNORECASE)


def _re_group_count(compiled, text):
    '''
    Return a dict with the counts of valid and invalid strings in text
    '''
    totals = {'valid': 0, 'invalid': 0}

    return reduce(
        lambda ac, groupdict: {
            k: v if groupdict[k] is None else v + 1
            for k, v in ac.items()},
        [m.groupdict() for m in compiled.finditer(text)],
        totals)


def validate_token_template(token_template):
    check = _re_group_count(_validator_re, token_template)
    return 0 == check['invalid']


def get_url_tokens_for_display(in_bold=False):
    show = lambda t: ('<b>#{%s}</b>' if in_bold else '#{%s}') % t

    return (', '.join(show(token) for token in _valid_url_tokens[:-1]) +
            str(_(' or ')) + show(_valid_url_tokens[-1]))
