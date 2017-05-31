
# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from time import sleep

from selenium.webdriver.support.wait import WebDriverWait

from django.core.urlresolvers import reverse

from treemap.instance import create_stewardship_udfs
from treemap.tests.ui import TreemapUITestCase

from otm_comments.models import EnhancedThreadedComment
from otm_comments.tests import CommentTestMixin, make_comment


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
        self.comments_url = reverse('comment_moderation_admin',
                                    args=(self.instance.url_name,))
        self.browse_to_url(self.comments_url)

    def assert_num_rows(self, num, msg=None):
        rows = self.driver.find_elements_by_css_selector(
            '.comment-table tbody tr')

        self.assertEqual(num, len(rows), msg)

    def go_to_page(self, page_num):
        page = str(page_num)
        page_link = self.find('.pagination').find_element_by_link_text(page)

        self.driver.execute_script("return arguments[0].scrollIntoView();",
                                   page_link)
        page_link.click()

        self.wait_until_on_page(page_num)

    def wait_until_on_page(self, page_num):
        # The each link is page # + 2, due to the "first" and "previous" links
        page_num = page_num + 2
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

        batch_checkbox = self.find('[data-toggle-all]')
        batch_checkbox.click()

        for checkbox in checkboxes:
            self.assertTrue(
                checkbox.is_selected(),
                "The select all checkbox should check every row's box")

        # Open the batch action dropdown
        self.click('[data-comment-batch-dropdown]')

        self.find('[data-batch-action]') \
            .find_element_by_link_text('Archive') \
            .click()

        sleep(3)

        self.assertEqual(5, EnhancedThreadedComment.objects
                         .filter(is_archived=True).count())


class CommentUITest(CommentTestMixin, TreemapUITestCase):
    def setUp(self):
        super(CommentUITest, self).setUp()
        create_stewardship_udfs(self.instance)

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
            object_pk=self.plot.pk, content_type__model='plot')
        self.assertEqual(comment_obj.comment, comment_text)
        self.assertCommentText(comment_obj.pk, comment_text)

        self.go_to_feature_detail(self.plot.pk)
        self.assertCommentText(comment_obj.pk, comment_text)

        comment_obj.is_removed = True
        comment_obj.save()
        self.go_to_feature_detail(self.plot.pk)
        self.assertCommentText(comment_obj.pk, removed_text)
