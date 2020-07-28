# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import csv
import json

from datetime import datetime

from contextlib import contextmanager

from django.core.exceptions import ValidationError
from django.db.models import Count, F, Q

from treemap.lib.dates import DATETIME_FORMAT
from treemap.models import NeighborhoodGroup, Audit

from exporter.util import sanitize_unicode_record


def write_groups(csv_obj, instance, aggregation_level, min_join_ts=None, min_edit_ts=None):
    field_names = None
    values = None

    if aggregation_level == 'neighborhood':
        field_names = ['ward', 'neighborhood', 'total']
        values = get_neighborhood_count(instance)
    elif aggregation_level == 'user':
        # FIXME remove the data being saved in that public S3
        #field_names = ['ward', 'neighborhood', 'user_email', 'total']
        #values = _get_user_neighborhood_count(instance)
        return

    writer = csv.DictWriter(csv_obj, field_names)
    writer.writeheader()
    for stats in values:
        writer.writerow(stats)


def _get_user_neighborhood_trees(instance):
    return (NeighborhoodGroup.objects
        .filter(user__mapfeature__plot__tree__isnull=False)
        .prefetch_related('user', 'mapfeature', 'plot', 'tree', 'species')
        .annotate(
            user_email=F('user__email'),
            tree_common_name=F('user__mapfeature__plot__tree__species__common_name')
        ).values(
            'ward',
            'neighborhood',
            'user_email',
            'tree_common_name'
        ).all())


def _get_user_neighborhood_count(instance):
    return (NeighborhoodGroup.objects
        .prefetch_related('user', 'mapfeature', 'plot', 'tree')
        .filter(user__mapfeature__plot__tree__isnull=False)
        .values(
            'ward',
            'neighborhood',
        )
        .annotate(
            user_email=F('user__email'),
            total=Count('user__mapfeature__plot__tree'))
        .all())


def get_neighborhood_count(instance):
    return (NeighborhoodGroup.objects
        .prefetch_related('user', 'mapfeature', 'plot', 'tree')
        .filter(user__mapfeature__plot__tree__isnull=False)
        .values(
            'ward',
            'neighborhood',
        )
        .annotate(
            total=Count('user__mapfeature__plot__tree'))
        .all())
