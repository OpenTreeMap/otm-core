# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.core.management.base import BaseCommand
from django.conf import settings

from treemap.models import User


class Command(BaseCommand):
    """
    Create a new system user
    """

    def handle(self, *args, **options):
        try:
            model_id = settings.SYSTEM_USER_ID
        except AttributeError:
            print('The `SYSTEM_USER_ID` settings is missing from '
                  'the settings file. Set this to a specific ID '
                  'before running this command.')
            return

        system_user_name = 'System User'

        existing_users = User.objects.filter(pk=model_id)
        users_with_name = User.objects.filter(username=system_user_name)

        if len(existing_users) == 1 and len(users_with_name) == 1:
            print('System user already exists')
        elif len(users_with_name) > 0:
            print('A user with username "%s" already exists but is not '
                  'a super user' % system_user_name)
        else:
            user = User(is_active=False,
                        username=system_user_name,
                        pk=model_id)
            user.save_base()
            print('Created system user')
