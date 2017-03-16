# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.gis.geos import Point
from django.utils import timezone

from treemap.audit import UserTrackingException
from treemap.models import Plot
from treemap.tests.base import OTMTestCase
from treemap.tests import make_instance, make_commander_user

from works_management.models import Team, Task, WorkOrder


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
        w.reference_number = instance.get_next_work_order_sequence()
        w.save_with_user(user)
    return w


def make_task(instance, user, map_feature, team=None, save=True):
    t = Task()
    t.instance = instance
    t.map_feature = map_feature
    t.team = team
    t.created_by = user
    t.requested_on = timezone.now()
    t.scheduled_on = timezone.now()
    t.closed_on = timezone.now()
    if save:
        t.reference_number = instance.get_next_task_sequence()
        t.save_with_user(user)
    return t


def make_plot(instance, user):
    p = Point(0, 0)
    plot = Plot(geom=p, instance=instance)
    plot.save_with_user(user)
    return plot


class WorksManagementTests(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.user = make_commander_user(self.instance)
        self.team = make_team(self.instance)
        self.plot = make_plot(self.instance, self.user)

    def test_work_order(self):
        w = make_work_order(self.instance, self.user)

        t = make_task(self.instance, self.user, self.plot)
        t.work_order = w
        t.save_with_user(self.user)
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
        t = make_task(self.instance, self.user, self.plot)
        with self.assertRaises(UserTrackingException):
            t.save()

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
        t1 = make_task(self.instance, self.user, self.plot)
        t2 = make_task(self.instance, self.user, self.plot)
        self.assertEqual(1, t1.reference_number)
        self.assertEqual(2, t2.reference_number)

        # Sequence numbers should be unique by instance.
        other_instance = make_instance()
        t1 = make_task(other_instance, self.user, self.plot)
        t2 = make_task(other_instance, self.user, self.plot)
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
        tasks = [make_task(self.instance, self.user, self.plot, save=False)
                 for _ in range(10)]

        value = self.instance.get_next_task_sequence(len(tasks))
        for i in range(len(tasks)):
            tasks[i].reference_number = value + i

        Task.objects.bulk_create(tasks)

        self.instance.refresh_from_db()
        self.assertEqual(11, self.instance.task_sequence_number)
