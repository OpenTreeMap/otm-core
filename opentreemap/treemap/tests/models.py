# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.test import TestCase
from django.test.utils import override_settings
from django.contrib.gis.geos import Point, MultiPolygon
from django.core.exceptions import ValidationError

from treemap.models import (Tree, Instance, Plot, FieldPermission, Species,
                            ITreeRegion)
from treemap.audit import Audit, ReputationMetric, Role
from treemap.tests import (make_instance, make_commander_user,
                           make_user_with_default_role, make_user,
                           make_simple_boundary)


class HashModelTest(TestCase):
    def setUp(self):
        self.instance = make_instance()
        self.user = make_commander_user(self.instance)

        self.p1 = Point(-8515941.0, 4953519.0)
        self.p2 = Point(-7615441.0, 5953519.0)

    def test_changing_fields_changes_hash(self):
        plot = Plot(geom=self.p1, instance=self.instance)
        plot.save_with_user(self.user)

        #
        # Make sure regular field updates change the hash
        #
        h1 = plot.hash
        plot.width = 44
        plot.save_with_user(self.user)
        h2 = plot.hash

        self.assertNotEqual(h1, h2, "Hashes should change")

        h1 = plot.hash
        plot.address_street = "test"
        plot.save_with_user(self.user)
        h2 = plot.hash

        self.assertNotEqual(h1, h2, "Hashes should change")

        #
        # Verify adding a new tree updates the plot hash
        #

        h1 = plot.hash
        tree = Tree(plot=plot,
                    instance=self.instance,
                    readonly=False)
        tree.save_with_user(self.user)
        h2 = plot.hash

        self.assertNotEqual(h1, h2, "Hashes should change")

        #
        # Verify that updating a tree related to a plot also
        # changes the plot hash
        #

        h1 = plot.hash
        tree.readonly = True
        tree.save_with_user(self.user)

        h2 = plot.hash

        self.assertNotEqual(h1, h2, "Hashes should change")


class GeoRevIncr(TestCase):
    def setUp(self):
        self.p1 = Point(-8515941.0, 4953519.0)
        self.p2 = Point(-7615441.0, 5953519.0)
        self.instance = make_instance()
        self.user = make_commander_user(self.instance)

    def hash_and_rev(self):
        i = Instance.objects.get(pk=self.instance.pk)
        return [i.geo_rev_hash, i.geo_rev]

    def test_changing_geometry_updates_counter(self):
        rev1h, rev1 = self.hash_and_rev()

        # Create
        plot1 = Plot(geom=self.p1, instance=self.instance)

        plot1.save_with_user(self.user)

        rev2h, rev2 = self.hash_and_rev()

        self.assertNotEqual(rev1h, rev2h)
        self.assertEqual(rev1 + 1, rev2)

        plot2 = Plot(geom=self.p2, instance=self.instance)

        plot2.save_with_user(self.user)

        rev3h, rev3 = self.hash_and_rev()

        self.assertNotEqual(rev2h, rev3h)
        self.assertEqual(rev2 + 1, rev3)

        # Update
        plot2.geom = self.p1
        plot2.save_with_user(self.user)

        rev4h, rev4 = self.hash_and_rev()

        self.assertNotEqual(rev3h, rev4h)
        self.assertEqual(rev3 + 1, rev4)

        # Delete
        plot2.delete_with_user(self.user)

        rev5h, rev5 = self.hash_and_rev()

        self.assertNotEqual(rev4h, rev5h)
        self.assertEqual(rev4 + 1, rev5)


class SpeciesModelTests(TestCase):
    def test_scientific_name_genus(self):
        s = Species(genus='Ulmus')
        self.assertEquals(s.scientific_name, 'Ulmus')

    def test_scientific_name_genus_species(self):
        s = Species(genus='Ulmus', species='rubra')
        self.assertEquals(s.scientific_name, 'Ulmus rubra')

    def test_scientific_name_genus_cultivar(self):
        s = Species(genus='Ulmus', cultivar='Columella')
        self.assertEquals(s.scientific_name, "Ulmus 'Columella'")

    def test_scientific_name_all(self):
        s = Species(genus='Ulmus', species='rubra', cultivar='Columella')
        self.assertEquals(s.scientific_name, "Ulmus rubra 'Columella'")


class ModelUnicodeTests(TestCase):

    def setUp(self):
        self.instance = make_instance(name='Test Instance')

        self.species = Species(instance=self.instance,
                               common_name='Test Common Name',
                               genus='Test Genus',
                               cultivar='Test Cultivar',
                               species='Test Species')
        self.species.save_base()

        self.user = make_user(username='commander', password='pw')

        self.plot = Plot(geom=Point(0, 0), instance=self.instance,
                         address_street="123 Main Street")

        self.plot.save_base()

        self.tree = Tree(plot=self.plot, instance=self.instance)

        self.tree.save_base()

        self.boundary = make_simple_boundary("Test Boundary")

        self.role = Role(instance=self.instance, name='Test Role',
                         rep_thresh=2)
        self.role.save()

        self.field_permission = FieldPermission(
            model_name="Tree",
            field_name="readonly",
            permission_level=FieldPermission.READ_ONLY,
            role=self.role,
            instance=self.instance)
        self.field_permission.save_base()

        self.audit = Audit(action=Audit.Type.Update,
                           model="Tree",
                           field="readonly",
                           model_id=1,
                           user=self.user,
                           previous_value=True,
                           current_value=False)
        self.audit.save_base()

        self.reputation_metric = ReputationMetric(instance=self.instance,
                                                  model_name="Tree",
                                                  action="Test Action")
        self.reputation_metric.save_base()

    def test_instance_model(self):
        self.assertEqual(unicode(self.instance), "Test Instance")

    def test_species_model(self):
        self.assertEqual(
            unicode(self.species),
            "Test Common Name [Test Genus Test Species 'Test Cultivar']")

    def test_user_model(self):
        self.assertEqual(unicode(self.user), 'commander')

    def test_plot_model(self):
        self.assertEqual(unicode(self.plot),
                         'Plot (0.0, 0.0) 123 Main Street')

    def test_tree_model(self):
        self.assertEqual(unicode(self.tree), '')

    def test_boundary_model(self):
        self.assertEqual(unicode(self.boundary), 'Test Boundary')

    def test_role_model(self):
        self.assertEqual(unicode(self.role), 'Test Role (%s)' % self.role.pk)

    def test_field_permission_model(self):
        self.assertEqual(unicode(self.field_permission),
                         'Tree.readonly - Test Role (%s)' % self.role.pk)

    def test_audit_model(self):
        self.assertEqual(
            unicode(self.audit),
            'pk=%s - action=Update - Tree.readonly:(1) - True => False'
            % self.audit.pk)

    def test_reputation_metric_model(self):
        self.assertEqual(unicode(self.reputation_metric),
                         'Test Instance - Tree - Test Action')


class PlotTest(TestCase):
    def setUp(self):
        self.instance = make_instance()
        self.user = make_commander_user(self.instance)

        self.plot = Plot(geom=Point(0, 0), instance=self.instance)
        self.p = Point(-7615441.0, 5953519.0)

    def test_plot_history_shows_all_trees(self):
        p = Plot(instance=self.instance, geom=self.p)
        p.save_with_user(self.user)

        self.assertEqual(len(p.get_tree_history()), 0)

        t = Tree(plot=p, instance=self.instance)
        t.save_with_user(self.user)
        tpk = t.pk

        self.assertEqual(list(p.get_tree_history()), [tpk])

        t.delete_with_user(self.user)

        self.assertEqual(list(p.get_tree_history()), [tpk])

        t2 = Tree(plot=p, instance=self.instance)
        t2.save_with_user(self.user)

        self.assertEqual(list(p.get_tree_history()), [t2.pk, tpk])

        t3 = Tree(plot=p, instance=self.instance)
        t3.save_with_user(self.user)

        self.assertEqual(list(p.get_tree_history()), [t3.pk, t2.pk, tpk])

    def test_street_address_only(self):
        self.plot.address_street = '1234 market st'
        self.assertEqual('1234 market st', self.plot.address_full)

    def test_city_only(self):
        self.plot.address_city = 'boomtown'
        self.assertEqual('boomtown', self.plot.address_full)

    def test_zip_only(self):
        self.plot.address_zip = '12345'
        self.assertEqual('12345', self.plot.address_full)

    def test_street_address_and_city(self):
        self.plot.address_street = '1234 market st'
        self.plot.address_city = 'boomtown'
        self.assertEqual('1234 market st, boomtown', self.plot.address_full)

    def test_street_address_and_zip(self):
        self.plot.address_street = '1234 market st'
        self.plot.address_zip = '12345'
        self.assertEqual('1234 market st, 12345', self.plot.address_full)

    def test_city_and_zip(self):
        self.plot.address_city = 'boomtown'
        self.plot.address_zip = '12345'
        self.assertEqual('boomtown, 12345', self.plot.address_full)

    def test_all_components(self):
        self.plot.address_street = '1234 market st'
        self.plot.address_city = 'boomtown'
        self.plot.address_zip = '12345'
        self.assertEqual('1234 market st, boomtown, 12345',
                         self.plot.address_full)


class InstanceUserModelTest(TestCase):
    def setUp(self):
        self.instance = make_instance()

    def test_get_instance_user(self):
        user = make_user_with_default_role(self.instance, 'user')
        iuser = user.get_instance_user(self.instance)
        self.assertEqual(iuser.user, user)
        self.assertEqual(iuser.instance, self.instance)

    def test_get_instance_user_fails(self):
        user = make_user(username='joe', password='pw')
        self.assertEqual(user.get_instance_user(self.instance), None)


class InstanceTest(TestCase):

    def test_force_url_name_downcase(self):
        up_name = "BiGNaMe"
        instance = make_instance(url_name=up_name)
        self.assertEqual(instance.url_name, 'bigname')

    def test_can_read_and_write_config(self):
        instance = make_instance()

        instance.config['config_value'] = 'test'
        instance.config['hold up'] = {'nested': 'true'}
        instance.save()

        reloaded_instance = Instance.objects.get(pk=instance.pk)

        self.assertEqual(reloaded_instance.config,
                         {'config_value': 'test',
                          'hold up': {'nested': 'true'}})

    def test_config_accessors_work(self):
        instance = make_instance()
        instance.mobile_search_fields = ['field 1', 'field 2']
        instance.save()

        reloaded_instance = Instance.objects.get(pk=instance.pk)

        self.assertEqual(reloaded_instance.mobile_search_fields,
                         ['field 1', 'field 2'])

        instance.mobile_search_fields.append('field 3')
        instance.save()

        reloaded_instance = Instance.objects.get(pk=instance.pk)

        self.assertEqual(reloaded_instance.mobile_search_fields,
                         ['field 1', 'field 2', 'field 3'])

    def test_verify_cant_do_lookup(self):
        self.assertRaises(TypeError, Instance.objects.filter, config='test')

    def test_url_name_cannot_be_empty(self):
        with self.assertRaises(ValidationError):
            make_instance(url_name='')

    def test_url_name_does_not_allow_leading_number(self):
        with self.assertRaises(ValidationError):
            make_instance(url_name='0a')

    def test_url_name_does_not_allow_leading_hyphen(self):
        with self.assertRaises(ValidationError):
            make_instance(url_name='-a')

    @override_settings(RESERVED_INSTANCE_URL_NAMES=('jsi18n',))
    def test_url_name_does_not_allow_reserved_words(self):
        with self.assertRaises(ValidationError):
            make_instance(url_name='jsi18n')

    def test_url_name_allows_lcase(self):
        make_instance(url_name='mymap')

    def test_url_name_allows_lcase_numbers_and_hyphens(self):
        make_instance(url_name='my-map-42')

    def test_url_name_must_be_unique(self):
        make_instance(url_name='philly')
        self.assertRaises(make_instance, url_name='philly')

    def test_has_itree_region_with_nothing(self):
        instance = make_instance()
        self.assertEqual(instance.has_itree_region(), False)

    def test_has_itree_region_with_default(self):
        instance = make_instance()
        instance.itree_region_default = 'PiedmtCLT'
        instance.save()
        self.assertEqual(instance.has_itree_region(), True)

    def test_has_itree_region_with_intersects(self):
        p1 = Point(0, 0)
        instance = make_instance(point=p1)
        instance.save()

        ITreeRegion.objects.create(geometry=MultiPolygon((p1.buffer(10))))

        self.assertEqual(instance.has_itree_region(), True)

    def test_advanced_search_fields(self):
        instance = make_instance()
        self.assertEqual(instance.advanced_search_fields,
                         {'standard': [], 'missing': [],
                          'display': [], 'stewardship': []})
