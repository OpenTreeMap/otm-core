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
        self._browse_to_url("/autotest-instance/plots/%s/edit" % plot_id)

    def test_empty_plot_edit_url(self):

        self._login_and_go_to_map_page()
        self._start_add_tree_and_click_point(20, 20)

        self._end_add_tree_by_clicking_add_tree()

        # Need to wait for change in database
        sleep(DATABASE_COMMIT_DELAY)

        self.assertEqual(1, self.nplots())

        plot = self.instance_plots().order_by('-id')[0]

        self.assertEqual(plot.width, None)

        self._go_to_plot_detail_edit(plot.pk)

        plot_width_field = self.driver.find_element_by_css_selector(
            'input[name="plot.width"]')

        plot_width_field.clear()
        plot_width_field.send_keys('5')

        save_button = self.driver.find_element_by_id(
            'save-edit-plot')

        save_button.click()

        # Need to wait for change in database
        sleep(DATABASE_COMMIT_DELAY)

        # Reload tree
        plot = Plot.objects.get(pk=plot.pk)

        self.assertEqual(plot.width, 5)

    @skip("This test will pass when issue #943 is fixed "
          "https://github.com/azavea/OTM2/issues/943")
    def test_tree_add_cancel(self):

        plot = Plot(instance=self.instance,
                    geom=Point(0, 0))

        plot.save_with_user(self.user)

        self._login_workflow()
        self._go_to_plot_detail_edit(plot.pk)

        add_tree_button = self.driver.find_element_by_id(
            'add-tree')
        add_tree_button.click()

        cancel_edit_button = self.driver.find_element_by_id(
            'cancel-edit-plot')
        cancel_edit_button.click()

        tree_details_div = self.driver.find_element_by_id(
            'tree-details')

        with self.assertRaises(ElementNotVisibleException):
            tree_details_div.click()

        self.assertFalse(Tree.objects.filter(plot=plot).exists())
