# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import csv
import json

from django.contrib.gis.geos import Point

from treemap.udf import UserDefinedFieldDefinition, DATETIME_FORMAT
from treemap.tests.views import LocalMediaTestCase, media_dir
from treemap.tests import (make_instance, make_commander_user, make_request,
                           set_write_permissions, make_commander_role)
from treemap.tests.base import OTMTestCase
from treemap.models import Species, Plot, Tree, User, InstanceUser
from treemap.audit import Audit, add_default_permissions

from exporter.models import ExportJob
from exporter import tasks
from exporter.views import begin_export, check_export
from exporter.user import users_json, users_csv

from django.utils.timezone import now
from django.core.exceptions import ValidationError
import datetime


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

        self.assertTrue(len(rows) > 1)
        for (header, value) in headers_and_values.iteritems():
            self.assertEqual(value,
                             rows[row_index][rows[0].index(header)])

    def assertTaskProducesCSV(self, user, model, assert_fields_and_values):
        self._assertTaskProducesCSVBase(user, model, assert_fields_and_values)

        # run the test again without a user
        # catches original version of:
        # https://github.com/OpenTreeMap/OTM2/issues/1384
        # "initial_qs referenced before assignment"
        add_default_permissions(self.instance,
                                [self.instance.default_role])
        self._assertTaskProducesCSVBase(None, model, assert_fields_and_values)

    def _assertTaskProducesCSVBase(self, user, model,
                                   assert_fields_and_values):
        job = ExportJob(instance=self.instance, user=user)
        job.save()
        tasks.csv_export(job.pk, model, '', '')

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

    @media_dir
    def test_species_task_unit(self):
        self.assertTaskProducesCSV(
            self.user, 'species', {'common name': 'foo'})

    @media_dir
    def test_psuedo_async_species_export(self):
        self.assertPsuedoAsyncTaskWorks('species', self.user, 'common name',
                                        'foo', '.*species_export(_\d+)?\.csv')


class UserExportsTestCase(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.commander = make_commander_user(self.instance, "comm")

        # Note unicode '⅀' is on purpose
        self.user1 = User(username='estraven', password='estraven',
                          email='estraven@example.com',
                          organization='org111',
                          first_name='therem', last_name='⅀straven')

        self.user1.save_with_user(self.commander)

        self.user2 = User(username='genly', password='genly',
                          email='genly@example.com',
                          first_name='genly', last_name='ai',
                          allow_email_contact=True)
        self.user2.save_with_user(self.commander)

        self.user3 = User(username='argaven_xv', password='argaven_xv',
                          email='argaven_xv@example.com')
        self.user3.save_with_user(self.commander)

        role = make_commander_role(self.instance)
        iuser1 = InstanceUser(instance=self.instance, user=self.user1,
                              role=role)
        iuser1.save_with_user(self.user1)
        iuser2 = InstanceUser(instance=self.instance, user=self.user2,
                              role=role)
        iuser2.save_with_user(self.user2)

        pt = Point(0, 0)

        self.plot = Plot(geom=pt, readonly=False, instance=self.instance,
                         width=4)
        self.plot.save_with_user(self.user1)

        self.tree = Tree(instance=self.instance, plot=self.plot, diameter=3)
        self.tree.save_with_user(self.user2)


class UserExportsTest(UserExportsTestCase):

    def test_export_users_csv(self):
        resp = users_csv(make_request(), self.instance)
        reader = csv.reader(resp)

        # Skip BOM and entry line
        reader.next()
        reader.next()

        header = reader.next()

        data = [dict(zip(header, [x.decode('utf8') for x in row]))
                for row in reader]

        commander, user1data, user2data = data

        self.assertEquals(commander['username'], self.commander.username)

        self.assertEquals(user1data['username'], self.user1.username)
        self.assertEquals(user1data['email'], '')
        self.assertEquals(user1data['email_hash'], self.user1.email_hash)
        self.assertEquals(user1data['first_name'], self.user1.first_name)
        self.assertEquals(user1data['last_name'], self.user1.last_name)
        self.assertEquals(user1data['organization'], self.user1.organization)
        self.assertEquals(user1data['allow_email_contact'], 'False')
        self.assertEquals(user1data['role'], 'commander')
        self.assertEquals(user1data['created'], str(self.user1.created))

        self.assertEquals(user1data['last_edit_model'], 'Plot')
        self.assertEquals(user1data['last_edit_model_id'], str(self.plot.pk))
        self.assertEquals(user1data['last_edit_instance_id'],
                          str(self.instance.pk))

        self.assertEquals(user1data['last_edit_user_id'], str(self.user1.pk))

        self.assertEquals(user2data['email'], 'genly@example.com')
        self.assertEquals(user2data['email_hash'], self.user2.email_hash)
        self.assertEquals(user2data['last_edit_model'], 'Tree')
        self.assertEquals(user2data['last_edit_model_id'], str(self.tree.pk))
        self.assertEquals(user2data['last_edit_instance_id'],
                          str(self.instance.pk))

        self.assertEquals(user2data['last_edit_user_id'], str(self.user2.pk))

    def test_export_users_json(self):
        resp = users_json(make_request(), self.instance)

        data = json.loads(resp.content)

        commander, user1data, user2data = data

        self.assertEquals(commander['username'], self.commander.username)

        self.assertEquals(user1data['username'], self.user1.username)
        self.assertEquals(user1data.get('email'), None)
        self.assertEquals(user1data['email_hash'], self.user1.email_hash)
        self.assertEquals(user1data['first_name'], self.user1.first_name)
        self.assertEquals(user1data['last_name'], self.user1.last_name)
        self.assertEquals(user1data['organization'], self.user1.organization)
        self.assertEquals(user1data['allow_email_contact'], 'False')
        self.assertEquals(user1data['role'], 'commander')
        self.assertEquals(user1data['created'], str(self.user1.created))

        self.assertEquals(user1data['last_edit_model'], 'Plot')
        self.assertEquals(user1data['last_edit_model_id'], str(self.plot.pk))
        self.assertEquals(user1data['last_edit_instance_id'],
                          str(self.instance.pk))

        self.assertEquals(user1data['last_edit_user_id'], str(self.user1.pk))

        self.assertEquals(user2data['email'], 'genly@example.com')
        self.assertEquals(user2data['email_hash'], self.user2.email_hash)
        self.assertEquals(user2data['last_edit_model'], 'Tree')
        self.assertEquals(user2data['last_edit_model_id'], str(self.tree.pk))
        self.assertEquals(user2data['last_edit_instance_id'],
                          str(self.instance.pk))

        self.assertEquals(user2data['last_edit_user_id'], str(self.user2.pk))

    def test_min_edit_date(self):
        last_week = now() - datetime.timedelta(days=7)
        two_days_ago = now() - datetime.timedelta(days=2)
        yesterday = now() - datetime.timedelta(days=1)
        tda_ts = two_days_ago.strftime(DATETIME_FORMAT)

        Audit.objects.filter(user=self.user1)\
            .update(created=last_week, updated=last_week)

        Audit.objects.filter(user=self.commander)\
            .update(created=last_week, updated=last_week)

        Audit.objects.filter(user=self.user2)\
            .update(created=yesterday, updated=yesterday)

        resp = users_json(make_request({'minEditDate': tda_ts}), self.instance)

        data = json.loads(resp.content)

        self.assertEquals(len(data), 1)

        self.assertEquals(data[0]['username'], self.user2.username)

    def test_min_join_date(self):
        last_week = now() - datetime.timedelta(days=7)
        two_days_ago = now() - datetime.timedelta(days=2)
        yesterday = now() - datetime.timedelta(days=1)
        tda_ts = two_days_ago.strftime(DATETIME_FORMAT)

        Audit.objects.filter(model='InstanceUser')\
            .filter(model_id=self.user1.get_instance_user(self.instance).pk)\
            .update(created=last_week)

        Audit.objects.filter(model='InstanceUser')\
            .filter(model_id=
                    self.commander.get_instance_user(self.instance).pk)\
            .update(created=last_week)

        Audit.objects.filter(model='InstanceUser')\
            .filter(model_id=self.user2.get_instance_user(self.instance).pk)\
            .update(created=yesterday)

        resp = users_json(make_request({'minJoinDate': tda_ts}), self.instance)

        data = json.loads(resp.content)

        self.assertEquals(len(data), 1)

        self.assertEquals(data[0]['username'], self.user2.username)

    def test_min_join_date_validation(self):
        with self.assertRaises(ValidationError):
            users_json(make_request({"minJoinDate": "fsdafsa"}), self.instance)

    def test_min_edit_date_validation(self):
        with self.assertRaises(ValidationError):
            users_json(make_request({"minEditDate": "fsdafsa"}), self.instance)
