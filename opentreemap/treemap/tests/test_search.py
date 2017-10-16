# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
import psycopg2

from datetime import datetime
from functools import partial

from django.db.models import Q
from django.db import connection
from django.db.models.query import QuerySet
from django.utils.tree import Node

from django.contrib.gis.geos import Point, MultiPolygon

from treemap.json_field import set_attr_on_json_field
from treemap.tests import (make_instance, make_commander_user,
                           make_simple_polygon, set_write_permissions)
from treemap.tests.base import OTMTestCase
from treemap.tests.test_udfs import make_collection_udf
from treemap.models import (Tree, Plot, Boundary, Species)
from treemap.udf import UserDefinedFieldDefinition
from treemap import search

COLLECTION_UDF_DATATYPE = [{'type': 'choice',
                            'choices': ['water', 'prune'],
                            'name': 'action'},
                           {'type': 'date',
                            'name': 'date'}]


def destructure_query_set(node):
    """
    Django query objects are not comparable by themselves, but they
    are built from a tree (django.util.tree) and stored in nodes

    This function generates a canonical representation using sets and
    tuples of a query tree

    This can be used to verify that query structures are made correctly
    """
    if isinstance(node, Node):
        children = [destructure_query_set(c) for c in node.children]
        try:
            child_hash = frozenset(children)
        except:
            # Necessary for udf collection queries, which contain
            # (selector, dict) pairs, and the dicts are unhashable
            child_hash = dict(children)
        n = (node.connector, child_hash)

        if node.negated:
            n = ('NOT', n)

        return n
    elif isinstance(node, tuple):
        # Lists are unhashable, so convert QuerySets into tuples for easy
        # comparison
        return tuple(tuple(c) if isinstance(c, QuerySet) else c for c in node)
    else:
        return node


def _setup_collection_udfs(instance, user):
    plotstew = make_collection_udf(instance, model='Plot',
                                   datatype=COLLECTION_UDF_DATATYPE)
    treestew = make_collection_udf(instance, model='Tree',
                                   datatype=COLLECTION_UDF_DATATYPE)

    set_write_permissions(instance, user, 'Plot', [plotstew.canonical_name])
    set_write_permissions(instance, user, 'Tree', [treestew.canonical_name])

    return plotstew, treestew


def _setup_models_for_collections(instance, user, point,
                                  plot_collection, tree_collection):
    p1, __ = _create_tree_and_plot(
        instance, user, point,
        plotudfs={plot_collection.name:
                  [{'action': 'water', 'date': "2013-08-06 00:00:00"},
                   {'action': 'prune', 'date': "2013-09-15 00:00:00"}]},
        treeudfs={tree_collection.name:
                  [{'action': 'water', 'date': "2013-05-15 00:00:00"},
                   {'action': 'water', 'date': None}]})

    p2, __ = _create_tree_and_plot(
        instance, user, point,
        plotudfs={plot_collection.name: [
            {'action': 'water', 'date': "2014-11-26 00:00:00"}]},
        treeudfs={tree_collection.name: [
            {'action': 'prune', 'date': "2014-06-23 00:00:00"}]})

    p3, __ = _create_tree_and_plot(
        instance, user, point,
        plotudfs={plot_collection.name: [
            {'action': 'water', 'date': "2015-08-05 00:00:00"},
            {'action': 'prune', 'date': "2015-04-13 00:00:00"}]},
        treeudfs={tree_collection.name:
                  [{'action': 'prune', 'date': "2013-06-19 00:00:00"},
                   {'action': 'water', 'date': None}]})

    return (p.pk for p in [p1, p2, p3])


def _create_tree_and_plot(instance, user, point,
                          plotudfs=None, treeudfs=None):
    plot = Plot(geom=point, instance=instance)

    if plotudfs:
        for k, v in plotudfs.iteritems():
            plot.udfs[k] = v

    plot.save_with_user(user)

    tree = Tree(plot=plot, instance=instance)
    if treeudfs:
        for k, v in treeudfs.iteritems():
            tree.udfs[k] = v

    tree.save_with_user(user)

    return plot, tree


class FilterParserScalarTests(OTMTestCase):
    def setUp(self):
        self.parse_dict_value = partial(
            search._parse_dict_value_for_mapping,
            search.PREDICATE_TYPES)

    def test_key_parser_plots(self):
        # Plots searches on plot go directly to a field
        match = search._parse_predicate_key('plot.width',
                                            mapping=search.DEFAULT_MAPPING)
        self.assertEqual(match, ('plot', '', 'width'))

    def test_udf_fields_look_good(self):
        match = search._parse_predicate_key('plot.udf:The 1st Planter',
                                            mapping=search.DEFAULT_MAPPING)
        self.assertEqual(match, ('plot', '', 'udf:The 1st Planter'))

    def test_key_parser_trees(self):
        # Tree searches on plot require a prefix and the field
        match = search._parse_predicate_key('tree.dbh',
                                            mapping=search.DEFAULT_MAPPING)
        self.assertEqual(match, ('tree', 'tree__', 'dbh'))

    def test_key_parser_invalid_model(self):
        # Invalid models should raise an exception
        self.assertRaises(search.ParseException,
                          search._parse_predicate_key,
                          "user.id",
                          mapping=search.DEFAULT_MAPPING)

    def test_key_parser_too_many_dots(self):
        # Dotted fields are also not allowed
        self.assertRaises(search.ParseException,
                          search._parse_predicate_key,
                          "plot.width.other",
                          mapping=search.DEFAULT_MAPPING)

    def test_combinator_and(self):
        qa = Q(a=1)
        qb = Q(b=1)
        qc = Q(c=1)

        # Simple AND
        ands = search._apply_combinator('AND', [qa, qb, qc])

        self.assertEqual(destructure_query_set(ands),
                         destructure_query_set(qa & qb & qc))

    def test_combinator_or(self):
        qa = Q(a=1)
        qb = Q(b=1)
        qc = Q(c=1)

        # Simple OR
        ands = search._apply_combinator('OR', [qa, qb, qc])

        self.assertEqual(destructure_query_set(ands),
                         destructure_query_set(qa | qb | qc))

    def test_combinator_invalid_combinator(self):
        qa = Q(a=1)
        qb = Q(b=1)
        qc = Q(c=1)

        # Error if not AND,OR
        self.assertRaises(search.ParseException,
                          search._apply_combinator,
                          'ANDarg', [qa, qb])

        self.assertRaises(search.ParseException,
                          search._apply_combinator,
                          qc, [qa, qb])

    def test_combinator_invalid_empty(self):
        # Error if empty
        self.assertRaises(search.ParseException,
                          search._apply_combinator,
                          'AND', [])

    def test_boundary_constraint(self):
        b = Boundary.objects.create(
            geom=MultiPolygon(make_simple_polygon(0)),
            name='whatever',
            category='whatever',
            sort_order=1)

        inparams = self.parse_dict_value({'IN_BOUNDARY': b.pk})
        self.assertEqual(inparams,
                         {'__within': b.geom})

    def test_constraints_in(self):
        inparams = self.parse_dict_value({'IN': [1, 2, 3]})
        self.assertEqual(inparams,
                         {'__in': [1, 2, 3]})

    def test_constraints_isnull(self):
        inparams = self.parse_dict_value({'ISNULL': True})
        self.assertEqual(inparams, {'__isnull': True})

    def test_constraints_is(self):
        # "IS" is a special case in that we don't need to appl
        # a suffix at all
        isparams = self.parse_dict_value({'IS': 'what'})
        self.assertEqual(isparams,
                         {'': 'what'})

    def test_constraints_invalid_groups(self):
        # It is an error to combine mutually exclusive groups
        self.assertRaises(search.ParseException,
                          self.parse_dict_value,
                          {'IS': 'what', 'IN': [1, 2, 3]})

        self.assertRaises(search.ParseException,
                          self.parse_dict_value,
                          {'IS': 'what', 'MIN': 3})

    def test_constraints_invalid_keys(self):
        self.assertRaises(search.ParseException,
                          self.parse_dict_value,
                          {'EXCLUSIVE': 9})

        self.assertRaises(search.ParseException,
                          self.parse_dict_value,
                          {'IS NOT VALID KEY': 'what'})

    def test_contraint_min(self):
        const = self.parse_dict_value({'MIN': 5})
        self.assertEqual(const, {'__gte': 5})

    def test_contraint_max(self):
        const = self.parse_dict_value({'MAX': 5})
        self.assertEqual(const, {'__lte': 5})

    def test_contraint_max_with_exclusive(self):
        const = self.parse_dict_value(
            {'MAX': {'VALUE': 5,
                     'EXCLUSIVE': True}})
        self.assertEqual(const, {'__lt': 5})

        const = self.parse_dict_value(
            {'MAX': {'VALUE': 5,
                     'EXCLUSIVE': False}})
        self.assertEqual(const, {'__lte': 5})

    def test_constraints_min_and_max(self):
        const = self.parse_dict_value(
            {'MIN': 5,
             'MAX': {'VALUE': 9,
                     'EXCLUSIVE': False}})
        self.assertEqual(const, {'__lte': 9, '__gte': 5})

    def test_parse_species_predicate(self):
        pred = search._parse_scalar_predicate(
            {'species.id': 113,
             'species.flowering': True},
            mapping=search.DEFAULT_MAPPING)

        target = ('AND', {('tree__species__id', 113),
                          ('tree__species__flowering', True)})

        self.assertEqual(destructure_query_set(pred), target)

    def test_like_predicate(self):
        pred = search._parse_scalar_predicate(
            {'tree.steward': {'LIKE': 'thisisatest'}},
            mapping=search.DEFAULT_MAPPING)

        target = ('AND', {('tree__steward__icontains', 'thisisatest')})

        self.assertEqual(destructure_query_set(pred), target)

    def test_parse_predicate(self):
        pred = search._parse_scalar_predicate(
            {'plot.width':
             {'MIN': 5,
              'MAX': {'VALUE': 9,
                      'EXCLUSIVE': False}},
             'tree.height': 9},
            mapping=search.DEFAULT_MAPPING)

        p1 = ('AND', {('width__lte', 9),
                      ('width__gte', 5),
                      ('tree__height', 9)})

        self.assertEqual(destructure_query_set(pred),
                         p1)

        pred = search._parse_scalar_predicate(
            {'tree.leaf_type': {'IS': 9},
             'tree.last_updated_by': 4},
            mapping=search.DEFAULT_MAPPING)

        p2 = ('AND', {('tree__leaf_type', 9),
                      ('tree__last_updated_by', 4)})

        self.assertEqual(destructure_query_set(pred),
                         p2)

    def test_parse_predicate_with_tree_map(self):
        pred = search._parse_scalar_predicate(
            {'plot.width':
             {'MIN': 5,
              'MAX': {'VALUE': 9,
                      'EXCLUSIVE': False}},
             'tree.height':
             9},
            mapping=search.DEFAULT_MAPPING)

        p1 = ('AND', {('width__lte', 9),
                      ('width__gte', 5),
                      ('tree__height', 9)})

        self.assertEqual(destructure_query_set(pred),
                         p1)

    def test_parse_filter_no_wrapper(self):
        pred = search._parse_filter(
            {'plot.width':
             {'MIN': 5,
              'MAX': {'VALUE': 9,
                      'EXCLUSIVE': False}},
             'tree.height': 9},
            mapping=search.DEFAULT_MAPPING)

        p = ('AND',
             {('width__lte', 9),
              ('width__gte', 5),
              ('tree__height', 9)})

        self.assertEqual(destructure_query_set(pred), p)

    def test_parse_filter_and(self):
        pred = search._parse_filter(
            ['AND',
             {'plot.width':
              {'MIN': 5,
               'MAX': {'VALUE': 9,
                       'EXCLUSIVE': False}},
              'tree.height': 9},
             {'tree.leaf_type': {'IS': 9},
              'tree.last_updated_by': 4}],
            mapping=search.DEFAULT_MAPPING)

        p = ('AND',
             {('width__lte', 9),
              ('width__gte', 5),
              ('tree__height', 9),
              ('tree__leaf_type', 9),
              ('tree__last_updated_by', 4)})

        self.assertEqual(destructure_query_set(pred), p)

    def test_parse_filter_or(self):
        pred = search._parse_filter(
            ['OR',
             {'plot.width':
              {'MIN': 5,
               'MAX': {'VALUE': 9,
                       'EXCLUSIVE': False}},
              'tree.height': 9},
             {'tree.leaf_type': {'IS': 9},
              'tree.last_updated_by': 4}],
            mapping=search.DEFAULT_MAPPING)

        p1 = ('AND', frozenset({('width__lte', 9),
                                ('width__gte', 5),
                                ('tree__height', 9)}))

        p2 = ('AND', frozenset({('tree__leaf_type', 9),
                                ('tree__last_updated_by', 4)}))

        self.assertEqual(destructure_query_set(pred), ('OR', {p1, p2}))

    def test_parse_normal_value(self):
        self.assertEqual(search._parse_value(1), 1)

    def test_parse_list(self):
        self.assertEqual(search._parse_value([1, 2]), [1, 2])

    def test_parse_date(self):
        date = datetime(2013, 4, 1, 12, 0, 0)
        self.assertEqual(search._parse_value("2013-04-01 12:00:00"), date)


class FilterParserCollectionTests(OTMTestCase):
    def _setup_tree_and_collection_udf(self):
        instance = self.instance = make_instance()
        commander = self.commander = make_commander_user(instance)

        self.plotstew, self.treestew = \
            _setup_collection_udfs(instance, commander)

        d1 = {'action': 'prune', 'date': "2014-05-3 00:00:00"}
        d2 = {'action': 'water', 'date': "2014-04-29 00:00:00"}

        self.plot = Plot(instance=instance, geom=instance.center)
        self.plot.udfs[self.plotstew.name] = [d1]
        self.plot.save_with_user(commander)

        self.tree = Tree(instance=instance, plot=self.plot)
        self.tree.udfs[self.treestew.name] = [d2]
        self.tree.save_with_user(commander)

    def test_key_parser_tree_collection_udf(self):
        # UDF searches go on the specified model's id
        match = search._parse_predicate_key('udf:tree:52.action',
                                            mapping=search.DEFAULT_MAPPING)
        self.assertEqual(match, ('udf:tree:52', 'tree__', 'action'))

    def test_key_parser_plot_collection_udf(self):
        # UDF searches go on the specified model's id
        match = search._parse_predicate_key('udf:plot:52.action',
                                            mapping=search.DEFAULT_MAPPING)
        self.assertEqual(match, ('udf:plot:52', '', 'action'))

    def test_parse_collection_udf_simple_predicate(self):
        self._setup_tree_and_collection_udf()
        pred = search._parse_query_dict(
            {'udf:plot:%s.action' % self.plotstew.pk: 'prune'},
            mapping=search.DEFAULT_MAPPING)

        target = ('AND', {('id__in', (self.plot.pk,))})

        self.assertEqual(destructure_query_set(pred), target)

    def test_parse_collection_udf_fail_nondatenumeric_comparison(self):
        self._setup_tree_and_collection_udf()

        with self.assertRaises(search.ParseException):
            search._parse_query_dict(
                {'udf:tree:%s.date' % self.treestew.pk: {'MAX': "foo"}},
                mapping=search.DEFAULT_MAPPING)

    def test_parse_collection_udf_nested_pass_numeric_comparison(self):
        self._setup_tree_and_collection_udf()
        agility = make_collection_udf(self.instance, model='Tree',
                                      name='Agility',
                                      datatype=[{'type': 'float',
                                                 'name': 'current'}])
        set_write_permissions(self.instance, self.commander,
                              'Tree', ['udf:Agility'])
        new_tree = Tree(instance=self.instance, plot=self.plot)
        new_tree.udfs[agility.name] = [{'current': '1.5'}]
        new_tree.save_with_user(self.commander)

        pred = search._parse_query_dict(
            {'udf:tree:%s.current' % agility.pk: {'MIN': 1}},
            mapping=search.DEFAULT_MAPPING)

        target = ('AND', {('tree__id__in', (new_tree.pk,))})

        self.assertEqual(destructure_query_set(pred), target)

    def test_parse_collection_udf_nested_pass_date_comparison(self):
        self._setup_tree_and_collection_udf()

        pred = search._parse_query_dict(
            {'udf:tree:%s.date' % self.treestew.pk:
             {'MAX': '2014-05-01 00:00:00'}},
            mapping=search.DEFAULT_MAPPING)

        target = ('AND', {('tree__id__in', (self.tree.pk,))})

        self.assertEqual(destructure_query_set(pred), target)

    def test_parse_collection_udf_date_and_action_should_fail(self):
        point = Point(0, 0)
        instance = make_instance(point=point)
        commander = make_commander_user(instance)

        plotstew, treestew = _setup_collection_udfs(instance, commander)
        _setup_models_for_collections(instance, commander, point,
                                      plotstew, treestew)

        pred = search._parse_query_dict(
            {'udf:plot:%s.action' % plotstew.pk: {'IS': 'water'},
             'udf:plot:%s.date' % plotstew.pk:
                # Range encompasses p1's prune but not p1's water action
                {'MIN': '2013-09-01 00:00:00',
                 'MAX': '2013-10-31 00:00:00'}},
            mapping=search.DEFAULT_MAPPING)

        connector, predset = destructure_query_set(pred)

        self.assertEqual(connector, 'AND')
        target = ('id__in', tuple())
        self.assertIn(target, predset)


class SearchTests(OTMTestCase):
    def setUp(self):
        self.p1 = Point(0, 0)
        self.instance = make_instance(point=self.p1)
        self.commander = make_commander_user(self.instance)
        self.parse_dict_value = partial(
            search._parse_dict_value_for_mapping,
            search.PREDICATE_TYPES)

    def create_tree_and_plot(self, plotudfs=None, treeudfs=None):
        plot = Plot(geom=self.p1, instance=self.instance)

        if plotudfs:
            for k, v in plotudfs.iteritems():
                plot.udfs[k] = v

        plot.save_with_user(self.commander)

        tree = Tree(plot=plot, instance=self.instance)
        if treeudfs:
            for k, v in treeudfs.iteritems():
                tree.udfs[k] = v

        tree.save_with_user(self.commander)

        return plot, tree

    def _setup_udfs(self):
        set_write_permissions(self.instance, self.commander,
                              'Plot',
                              ['udf:Test string', 'udf:Test date'])
        set_write_permissions(self.instance, self.commander,
                              'Tree',
                              ['udf:Test float'])

        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'string'}),
            iscollection=False,
            name='Test string')

        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'date'}),
            iscollection=False,
            name='Test date')

        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Tree',
            datatype=json.dumps({'type': 'float'}),
            iscollection=False,
            name='Test float')

        psycopg2.extras.register_hstore(connection.cursor(), globally=True)

        p1, __ = self.create_tree_and_plot(
            plotudfs={'Test string': 'testing foo',
                      'Test date': datetime(2010, 1, 9)},
            treeudfs={'Test float': 9.2})

        p2, __ = self.create_tree_and_plot(
            plotudfs={'Test string': 'testing baz or fish',
                      'Test date': datetime(2012, 1, 9)},
            treeudfs={'Test float': 12.0})

        p3, __ = self.create_tree_and_plot(
            plotudfs={'Test string': 'baz',
                      'Test date': datetime(2014, 1, 9)},
            treeudfs={'Test float': 2.2})

        return (p.pk for p in [p1, p2, p3])

    def _setup_collection_udfs(self):
        self.plotstew, self.treestew = _setup_collection_udfs(
            self.instance, self.commander)

        return _setup_models_for_collections(
            self.instance, self.commander, self.p1,
            self.plotstew, self.treestew)

    def _execute_and_process_filter(self, filter={}, display=''):
        f = search.Filter(json.dumps(filter), display, self.instance)
        return {p.pk
                for p
                in f.get_objects(Plot)}

    def test_udf_numeric_search(self):
        p1, p2, p3 = self._setup_udfs()

        self.assertEqual(
            {p1, p3},
            self._execute_and_process_filter(
                {'tree.udf:Test float': {'MAX': 10.0}}))

    def test_udf_date_search(self):
        p1, p2, __ = self._setup_udfs()

        self.assertEqual(
            {p1, p2},
            self._execute_and_process_filter(
                {'plot.udf:Test date': {'MAX': "2013-01-01 00:00:00"}}))

    def test_udf_like_search(self):
        p1, p2, p3 = self._setup_udfs()

        self.assertEqual(
            {p1, p2},
            self._execute_and_process_filter(
                {'plot.udf:Test string': {'LIKE': 'testing'}}))

        self.assertEqual(
            {p2, p3},
            self._execute_and_process_filter(
                {'plot.udf:Test string': {'LIKE': 'baz'}}))

    def test_udf_direct_search(self):
        __, __, p3 = self._setup_udfs()

        self.assertEqual(
            {p3},
            self._execute_and_process_filter(
                {'plot.udf:Test string': {'IS': 'baz'}}))

    def test_species_id_search(self):
        species1 = Species(
            common_name='Species-1',
            genus='Genus-1',
            otm_code='S1',
            instance=self.instance)
        species1.save_with_user(self.commander)

        species2 = Species(
            common_name='Species-2',
            genus='Genus-2',
            otm_code='S1',
            instance=self.instance)
        species2.save_with_user(self.commander)

        p1, t1 = self.create_tree_and_plot()
        p2, t2 = self.create_tree_and_plot()
        p3, t3 = self.create_tree_and_plot()

        t1.species = species1
        t1.save_with_user(self.commander)

        t2.species = species2
        t2.save_with_user(self.commander)

        species1_filter = json.dumps({'species.id': species1.pk})
        species2_filter = json.dumps({'species.id': species2.pk})
        species3_filter = json.dumps({'species.id': -1})

        plots =\
            search.Filter(species1_filter, '', self.instance).get_objects(Plot)

        self.assertEqual(
            {p1.pk},
            {p.pk
             for p in plots})

        plots =\
            search.Filter(species2_filter, '', self.instance).get_objects(Plot)

        self.assertEqual(
            {p2.pk},
            {p.pk
             for p in plots})

        plots =\
            search.Filter(species3_filter, '', self.instance).get_objects(Plot)

        self.assertEqual(
            0, len(plots))

    def test_boundary_search(self):
        # Unit Square
        b1 = Boundary.objects.create(
            geom=MultiPolygon(make_simple_polygon(0)),
            name='whatever',
            category='whatever',
            sort_order=1)

        # Unit Square translated by (0.2,0.2)
        b2 = Boundary.objects.create(
            geom=MultiPolygon(make_simple_polygon(0.2)),
            name='whatever',
            category='whatever',
            sort_order=1)

        # Unit square translated by (-1,-1)
        b3 = Boundary.objects.create(
            geom=MultiPolygon(make_simple_polygon(-1)),
            name='whatever',
            category='whatever',
            sort_order=1)

        plot1 = Plot(geom=Point(0.9, 0.9), instance=self.instance)
        plot2 = Plot(geom=Point(1.1, 1.1), instance=self.instance)
        plot3 = Plot(geom=Point(2.5, 2.5), instance=self.instance)

        for p in (plot1, plot2, plot3):
            p.save_with_user(self.commander)

        boundary1_filter = json.dumps({'plot.geom':
                                       {'IN_BOUNDARY': b1.pk}})

        plots = search.Filter(boundary1_filter, '', self.instance)\
                      .get_objects(Plot)

        self.assertEqual(
            {plot1.pk},
            {p.pk
             for p in plots})

        boundary2_filter = json.dumps({'plot.geom':
                                       {'IN_BOUNDARY': b2.pk}})

        plots = search.Filter(boundary2_filter, '', self.instance)\
                      .get_objects(Plot)

        self.assertEqual(
            {plot1.pk, plot2.pk},
            {p.pk
             for p in plots})

        boundary3_filter = json.dumps({'plot.geom':
                                       {'IN_BOUNDARY': b3.pk}})

        plots = search.Filter(boundary3_filter, '', self.instance)\
                      .get_objects(Plot)

        self.assertEqual(
            0, len(plots))

    def setup_diameter_test(self):
        p1, t1 = self.create_tree_and_plot()
        t1.diameter = 2.0

        p2, t2 = self.create_tree_and_plot()
        t2.diameter = 4.0

        p3, t3 = self.create_tree_and_plot()
        t3.diameter = 6.0

        p4, t4 = self.create_tree_and_plot()
        t4.diameter = 8.0

        for t in [t1, t2, t3, t4]:
            t.save_with_user(self.commander)

        return [p1, p2, p3, p4]

    def test_diameter_units(self):
        p1, p2, p3, p4 = self.setup_diameter_test()

        filter = json.dumps({'tree.diameter': {'MAX': 9.0}})

        plots = search.Filter(filter, '', self.instance)\
                      .get_objects(Plot)

        ids = {p.pk for p in plots}
        self.assertEqual(ids, {p1.pk, p2.pk, p3.pk, p4.pk})

        set_attr_on_json_field(self.instance,
                               'config.value_display.tree.diameter.units',
                               'cm')
        self.instance.save()

        filter = json.dumps({'tree.diameter': {'MAX': 9.0}})

        plots = search.Filter(filter, '', self.instance)\
                      .get_objects(Plot)

        ids = {p.pk for p in plots}
        # The filter range equates to 0 to 3.54.
        self.assertEqual(ids, {p1.pk})

        # This is also testing the alternative range syntax
        filter = json.dumps({'tree.diameter':
                             {'MIN': {'VALUE': 10, 'EXCLUSIVE': True},
                              'MAX': {'VALUE': 15.3, 'EXCLUSIVE': True}}})

        plots = search.Filter(filter, '', self.instance)\
                      .get_objects(Plot)

        ids = {p.pk for p in plots}
        # The filter range equates to 3.93 to 6.02 inches
        self.assertEqual(ids, {p2.pk, p3.pk})

    def test_diameter_min_filter(self):
        p1, p2, p3, p4 = self.setup_diameter_test()

        diameter_range_filter = json.dumps({'tree.diameter':
                                            {'MIN': 3.0}})

        plots = search.Filter(diameter_range_filter, '', self.instance)\
                      .get_objects(Plot)

        ids = {p.pk
               for p in plots}

        self.assertEqual(ids, {p2.pk, p3.pk, p4.pk})

    def test_diameter_max_filter(self):
        p1, p2, p3, p4 = self.setup_diameter_test()

        diameter_range_filter = json.dumps({'tree.diameter':
                                            {'MAX': 3.0}})

        plots = search.Filter(diameter_range_filter, '', self.instance)\
                      .get_objects(Plot)

        ids = {p.pk
               for p in plots}

        self.assertEqual(ids, {p1.pk})

    def test_diameter_range_filter(self):
        p1, p2, p3, p4 = self.setup_diameter_test()

        diameter_range_filter = json.dumps({'tree.diameter':
                                            {'MAX': 7.0,
                                             'MIN': 3.0}})

        plots = search.Filter(diameter_range_filter, '', self.instance)\
                      .get_objects(Plot)

        ids = {p.pk for p in plots}

        self.assertEqual(ids, {p2.pk, p3.pk})

    def test_like_filter(self):
        species = Species(
            instance=self.instance,
            common_name='this is a test species',
            genus='Genus-1',
            otm_code='S1')
        species.save_with_user(self.commander)

        p, t = self.create_tree_and_plot()

        t.species = species
        t.save_with_user(self.commander)

        species_like_filter = json.dumps({
            'species.common_name':
            {'LIKE': 's a tes'}})

        plots = search.Filter(species_like_filter, '', self.instance)\
                      .get_objects(Plot)

        result = [o.pk for o in plots]

        self.assertEqual(result, [p.pk])

        species.common_name = 'no match'
        species.save_with_user(self.commander)

        plots = search.Filter(species_like_filter, '', self.instance)\
                      .get_objects(Plot)

        self.assertEqual(len(plots), 0)

    def test_display_filter_filters_out_models(self):
        plot, tree = self.create_tree_and_plot()

        plots = search.Filter('', '["FireHydrant"]', self.instance)\
                      .get_objects(Plot)

        self.assertEqual(len(plots), 0)

    def test_empty_plot_filter(self):
        plot, tree = self.create_tree_and_plot()
        empty_plot = Plot(geom=self.p1, instance=self.instance)
        empty_plot.save_with_user(self.commander)

        plots = search.Filter('', '["EmptyPlot"]', self.instance)\
                      .get_objects(Plot)

        ids = {p.pk for p in plots}

        self.assertEqual(ids, {empty_plot.pk})

    def test_tree_filter(self):
        plot, tree = self.create_tree_and_plot()
        empty_plot = Plot(geom=self.p1, instance=self.instance)
        empty_plot.save_with_user(self.commander)

        plots = search.Filter('', '["Tree"]', self.instance)\
                      .get_objects(Plot)

        ids = {p.pk for p in plots}

        self.assertEqual(ids, {plot.pk})

    def test_plot_filter(self):
        plot, tree = self.create_tree_and_plot()
        empty_plot = Plot(geom=self.p1, instance=self.instance)
        empty_plot.save_with_user(self.commander)

        plots = search.Filter('', '["Plot"]', self.instance)\
                      .get_objects(Plot)

        ids = {p.pk for p in plots}

        self.assertEqual(ids, {plot.pk, empty_plot.pk})

    def test_allows_cudf(self):
        plot, tree = self.create_tree_and_plot()
        empty_plot = Plot(geom=self.p1, instance=self.instance)
        empty_plot.save_with_user(self.commander)

        plots = search.Filter('', '["Plot"]', self.instance)\
                      .get_objects(Plot)

        ids = {p.pk for p in plots}

        self.assertEqual(ids, {plot.pk, empty_plot.pk})

    def test_cudf_range_search(self):
        p1, p2, p3 = self._setup_collection_udfs()

        self.assertEqual(
            {p2},
            self._execute_and_process_filter(
                {'udf:plot:%s.date' % self.plotstew.pk:
                 {'MIN': "2014-01-01 00:00:00",
                  'MAX': "2014-12-31 00:00:00"}}))

        self.assertEqual(
            {p1, p2},
            self._execute_and_process_filter(
                {'udf:plot:%s.date' % self.plotstew.pk:
                 {'MIN': "2013-01-01 00:00:00",
                  'MAX': "2014-12-31 00:00:00"}}))

        self.assertEqual(
            {p3},
            self._execute_and_process_filter(
                {'udf:plot:%s.date' % self.plotstew.pk:
                 {'MIN': "2015-01-01 00:00:00"}}))

    def test_cudf_is_search(self):
        p1, __, p3 = self._setup_collection_udfs()

        self.assertEqual(
            {p1, p3},
            self._execute_and_process_filter(
                {'udf:plot:%s.action' % self.plotstew.pk: {'IS': 'prune'}}))

    def test_cudf_compound_search_passes_date(self):
        p1, __, p3 = self._setup_collection_udfs()

        self.assertEqual(
            {p1},
            self._execute_and_process_filter(
                {'udf:plot:%s.action' % self.plotstew.pk: {'IS': 'prune'},
                 'udf:plot:%s.date' % self.plotstew.pk:
                 {'MAX': '2014-05-01 00:00:00'}}))

    def test_cudf_compound_search_fails_nondatenumeric(self):
        p1, __, p3 = self._setup_collection_udfs()

        with self.assertRaises(search.ParseException):
            self._execute_and_process_filter(
                {'udf:plot:%s.action' % self.plotstew.pk: {'IS': 'prune'},
                 'udf:plot:%s.date' % self.plotstew.pk: {'MAX': "foo"}})

    def test_cudf_date_min_bound_succeeds(self):
        p1, __, __ = self._setup_collection_udfs()
        self.assertIn(p1,
                      self._execute_and_process_filter(
                          {'udf:plot:%s.action' % self.plotstew.pk:
                           {'IS': 'prune'},
                           'udf:plot:%s.date' % self.plotstew.pk:
                           {'MIN': '2013-09-15 00:00:00'}}))

    def test_cudf_pass_date_matches_udf_value(self):
        p1, __, __ = self._setup_collection_udfs()

        self.assertEqual(
            {p1},
            self._execute_and_process_filter(
                {'udf:plot:%s.action' % self.plotstew.pk: {'IS': 'prune'},
                 'udf:plot:%s.date' % self.plotstew.pk:
                    # Range encompasses p1's prune but not p1's water action
                    {'MIN': '2013-09-01 00:00:00',
                     'MAX': '2013-10-31 00:00:00'}}))

    def test_cudf_fail_date_matches_other_udf_value(self):
        self._setup_collection_udfs()

        self.assertEqual(
            set(),
            self._execute_and_process_filter(
                {'udf:plot:%s.action' % self.plotstew.pk: {'IS': 'water'},
                 'udf:plot:%s.date' % self.plotstew.pk:
                    # Range encompasses p1's prune but not p1's water action
                    {'MIN': '2013-09-01 00:00:00',
                     'MAX': '2013-10-31 00:00:00'}}))
