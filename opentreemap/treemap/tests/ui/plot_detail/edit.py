# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from time import sleep
from selenium.common.exceptions import ElementNotVisibleException

from django.utils.unittest.case import skip

from treemap.models import Plot, Tree

from cases import PlotDetailUITestCase


class PlotEditTest(PlotDetailUITestCase):
    def test_edit_empty_plot_doesnt_create_tree(self):
        self.go_to_feature_detail(self.plot.pk)
        self._select_buttons()
        self.edit_plot.click()
        self.save_edit.click()
        self.wait_until_visible(self.edit_plot)
        self.assertEqual(Tree.objects.count(), 0)

    def test_edit_empty_plot_from_map(self):
        Plot.objects.all().delete()
        self.login_and_go_to_map_page()
        self.start_add_tree(20, 20)

        # this goes to the plot detail page
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
