from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import datetime

from django.test import TestCase
from django.contrib.gis.geos import Point

from treemap.models import (Tree, Instance, Plot, FieldPermission, Species,
                            InstanceSpecies, ImportEvent)
from treemap.audit import Audit, ReputationMetric
from treemap.tests import (make_loaded_role, make_instance_and_basic_user,
                           make_instance, make_system_user,
                           make_simple_boundary, make_commander_role)


class HashModelTest(TestCase):
    def setUp(self):
        self.instance, self.user = make_instance_and_basic_user()
        permissions = (
            ('Plot', 'geom', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'width', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'length', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'address_street', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'plot', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'readonly', FieldPermission.WRITE_DIRECTLY))

        self.user.roles.add(
            make_loaded_role(self.instance, "custom", 0, permissions))

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
        self.instance, self.user = make_instance_and_basic_user()

        permissions = (
            ('Plot', 'geom', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'width', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'length', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'address_street', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'address_city', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'address_zip', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'import_event', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'owner_orig_id', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'readonly', FieldPermission.WRITE_DIRECTLY))

        self.user.roles.add(
            make_loaded_role(self.instance, "custom", 0, permissions))

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
        s = Species(genus='Ulmus', cultivar_name='Columella')
        self.assertEquals(s.scientific_name, "Ulmus 'Columella'")

    def test_scientific_name_all(self):
        s = Species(genus='Ulmus', species='rubra', cultivar_name='Columella')
        self.assertEquals(s.scientific_name, "Ulmus rubra 'Columella'")


class ModelUnicodeTests(TestCase):

    def setUp(self):
        self.instance = make_instance(name='Test Instance')

        self.species = Species(common_name='Test Common Name',
                               genus='Test Genus',
                               cultivar_name='Test Cultivar',
                               species='Test Species')
        self.species.save_base()

        self.instance_species = InstanceSpecies(instance=self.instance,
                                                species=self.species,
                                                common_name='Test Common Name')
        self.instance_species.save_base()

        self.user = make_system_user()

        self.import_event = ImportEvent(imported_by=self.user)
        self.import_event.save_base()

        self.plot = Plot(geom=Point(0, 0), instance=self.instance,
                         address_street="123 Main Street")

        self.plot.save_base()

        self.tree = Tree(plot=self.plot, instance=self.instance)

        self.tree.save_base()

        self.boundary = make_simple_boundary("Test Boundary")

        self.role = make_commander_role(self.instance)
        self.role.name = "Test Role"
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
        self.assertEqual(unicode(self.species),
                         "Test Genus Test Species 'Test Cultivar'")

    def test_instance_species_model(self):
        self.assertEqual(unicode(self.instance_species), 'Test Common Name')

    def test_user_model(self):
        self.assertEqual(unicode(self.user), 'system_user')

    def test_import_event_model(self):
        today = datetime.datetime.today().strftime('%Y-%m-%d')
        self.assertEqual(unicode(self.import_event),
                         'system_user - %s' % today)

    def test_plot_model(self):
        self.assertEqual(unicode(self.plot),
                         'X: 0.0, Y: 0.0 - 123 Main Street')

    def test_tree_model(self):
        self.assertEqual(unicode(self.tree), '')

    def test_boundary_model(self):
        self.assertEqual(unicode(self.boundary), 'Test Boundary')

    def test_role_model(self):
        self.assertEqual(unicode(self.role), 'Test Role')

    def test_field_permission_model(self):
        self.assertEqual(unicode(self.field_permission),
                         'Tree.readonly - Test Role')

    def test_audit_model(self):
        self.assertEqual(unicode(self.audit),
                         'ID: 3 Tree.readonly (1) True => False')

    def test_reputation_metric_model(self):
        self.assertEqual(unicode(self.reputation_metric),
                         'Test Instance - Tree - Test Action')


class PlotFullAddressTests(TestCase):

    def setUp(self):
        self.instance = make_instance(name='Test Instance')
        self.plot = Plot(geom=Point(0, 0), instance=self.instance)

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
        self.assertEqual('1234 market st, boomtown, 12345', self.plot.address_full)
