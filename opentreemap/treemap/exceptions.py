# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


class HttpBadRequestException(Exception):
    pass


class InvalidInstanceException(Exception):
    pass


class FeatureNotEnabledException(Exception):
    pass
