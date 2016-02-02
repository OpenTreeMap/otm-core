# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from treemap.models import FieldPermission
from treemap.search_fields import mobile_search_fields
from treemap.tests import make_instance, make_commander_user
from treemap.tests.base import OTMTestCase
from treemap.udf import UserDefinedFieldDefinition


class InstanceAdvancedSearch(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.user = make_commander_user(self.instance)

    def assert_search_present(self, **groups):
        search = self.instance.advanced_search_fields(self.user)
        for group_name, field in groups.iteritems():
            self.assertIn(group_name, search)
            search_group = search[group_name]

            field_info = search_group[0]
            if 'label' in field_info:
                field_info['label'] = unicode(field_info['label'])
            if 'id' in field_info:
                del field_info['id']

            self.assertEquals(field_info, field)

    def assert_search_absent(self, group_name):
        search = self.instance.advanced_search_fields(self.user)
        present = group_name in search and len(search[group_name]) > 0
        self.assertFalse(present)

    def test_missing_filters(self):
        self.instance.search_config = {
            'missing': [{'identifier': 'mapFeaturePhoto.id'}]
        }
        self.assert_search_present(
            missing={
                'label': 'Show Missing Photos',
                'identifier': 'mapFeaturePhoto.id',
                'search_type': 'ISNULL',
                'value': 'true'
            }
        )
        self.instance.search_config = {
            'missing': [{'identifier': 'tree.id'}]
        }
        self.assert_search_present(
            missing={
                'label': 'Show Missing Trees',
                'identifier': 'tree.id',
                'search_type': 'ISNULL',
                'value': 'true'
            }
        )

    def test_section_empty_when_field_not_visible(self):
        perm = FieldPermission.objects.filter(role__name='commander',
                                              model_name='Tree',
                                              field_name='diameter')
        self.assertEqual(perm.count(), 1)
        perm.update(permission_level=0)

        self.instance.search_config = {
            'Tree': [{'identifier': 'tree.diameter'}],
        }
        self.assert_search_absent('Tree')

    def test_more_section_empty_when_only_tree_and_plot_fields(self):
        self.instance.search_config = {
            'Tree': [{'identifier': 'tree.diameter'}],
            'Plot': [{'identifier': 'plot.length'}]
        }
        self.assert_search_absent('more')


class InstanceMobileSearch(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()

    def assert_search_present(self, **groups):
        search = mobile_search_fields(self.instance)
        for group_name, field in groups.iteritems():
            self.assertIn(group_name, search)
            search_group = search[group_name]

            field_info = search_group[0]
            if 'label' in field_info:
                field_info['label'] = unicode(field_info['label'])

            self.assertEquals(field_info, field)

    def test_missing_filters(self):
        self.instance.mobile_search_fields = {
            'missing': [{'identifier': 'mapFeaturePhoto.id'}],
            'standard': []
        }
        self.assert_search_present(
            missing={
                'label': 'Show Missing Photos',
                'identifier': 'mapFeaturePhoto.id',
            }
        )
        self.instance.mobile_search_fields = {
            'missing': [{'identifier': 'tree.id'}],
            'standard': []
        }
        self.assert_search_present(
            missing={
                'label': 'Show Missing Trees',
                'identifier': 'tree.id',
            }
        )

    def test_species_search(self):
        self.instance.mobile_search_fields = {
            'standard': [{'identifier': 'species.id'}],
            'missing': []
        }
        self.assert_search_present(
            standard={
                'label': 'Species',
                'identifier': 'species.id',
                'search_type': 'SPECIES'
            }
        )

    def test_choice_search(self):
        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'choice',
                                 'choices': ['a', 'b', 'c']}),
            iscollection=False,
            name='Choice')

        self.instance.mobile_search_fields = {
            'standard': [{'identifier': 'plot.udf:Choice'}],
            'missing': []
        }
        self.assert_search_present(
            standard={
                'label': 'Planting Site Choice',
                'identifier': 'plot.udf:Choice',
                'search_type': 'CHOICE',
                'choices': [{'display_value': '', 'value': ''},
                            {'display_value': 'a', 'value': 'a'},
                            {'display_value': 'b', 'value': 'b'},
                            {'display_value': 'c', 'value': 'c'}]
            }
        )

    def test_multichoice_search(self):
        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Tree',
            datatype=json.dumps({'type': 'multichoice',
                                 'choices': ['a', 'b', 'c']}),
            iscollection=False,
            name='MultiChoice')

        self.instance.mobile_search_fields = {
            'standard': [{'identifier': 'tree.udf:MultiChoice'}],
            'missing': []
        }
        self.assert_search_present(
            standard={
                'label': 'Tree MultiChoice',
                'identifier': 'tree.udf:MultiChoice',
                'search_type': 'MULTICHOICE',
                'choices': [{'display_value': '', 'value': ''},
                            {'display_value': 'a', 'value': 'a'},
                            {'display_value': 'b', 'value': 'b'},
                            {'display_value': 'c', 'value': 'c'}]
            }
        )
