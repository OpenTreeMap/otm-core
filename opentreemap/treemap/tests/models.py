from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import datetime

import json

from django.test import TestCase
from django.contrib.gis.geos import Point

from treemap.models import (Tree, Instance, Plot, FieldPermission, Species,
                            InstanceSpecies, ImportEvent, User)
from treemap.audit import Audit, ReputationMetric
from treemap.tests import (make_loaded_role, make_instance_and_basic_user,
                           make_instance, make_system_user,
                           make_simple_boundary, make_commander_role,
                           make_instance_and_system_user, make_god_role)

from treemap.management.commands.migrate_otm1 import hash_to_model


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
        self.assertEqual(
            unicode(self.species),
            "Test Common Name [Test Genus Test Species 'Test Cultivar']")

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
        self.assertEqual('1234 market st, boomtown, 12345',
                         self.plot.address_full)


class MigrationCommandTests(TestCase):
    def setUp(self):
        self.instance, self.user = make_instance_and_system_user()

        self.god = User(username="god")
        self.god.save_with_user(self.user)
        self.god.roles.add(make_god_role(self.instance))

        self.tree_blob = """
        {"pk": 95,
        "model": "treemap.tree",
        "fields": {
        "dbh": 0.2900001566,
        "last_updated": "2013-05-10 11:28:54",
        "tree_owner": "Open University",
        "date_planted": null,
        "import_event": 7,
        "height": 12.0,
        "orig_species": null,
        "sponsor": null,
        "s_order": null,
        "species": 85,
        "steward_name": null,
        "plot": 95,
        "pests": null,
        "species_other1": null,
        "readonly": true,
        "species_other2": null,
        "condition": null,
        "projects": "",
        "steward_user": null,
        "photo_count": 0,
        "date_removed": null,
        "canopy_height": null,
        "last_updated_by": 1,
        "canopy_condition": null,
        "present": true,
        "url": null}}"""

        self.plot_blob = """
        {"pk": 29895,
        "model": "treemap.plot",
        "fields": {
        "last_updated": "2013-04-11 17:20:36",
        "geocoded_lat": null,
        "geocoded_address": "",
        "owner_orig_id": "84368",
        "import_event": 61,
        "neighborhood": [283],
        "address_street": null,
        "owner_additional_properties": null,
        "zipcode": "12345",
        "width": 5.2,
        "readonly": true,
        "type": null,
        "sidewalk_damage": null,
        "last_updated_by": 1,
        "data_owner": 31,
        "present": true,
        "address_zip": null,
        "owner_additional_id": null,
        "address_city": "123 Main Street",
        "neighborhoods": " 283",
        "geometry": "POINT (0.0 0.0)",
        "length": 1.3,
        "powerline_conflict_potential": null,
        "geocoded_accuracy": null,
        "geocoded_lon": null}}
        """

        self.user_blob = """
        {"pk": 17,
        "model": "auth.user",
        "fields":
        {"username": "kyle_reese",
        "first_name": "Kyle",
        "last_name": "Reese",
        "is_active": true,
        "is_superuser": false,
        "is_staff": false,
        "last_login": "2012-12-13 10:42:13",
        "groups": [],
        "user_permissions": [],
        "password": "sha1$f2a24$3ce09546b51c55642ed21a802510e096560ad322",
        "email": "kyle@the_resistence.org",
        "date_joined": "2012-12-13 10:42:13"}}"""

        self.species_blob = """
        {"pk": 229,
        "model": "treemap.species",
        "fields":
        {"v_max_height": null,
        "family": null,
        "scientific_name": "Salix viminalis",
        "alternate_symbol": null,
        "v_max_dbh": null,
        "tree_count": 21,
        "flower_conspicuous": null,
        "common_name": "Basket willow",
        "plant_guide": null,
        "fall_conspicuous": null,
        "species": "viminalis",
        "other_part_of_name": null,
        "wildlife_value": null,
        "fact_sheet": "http://eol.org/search?q=Salix viminalis",
        "cultivar_name": "",
        "native_status": "False",
        "palatable_human": null,
        "itree_code": "BDS OTHER",
        "symbol": "SAVI",
        "fruit_period": null,
        "resource": [32],
        "v_multiple_trunks": null,
        "gender": "",
        "bloom_period": null,
        "genus": "Salix"}}
        """

    def test_user_hash_to_model(self):
        user_dict = json.loads(self.user_blob)
        user = hash_to_model(User, 'user', user_dict, self.instance,
                             self.god)
        user.save_with_user(self.god)
        self.assertEqual(user.pk, 17)
        self.assertEqual(user.username, "kyle_reese")
        self.assertEqual(user.first_name, "Kyle")
        self.assertEqual(user.last_name, "Reese")
        self.assertEqual(user.email, "kyle@the_resistence.org")
        self.assertEqual(user.is_active, True)
        self.assertEqual(user.is_superuser, False)
        self.assertEqual(user.is_staff, False)
        self.assertEqual(user.groups.count(), 0)
        self.assertEqual(user.user_permissions.count(), 0)

    def test_species_hash_to_model(self):
        species_dict = json.loads(self.species_blob)
        species = hash_to_model(Species, 'species', species_dict,
                                self.instance, self.god)
        species.save()
        self.assertEqual(species.symbol, 'SAVI')
        self.assertEqual(species.genus, 'Salix')
        self.assertEqual(species.species, 'viminalis')
        self.assertEqual(species.cultivar_name, '')
        self.assertEqual(species.gender, '')
        self.assertEqual(species.common_name, "Basket willow")
        self.assertEqual(species.native_status, 'False')
        self.assertEqual(species.bloom_period, None)
        self.assertEqual(species.fruit_period, None)
        self.assertEqual(species.fall_conspicuous, None)
        self.assertEqual(species.flower_conspicuous, None)
        self.assertEqual(species.palatable_human, None)
        self.assertEqual(species.wildlife_value, None)
        self.assertEqual(species.fact_sheet,
                         'http://eol.org/search?q=Salix viminalis')
        self.assertEqual(species.plant_guide, None)

    def test_plot_hash_to_model(self):
        plot_dict = json.loads(self.plot_blob)
        plot = hash_to_model(Plot, 'plot', plot_dict, self.instance,
                             self.god)
        plot.save_with_user(self.god)

        self.assertEqual(plot.owner_orig_id, '84368')
        self.assertEqual(plot.address_street, None)
        self.assertEqual(plot.address_zip, None)
        self.assertEqual(plot.width, 5.2)
        self.assertEqual(plot.readonly, True)
        self.assertEqual(plot.address_city, "123 Main Street")
        self.assertEqual(plot.geom, Point(0, 0))
        self.assertEqual(plot.length, 1.3)

    def test_tree_hash_to_model(self):
        test_plot = Plot(geom=Point(0, 0), instance=self.instance)
        test_plot.id = 95
        test_plot.save_with_user(self.god)

        tree_dict = json.loads(self.tree_blob)
        tree = hash_to_model(Tree, 'tree', tree_dict, self.instance,
                             self.god)
        tree.save_with_user(self.god)
        self.assertEqual(tree.pk, 95)
        self.assertEqual(tree.plot, test_plot)
        self.assertEqual(tree.species, None)
        self.assertEqual(tree.readonly, True)
        self.assertEqual(tree.diameter, 0.2900001566)
        self.assertEqual(tree.canopy_height, None)
        self.assertEqual(tree.date_planted, None)
        self.assertEqual(tree.date_removed, None)
