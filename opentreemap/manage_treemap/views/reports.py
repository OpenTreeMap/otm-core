# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from copy import deepcopy
from functools import wraps, partial
import json

from django.db import IntegrityError, connection, transaction
from django.contrib.contenttypes.models import ContentType
from django_tinsel.utils import LazyEncoder
from django.http import (HttpResponse, HttpResponseBadRequest,
                         HttpResponseRedirect)

from treemap.ecobenefits import get_benefits_for_filter
from treemap.search import Filter
from treemap.models import Boundary, NeighborhoodGroup, MapFeature


def add_boundary_clause(aggregation_level, alias='m', join='boundary_join', where='boundary_where'):
    format_args = {}
    args = []
    if not aggregation_level:
        format_args[join] = "cross join (select 'ALL'::varchar as name) b"
        format_args[where] = 'and    1=1'
    else:
        format_args[join] = '''
            left join   treemap_boundary b on
                (st_within({alias}.the_geom_webmercator, b.the_geom_webmercator))
        '''.format(alias=alias)
        format_args[where] = '''
            and     b.name is not null
            and     lower(b.category) = %s
        '''
        args.append(aggregation_level)

    return (format_args, args)


def add_user_clause(user, alias='m', where='user_where'):
    format_args = {}
    args = []
    if user:
        format_args[where] = 'and    {alias}.updated_by_id = %s'.format(alias=alias)
        args.append(user.id)
    else:
        format_args[where] = 'and    1=1'

    return (format_args, args)


def check_report_query_parameters(view_fn):
    @wraps(view_fn)
    def f(request, instance, *args, **kwargs):
        data_set = request.GET.get('data_set')
        if data_set not in _REPORTS:
            message_dict = { 'globalErrors': ['Please choose a correct report'] }
            return HttpResponseBadRequest(
                json.dumps(message_dict, cls=LazyEncoder))

        aggregation_level = request.GET.get('aggregation_level')
        return view_fn(request, instance, data_set, aggregation_level, *args, **kwargs)

        #raise PermissionDenied
    return f


def include_user(view_fn):
    @wraps(view_fn)
    def f(request, *args, **kwargs):
        return view_fn(request, *args, include_user=True, **kwargs)
    return f


def reports(request, instance):
    neighborhoods = Boundary.objects.filter(category__iexact='neighborhood').values('name').order_by('name').all()
    wards = Boundary.objects.filter(category__iexact='ward').order_by('name').values('name').all()
    parks = Boundary.objects.filter(category__iexact='park').order_by('name').values('name').distinct().all()
    sids = Boundary.objects.filter(category__iexact='sid').order_by('name').values('name').distinct().all()

    return {
        'instance': instance,
        'neighborhoods': neighborhoods,
        'wards': wards,
        'parks': parks,
        'sids': sids
    }


def get_reports_data(request, instance, data_set, aggregation_level, include_user=False):
    data_set_funcs = {
        'count': get_tree_count,
        'count_over_time': get_tree_count_over_time,
        'species': get_species_count,
        'condition': get_tree_conditions,
        'diameter': get_tree_diameters,
        'ecobenefits': get_ecobenefits,
        'ecobenefits_by_user': get_ecobenefits_by_user
    }
    if data_set in data_set_funcs:
        return {'data': data_set_funcs[data_set](
            aggregation_level,
            instance,
            request.user if include_user else None)}

    return None


def get_tree_count(aggregation_level, instance, user):
    _query = """
        select  b.name as "name",
                count(1) as "count"
        from    treemap_mapfeature m
        join	treemap_tree t  on m.id = t.plot_id
        {boundary_join}
        where   1=1
        {boundary_where}
        {user_where}
        group by b.name
    """

    (format_boundary, args_boundary) = add_boundary_clause(aggregation_level)
    (format_user, args_user) = add_user_clause(user)

    query = _query.format(**format_boundary, **format_user)
    args = [*args_boundary, *args_user]

    columns = ['name', 'count']
    with connection.cursor() as cursor:
        cursor.execute(query, args)
        results = cursor.fetchall()
        return [dict(zip(columns, r)) for r in results]


def get_tree_count_over_time(aggregation_level, instance, user):
    _query = """
        WITH week_range as (
            select date_trunc('week', i) as "date"
            from generate_series(current_date - interval '3 months',
            current_date, '1 week'::interval) i
        ), trees as (
            select  date_trunc('week', m.updated_at::date) as "date",
                    count(1) as "count"
            from    treemap_mapfeature m
            join	treemap_tree t  on m.id = t.plot_id
            where   1=1
            {user_where}
            group by date_trunc('week', m.updated_at::date)
        )
        SELECT  w.date, t.count
        FROM    week_range w
        LEFT JOIN trees t on t.date = w.date
    """

    (format_user, args) = add_user_clause(user)
    query = _query.format(**format_user)

    #import ipdb; ipdb.set_trace() # BREAKPOINT
    columns = ['name', 'count']
    with connection.cursor() as cursor:
        cursor.execute(query, args)
        results = cursor.fetchall()
        return [dict(zip(columns, r)) for r in results]


def get_species_count(aggregation_level, instance, user):
    query = """
        SELECT  s.common_name as species_name,
                b.name as name,
                count(1) as "count"
        from    treemap_mapfeature m
        join	treemap_tree t  on m.id = t.plot_id
        left join   treemap_species s on s.id = t.species_id
        left join   treemap_boundary b on
            (st_within(m.the_geom_webmercator, b.the_geom_webmercator))
        WHERE   1=1
        and     s.common_name is not null
        and     b.name is not null
        and     lower(b.category) = %s
        group by s.common_name, b.name
    """
    columns = ['species_name', 'name', 'count']
    with connection.cursor() as cursor:
        cursor.execute(query, [aggregation_level])
        results = cursor.fetchall()
        return [dict(zip(columns, r)) for r in results]


def get_tree_conditions(aggregation_level, instance, user):
    query = """
        select  b.name,
                sum(case when t.udfs -> 'Condition' = 'Healthy' then 1 else 0 end) as healthy,
                sum(case when t.udfs -> 'Condition' = 'Unhealthy' then 1 else 0 end) as unhealthy,
                sum(case when t.udfs -> 'Condition' = 'Dead' then 1 else 0 end) as dead,
                sum(case when t.udfs -> 'JC Forester - Roots Sidewalk Issue' = 'Yes' then 1 else 0 end) as sidewalk_issue,
                sum(case when t.udfs -> 'JC Forester - Canopy Power Lines Issue' = 'Yes' then 1 else 0 end) as power_lines_issue
        from    treemap_mapfeature m
        join	treemap_tree t  on m.id = t.plot_id
        left JOIN   treemap_boundary b on (ST_Within(m.the_geom_webmercator, b.the_geom_webmercator))
        where   1=1
        and     lower(b.category) = %s
        and     b.name is not null
        group by b.name
    """
    columns = [
        'name',
        'healthy',
        'unhealthy',
        'dead',
        'sidewalk_issue',
        'power_lines_issue'
    ]
    with connection.cursor() as cursor:
        cursor.execute(query, [aggregation_level])
        results = cursor.fetchall()
        return [dict(zip(columns, r)) for r in results]


def get_tree_diameters(aggregation_level, instance, user):
    query = """
        with tstats as (
            select  min(diameter) as min,
                    max(diameter) as max
            from        treemap_mapfeature m
            left join   treemap_tree t  on m.id = t.plot_id
            left join   treemap_species s on s.id = t.species_id
            where   1=1
            and     diameter is not null
            and     s.common_name is not null
            -- this is otherwise probably just wrong data
            and     diameter >= 2.5
        )
        select  diameter as diameter,
                b.name as name,
                tstats.min as "min",
                tstats.max as "max"
            from        treemap_mapfeature m
            cross join  tstats
            left join   treemap_tree t  on m.id = t.plot_id
            left join   treemap_species s on s.id = t.species_id
            left JOIN   treemap_boundary b on (ST_Within(m.the_geom_webmercator, b.the_geom_webmercator))
            where   1=1
            and     lower(b.category) = %s
            and     b.name is not null
            and     diameter is not null
            and     s.common_name is not null
            -- this is otherwise probably just wrong data
            and     diameter >= 2.5
    """

    columns = ['diameter', 'name', 'min', 'max']
    with connection.cursor() as cursor:
        cursor.execute(query, [aggregation_level])
        results = cursor.fetchall()
        return [dict(zip(columns, r)) for r in results]


def get_ecobenefits(aggregation_level, instance, user):
    """
    Get the ecobenefits as a flattened table.
    We will have two columns per label, one is the value per year,
    one is the units per year
    """
    columns = ['Name']
    data = []
    boundaries = Boundary.objects.filter(category__iexact=aggregation_level).order_by('name').all()

    _filter = Filter(None, None, instance)
    benefits_all, basis_all = get_benefits_for_filter(_filter)
    data_all = ['Total']
    for (_, value) in benefits_all['plot'].items():
        label = value['label']
        columns.extend(['{} {}/year'.format(label, value['unit']), '{} ($)'.format(label)])
        data_all.extend([value['value'], value['currency']])
    columns.append('Total Trees')
    data_all.append(basis_all['plot']['n_objects_used'])

    boundary_filters = []

    # iterate over the boundaries and get the benefits for each one
    for boundary in boundaries:
        # for now, skip this one
        if boundary.name == 'Liberty State Park':
            continue

        boundary_filter = json.dumps({'plot.geom':
                                       {'IN_BOUNDARY': boundary.pk}})
        _filter = Filter(boundary_filter, None, instance)
        benefits_boundary, basis_boundary = get_benefits_for_filter(_filter)

        data_boundary = [boundary.name]
        for (_, value) in benefits_boundary['plot'].items():
            label = value['label']
            data_boundary.extend([value['value'], value['currency']])
        data_boundary.append(basis_boundary['plot']['n_objects_used'])

        data.append(data_boundary)

    # add our totals at the end
    data.append(data_all)
    return {'columns': columns, 'data': data}


def get_ecobenefits_by_user(aggregation_level, instance, user):
    """
    Get the ecobenefits as a flattened table.
    We will have two columns per label, one is the value per year,
    one is the units per year
    """
    columns = ['Name']
    data = []

    user_filter = json.dumps({'plot.updated_by_id': user.id})

    _filter = Filter(user_filter, None, instance)
    benefits_all, basis_all = get_benefits_for_filter(_filter)
    data_all = ['Total']
    for (_, value) in benefits_all['plot'].items():
        label = value['label']
        columns.extend(['{} {}/year'.format(label, value['unit']), '{} ($)'.format(label)])
        data_all.extend([value['value'], value['currency']])
    columns.append('Total Trees')
    data_all.append(basis_all['plot']['n_objects_used'])

    return {'columns': columns, 'data': data_all}


_REPORTS = {
    'count': get_tree_count,
    'count_over_time': get_tree_count_over_time,
    'species': get_species_count,
    'condition': get_tree_conditions,
    'diameter': get_tree_diameters,
    'ecobenefits': get_ecobenefits,
    'ecobenefits_by_user': get_ecobenefits_by_user
}
