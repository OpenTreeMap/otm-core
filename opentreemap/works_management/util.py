# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.db import transaction

from works_management.models import Team


@transaction.atomic
def team_create(params, instance):
    data = _parse_params(params)

    team = Team(
        instance=instance,
        name=data['name'])
    team.save()

    return team


def _parse_params(params):
    name = params.get('team.name', None)
    return {
        'name': name,
    }
