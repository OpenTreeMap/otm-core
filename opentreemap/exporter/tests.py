# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import csv
import json

from django.contrib.gis.geos import Point
from django.utils.unittest.case import skip

from treemap.udf import UserDefinedFieldDefinition
from treemap.tests.views import LocalMediaTestCase, media_dir
from treemap.tests import (make_instance, make_commander_user, make_request,
                           set_write_permissions)
from treemap.models import Species, Plot, Tree, User

from exporter.models import ExportJob
from exporter import tasks
from exporter.views import begin_export, check_export


class AsyncCSVTestCase(LocalMediaTestCase):

    def setUp(self):
        super(AsyncCSVTestCase, self).setUp()
        self.instance = make_instance()
        self.user = make_commander_user(self.instance)

        self.unprivileged_user = User.objects.create_user(username='foo',
                                                          email='foo@bar.com',
                                                          password='bar')

    def assertCSVRowValue(self, csv_file, row_index, headers_and_values):
        csvreader = csv.reader(csv_file, delimiter=b",")
        rows = list(csvreader)

        for (header, value) in headers_and_values.iteritems():
            self.assertEqual(value,
                             rows[row_index][rows[0].index(header)])

    def assertTaskProducesCSV(self, user, model, assert_fields_and_values):
        job = ExportJob(instance=self.instance, user=user)
        job.save()
        tasks.csv_export(job.pk, model, '')

        # Refresh model with outfile
        job = ExportJob.objects.get(pk=job.pk)
        self.assertCSVRowValue(job.outfile, 1, assert_fields_and_values)

    def assertPsuedoAsyncTaskWorks(self, model,
                                   user,
                                   assertion_field, assertion_value,
                                   assertion_filename):

        request = make_request(user=user)
        ctx = begin_export(request, self.instance, model)
        self.assertIn('job_id', ctx.keys())
        self.assertEqual(ctx['start_status'], 'OK')

        job_id = ctx['job_id']
        job = ExportJob.objects.get(pk=job_id)
        self.assertCSVRowValue(job.outfile, 1,
                               {assertion_field: assertion_value})

        ctx = check_export(request, self.instance, job_id)
        self.assertIn('.csv', ctx['url'])
        self.assertEqual(ctx['status'], 'COMPLETE')

        self.assertRegexpMatches(job.outfile.name, assertion_filename)


class ExportTreeTaskTest(AsyncCSVTestCase):

    def setUp(self):
        super(ExportTreeTaskTest, self).setUp()

        set_write_permissions(self.instance, self.user,
                              'Plot', ['udf:Test choice'])
        set_write_permissions(self.instance, self.user,
                              'Tree', ['udf:Test int'])

        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'choice',
                                 'choices': ['a', 'b', 'c']}),
            iscollection=False,
            name='Test choice')

        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Tree',
            datatype=json.dumps({'type': 'int'}),
            iscollection=False,
            name='Test int')

        p = Plot(geom=Point(0, 0), instance=self.instance,
                 address_street="123 Main Street")
        p.udfs['Test choice'] = 'a'

        p.save_with_user(self.user)

        t = Tree(plot=p, instance=self.instance, diameter=2)
        t.udfs['Test int'] = 4

        t.save_with_user(self.user)

    @media_dir
    def test_tree_task_unit(self):
        self.assertTaskProducesCSV(
            self.user, 'tree', {'diameter': '2.0',
                                'udf:Test int': '4',
                                'plot__udf:Test choice': 'a'})

    @media_dir
    def test_export_view_permission_failure(self):
        request = make_request(user=self.unprivileged_user)
        begin_ctx = begin_export(request, self.instance, 'tree')
        check_ctx = check_export(request, self.instance, begin_ctx['job_id'])
        self.assertEqual(check_ctx['status'], 'MODEL_PERMISSION_ERROR')
        self.assertEqual(check_ctx['message'],
                         'User has no permissions on this model')

    @media_dir
    def test_psuedo_async_tree_export(self):
        self.assertPsuedoAsyncTaskWorks('tree', self.user, 'diameter', '2.0',
                                        '.*tree_export(_\d+)?\.csv')


class ExportSpeciesTaskTest(AsyncCSVTestCase):

    def setUp(self):
        super(ExportSpeciesTaskTest, self).setUp()

        species = Species(common_name='foo', instance=self.instance)
        species.save_with_user(self.user)

    @skip('Need to figure how to remove transactions here')
    @media_dir
    def test_species_task_unit(self):
        self.assertTaskProducesCSV(
            self.user, 'species', {'common_name': 'foo'})

    @media_dir
    def test_psuedo_async_species_export(self):
        self.assertPsuedoAsyncTaskWorks('species', self.user, 'common name',
                                        'foo', '.*species_export(_\d+)?\.csv')
