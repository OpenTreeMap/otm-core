# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from datetime import datetime, timedelta

from django.contrib.gis.geos import Point
from django.contrib.sites.models import Site

from treemap.models import Plot
from treemap.tests.base import OTMTestCase
from treemap.tests import make_instance, make_commander_user, make_request

from otm_comments.models import EnhancedThreadedComment
from otm_comments.views import comments_review


def make_comment(model, user, text='testing 1 2 3', **kwargs):
    site = Site.objects.all()[0]
    return EnhancedThreadedComment.objects.create(
        content_object=model, user=user, comment=text, site=site, **kwargs)


class EnhancedCommentTest(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.user = make_commander_user(self.instance)
        self.plot = Plot(geom=Point(0, 0), instance=self.instance)
        self.plot.save_with_user(self.user)

    def test_creating_comment_on_plots_sets_instance(self):
        ec = make_comment(self.plot, self.user)

        self.assertEqual(self.instance, ec.instance)

        ec.save()

        retrieved_ec = EnhancedThreadedComment.objects.get(pk=ec.pk)

        self.assertEqual(self.instance, retrieved_ec.instance)


class CommentReviewTest(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.user = make_commander_user(self.instance)

        self.plot = Plot(geom=Point(0, 0), instance=self.instance)
        self.plot.save_with_user(self.user)

    def _get_comments(self, **get_params):
        context = comments_review(make_request(get_params), self.instance)

        return context['comments']

    def test_comments_pagination(self):
        make_comment(self.plot, self.user)
        make_comment(self.plot, self.user)
        make_comment(self.plot, self.user)
        make_comment(self.plot, self.user)
        make_comment(self.plot, self.user)

        comments_p1 = self._get_comments(size='2')

        self.assertEqual(False, comments_p1.has_previous())
        self.assertEqual(1, comments_p1.number)
        self.assertEqual(3, comments_p1.paginator.num_pages)
        self.assertEqual(2, len(comments_p1))
        self.assertEqual(2, comments_p1.next_page_number())

    def test_archived_filter(self):
        ecomment1 = make_comment(self.plot, self.user, is_archived=True,
                                 is_removed=False)
        ecomment2 = make_comment(self.plot, self.user, is_archived=False,
                                 is_removed=True)

        comments = self._get_comments()

        # Without any parameters, you get all comments
        self.assertEqual(2, len(comments))

        comments = self._get_comments(archived='True')

        self.assertEqual(1, len(comments))
        self.assertEqual(ecomment1, comments[0])

        comments = self._get_comments(archived='False')

        self.assertEqual(1, len(comments))
        self.assertEqual(ecomment2, comments[0])

    def test_hidden_filter(self):
        ecomment1 = make_comment(self.plot, self.user, is_archived=True,
                                 is_removed=False)
        ecomment2 = make_comment(self.plot, self.user, is_archived=False,
                                 is_removed=True)

        comments = self._get_comments()

        # Without any parameters, you get all comments
        self.assertEqual(2, len(comments))

        comments = self._get_comments(removed='True')

        self.assertEqual(1, len(comments))
        self.assertEqual(ecomment2, comments[0])

        comments = self._get_comments(removed='False')

        self.assertEqual(1, len(comments))
        self.assertEqual(ecomment1, comments[0])

    def test_sorting(self):
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        last_week = today - timedelta(days=7)

        ecomment1 = make_comment(self.plot, self.user, submit_date=today)
        ecomment2 = make_comment(self.plot, self.user, submit_date=last_week)
        ecomment3 = make_comment(self.plot, self.user, submit_date=yesterday)

        comments = self._get_comments()

        # The default sort order is submit_date, with the most recent first
        self.assertEqual(3, len(comments))
        self.assertEqual(ecomment1, comments[0])
        self.assertEqual(ecomment3, comments[1])
        self.assertEqual(ecomment2, comments[2])

        # You can sort on arbitrary fields
        comments = self._get_comments(sort='id')

        self.assertEqual(3, len(comments))
        self.assertEqual(ecomment1, comments[0])
        self.assertEqual(ecomment2, comments[1])
        self.assertEqual(ecomment3, comments[2])

        comments = self._get_comments(sort='-id')

        # Adding a '-' reverses the sort order
        self.assertEqual(3, len(comments))
        self.assertEqual(ecomment3, comments[0])
        self.assertEqual(ecomment2, comments[1])
        self.assertEqual(ecomment1, comments[2])
