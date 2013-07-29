from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from django.test import TestCase
from django.test.client import RequestFactory

from django.contrib.gis.geos import Point

from treemap.audit import Role, Audit, approve_or_reject_audit_and_apply

from treemap.models import Instance, Species, User, Plot, Tree

from treemap.views import (species_list, boundary_to_geojson,
                           boundary_autocomplete, audits, search_tree_benefits)

from treemap.tests import (ViewTestCase, make_instance, make_system_user,
                           make_commander_role, make_officer_role,
                           make_basic_user, make_apprentice_role,
                           make_simple_boundary)


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

    def test_invalid_instance_returns_404(self):
        response = self.client.get('/%s/' % self.instance1.pk)
        self.assertEqual(response.status_code, 200)

        response = self.client.get('/1000/')
        self.assertEqual(response.status_code, 404)


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
        self.test_boundary_hashes = []
        for i, v in enumerate(self.test_boundaries):
            boundary = make_simple_boundary(v, i)
            self.instance.boundaries.add(boundary)
            self.instance.save()
            self.test_boundary_hashes.append({'name': boundary.name,
                                              'category': boundary.category})

    def test_boundary_to_geojson_view(self):
        boundary = make_simple_boundary("Hello, World", 1)
        response = boundary_to_geojson(
            self._make_request(),
            boundary.pk)

        self.assertEqual(response.content, boundary.geom.geojson)

    def test_autocomplete_view(self):
        response = boundary_autocomplete(
            self._make_request({'q': 'fa'}),
            self.instance)

        self.assertEqual(response, self.test_boundary_hashes[2:6])

    def test_autocomplete_view_scoped(self):
        # make a boundary that is not tied to this
        # instance, should not be in the search
        # results
        make_simple_boundary("fargo", 1)
        response = boundary_autocomplete(
            self._make_request({'q': 'fa'}),
            self.instance)

        self.assertEqual(response, self.test_boundary_hashes[2:6])

    def test_autocomplete_view_limit(self):
        response = boundary_autocomplete(
            self._make_request({'q': 'fa',
                                'max_items': 2}),
            self.instance)

        self.assertEqual(response, self.test_boundary_hashes[2:4])


class RecentEditsViewTest(TestCase):
    def setUp(self):
        self.instance = make_instance()

        self.system_user = make_system_user()
        self.system_user.roles.add(make_commander_role(self.instance))

        self.officer = User(username="officer")
        self.officer.save_with_user(self.system_user)
        self.officer.roles.add(make_officer_role(self.instance))

        self.pending_user = make_basic_user(self.instance, "user pdg")
        self.pending_user.roles.add(make_apprentice_role(self.instance))

        self.p1 = Point(-7615441.0, 5953519.0)
        self.factory = RequestFactory()

        self.plot = Plot(geom=self.p1, instance=self.instance)

        self.plot.save_with_user(self.system_user)

        self.tree = Tree(plot=self.plot, instance=self.instance)

        self.tree.save_with_user(self.officer)

        self.tree.diameter = 4
        self.tree.save_with_user(self.officer)

        self.tree.diameter = 5
        self.tree.save_with_user(self.officer)

        self.plot.width = 9
        self.plot.save_with_user(self.system_user)

        self.plot_delta = {
            "model": "Plot",
            "model_id": self.plot.pk,
            "ref_id": None,
            "action": Audit.Type.Update,
            "previous_value": None,
            "current_value": "9",
            "requires_auth": False,
            "user_id": self.system_user.pk,
            "instance_id": self.instance.pk,
            "field": "width"
        }

        self.next_plot_delta = self.plot_delta.copy()
        self.next_plot_delta["current_value"] = "44"
        self.next_plot_delta["previous_value"] = "9"

        self.plot.width = 44
        self.plot.save_with_user(self.system_user)

    def check_audits(self, url, dicts):
        req = self.factory.get(url)
        resulting_audits = [a.audit.dict()
                            for a
                            in audits(req, self.instance)['audits']]

        self.assertEqual(len(dicts), len(resulting_audits))

        for expected, generated in zip(dicts, resulting_audits):
            for k, v in expected.iteritems():
                self.assertEqual(v, generated[k])

    def test_multiple_deltas(self):
        self.check_audits('/blah/?page_size=2',
                          [self.next_plot_delta, self.plot_delta])

    def test_paging(self):
        self.check_audits('/blah/?page_size=1&page=1', [self.plot_delta])

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

    def test_user_filtering(self):

        generic_officer_delta = {
            "user_id": self.officer.pk
        }

        generic_systemuser_delta = {
            "user_id": self.system_user.pk
        }

        self.check_audits(
            "/blah/?user=%s&page_size=3" % self.officer.pk,
            [generic_officer_delta] * 3)

        self.check_audits(
            "/blah/?user=%s&page_size=3" % self.system_user.pk,
            [generic_systemuser_delta] * 3)

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
            "user_id": self.system_user.pk,
            "instance_id": self.instance.pk,
        }

        self.check_audits(
            "/blah/?page_size=2&include_pending=true",
            [pending_plot_delta, self.next_plot_delta])

        self.check_audits(
            "/blah/?page_size=2&include_pending=false",
            [self.next_plot_delta, self.plot_delta])

        a = approve_or_reject_audit_and_apply(
            Audit.objects.all().order_by("-created")[0],
            self.system_user, approved=True)

        pending_plot_delta["ref_id"] = a.pk

        self.check_audits(
            "/blah/?page_size=4&include_pending=false",
            [approve_delta, pending_plot_delta,
             self.next_plot_delta, self.plot_delta])


class SpeciesViewTests(ViewTestCase):
    def setUp(self):
        super(SpeciesViewTests, self).setUp()

        self.species_dict = [
            {'common_name': 'asian cherry', 'genus': 'cherrificus'},
            {'common_name': 'cherrytree', 'genus': 'cherritius',
             'cultivar_name': 'asian'},
            {'common_name': 'elm', 'genus': 'elmitius'},
            {'common_name': 'oak', 'genus': 'acorn',
             'species': 'oakenitus'},
            {'common_name': 'pine', 'genus': 'piniferus',
             'cultivar_name': 'green'},
            {'common_name': 'thing', 'genus': 'elmitius'},
            {'common_name': 'xmas', 'genus': 'christmas',
             'species': 'tree', 'cultivar_name': 'douglass'},
            {'common_name': 'xmas tree', 'genus': 'xmas',
             'species': 'tree', 'cultivar_name': 'douglass'},
        ]
        self.species_json = []
        for i, item in enumerate(self.species_dict):
            species = Species(common_name=item.get('common_name'),
                              genus=item.get('genus'),
                              species=item.get('species'),
                              cultivar_name=item.get('cultivar_name'),
                              symbol=str(i))
            species.save()
            self.species_json.append(
                {'id': species.id,
                 'common_name': species.common_name,
                 'scientific_name': species.scientific_name})

    def test_get_species_list(self):
        self.assertEquals(species_list(self._make_request(), None),
                          self.species_json)

    def test_get_species_list_filter_common(self):
        self.assertEquals(
            species_list(self._make_request({'q': 'pine'}), None),
            self.species_json[4:5])

    def test_get_species_list_filter_scientific(self):
        self.assertEquals(
            species_list(self._make_request({'q': 'lmitiu'}), None),
            [self.species_json[2], self.species_json[5]])

    def test_get_species_list_filter_both_names(self):
        self.assertEquals(
            species_list(self._make_request({'q': 'xmas'}), None),
            self.species_json[6:8])

    def test_get_species_list_max_items(self):
        self.assertEquals(
            species_list(self._make_request({'max_items': 3}), None),
            self.species_json[:3])

    def test_get_species_list_no_split_match(self):
        self.assertEquals(
            species_list(self._make_request({'q': 'asian cherry'}), None),
            self.species_json[:1])

    def test_get_species_list_contains(self):
        self.assertEquals(
            species_list(self._make_request({'q': 'cherry'}), None),
            self.species_json[:2])

    def test_get_species_list_out_of_order_matches(self):
        self.assertEquals(
            species_list(self._make_request({'q': 'cherry asian'}), None),
            self.species_json[:2])

    def test_get_species_list_punctuation_split(self):
        self.assertEquals(
            species_list(self._make_request({'q': "asian,cherry'cherritius'"}),
                         None),
            self.species_json[1:2])

    def test_get_species_list_no_match(self):
        self.assertEquals(
            species_list(self._make_request({'q': 'cherry elm'}), None), [])


class SearchTreeBenefitsTests(ViewTestCase):
    def setUp(self):
        super(SearchTreeBenefitsTests, self).setUp()
        self.instance = make_instance()
        self.system_user = make_system_user()
        self.system_user.roles.add(make_commander_role(self.instance))
        self.p1 = Point(-7615441.0, 5953519.0)
        self.species_good = Species(itree_code='CEM OTHER')
        self.species_good.save()
        self.species_bad = Species()
        self.species_bad.save()

    def make_tree(self, diameter, species):
        plot = Plot(geom=self.p1, instance=self.instance)
        plot.save_with_user(self.system_user)
        tree = Tree(plot=plot, instance=self.instance,
                    diameter=diameter, species=species)
        tree.save_with_user(self.system_user)

    def search_benefits(self):
        request = self._make_request(
            {'q': json.dumps({'tree.readonly': {'IS': False}})})  # all trees
        result = search_tree_benefits(request, self.instance)
        return result

    def test_tree_with_species_and_diameter_included(self):
        self.make_tree(10, self.species_good)
        benefits = self.search_benefits()
        self.assertEqual(benefits['basis']['n_trees_used'], 1)

    def test_tree_without_diameter_ignored(self):
        self.make_tree(None, self.species_good)
        benefits = self.search_benefits()
        self.assertEqual(benefits['basis']['n_trees_used'], 0)

    def test_tree_without_species_ignored(self):
        self.make_tree(10, None)
        benefits = self.search_benefits()
        self.assertEqual(benefits['basis']['n_trees_used'], 0)

    def test_tree_without_itree_code_ignored(self):
        self.make_tree(10, self.species_bad)
        benefits = self.search_benefits()
        self.assertEqual(benefits['basis']['n_trees_used'], 0)

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
