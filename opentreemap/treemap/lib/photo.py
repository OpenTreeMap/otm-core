# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from urlparse import urlparse, urlunparse

from django.core.urlresolvers import reverse


def _drop_querystring(url):
    parts = urlparse(url)
    return urlunparse((parts.scheme, parts.netloc, parts.path,
                       parts.params, None, parts.fragment))


def context_dict_for_photo(request, photo):
    photo_dict = photo.as_dict()
    # TODO: we should be able replace this whole method
    # with a call to photo.as_dict() with a few replacements
    # TODO: cleanup this api. 'image' sounds like 'rich object'
    photo_dict['image'] = photo.image.url
    photo_dict['thumbnail'] = photo.thumbnail.url
    photo_dict['raw'] = photo

    url = reverse(
        'map_feature_photo_detail',
        kwargs={'instance_url_name': photo.map_feature.instance.url_name,
                'feature_id': photo.map_feature_id,
                'photo_id': photo.id})

    # TODO: use this on the client to link from the carousel/lightbox
    photo_dict['detail_url'] = url
    photo_dict['absolute_detail_url'] = request.build_absolute_uri(url)

    # we drop the querystring parameters for two reasons. First, we
    # are working around a bug in which embedding a url with qs params
    # inside the qs params of a url does not produce a properly
    # escaped URL to achieve this. For this reason, S3 urls were being
    # truncated after the first qs param, and therefore producing
    # broken urls. Second, even if we correctly provide all S3 qs
    # params, they are not necessary for public buckets, and can add
    # temporary credentials that expire when the underlying public
    # image does not.
    photo_dict['absolute_image'] = request.build_absolute_uri(
        _drop_querystring(photo.image.url))

    return photo_dict
