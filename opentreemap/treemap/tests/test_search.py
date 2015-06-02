# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
import psycopg2

from datetime import datetime

from django.db.models import Q
from django.db.models.query import ValuesListQuerySet
from django.db import connection
from django.utils.tree import Node

from django.contrib.gis.geos import Point, MultiPolygon
from django.contrib.gis.measure import Distance

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


class FilterParserTests(OTMTestCase):
    def _setup_tree_and_collection_udf(self):
        instance = make_instance()

        self.plotstew = make_collection_udf(instance, model='Plot',
                                            datatype=COLLECTION_UDF_DATATYPE)
        self.treestew = make_collection_udf(instance, model='Tree',
                                            datatype=COLLECTION_UDF_DATATYPE)

        commander = make_commander_user(instance)
        set_write_permissions(instance, commander, 'Plot', ['udf:Stewardship'])
        set_write_permissions(instance, commander, 'Tree', ['udf:Stewardship'])

        d1 = {'action': 'prune', 'date': "2014-05-3 00:00:00"}
        d2 = {'action': 'water', 'date': "2014-04-29 00:00:00"}

        self.plot = Plot(instance=instance, geom=instance.center)
        self.plot.udfs[self.plotstew.name] = [d1]
        self.plot.save_with_user(commander)

        self.tree = Tree(instance=instance, plot=self.plot)
        self.tree.udfs[self.treestew.name] = [d2]
        self.tree.save_with_user(commander)

    def destructure_query_set(self, node):
        """
        Django query objects are not comparable by themselves, but they
        are built from a tree (django.util.tree) and stored in nodes

        This function generates a canonical representation using sets and
        tuples of a query tree

        This can be used to verify that query structures are made correctly
        """
        if isinstance(node, Node):
            n = (node.connector,
                 frozenset(
                     {self.destructure_query_set(c) for c in node.children}))

            if node.negated:
                n = ('NOT', n)

            return n
        elif isinstance(node, tuple):
            # Lists are unhashable, so convert ValuesListQuerySets into tuples
            # for easy comparison
            return tuple(tuple(c) if isinstance(c, ValuesListQuerySet) else c
                         for c in node)
        else:
            return node

    def test_key_parser_plots(self):
        # Plots searches on plot go directly to a field
        match = search._parse_predicate_key('plot.width',
                                            mapping=search.DEFAULT_MAPPING)
        self.assertEqual(match, ('plot', 'width'))

    def test_key_parser_plots_with_tree_map(self):
        # Plots searches on tree go require a prefix
        match = search._parse_predicate_key('plot.width',
                                            mapping=search.TREE_MAPPING)
        self.assertEqual(match, ('plot', 'plot__width'))

    def test_udf_fields_look_good(self):
        match = search._parse_predicate_key('plot.udf:The 1st Planter',
                                            mapping=search.DEFAULT_MAPPING)
        self.assertEqual(match, ('plot', 'udf:The 1st Planter'))

    def test_key_parser_trees(self):
        # Tree searches on plot require a prefix and the field
        match = search._parse_predicate_key('tree.dbh',
                                            mapping=search.DEFAULT_MAPPING)
        self.assertEqual(match, ('tree', 'tree__dbh'))

    def test_key_parser_trees_with_tree_map(self):
        # Tree searches on tree go directly to the field
        match = search._parse_predicate_key('tree.dbh',
                                            mapping=search.TREE_MAPPING)
        self.assertEqual(match, ('tree', 'dbh'))

    def test_key_parser_tree_collection_udf(self):
        # UDF searches go on the specified model's id
        match = search._parse_predicate_key('udf:tree:52.action',
                                            mapping=search.TREE_MAPPING)
        self.assertEqual(match, ('udf:tree:52', 'id'))

    def test_key_parser_plot_collection_udf(self):
        # UDF searches go on the specified model's id
        match = search._parse_predicate_key('udf:plot:52.action',
                                            mapping=search.TREE_MAPPING)
        self.assertEqual(match, ('udf:plot:52', 'plot__id'))

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

        self.assertEqual(self.destructure_query_set(ands),
                         self.destructure_query_set(qa & qb & qc))

    def test_combinator_or(self):
        qa = Q(a=1)
        qb = Q(b=1)
        qc = Q(c=1)

        # Simple OR
        ands = search._apply_combinator('OR', [qa, qb, qc])

        self.assertEqual(self.destructure_query_set(ands),
                         self.destructure_query_set(qa | qb | qc))

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

        inparams = search._parse_dict_value({'IN_BOUNDARY': b.pk})
        self.assertEqual(inparams,
                         {'__within': b.geom})

    def test_constraints_in(self):
        inparams = search._parse_dict_value({'IN': [1, 2, 3]})
        self.assertEqual(inparams,
                         {'__in': [1, 2, 3]})

    def test_constraints_isnull(self):
        inparams = search._parse_dict_value({'ISNULL': True})
        self.assertEqual(inparams, {'__isnull': True})

    def test_constraints_is(self):
        # "IS" is a special case in that we don't need to appl
        # a suffix at all
        isparams = search._parse_dict_value({'IS': 'what'})
        self.assertEqual(isparams,
                         {'': 'what'})

    def test_constraints_invalid_groups(self):
        # It is an error to combine mutually exclusive groups
        self.assertRaises(search.ParseException,
                          search._parse_dict_value,
                          {'IS': 'what', 'IN': [1, 2, 3]})

        self.assertRaises(search.ParseException,
                          search._parse_dict_value,
                          {'IS': 'what', 'MIN': 3})

    def test_constraints_invalid_keys(self):
        self.assertRaises(search.ParseException,
                          search._parse_dict_value,
                          {'EXCLUSIVE': 9})

        self.assertRaises(search.ParseException,
                          search._parse_dict_value,
                          {'IS NOT VALID KEY': 'what'})

    def test_contraint_min(self):
        const = search._parse_dict_value({'MIN': 5})
        self.assertEqual(const, {'__gte': 5})

    def test_contraint_max(self):
        const = search._parse_dict_value({'MAX': 5})
        self.assertEqual(const, {'__lte': 5})

    def test_contraint_max_with_exclusive(self):
        const = search._parse_dict_value(
            {'MAX': {'VALUE': 5,
                     'EXCLUSIVE': True}})
        self.assertEqual(const, {'__lt': 5})

        const = search._parse_dict_value(
            {'MAX': {'VALUE': 5,
                     'EXCLUSIVE': False}})
        self.assertEqual(const, {'__lte': 5})

    def test_constraints_min_and_max(self):
        const = search._parse_dict_value(
            {'MIN': 5,
             'MAX': {'VALUE': 9,
                     'EXCLUSIVE': False}})
        self.assertEqual(const, {'__lte': 9, '__gte': 5})

    def test_within_radius(self):
        const = search._parse_dict_value(
            {'WITHIN_RADIUS': {
                "RADIUS": 5,
                "POINT": {
                    "x": 100,
                    "y": 50}}})
        self.assertEqual(const,
                         {'__dwithin': (Point(100, 50), Distance(m=5))})

    def test_parse_species_predicate(self):
        pred = search._parse_predicate(
            {'species.id': 113,
             'species.flowering': True},
            mapping=search.DEFAULT_MAPPING)

        target = ('AND', {('tree__species__id', 113),
                          ('tree__species__flowering', True)})

        self.assertEqual(self.destructure_query_set(pred), target)

    def test_like_predicate(self):
        pred = search._parse_predicate(
            {'tree.steward': {'LIKE': 'thisisatest'}},
            mapping=search.DEFAULT_MAPPING)

        target = ('AND', {('tree__steward__icontains', 'thisisatest')})

        self.assertEqual(self.destructure_query_set(pred), target)

    def test_parse_predicate(self):
        pred = search._parse_predicate(
            {'plot.width':
             {'MIN': 5,
              'MAX': {'VALUE': 9,
                      'EXCLUSIVE': False}},
             'tree.height': 9},
            mapping=search.DEFAULT_MAPPING)

        p1 = ('AND', {('width__lte', 9),
                      ('width__gte', 5),
                      ('tree__height', 9)})

        self.assertEqual(self.destructure_query_set(pred),
                         p1)

        pred = search._parse_predicate(
            {'tree.leaf_type': {'IS': 9},
             'tree.last_updated_by': 4},
            mapping=search.DEFAULT_MAPPING)

        p2 = ('AND', {('tree__leaf_type', 9),
                      ('tree__last_updated_by', 4)})

        self.assertEqual(self.destructure_query_set(pred),
                         p2)

    def test_parse_predicate_with_tree_map(self):
        pred = search._parse_predicate(
            {'plot.width':
             {'MIN': 5,
              'MAX': {'VALUE': 9,
                      'EXCLUSIVE': False}},
             'tree.height':
             9},
            mapping=search.TREE_MAPPING)

        p1 = ('AND', {('plot__width__lte', 9),
                      ('plot__width__gte', 5),
                      ('height', 9)})

        self.assertEqual(self.destructure_query_set(pred),
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

        self.assertEqual(self.destructure_query_set(pred), p)

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

        self.assertEqual(self.destructure_query_set(pred), p)

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

        self.assertEqual(self.destructure_query_set(pred), ('OR', {p1, p2}))

    def test_parse_collection_udf_simple_predicate(self):
        self._setup_tree_and_collection_udf()
        pred = search._parse_predicate(
            {'udf:plot:%s.action' % self.plotstew.pk: 'prune'},
            mapping=search.DEFAULT_MAPPING)

        target = ('AND', {('id__in', (self.plot.pk,))})

        self.assertEqual(self.destructure_query_set(pred), target)

    def test_parse_collection_udf_fail_nondate_comparison(self):
        self._setup_tree_and_collection_udf()

        with self.assertRaises(search.ParseException):
            search._parse_predicate(
                {'udf:tree:%s.date' % self.treestew.pk: {'MAX': 3}},
                mapping=search.DEFAULT_MAPPING)

    def test_parse_collection_udf_nested_pass_date_comparison(self):
        self._setup_tree_and_collection_udf()

        pred = search._parse_predicate(
            {'udf:tree:%s.date' % self.treestew.pk:
             {'MAX': '2014-05-01 00:00:00'}},
            mapping=search.DEFAULT_MAPPING)

        target = ('AND', {('tree__id__in', (self.tree.pk,))})

        self.assertEqual(self.destructure_query_set(pred), target)

    def test_parse_normal_value(self):
        self.assertEqual(search._parse_value(1), 1)

    def test_parse_list(self):
        self.assertEqual(search._parse_value([1, 2]), [1, 2])

    def test_parse_date(self):
        date = datetime(2013, 4, 1, 12, 0, 0)
        self.assertEqual(search._parse_value("2013-04-01 12:00:00"), date)


class SearchTests(OTMTestCase):
    def setUp(self):
        self.p1 = Point(0, 0)
        self.instance = make_instance(point=self.p1)
        self.commander = make_commander_user(self.instance)

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
        self.plotstew = make_collection_udf(self.instance, model='Plot',
                                            datatype=COLLECTION_UDF_DATATYPE)
        self.treestew = make_collection_udf(self.instance, model='Tree',
                                            datatype=COLLECTION_UDF_DATATYPE)

        set_write_permissions(self.instance, self.commander, 'Plot',
                              [self.plotstew.canonical_name])
        set_write_permissions(self.instance, self.commander, 'Tree',
                              [self.treestew.canonical_name])

        p1, __ = self.create_tree_and_plot(
            plotudfs={self.plotstew.name:
                      [{'action': 'water', 'date': "2013-08-06 00:00:00"},
                       {'action': 'prune', 'date': "2013-09-15 00:00:00"}]},
            treeudfs={self.treestew.name:
                      [{'action': 'water', 'date': "2013-05-15 00:00:00"},
                       {'action': 'water', 'date': None}]})

        p2, __ = self.create_tree_and_plot(
            plotudfs={self.plotstew.name: [
                {'action': 'water', 'date': "2014-11-26 00:00:00"}]},
            treeudfs={self.treestew.name: [
                {'action': 'prune', 'date': "2014-06-23 00:00:00"}]})

        p3, __ = self.create_tree_and_plot(
            plotudfs={self.plotstew.name: [
                {'action': 'water', 'date': "2015-08-05 00:00:00"},
                {'action': 'prune', 'date': "2015-04-13 00:00:00"}]},
            treeudfs={self.treestew.name:
                      [{'action': 'prune', 'date': "2013-06-19 00:00:00"},
                       {'action': 'water', 'date': None}]})

        return (p.pk for p in [p1, p2, p3])

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

    def test_within_radius_integration(self):
        test_point = Point(0, 0)
        near_point = Point(1, 1)
        far_point = Point(250, 250)

        near_plot = Plot(geom=near_point, instance=self.instance)
        near_plot.save_with_user(self.commander)
        near_tree = Tree(plot=near_plot, instance=self.instance)
        near_tree.save_with_user(self.commander)

        # just to make sure that the geospatial
        # query actually filters by distance
        far_plot = Plot(geom=far_point, instance=self.instance)
        far_plot.save_with_user(self.commander)
        far_tree = Tree(plot=far_plot, instance=self.instance)
        far_tree.save_with_user(self.commander)

        radius_filter = json.dumps(
            {'plot.geom':
             {
                 'WITHIN_RADIUS': {
                     'POINT': {'x': test_point.x, 'y': test_point.y},
                     'RADIUS': 10
                 }
             }})

        plots = search.Filter(radius_filter, '', self.instance)\
                      .get_objects(Plot)

        ids = {p.pk for p in plots}

        self.assertEqual(ids, {near_plot.pk})

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

    def test_cudf_compound_search_fails_nondate(self):
        p1, __, p3 = self._setup_collection_udfs()

        with self.assertRaises(search.ParseException):
            self._execute_and_process_filter(
                {'udf:plot:%s.action' % self.plotstew.pk: {'IS': 'prune'},
                 'udf:plot:%s.date' % self.plotstew.pk: {'MAX': 2}})

    def test_cudf_date_min_bound_succeeds(self):
        p1, __, __ = self._setup_collection_udfs()
        self.assertIn(p1,
                      self._execute_and_process_filter(
                          {'udf:plot:%s.action' % self.plotstew.pk:
                           {'IS': 'prune'},
                           'udf:plot:%s.date' % self.plotstew.pk:
                           {'MIN': '2013-09-15 00:00:00'}}))
