# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from time import sleep
from selenium.common.exceptions import ElementNotVisibleException

from django.utils.unittest.case import skip

from treemap.tests.ui import TreemapUITestCase

from treemap.models import Plot, Tree


class PlotEditTest(TreemapUITestCase):

    def test_edit_empty_plot(self):

        self.login_and_go_to_map_page()
        self.start_add_tree(20, 20)

        self.add_tree_done('edit')

        self.assertEqual(1, self.nplots())

        plot = self.instance_plots().order_by('-id')[0]

        self.assertEqual(plot.width, None)

        plot_width_field = self.find('input[name="plot.width"]')
        plot_width_field.clear()
        plot_width_field.send_keys('5')

        self.click('#save-edit-plot')
        self.wait_until_visible('#edit-plot')

        plot = Plot.objects.get(pk=plot.pk)

        self.assertEqual(plot.width, 5)

        sleep(1)  # prevent hang

    @skip("This test will pass when issue #943 is fixed "
          "https://github.com/azavea/OTM2/issues/943")
    def test_tree_add_cancel(self):

        plot = Plot(instance=self.instance, geom=self.instance.center)
        plot.save_with_user(self.user)

        self.login_workflow()
        self.go_to_feature_detail(plot.pk, edit=True)

        self.click('#add-tree')
        self.click('#cancel-edit-plot')
        self.wait_until_visible('#edit-plot')

        with self.assertRaises(ElementNotVisibleException):
            self.click('#tree-details')

        self.assertFalse(Tree.objects.filter(plot=plot).exists())


class PlotDeleteTest(TreemapUITestCase):

    def setUp(self):
        super(PlotDeleteTest, self).setUp()
        self.login_workflow()

        self.plot = Plot(instance=self.instance, geom=self.instance.center)
        self.plot.save_with_user(self.user)
        self.assertEqual(Plot.objects.count(), 1)

    def _select_buttons(self):
        self.delete_begin = self.find_id('delete-plot-or-tree')
        self.delete_confirm = self.find_id('delete-confirm')
        self.delete_cancel = self.find_id('delete-cancel')
        self.add_tree = self.find_id('add-tree')
        self.diameter_input = self.find('input[data-class="diameter-input"]')
        self.save_edit = self.find_id('save-edit-plot')
        self.edit_plot = self.find_id('edit-plot')

    def _assertCantClickDeleteOrCancel(self):
        with self.assertRaises(ElementNotVisibleException):
            self.delete_confirm.click()
            self.delete_cancel.click()

    def _click_delete(self):
        self._select_buttons()
        self.delete_begin.click()
        self.wait_until_visible(self.delete_confirm)
        self.delete_confirm.click()
        self.wait_until_invisible(self.delete_confirm)

    def _assert_plot_and_tree_counts(self, nplots, ntrees):
        self.assertEqual(Plot.objects.count(), nplots)
        self.assertEqual(Tree.objects.count(), ntrees)

    def test_delete_tree(self):
        tree = Tree(instance=self.instance, plot=self.plot)
        tree.save_with_user(self.user)
        self.assertEqual(Tree.objects.count(), 1)

        self.go_to_feature_detail(self.plot.pk)
        self._select_buttons()
        self._assertCantClickDeleteOrCancel()
        self._assert_plot_and_tree_counts(1, 1)

        self.delete_begin.click()
        self.delete_cancel.click()
        self._assertCantClickDeleteOrCancel()
        self._assert_plot_and_tree_counts(1, 1)

        self._click_delete()
        self._assert_plot_and_tree_counts(1, 0)

    def test_delete_plot(self):
        self.go_to_feature_detail(self.plot.pk)
        self._select_buttons()
        self._assertCantClickDeleteOrCancel()
        self.assertEqual(Plot.objects.count(), 1)

        self._select_buttons()
        self.delete_begin.click()
        self.delete_cancel.click()
        self.assertEqual(Plot.objects.count(), 1)
        self._assertCantClickDeleteOrCancel()

        self._click_delete()
        self.assertEqual(Plot.objects.count(), 0)

    def test_add_tree_then_delete(self):
        self.go_to_feature_detail(self.plot.pk, edit=True)

        self._select_buttons()
        self.add_tree.click()
        self.diameter_input.clear()
        self.diameter_input.send_keys('11')
        self.save_edit.click()
        self.wait_until_visible(self.edit_plot)

        self.assertEqual(Tree.objects.count(), 1)

        self._click_delete()
        self.assertEqual(Tree.objects.count(), 0)

    @skip("revisit when urls are figured out")
    def test_delete_tree_from_both_urls(self):
        """
        tests that features/%s/trees/%s/ and features/%s/
        have the same delete tree UI behavior

        this test was created after discovering this bug
        on staging.
        """

        # make a plot and tree
        tree1 = Tree(instance=self.instance, plot=self.plot)
        tree1.save_with_user(self.user)

        # delete the tree from plot detail page
        self.go_to_feature_detail(self.plot.pk)
        self._select_buttons()
        self.delete_begin.click()
        self.delete_confirm.click()
        self.wait_until_invisible(self.delete_confirm)

        # Expect tree to be deleted and redirect
        # to detail page for the plot
        self._assert_plot_and_tree_counts(1, 0)
        self.assertTrue(
            self.driver.current_url.endswith(
                '/%s/features/%s/' % (self.instance.url_name,
                                      self.plot.pk)))

        # make another tree to reestablish test case
        tree2 = Tree(instance=self.instance, plot=self.plot)
        tree2.save_with_user(self.user)
        self._assert_plot_and_tree_counts(1, 1)

        # delete the tree from the tree detail page
        self.go_to_tree_detail(self.plot.pk, tree2.pk)
        self._click_delete()

        # Expect tree to be deleted and redirect
        # to detail page for the plot (again)
        self._assert_plot_and_tree_counts(1, 0)
        self.assertTrue(
            self.driver.current_url.endswith(
                '/%s/features/%s/' % (self.instance.url_name, self.plot.pk)))

        # finally, delete the plot and expect to be
        # on the map page
        self._click_delete()
        self._assert_plot_and_tree_counts(0, 0)
        self.assertTrue(
            self.driver.current_url.endswith('/%s/map/'
                                             % self.instance.url_name))
