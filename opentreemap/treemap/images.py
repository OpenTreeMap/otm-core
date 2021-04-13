# -*- coding: utf-8 -*-


from PIL import Image
import hashlib
import os
from io import BytesIO

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from django.core.files.uploadedfile import SimpleUploadedFile


def _rotate_image_based_on_exif(img):
    try:
        # According to PIL.ExifTags, 0x0112 is "Orientation"
        orientation = img._getexif()[0x0112]
        if orientation == 6:  # Right turn
            img = img.rotate(-90, expand=True)
        elif orientation == 5:  # Left turn
            img = img.rotate(90, expand=True)
    except:
        pass

    return img


def _get_file_for_image(image, filename, format):
    temp = BytesIO()
    image.save(temp, format=format)
    temp.seek(0)
    return SimpleUploadedFile(filename, temp.read(),
                              'image/%s' % format.lower())


def save_image_from_request(request, name_prefix, thumb_size=None):
    if 'file' in request.FILES:
        image_data = request.FILES['file'].file
    else:
        image_data = request.body

    return save_uploaded_image(image_data, name_prefix, thumb_size)


def save_uploaded_image(image_data, name_prefix, thumb_size=None,
                        degrees_to_rotate=None):
    # We support passing data directly in here but we
    # have to treat it as a file-like object
    if type(image_data) is str:
        image_data = StringIO(image_data)
    elif type(image_data) is bytes:
        image_data = BytesIO(image_data)

    image_data.seek(0, os.SEEK_END)
    file_size = image_data.tell()

    if file_size > settings.MAXIMUM_IMAGE_SIZE:
        raise ValidationError(_('The uploaded image is too large'))

    image_data.seek(0)

    try:
        image = Image.open(image_data)
        image.verify()
    except IOError:
        raise ValidationError(_('Invalid image'))

    try:
        # http://pillow.readthedocs.org/en/latest/_modules/PIL/Image.html#Image.verify  # NOQA
        # ...if you need to load the image after using verify,
        # you must reopen the image file.
        image_data.seek(0)
        image = Image.open(image_data)
        format = image.format

        image_data.seek(0)
        hash = hashlib.md5(image_data.read()).hexdigest()
        name = "%s-%s.%s" % (name_prefix, hash, format.lower())

        if degrees_to_rotate is None:
            image = _rotate_image_based_on_exif(image)
        else:
            image = image.rotate(degrees_to_rotate, expand=True)

        image_file = _get_file_for_image(image, name, format)
        thumb_file = None

        if thumb_size is not None:
            thumb_image = image.copy()
            thumb_image.thumbnail(thumb_size, Image.ANTIALIAS)
            thumb_file = _get_file_for_image(thumb_image, 'thumb-%s' % name,
                                             format)

        # Reset image position
        image_data.seek(0)

        return image_file, thumb_file
    except:
        raise ValidationError(_('Image upload issue'))


def get_image_from_request(request):
    if 'file' in request.FILES:
        return request.FILES['file'].file
    else:
        return request.body
