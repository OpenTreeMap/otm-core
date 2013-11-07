# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.test import TestCase

from treemap.tests import make_instance
from treemap.json_field import get_attr_from_json_field, set_attr_on_json_field


class JsonFieldTests(TestCase):
    def setUp(self):
        self.instance = make_instance()
        self.instance.config = '{"a":"x", "b":{"c":"y"}}'

    def _assert_get(self, model, field_name, value):
        val = get_attr_from_json_field(model, field_name)
        self.assertEqual(val, value)

    def test_get(self):
        self._assert_get(self.instance, "config.a", "x")
        self._assert_get(self.instance, "config.b.c", "y")

    def test_get_returns_none_if_missing(self):
        self._assert_get(self.instance, "config.no", None)
        self._assert_get(self.instance, "config.b.no", None)
        self._assert_get(self.instance, "config.d.e.no", None)

    def test_get_fails_on_non_dict(self):
        self.assertRaises(ValueError, get_attr_from_json_field,
                          self.instance, "no.no")
        self.assertRaises(KeyError, get_attr_from_json_field,
                          self.instance, "config.a.no")

    def _assert_set(self, model, field_name, value):
        set_attr_on_json_field(model, field_name, value)
        self._assert_get(model, field_name, value)

    def test_set(self):
        self._assert_set(self.instance, "config.a", "1")
        self._assert_set(self.instance, "config.m", "2")
        self._assert_set(self.instance, "config.b.c", "3")
        self._assert_set(self.instance, "config.b.n", "4")
        self._assert_set(self.instance, "config.x.y.z", "5")

    def test_set_fails_on_non_dict(self):
        self.assertRaises(ValueError, set_attr_on_json_field,
                          self.instance, "no.no", "1")
        self.assertRaises(KeyError, set_attr_on_json_field,
                          self.instance, "config.a.no", "1")
        self.assertRaises(KeyError, set_attr_on_json_field,
                          self.instance, "config.b.c.no", "1")
