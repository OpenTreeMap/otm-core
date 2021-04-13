# -*- coding: utf-8 -*-


from urllib.parse import urlparse, urlunparse

from django.urls import reverse


def _drop_querystring(url):
    parts = urlparse(url)
    return urlunparse((parts.scheme, parts.netloc, parts.path,
                       parts.params, None, parts.fragment))


def context_dict_for_photo(request, photo):
    # TODO: we should be able replace this whole method
    # with a call to photo.as_dict() with a few replacements
    photo_dict = photo.as_dict()
    # We drop the querystring parameters to workaround a few bugs.
    # - Embedding the image URL inside another URL for social media sharing
    #   gets tripped up when the image URL contains a querystring
    # - By default Boto adds signing arguments to S3 URLs to allow access to
    #   private buckets, these annoyingly expire in an hour and tree photos are
    #   in a public bucket anyways
    # - The Android app ran into (mysterious and unexplained) issues with
    #   signed S3 URLs, but works fine if the querystring is removed
    image_url = _drop_querystring(photo.image.url)
    thumbnail_url = _drop_querystring(photo.thumbnail.url)

    # TODO: cleanup this api. 'image' sounds like 'rich object'
    photo_dict['image'] = image_url
    photo_dict['thumbnail'] = thumbnail_url
    photo_dict['raw'] = photo

    # add the label
    # TODO use a OneToOne mapping
    labels = photo.mapfeaturephotolabel_set.all()
    if labels:
        photo_dict['has_label'] = True
        photo_dict['label'] = labels[0].name
        photo_dict['label_id'] = labels[0].id
    else:
        photo_dict['has_label'] = False

    url = reverse(
        'map_feature_photo_detail',
        kwargs={'instance_url_name': photo.map_feature.instance.url_name,
                'feature_id': photo.map_feature_id,
                'photo_id': photo.id})

    # TODO: use this on the client to link from the carousel/lightbox
    photo_dict['detail_url'] = url
    photo_dict['absolute_detail_url'] = request.build_absolute_uri(url)
    photo_dict['absolute_image'] = request.build_absolute_uri(image_url)

    return photo_dict
