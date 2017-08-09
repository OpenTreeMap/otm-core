# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import random
import math

from django.contrib.gis.geos import Point

from treemap.models import Plot, Tree, Species

from treemap.management.util import InstanceDataCommand


class Command(InstanceDataCommand):

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument(
            '-r', '--radius',
            action='store',
            type=int,
            dest='radius',
            default=5000,
            help='Number of meters from the center'),
        parser.add_argument(
            '-n', '--number-of-trees',
            action='store',
            type=int,
            dest='n',
            default=100000,
            help='Number of trees to create'),
        parser.add_argument(
            '-p', '--prob-of-tree',
            action='store',
            type=int,
            dest='ptree',
            default=50,
            help='Probability that a given plot will have a tree (0-100)'),
        parser.add_argument(
            '-s', '--prob-of-species',
            action='store',
            type=int,
            dest='pspecies',
            default=50,
            help='Probability that a given tree will have a species (0-100)'),
        parser.add_argument(
            '-D', '--prob-of-diameter',
            action='store',
            type=int,
            dest='pdiameter',
            default=10,
            help='Probability that a given tree will have a diameter (0-100)')

    def handle(self, *args, **options):
        """ Create some seed data """
        instance, user = self.setup_env(*args, **options)

        species_qs = instance.scope_model(Species)

        n = options['n']
        self.stdout.write("Will create %s plots" % n)

        get_prob = lambda option: float(min(100, max(0, option))) / 100.0
        tree_prob = get_prob(options['ptree'])
        species_prob = get_prob(options['pspecies'])
        diameter_prob = get_prob(options['pdiameter'])
        max_radius = options['radius']

        center_x = instance.center.x
        center_y = instance.center.y

        ct = 0
        cp = 0
        for i in xrange(0, n):
            mktree = random.random() < tree_prob
            radius = random.gauss(0.0, max_radius)
            theta = random.random() * 2.0 * math.pi

            x = math.cos(theta) * radius + center_x
            y = math.sin(theta) * radius + center_y

            plot = Plot(instance=instance,
                        geom=Point(x, y))

            plot.save_with_user(user)
            cp += 1

            if mktree:
                add_species = random.random() < species_prob
                if add_species:
                    species = random.choice(species_qs)
                else:
                    species = None

                add_diameter = random.random() < diameter_prob
                if add_diameter:
                    diameter = 2 + random.random() * 18
                else:
                    diameter = None

                tree = Tree(plot=plot,
                            species=species,
                            diameter=diameter,
                            instance=instance)
                tree.save_with_user(user)
                ct += 1

        instance.update_revs('geo_rev', 'eco_rev')
        self.stdout.write("Created %s trees and %s plots" % (ct, cp))
