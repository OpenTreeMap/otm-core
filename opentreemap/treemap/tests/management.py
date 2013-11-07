# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
from StringIO import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.contrib.gis.geos import Point

from treemap.models import Instance, Plot, Tree, Species
from treemap.tests import (make_instance, make_user, make_commander_user)
from treemap.management.commands.migrate_otm1 import hash_to_model


class CreateInstanceManagementTest(TestCase):
    def setUp(self):
        self.user = make_user(username='WALL-E', password='EVE')

    def test_can_create_instance(self):
        center = '0,0'
        user = self.user.pk
        name = 'my_instance'
        url_name = 'my-instance'

        self.assertEqual(Instance.objects.count(), 0)
        call_command('create_instance', name, center=center, user=user,
                     url_name=url_name)
        self.assertEqual(Instance.objects.count(), 1)


class RandomTreesManagementTest(TestCase):
    def setUp(self):
        self.instance = make_instance()
        user = make_commander_user(instance=self.instance)
        species = Species(instance=self.instance, otm_code='',
                          common_name='', genus='')
        species.save_with_user(user)

    def run_command(self, **override_options):
        options = {
            'instance': self.instance.pk,
            'n': 1,
        }
        options.update(override_options)
        f = StringIO()
        call_command('random_trees', stdout=f, **options)

    def test_num_trees(self):
        self.run_command(n=1)
        self.assertEqual(self.instance.scope_model(Plot).count(), 1)

        self.run_command(n=2)
        self.assertEqual(self.instance.scope_model(Plot).count(), 3)

    def test_delete(self):
        self.run_command(n=1, delete=False)
        self.assertEqual(self.instance.scope_model(Plot).count(), 1)

        self.run_command(n=1, delete=True)
        self.assertEqual(self.instance.scope_model(Plot).count(), 1)

    def test_tree_prob(self):
        self.run_command(n=1, ptree=0)
        self.assertEqual(self.instance.scope_model(Plot).count(), 1)
        self.assertEqual(self.instance.scope_model(Tree).count(), 0)

        self.run_command(n=1, ptree=100)
        self.assertEqual(self.instance.scope_model(Plot).count(), 2)
        self.assertEqual(self.instance.scope_model(Tree).count(), 1)

    def test_species_prob(self):
        self.run_command(n=1, ptree=100, pspecies=0)
        tree = self.instance.scope_model(Tree).get()
        self.assertIsNone(tree.species)

        self.run_command(n=1, delete=True, ptree=100, pspecies=100)
        tree = self.instance.scope_model(Tree).get()
        self.assertIsNotNone(tree.species)


class MigrationCommandTests(TestCase):
    def setUp(self):
        self.instance = make_instance()
        self.commander = make_commander_user(self.instance)

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
        user = hash_to_model('user', user_dict, self.instance,
                             self.commander)
        user.save_with_user(self.commander)
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
        species = hash_to_model('species', species_dict,
                                self.instance, self.commander)
        species.save_with_user(self.commander)
        self.assertEqual(species.otm_code, 'SAVI')
        self.assertEqual(species.genus, 'Salix')
        self.assertEqual(species.species, 'viminalis')
        self.assertEqual(species.cultivar, '')
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
        plot = hash_to_model('plot', plot_dict, self.instance,
                             self.commander)
        plot.save_with_user(self.commander)

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
        test_plot.save_with_user(self.commander)

        tree_dict = json.loads(self.tree_blob)
        tree = hash_to_model('tree', tree_dict, self.instance,
                             self.commander)
        tree.save_with_user(self.commander)
        self.assertEqual(tree.plot, test_plot)
        self.assertEqual(tree.species, None)
        self.assertEqual(tree.readonly, True)
        self.assertEqual(tree.diameter, 0.2900001566)
        self.assertEqual(tree.canopy_height, None)
        self.assertEqual(tree.date_planted, None)
        self.assertEqual(tree.date_removed, None)
