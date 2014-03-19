# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from PIL import Image

from treemap.images import save_uploaded_image
from treemap.tests import LocalMediaTestCase, media_dir


class SaveImageTest(LocalMediaTestCase):
    @media_dir
    def test_rotates_image(self):
        sideways_file = self.load_resource('tree_sideways.jpg')

        img_file, _ = save_uploaded_image(sideways_file, 'test')

        expected_width, expected_height = Image.open(sideways_file).size
        actual_width, actual_height = Image.open(img_file).size
        self.assertEquals(expected_width, actual_height)
        self.assertEquals(expected_height, actual_width)
