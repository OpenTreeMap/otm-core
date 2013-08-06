from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
from datetime import datetime

from django.test import TestCase
from django.core.exceptions import ValidationError

from django.contrib.gis.geos import Point

from treemap.tests import make_instance, make_commander_role

from treemap.udf import UserDefinedFieldDefinition
from treemap.models import User, Plot
from treemap.audit import (AuthorizeException, FieldPermission,
                           approve_or_reject_audit_and_apply)

import psycopg2


class ScalarUDFAuditTest(TestCase):
    def setUp(self):
        self.instance = make_instance()
        self.commander_user = User(username='commander', password='pw')
        self.commander_user.save()
        self.commander_user.roles.add(
            make_commander_role(self.instance,
                                extra_plot_fields=['Test choice']))

        self.p = Point(-8515941.0, 4953519.0)

        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps([{'type': 'choice',
                                  'choices': ['a', 'b', 'c']}]),
            iscollection=False,
            name='Test choice')

        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps([{'type': 'string'}]),
            iscollection=False,
            name='Test unauth')

        self.plot = Plot(geom=self.p, instance=self.instance)
        self.plot.save_with_user(self.commander_user)

        from django.db import connection
        psycopg2.extras.register_hstore(connection.cursor(), globally=True)

    def test_update_field_creates_audit(self):
        self.plot.udf_scalar_values['Test choice'] = 'b'
        self.plot.save_with_user(self.commander_user)

        last_audit = list(self.plot.audits())[-1]

        self.assertEqual(last_audit.model, 'Plot')
        self.assertEqual(last_audit.model_id, self.plot.pk)
        self.assertEqual(last_audit.field, 'Test choice')
        self.assertEqual(last_audit.previous_value, None)
        self.assertEqual(last_audit.current_value, 'b')

        self.plot.udf_scalar_values['Test choice'] = 'c'
        self.plot.save_with_user(self.commander_user)

        last_audit = list(self.plot.audits())[-1]

        self.assertEqual(last_audit.model, 'Plot')
        self.assertEqual(last_audit.model_id, self.plot.pk)
        self.assertEqual(last_audit.field, 'Test choice')
        self.assertEqual(last_audit.previous_value, 'b')
        self.assertEqual(last_audit.current_value, 'c')

    def test_cant_edit_unathorized_field(self):
        self.plot.udf_scalar_values['Test unauth'] = 'c'
        self.assertRaises(AuthorizeException,
                          self.plot.save_with_user, self.commander_user)

        self.commander_user.roles = [
            make_commander_role(self.instance,
                                extra_plot_fields=['Test unauth'])]

        self.plot.udf_scalar_values['Test unauth'] = 'c'
        self.plot.save_with_user(self.commander_user)

    def test_create_and_apply_pending(self):
        pending = self.plot.audits().filter(requires_auth=True)

        self.assertEqual(len(pending), 0)

        role = self.commander_user.roles.all()[0]
        fp, _ = FieldPermission.objects.get_or_create(
            model_name='Plot', field_name='Test unauth',
            permission_level=FieldPermission.WRITE_WITH_AUDIT,
            role=role, instance=self.instance)

        self.plot.udf_scalar_values['Test unauth'] = 'c'
        self.plot.save_with_user(self.commander_user)

        reloaded_plot = Plot.objects.get(pk=self.plot.pk)

        self.assertEqual(
            reloaded_plot.udf_scalar_values['Test unauth'],
            None)

        pending = self.plot.audits().filter(requires_auth=True)

        self.assertEqual(len(pending), 1)

        fp.permission_level = FieldPermission.WRITE_DIRECTLY
        fp.save()

        approve_or_reject_audit_and_apply(pending[0],
                                          self.commander_user,
                                          True)

        reloaded_plot = Plot.objects.get(pk=self.plot.pk)

        self.assertEqual(
            reloaded_plot.udf_scalar_values['Test unauth'],
            'c')


class ScalarUDFDefTest(TestCase):

    def setUp(self):
        self.instance = make_instance()

    def _create_and_save_with_datatype(
            self, d, model_type='Plot', name='Blah'):
        return UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type=model_type,
            datatype=json.dumps(d),
            iscollection=False,
            name=name)

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

    def test_choices_not_empty_or_missing(self):
        self.assertRaises(
            ValidationError,
            self._create_and_save_with_datatype,
            {'type': 'choice'})

        self.assertRaises(
            ValidationError,
            self._create_and_save_with_datatype,
            {'type': 'choice',
             'choices': []})

        self._create_and_save_with_datatype(
            {'type': 'choice',
             'choices': ['a choice', 'another']})


class ScalarUDFTest(TestCase):

    def setUp(self):
        self.instance = make_instance()
        self.p = Point(-8515941.0, 4953519.0)

        def make_and_save_type(dtype):
            UserDefinedFieldDefinition.objects.create(
                instance=self.instance,
                model_type='Plot',
                datatype=json.dumps([{'type': dtype}]),
                iscollection=False,
                name='Test %s' % dtype)

        allowed_types = 'float', 'int', 'string', 'user', 'date'

        addl_fields = ['Test %s' % ttype for ttype in allowed_types]
        addl_fields.append('Test choice')

        self.commander_user = User(username='commander', password='pw')
        self.commander_user.save()
        self.commander_user.roles.add(
            make_commander_role(self.instance, extra_plot_fields=addl_fields))

        for dtype in allowed_types:
            make_and_save_type(dtype)

        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps([{'type': 'choice',
                                  'choices': ['a', 'b', 'c']}]),
            iscollection=False,
            name='Test choice')

        self.plot = Plot(geom=self.p, instance=self.instance)
        self.plot.save_with_user(self.commander_user)

        from django.db import connection
        psycopg2.extras.register_hstore(connection.cursor(), globally=True)

    def _test_datatype(self, field, value):
        self.plot.udf_scalar_values[field] = value
        self.plot.save_with_user(self.commander_user)

        self.plot = Plot.objects.get(pk=self.plot.pk)

        self.assertEqual(
            self.plot.udf_scalar_values[field], value)

    def test_int_datatype(self):
        self._test_datatype('Test int', 4)

    def test_int_validation_non_integer(self):
        self.assertRaises(ValidationError,
                          self._test_datatype, 'Test int', 42.3)

        self.assertRaises(ValidationError,
                          self._test_datatype, 'Test int', 'blah')

    def test_float_datatype(self):
        self._test_datatype('Test float', 4.4)

    def test_float_validation(self):
        self.assertRaises(ValidationError,
                          self._test_datatype, 'Test float', 'blah')

    def test_choice_datatype(self):
        self._test_datatype('Test choice', 'a')

    def test_choice_validation(self):
        self.assertRaises(ValidationError,
                          self._test_datatype, 'Test choice', 'bad choice')

    def test_user_datatype(self):
        self._test_datatype('Test user', self.commander_user)

    def test_date_datatype(self):
        d = datetime.now().replace(microsecond=0)

        self._test_datatype('Test date', d)

    def test_string_datatype(self):
        self._test_datatype('Test string', 'Sweet Plot')

    def test_user_validation_invalid_id(self):
        self.assertRaises(ValidationError,
                          self._test_datatype, 'Test user', 349949)

    def test_user_validation_non_integer(self):
        self.assertRaises(ValidationError,
                          self._test_datatype, 'Test user', 'zztop')

    def test_in_operator(self):
        self.assertEqual('Test string' in self.plot.udf_scalar_values,
                         True)
        self.assertEqual('RanDoM NAme' in self.plot.udf_scalar_values,
                         False)

    def test_returns_none_for_empty_but_valid_udfs(self):
        self.assertEqual(self.plot.udf_scalar_values['Test string'],
                         None)

    def test_raises_keyerror_for_invalid_udf(self):
        self.assertRaises(KeyError,
                          lambda: self.plot.udf_scalar_values['RaNdoName'])
