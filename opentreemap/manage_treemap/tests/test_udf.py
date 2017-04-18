from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import json

from django.contrib.gis.geos import Point
from django.test.client import RequestFactory

from manage_treemap.views.udf import (udf_list, udf_create, udf_delete,
                                      udf_bulk_update)
from treemap.audit import Audit, FieldPermission
from treemap.instance import Instance, create_stewardship_udfs
from treemap.models import Plot
from treemap.tests import (make_instance, make_commander_user,
                           set_write_permissions, make_request)
from treemap.tests.base import OTMTestCase
from treemap.tests.test_udfs import UdfCRUTestCase
from treemap.udf import UserDefinedFieldDefinition


def _do_create_udf_request(body, instance):
    return udf_create(
        make_request(method='POST', body=json.dumps(body)),
        instance)


class UdfReadUpdateTest(UdfCRUTestCase):
    def test_get_udfs(self):
        resp = udf_list(make_request(), self.instance)

        self.assertIn('udf_models', resp)
        plot_udfs = [m for m in resp['udf_models']
                     if m['name'] == 'Plot']
        self.assertEqual(len(plot_udfs), 1)
        self.assertIn('specs', plot_udfs[0])
        plain_udfs = [s['udf'] for s in plot_udfs[0]['specs']
                      if not s['udf'].iscollection]
        self.assertEqual(len(plain_udfs), 1)
        self.assertEqual(plain_udfs[0].pk, self.udf.pk)


class UdfBulkUpdateTest(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.plot_stew, self.tree_stew = tuple(
            create_stewardship_udfs(self.instance))

        self.user = make_commander_user(self.instance)

    def _make_put_request(self, params):
        request = RequestFactory().put(
            'does/not/matter/', json.dumps(params),
            content_type=u'application/json')
        request.method = 'PUT'
        setattr(request, 'user',  self.user)
        setattr(request, 'instance', self.instance)
        return request

    def _make_point(self, fraction):
        __, __, maxx, maxy = self.instance.bounds_extent
        return Point((maxx - self.instance.center.x) * fraction
                     + self.instance.center.x,
                     (maxy - self.instance.center.y) * fraction
                     + self.instance.center.y,
                     srid=self.instance.center.srid)

    def test_bulk_update_scalar_choices(self):
        plot_udfd = UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'choice',
                                 'choices': ['a', 'b']}),
            iscollection=False,
            name='Test plot choice')

        tree_udfd = UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Tree',
            datatype=json.dumps({'type': 'choice',
                                 'choices': ['x', 'y']}),
            iscollection=False,
            name='Test tree choice')

        set_write_permissions(self.instance, self.user,
                              'Plot', ['udf:Test plot choice'])

        set_write_permissions(self.instance, self.user,
                              'Tree', ['udf:Test tree choice'])

        params = {'choice_changes': [
            {'id': str(plot_udfd.pk), 'changes': [
                {"action": "rename",
                 "original_value": "b",
                 "new_value": "B",
                 "subfield": ""},
                {"action": "add",
                 "original_value": "",
                 "new_value": "p",
                 "subfield": ""}]},
            {'id': str(tree_udfd.pk), 'changes': [
                {"action": "rename",
                 "original_value": "y",
                 "new_value": "Y",
                 "subfield": ""},
                {"action": "add",
                 "original_value": "",
                 "new_value": "q",
                 "subfield": ""}]}]}
        request = self._make_put_request(params)
        udf_bulk_update(request, self.instance)

        plot_udfd.refresh_from_db()
        tree_udfd.refresh_from_db()

        plot_datatype = json.loads(plot_udfd.datatype)
        tree_datatype = json.loads(tree_udfd.datatype)

        self.assertIn('choices', plot_datatype)
        self.assertEqual(set(plot_datatype['choices']), {'a', 'B', 'p'})

        self.assertIn('choices', tree_datatype)
        self.assertEqual(set(tree_datatype['choices']), {'x', 'Y', 'q'})


class UdfDeleteTest(OTMTestCase):
    def setUp(self):
        # Just in case - cleanup other bad test cases
        Instance.objects.all().delete()

        self.instance = make_instance()
        plot_stew, tree_stew = tuple(
            create_stewardship_udfs(self.instance))
        self.cudf = plot_stew
        self.user = make_commander_user(self.instance)

        self.udf = UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'choice',
                                 'choices': ['a', 'b', 'c']}),
            iscollection=False,
            name='Test choice')

        self.plot = Plot(instance=self.instance, geom=self.instance.center)

        set_write_permissions(self.instance, self.user,
                              'Plot', ['udf:Test choice', 'udf:Stewardship'])

    def test_cant_delete_stewardship(self):
        self.instance.config['plot_stewardship_udf_id'] = self.cudf.pk
        self.instance.save()
        resp = udf_delete(make_request(), self.instance, self.cudf.pk)
        self.assertEquals(resp.status_code, 400)

    def test_delete_udf_deletes_perms(self):
        body = {'udf.name': 'cool udf',
                'udf.model': 'Plot',
                'udf.type': 'string'}

        qs = FieldPermission.objects.filter(
            field_name='udf:cool udf',
            model_name='Plot')

        resp = _do_create_udf_request(body, self.instance)
        self.assertTrue(qs.exists())

        resp = udf_delete(make_request(), self.instance, resp['udf'].pk)
        self.assertFalse(qs.exists())

        body = {'udf.name': 'cool udf',
                'udf.model': 'Plot',
                'udf.type': 'choice',
                'udf.choices': ['a', 'b', 'c']}

        resp = _do_create_udf_request(body, self.instance)
        self.assertTrue(qs.exists())
        resp = udf_delete(make_request(), self.instance, resp['udf'].pk)
        self.assertFalse(qs.exists())

    def test_delete_scalar_udf(self):
        self.plot.udfs['Test choice'] = 'a'
        self.plot.save_with_user(self.user)

        self.assertTrue(Audit.objects.filter(instance=self.instance)
                                     .filter(model=self.udf.model_type)
                                     .filter(field=self.udf.canonical_name)
                                     .exists())

        resp = udf_delete(make_request(), self.instance, self.udf.pk)
        self.assertEquals(resp.status_code, 200)

        self.assertFalse(Audit.objects.filter(instance=self.instance)
                                      .filter(model=self.udf.model_type)
                                      .filter(field=self.udf.canonical_name)
                                      .exists())

        self.assertFalse(UserDefinedFieldDefinition.objects
                         .filter(pk=self.udf.pk)
                         .exists())

        updated_plot = Plot.objects.get(pk=self.plot.pk)
        self.assertNotIn(self.udf.name, updated_plot.udfs)

    def test_cant_delete_collection_udf(self):
        stew_record = {'Action': 'Enlarged',
                       'Date': datetime.date.today().strftime('%Y-%m-%d')}
        self.plot.udfs['Stewardship'] = [stew_record]
        self.plot.save_with_user(self.user)

        self.assertTrue(Audit.objects.filter(instance=self.instance)
                                     .filter(model='udf:%s' % self.cudf.pk)
                                     .exists())

        resp = udf_delete(make_request(), self.instance, self.cudf.pk)
        self.assertEquals(resp.status_code, 400)

        self.assertTrue(Audit.objects.filter(instance=self.instance)
                        .filter(model='udf:%s' % self.cudf.pk)
                        .exists())

        self.assertTrue(UserDefinedFieldDefinition.objects
                        .filter(pk=self.cudf.pk)
                        .exists())

        updated_plot = Plot.objects.get(pk=self.plot.pk)
        self.assertIn(self.cudf.name, updated_plot.udfs)
