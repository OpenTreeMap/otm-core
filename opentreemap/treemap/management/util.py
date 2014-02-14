# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from optparse import make_option

from django.core.management.base import BaseCommand

from treemap.models import (Instance, User, Plot, Tree, Role, InstanceUser,
                            MapFeature)
from treemap.audit import add_default_permissions


class InstanceDataCommand(BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('-i', '--instance',
                    action='store',
                    type='int',
                    dest='instance',
                    help='Specify the instance to add trees to'),
        make_option('-d', '--delete',
                    action='store_true',
                    dest='delete',
                    default=False,
                    help='Delete previous trees/plots in the instance first'),
        make_option('-k', '--kill_resources',
                    action='store_true',
                    dest='delete_resources',
                    default=False,
                    help='Delete previous resources in the instance first'),)

    def setup_env(self, *args, **options):
        """ Create some seed data """
        instance = Instance.objects.get(pk=options['instance'])

        try:
            user = User.system_user()
        except User.DoesNotExist:
            self.stdout.write('Error: Could not find a superuser to use')
            return 1

        instance_user = user.get_instance_user(instance)

        if instance_user is None:
            r = Role.objects.get_or_create(name='administrator', rep_thresh=0,
                                           instance=instance,
                                           default_permission=3)
            instance_user = InstanceUser(instance=instance,
                                         user=user,
                                         role=r[0])
            instance_user.save_with_user(user)
            self.stdout.write(
                'Added system user to instance with "administrator" role')

        add_default_permissions(instance)

        dt = 0
        dp = 0
        if options.get('delete', False):
            for t in Tree.objects.all():
                t.delete_with_user(user)
                dt += 1
            for p in Plot.objects.all():
                p.delete_with_user(user)
                dp += 1

            self.stdout.write("Deleted %s trees and %s plots" % (dt, dp))

        dr = 0
        if options.get('delete_resources', False):
            for f in MapFeature.objects.all():
                if f.feature_type != 'Plot':
                    f.delete_with_user(user)
                    dr += 1

            self.stdout.write("Deleted %s resources" % dr)

        return instance, user
