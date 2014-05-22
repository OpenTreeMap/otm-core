# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


def context_dict_for_photo(photo):
    photo_dict = photo.as_dict()
    # TODO: we should be able replace this whole method
    # with a call to photo.as_dict() with a few replacements
    # TODO: cleanup this api. 'image' sounds like 'rich object'
    photo_dict['image'] = photo.image.url
    photo_dict['thumbnail'] = photo.thumbnail.url
    return photo_dict
