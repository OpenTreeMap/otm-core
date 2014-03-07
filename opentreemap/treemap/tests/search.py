# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
import psycopg2

from datetime import datetime

from django.test import TestCase
from django.db.models import Q
from django.db import connection
from django.utils.tree import Node

from django.contrib.gis.geos import Point, MultiPolygon
from django.contrib.gis.measure import Distance

from treemap.tests import (make_instance, make_commander_user,
                           make_simple_polygon, set_write_permissions)
from treemap.views import _execute_filter
from treemap.models import (Tree, Plot, Boundary, Species)
from treemap.udf import UserDefinedFieldDefinition
from treemap import search


class FilterParserTests(TestCase):
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
        else:
            return node

    def test_key_parser_plots(self):
        # Plots go directly to a field
        match = search._parse_predicate_key('plot.width',
                                            mapping=search.PLOT_MAPPING)
        self.assertEqual(match, 'width')

    def test_key_parser_plots_with_tree_map(self):
        # Plots go directly to a field
        match = search._parse_predicate_key('plot.width',
                                            mapping=search.TREE_MAPPING)
        self.assertEqual(match, 'plot__width')

    def test_udf_fields_look_good(self):
        match = search._parse_predicate_key('plot.udf:The 1st Planter',
                                            mapping=search.PLOT_MAPPING)
        self.assertEqual(match, 'udf:The 1st Planter')

    def test_key_parser_trees(self):
        # Trees require a prefix and the field
        match = search._parse_predicate_key('tree.dbh',
                                            mapping=search.PLOT_MAPPING)
        self.assertEqual(match, 'tree__dbh')

    def test_key_parser_trees_with_tree_map(self):
        # Trees require a prefix and the field
        match = search._parse_predicate_key('tree.dbh',
                                            mapping=search.TREE_MAPPING)
        self.assertEqual(match, 'dbh')

    def test_key_parser_invalid_model(self):
        # Invalid models should raise an exception
        self.assertRaises(search.ParseException,
                          search._parse_predicate_key,
                          "user.id",
                          mapping=search.PLOT_MAPPING)

    def test_key_parser_too_many_dots(self):
        # Dotted fields are also not allowed
        self.assertRaises(search.ParseException,
                          search._parse_predicate_key,
                          "plot.width.other",
                          mapping=search.PLOT_MAPPING)

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
                         {'__contained': b.geom})

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
            mapping=search.PLOT_MAPPING)

        target = ('AND', {('tree__species__id', 113),
                          ('tree__species__flowering', True)})

        self.assertEqual(self.destructure_query_set(pred), target)

    def test_like_predicate(self):
        pred = search._parse_predicate(
            {'tree.steward': {'LIKE': 'thisisatest'}},
            mapping=search.PLOT_MAPPING)

        target = ('AND', {('tree__steward__icontains', 'thisisatest')})

        self.assertEqual(self.destructure_query_set(pred), target)

    def test_parse_predicate(self):
        pred = search._parse_predicate(
            {'plot.width':
             {'MIN': 5,
              'MAX': {'VALUE': 9,
                      'EXCLUSIVE': False}},
             'tree.height':
             9},
            mapping=search.PLOT_MAPPING)

        p1 = ('AND', {('width__lte', 9),
                      ('width__gte', 5),
                      ('tree__height', 9)})

        self.assertEqual(self.destructure_query_set(pred),
                         p1)

        pred = search._parse_predicate(
            {'tree.leaf_type': {'IS': 9},
             'tree.last_updated_by': 4},
            mapping=search.PLOT_MAPPING)

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
            mapping=search.PLOT_MAPPING)

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
            mapping=search.PLOT_MAPPING)

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
            mapping=search.PLOT_MAPPING)

        p1 = ('AND', frozenset({('width__lte', 9),
                                ('width__gte', 5),
                                ('tree__height', 9)}))

        p2 = ('AND', frozenset({('tree__leaf_type', 9),
                                ('tree__last_updated_by', 4)}))

        self.assertEqual(self.destructure_query_set(pred), ('OR', {p1, p2}))

    def test_parse_normal_value(self):
        self.assertEqual(search._parse_value(1), 1)

    def test_parse_list(self):
        self.assertEqual(search._parse_value([1, 2]), [1, 2])

    def test_parse_date(self):
        date = datetime(2013, 4, 1, 12, 0, 0)
        self.assertEqual(search._parse_value("2013-04-01 12:00:00"), date)


class SearchTests(TestCase):
    def setUp(self):
        self.instance = make_instance()
        self.commander = make_commander_user(self.instance)
        self.p1 = Point(-7615441.0, 5953519.0)

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

        p1, _ = self.create_tree_and_plot(
            plotudfs={'Test string': 'testing foo',
                      'Test date': datetime(2010, 1, 9)},
            treeudfs={'Test float': 9.2})

        p2, _ = self.create_tree_and_plot(
            plotudfs={'Test string': 'testing baz or fish',
                      'Test date': datetime(2012, 1, 9)},
            treeudfs={'Test float': 12.0})

        p3, _ = self.create_tree_and_plot(
            plotudfs={'Test string': 'baz',
                      'Test date': datetime(2014, 1, 9)},
            treeudfs={'Test float': 2.2})

        return (p.pk for p in [p1, p2, p3])

    def _execute_and_process_filter(self, filter):
        return {p.pk
                for p
                in _execute_filter(
                    self.instance, json.dumps(filter))}

    def test_udf_numeric_search(self):
        p1, p2, p3 = self._setup_udfs()

        self.assertEqual(
            {p1, p3},
            self._execute_and_process_filter(
                {'tree.udf:Test float': {'MAX': 10.0}}))

    def test_udf_date_search(self):
        p1, p2, _ = self._setup_udfs()

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
        _, _, p3 = self._setup_udfs()

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

        self.assertEqual(
            {p1.pk},
            {p.pk
             for p in _execute_filter(self.instance, species1_filter)})

        self.assertEqual(
            {p2.pk},
            {p.pk
             for p in _execute_filter(self.instance, species2_filter)})

        self.assertEqual(
            0, len(_execute_filter(self.instance, species3_filter)))

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

        self.assertEqual(
            {plot1.pk},
            {p.pk
             for p in _execute_filter(self.instance, boundary1_filter)})

        boundary2_filter = json.dumps({'plot.geom':
                                       {'IN_BOUNDARY': b2.pk}})

        self.assertEqual(
            {plot1.pk, plot2.pk},
            {p.pk
             for p in _execute_filter(self.instance, boundary2_filter)})

        boundary3_filter = json.dumps({'plot.geom':
                                       {'IN_BOUNDARY': b3.pk}})

        self.assertEqual(
            0, len(_execute_filter(self.instance, boundary3_filter)))

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

        ids = {p.pk
               for p
               in _execute_filter(
                   self.instance, diameter_range_filter)}

        self.assertEqual(ids, {p2.pk, p3.pk, p4.pk})

    def test_diameter_max_filter(self):
        p1, p2, p3, p4 = self.setup_diameter_test()

        diameter_range_filter = json.dumps({'tree.diameter':
                                            {'MAX': 3.0}})

        ids = {p.pk
               for p
               in _execute_filter(
                   self.instance, diameter_range_filter)}

        self.assertEqual(ids, {p1.pk})

    def test_within_radius_integration(self):
        test_point = Point(-7615443.0, 5953520.0)
        near_point = Point(-7615444.0, 5953521.0)
        far_point = Point(-9615444.0, 8953521.0)

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

        ids = {p.pk
               for p
               in _execute_filter(
                   self.instance, radius_filter)}

        self.assertEqual(ids, {near_plot.pk})

    def test_diameter_range_filter(self):
        p1, p2, p3, p4 = self.setup_diameter_test()

        diameter_range_filter = json.dumps({'tree.diameter':
                                            {'MAX': 7.0,
                                             'MIN': 3.0}})

        ids = {p.pk
               for p
               in _execute_filter(
                   self.instance, diameter_range_filter)}

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

        result = [o.pk for o in
                  _execute_filter(
                      self.instance, species_like_filter)]

        self.assertEqual(result, [p.pk])

        species.common_name = 'no match'
        species.save_with_user(self.commander)

        result = _execute_filter(
            self.instance, species_like_filter)

        self.assertEqual(len(result), 0)
