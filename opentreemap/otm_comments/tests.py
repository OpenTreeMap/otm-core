# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from time import sleep

from datetime import datetime, timedelta

from django.contrib.gis.geos import Point
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.test.client import RequestFactory

from selenium.webdriver.support.wait import WebDriverWait

from treemap.models import Plot
from treemap.tests.base import OTMTestCase
from treemap.tests import (make_instance, make_commander_user,
                           make_admin_user, make_request)
from treemap.tests.ui import TreemapUITestCase

from otm_comments.models import (EnhancedThreadedComment,
                                 EnhancedThreadedCommentFlag)
from otm_comments.views import (comment_moderation, flag, unflag,
                                archive, unarchive, hide_flags,
                                hide, show)


def make_comment(model, user, text='testing 1 2 3', **kwargs):
    site = Site.objects.all()[0]
    return EnhancedThreadedComment.objects.create(
        content_object=model, user=user, comment=text, site=site, **kwargs)


class CommentTestMixin(object):
    # A mixin class for comment tests, sets up some non-comment related data
    def setUp(self):
        super(CommentTestMixin, self).setUp()
        self.instance = make_instance()
        self.user = make_commander_user(self.instance)
        self.admin = make_admin_user(self.instance)
        self.plot = Plot(geom=Point(0, 0), instance=self.instance)
        self.plot.save_with_user(self.user)


class CommentTestCase(CommentTestMixin, OTMTestCase):
    pass


class EnhancedCommentTest(CommentTestCase):
    def test_creating_comment_on_plots_sets_instance(self):
        ec = make_comment(self.plot, self.user)

        self.assertEqual(self.instance, ec.instance)

        ec.save()

        retrieved_ec = EnhancedThreadedComment.objects.get(pk=ec.pk)

        self.assertEqual(self.instance, retrieved_ec.instance)


class CommentReviewTest(CommentTestCase):
    def _get_comments(self, **get_params):
        context = comment_moderation(make_request(get_params), self.instance)

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

        # Without any parameters, you get only "Active" comments
        self.assertEqual(1, len(comments))

        comments = self._get_comments(archived='True')

        self.assertEqual(1, len(comments))
        self.assertEqual(ecomment1, comments[0])

        comments = self._get_comments(archived='False')

        self.assertEqual(1, len(comments))
        self.assertEqual(ecomment2, comments[0])

    def test_hidden_filter(self):
        make_comment(self.plot, self.user, is_archived=True, is_removed=False)
        ecomment2 = make_comment(self.plot, self.user, is_archived=False,
                                 is_removed=True)
        ecomment3 = make_comment(self.plot, self.user, is_archived=False,
                                 is_removed=False)

        comments = self._get_comments()

        # Without any parameters, you get "Active" comments
        self.assertEqual(2, len(comments))
        self.assertIn(ecomment2, comments)
        self.assertIn(ecomment3, comments)

        comments = self._get_comments(removed='True')

        self.assertEqual(1, len(comments))
        self.assertEqual(ecomment2, comments[0])

        comments = self._get_comments(removed='False')

        self.assertEqual(1, len(comments))
        self.assertEqual(ecomment3, comments[0])

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


class CommentReviewUITest(CommentTestMixin, TreemapUITestCase):
    def setUp(self):
        super(CommentReviewUITest, self).setUp()
        self.removed_comment =\
            make_comment(self.plot, self.user, is_removed=True)
        make_comment(self.plot, self.user)
        make_comment(self.plot, self.user)
        make_comment(self.plot, self.user)
        make_comment(self.plot, self.user)
        make_comment(self.plot, self.user, text="""
                     This is a really long comment

                     It spans a lot of lines, and has a lot of text

                     So it should get cut off in the UI, and only show the
                     first few lines.

                     We have a link on the page to show less/more of the
                     comment text.

                     Lorem ipsum dolor sit amet, consectetur adipiscing elit,
                     sed do eiusmod tempor incididunt ut labore et dolore magna
                     aliqua. Ut enim ad minim veniam, quis nostrud exercitation
                     ullamco laboris nisi ut aliquip ex ea commodo consequat.
                     Duis aute irure dolor in reprehenderit in voluptate velit
                     esse cillum dolore eu fugiat nulla pariatur. Excepteur
                     sint occaecat cupidatat non proident, sunt in culpa qui
                     officia deserunt mollit anim id est laborum
                     """)

        self.login_workflow(user=self.admin)
        self.comments_url = reverse('comment_moderation_full',
                                    args=(self.instance.url_name,))
        self.browse_to_url(self.comments_url)

    def assert_num_rows(self, num, msg=None):
        rows = self.driver.find_elements_by_css_selector(
            '.comment-table tbody tr')

        self.assertEqual(num, len(rows), msg)

    def go_to_page(self, page_num):
        page = str(page_num)
        page_link = self.find('.pagination').find_element_by_link_text(page)
        page_link.click()

        self.wait_until_on_page(page_num)

    def wait_until_on_page(self, page_num):
        # The each link is page # + 1, due to the "previous" link
        page_num = page_num + 1
        self.wait_until_present('.pagination li:nth-child(%s).active'
                                % page_num)

    def test_pagination(self):
        self.assert_num_rows(5, 'There are 5 comments on the first page')

        self.go_to_page(2)

        self.assert_num_rows(1, 'There is 1 comment on the second page')

    def test_filtering(self):
        self.assert_num_rows(
            5, 'There are 5 comments on this page before filtering')

        self.click('.page-header [data-toggle="dropdown"]')

        dropdown = self.driver.find_element_by_css_selector(
            '[data-comments-filter]')
        hidden_link = dropdown.find_element_by_link_text('Hidden')

        self.wait_until_visible(hidden_link)
        hidden_link.click()

        sleep(3)

        self.assert_num_rows(1, 'Only the hidden comment should be shown')

        id_link = self.find('.comment-table tbody') \
            .find_element_by_link_text(str(self.removed_comment.pk))

        url = id_link.get_attribute('href')
        reversed_url = reverse('map_feature_detail',
                               args=(self.instance.url_name, self.plot.pk))

        self.assertTrue(url.endswith(reversed_url),
                        'The comment should link to the detail page')

    def test_less_or_more(self):
        first_comment = self.find('.comment-table tbody tr:first-child')

        height = first_comment.size['height']

        less_or_more_link = \
            first_comment.find_element_by_css_selector('[data-less-more]')
        less_or_more_link.click()

        # After clicking the text should change to "less"
        WebDriverWait(self.driver, 3).until(
            lambda driver: less_or_more_link.text == 'less')

        updated_height = first_comment.size['height']

        # The table row should get larger
        self.assertGreater(updated_height, height)

        # After clicking again the text should change to "more"
        less_or_more_link.click()
        WebDriverWait(self.driver, 3).until(
            lambda driver: less_or_more_link.text == 'more')

        updated_height = first_comment.size['height']

        # The table row should go back to the original height
        self.assertEqual(updated_height, height)

    def test_archiving_single(self):
        self.go_to_page(2)

        self.assert_num_rows(1)

        self.find('.comment-table tbody tr') \
            .find_element_by_link_text('Archive') \
            .click()

        # Archiving the only item on this page should bring us back to page 1
        self.wait_until_on_page(1)

        self.assert_num_rows(5)

        self.assertEqual(1, EnhancedThreadedComment.objects
                         .filter(is_archived=True).count())

    def test_archiving_batch(self):
        checkboxes = self.driver \
            .find_elements_by_css_selector('[data-batch-action-checkbox]')

        for checkbox in checkboxes:
            self.assertFalse(checkbox.is_selected())

        batch_checkbox = self.find('[data-comment-toggle-all]')
        batch_checkbox.click()

        for checkbox in checkboxes:
            self.assertTrue(
                checkbox.is_selected(),
                "The select all checkbox should check every row's box")

        # Open the batch action dropdown
        self.click('[data-comment-batch-dropdown]')

        self.find('[data-comment-batch]') \
            .find_element_by_link_text('Archive') \
            .click()

        sleep(3)

        self.assertEqual(5, EnhancedThreadedComment.objects
                         .filter(is_archived=True).count())


def _comment_ids_to_params(*args):
    return {'comment-ids': ','.join(str(arg) for arg in args)}


def make_post_request(user, params={}):
    # TODO: We should really be using the make_request helper in treemap.tests,
    # but it *always* does .get(), even when method='POST'
    req = RequestFactory().post("hello/world", params)
    setattr(req, 'user', user)
    return req


class CommentModerationTestCase(CommentTestCase):
    def setUp(self):
        super(CommentModerationTestCase, self).setUp()
        self.comment = make_comment(self.plot, self.user)
        self.comment2 = make_comment(self.plot, self.user)


class CommentFlagTest(CommentModerationTestCase):
    def test_flagging(self):
        self.assertFalse(self.comment.is_flagged)
        self.assertFalse(self.comment.is_flagged_by_user(self.user))
        self.assertFalse(self.comment.is_flagged_by_user(self.admin))

        req = make_post_request(user=self.user)
        flag(req, self.instance, self.comment.id)

        updated_comment = EnhancedThreadedComment.objects.get(
            pk=self.comment.id)
        self.assertEqual(1, EnhancedThreadedCommentFlag.objects
                         .all().count(),
                         "There should be 1 comment flag row created")
        self.assertTrue(updated_comment.is_flagged)
        self.assertTrue(updated_comment.is_flagged_by_user(self.user))
        self.assertFalse(updated_comment.is_flagged_by_user(self.admin))

    def test_can_unflag(self):
        req = make_post_request(user=self.user)
        flag(req, self.instance, self.comment.id)
        updated_comment = EnhancedThreadedComment.objects.get(
            pk=self.comment.id)
        self.assertTrue(updated_comment.is_flagged)

        req = make_post_request(user=self.user)
        unflag(req, self.instance, self.comment.id)
        updated_comment = EnhancedThreadedComment.objects.get(
            pk=self.comment.id)
        self.assertFalse(updated_comment.is_flagged)

    def test_cant_double_flag(self):
        req = make_post_request(user=self.user)
        flag(req, self.instance, self.comment.id)
        self.assertEqual(1, EnhancedThreadedCommentFlag.objects
                         .all().count(),
                         "There should be 1 comment flag row created")

        req = make_post_request(user=self.user)
        flag(req, self.instance, self.comment.id)
        self.assertEqual(1, EnhancedThreadedCommentFlag.objects
                         .all().count(),
                         "There should still be 1 comment flag row")

    def test_flag_unflag_flag_makes_two_rows(self):
        req = make_post_request(user=self.user)
        flag(req, self.instance, self.comment.id)
        self.assertEqual(1, EnhancedThreadedCommentFlag.objects
                         .all().count(),
                         "There should be 1 comment flag row created")

        req = make_post_request(user=self.user)
        unflag(req, self.instance, self.comment.id)
        self.assertEqual(1, EnhancedThreadedCommentFlag.objects
                         .all().count(),
                         "There should still 1 comment flag row after unflag")

        req = make_post_request(user=self.user)
        flag(req, self.instance, self.comment.id)
        self.assertEqual(2, EnhancedThreadedCommentFlag.objects.all().count(),
                         "There should be 2 comment flag rows")

    def test_flag_hide_flags_flag_makes_two_rows(self):
        req = make_post_request(user=self.user)
        flag(req, self.instance, self.comment.id)
        self.assertEqual(1, EnhancedThreadedCommentFlag.objects.all().count(),
                         "There should be 1 comment flag row created")

        req = make_post_request(user=self.admin,
                                params=_comment_ids_to_params(self.comment.id))
        hide_flags(req, self.instance)
        self.assertEqual(1, EnhancedThreadedCommentFlag.objects.all().count(),
                         "There should still 1 comment flag row after unflag")

        req = make_post_request(user=self.user)
        flag(req, self.instance, self.comment.id)
        self.assertEqual(2, EnhancedThreadedCommentFlag.objects.all().count(),
                         "There should be 2 comment flag rows")

    def test_multiple_flags(self):
        req = make_post_request(user=self.user)
        flag(req, self.instance, self.comment.id)
        req = make_post_request(user=self.admin)
        flag(req, self.instance, self.comment.id)

        self.assertEqual(2, EnhancedThreadedCommentFlag.objects.all().count(),
                         "There should be 2 comment flag rows")
        updated_comment = EnhancedThreadedComment.objects.get(
            pk=self.comment.id)
        self.assertTrue(updated_comment.is_flagged)

        req = make_post_request(user=self.user)
        unflag(req, self.instance, self.comment.id)
        self.assertEqual(2, EnhancedThreadedCommentFlag.objects.all().count(),
                         "Unflagging should not remove comment rows")
        self.assertTrue(updated_comment.is_flagged,
                        "Removing 1 of 2 flags leaves the comment flagged")
        self.assertFalse(updated_comment.is_flagged_by_user(self.user))
        self.assertTrue(updated_comment.is_flagged_by_user(self.admin))

    def test_hide_flags(self):
        req = make_post_request(user=self.user)
        flag(req, self.instance, self.comment.id)
        req = make_post_request(user=self.admin)
        flag(req, self.instance, self.comment.id)
        self.assertEqual(2, EnhancedThreadedCommentFlag.objects
                         .filter(hidden=False).count(),
                         "There should be 2 non-hidden comment flag rows")
        updated_comment = EnhancedThreadedComment.objects.get(
            pk=self.comment.id)
        self.assertTrue(updated_comment.is_flagged_by_user(self.user))
        self.assertTrue(updated_comment.is_flagged_by_user(self.admin))

        req = make_post_request(user=self.admin,
                                params=_comment_ids_to_params(self.comment.id))
        hide_flags(req, self.instance)
        self.assertEqual(2, EnhancedThreadedCommentFlag.objects
                         .filter(hidden=True).count(),
                         "There should be 2 hidden comment flag rows")
        updated_comment = EnhancedThreadedComment.objects.get(
            pk=self.comment.id)
        self.assertFalse(updated_comment.is_flagged_by_user(self.user))
        self.assertFalse(updated_comment.is_flagged_by_user(self.admin))

    def test_batch_hide_flags(self):
        req = make_post_request(user=self.admin)
        flag(req, self.instance, self.comment.id)

        req = make_post_request(user=self.user)
        flag(req, self.instance, self.comment2.id)

        self.assertEqual(2, EnhancedThreadedCommentFlag.objects
                         .filter(hidden=False).count(),
                         "There should be 2 non-hidden comment flag rows")

        req = make_post_request(user=self.admin,
                                params=_comment_ids_to_params(
                                    self.comment.id, self.comment2.id))
        hide_flags(req, self.instance)
        self.assertEqual(2, EnhancedThreadedCommentFlag.objects
                         .filter(hidden=True).count(),
                         "There should be 2 hidden comment flag rows")


class CommentArchiveTest(CommentModerationTestCase):
    def test_archive(self):
        self.assertFalse(self.comment.is_archived)
        req = make_post_request(user=self.user,
                                params=_comment_ids_to_params(self.comment.id))
        archive(req, self.instance)

        updated_comment = EnhancedThreadedComment.objects.get(
            pk=self.comment.id)
        self.assertTrue(updated_comment.is_archived)

    def test_unarchive(self):
        self.comment.is_archived = True
        self.comment.save()

        req = make_post_request(user=self.user,
                                params=_comment_ids_to_params(self.comment.id))
        unarchive(req, self.instance)

        updated_comment = EnhancedThreadedComment.objects.get(
            pk=self.comment.id)
        self.assertFalse(updated_comment.is_archived)

    def test_batch_archive(self):
        self.assertFalse(self.comment.is_archived)
        self.assertFalse(self.comment2.is_archived)
        req = make_post_request(user=self.user,
                                params=_comment_ids_to_params(
                                    self.comment.id, self.comment2.id))
        archive(req, self.instance)
        updated_comments = EnhancedThreadedComment.objects.all()
        for updated_comment in updated_comments:
            self.assertTrue(updated_comment.is_archived)

    def test_flagging_unarchives(self):
        self.comment.is_archived = True
        self.comment.save()

        req = make_post_request(user=self.user,
                                params=_comment_ids_to_params(self.comment.id))
        flag(req, self.instance, self.comment.id)
        updated_comment = EnhancedThreadedComment.objects.get(
            pk=self.comment.id)
        self.assertFalse(updated_comment.is_archived)


class CommentHideAndShowTest(CommentModerationTestCase):
    def test_hide(self):
        self.assertFalse(self.comment.is_removed)
        req = make_post_request(user=self.user,
                                params=_comment_ids_to_params(self.comment.id))
        hide(req, self.instance)

        updated_comment = EnhancedThreadedComment.objects.get(
            pk=self.comment.id)
        self.assertTrue(updated_comment.is_removed)

    def test_show(self):
        self.comment.is_removed = True
        self.comment.save()

        req = make_post_request(user=self.user,
                                params=_comment_ids_to_params(self.comment.id))
        show(req, self.instance)

        updated_comment = EnhancedThreadedComment.objects.get(
            pk=self.comment.id)
        self.assertFalse(updated_comment.is_removed)

    def test_batch_hide(self):
        self.assertFalse(self.comment.is_removed)
        self.assertFalse(self.comment2.is_removed)
        req = make_post_request(user=self.user,
                                params=_comment_ids_to_params(
                                    self.comment.id, self.comment2.id))
        hide(req, self.instance)
        updated_comments = EnhancedThreadedComment.objects.all()
        for updated_comment in updated_comments:
            self.assertTrue(updated_comment.is_removed)


class CommentUITest(CommentTestMixin, TreemapUITestCase):
    def assertCommentText(self, pk, comment_text):
        comment_text_el = (self
                           .find_id('c' + str(pk))
                           .find_element_by_css_selector('.comment_text'))
        self.assertEqual(comment_text_el.text, comment_text)

    def click_post_button(self):
        (self
         .find('.comment-create-form')
         .find_element_by_name('post')
         .click())

    def test_mask_comment(self):
        comment_text = "Time is a flat circle."
        removed_text = "[This comment has been removed by a moderator.]"
        comment_input_element_selector = '#id_comment'

        self.login_workflow()

        self.go_to_feature_detail(self.plot.pk)

        self.wait_until_present(comment_input_element_selector)

        self.find(comment_input_element_selector).send_keys(comment_text)
        self.click_post_button()

        sleep(3)
        comment_obj = EnhancedThreadedComment.objects.get(
            object_pk=self.plot.pk, content_type__name='plot')
        self.assertEqual(comment_obj.comment, comment_text)
        self.assertCommentText(comment_obj.pk, comment_text)

        self.go_to_feature_detail(self.plot.pk)
        self.assertCommentText(comment_obj.pk, comment_text)

        comment_obj.is_removed = True
        comment_obj.save()
        self.go_to_feature_detail(self.plot.pk)
        self.assertCommentText(comment_obj.pk, removed_text)
