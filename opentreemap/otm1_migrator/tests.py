# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
from copy import copy

from django.contrib.gis.geos import Point

from treemap.models import Plot, Tree, Species, User, TreePhoto
from treemap.tests import (make_instance, make_commander_user,
                           LocalMediaTestCase, media_dir)

from otm1_migrator.management.commands.perform_migration import (
    hash_to_model, hashes_to_saved_objects)


class MigrationCommandTests(LocalMediaTestCase):
    def setUp(self):
        super(MigrationCommandTests, self).setUp()

        self.instance = make_instance()
        self.commander = make_commander_user(self.instance)

        self.photo_blob = """
        {"pk": 54,
        "model": "treemap.treephoto",
        "fields": {
        "comment": "",
        "title": "",
        "reported_by": 1,
        "photo": "%s",
        "tree": 1,
        "reported": "2012-06-17 13:44:30"}}
        """

        self.tree_blob = """
        {"pk": 95,
        "model": "treemap.tree",
        "fields": {
        "dbh": 0.2900001566,
        "last_updated": "2013-05-10 11:28:54",
        "tree_owner": "Open University",
        "date_planted": null,
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
        "email": "kyle@theresistence.org",
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
        "other_part_of_name": "",
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
        "genus": "Eucalyptus"}}
        """

    def test_user_hash_to_model(self):
        user_dict = json.loads(self.user_blob)
        user = hash_to_model('user', user_dict, self.instance,
                             self.commander)

        user.save_with_user(self.commander)

        user = User.objects.get(pk=user.pk)
        self.assertEqual(user.username, "kyle_reese")
        self.assertEqual(user.first_name, "Kyle")
        self.assertEqual(user.last_name, "Reese")
        self.assertEqual(user.email, "kyle@theresistence.org")
        self.assertEqual(user.is_active, True)
        self.assertEqual(user.is_superuser, False)
        self.assertEqual(user.is_staff, False)
        self.assertEqual(user.groups.count(), 0)
        self.assertEqual(user.user_permissions.count(), 0)

    def test_dont_add_duplicates(self):
        species_dict = json.loads(self.species_blob)
        species_dicts = [species_dict, species_dict, species_dict]

        role = self.commander.instanceuser_set.get(
            instance=self.instance).role

        hashes_to_saved_objects("species", species_dicts, {},
                                self.instance, self.commander,
                                commander_role=role,
                                save_with_user=True)

        allspecies = Species.objects.filter(instance=self.instance)
        self.assertEqual(len(allspecies), 1)

    def test_species_hash_to_model(self):
        species_dict = json.loads(self.species_blob)
        role = self.commander.instanceuser_set.get(
            instance=self.instance).role

        hashes_to_saved_objects("species", [species_dict], {},
                                self.instance, self.commander,
                                commander_role=role,
                                save_with_user=True)

        allspecies = Species.objects.filter(instance=self.instance)
        self.assertEqual(len(allspecies), 1)

        species = allspecies[0]

        self.assertEqual(species.otm_code, 'EUVI')
        self.assertEqual(species.genus, 'Eucalyptus')
        self.assertEqual(species.species, 'viminalis')
        self.assertEqual(species.cultivar, '')
        self.assertEqual(species.gender, '')
        self.assertEqual(species.common_name, "Basket willow")
        self.assertEqual(species.native_status, False)
        self.assertEqual(species.bloom_period, None)
        self.assertEqual(species.fruit_period, None)
        self.assertEqual(species.fall_conspicuous, None)
        self.assertEqual(species.flower_conspicuous, None)
        self.assertEqual(species.palatable_human, None)
        self.assertEqual(species.wildlife_value, None)
        self.assertEqual(species.fact_sheet,
                         'http://eol.org/search?q=Salix viminalis')
        self.assertEqual(species.plant_guide, None)

    @media_dir
    def test_treephoto_hash_to_model(self):
        plot = Plot(geom=Point(0, 0), instance=self.instance)
        plot.save_with_user(self.commander)
        tree = Tree(plot=plot, instance=self.instance)
        tree.save_with_user(self.commander)

        ipath = self.resource_path('tree1.gif')

        tp_dict = json.loads(self.photo_blob % ipath)

        role = self.commander.instanceuser_set.get(
            instance=self.instance).role

        self.assertEqual(TreePhoto.objects.count(), 0)

        hashes_to_saved_objects("treephoto", [tp_dict],
                                {'tree': {1: tree.pk},
                                 'user': {1: self.commander.pk}},
                                self.instance, self.commander,
                                commander_role=role,
                                save_with_user=True,
                                treephoto_path='')

        self.assertEqual(TreePhoto.objects.count(), 1)
        photo = TreePhoto.objects.all()[0]

        self.assertIsNotNone(photo.image)
        self.assertIsNotNone(photo.thumbnail)

    def test_plot_hash_to_model(self):
        plot_dict = json.loads(self.plot_blob)
        plot = hash_to_model('plot', plot_dict, self.instance,
                             self.commander)
        # test that the plot geom is transformed as follows
        test_geom = copy(plot.geom)
        test_geom.transform(3857)
        plot.save_with_user(self.commander)
        plot = Plot.objects.get(pk=plot.pk)
        self.assertEqual(plot.owner_orig_id, '84368')
        self.assertEqual(plot.address_street, None)
        self.assertEqual(plot.address_zip, None)
        self.assertEqual(plot.width, 5.2)
        self.assertEqual(plot.readonly, True)
        self.assertEqual(plot.address_city, "123 Main Street")
        self.assertEqual(plot.geom.x, test_geom.x)
        self.assertEqual(plot.geom.y, test_geom.y)
        self.assertEqual(plot.length, 1.3)

    def test_tree_hash_to_model(self):
        test_plot = Plot(geom=Point(0, 0), instance=self.instance)
        test_plot.id = 95
        test_plot.save_with_user(self.commander)

        tree_dict = json.loads(self.tree_blob)
        tree = hash_to_model('tree', tree_dict, self.instance,
                             self.commander)
        tree.save_with_user(self.commander)
        tree = Tree.objects.get(pk=tree.pk)
        self.assertEqual(tree.plot, test_plot)
        self.assertEqual(tree.species, None)
        self.assertEqual(tree.readonly, True)
        self.assertEqual(tree.diameter, 0.2900001566)
        self.assertEqual(tree.canopy_height, None)
        self.assertEqual(tree.date_planted, None)
        self.assertEqual(tree.date_removed, None)
