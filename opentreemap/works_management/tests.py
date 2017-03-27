# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from django.core.exceptions import ValidationError
from django.contrib.gis.geos import Point
from django.utils import timezone
from django.test.utils import override_settings

from treemap.audit import UserTrackingException, Audit, bulk_create_with_user
from treemap.search import Filter
from treemap.models import Plot, Tree, Species
from treemap.tests.base import OTMTestCase
from treemap.tests import make_instance, make_commander_user, make_request

from works_management.models import Team, Task, WorkOrder
from works_management.views import create_tasks


def make_team(instance, name='Test Team'):
    t = Team()
    t.instance = instance
    t.name = name
    t.save()
    return t


def make_work_order(instance, user, name='Test Work Order', save=True):
    w = WorkOrder()
    w.name = name
    w.instance = instance
    w.created_by = user
    if save:
        w.save_with_user(user)
    return w


def make_task(instance, user, map_feature, work_order, team=None, save=True):
    t = Task()
    t.instance = instance
    t.map_feature = map_feature
    t.team = team
    t.work_order = work_order
    t.created_by = user
    t.requested_on = timezone.now()
    t.scheduled_on = timezone.now()
    t.closed_on = timezone.now()
    if save:
        t.save_with_user(user)
    return t


def make_plot(instance, user, n=0):
    p = Point(n, n)
    plot = Plot(geom=p, instance=instance)
    plot.save_with_user(user)
    return plot


def make_tree(instance, user, plot, species=None, diameter=None):
    tree = Tree(instance=instance, plot=plot, species=species,
                diameter=diameter)
    tree.save_with_user(user)
    return tree


@override_settings(FEATURE_BACKEND_FUNCTION=None)
class WorksManagementModelTests(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.instance.initialize_udfs([Task.__name__], [Task], dot=True)
        self.user = make_commander_user(self.instance)
        self.team = make_team(self.instance)
        self.plot = make_plot(self.instance, self.user)

    def test_work_order(self):
        w = make_work_order(self.instance, self.user)

        t = make_task(self.instance, self.user, self.plot, w)
        self.assertEqual(1, w.task_set.count())

        # Test that WorkOrder updated_at field updates when Tasks update
        old_updated_at = w.updated_at
        t.status = Task.COMPLETED
        t.save_with_user(self.user)

        w = WorkOrder.objects.get(id=w.id)
        self.assertTrue(w.updated_at > old_updated_at)

    def test_cannot_call_save_on_work_order(self):
        # WorkOrder is Auditible and should only allow calling save_with_user.
        w = make_work_order(self.instance, self.user)
        with self.assertRaises(UserTrackingException):
            w.save()

    def test_cannot_call_save_on_task(self):
        # Task is Auditible and should only allow calling save_with_user.
        w = make_work_order(self.instance, self.user)
        t = make_task(self.instance, self.user, self.plot, w, save=False)
        with self.assertRaises(UserTrackingException):
            t.save()

    def test_task_udf(self):
        t = make_task(self.instance, self.user,
                      make_plot(self.instance, self.user),
                      make_work_order(self.instance, self.user))
        t.udfs['Action'] = 'Plant Tree'
        t.save_with_user(self.user)

        count = Task.objects.filter(**{'udf:Action': 'Plant Tree'}).count()
        self.assertEqual(1, count)

    def test_instance_sequence_helpers(self):
        self.assertEqual(1, self.instance.get_next_task_sequence(9))
        self.assertEqual(10, self.instance.get_next_task_sequence())

        self.assertEqual(1, self.instance.get_next_work_order_sequence(9))
        self.assertEqual(10, self.instance.get_next_work_order_sequence())

        # Try to commit bad data.
        self.instance.task_sequence_number = 0
        self.instance.work_order_sequence_number = 0
        self.instance.save()
        self.instance.refresh_from_db()

        self.assertEqual(11, self.instance.task_sequence_number)
        self.assertEqual(11, self.instance.work_order_sequence_number)

    def test_work_order_sequence(self):
        w1 = make_work_order(self.instance, self.user)
        w2 = make_work_order(self.instance, self.user)
        self.assertEqual(1, w1.reference_number)
        self.assertEqual(2, w2.reference_number)

        # Sequence numbers should be unique by instance.
        other_instance = make_instance()
        w1 = make_work_order(other_instance, self.user)
        w2 = make_work_order(other_instance, self.user)
        self.assertEqual(1, w1.reference_number)
        self.assertEqual(2, w2.reference_number)

    def test_task_sequence(self):
        w = make_work_order(self.instance, self.user)
        t1 = make_task(self.instance, self.user, self.plot, w)
        t2 = make_task(self.instance, self.user, self.plot, w)
        self.assertEqual(1, t1.reference_number)
        self.assertEqual(2, t2.reference_number)

        # Sequence numbers should be unique by instance.
        other_instance = make_instance()
        u = make_commander_user(other_instance, 'other_guy')
        w = make_work_order(other_instance, u)
        p = make_plot(other_instance, u)
        t1 = make_task(other_instance, u, p, w)
        t2 = make_task(other_instance, u, p, w)
        self.assertEqual(1, t1.reference_number)
        self.assertEqual(2, t2.reference_number)

    def test_work_order_sequence_bulk_create(self):
        orders = [make_work_order(self.instance, self.user, save=False)
                  for _ in range(10)]

        value = self.instance.get_next_work_order_sequence(len(orders))
        for i in range(len(orders)):
            orders[i].reference_number = value + i

        WorkOrder.objects.bulk_create(orders)

        self.instance.refresh_from_db()
        self.assertEqual(11, self.instance.work_order_sequence_number)

    def test_task_sequence_bulk_create(self):
        w = make_work_order(self.instance, self.user)
        tasks = [make_task(self.instance, self.user, self.plot, w, save=False)
                 for _ in range(10)]

        value = self.instance.get_next_task_sequence(len(tasks))
        for i in range(len(tasks)):
            tasks[i].reference_number = value + i

        Task.objects.bulk_create(tasks)

        self.instance.refresh_from_db()
        self.assertEqual(11, self.instance.task_sequence_number)

    def test_task_sequence_audited_bulk_create(self):
        w = make_work_order(self.instance, self.user)
        tasks = [make_task(self.instance, self.user, self.plot, w, save=False)
                 for _ in range(10)]

        value = self.instance.get_next_task_sequence(len(tasks))
        for i in range(len(tasks)):
            tasks[i].reference_number = value + i

        bulk_create_with_user(tasks, self.user)

        self.instance.refresh_from_db()
        self.assertEqual(11, self.instance.task_sequence_number)


@override_settings(FEATURE_BACKEND_FUNCTION=None)
class WorksManagementViewTests(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.instance.initialize_udfs([Task.__name__], [Task], dot=True)
        self.user = make_commander_user(self.instance)
        self.team = make_team(self.instance)

        plot = make_plot(self.instance, self.user, 0)
        self.species = Species(common_name='foo', instance=self.instance)
        self.species.save_with_user(self.user)
        make_tree(self.instance, self.user, plot, species=self.species,
                  diameter=1)

    def test_create_task_and_work_order(self):
        work_order_name = 'Go Dog Go'
        request_dict = {
            'form_fields': {
                'task.requested_on': '2016-01-01',
                'workorder.name': work_order_name
            },
            'q': json.dumps({
                'species.id': {'IS': self.species.pk}
            })
        }

        self.assertEqual(WorkOrder.objects.count(), 0)
        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(Plot.objects.count(), 1)

        request = make_request(method='POST', body=json.dumps(request_dict),
                               instance=self.instance, user=self.user)
        create_tasks(request, self.instance)

        self.assertEqual(WorkOrder.objects.count(), 1)
        self.assertEqual(Task.objects.count(), 1)

    def test_bad_field_value(self):
        work_order_name = 'Go Dog Go'
        request_dict = {
            'form_fields': {
                'task.requested_on': 'not a date',
                'workorder.name': work_order_name
            },
            'q': json.dumps({
                'species.id': {'IS': self.species.pk}
            })
        }

        self.assertEqual(WorkOrder.objects.count(), 0)
        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(Plot.objects.count(), 1)

        request = make_request(method='POST', body=json.dumps(request_dict),
                               instance=self.instance, user=self.user)
        with self.assertRaises(ValidationError) as validation_error:
            create_tasks(request, self.instance)

        # Rollback occurred
        self.assertEqual(WorkOrder.objects.count(), 0)
        self.assertEqual(Task.objects.count(), 0)

        # ValidationError.message_dict as expected by
        # treemap.return_400_if_validation_errors
        validation_exception = validation_error.exception
        self.assertTrue(hasattr(validation_exception, 'message_dict'),
                        'ValidationError must have a message_dict.')
        message_dict = validation_exception.message_dict
        self.assertIn('task.requested_on', message_dict)

    # TODO: Like test_bad_field_value, but with multiple bad values,
    # and assert that the error dict contains complaints for each of them.
    def test_bad_field_values(self):
        pass

    # TODO: Make a request that neither specifies a workorder.name
    # nor a task.work_order, and assert that the error dict contains
    # a complaint for task.work_order.
    def test_no_work_order(self):
        pass

    def test_set_protected_udf(self):
        work_order_name = 'Go Dog Go'
        action = 'Remove Tree'
        request_dict = {
            'form_fields': {
                'task.requested_on': '2016-01-01',
                'workorder.name': work_order_name,
                'task.udf:Action': action
            },
            'q': json.dumps({
                'species.id': {'IS': self.species.pk}
            })
        }
        request = make_request(method='POST', body=json.dumps(request_dict),
                               instance=self.instance, user=self.user)
        create_tasks(request, self.instance)

        task = Task.objects.get(instance=self.instance)
        self.assertEqual(task.udfs['Action'], action)

    def test_set_protected_udf_bad_value(self):
        work_order_name = 'Go Dog Go'
        action = 'Invalid choice'
        request_dict = {
            'form_fields': {
                'task.requested_on': '2016-01-01',
                'workorder.name': work_order_name,
                'task.udf:Action': action
            },
            'q': json.dumps({
                'species.id': {'IS': self.species.pk}
            })
        }
        request = make_request(method='POST', body=json.dumps(request_dict),
                               instance=self.instance, user=self.user)
        with self.assertRaises(ValidationError) as validation_error:
            create_tasks(request, self.instance)

        self.assertEqual(Task.objects.count(), 0)

        validation_exception = validation_error.exception
        self.assertTrue(hasattr(validation_exception, 'message_dict'),
                        'ValidationError must have a message_dict.')
        message_dict = validation_exception.message_dict
        self.assertIn('task.udf:Action', message_dict)

    # TODO: try setting values on more than one udf, and assert that
    # they all get set. Mix protected with regular udfs.
    def test_set_multiple_udfs(self):
        pass

    # TODO: try setting values on more than one udf, where
    # the values are invalid for those udfs.
    # Assert that the request throws a ValidationError,
    # and that the error dict contains complaints for each of them.
    def test_set_multiple_udfs_bad_values(self):
        pass

    def test_empty_search_results(self):
        species = Species(common_name='bar', instance=self.instance)
        species.save_with_user(self.user)

        work_order_name = 'Go Dog Go'
        action = 'Remove Tree'
        request_dict = {
            'form_fields': {
                'task.requested_on': 'not a date',
                'workorder.name': work_order_name,
                'task.udf:Action': action
            },
            'q': json.dumps({
                'species.id': {'IS': species.pk}
            })
        }

        request = make_request(method='POST', body=json.dumps(request_dict),
                               instance=self.instance, user=self.user)
        with self.assertRaises(ValidationError) as validation_error:
            create_tasks(request, self.instance)

        validation_exception = validation_error.exception
        self.assertTrue(hasattr(validation_exception, 'message_dict'),
                        'ValidationError must have a message_dict.')
        message_dict = validation_exception.message_dict
        self.assertIn('task.requested_on', message_dict)
        # Empty search should register as a global error
        self.assertIn('globalErrors', message_dict)

    def test_invalid_search(self):
        work_order_name = 'Go Dog Go'
        request_dict = {
            'form_fields': {
                'task.requested_on': '2016-01-01',
                'workorder.name': work_order_name
            },
            'q': json.dumps({
                'species.id': {'IS': 'not a species pk'}
            })
        }

        request = make_request(method='POST', body=json.dumps(request_dict),
                               instance=self.instance, user=self.user)
        with self.assertRaises(ValidationError) as validation_error:
            create_tasks(request, self.instance)

        validation_exception = validation_error.exception
        self.assertTrue(hasattr(validation_exception, 'message_dict'),
                        'ValidationError must have a message_dict.')
        message_dict = validation_exception.message_dict
        # Empty search should register as a global error
        self.assertIn('globalErrors', message_dict)

    def test_audit_trail(self):
        plots = [make_plot(self.instance, self.user, i) for i in range(1, 4)]
        for p in plots:
            make_tree(self.instance, self.user, p, species=self.species,
                      diameter=1)
        work_order_name = 'Go Dog Go'
        request_dict = {
            'form_fields': {
                'task.team': self.team.pk,
                'task.requested_on': '2016-01-01',
                'workorder.name': work_order_name
            },
            'q': json.dumps({
                'species.id': {'IS': self.species.pk}
            })
        }
        filter = Filter(request_dict['q'], json.dumps(['Plot']),
                        self.instance)
        plots = filter.get_objects(Plot)
        plot_ids = [p.pk for p in plots]

        request = make_request(method='POST', body=json.dumps(request_dict),
                               instance=self.instance, user=self.user)
        create_tasks(request, self.instance)

        self.assertEqual(WorkOrder.objects.count(), 1)
        self.assertEqual(Task.objects.count(), len(plots))

        audit_qs = Audit.objects.filter(
            instance=self.instance, user=self.user,
            action=Audit.Type.Insert, model='Task', field='map_feature',
            current_value__in=plot_ids)

        self.assertEqual(audit_qs.count(), len(plot_ids))
