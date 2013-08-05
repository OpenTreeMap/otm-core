import os

from django.contrib.gis.geos.collections import MultiPolygon
from django.contrib.gis.geos.point import Point
from django.contrib.gis.geos.polygon import Polygon
from django.test import TestCase

from treemap.models import User, Boundary, Plot
from treemap.tests import (make_instance, make_god_role, make_simple_boundary)
from opentreemap.local_settings import STATIC_ROOT

class UrlTestCase(TestCase):

    def make_god_user(self):
        god = User(username='god', password='abc')
        god.save()
        god.roles.add(make_god_role(self.instance))
        return god

    def assert_status_code(self, url, code):
        response = self.client.get(url)
        self.assertEqual(response.status_code, code)
        return response

    def assert_200(self, url):
        return self.assert_status_code(url, 200)

    def assert_template(self, url, template_path):
        response = self.assert_status_code(url, 200)
        self.assertTemplateUsed(response, template_path)
        return response

    def assert_404(self, url):
        return self.assert_status_code(url, 404)

    def assert_redirects(self, url, expected_url, status_code=302):
        response = self.client.get(url)
        self.assertRedirects(response, expected_url, status_code)

    def assert_redirects_to_static_file(self, url, expected_url):
        response = self.assert_status_code(url, 302)
        new_url = response._headers['location'][1]
        self.assertTrue(expected_url in new_url)
        self.assert_static_file_exists(expected_url)

    def assert_static_file_exists(self, url):
        self.assertEquals(url[:8], '/static/')
        path = os.path.join(STATIC_ROOT, url[8:])
        self.assertTrue(os.path.exists(path))


class RootUrlTests(UrlTestCase):
    # Tests for URLs defined in opentreemap/urls.py

    def test_favicon(self):
        self.assert_redirects_to_static_file(
            '/favicon.ico', '/static/img/favicon.ico')

    def test_settings_js(self):
        self.assert_template('/config/settings.js', 'treemap/settings.js')

    def test_user(self):
        self.instance = make_instance()
        god = self.make_god_user()
        self.assert_template('/users/%s/' % god.username, 'treemap/user.html')

    def test_user_invalid(self):
        self.assert_404('/users/nobody/')

    # Note: /accounts/profile/ is tested in tests/auth.py


class TreemapUrlTests(UrlTestCase):
    # Tests for URLs defined in treemap/urls.py
    # All treemap URLs start with /<instance_id>/

    def setUp(self):
        self.instance = make_instance()
        self.prefix = '/%s/' % self.instance.id

    def make_plot(self):
        god = self.make_god_user()
        plot = Plot(geom=Point(0, 0), instance=self.instance)
        plot.save_with_user(god)
        return plot

    def make_boundary(self):
        boundary = make_simple_boundary('b')
        boundary.save()
        self.instance.boundaries.add(boundary)
        return boundary

    def test_instance(self):
        self.assert_template(self.prefix, 'treemap/index.html')

    def test_instance_invalid(self):
        self.assert_404('/999/')

    def test_trailing_slash_added(self):
        url = '/%s' % self.instance.id
        self.assert_redirects(url, url + '/', 301)

    def test_boundary(self):
        boundary = self.make_boundary()
        self.assert_200(self.prefix + 'boundaries/%s/geojson/' % boundary.id)

    def test_boundary_invalid(self):
        self.assert_404(self.prefix + 'boundaries/99/geojson/')

    def test_boundaries_autocomplete(self):
        self.make_boundary()
        self.assert_200(self.prefix + 'boundaries/')

    def test_recent_edits(self):
        self.assert_template(
            self.prefix + 'recent_edits/', 'treemap/recent_edits.html')

    def test_species_list(self):
        self.assert_200(self.prefix + 'species/')

    def test_tree_list(self):
        self.assert_template(self.prefix + 'trees/', 'treemap/map.html')

    def test_plot_detail(self):
        plot = self.make_plot();
        self.assert_template(
            self.prefix + 'trees/%s/' % plot.id, 'treemap/plot_detail.html')

    def test_plot_detail_invalid(self):
        self.assert_404(self.prefix + 'trees/999/')

    def test_plot_popup(self):
        plot = self.make_plot();
        self.assert_template(
            self.prefix + 'plots/%s/' % plot.id, 'treemap/plot_popup.html')

    def test_plot_popup_invalid(self):
        self.assert_404(self.prefix + 'plots/999/')

    def test_instance_settings_js(self):
        self.assert_template(
            self.prefix + 'config/settings.js', 'treemap/settings.js')

    def test_benefit_search(self):
        self.assert_template(
            self.prefix + 'benefit/search', 'treemap/eco_benefits.html')

    def test_user(self):
        username = self.make_god_user().username
        self.assert_redirects(
            self.prefix + 'users/%s/' % username,
            '/users/%s/?instance_id=%s' % (username, self.instance.id))
