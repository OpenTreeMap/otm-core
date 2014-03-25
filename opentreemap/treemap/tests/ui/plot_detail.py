# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from time import sleep

from selenium.common.exceptions import ElementNotVisibleException
from django.contrib.gis.geos import Point

from django.utils.unittest.case import skip

from treemap.tests.ui import TreemapUITestCase

from treemap.models import Plot, Tree

DATABASE_COMMIT_DELAY = 2


class PlotDetailTest(TreemapUITestCase):

    def _go_to_plot_detail_edit(self, plot_id):
        self.browse_to_url("/autotest-instance/features/%s/edit" % plot_id)

    def _go_to_plot_detail(self, plot_id):
        self.browse_to_url("/autotest-instance/features/%s/" % plot_id)

    def _go_to_tree_detail(self, plot_id, tree_id):
        self.browse_to_url("/autotest-instance/features/%s/trees/%s/"
                            % (plot_id, tree_id))


class PlotEditTest(PlotDetailTest):

    def test_empty_plot_edit_url(self):

        self.login_and_go_to_map_page()
        self.start_add_tree(20, 20)

        self.add_tree_done()

        # Need to wait for change in database
        sleep(DATABASE_COMMIT_DELAY)

        self.assertEqual(1, self.nplots())

        plot = self.instance_plots().order_by('-id')[0]

        self.assertEqual(plot.width, None)

        self._go_to_plot_detail_edit(plot.pk)

        plot_width_field = self.find('input[name="plot.width"]')

        plot_width_field.clear()
        plot_width_field.send_keys('5')

        self.click('#save-edit-plot')

        self.wait_until_visible(self.find('#edit-plot'))

        # Reload tree
        plot = Plot.objects.get(pk=plot.pk)

        self.assertEqual(plot.width, 5)

    @skip("This test will pass when issue #943 is fixed "
          "https://github.com/azavea/OTM2/issues/943")
    def test_tree_add_cancel(self):

        plot = Plot(instance=self.instance,
                    geom=Point(0, 0))

        plot.save_with_user(self.user)

        self.login_workflow()
        self._go_to_plot_detail_edit(plot.pk)

        self.click('#add-tree')
        self.click('#cancel-edit-plot')

        with self.assertRaises(ElementNotVisibleException):
            self.click('#tree-details')

        self.assertFalse(Tree.objects.filter(plot=plot).exists())


class PlotDeleteTest(PlotDetailTest):

    def tearDown(self, *args, **kwargs):
        # This sleep is critical, removing it causes the tests to break
        sleep(10)
        super(PlotDeleteTest, self).tearDown(*args, **kwargs)

    def select_buttons(self):
        self.delete_begin = self.find_id('delete-plot-or-tree')
        self.delete_confirm = self.find_id('delete-confirm')
        self.delete_cancel = self.find_id('delete-cancel')
        self.add_tree = self.find_id('add-tree')
        self.diameter_input = self.find('input[data-class="diameter-input"]')
        self.save_edit = self.find_id('save-edit-plot')
        self.edit_plot = self.find_id('edit-plot')

    def assertCantClickDeleteOrCancel(self):
        with self.assertRaises(ElementNotVisibleException):
            self.delete_confirm.click()
            self.delete_cancel.click()

    def test_delete_tree(self):
        plot = Plot(instance=self.instance,
                    geom=Point(0, 0))
        plot.save_with_user(self.user)
        tree = Tree(instance=self.instance,
                    plot=plot)
        tree.save_with_user(self.user)

        self.assertEqual(Plot.objects.count(), 1)
        self.assertEqual(Tree.objects.count(), 1)

        self.login_workflow()
        self._go_to_plot_detail(plot.pk)
        self.select_buttons()
        self.assertCantClickDeleteOrCancel()
        self.assertEqual(Plot.objects.count(), 1)
        self.assertEqual(Tree.objects.count(), 1)

        self.delete_begin.click()
        self.delete_cancel.click()
        self.assertCantClickDeleteOrCancel()
        self.assertEqual(Plot.objects.count(), 1)
        self.assertEqual(Tree.objects.count(), 1)

        self.select_buttons()
        self.delete_begin.click()
        self.delete_confirm.click()
        sleep(DATABASE_COMMIT_DELAY)
        self.assertEqual(Plot.objects.count(), 1)
        self.assertEqual(Tree.objects.count(), 0)

    def test_delete_plot(self):
        plot = Plot(instance=self.instance,
                    geom=Point(0, 0))
        plot.save_with_user(self.user)

        self.login_workflow()
        self._go_to_plot_detail(plot.pk)
        self.select_buttons()
        self.assertCantClickDeleteOrCancel()
        self.assertEqual(Plot.objects.count(), 1)

        self.select_buttons()
        self.delete_begin.click()
        self.delete_cancel.click()
        self.assertEqual(Plot.objects.count(), 1)
        self.assertCantClickDeleteOrCancel()

        self.delete_begin.click()
        self.delete_confirm.click()
        sleep(DATABASE_COMMIT_DELAY)
        self.assertEqual(Plot.objects.count(), 0)

    def test_add_tree_then_delete(self):
        plot = Plot(instance=self.instance,
                    geom=Point(0, 0))
        plot.save_with_user(self.user)
        self.login_workflow()
        self._go_to_plot_detail_edit(plot.pk)

        self.select_buttons()
        self.add_tree.click()
        self.diameter_input.clear()
        self.diameter_input.send_keys('11')
        self.save_edit.click()
        self.wait_until_visible(self.edit_plot)

        self.assertEqual(Tree.objects.count(), 1)

        self.delete_begin.click()
        self.delete_confirm.click()
        sleep(DATABASE_COMMIT_DELAY)
        self.assertEqual(Tree.objects.count(), 0)

    @skip("revist when urls are figured out")
    def test_delete_tree_from_both_urls(self):
        """
        tests that features/%s/trees/%s/ and features/%s/
        have the same delete tree UI behavior

        this test was created after discovering this bug
        on staging.
        """

        # make a plot and tree
        plot = Plot(instance=self.instance,
                    geom=Point(0, 0))
        plot.save_with_user(self.user)
        tree1 = Tree(instance=self.instance,
                     plot=plot)
        tree1.save_with_user(self.user)

        # login and delete the tree from plot detail page
        self.login_workflow()
        self._go_to_plot_detail(plot.pk)
        self.select_buttons()
        self.delete_begin.click()
        self.delete_confirm.click()
        sleep(DATABASE_COMMIT_DELAY)

        # Expect tree to be deleted and redirect
        # to detail page for the plot
        self.assertEqual(Plot.objects.count(), 1)
        self.assertEqual(Tree.objects.count(), 0)
        self.assertTrue(
            self.driver.current_url.endswith(
                '/autotest-instance/features/%s/' % plot.pk))

        # make another tree to reestablish test case
        tree2 = Tree(instance=self.instance,
                     plot=plot)
        tree2.save_with_user(self.user)
        self.assertEqual(Plot.objects.count(), 1)
        self.assertEqual(Tree.objects.count(), 1)

        # delete the tree from the tree detail page
        self._go_to_tree_detail(plot.pk, tree2.pk)
        self.select_buttons()
        self.delete_begin.click()
        self.delete_confirm.click()
        sleep(DATABASE_COMMIT_DELAY)

        # Expect tree to be deleted and redirect
        # to detail page for the plot (again)
        self.assertEqual(Plot.objects.count(), 1)
        self.assertEqual(Tree.objects.count(), 0)
        self.assertTrue(
            self.driver.current_url.endswith(
                '/autotest-instance/features/%s/' % plot.pk))

        # finally, delete the plot and expect to be
        # on the map page
        self.select_buttons()
        self.delete_begin.click()
        self.delete_confirm.click()
        sleep(DATABASE_COMMIT_DELAY)
        self.assertEqual(Plot.objects.count(), 0)
        self.assertEqual(Tree.objects.count(), 0)
        self.assertTrue(
            self.driver.current_url.endswith('/autotest-instance/map/'))
