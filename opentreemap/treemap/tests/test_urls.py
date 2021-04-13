# -*- coding: utf-8 -*-


import os
import json

from django.urls import reverse
from django.test.utils import override_settings

from treemap.models import Plot, Tree
from treemap.instance import create_stewardship_udfs
from treemap.tests import (make_instance, make_commander_user, login,
                           make_simple_boundary, RequestTestCase,
                           LocalMediaTestCase)
from treemap.tests.base import OTMTestCase

from opentreemap.settings import STATIC_ROOT


class UrlTestCase(OTMTestCase):

    def assert_status_code(self, url, code, method='GET', data='',
                           content_type=None):
        send = {
            'GET': self.client.get,
            'PUT': self.client.put,
            'POST': self.client.post,
            'DELETE': self.client.delete
        }[method]
        if content_type is None:
            response = send(url, data)
        else:
            response = send(url, data, content_type)
        self.assertEqual(response.status_code, code,
                         "Actual code [%s] Expected code [%s]"
                         % (response.status_code, code))
        return response

    def assert_200(self, url, method='GET', data='', content_type=None):
        return self.assert_status_code(url, 200, method, data, content_type)

    def assert_template(self, url, template_path):
        response = self.assert_status_code(url, 200)
        self.assertTemplateUsed(response, template_path)
        return response

    def assert_404(self, url, method='GET', data='', content_type=None):
        return self.assert_status_code(url, 404, method, data, content_type)

    def assert_401(self, url, method='GET', data='', content_type=None):
        return self.assert_status_code(url, 401, method, data, content_type)

    def assert_403(self, url, method='GET', data='', content_type=None):
        return self.assert_status_code(url, 403, method, data, content_type)

    def assert_redirects(self, url, expected_url, status_code=302):
        response = self.client.get(url)
        self.assertRedirects(response, expected_url, status_code)

    def assert_redirects_to_static_file(self, url, expected_url):
        response = self.assert_status_code(url, 302)
        new_url = response._headers['location'][1]
        self.assertTrue(expected_url in new_url)
        self.assert_static_file_exists(expected_url)

    def assert_static_file_exists(self, url):
        self.assertEqual(url[:8], '/static/')
        path = os.path.join(STATIC_ROOT, url[8:])
        self.assertTrue(os.path.exists(path))


class RootUrlTests(UrlTestCase):
    # Tests for URLs defined in opentreemap/urls.py

    def test_favicon(self):
        self.assert_redirects_to_static_file(
            '/favicon.png', '/static/img/favicon.png')

    def test_settings_js(self):
        self.assert_template('/config/settings.js', 'treemap/settings.js')

    def test_user(self):
        self.instance = make_instance()
        user = make_commander_user(self.instance)
        self.assert_template('/users/%s/' % user.username, 'treemap/user.html')

    def test_user_with_weird_characters(self):
        self.instance = make_instance()
        user = make_commander_user(self.instance, username='dot.name-site.com')
        self.assert_template('/users/%s/' % user.username, 'treemap/user.html')

    def test_user_invalid(self):
        self.assert_404('/users/nobody/')

    def test_user_update(self):
        username = make_commander_user().username
        login(self.client, username)
        self.assert_200('/users/%s/' % username, method='PUT', data='{}')

    def test_user_update_invalid(self):
        self.assert_404('/users/nobody/', method='PUT', data='{}')

    def test_user_update_forbidden(self):
        username = make_commander_user().username
        self.assert_403('/users/%s/' % username, method='PUT', data='{}')

    # Not testing 200 since it would involve loading valid image data
    def test_user_update_photo_invalid(self):
        self.assert_404('/users/nobody/photo/', method='POST', data={})

    def test_user_update_photo_forbidden(self):
        username = make_commander_user().username
        self.assert_403('/users/%s/photo/' % username, method='POST', data={})

    # Note: /accounts/profile/ is tested in tests/auth.py

    def test_user_audits(self):
        self.instance = make_instance()
        username = make_commander_user(self.instance).username
        self.assert_template('/users/%s/edits/' % username,
                             'treemap/recent_user_edits.html')
        self.assert_template('/users/%s/edits/?instance_id=%s'
                             % (username, self.instance.id),
                             'treemap/recent_user_edits.html')

    def test_user_audits_invalid(self):
        self.instance = make_instance()
        username = make_commander_user(self.instance).username
        self.assert_404('/users/fake/edits/')
        self.assert_404('/users/%s/edits/?instance_id=0' % username)

    def test_dynamic_scss(self):
        self.assert_200('/main.css?primary-color=fff')

    def test_point_within_itree_regions(self):
        self.assert_200('/eco/benefit/within_itree_regions/')


@override_settings(FEATURE_BACKEND_FUNCTION=None)
class TreemapUrlTests(UrlTestCase, LocalMediaTestCase):
    # Tests for URLs defined in treemap/urls.py
    # All treemap URLs start with /<instance_url_name>/

    def setUp(self):
        super(TreemapUrlTests, self).setUp()
        self.instance = make_instance(is_public=True)
        self.prefix = '/%s/' % self.instance.url_name

    def make_plot(self):
        user = make_commander_user(self.instance)
        plot = Plot(geom=self.instance.center, instance=self.instance)
        plot.save_with_user(user)
        return plot

    def make_tree(self, user=None):
        user = user or make_commander_user(self.instance)
        plot = Plot(geom=self.instance.center, instance=self.instance)
        plot.save_with_user(user)
        tree = Tree(instance=self.instance, plot=plot)
        tree.save_with_user(user)
        return tree

    def make_boundary(self):
        boundary = make_simple_boundary('b')
        boundary.save()
        self.instance.boundaries.add(boundary)
        return boundary

    def test_instance(self):
        self.assert_redirects(self.prefix, self.prefix + 'map/', 302)

    def test_instance_invalid(self):
        self.assert_404('/999/')

    def test_trailing_slash_added(self):
        url = '/%s' % self.instance.url_name
        self.assert_redirects(url + '/map', url + '/map/', 301)

    def test_boundary(self):
        boundary = self.make_boundary()
        self.assert_200(self.prefix + 'boundaries/%s/geojson/' % boundary.id)

    def test_boundary_invalid(self):
        self.assert_404(self.prefix + 'boundaries/99/geojson/')

    def test_anonymous_boundary(self):
        url = reverse('anonymous_boundary')
        self.assert_200(url, method='POST', data=json.dumps({
            'polygon': [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
        }), content_type="application/json")

    def test_boundaries_autocomplete(self):
        self.make_boundary()
        self.assert_200(self.prefix + 'boundaries/')

    def test_edits(self):
        self.assert_template(
            self.prefix + 'edits/', 'treemap/edits.html')

    def test_species_list(self):
        self.assert_200(self.prefix + 'species/')

    def test_tree_list(self):
        self.assert_template(self.prefix + 'map/', 'treemap/map.html')

    def test_tree_list_embed(self):
        self.assert_template(self.prefix + 'map/?embed=', 'treemap/map.html')

    def test_plot_detail(self):
        create_stewardship_udfs(self.instance)
        plot = self.make_plot()
        url = self.prefix + 'features/%s/' % plot.id
        self.assert_template(url, 'treemap/partials/plot_detail.html')
        self.assert_template(url, 'treemap/map_feature_detail.html')

    def test_plot_detail_invalid(self):
        self.assert_404(self.prefix + 'features/999/')

    def test_plot_detail_update(self):
        plot = self.make_plot()
        self.client.login(username='commander', password='password')
        self.assert_200(
            self.prefix + 'features/%s/' % plot.id, 'PUT',
            json.dumps({"plot.length": "1"}))

    def test_plot_detail_update_invalid(self):
        self.assert_401(self.prefix + 'features/999/', 'PUT',
                        json.dumps({"plot.length": "1"}))

    def test_plot_popup(self):
        plot = self.make_plot()
        self.assert_template(
            self.prefix + 'features/%s/popup' % plot.id,
            'treemap/partials/map_feature_popup.html')

    def test_plot_popup_invalid(self):
        self.assert_404(self.prefix + 'features/999/popup')

    def test_delete_plot_photo(self):
        commander = make_commander_user(self.instance)
        self.client.login(username=commander.username, password='password')
        tree = self.make_tree(commander)
        image = self.load_resource('tree1.gif')
        tp = tree.add_photo(image, commander)
        tp.save_with_user(commander)

        url = self.prefix + 'features/%s/photo/%s' % (tree.plot.id, tp.id)
        self.assert_200(url, method='DELETE')

    def test_rotate_tree_photo(self):
        commander = make_commander_user(self.instance)
        self.client.login(username=commander.username, password='password')
        tree = self.make_tree(commander)
        image = self.load_resource('tree1.gif')
        tp = tree.add_photo(image, commander)
        tp.save_with_user(commander)

        url = self.prefix + 'features/%s/photo/%s' % (tree.plot.id, tp.id)
        self.assert_200(url, method='POST', data={
            'degrees': -90
        })

    def test_map_feature_accordion(self):
        create_stewardship_udfs(self.instance)
        plot = self.make_plot()
        self.assert_template(
            self.prefix + 'features/%s/accordion' % plot.id,
            'treemap/partials/map_feature_accordion.html')

    def test_map_feature_accordion_invalid(self):
        self.assert_404(self.prefix + 'features/999/detail')

    def test_plot_create(self):
        username = make_commander_user(self.instance).username
        self.client.login(username=username, password='password')
        self.assert_200(
            self.prefix + 'plots/', 'POST',
            json.dumps({'plot.geom': {'x': 270, 'y': 45}}),
            content_type="application/json")

    def test_instance_settings_js(self):
        self.assert_template(
            self.prefix + 'config/settings.js', 'treemap/settings.js')

    def test_benefit_search(self):
        self.assert_template(
            self.prefix + 'benefit/search',
            'treemap/partials/eco_benefits.html')

    def test_user(self):
        username = make_commander_user(self.instance).username
        self.assert_redirects(
            self.prefix + 'users/%s/' % username,
            '/users/%s/?instance_id=%s' % (username, self.instance.id))

    def test_user_audits(self):
        username = make_commander_user(self.instance).username
        self.assert_redirects(
            self.prefix + 'users/%s/edits/' % username,
            '/users/%s/edits/?instance_id=%s'
            % (username, self.instance.id))


@override_settings(FEATURE_BACKEND_FUNCTION=None)
class TreemapPrivateUrlTests(UrlTestCase):
    # Tests for URLs defined in treemap/urls.py
    # All treemap URLs start with /<instance_url_name>/

    def setUp(self):
        self.instance = make_instance(is_public=False)
        self.prefix = '/%s/' % self.instance.url_name

    def test_instance(self):
        desired_path = self.prefix + 'map/'
        expected_path = '/accounts/login/?next=' + desired_path
        self.assert_redirects(desired_path, expected_path, 302)

    def test_embed(self):
        desired_path = self.prefix + 'map/?embed=1'
        expected_path = '/not-available?embed=1'
        self.assert_redirects(desired_path, expected_path, 302)


class InstanceUrlTests(RequestTestCase):
    def setUp(self):
        make_instance(name='The inztance', is_public=True,
                      url_name='ThEiNsTaNCe')

    def test_case_insensitive_url_lookup_upper(self):
        res = self.client.get('/%s/map/' % 'THEINSTANCE')
        self.assertOk(res)

    def test_case_insensitive_url_lookup_lower(self):

        res = self.client.get('/%s/map/' % 'theinstance')
        self.assertOk(res)

    def test_case_insensitive_url_lookup_mixed(self):
        res = self.client.get('/%s/map/' % 'ThEINStanCe')
        self.assertOk(res)
