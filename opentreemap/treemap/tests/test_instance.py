# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from django.core.exceptions import ValidationError
from django.utils.encoding import force_text

from treemap.instance import (add_species_to_instance, create_stewardship_udfs,
                              InstanceBounds)
from treemap.models import ITreeRegion, Species
from treemap.search_fields import (INSTANCE_FIELD_ERRORS,
                                   DEFAULT_MOBILE_API_FIELDS,
                                   DEFAULT_WEB_DETAIL_FIELDS)
from treemap.udf import UserDefinedFieldDefinition
from treemap.species import SPECIES
from treemap.species.codes import species_codes_for_regions
from treemap.tests import (make_instance, make_simple_boundary,
                           make_anonymous_boundary)
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


class ThumbprintTests(OTMTestCase):
    def test_species_thumbprint(self):
        instance = make_instance()
        add_species_to_instance(instance)
        thumbprint1 = instance.species_thumbprint
        s = Species.objects.get(instance=instance, common_name='Afghan pine')
        s.common_name = 'Afghan pony'
        s.save_with_system_user_bypass_auth()
        thumbprint2 = instance.species_thumbprint
        self.assertNotEqual(thumbprint1, thumbprint2)

        s = Species.objects.filter(instance=instance, common_name='Acacia')
        s.delete()
        thumbprint3 = instance.species_thumbprint
        self.assertNotEqual(thumbprint2, thumbprint3)

    def test_boundary_thumbprint(self):
        b = make_simple_boundary('n', n=0)
        instance = make_instance()
        thumbprint1 = instance.boundary_thumbprint
        b.name = 'n1'
        b.save()
        thumbprint2 = instance.boundary_thumbprint
        self.assertNotEqual(thumbprint1, thumbprint2)

    def test_two_boundary_thumbprint(self):
        make_simple_boundary('n1', n=0)
        instance = make_instance()
        thumbprint1 = instance.boundary_thumbprint
        make_simple_boundary('n2', n=1)
        thumbprint2 = instance.boundary_thumbprint
        self.assertNotEqual(thumbprint1, thumbprint2)

    def test_anonymous_boundary_thumbprint(self):
        make_simple_boundary('n', n=0)
        instance = make_instance()
        thumbprint1 = instance.boundary_thumbprint
        make_anonymous_boundary(n=1)
        thumbprint2 = instance.boundary_thumbprint
        self.assertEqual(thumbprint1, thumbprint2)


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

    def test_default_api_fields(self):
        self.instance.mobile_api_fields = DEFAULT_MOBILE_API_FIELDS
        self.instance.save()

    def assert_raises_code(self, msg, fields):
        with self.assertRaises(ValidationError) as m:
            self.instance.mobile_api_fields = fields
            self.instance.save()

        val_err = m.exception
        self.assertIn('mobile_api_fields', val_err.message_dict)
        messages = {force_text(e) for e
                    in val_err.message_dict['mobile_api_fields']}
        self.assertIn(force_text(msg), messages)

    def test_basic_errors(self):
        self.assert_raises_code(INSTANCE_FIELD_ERRORS['no_field_groups'], [])
        self.assert_raises_code(INSTANCE_FIELD_ERRORS['no_field_groups'], {})

        self.assert_raises_code(INSTANCE_FIELD_ERRORS['group_has_no_header'], [
            {'header': '', 'field_keys': ['tree.height']}
        ])
        self.assert_raises_code(INSTANCE_FIELD_ERRORS['group_has_no_header'], [
            {'field_keys': ['tree.height']}
        ])

        self.assert_raises_code(INSTANCE_FIELD_ERRORS['group_has_no_keys'], [
            {'header': 'Trees'}
        ])
        self.assert_raises_code(INSTANCE_FIELD_ERRORS['group_has_no_keys'], [
            {'header': 'Trees', 'collection_udf_keys': None}
        ])

        self.assert_raises_code(INSTANCE_FIELD_ERRORS['group_has_both_keys'], [
            {'header': 'Trees',
             'field_keys': ['plot.width', 'plot.length'],
             'collection_udf_keys': ['plot.udf:Stewardship']}
        ])

    def test_collection_udf_errors(self):
        self.assert_raises_code(
            INSTANCE_FIELD_ERRORS['group_has_no_sort_key'], [
                {'header': 'Trees', 'sort_key': '',
                 'collection_udf_keys': ['plot.udf:Stewardship']}
            ])
        self.assert_raises_code(
            INSTANCE_FIELD_ERRORS['group_has_no_sort_key'], [
                {'header': 'Trees',
                 'collection_udf_keys': ['plot.udf:Stewardship']}
            ])

        self.assert_raises_code(
            INSTANCE_FIELD_ERRORS['group_has_missing_cudf'], [
                {'header': 'Trees',
                 'collection_udf_keys': ['plot.udf:Not a field']}
            ])
        # UDF: Name exists, but it is not a collection field
        self.assert_raises_code(
            INSTANCE_FIELD_ERRORS['group_has_missing_cudf'], [
                {'header': 'Trees',
                 'collection_udf_keys': ['plot.udf:Name']}
            ])
        # Similar for plot.width
        self.assert_raises_code(
            INSTANCE_FIELD_ERRORS['group_has_missing_cudf'], [
                {'header': 'Trees',
                 'collection_udf_keys': ['plot.width']}
            ])

        self.assert_raises_code(
            INSTANCE_FIELD_ERRORS['group_has_invalid_sort_key'],
            [
                {'header': 'Trees', 'sort_key': 1,
                 'collection_udf_keys': ['plot.udf:Stewardship',
                                         'tree.udf:Stewardship']}
            ]
        )
        self.assert_raises_code(
            INSTANCE_FIELD_ERRORS['group_has_invalid_sort_key'],
            [
                {'header': 'Trees', 'sort_key': 'Date Created',
                 'collection_udf_keys': ['plot.udf:Stewardship',
                                         'tree.udf:Stewardship']}
            ]
        )

    def test_standard_errors(self):
        self.assert_raises_code(INSTANCE_FIELD_ERRORS['duplicate_fields'], [
            {'header': 'Best Fields', 'model': 'tree',
             'field_keys': ['tree.udf:Man Units', 'tree.height']},
            {'header': 'Other Fields', 'model': 'tree',
             'field_keys': ['tree.date_planted', 'tree.height']}
        ])
        self.assert_raises_code(INSTANCE_FIELD_ERRORS['duplicate_fields'], [
            {'header': 'Fields', 'sort_key': 'Date',
             'collection_udf_keys': [
                 'tree.udf:Stewardship', 'plot.udf:Stewardship']},
            {'header': 'Other fields', 'sort_key': 'Date',
             'collection_udf_keys': ['tree.udf:Stewardship']}
        ])

        self.assert_raises_code(
            INSTANCE_FIELD_ERRORS['group_missing_model'],
            [{'header': 'Trees', 'field_keys': ['hydrant.valves']}]
        )
        self.assert_raises_code(
            INSTANCE_FIELD_ERRORS['group_missing_model'],
            [{'header': 'Stuff', 'model': 'hydrant',
              'field_keys': ['hydrant.valves']}]
        )

        self.assert_raises_code(
            INSTANCE_FIELD_ERRORS['group_invalid_model'],
            [{'header': 'Trees', 'model': 'tree', 'field_keys': ['length']}]
        )

        self.assert_raises_code(INSTANCE_FIELD_ERRORS['missing_field'], [
            {'header': 'Trees', 'model': 'tree',
             'field_keys': ['tree.udf:Stewardship']}
        ])
        self.assert_raises_code(INSTANCE_FIELD_ERRORS['missing_field'], [
            {'header': 'Trees', 'model': 'plot',
             'field_keys': ['plot.udf:Not a field']}
        ])
        self.assert_raises_code(INSTANCE_FIELD_ERRORS['missing_field'], [
            {'header': 'Trees', 'model': 'plot',
             'field_keys': ['plot.doesnotexist']}
        ])


class InstanceWebDetailFieldsTests(OTMTestCase):
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

    def test_default_detail_fields(self):
        self.instance.web_detail_fields = DEFAULT_WEB_DETAIL_FIELDS
        self.instance.save()

    def assert_raises_code(self, msg, fields):
        with self.assertRaises(ValidationError) as m:
            self.instance.web_detail_fields = fields
            self.instance.save()

        val_err = m.exception
        self.assertIn('web_detail_fields', val_err.message_dict)
        messages = {force_text(e) for e
                    in val_err.message_dict['web_detail_fields']}
        self.assertIn(force_text(msg), messages)

    def test_basic_errors(self):
        self.assert_raises_code(INSTANCE_FIELD_ERRORS['no_field_groups'], [])
        self.assert_raises_code(INSTANCE_FIELD_ERRORS['no_field_groups'], {})

        self.assert_raises_code(INSTANCE_FIELD_ERRORS['group_has_no_header'], [
            {'header': '', 'field_keys': ['tree.height']}
        ])
        self.assert_raises_code(INSTANCE_FIELD_ERRORS['group_has_no_header'], [
            {'field_keys': ['tree.height']}
        ])

        self.assert_raises_code(INSTANCE_FIELD_ERRORS['group_has_no_keys'], [
            {'header': 'Trees'}
        ])
        self.assert_raises_code(INSTANCE_FIELD_ERRORS['group_has_no_keys'], [
            {'header': 'Trees', 'collection_udf_keys': None}
        ])

    def test_collection_udf_errors(self):
        self.assert_raises_code(
            INSTANCE_FIELD_ERRORS['group_has_missing_cudf'], [
                {'header': 'Trees',
                 'collection_udf_keys': ['plot.udf:Not a field']}
            ])
        # UDF: Name exists, but it is not a collection field
        self.assert_raises_code(
            INSTANCE_FIELD_ERRORS['group_has_missing_cudf'], [
                {'header': 'Trees',
                 'collection_udf_keys': ['plot.udf:Name']}
            ])
        # Similar for plot.width
        self.assert_raises_code(
            INSTANCE_FIELD_ERRORS['group_has_missing_cudf'], [
                {'header': 'Trees',
                 'collection_udf_keys': ['plot.width']}
            ])

    def test_standard_errors(self):
        self.assert_raises_code(INSTANCE_FIELD_ERRORS['duplicate_fields'], [
            {'header': 'Best Fields', 'model': 'tree',
             'field_keys': ['tree.udf:Man Units', 'tree.height']},
            {'header': 'Other Fields', 'model': 'tree',
             'field_keys': ['tree.date_planted', 'tree.height']}
        ])
        self.assert_raises_code(INSTANCE_FIELD_ERRORS['duplicate_fields'], [
            {'header': 'Fields', 'sort_key': 'Date',
             'collection_udf_keys': [
                 'tree.udf:Stewardship', 'plot.udf:Stewardship']},
            {'header': 'Other fields', 'sort_key': 'Date',
             'collection_udf_keys': ['tree.udf:Stewardship']}
        ])

        self.assert_raises_code(
            INSTANCE_FIELD_ERRORS['group_missing_model'],
            [{'header': 'Trees', 'field_keys': ['hydrant.valves']}]
        )
        self.assert_raises_code(
            INSTANCE_FIELD_ERRORS['group_missing_model'],
            [{'header': 'Stuff', 'model': 'hydrant',
              'field_keys': ['hydrant.valves']}]
        )

        self.assert_raises_code(
            INSTANCE_FIELD_ERRORS['group_invalid_model'],
            [{'header': 'Trees', 'model': 'tree', 'field_keys': ['length']}]
        )

        self.assert_raises_code(INSTANCE_FIELD_ERRORS['missing_field'], [
            {'header': 'Trees', 'model': 'tree',
             'field_keys': ['tree.udf:Stewardship']}
        ])
        self.assert_raises_code(INSTANCE_FIELD_ERRORS['missing_field'], [
            {'header': 'Trees', 'model': 'plot',
             'field_keys': ['plot.udf:Not a field']}
        ])
        self.assert_raises_code(INSTANCE_FIELD_ERRORS['missing_field'], [
            {'header': 'Trees', 'model': 'plot',
             'field_keys': ['plot.doesnotexist']}
        ])


class InstanceBoundsTests(OTMTestCase):
    def test_create_from_geojson(self):
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [
                                    -75.20416259765625,
                                    40.011838968100335
                                ],
                                [
                                    -75.19866943359375,
                                    40.02551125229787
                                ],
                                [
                                    -75.20484924316406,
                                    40.029717557833266
                                ],
                                [
                                    -75.21171569824219,
                                    40.02340800226773
                                ],
                                [
                                    -75.21102905273438,
                                    40.01762373035351
                                ],
                                [
                                    -75.20416259765625,
                                    40.011838968100335
                                ]
                            ]
                        ]
                    }
                }
            ]
        }
        i = InstanceBounds.create_from_geojson(json.dumps(geojson))
        self.assertTrue(i.geom.valid)

    def test_create_from_geojson_missing_point(self):
        # Same as above, but last point is missing
        invalid_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [
                                    -75.20416259765625,
                                    40.011838968100335
                                ],
                                [
                                    -75.19866943359375,
                                    40.02551125229787
                                ],
                                [
                                    -75.20484924316406,
                                    40.029717557833266
                                ],
                                [
                                    -75.21171569824219,
                                    40.02340800226773
                                ],
                                [
                                    -75.21102905273438,
                                    40.01762373035351
                                ]
                            ]
                        ]
                    }
                }
            ]
        }
        with self.assertRaises(ValidationError):
            InstanceBounds.create_from_geojson(json.dumps(invalid_geojson))

    def test_create_from_geojson_self_intersection(self):
        invalid_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [
                                    -78.28857421875,
                                    41.19518982948959
                                ],
                                [
                                    -76.79443359375,
                                    41.65649719441145
                                ],
                                [
                                    -78.134765625,
                                    39.04478604850143
                                ],
                                [
                                    -74.970703125,
                                    40.896905775860006
                                ],
                                [
                                    -78.28857421875,
                                    41.19518982948959
                                ]
                            ]
                        ]
                    }
                }
            ]
        }

        with self.assertRaises(ValidationError):
            InstanceBounds.create_from_geojson(json.dumps(invalid_geojson))
