from django.core.management.base import BaseCommand
from optparse import make_option

from treemap.models import (Instance, User, Plot, Tree,
                            FieldPermission, Role)


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
            user.save_base()

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

        return instance, user
