# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from optparse import make_option

from django.core.management.base import BaseCommand

from treemap.models import (Instance, User, Plot, Tree,
                            FieldPermission, Role, InstanceUser)


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
                    help='Delete previous trees/plots in the instance first'),)

    def setup_env(self, *args, **options):
        """ Create some seed data """
        instance = Instance.objects.get(pk=options['instance'])

        try:
            user = User.system_user()
            instance_user = user.get_instance_user(instance)
        except Exception:
            self.stdout.write('Error: Could not find a superuser to use')
            return 1

        if instance_user is None:
            r = Role(name='global', rep_thresh=0, instance=instance)
            r.save()
            instance_user = InstanceUser(instance=instance,
                                         user=user,
                                         role=r)
            instance_user.save_with_user(user)
            self.stdout.write('Added system user to instance with global role')

        for field in Plot._meta.get_all_field_names():
            _, c = FieldPermission.objects.get_or_create(
                model_name='Plot',
                field_name=field,
                role=instance_user.role,
                instance=instance,
                permission_level=FieldPermission.WRITE_DIRECTLY)
            if c:
                self.stdout.write('Created plot permission for field "%s"'
                                  % field)

        for field in Tree._meta.get_all_field_names():
            _, c = FieldPermission.objects.get_or_create(
                model_name='Tree',
                field_name=field,
                role=instance_user.role,
                instance=instance,
                permission_level=FieldPermission.WRITE_DIRECTLY)
            if c:
                self.stdout.write('Created tree permission for field "%s"'
                                  % field)

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

        return instance, user
