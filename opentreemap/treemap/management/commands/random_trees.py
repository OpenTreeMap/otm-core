from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from optparse import make_option

from treemap.models import Instance, User, Plot, Tree, ImportEvent,\
    FieldPermission, Role

import random
import math


class Command(BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('-i', '--instance',
                    action='store',
                    type='int',
                    dest='instance',
                    help='Specify the instance to add trees to'),
        make_option('-r', '--radius',
                    action='store',
                    type='int',
                    dest='radius',
                    default=5000,
                    help='Number of meters from the center'),
        make_option('-n', '--number-of-trees',
                    action='store',
                    type='int',
                    dest='n',
                    default=100000,
                    help='Number of trees to create'),
        make_option('-d', '--delete',
                    action='store_true',
                    dest='delete',
                    default=False,
                    help='Delete previous trees/plots in the instance first'),
        make_option('-p', '--prob-of-tree',
                    action='store',
                    type='int',
                    dest='ptree',
                    default=50,
                    help=('Probability that a given plot will '
                          'have a tree (0-100)')))

    def handle(self, *args, **options):
        """ Create some seed data """
        instance = Instance.objects.get(pk=options['instance'])

        user = User.objects.filter(is_superuser=True)

        if len(user) == 0:
            print('Error: Could not find a superuser to use')
            return 1
        else:
            user = user[0]

        if user.roles.count() == 0:
            print('Added global role to user')
            r = Role(name='global', rep_thresh=0, instance=instance)
            r.save()
            user.roles.add(r)
            user.save()

        for field in ('geom', 'import_event'):
            _, c = FieldPermission.objects.get_or_create(
                model_name='Plot',
                field_name=field,
                role=user.roles.all()[0],
                instance=instance,
                permission_level=FieldPermission.WRITE_DIRECTLY)
            if c:
                print('Created plot permission for field "%s"' % field)

        for field in ('plot',):
            _, c = FieldPermission.objects.get_or_create(
                model_name='Tree',
                field_name=field,
                role=user.roles.all()[0],
                instance=instance,
                permission_level=FieldPermission.WRITE_DIRECTLY)
            if c:
                print('Created tree permission for field "%s"' % field)

        dt = 0
        dp = 0
        if options.get('delete', False):
            for t in Tree.objects.all():
                t.delete_with_user(user)
                dt += 1
            for p in Plot.objects.all():
                p.delete_with_user(user)
                dp += 1

            print("Deleted %s trees and %s plots" % (dt, dp))

        n = options['n']
        print("Will create %s plots" % n)

        tree_prob = float(max(100, min(0, options['ptree']))) / 100.0
        max_radius = options['radius']

        center_x = instance.center.x
        center_y = instance.center.y

        import_event = ImportEvent(imported_by=user)
        import_event.save()

        ct = 0
        cp = 0
        for i in xrange(0, n):
            mktree = random.random() < tree_prob
            radius = random.gauss(0.0, max_radius)
            theta = random.random() * 2.0 * math.pi

            x = math.cos(theta) * radius + center_x
            y = math.sin(theta) * radius + center_y

            plot = Plot(instance=instance,
                        geom=Point(x, y),
                        import_event=import_event)

            plot.save_with_user(user)
            cp += 1

            if mktree:
                tree = Tree(plot=plot,
                            import_event=import_event,
                            instance=instance)
                tree.save_with_user(user)
                ct += 1

        print("Created %s trees and %s plots" % (ct, cp))
