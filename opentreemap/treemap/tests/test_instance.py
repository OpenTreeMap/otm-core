# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
from copy import deepcopy
from unittest import skip

from django.core.exceptions import ValidationError

from treemap.instance import (
    add_species_to_instance, DEFAULT_MOBILE_API_FIELDS, API_FIELD_ERRORS,
    create_stewardship_udfs
)
from treemap.models import ITreeRegion
from treemap.udf import UserDefinedFieldDefinition
from treemap.species import SPECIES
from treemap.species.codes import species_codes_for_regions
from treemap.tests import make_instance
from treemap.tests.base import OTMTestCase
from treemap.tests.test_udfs import make_collection_udf


class AddSpeciesToInstanceTests(OTMTestCase):
    def _assert_right_species_for_region(self, instance):
        add_species_to_instance(instance)
        self.assertNotEqual(len(SPECIES),
                            len(instance.species_set.all()))
        otm_codes = species_codes_for_regions(['NoEastXXX'])
        self.assertEqual(len(otm_codes), len(instance.species_set.all()))

    def test_adds_species_based_on_itree_region(self):
        region = ITreeRegion.objects.get(code='NoEastXXX')
        instance = make_instance(point=region.geometry.point_on_surface)
        self._assert_right_species_for_region(instance)

    def test_adds_species_based_on_default_itree_region(self):
        instance = make_instance()
        instance.itree_region_default = 'NoEastXXX'
        self._assert_right_species_for_region(instance)

    def test_all_species_added_when_no_itree_region(self):
        instance = make_instance()
        add_species_to_instance(instance)
        self.assertEqual(len(SPECIES), len(instance.species_set.all()))


class InstanceMobileApiFieldsTests(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        datatype = [
            {'type': 'choice', 'choices': ['love', 'hug'], 'name': 'action'},
            {'type': 'int', 'name': 'times'},
            {'type': 'date', 'name': 'day'},
        ]
        create_stewardship_udfs(self.instance)
        make_collection_udf(self.instance, model='Plot', name='Caring',
                            datatype=datatype)
        make_collection_udf(self.instance, model='Tree', name='Caring',
                            datatype=datatype)

        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'string'}),
            iscollection=False,
            name='Name')

        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Tree',
            datatype=json.dumps({'type': 'int'}),
            iscollection=False,
            name='Man Units')

    @skip("Skipping until mobile api field validation is re-enabled")
    def test_default_api_fields(self):
        # If the default fields fail validation, that's very bad
        fields = deepcopy(DEFAULT_MOBILE_API_FIELDS)
        for group in fields:
            group['header'] = str(group['header'])  # coerce lazy translations

        self.instance.mobile_api_fields = fields
        self.instance.save()

    def assert_raises_code(self, msg, fields):
        with self.assertRaises(ValidationError) as m:
            self.instance.mobile_api_fields = fields
            self.instance.save()

        val_err = m.exception
        self.assertIn('mobile_api_fields', val_err.message_dict)
        self.assertIn(msg, val_err.message_dict['mobile_api_fields'])

    @skip("Skipping until mobile api field validation is re-enabled")
    def test_basic_errors(self):
        self.assert_raises_code(API_FIELD_ERRORS['no_field_groups'], [])
        self.assert_raises_code(API_FIELD_ERRORS['no_field_groups'], {})

        self.assert_raises_code(API_FIELD_ERRORS['group_has_no_header'], [
            {'header': '', 'field_keys': ['tree.height']}
        ])
        self.assert_raises_code(API_FIELD_ERRORS['group_has_no_header'], [
            {'field_keys': ['tree.height']}
        ])

        self.assert_raises_code(API_FIELD_ERRORS['group_has_no_keys'], [
            {'header': 'Trees'}
        ])
        self.assert_raises_code(API_FIELD_ERRORS['group_has_no_keys'], [
            {'header': 'Trees', 'field_keys': []}
        ])
        self.assert_raises_code(API_FIELD_ERRORS['group_has_no_keys'], [
            {'header': 'Trees', 'collection_udf_keys': []}
        ])

        self.assert_raises_code(API_FIELD_ERRORS['group_has_both_keys'], [
            {'header': 'Trees', 'field_keys': ['plot.width', 'plot.length'],
             'collection_udf_keys': ['plot.udf:Stewardship']}
        ])

    @skip("Skipping until mobile api field validation is re-enabled")
    def test_collection_udf_errors(self):
        self.assert_raises_code(API_FIELD_ERRORS['group_has_no_sort_key'], [
            {'header': 'Trees', 'sort_key': '',
             'collection_udf_keys': ['plot.udf:Stewardship']}
        ])
        self.assert_raises_code(API_FIELD_ERRORS['group_has_no_sort_key'], [
            {'header': 'Trees',
             'collection_udf_keys': ['plot.udf:Stewardship']}
        ])

        self.assert_raises_code(API_FIELD_ERRORS['group_has_missing_cudf'], [
            {'header': 'Trees',
             'collection_udf_keys': ['plot.udf:Not a field']}
        ])
        # UDF: Name exists, but it is not a collection field
        self.assert_raises_code(API_FIELD_ERRORS['group_has_missing_cudf'], [
            {'header': 'Trees',
             'collection_udf_keys': ['plot.udf:Name']}
        ])
        # Similar for plot.width
        self.assert_raises_code(API_FIELD_ERRORS['group_has_missing_cudf'], [
            {'header': 'Trees',
             'collection_udf_keys': ['plot.width']}
        ])

        self.assert_raises_code(
            API_FIELD_ERRORS['group_has_invalid_sort_key'],
            [
                {'header': 'Trees', 'sort_key': 1,
                 'collection_udf_keys': ['plot.udf:Stewardship',
                                         'tree.udf:Stewardship']}
            ]
        )
        self.assert_raises_code(
            API_FIELD_ERRORS['group_has_invalid_sort_key'],
            [
                {'header': 'Trees', 'sort_key': 'Date Created',
                 'collection_udf_keys': ['plot.udf:Stewardship',
                                         'tree.udf:Stewardship']}
            ]
        )

    @skip("Skipping until mobile api field validation is re-enabled")
    def test_standard_errors(self):
        self.assert_raises_code(API_FIELD_ERRORS['duplicate_fields'], [
            {'header': 'Fields', 'field_keys': ['tree.udf:Man Units',
                                                'tree.height']},
            {'header': 'Other things', 'field_keys': ['plot.width',
                                                      'tree.height']}
        ])
        self.assert_raises_code(API_FIELD_ERRORS['duplicate_fields'], [
            {'header': 'Fields', 'sort_key': 'Date',
             'collection_udf_keys': [
                 'tree.udf:Stewardship', 'tree.udf:Stewardship']},
            {'header': 'Other fields', 'sort_key': 'Date',
             'collection_udf_keys': [
                 'tree.udf:Caring', 'tree.udf:Stewardship']}
        ])

        self.assert_raises_code(
            API_FIELD_ERRORS['invalid_field'] % {'field': 'hydrant.valves'},
            [{'header': 'Trees', 'field_keys': ['hydrant.valves']}]
        )
        self.assert_raises_code(
            API_FIELD_ERRORS['invalid_field'] % {'field': 'length'},
            [{'header': 'Trees', 'field_keys': ['length']}]
        )

        self.assert_raises_code(API_FIELD_ERRORS['missing_field'], [
            {'header': 'Trees', 'field_keys': ['tree.udf:Stewardship']}
        ])
        self.assert_raises_code(API_FIELD_ERRORS['missing_field'], [
            {'header': 'Trees', 'field_keys': ['plot.udf:Not a field']}
        ])
        self.assert_raises_code(API_FIELD_ERRORS['missing_field'], [
            {'header': 'Trees', 'field_keys': ['plot.doesnotexist']}
        ])
