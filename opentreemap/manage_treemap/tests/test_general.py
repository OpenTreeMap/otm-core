# -*- coding: utf-8 -*-
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json

from django.core.exceptions import ValidationError
from django.test.utils import override_settings

from manage_treemap.views.management import update_logo, update_external_link
from treemap.tests import (make_instance, make_commander_user, make_request,
                           media_dir, LocalMediaTestCase)
from treemap.tests.base import OTMTestCase


class LogoUpdateTest(LocalMediaTestCase):
    def update_logo(self, filename):
        self.instance = make_instance()
        file = self.load_resource(filename)
        return update_logo(make_request(file=file), self.instance)

    @media_dir
    def test_update_logo(self):
        self.update_logo('tree1.gif')
        path = self.instance.logo.path
        self.assertPathExists(path)

        self.update_logo('tree2.jpg')
        self.assertPathExists(self.instance.logo.path)

    @media_dir
    def test_non_image(self):
        with self.assertRaises(ValidationError):
            self.update_logo('nonImage.jpg')

    @media_dir
    @override_settings(MAXIMUM_IMAGE_SIZE=10)
    def test_rejects_large_files(self):
        with self.assertRaises(ValidationError):
            self.update_logo('tree2.jpg')


class ExternalLinkUpdateTest(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.commander = make_commander_user(self.instance)

    def update_links(self, updates):
        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        update_external_link(request, self.instance)

    def test_update_some_values(self):
        self.update_links({
            'instance.config.externalLink.text': 'A link',
            'instance.config.externalLink.url': 'http://opentreemap.org/'
        })

        self.assertEqual(self.instance.config['externalLink.text'], 'A link')
        self.assertEqual(self.instance.config['externalLink.url'],
                         'http://opentreemap.org/')

        self.update_links({
            'instance.config.externalLink.text': 'Different text',
        })

        self.assertEqual(self.instance.config['externalLink.text'],
                         'Different text')
        self.assertEqual(self.instance.config['externalLink.url'],
                         'http://opentreemap.org/')

        self.update_links({
            'instance.config.externalLink.url': 'http://example.com/',
        })

        self.assertEqual(self.instance.config['externalLink.text'],
                         'Different text')
        self.assertEqual(self.instance.config['externalLink.url'],
                         'http://example.com/')

        self.update_links({
            'instance.config.externalLink.text': '',
            'instance.config.externalLink.url': ''
        })

        self.assertEqual(self.instance.config['externalLink.text'], '')
        self.assertEqual(self.instance.config['externalLink.url'], '')

    def test_error_on_blank(self):
        self.assertIsNone(self.instance.config.get('externalLink'))

        with self.assertRaises(ValidationError):
            self.update_links({
                # omitted text is the same as blank text before configuration
                'instance.config.externalLink.url': 'http://opentremap.org/'
            })

        with self.assertRaises(ValidationError):
            self.update_links({
                'instance.config.externalLink.text': 'A link'
                # omitted url is the same as a blank url before configuration
            })

        with self.assertRaises(ValidationError):
            self.update_links({
                'instance.config.externalLink.text': '',
                'instance.config.externalLink.url': 'http://opentreemap.org/'
            })

        with self.assertRaises(ValidationError):
            self.update_links({
                'instance.config.externalLink.text': None,
                'instance.config.externalLink.url': 'http://opentreemap.org/'
            })

        with self.assertRaises(ValidationError):
            self.update_links({
                'instance.config.externalLink.text': 'A link',
                'instance.config.externalLink.url': ''
            })

        with self.assertRaises(ValidationError):
            self.update_links({
                'instance.config.externalLink.text': 'A link',
                'instance.config.externalLink.url': None
            })

    def test_error_on_tokens(self):
        # No errors
        self.update_links({
            'instance.config.externalLink.text': 'A link',
            'instance.config.externalLink.url': 'http://opentreemap.org/plot/#{planting_site.id}'  # NOQA
        })

        with self.assertRaises(ValidationError):
            self.update_links({
                'instance.config.externalLink.text': 'A link',
                'instance.config.externalLink.url': 'http://opentreemap.org/plot/#{planting_site.width}'  # NOQA
            })

        with self.assertRaises(ValidationError):
            self.update_links({
                'instance.config.externalLink.text': 'A link',
                'instance.config.externalLink.url': 'http://opentreemap.org/plot/#{bioswale.id}'  # NOQA
            })

        with self.assertRaises(ValidationError):
            self.update_links({
                'instance.config.externalLink.text': 'A link',
                'instance.config.externalLink.url': 'http://opentreemap.org/plot/#{id}'  # NOQA
            })

        with self.assertRaises(ValidationError):
            self.update_links({
                'instance.config.externalLink.text': 'A link',
                'instance.config.externalLink.url': 'http://opentreemap.org/plot/#{}'  # NOQA
            })

    def test_error_with_omitted_field(self):
        # No errors
        self.update_links({
            'instance.config.externalLink.text': 'A link',
            'instance.config.externalLink.url': 'http://opentreemap.org/plot/#{planting_site.id}'  # NOQA
        })

        # text is required while url is still in effect
        with self.assertRaises(ValidationError):
            self.update_links({
                'instance.config.externalLink.text': '',
            })

        # url is required while text is still in effect
        with self.assertRaises(ValidationError):
            self.update_links({
                'instance.config.externalLink.url': ''
            })
