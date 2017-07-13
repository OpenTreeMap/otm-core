
from django.http import Http404, HttpResponse
import json

from django.test import SimpleTestCase
from django.core.exceptions import PermissionDenied

from treemap.models import Species
from treemap.tests import make_request, make_instance, make_plain_user
from treemap.tests.base import OTMTestCase

from modeling.models import Plan
from modeling.views import (add_plan, get_plan,
                            update_plan, delete_plan, get_plans_context)
from modeling.run_model.GrowthAndMortalityModel import GrowthAndMortalityModel
from modeling.run_model.GrowthModelUrbanTreeDatabase import bisect
from modeling.run_model.MortalityModelUrbanTreeDatabase import DIAMETER_BREAKS


class TestPlanCrud(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.user = make_plain_user('a', 'a')
        self.user2 = make_plain_user('b', 'b')

        self.plan_spec = {
            'name': 'My Plan',
            'description': 'A fascinating plan',
            'is_published': True,
            'scenarios': {
                'scenarios': [],
                'currentScenarioId': None
            }
        }
        request = make_request(method='POST', user=self.user,
                               body=json.dumps(self.plan_spec)),
        result = add_plan(request[0], self.instance)
        self.plan_id = result['id']

    def _get_plan(self, user):
        request = make_request(user=user)
        return get_plan(request, self.instance, self.plan_id)

    def _update_plan(self, updates, user=None, force=False):
        user = user or self.user
        # Need to match the client, which places the force parameter in the
        # query string, not the request body
        path = '/hello?force=1' if force else '/hello'
        request = make_request(path=path, method='PUT', user=user,
                               body=json.dumps(updates))
        result = update_plan(request, self.instance, self.plan_id)
        if isinstance(result, HttpResponse):
            return result  # there was an error
        else:
            return self._get_plan(self.user)

    def _delete_plan(self, user):
        request = make_request(method='DELETE', user=user)
        delete_plan(request, self.instance, self.plan_id)

    def _assert_plans_match(self, spec, result):
        for key, value in spec.iteritems():
            self.assertEqual(value, result[key],
                             "Mismatch in plan field '%s'" % key)

    def test_get_plan(self):
        plan = self._get_plan(self.user)
        self._assert_plans_match(self.plan_spec, plan)

    def test_update_plan(self):
        updates = {'name': 'foo', 'is_published': False}
        plan = self._update_plan(updates)
        self.plan_spec.update(updates)
        self._assert_plans_match(self.plan_spec, plan)

    def test_delete_plan(self):
        self._delete_plan(self.user)
        self.assertFalse(Plan.objects.all().exists())

    def test_cant_get_private_plan(self):
        self._update_plan({'is_published': False})
        self.assertRaises(PermissionDenied, self._get_plan, self.user2)

    def test_cant_update_someone_elses_plan(self):
        self.assertRaises(Http404,
                          self._update_plan, {'name': 'foo'}, self.user2)

    def test_cant_delete_someone_elses_plan(self):
        self.assertRaises(Http404, self._delete_plan, self.user2)

    def test_revision_number(self):
        plan = self._get_plan(self.user)
        revision = plan['revision']
        updates = {'name': 'foo', 'revision': revision}

        # Updating increments the revision
        result = self._update_plan(updates)
        self.assertEqual(result['revision'], revision + 1)

        # Trying to update with the stale revision number causes an error
        result = self._update_plan(updates)
        self.assertTrue(type(result) is HttpResponse,
                        'Expected conflicting update to return an '
                        'HttpResponse')
        self.assertEqual(result.status_code, 409)

        # Forcing an update succeeds even with the stale revision number
        result = self._update_plan(updates, force=True)
        self.assertEqual(result['revision'], revision + 2)


class TestPlansList(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.user_a = make_plain_user('a', 'a')
        self.user_b = make_plain_user('b', 'b')
        self.plan_a1 = self._make_plan('a1', self.user_a, True)
        self.plan_a2 = self._make_plan('a2', self.user_a, False)
        self.plan_b1 = self._make_plan('b1', self.user_b, True)
        self.plan_b2 = self._make_plan('b2', self.user_b, False)

    def _make_plan(self, name, owner, is_published, **kwargs):
        return Plan.objects.create(instance=self.instance,
                                   owner=owner,
                                   name=name,
                                   is_published=is_published,
                                   **kwargs)

    def _get_plans(self, **params):
        context = get_plans_context(
            make_request(params, self.user_a), self.instance)
        return list(context['plans'])

    def test_user_filter(self):
        plans = self._get_plans()
        self.assertEqual(set(plans), {self.plan_a1, self.plan_a2})

    def test_public_filter(self):
        plans = self._get_plans(filter='public')
        self.assertEqual(set(plans), {self.plan_b1})

    def test_sort_by_modification_time(self):
        plans = self._get_plans()
        self.assertEqual(plans, [self.plan_a2, self.plan_a1])

    def test_sort_by_name(self):
        plans = self._get_plans(sort='name')
        self.assertEqual(plans, [self.plan_a1, self.plan_a2])

    def test_sort_by_name_reversed(self):
        plans = self._get_plans(sort='-name')
        self.assertEqual(plans, [self.plan_a2, self.plan_a1])


class TestGrowthModel(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.instance.itree_region_default = 'GulfCoCHS'
        self.instance.save()

        self.maple = Species(otm_code='ACRU',
                             genus='Acer',
                             species='rubrum')
        self.honeylocust = Species(otm_code='GLTR',
                                   genus='Gleditsia',
                                   species='triacanthos')

        self.model_params = \
            GrowthAndMortalityModel.get_default_params(self.instance)

        # This minimal model runs for 1 year and kills no trees.
        # Different tests add and exercise different parameters.
        self.scenario = {
            'groups': [],
            'trees': [],
            'years': 1,
            'replant_years': 0
        }

    def add_tree(self, diameter, species):
        self.scenario['trees'].append(
            {
                'count': 1,
                'species': species,
                'diameter': diameter
            }
        )

    def add_group(self, count, name=1, diameter=10, species=None):
        self.scenario['groups'].append(
            {
                'name': name,
                'species': species or self.maple,
                'diameter': diameter,
                'count': count
            }
        )

    def run_model(self, expected_n_trees=1, expected_n_years=1):
        growth_model = GrowthAndMortalityModel(self.model_params,
                                               self.instance)
        yearly_counts, planted_trees = growth_model.run(self.scenario)
        self.assertEqual(len(yearly_counts), expected_n_years + 1)
        self.assertEqual(yearly_counts[-1], expected_n_trees)
        return planted_trees


class TestBisect(SimpleTestCase):
    def setUp(self):
        self.choices = range(10)
        self.identity = lambda n: n
        self.tolerance = 0
        self.max_iterations = 15

    def run_bisect(self, target):
        return bisect(self.identity, 0, len(self.choices), target,
                      self.max_iterations, self.tolerance)

    def assert_bisect_exception(self, target):
        with self.assertRaises(Exception):
            return self.run_bisect(target)

    def test_bisect_bounds(self):
        """
        Test that an exception is thrown if the function will never
        produce the target value within the constraint boundaries.
        """
        self.assert_bisect_exception(-1)
        self.assert_bisect_exception(len(self.choices))

    def test_bisect_discrete(self):
        """
        Test that bisect returns the correct index value when the
        function produces an exact match against our target.
        """
        result = self.run_bisect(5)
        self.assertEqual(5, result)

    def test_bisect_continuous_tolerance(self):
        """
        Test that bisect interpolates the correct index value, within
        an acceptable tolerance level, when the function does not
        produce an exact match against our target.
        """
        self.tolerance = 0.1
        result = self.run_bisect(1.5)
        self.assertAlmostEqual(1.5, result, delta=self.tolerance)

    def test_bisect_continuous_no_tolerance(self):
        """
        Test that an exception is thrown when trying to interpolate
        continuous values with a tolerance of 0.
        """
        self.assert_bisect_exception(1.5)


class TestGrowthModelUrbanTreeDatabase(TestGrowthModel):
    # Parameters for our test tree, a Honeylocust in GulfCoCHS:
    #   age_to_diameter() is a quadratic function
    #   min_age =  2.53   (min age suggested for use with UTD equation)
    #   max_age = 34.54   (max age suggested for use with UTD equation)
    #   min_diameter =  5.90 cm  (diameter at min_age)
    #   max_diameter = 32.36 cm  (diameter at max_age)
    #   growth_rate_at_min_age = 1.28 cm/year

    def test_growth_below_min_age(self):
        # Initial diameter of 5 cm is below the min diameter, so
        # initial age is computed using linear interpolation,
        # and the first year of growth uses growth_rate_at_min_age
        self.add_tree(5, self.honeylocust)
        tree = self.run_model(expected_n_trees=1)[0]
        self.assertAlmostEqual(tree.initial_age, 1.83, delta=.01)
        self.assertAlmostEqual(tree.diameter - 5, 1.28, delta=.01)

    def test_growth_above_min_age(self):
        # Initial diameter of 10 cm is above the min diameter, so
        # initial age is computed using bisection.
        self.add_tree(10, self.honeylocust)
        tree = self.run_model(expected_n_trees=1)[0]
        self.assertAlmostEqual(tree.initial_age, 5.84, delta=.01)
        self.assertAlmostEqual(tree.diameter - 10, 1.22, delta=.01)

    def test_growth_above_max_age(self):
        # Initial diameter of 35 cm is above the max diameter
        self.add_tree(35, self.honeylocust)
        with self.assertRaises(Exception):
            self.run_model()


class TestMortalityModelUrbanTreeDatabase(TestGrowthModel):
    def test_invalid_mortality_mode(self):
        """
        Test that model fails to run if incorrect mortality mode is used.
        """
        self.model_params['mortality']['params']['mode'] = 'foo'
        with self.assertRaises(Exception):
            self.add_tree(10, self.maple)
            self.run_model()

    def test_default_mortality_none(self):
        """
        Test that no trees die with 0% annual mortality rate.
        """
        self.model_params['mortality']['params']['default'] = 0
        self.add_group(count=10, species=self.maple)
        self.run_model(expected_n_trees=10)

    def test_default_mortality_all(self):
        """
        Test that all trees die with 100% annual mortality rate.
        """
        self.model_params['mortality']['params']['default'] = 100
        self.add_group(count=10, species=self.maple)
        self.run_model(expected_n_trees=0)

    def test_custom_mortality_none(self):
        """
        Test that all trees live.
        """
        params = self.model_params['mortality']['params']
        params['mode'] = 'speciesAndDiameters'
        params['speciesAndDiameters'] = [
            {'otmCode': 'default', 'mortalityRates': [0, 0, 0, 0]},
        ]
        self.add_tree(DIAMETER_BREAKS[0], self.maple)
        self.add_tree(DIAMETER_BREAKS[1], self.maple)
        self.add_tree(DIAMETER_BREAKS[2], self.maple)
        self.add_tree(DIAMETER_BREAKS[2] + 1, self.maple)
        self.run_model(expected_n_trees=4)

    def test_custom_mortality_small(self):
        """
        Test that only small trees die.
        """
        params = self.model_params['mortality']['params']
        params['mode'] = 'speciesAndDiameters'
        params['speciesAndDiameters'] = [
            {'otmCode': 'default', 'mortalityRates': [100, 0, 0, 0]},
        ]
        self.add_tree(DIAMETER_BREAKS[0], self.maple)
        self.add_tree(DIAMETER_BREAKS[1], self.maple)
        self.add_tree(DIAMETER_BREAKS[2], self.maple)
        self.add_tree(DIAMETER_BREAKS[2] + 1, self.maple)
        self.run_model(expected_n_trees=3)

    def test_custom_mortality_medium(self):
        """
        Test that only medium trees die.
        """
        params = self.model_params['mortality']['params']
        params['mode'] = 'speciesAndDiameters'
        params['speciesAndDiameters'] = [
            {'otmCode': 'default', 'mortalityRates': [0, 100, 0, 0]},
        ]
        self.add_tree(DIAMETER_BREAKS[0], self.maple)
        self.add_tree(DIAMETER_BREAKS[1], self.maple)
        self.add_tree(DIAMETER_BREAKS[2], self.maple)
        self.add_tree(DIAMETER_BREAKS[2] + 1, self.maple)
        self.run_model(expected_n_trees=3)

    def test_custom_mortality_large(self):
        """
        Test that only large trees die.
        """
        params = self.model_params['mortality']['params']
        params['mode'] = 'speciesAndDiameters'
        params['speciesAndDiameters'] = [
            {'otmCode': 'default', 'mortalityRates': [0, 0, 100, 0]},
        ]
        self.add_tree(DIAMETER_BREAKS[0], self.maple)
        self.add_tree(DIAMETER_BREAKS[1], self.maple)
        self.add_tree(DIAMETER_BREAKS[2], self.maple)
        self.add_tree(DIAMETER_BREAKS[2] + 1, self.maple)
        self.run_model(expected_n_trees=3)

    def test_custom_mortality_very_large(self):
        """
        Test that only very large trees die.
        """
        params = self.model_params['mortality']['params']
        params['mode'] = 'speciesAndDiameters'
        params['speciesAndDiameters'] = [
            {'otmCode': 'default', 'mortalityRates': [0, 0, 0, 100]},
        ]
        self.add_tree(DIAMETER_BREAKS[0], self.maple)
        self.add_tree(DIAMETER_BREAKS[1], self.maple)
        self.add_tree(DIAMETER_BREAKS[2], self.maple)
        self.add_tree(DIAMETER_BREAKS[2] + 1, self.maple)
        self.run_model(expected_n_trees=3)

    def test_custom_mortality_species(self):
        """
        Test that all maple trees die and all honeylocust trees live.
        """
        params = self.model_params['mortality']['params']
        params['mode'] = 'speciesAndDiameters'
        params['speciesAndDiameters'] = [
            {'otmCode': 'default', 'mortalityRates': [100, 100, 100, 100]},
            {'otmCode': self.maple.otm_code, 'mortalityRates': [0, 0, 0, 0]},
        ]
        self.add_group(count=3, species=self.maple)
        self.add_group(count=5, species=self.honeylocust)
        self.run_model(expected_n_trees=3)

    def _count_dead_trees(self, trees, species):
        dead = [t for t in trees if not t.is_alive and t.species == species]
        return len(dead)

    def test_egalitarian_death_default_mortality(self):
        """
        Test that with default mortality, trees from different species die at
        the same rate.
        """
        self.add_group(count=20, species=self.maple)
        self.add_group(count=20, species=self.honeylocust)
        trees = self.run_model(expected_n_trees=38)
        self.assertEqual(self._count_dead_trees(trees, self.maple), 1)
        self.assertEqual(self._count_dead_trees(trees, self.honeylocust), 1)

    def test_egalitarian_death_custom_mortality(self):
        """
        Test that with custom mortality, trees from different species die at
        the same rate.
        """
        params = self.model_params['mortality']['params']
        params['mode'] = 'speciesAndDiameters'
        params['speciesAndDiameters'] = [
            {'otmCode': 'default', 'mortalityRates': [20, 20, 20, 20]},
        ]
        self.add_group(count=20, species=self.maple)
        self.add_group(count=20, species=self.honeylocust)
        trees = self.run_model(expected_n_trees=32)
        self.assertEqual(self._count_dead_trees(trees, self.maple), 4)
        self.assertEqual(self._count_dead_trees(trees, self.honeylocust), 4)

    def test_remainder(self):
        """
        Test that tree count is as expected after 30 years
        """
        # Expected count when running 100 trees for 30 years at 5% mortality
        expected_tree_count = int(round(100 * .95 ** 30))

        self.scenario['years'] = 30
        self.add_group(count=100, species=self.maple)
        self.run_model(expected_n_trees=expected_tree_count,
                       expected_n_years=30)


class TestGrowthAndMortalityModel(TestGrowthModel):
    def test_full_growth_model_validates(self):
        params = GrowthAndMortalityModel.get_default_params(self.instance)
        GrowthAndMortalityModel(params, self.instance)

    def test_simple_growth_model_validates(self):
        GrowthAndMortalityModel(self.model_params, self.instance)

    def test_growth_interpolation(self):
        self.add_tree(20, self.maple)
        tree = self.run_model()[0]
        self.assertAlmostEqual(tree.diameter, 21.8, delta=0.1)

    def test_replanting(self):
        """
        Test that tree counts for first 2 years are constant, due to
        replanting, but then drop to 0 due to 100% mortality rate.
        """
        self.add_group(8, species=self.maple, diameter=10)
        self.scenario['years'] = 3
        self.scenario['replant_years'] = 1
        self.model_params['mortality']['params']['default'] = 100
        growth_model = GrowthAndMortalityModel(self.model_params,
                                               self.instance)
        yearly_counts, planted_trees = growth_model.run(self.scenario)
        self.assertEqual(yearly_counts, [8, 8, 0, 0])
        self.assertEqual(len(planted_trees), 16)
        for tree in planted_trees:
            self.assertEqual(tree.initial_diameter, 10)
