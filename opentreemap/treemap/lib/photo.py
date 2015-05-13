# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.core.urlresolvers import reverse


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
    photo_dict['absolute_image'] = request.build_absolute_uri(photo.image.url)

    return photo_dict
