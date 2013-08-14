from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from django.test import TestCase
from django.test.client import RequestFactory
from django.http import Http404

from django.contrib.gis.geos import Point

from treemap.audit import Role, Audit, approve_or_reject_audit_and_apply

from treemap.models import (Instance, Species, User, Plot, Tree,
                            InstanceUser, BenefitCurrencyConversion)

from treemap.views import (species_list, boundary_to_geojson, plot_detail,
                           boundary_autocomplete, audits, user_audits,
                           search_tree_benefits, user, instance_user_view)

from treemap.tests import (ViewTestCase, make_instance, make_officer_user,
                           make_commander_user, make_apprentice_user,
                           make_user_with_default_role, make_simple_boundary)


class InstanceValidationTest(TestCase):

    def setUp(self):

        global_role = Role(name='global', rep_thresh=0)
        global_role.save()

        p = Point(-8515941.0, 4953519.0)
        self.instance1 = Instance(name='i1', geo_rev=0, center=p,
                                  default_role=global_role)

        self.instance1.save()

        self.instance2 = Instance(name='i2', geo_rev=0, center=p,
                                  default_role=global_role)

        self.instance2.save()


class BoundaryViewTest(ViewTestCase):

    def setUp(self):
        super(BoundaryViewTest, self).setUp()

        self.test_boundaries = [
            'alabama',
            'arkansas',
            'far',
            'farquaad\'s castle',
            'farther',
            'farthest',
            'ferenginar',
            'romulan star empire',
        ]
        self.test_boundary_hashes = [
            {'tokens': ['alabama']},
            {'tokens': ['arkansas']},
            {'tokens': ['far']},
            {'tokens': ['farquaad\'s', 'castle']},
            {'tokens': ['farther']},
            {'tokens': ['farthest']},
            {'tokens': ['ferenginar']},
            {'tokens': ['romulan', 'star', 'empire']},
        ]
        for i, v in enumerate(self.test_boundaries):
            boundary = make_simple_boundary(v, i)
            self.instance.boundaries.add(boundary)
            self.instance.save()
            js_boundary = self.test_boundary_hashes[i]

            js_boundary['id'] = boundary.id
            js_boundary['name'] = boundary.name
            js_boundary['category'] = boundary.category
            js_boundary['value'] = boundary.name

    def test_boundary_to_geojson_view(self):
        boundary = make_simple_boundary("Hello, World", 1)
        self.instance.boundaries.add(boundary)
        self.instance.save()
        response = boundary_to_geojson(
            self._make_request(),
            self.instance,
            boundary.pk)

        self.assertEqual(response.content, boundary.geom.geojson)

    def test_autocomplete_view(self):
        response = boundary_autocomplete(self._make_request(), self.instance)

        self.assertEqual(response, self.test_boundary_hashes)

    def test_autocomplete_view_scoped(self):
        # make a boundary that is not tied to this
        # instance, should not be in the search
        # results
        make_simple_boundary("fargo", 1)
        response = boundary_autocomplete(self._make_request(), self.instance)

        self.assertEqual(response, self.test_boundary_hashes)

    def test_autocomplete_view_limit(self):
        response = boundary_autocomplete(
            self._make_request({'max_items': 2}),
            self.instance)

        self.assertEqual(response, self.test_boundary_hashes[0:2])


class PlotViewTest(ViewTestCase):

    def setUp(self):
        super(PlotViewTest, self).setUp()

        self.instance = make_instance()
        self.user = make_commander_user(self.instance)

        self.p = Point(-7615441.0, 5953519.0)

    def test_simple_audit_history(self):
        plot = Plot(instance=self.instance, geom=self.p)
        plot.save_with_user(self.user)

        plot.width = 9
        plot.save_with_user(self.user)

        details = plot_detail(self._make_request(user=self.user),
                              self.instance,
                              plot.pk)

        self.assertIn('recent_activity', details)

        recent_activity = details['recent_activity']

        audit = recent_activity[0]
        self.assertEqual(audit.model, 'Plot')
        self.assertEqual(audit.field, 'width')

    def test_tree_audits_show_up_too(self):
        plot = Plot(instance=self.instance, geom=self.p)
        plot.save_with_user(self.user)

        tree = Tree(instance=self.instance, plot=plot)
        tree.save_with_user(self.user)

        tree.readonly = True
        tree.save_with_user(self.user)

        details = plot_detail(self._make_request(user=self.user),
                              self.instance,
                              plot.pk)

        self.assertIn('recent_activity', details)

        recent_activity = details['recent_activity']
        readonly_audit = recent_activity[0]
        insert_audit = recent_activity[1]

        self.assertEqual(readonly_audit.model, 'Tree')
        self.assertEqual(readonly_audit.field, 'readonly')
        self.assertEqual(readonly_audit.model_id, tree.pk)
        self.assertEqual(readonly_audit.action, Audit.Type.Update)

        self.assertEqual(insert_audit.model, 'Tree')
        self.assertEqual(insert_audit.model_id, tree.pk)
        self.assertEqual(insert_audit.action, Audit.Type.Insert)

    def test_plot_with_tree(self):
        species = Species(itree_code='CEM OTHER')
        species.save()

        plot_w_tree = Plot(geom=self.p, instance=self.instance)
        plot_w_tree.save_with_user(self.user)

        tree = Tree(plot=plot_w_tree, instance=self.instance,
                    diameter=10, species=species)
        tree.save_with_user(self.user)

        context = plot_detail(self._make_request(user=self.user),
                              self.instance, plot_w_tree.pk)

        self.assertEquals(plot_w_tree, context['plot'])
        self.assertIn('benefits', context)

    def test_plot_without_tree(self):
        plot_wo_tree = Plot(geom=self.p, instance=self.instance)
        plot_wo_tree.save_with_user(self.user)

        context = plot_detail(self._make_request(user=self.user),
                              self.instance, plot_wo_tree.pk)

        self.assertEquals(plot_wo_tree, context['plot'])
        self.assertNotIn('benefits', context)


class RecentEditsViewTest(TestCase):

    def setUp(self):
        self.longMessage = True

        self.instance = make_instance()
        self.instance2 = make_instance('i2')
        self.officer = make_officer_user(self.instance)
        self.commander = make_commander_user(self.instance)
        self.pending_user = make_apprentice_user(self.instance)
        iuser = InstanceUser(instance=self.instance2, user=self.commander,
                             role=self.commander.get_role(self.instance))
        iuser.save_with_user(self.commander)

        self.p1 = Point(-7615441.0, 5953519.0)
        self.factory = RequestFactory()

        self.plot = Plot(geom=self.p1, instance=self.instance)

        self.dif_instance_plot = Plot(geom=self.p1, instance=self.instance2)
        self.dif_instance_plot.save_with_user(self.commander)

        self.plot.save_with_user(self.commander)

        self.tree = Tree(plot=self.plot, instance=self.instance)

        self.tree.save_with_user(self.officer)

        self.tree.diameter = 4
        self.tree.save_with_user(self.officer)

        self.tree.diameter = 5
        self.tree.save_with_user(self.officer)

        self.plot.width = 9
        self.plot.save_with_user(self.commander)

        self.plot_delta = {
            "model": "Plot",
            "model_id": self.plot.pk,
            "ref_id": None,
            "action": Audit.Type.Update,
            "previous_value": None,
            "current_value": "9",
            "requires_auth": False,
            "user_id": self.commander.pk,
            "instance_id": self.instance.pk,
            "field": "width"
        }

        self.next_plot_delta = self.plot_delta.copy()
        self.next_plot_delta["current_value"] = "44"
        self.next_plot_delta["previous_value"] = "9"

        self.plot.width = 44
        self.plot.save_with_user(self.commander)

        self.dif_instance_plot.width = '22'
        self.dif_instance_plot.save_with_user(self.commander)
        self.dif_plot_delta = {
            "model": "Plot",
            "model_id": self.dif_instance_plot.pk,
            "ref_id": None,
            "action": Audit.Type.Update,
            "previous_value": None,
            "current_value": '22',
            "requires_auth": False,
            "user_id": self.commander.pk,
            "instance_id": self.instance2.pk,
            "field": "width"
        }

    def _assert_dicts_equal(self, expected, actual):
        self.assertEqual(len(expected), len(actual), "Number of dicts")

        for expected, generated in zip(expected, actual):
            for k, v in expected.iteritems():
                self.assertEqual(v, generated[k], "key [%s]" % k)

    def check_audits(self, url, dicts):
        req = self.factory.get(url)
        resulting_audits = [a.audit.dict()
                            for a
                            in audits(req, self.instance)['audits']]

        self._assert_dicts_equal(dicts, resulting_audits)

    def check_user_audits(self, url, username, dicts):
        req = self.factory.get(url)
        resulting_audits = [a.audit.dict()
                            for a
                            in user_audits(req, username)['audits']]

        self._assert_dicts_equal(dicts, resulting_audits)

    def test_multiple_deltas(self):
        self.check_audits('/blah/?page_size=2',
                          [self.next_plot_delta, self.plot_delta])
        self.check_user_audits('/blah/?page_size=2&instance_id=%s'
                               % self.instance.pk, self.commander.username,
                               [self.next_plot_delta, self.plot_delta])

    def test_paging(self):
        self.check_audits('/blah/?page_size=1&page=1', [self.plot_delta])
        self.check_user_audits('/eblah/?page_size=1&page=1&instance_id=%s'
                               % self.instance.pk,
                               self.commander.username, [self.plot_delta])

    def test_model_filtering_errors(self):
        self.assertRaises(Exception,
                          self.check_audits,
                          "/blah/?model_id=%s&page=0&page_size=1" %
                          self.tree.pk, [])

        self.assertRaises(Exception,
                          self.check_audits,
                          "/blah/?model_id=%s&"
                          "models=Tree,Plot&page=0&page_size=1" %
                          self.tree.pk, [])

        self.assertRaises(Exception,
                          self.check_audits,
                          "/blah/?models=User&page=0&page_size=1", [])

        self.assertRaises(Exception,
                          self.check_user_audits,
                          "/blah/?model_id=%s&page=0&page_size=1"
                          "&instance_id=%s"
                          % (self.instance.pk, self.tree.pk),
                          self.commander.username, [])

        self.assertRaises(Exception,
                          self.check_user_audits,
                          "/blah/?model_id=%s&"
                          "models=Tree,Plot&page=0&page_size=1"
                          "&instance_id=%s"
                          % (self.instance.pk, self.tree.pk),
                          self.commander.username, [])

        self.assertRaises(Exception,
                          self.check_user_audits,
                          "/blah/?models=User&page=0&page_size=1",
                          "&instance_id=%s" % self.instance.pk,
                          self.commander.username, [])

    def test_model_filtering(self):

        specific_tree_delta = {
            "model": "Tree",
            "model_id": self.tree.pk,
            "action": Audit.Type.Update,
            "user_id": self.officer.pk,
        }

        generic_tree_delta = {
            "model": "Tree"
        }

        generic_plot_delta = {
            "model": "Plot"
        }

        self.check_audits(
            "/blah/?model_id=%s&models=Tree&page=0&page_size=1" % self.tree.pk,
            [specific_tree_delta])

        self.check_audits(
            "/blah/?model_id=%s&models=Plot&page=0&page_size=1" % self.plot.pk,
            [self.next_plot_delta])

        self.check_audits(
            "/blah/?models=Plot,Tree&page=0&page_size=3",
            [generic_plot_delta, generic_plot_delta, generic_tree_delta])

        self.check_audits(
            "/blah/?models=Plot&page=0&page_size=5",
            [generic_plot_delta] * 5)

        self.check_audits(
            "/blah/?models=Tree&page=0&page_size=5",
            [generic_tree_delta] * 5)

    def test_model_user_filtering(self):

        specific_tree_delta = {
            "model": "Tree",
            "model_id": self.tree.pk,
            "action": Audit.Type.Update,
            "user_id": self.officer.pk,
        }

        generic_tree_delta = {
            "model": "Tree"
        }

        generic_plot_delta = {
            "model": "Plot"
        }

        self.check_user_audits(
            "/blah/?model_id=%s&models=Tree&page=0&page_size=1" % self.tree.pk,
            self.officer.username, [specific_tree_delta])

        self.check_user_audits(
            "/blah/?model_id=%s&models=Plot&page=0&page_size=1&instance_id=%s"
            % (self.plot.pk, self.instance.pk),
            self.commander.username, [self.next_plot_delta])

        self.check_user_audits(
            "/blah/?models=Plot&page=0&page_size=3&instance_id=%s"
            % self.instance.pk, self.commander.username,
            [generic_plot_delta] * 3)

        self.check_user_audits(
            "/blah/?models=Tree&page=0&page_size=3", self.officer.username,
            [generic_tree_delta] * 3)

    def test_user_filtering(self):

        generic_officer_delta = {
            "user_id": self.officer.pk
        }

        generic_commander_delta = {
            "user_id": self.commander.pk
        }

        self.check_audits(
            "/blah/?user=%s&page_size=3" % self.officer.pk,
            [generic_officer_delta] * 3)

        self.check_audits(
            "/blah/?user=%s&page_size=3" % self.commander.pk,
            [generic_commander_delta] * 3)

    def test_user_id_ignored(self):

        generic_officer_delta = {
            "user_id": self.officer.pk
        }

        generic_commander_delta = {
            "user_id": self.commander.pk
        }

        self.check_user_audits(
            "/blah/?user=%s&page_size=3" % self.officer.pk,
            self.commander.username, [generic_commander_delta] * 3)

        self.check_user_audits(
            "/blah/?user=%s&page_size=3" % self.commander.pk,
            self.officer.username, [generic_officer_delta] * 3)

    def test_user_audits_multiple_instances(self):
        self.check_user_audits(
            "/blah/?page_size=2", self.commander.username,
            [self.dif_plot_delta, self.next_plot_delta])

        self.check_user_audits(
            "/blah/?instance_id=%s&page_size=1" % self.instance2.pk,
            self.commander.username, [self.dif_plot_delta])

    def test_pending_filtering(self):
        self.plot.width = 22
        self.plot.save_with_user(self.pending_user)

        pending_plot_delta = {
            "model": "Plot",
            "model_id": self.plot.pk,
            "ref_id": None,
            "action": Audit.Type.Update,
            "previous_value": "44",
            "current_value": "22",
            "requires_auth": True,
            "user_id": self.pending_user.pk,
            "instance_id": self.instance.pk,
            "field": "width"
        }

        approve_delta = {
            "action": Audit.Type.PendingApprove,
            "user_id": self.commander.pk,
            "instance_id": self.instance.pk,
        }

        self.check_audits(
            "/blah/?page_size=2&exclude_pending=false",
            [pending_plot_delta, self.next_plot_delta])

        self.check_audits(
            "/blah/?page_size=2&exclude_pending=true",
            [self.next_plot_delta, self.plot_delta])

        a = approve_or_reject_audit_and_apply(
            Audit.objects.all().order_by("-created")[0],
            self.commander, approved=True)

        pending_plot_delta["ref_id"] = a.pk

        self.check_audits(
            "/blah/?page_size=4&exclude_pending=true",
            [approve_delta, pending_plot_delta,
             self.next_plot_delta, self.plot_delta])


class SpeciesViewTests(ViewTestCase):

    def setUp(self):
        super(SpeciesViewTests, self).setUp()

        self.species_dict = [
            {'common_name': "apple 'Red Devil'", 'genus': 'applesauce'},
            {'common_name': 'asian cherry', 'genus': 'cherrificus'},
            {'common_name': 'cherrytree', 'genus': 'cherritius',
             'cultivar': 'asian'},
            {'common_name': 'elm', 'genus': 'elmitius'},
            {'common_name': 'oak', 'genus': 'acorn',
             'species': 'oakenitus'}
        ]
        self.species_json = [
            {'tokens': ['apple', 'Red', 'Devil', 'applesauce']},
            {'tokens': ['asian', 'cherry', 'cherrificus']},
            {'tokens': ['cherrytree', 'cherritius', 'asian']},
            {'tokens': ['elm', 'elmitius']},
            {'tokens': ['oak', 'acorn', 'oakenitus']}
        ]
        for i, item in enumerate(self.species_dict):
            species = Species(common_name=item.get('common_name'),
                              genus=item.get('genus'),
                              species=item.get('species'),
                              cultivar=item.get('cultivar'),
                              symbol=str(i))
            species.save()

            js_species = self.species_json[i]
            js_species['id'] = species.id
            js_species['common_name'] = species.common_name
            js_species['scientific_name'] = species.scientific_name
            js_species['value'] = species.display_name

    def test_get_species_list(self):
        self.assertEquals(species_list(self._make_request(), None),
                          self.species_json)

    def test_get_species_list_max_items(self):
        self.assertEquals(
            species_list(self._make_request({'max_items': 3}), None),
            self.species_json[:3])


class SearchTreeBenefitsTests(ViewTestCase):

    def setUp(self):
        super(SearchTreeBenefitsTests, self).setUp()
        self.instance = make_instance()
        self.commander = make_commander_user(self.instance)

        self.p1 = Point(-7615441.0, 5953519.0)
        self.species_good = Species(itree_code='CEM OTHER')
        self.species_good.save()
        self.species_bad = Species()
        self.species_bad.save()

    def make_tree(self, diameter, species):
        plot = Plot(geom=self.p1, instance=self.instance)
        plot.save_with_user(self.commander)
        tree = Tree(plot=plot, instance=self.instance,
                    diameter=diameter, species=species)
        tree.save_with_user(self.commander)

    def search_benefits(self):
        request = self._make_request(
            {'q': json.dumps({'tree.readonly': {'IS': False}})})  # all trees
        result = search_tree_benefits(request, self.instance)
        return result

    def test_tree_with_species_and_diameter_included(self):
        self.make_tree(10, self.species_good)
        benefits = self.search_benefits()
        # The benefit counts are returned as localized strings
        self.assertEqual(benefits['basis']['n_trees_used'], '1')

    def test_tree_without_diameter_ignored(self):
        self.make_tree(None, self.species_good)
        benefits = self.search_benefits()
        # The benefit counts are returned as localized strings
        self.assertEqual(benefits['basis']['n_trees_used'], '0')

    def test_tree_without_species_ignored(self):
        self.make_tree(10, None)
        benefits = self.search_benefits()
        # The benefit counts are returned as localized strings
        self.assertEqual(benefits['basis']['n_trees_used'], '0')

    def test_tree_without_itree_code_ignored(self):
        self.make_tree(10, self.species_bad)
        benefits = self.search_benefits()
        # The benefit counts are returned as localized strings
        self.assertEqual(benefits['basis']['n_trees_used'], '0')

    def test_extrapolation_increases_benefits(self):
        self.make_tree(10, self.species_good)
        self.make_tree(20, self.species_good)
        self.make_tree(30, self.species_good)
        benefits = self.search_benefits()
        value = float(benefits['benefits'][0]['value'])

        self.make_tree(None, self.species_good)
        self.make_tree(10, None)
        benefits = self.search_benefits()
        value_with_extrapolation = float(benefits['benefits'][0]['value'])

        self.assertEqual(benefits['basis']['percent'], 0.6)
        self.assertGreater(self, value_with_extrapolation, value)

    def test_currency_is_empty_if_not_set(self):
        self.make_tree(10, self.species_good)
        benefits = self.search_benefits()

        for benefit in benefits['benefits']:
            self.assertNotIn('currency_saved', benefit)

    def test_currency_is_not_empty(self):
        benefit = BenefitCurrencyConversion(
            kwh_to_currency=2.0,
            stormwater_gal_to_currency=2.0,
            carbon_dioxide_lb_to_currency=2.0,
            airquality_aggregate_lb_to_currency=2.0,
            currency_symbol='$')

        benefit.save()
        self.instance.eco_benefits_conversion = benefit
        self.instance.save()

        self.make_tree(10, self.species_good)
        benefits = self.search_benefits()

        for benefit in benefits['benefits']:
            self.assertEqual(
                benefit['currency_saved'],
                '%d' % (float(benefit['value']) * 2.0))

        self.assertEqual(benefits['currency_symbol'], '$')


class UserViewTests(ViewTestCase):

    def setUp(self):
        super(UserViewTests, self).setUp()
        self.joe = make_user_with_default_role(self.instance, 'joe')

    def test_get_by_username(self):
        context = user(self._make_request(), self.joe.username)
        self.assertEquals(self.joe.username, context['user'].username,
                          'the user view should return a dict with user with '
                          '"username" set to %s ' % self.joe.username)
        self.assertEquals([], context['audits'],
                          'the user view should return a audits list')

    def test_get_with_invalid_username_returns_404(self):
        self.assertRaises(Http404, user, self._make_request(),
                          'no_way_this_is_a_username')


class InstanceUserViewTests(ViewTestCase):

    def setUp(self):
        super(InstanceUserViewTests, self).setUp()

        self.commander = User(username="commander", password='pw')
        self.commander.save()

    def test_get_by_username_redirects(self):
        res = instance_user_view(self._make_request(),
                                 self.instance.id,
                                 self.commander.username)
        expected_url = '/users/%s?instance_id=%d' %\
            (self.commander.username, self.instance.id)
        self.assertEquals(res.status_code, 302, "should be a 302 Found \
            temporary redirect")
        self.assertEquals(expected_url, res['Location'],
                          'the view should redirect to %s not %s ' %
                          (expected_url, res['Location']))

    def test_get_with_invalid_username_redirects(self):
        test_instance_id, test_username = 9999999999999, 'no_way_username'
        res = instance_user_view(self._make_request(),
                                 test_instance_id,
                                 test_username)
        expected_url = '/users/%s?instance_id=%d' %\
            (test_username, test_instance_id)
        self.assertEquals(res.status_code, 302, "should be a 302 Found \
            temporary redirect")
        self.assertEquals(expected_url, res['Location'],
                          'the view should redirect to %s not %s ' %
                          (expected_url, res['Location']))
