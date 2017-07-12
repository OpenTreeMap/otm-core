# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from StringIO import StringIO

from django.core.management import call_command

from treemap.models import Instance, Plot, Tree, Species
from treemap.tests import (make_instance, make_user, make_commander_user)
from treemap.tests.base import OTMTestCase


class CreateInstanceManagementTest(OTMTestCase):
    def setUp(self):
        self.user = make_user(username='WALL-E', password='EVE')

    def test_can_create_instance(self):
        user = self.user.username
        name = 'my_instance'

        # Allow test --keepdb to work
        count = Instance.objects.count()
        call_command('create_instance', name, '--center=0,0',
                     '--user=%s' % user, '--url_name=my-instance')
        self.assertEqual(Instance.objects.count(), count + 1)


class RandomTreesManagementTest(OTMTestCase):
    def setUp(self):
        self.instance = make_instance(edge_length=100000)
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
