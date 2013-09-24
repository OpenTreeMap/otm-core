from treemap.tests import make_instance, make_commander_user, make_request
from treemap.models import Species, InstanceSpecies, Plot, Tree, User

from django.contrib.gis.geos import Point

from django.test import TestCase

from exporter.models import ExportJob
from exporter import tasks
from exporter.views import begin_export, check_export

import csv


class AsyncCSVTestCase(TestCase):

    def setUp(self):
        self.instance = make_instance()
        self.user = make_commander_user(self.instance)

        self.unprivileged_user = User.objects.create_user(username='foo',
                                                          email='foo@bar.com',
                                                          password='bar')

    def assertCSVRowValue(self, csv_file, row_index, header, value):
        csvreader = csv.reader(csv_file, delimiter=",")
        rows = list(csvreader)
        self.assertEqual(value,
                         rows[row_index][rows[0].index(header)])

    def assertTaskProducesCSV(self, model, assert_field,
                              assert_value, user=None):
        job = ExportJob(instance=self.instance, user=user)
        tasks.csv_export(job, model, '')
        self.assertCSVRowValue(job.outfile, 1, assert_field, assert_value)

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
        self.assertCSVRowValue(job.outfile, 1, assertion_field,
                               assertion_value)

        ctx = check_export(request, self.instance, job_id)
        self.assertIn('.csv', ctx['url'])
        self.assertEqual(ctx['status'], 'COMPLETE')

        self.assertRegexpMatches(job.outfile.name, assertion_filename)


class ExportTreeTaskTest(AsyncCSVTestCase):

    def setUp(self):
        super(ExportTreeTaskTest, self).setUp()

        p = Plot(geom=Point(0, 0), instance=self.instance,
                 address_street="123 Main Street")
        p.save_with_user(self.user)

        t = Tree(plot=p, instance=self.instance, diameter=2)
        t.save_with_user(self.user)

    def test_tree_task_unit(self):
        self.assertTaskProducesCSV('tree', 'diameter', '2.0',
                                   user=self.user)

    def test_export_view_permission_failure(self):
        request = make_request(user=self.unprivileged_user)
        begin_ctx = begin_export(request, self.instance, 'tree')
        check_ctx = check_export(request, self.instance, begin_ctx['job_id'])
        self.assertEqual(check_ctx['status'], 'MODEL_PERMISSION_ERROR')
        self.assertEqual(check_ctx['message'],
                         'User has no permissions on this model')

    def test_psuedo_async_tree_export(self):
        self.assertPsuedoAsyncTaskWorks('tree', self.user, 'diameter', '2.0',
                                        '.*tree_export(_\d+)?\.csv')


class ExportSpeciesTaskTest(AsyncCSVTestCase):

    def setUp(self):
        super(ExportSpeciesTaskTest, self).setUp()

        InstanceSpecies(instance=self.instance,
                        species=Species.objects.create(common_name='foo'),
                        common_name='foo').save_with_user(self.user)

    def test_species_task_unit(self):
        self.assertTaskProducesCSV('species', 'common_name', 'foo')

    def test_psuedo_async_species_export(self):
        self.assertPsuedoAsyncTaskWorks('species', None, 'common_name', 'foo',
                                        '.*species_export(_\d+)?\.csv')
