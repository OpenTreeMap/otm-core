# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
from random import shuffle
from datetime import datetime
import psycopg2

from django.db import connection
from django.db.models import Q
from django.core.exceptions import ValidationError

from django.contrib.gis.geos import Point, Polygon

from treemap.tests import (make_instance, make_commander_user,
                           make_officer_user,
                           set_write_permissions)

from treemap.lib.object_caches import role_field_permissions
from treemap.lib.udf import udf_create

from treemap.instance import create_stewardship_udfs
from treemap.udf import UserDefinedFieldDefinition, UDFDictionary
from treemap.models import Instance, Plot, User
from treemap.audit import AuthorizeException, FieldPermission, Role
from treemap.tests.base import OTMTestCase


def make_collection_udf(instance, name='Stewardship', model='Plot',
                        datatype=None):
    # Need to setup the hstore extension to make UDFs
    psycopg2.extras.register_hstore(connection.cursor(), globally=True)

    if datatype is None:
        datatype = [
            {'type': 'choice',
             'choices': ['water', 'prune'],
             'name': 'action'},
            {'type': 'int',
             'name': 'height'}]

    return UserDefinedFieldDefinition.objects.create(
        instance=instance,
        model_type=model,
        datatype=json.dumps(datatype),
        iscollection=True,
        name=name)


class UDFDictionaryTestCase(OTMTestCase):
    def setUp(self):
        self.p = Point(0, 0)
        self.instance = make_instance(point=self.p)
        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'choice',
                                 'choices': ['a', 'b', 'c']}),
            iscollection=False,
            name='Test choice')

        self.plot = self.plot = Plot(geom=self.p, instance=self.instance)
        self.d = UDFDictionary()
        self.d.set_model_instance(self.plot)

    def test_set_item_to_none_removes_key(self):
        self.d['Test choice'] = 'a'
        self.assertEqual(1, len(self.d.keys()))
        self.d['Test choice'] = None
        self.assertEqual(0, len(self.d.keys()))

    def test_setting_nonexistant_key_to_none_is_a_noop(self):
        # Should not raise an error
        self.d['Test choice'] = None


class ScalarUDFTestCase(OTMTestCase):
    def setUp(self):
        psycopg2.extras.register_hstore(connection.cursor(), globally=True)

        self.p = Point(0, 0)
        self.instance = make_instance(point=self.p)
        self.commander_user = make_commander_user(self.instance)
        set_write_permissions(self.instance, self.commander_user,
                              'Plot',
                              ['udf:Test choice', 'udf:Test string',
                               'udf:Test int', 'udf:Test date',
                               'udf:Test float'])

        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'choice',
                                 'choices': ['a', 'b', 'c']}),
            iscollection=False,
            name='Test choice')

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
            model_type='Plot',
            datatype=json.dumps({'type': 'int'}),
            iscollection=False,
            name='Test int')

        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'float'}),
            iscollection=False,
            name='Test float')

        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({
                'type': 'multichoice',
                'choices': [
                    'a',
                    'contains a',
                    'also does']}),
            iscollection=False,
            name='Test multichoice')

        self.plot = Plot(geom=self.p, instance=self.instance)
        self.plot.save_with_user(self.commander_user)


class ScalarUDFFilterTest(ScalarUDFTestCase):
    def setUp(self):
        super(ScalarUDFFilterTest, self).setUp()

        def create_and_save_with_choice(c, n=1):
            plots = []
            for i in xrange(n):
                plot = Plot(geom=self.p, instance=self.instance)
                plot.udfs['Test choice'] = c
                plot.save_with_user(self.commander_user)
                plots.append(plot)

            return {plot.pk for plot in plots}

        self.choice_a = create_and_save_with_choice('a', n=2)
        self.choice_b = create_and_save_with_choice('b', n=3)
        self.choice_c = create_and_save_with_choice('c', n=7)

    def test_filtering_on_string_and_choice_using_count(self):
        plots = Plot.objects.filter(**{'udfs__Test choice': 'a'})
        self.assertEqual(
            len(self.choice_a),
            plots.count())

    def test_filtering_on_value_works(self):
        plots = Plot.objects.filter(**{'udfs__Test choice': 'b'})
        self.assertEqual(
            self.choice_b,
            {plot.pk for plot in plots})

    def test_filter_on_multichoice_value_works(self):
        plot = Plot(geom=self.p, instance=self.instance)
        plot.udfs['Test multichoice'] = ['a']
        plot.save_with_user(self.commander_user)

        plot = Plot(geom=self.p, instance=self.instance)
        plot.udfs['Test multichoice'] = ['contains a']
        plot.save_with_user(self.commander_user)

        plot = Plot(geom=self.p, instance=self.instance)
        plot.udfs['Test multichoice'] = ['also does']
        plot.save_with_user(self.commander_user)

        # Requires the double quotes in order to not find the other two.
        plots_with_a = Plot.objects.filter(
            **{'udfs__Test multichoice__contains': '"a"'})
        self.assertEqual(plots_with_a.count(), 1)

    def test_combine_with_geom(self):
        plot_a = Plot.objects.get(pk=self.choice_a.pop())
        plot_b = Plot.objects.get(pk=self.choice_b.pop())

        p = Point(10, 0)

        poly = Polygon(((5, -5), (15, -5), (15, 5), (5, 5), (5, -5)))

        plot_a.geom = p
        plot_a.save_with_user(self.commander_user)

        plot_b.geom = p
        plot_b.save_with_user(self.commander_user)

        a_in_poly = Plot.objects.filter(**{'udfs__Test choice': 'a'})\
                                .filter(geom__contained=poly)

        self.assertEqual({plot.pk for plot in a_in_poly},
                         {plot_a.pk, })

        b_in_poly = Plot.objects.filter(**{'udfs__Test choice': 'b'})\
                                .filter(geom__contained=poly)

        self.assertEqual({plot.pk for plot in b_in_poly},
                         {plot_b.pk, })

    def test_search_suffixes(self):
        plot1 = Plot(geom=self.p, instance=self.instance)
        plot1.udfs['Test string'] = 'this is a test'
        plot1.save_with_user(self.commander_user)

        plot2 = Plot(geom=self.p, instance=self.instance)
        plot2.udfs['Test string'] = 'this is aLsO'
        plot2.save_with_user(self.commander_user)

        def run(sfx, val):
            return {plot.pk
                    for plot
                    in Plot.objects.filter(
                        **{'udfs__Test string' + sfx: val})}

        self.assertEqual(set(), run('', 'also'))

        self.assertEqual({plot1.pk, plot2.pk},
                         run('__contains', 'this is a'))

        self.assertEqual({plot2.pk}, run('__icontains', 'this is al'))

    def _setup_dates(self):
        def create_plot_with_date(adate):
            plot = Plot(geom=self.p, instance=self.instance)
            plot.udfs['Test date'] = adate
            plot.save_with_user(self.commander_user)
            return plot

        dates = [
            (2010, 3, 4),
            (2010, 3, 5),
            (2010, 4, 4),
            (2010, 5, 5),
            (2012, 3, 4),
            (2012, 3, 5),
            (2012, 4, 4),
            (2012, 5, 5),
            (2013, 3, 4)]

        dates = [datetime(*adate) for adate in dates]

        # Get dates out of standard order
        shuffle(dates, lambda: 0.5)
        for adate in dates:
            create_plot_with_date(adate)

        return dates

    def test_has_key(self):
        dates = self._setup_dates()
        plots = Plot.objects.filter(**{'udfs__has_key': 'Test date'})
        self.assertEqual(len(plots), len(dates))

    def test_integer_gt_and_lte_constraints(self):
        '''
        The straightforward test
        plots = Plot.objects.filter(**{'udfs__Test int__gt': 20,
                                       'udfs__Test int__lte': 50})
        fails because it does a lexical comparison, not numerical.

        In order to get it to do an integer comparison,
        it is necessary to add a Transform to cast both the
        LHS and RHS of the comparison to `int`.

        So...
        udfs__Test int__gt becomes
        udfs__Test int__int__gt, where
                        ^ this __int is the casting Transform.
        '''
        def create_plot_with_num(anint):
            plot = Plot(geom=self.p, instance=self.instance)
            plot.udfs['Test int'] = anint
            plot.save_with_user(self.commander_user)
            return plot

        # in range
        create_plot_with_num(21)
        create_plot_with_num(50)
        # out of range numerically, but in range lexically
        create_plot_with_num(3)
        create_plot_with_num(300)
        # out of range either way
        create_plot_with_num(2)
        create_plot_with_num(20)

        plots = Plot.objects.filter(**{'udfs__Test int__int__gt': 20,
                                       'udfs__Test int__int__lte': 50})
        self.assertEqual(len(plots), 2)

    def test_float_gt_and_lte_constraints(self):
        '''
        The straightforward test
        plots = Plot.objects.filter(**{'udfs__Test float__gt': 20.5,
                                       'udfs__Test float__lte': 50.0})
        fails because it does a lexical comparison, not numerical.

        In order to get it to do a float comparison,
        it is necessary to add a Transform to cast both the
        LHS and RHS of the comparison to `float`.

        So...
        udfs__Test float__gt becomes
        udfs__Test float__float__gt, where
                          ^ this __float is the casting Transform.

        '''
        def create_plot_with_num(afloat):
            plot = Plot(geom=self.p, instance=self.instance)
            plot.udfs['Test float'] = afloat
            plot.save_with_user(self.commander_user)
            return plot

        # in range
        create_plot_with_num(20.6)
        create_plot_with_num(50.0)
        # out of range numerically, but in range lexically
        create_plot_with_num(3.1)
        create_plot_with_num(300.1)
        # out of range either way
        create_plot_with_num(2.5)
        create_plot_with_num(20.5)

        plots = Plot.objects.filter(
            **{'udfs__Test float__float__gt': 20.5,
               'udfs__Test float__float__lte': 50.0})

        self.assertEqual(len(plots), 2)

    def test_using_q_objects(self):
        qb = Q(**{'udfs__Test choice': 'b'})
        qc = Q(**{'udfs__Test choice': 'c'})

        q = qb | qc

        plots = Plot.objects.filter(q)

        self.assertEqual(
            self.choice_b | self.choice_c,
            {plot.pk for plot in plots})


class UDFAuditTest(OTMTestCase):
    def setUp(self):
        self.p = Point(-8515941.0, 4953519.0)
        self.instance = make_instance(point=self.p)
        self.commander_user = make_commander_user(self.instance)
        set_write_permissions(self.instance, self.commander_user,
                              'Plot', ['udf:Test choice'])

        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'choice',
                                 'choices': ['a', 'b', 'c']}),
            iscollection=False,
            name='Test choice')

        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'string'}),
            iscollection=False,
            name='Test unauth')

        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps([{'type': 'choice',
                                  'name': 'a choice',
                                  'choices': ['a', 'b', 'c']},
                                 {'type': 'string',
                                  'name': 'a string'}]),
            iscollection=True,
            name='Test collection')

        self.plot = Plot(geom=self.p, instance=self.instance)
        self.plot.save_with_user(self.commander_user)

        psycopg2.extras.register_hstore(connection.cursor(), globally=True)

    def test_mask_unauthorized_with_udfs(self):
        officer_user = make_officer_user(self.instance)

        self.plot.udfs['Test choice'] = 'b'
        self.plot.save_with_user(self.commander_user)
        self.plot.udfs['Test unauth'] = 'foo'
        self.plot.save_base()

        newplot = Plot.objects.get(pk=self.plot.pk)
        self.assertEqual(newplot.udfs['Test choice'], 'b')
        self.assertEqual(newplot.udfs['Test unauth'], 'foo')

        newplot = Plot.objects.get(pk=self.plot.pk)
        newplot.mask_unauthorized_fields(self.commander_user)
        self.assertEqual(newplot.udfs['Test choice'], 'b')
        self.assertEqual(newplot.udfs['Test unauth'], None)

        newplot = Plot.objects.get(pk=self.plot.pk)
        newplot.mask_unauthorized_fields(officer_user)
        self.assertEqual(newplot.udfs['Test choice'], None)
        self.assertEqual(newplot.udfs['Test unauth'], None)

    def test_update_field_creates_audit(self):
        self.plot.udfs['Test choice'] = 'b'
        self.plot.save_with_user(self.commander_user)

        last_audit = list(self.plot.audits())[-1]

        self.assertEqual(last_audit.model, 'Plot')
        self.assertEqual(last_audit.model_id, self.plot.pk)
        self.assertEqual(last_audit.field, 'udf:Test choice')
        self.assertEqual(last_audit.previous_value, None)
        self.assertEqual(last_audit.current_value, 'b')

        self.plot.udfs['Test choice'] = 'c'
        self.plot.save_with_user(self.commander_user)

        last_audit = list(self.plot.audits())[-1]

        self.assertEqual(last_audit.model, 'Plot')
        self.assertEqual(last_audit.model_id, self.plot.pk)
        self.assertEqual(last_audit.field, 'udf:Test choice')
        self.assertEqual(last_audit.previous_value, 'b')
        self.assertEqual(last_audit.current_value, 'c')

    def test_cant_edit_unauthorized_collection(self):
        self.plot.udfs['Test collection'] = [
            {'a choice': 'a', 'a string': 's'}]

        self.assertRaises(AuthorizeException,
                          self.plot.save_with_user, self.commander_user)

    def test_cant_edit_unauthorized_field(self):
        self.plot.udfs['Test unauth'] = 'c'
        self.assertRaises(AuthorizeException,
                          self.plot.save_with_user, self.commander_user)

    def test_create_invalid_pending_collection(self):
        pending = self.plot.audits().filter(requires_auth=True)

        self.assertEqual(len(pending), 0)

        role = self.commander_user.get_role(self.instance)
        fp, __ = FieldPermission.objects.get_or_create(
            model_name='Plot', field_name='udf:Test collection',
            permission_level=FieldPermission.WRITE_WITH_AUDIT,
            role=role, instance=self.instance)

        self.plot.udfs['Test collection'] = [
            {'a choice': 'invalid choice', 'a string': 's'}]
        self.assertRaises(ValidationError,
                          self.plot.save_with_user, self.commander_user)


class UDFDefTest(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()

    def _create_and_save_with_datatype(
            self, d, model_type='Plot', name='Blah', iscollection=False):
        return UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type=model_type,
            datatype=json.dumps(d),
            iscollection=iscollection,
            name=name)

    def test_cannot_create_datatype_with_invalid_model(self):
        self.assertRaises(
            ValidationError,
            self._create_and_save_with_datatype,
            {'type': 'string'},
            model_type='InvalidModel')

    def test_cannot_create_datatype_with_nonudf(self):
        self.assertRaises(
            ValidationError,
            self._create_and_save_with_datatype,
            {'type': 'string'},
            model_type='InstanceUser')

    def test_cannot_create_duplicate_udfs(self):
        self._create_and_save_with_datatype(
            {'type': 'string'},
            name='random')

        self.assertRaises(
            ValidationError,
            self._create_and_save_with_datatype,
            {'type': 'string'},
            name='random')

        self._create_and_save_with_datatype(
            {'type': 'string'},
            name='random2')

    def test_cannot_create_datatype_with_existing_field(self):
        self.assertRaises(
            ValidationError,
            self._create_and_save_with_datatype,
            {'type': 'string'},
            name='width')

        self.assertRaises(
            ValidationError,
            self._create_and_save_with_datatype,
            {'type': 'string'},
            name='id')

        self._create_and_save_with_datatype(
            {'type': 'string'},
            name='random')

    def test_must_have_type_key(self):
        self.assertRaises(
            ValidationError,
            self._create_and_save_with_datatype, {})

    def test_invalid_type(self):
        self.assertRaises(
            ValidationError,
            self._create_and_save_with_datatype, {'type': 'woohoo'})

        self._create_and_save_with_datatype({'type': 'float'})

    def test_description_op(self):
        self._create_and_save_with_datatype(
            {'type': 'float',
             'description': 'this is a float field'})

    def test_choices_not_missing(self):
        self.assertRaises(
            ValidationError,
            self._create_and_save_with_datatype,
            {'type': 'choice'})

        self._create_and_save_with_datatype(
            {'type': 'choice',
             'choices': ['a choice', 'another']})

    def test_choices_not_empty(self):
        self.assertRaises(
            ValidationError,
            self._create_and_save_with_datatype,
            {'type': 'choice',
             'choices': []})

        self._create_and_save_with_datatype(
            {'type': 'choice',
             'choices': ['a choice', 'another']})

    def test_cannot_create_choices_with_numeric_values(self):
        with self.assertRaises(ValidationError):
            self._create_and_save_with_datatype(
                {'type': 'choice',
                 'choices': [0, 1, 3, 4, 5]})

    def test_can_create_subfields(self):
        self._create_and_save_with_datatype(
            [{'type': 'choice',
              'name': 'achoice',
              'choices': ['a', 'b']},
             {'type': 'string',
              'name': 'something'}], iscollection=True)

    def test_must_have_name_on_subfields(self):
        self.assertRaises(
            ValidationError,
            self._create_and_save_with_datatype,
            [{'type': 'choice',
              'choices': ['a', 'b']},
             {'type': 'string',
              'name': 'something'}],
            iscollection=True)

        self.assertRaises(
            ValidationError,
            self._create_and_save_with_datatype,
            [{'type': 'choice',
              'choices': ['a', 'b'],
              'name': ''},
             {'type': 'string',
              'name': 'something'}],
            iscollection=True)

        self._create_and_save_with_datatype(
            [{'type': 'choice',
              'name': 'valid name',
              'choices': ['a', 'b']},
             {'type': 'string',
              'name': 'something'}],
            iscollection=True)

    def test_subfields_may_not_have_duplicate_names(self):
        self.assertRaises(
            ValidationError,
            self._create_and_save_with_datatype,
            [{'type': 'choice',
              'name': 'valid name',
              'choices': ['a', 'b']},
             {'type': 'string',
              'name': 'valid name'}],
            name='another',
            iscollection=True)

        self._create_and_save_with_datatype(
            [{'type': 'choice',
              'name': 'valid name',
              'choices': ['a', 'b']},
             {'type': 'string',
              'name': 'valid name2'}],
            iscollection=True)

    def test_iscollection_requires_json_array(self):
        self.assertRaises(
            ValidationError,
            self._create_and_save_with_datatype,
            [{'type': 'choice',
              'name': 'a name',
              'choices': ['a', 'b']},
             {'type': 'string',
              'name': 'something'}],
            iscollection=False)

        self._create_and_save_with_datatype(
            [{'type': 'choice',
              'choices': ['a', 'b'],
              'name': 'a name'},
             {'type': 'string',
              'name': 'something'}],
            iscollection=True)

    def test_not_iscollection_requires_only_a_dict(self):
        self.assertRaises(
            ValidationError,
            self._create_and_save_with_datatype,
            {'type': 'choice',
             'choices': ['a', 'b']},
            iscollection=True)

        self._create_and_save_with_datatype(
            {'type': 'choice',
             'choices': ['a', 'b']},
            iscollection=False)

    def test_subfield_cannot_be_called_id(self):
        self.assertRaises(
            ValidationError,
            self._create_and_save_with_datatype,
            [{'type': 'choice',
              'name': 'id',
              'choices': ['a', 'b']},
             {'type': 'string',
              'name': 'something'}],
            iscollection=True)

        self._create_and_save_with_datatype(
            [{'type': 'choice',
              'name': 'anything else',
              'choices': ['a', 'b']},
             {'type': 'string',
              'name': 'something'}],
            iscollection=True)

    def test_default_values(self):
        with self.assertRaises(ValidationError):
            self._create_and_save_with_datatype(
                [{'type': 'choice',
                  'name': 'a name',
                  'choices': ['a', 'b'],
                  'default': 'c'},
                 {'type': 'string',
                  'name': 'something'}],
                iscollection=True)

        self._create_and_save_with_datatype(
            [{'type': 'choice',
              'name': 'a name',
              'choices': ['a', 'b'],
              'default': 'a'},
             {'type': 'string',
              'name': 'something',
              'default': 'anything'}],
            iscollection=True)

    def test_create_multiple_choice_udf(self):
        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({
                'type': 'multichoice',
                'choices': ['a', 'b']
            }),
            iscollection=False,
            name='a name')

    def test_cannot_create_multiple_choice_udf_with_double_quotes(self):
        with self.assertRaises(ValidationError):
            UserDefinedFieldDefinition.objects.create(
                instance=self.instance,
                model_type='Plot',
                datatype=json.dumps({
                    'type': 'multichoice',
                    'choices': ['a', 'b"']
                }),
                iscollection=False,
                name='a name')

    def test_invalid_names(self):
        with self.assertRaises(ValidationError):
            UserDefinedFieldDefinition.objects.create(
                instance=self.instance,
                model_type='Plot',
                datatype=json.dumps({'type': 'string'}),
                iscollection=False,
                name='%')

        with self.assertRaises(ValidationError):
            UserDefinedFieldDefinition.objects.create(
                instance=self.instance,
                model_type='Tree',
                datatype=json.dumps({'type': 'string'}),
                iscollection=False,
                name='.')

        with self.assertRaises(ValidationError):
            UserDefinedFieldDefinition.objects.create(
                instance=self.instance,
                model_type='Plot',
                datatype=json.dumps({'type': 'string'}),
                iscollection=False,
                name='__contains')


class ScalarUDFInstanceIsolationTest(OTMTestCase):
    def setUp(self):
        self.p = Point(-8515941.0, 4953519.0)
        self.instances = [
            make_instance(point=self.p),
            make_instance(point=self.p)
        ]
        self.commander_users = [
            make_commander_user(i, username='commander%d' % i.pk)
            for i in self.instances]
        for i in range(len(self.instances)):
            set_write_permissions(self.instances[i], self.commander_users[i],
                                  'Plot', ['udf:Test choice'])
        self.choice_udfds = [
            UserDefinedFieldDefinition.objects.create(
                instance=i,
                model_type='Plot',
                datatype=json.dumps({'type': 'choice',
                                     'choices': ['a', 'b', 'c']}),
                iscollection=False,
                name='Test choice') for i in self.instances]

        self.plots = [
            Plot(geom=self.p, instance=i) for i in self.instances]

        for i in range(len(self.plots)):
            self.plots[i].save_with_user(self.commander_users[i])

        psycopg2.extras.register_hstore(connection.cursor(), globally=True)

    def test_update_choice_value_in_one_instance(self):
        # Add and assert a choice value in both instances
        for i in range(len(self.plots)):
            self.plots[i].udfs['Test choice'] = 'a'
            self.plots[i].save_with_user(self.commander_users[i])

            self.plots[i] = Plot.objects.get(pk=self.plots[i].pk)
            audit = self.plots[i].audits().get(field='udf:Test choice')

            self.assertEqual(
                self.plots[i].udfs['Test choice'], 'a')
            self.assertEqual(
                audit.current_value, 'a')

        # Update a choice name in the first instance only and assert the change
        self.choice_udfds[0].update_choice('a', 'm')

        self.plots[0] = Plot.objects.get(pk=self.plots[0].pk)
        audit0 = self.plots[0].audits().get(field='udf:Test choice')

        self.assertEqual(
            self.plots[0].udfs['Test choice'], 'm')
        self.assertEqual(
            audit0.current_value, 'm')

        choice0 = UserDefinedFieldDefinition.objects.get(
            pk=self.choice_udfds[0].pk)

        self.assertEqual(
            set(choice0.datatype_dict['choices']),
            {'m', 'b', 'c'})

        # Assert that the second instance is unchanged
        self.plots[1] = Plot.objects.get(pk=self.plots[1].pk)
        audit0 = self.plots[1].audits().get(field='udf:Test choice')

        self.assertEqual(
            self.plots[1].udfs['Test choice'], 'a')
        self.assertEqual(
            audit0.current_value, 'a')

        choice1 = UserDefinedFieldDefinition.objects.get(
            pk=self.choice_udfds[1].pk)

        self.assertEqual(
            set(choice1.datatype_dict['choices']),
            {'a', 'b', 'c'})


class ScalarUDFTest(OTMTestCase):

    def setUp(self):
        self.p = Point(-8515941.0, 4953519.0)
        self.instance = make_instance(point=self.p)

        def make_and_save_type(dtype):
            UserDefinedFieldDefinition.objects.create(
                instance=self.instance,
                model_type='Plot',
                datatype=json.dumps({'type': dtype}),
                iscollection=False,
                name='Test %s' % dtype)

        allowed_types = 'float', 'int', 'string', 'date'

        addl_fields = ['udf:Test %s' % ttype for ttype in allowed_types]
        addl_fields.append('udf:Test choice')
        addl_fields.append('udf:Test multichoice')

        self.commander_user = make_commander_user(self.instance)
        set_write_permissions(self.instance, self.commander_user,
                              'Plot', addl_fields)

        for dtype in allowed_types:
            make_and_save_type(dtype)

        self.choice_udfd = UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'choice',
                                 'choices': ['a', 'b', 'c']}),
            iscollection=False,
            name='Test choice')

        self.multichoice_udfd = UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'multichoice',
                                 'choices': ['a', 'b', 'c']}),
            iscollection=False,
            name='Test multichoice')

        self.plot = Plot(geom=self.p, instance=self.instance)
        self.plot.save_with_user(self.commander_user)

        psycopg2.extras.register_hstore(connection.cursor(), globally=True)

    def _test_datatype(self, field, value):
        self.plot.udfs[field] = value
        self.plot.save_with_user(self.commander_user)

        self.plot = Plot.objects.get(pk=self.plot.pk)

        self.assertEqual(
            self.plot.udfs[field], value)

    def test_int_datatype(self):
        self._test_datatype('Test int', 4)
        self.assertEqual(getattr(self.plot, 'udf:Test int', None), 4)

    def test_int_validation_non_integer(self):
        self.assertRaises(ValidationError,
                          self._test_datatype, 'Test int', 42.3)

        self.assertRaises(ValidationError,
                          self._test_datatype, 'Test int', 'blah')

    def test_float_datatype(self):
        self._test_datatype('Test float', 4.4)
        self.assertEqual(getattr(self.plot, 'udf:Test float', None), 4.4)

    def test_float_validation(self):
        self.assertRaises(ValidationError,
                          self._test_datatype, 'Test float', 'blah')

    def test_cant_update_choices_on_non_choice_model(self):
        floatfield = UserDefinedFieldDefinition\
            .objects\
            .filter(name='Test float')

        self.assertRaises(ValidationError,
                          floatfield[0].update_choice,
                          'a', 'b')

    def test_update_invalid_choice(self):
        self.assertRaises(ValidationError,
                          self.choice_udfd.update_choice,
                          'WHAT?????', 'm')

    def test_multiple_invalid_choices(self):
        self.plot.udfs['Test int'] = 'not an integer'
        self.plot.udfs['Test float'] = 'not a float'

        with self.assertRaises(ValidationError) as ve:
            self.plot.save_with_user(self.commander_user)

        self.assertValidationErrorDictContainsKey(
            ve.exception, 'udf:Test int')
        self.assertValidationErrorDictContainsKey(
            ve.exception, 'udf:Test float')

    def test_empty_choice_deletes_field(self):
        self._test_datatype('Test choice', 'a')
        self.assertEqual(getattr(self.plot, 'udf:Test choice', None), 'a')

        count = Plot.objects.filter(**{
            'udfs__Test choice': 'a'}).count()
        self.assertEqual(count, 1)

        # should remove the udf
        self.plot.udfs['Test choice'] = ''
        self.plot.save_with_user(self.commander_user)

        self.plot = Plot.objects.get(pk=self.plot.pk)

        self.assertIsNone(self.plot.udfs['Test choice'])
        self.assertEqual(getattr(self.plot, 'udf:Test choice', None), None)

        count = Plot.objects.filter(**{
            'udfs__has_key': 'Test choice'}).count()
        self.assertEqual(count, 0)

    def test_delete_choice_value(self):
        self.plot.udfs['Test choice'] = 'a'
        self.plot.save_with_user(self.commander_user)

        self.plot = Plot.objects.get(pk=self.plot.pk)
        audit = self.plot.audits().get(field='udf:Test choice')

        self.assertEqual(
            self.plot.udfs['Test choice'], 'a')
        self.assertEqual(
            audit.current_value, 'a')

        self.choice_udfd.delete_choice('a')

        self.plot = Plot.objects.get(pk=self.plot.pk)
        audit = self.plot.audits().filter(field='udf:Test choice')

        self.assertEqual(
            self.plot.udfs['Test choice'], None)
        self.assertEqual(
            audit.exists(), False)

        choice = UserDefinedFieldDefinition.objects.get(
            pk=self.choice_udfd.pk)

        self.assertEqual(
            set(choice.datatype_dict['choices']),
            {'b', 'c'})

    def test_delete_multichoice_value(self):
        self.plot.udfs['Test multichoice'] = ['a']
        self.plot.save_with_user(self.commander_user)

        self.plot = Plot.objects.get(pk=self.plot.pk)
        audit = self.plot.audits().get(field='udf:Test multichoice')

        self.assertEqual(
            self.plot.udfs['Test multichoice'], ['a'])
        self.assertEqual(
            json.loads(audit.current_value), ['a'])

        self.multichoice_udfd.delete_choice('a')

        self.plot = Plot.objects.get(pk=self.plot.pk)
        audit = self.plot.audits().filter(field='udf:Test multichoice')

        self.assertEqual(self.plot.udfs['Test multichoice'], None)
        self.assertEqual(json.loads(audit[0].current_value), None)

        choice = UserDefinedFieldDefinition.objects.get(
            pk=self.multichoice_udfd.pk)

        self.assertEqual(
            set(choice.datatype_dict['choices']),
            {'b', 'c'})

    def test_update_multichoice_value(self):
        # setup plot and requery
        self.plot.udfs['Test multichoice'] = ['a']
        self.plot.save_with_user(self.commander_user)
        self.plot = Plot.objects.get(pk=self.plot.pk)

        self.multichoice_udfd.update_choice('a', 'weird \\\\\\1a2chars')

        self.plot = Plot.objects.get(pk=self.plot.pk)
        audit = self.plot.audits().get(field='udf:Test multichoice')

        self.assertEqual(
            self.plot.udfs['Test multichoice'], ['weird \\\\\\1a2chars'])
        self.assertEqual(json.loads(audit.current_value),
                         ['weird \\\\\\1a2chars'])

        choice = UserDefinedFieldDefinition.objects.get(
            pk=self.multichoice_udfd.pk)

        self.assertEqual(
            set(choice.datatype_dict['choices']),
            {'weird \\\\\\1a2chars', 'b', 'c'})

        self.plot = Plot.objects.get(pk=self.plot.pk)
        self.multichoice_udfd.update_choice('b', 'd')
        self.assertEqual(
            self.plot.udfs['Test multichoice'], ['weird \\\\\\1a2chars'])

        choice = UserDefinedFieldDefinition.objects.get(
            pk=self.multichoice_udfd.pk)

        self.assertEqual(
            set(choice.datatype_dict['choices']),
            {'weird \\\\\\1a2chars', 'd', 'c'})

    def test_update_choice_value(self):
        self.plot.udfs['Test choice'] = 'a'
        self.plot.save_with_user(self.commander_user)

        self.plot = Plot.objects.get(pk=self.plot.pk)
        audit = self.plot.audits().get(field='udf:Test choice')

        self.assertEqual(
            self.plot.udfs['Test choice'], 'a')
        self.assertEqual(
            audit.current_value, 'a')

        self.choice_udfd.update_choice('a', 'm')

        self.plot = Plot.objects.get(pk=self.plot.pk)
        audit = self.plot.audits().get(field='udf:Test choice')

        self.assertEqual(
            self.plot.udfs['Test choice'], 'm')
        self.assertEqual(
            audit.current_value, 'm')

        choice = UserDefinedFieldDefinition.objects.get(
            pk=self.choice_udfd.pk)

        self.assertEqual(
            set(choice.datatype_dict['choices']),
            {'m', 'b', 'c'})

    def test_choice_datatype(self):
        self._test_datatype('Test choice', 'a')

    def test_choice_validation(self):
        self.assertRaises(ValidationError,
                          self._test_datatype, 'Test choice', 'bad choice')

    def test_date_datatype(self):
        d = datetime.now().replace(microsecond=0)

        self._test_datatype('Test date', d)

    def test_string_datatype(self):
        self._test_datatype('Test string', 'Sweet Plot')

    def test_in_operator(self):
        self.assertNotIn('Test string', self.plot.udfs)
        self.assertNotIn('RanDoM NAme', self.plot.udfs)

    def test_returns_none_for_empty_but_valid_udfs(self):
        self.assertEqual(self.plot.udfs['Test string'],
                         None)

    def test_raises_keyerror_for_invalid_udf(self):
        self.assertRaises(KeyError,
                          lambda: self.plot.udfs['RaNdoName'])


class CollectionUDFTest(OTMTestCase):
    def setUp(self):
        self.p = Point(-8515941.0, 4953519.0)
        self.instance = make_instance(point=self.p)

        self.udf = make_collection_udf(self.instance, 'Stewardship')

        self.commander_user = make_commander_user(self.instance)
        set_write_permissions(self.instance, self.commander_user,
                              'Plot', ['udf:Stewardship'])

        self.plot = Plot(geom=self.p, instance=self.instance)
        self.plot.save_with_user(self.commander_user)

    def test_can_update_choice_option(self):
        stews = [{'action': 'water',
                  'height': 42},
                 {'action': 'prune',
                  'height': 12}]

        self.plot.udfs['Stewardship'] = stews
        self.plot.save_with_user(self.commander_user)

        plot = Plot.objects.get(pk=self.plot.pk)
        audits = [a.current_value for a in
                  plot.audits().filter(field='udf:action')]

        self.assertEqual(self._get_udf_actions(plot), {'water', 'prune'})
        self.assertEqual(audits, ['water', 'prune'])

        self.udf.update_choice('water', 'h2o', name='action')

        plot = Plot.objects.get(pk=self.plot.pk)
        audits = [a.current_value for a in
                  plot.audits().filter(field='udf:action')]

        self.assertEqual(self._get_udf_actions(plot), {'h2o', 'prune'})
        self.assertEqual(audits, ['h2o', 'prune'])

    def _get_udf_actions(self, plot):
        # UDF collection values are not ordered! So compare using sets.
        return {value['action'] for value in plot.udfs['Stewardship']}

    def test_can_delete_choice_option(self):
        stews = [{'action': 'water',
                  'height': 42},
                 {'action': 'prune',
                  'height': 12}]

        self.plot.udfs['Stewardship'] = stews
        self.plot.save_with_user(self.commander_user)

        plot = Plot.objects.get(pk=self.plot.pk)
        audits = [a.current_value for a in
                  plot.audits().filter(field='udf:action')]

        self.assertEqual(self._get_udf_actions(plot), {'water', 'prune'})
        self.assertEqual(audits, ['water', 'prune'])

        self.udf.delete_choice('water', name='action')

        plot = Plot.objects.get(pk=self.plot.pk)
        audits = [a.current_value for a in
                  plot.audits().filter(field='udf:action')]

        self.assertEqual(self._get_udf_actions(plot), {'prune'})
        self.assertEqual(audits, ['prune'])

    def test_can_get_and_set(self):
        stews = [{'action': 'water',
                  'height': 42},
                 {'action': 'prune',
                  'height': 12}]

        self.plot.udfs['Stewardship'] = stews

        self.plot.save_with_user(self.commander_user)

        reloaded_plot = Plot.objects.get(pk=self.plot.pk)

        new_stews = reloaded_plot.udfs['Stewardship']

        for expected_stew, actual_stew in zip(stews, new_stews):
            self.assertIn('id', actual_stew)

            self.assertDictContainsSubset(expected_stew, actual_stew)

    def test_can_delete(self):
        stews = [{'action': 'water',
                  'height': 42},
                 {'action': 'prune',
                  'height': 12}]

        self.plot.udfs['Stewardship'] = stews
        self.plot.save_with_user(self.commander_user)

        reloaded_plot = Plot.objects.get(pk=self.plot.pk)
        all_new_stews = reloaded_plot.udfs['Stewardship']

        # Keep only 'prune' (note that UDF collection values are unordered)
        new_stews = filter(lambda v: v['action'] == 'prune', all_new_stews)
        reloaded_plot.udfs['Stewardship'] = new_stews
        reloaded_plot.save_with_user(self.commander_user)

        reloaded_plot = Plot.objects.get(pk=self.plot.pk)
        newest_stews = reloaded_plot.udfs['Stewardship']

        self.assertEqual(len(newest_stews), 1)
        self.assertEqual(newest_stews[0]['action'], 'prune')
        self.assertEqual(newest_stews[0]['height'], 12)

    # Collection fields used the same validation logic as scalar
    # udfs the point of this section is prove that the code is hooked
    # up, not to exhaustively test datatype validation
    def test_cannot_save_with_invalid_field_name(self):
        self.plot.udfs['Stewardship'] = [
            {'action': 'water',
             'height': 32,
             'random': 'test'}]

        self.assertRaises(
            ValidationError,
            self.plot.save_with_user,
            self.commander_user)

    def test_cannot_save_with_invalid_value(self):
        self.plot.udfs['Stewardship'] = [
            {'action': 'water',
             'height': 'too high'}]

        self.assertRaises(
            ValidationError,
            self.plot.save_with_user,
            self.commander_user)


class UdfDeleteTest(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.commander_user = make_commander_user(self.instance)

    def test_delete_udf_deletes_perms_collection(self):
        set_write_permissions(self.instance, self.commander_user,
                              'Plot', ['udf:Test choice'])

        udf_def = UserDefinedFieldDefinition(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps([{'name': 'pick',
                                  'type': 'choice',
                                  'choices': ['a', 'b', 'c']},
                                 {'type': 'int',
                                  'name': 'height'}]),
            iscollection=True,
            name='Test choice')

        udf_def.save()

        qs = FieldPermission.objects.filter(
            field_name='udf:Test choice',
            model_name='Plot')

        self.assertTrue(qs.exists())
        udf_def.delete()
        self.assertFalse(qs.exists())

    def test_delete_udf_deletes_perms_value(self):
        set_write_permissions(self.instance, self.commander_user,
                              'Plot', ['udf:Test string'])

        udf_def = UserDefinedFieldDefinition(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'string'}),
            iscollection=False,
            name='Test string')

        udf_def.save()

        qs = FieldPermission.objects.filter(
            field_name='udf:Test string',
            model_name='Plot')

        self.assertTrue(qs.exists())
        udf_def.delete()
        self.assertFalse(qs.exists())

    def test_delete_udf_deletes_mobile_api_field(self):
        udf_def = UserDefinedFieldDefinition(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'string'}),
            iscollection=False,
            name='Test string')
        udf_def.save()

        self.instance.mobile_api_fields = [
            {'header': 'fields', 'model': 'plot',
             'field_keys': ['plot.udf:Test string']}]
        self.instance.save()

        udf_def.delete()

        updated_instance = Instance.objects.get(pk=self.instance.pk)
        self.assertEquals(
            0, len(updated_instance.mobile_api_fields[0]['field_keys']))

    def test_delete_cudf_deletes_mobile_api_field_group(self):
        tree_udf_def = UserDefinedFieldDefinition(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps([{'name': 'pick',
                                  'type': 'choice',
                                  'choices': ['a', 'b', 'c']},
                                 {'type': 'int',
                                  'name': 'height'}]),
            iscollection=True,
            name='Choices')
        tree_udf_def.save()
        plot_udf_def = UserDefinedFieldDefinition(
            instance=self.instance,
            model_type='Tree',
            datatype=json.dumps([{'name': 'pick',
                                  'type': 'choice',
                                  'choices': ['1', '2', '3']},
                                 {'type': 'int',
                                  'name': 'times'}]),
            iscollection=True,
            name='Choices')
        plot_udf_def.save()

        self.instance.mobile_api_fields = [
            {'header': 'plot', 'model': 'plot', 'field_keys': ['plot.width']},
            {'header': 'Choices', 'sort_key': 'pick',
             'collection_udf_keys': ['plot.udf:Choices', 'tree.udf:Choices']}
        ]
        self.instance.save()

        tree_udf_def.delete()

        updated_instance = Instance.objects.get(pk=self.instance.pk)
        self.assertEquals(1, len(
            updated_instance.mobile_api_fields[1]['collection_udf_keys']))

        plot_udf_def.delete()

        updated_instance = Instance.objects.get(pk=self.instance.pk)
        self.assertEquals(1, len(updated_instance.mobile_api_fields))


class UdfCRUTestCase(OTMTestCase):
    def setUp(self):
        User._system_user.save_base()

        self.instance = make_instance()
        create_stewardship_udfs(self.instance)
        self.user = make_commander_user(self.instance)

        set_write_permissions(self.instance, self.user,
                              'Plot', ['udf:Test choice'])

        self.udf = UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'choice',
                                 'choices': ['a', 'b', 'c']}),
            iscollection=False,
            name='Test choice')


class UdfCreateTest(UdfCRUTestCase):
    def test_create_non_choice_udf(self):
        body = {'udf.name': ' cool udf  ',
                'udf.model': 'Plot',
                'udf.type': 'string'}

        udf = udf_create(body, self.instance)
        self.assertEqual(udf.instance_id, self.instance.pk)
        self.assertEqual(udf.model_type, 'Plot')
        self.assertEqual(udf.name, 'cool udf')
        self.assertEqual(udf.datatype_dict['type'], 'string')

    def test_adds_udf_to_role_when_created(self):
        body = {'udf.name': 'cool udf',
                'udf.model': 'Plot',
                'udf.type': 'string'}

        udf_create(body, self.instance)

        roles_in_instance = Role.objects.filter(instance=self.instance)

        self.assertGreater(len(roles_in_instance), 0)

        for role in roles_in_instance:
            perms = [perm.field_name
                     for perm in role_field_permissions(role, self.instance)]

            self.assertIn('udf:cool udf', perms)

    def test_create_choice_udf(self):
        body = {'udf.name': 'cool udf',
                'udf.model': 'Plot',
                'udf.type': 'choice',
                'udf.choices': ['a', 'b', 'c']}

        udf = udf_create(body, self.instance)

        self.assertEqual(udf.instance_id, self.instance.pk)
        self.assertEqual(udf.model_type, 'Plot')
        self.assertEqual(udf.name, 'cool udf')
        self.assertEqual(udf.datatype_dict['type'], 'choice')
        self.assertEqual(udf.datatype_dict['choices'], ['a', 'b', 'c'])

    def test_invalid_choice_list(self):
        body = {'udf.name': 'cool udf',
                'udf.model': 'Plot',
                'udf.type': 'choice'}

        self.assertRaises(ValidationError, udf_create, body, self.instance)

        body = {'udf.name': 'cool udf',
                'udf.model': 'Plot',
                'udf.type': 'choice',
                'udf.choices': ['', 'a']}

        self.assertRaises(ValidationError, udf_create, body, self.instance)

        body = {'udf.name': 'cool udf',
                'udf.model': 'Plot',
                'udf.type': 'choice',
                'udf.choices': ['a', 'a']}

        self.assertRaises(ValidationError, udf_create, body, self.instance)

    def test_missing_params(self):
        body = {'udf.model': 'Plot',
                'udf.type': 'string',
                'udf.choices': []}

        self.assertRaises(ValidationError, udf_create, body, self.instance)

        body = {'udf.name': 'cool udf',
                'udf.type': 'string',
                'udf.choices': []}

        self.assertRaises(ValidationError, udf_create, body, self.instance)

        body = {'udf.name': 'cool udf',
                'udf.model': 'Plot'}

        self.assertRaises(ValidationError, udf_create, body, self.instance)

    def test_empty_name(self):
        body = {'udf.name': '',
                'udf.model': 'Plot',
                'udf.type': 'string'}

        self.assertRaises(ValidationError, udf_create, body, self.instance)

    def test_duplicate_name(self):
        body = {'udf.name': 'Test choice',
                'udf.model': 'Plot',
                'udf.type': 'string'}

        self.assertRaises(ValidationError, udf_create, body, self.instance)

    def test_invalid_model_name(self):
        body = {'udf.name': 'Testing choice',
                'udf.model': 'Shoe',
                'udf.type': 'string'}

        self.assertRaises(ValidationError, udf_create, body, self.instance)
