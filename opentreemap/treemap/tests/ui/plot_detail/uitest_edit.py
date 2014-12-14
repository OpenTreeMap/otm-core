# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from treemap.models import Plot, Tree

from cases import PlotDetailUITestCase


class PlotEditTest(PlotDetailUITestCase):
    def test_edit_empty_plot_doesnt_create_tree(self):
        self.go_to_feature_detail(self.plot.pk)
        self._select_elements()
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

    def test_tree_add_cancel(self):
        """
        This is an old test, written around #943 on github.
        It has since been more or less duplicated in add.py, but
        remains around for diagnostics.
        """

        plot = Plot(instance=self.instance, geom=self.instance.center)
        plot.save_with_user(self.user)

        self.login_workflow()
        self.go_to_feature_detail(plot.pk, edit=True)
        self._select_elements()

        self.begin_add_tree.click()
        self.cancel_edit.click()
        self.wait_until_visible(self.edit_plot)

        self.assertElementVisibility(self.tree_details_section, False)
        self.assertFalse(Tree.objects.filter(plot=plot).exists())

    def test_plot_with_tree_always_shows_tree_details(self):
        plot = Plot(instance=self.instance, geom=self.instance.center)
        plot.save_with_user(self.user)
        tree = Tree(plot=plot, diameter=10, instance=self.instance)
        tree.save_with_user(self.user)

        self.login_workflow()
        self.go_to_feature_detail(plot.pk)
        self._select_elements()
        self.edit_plot.click()
        self.cancel_edit.click()
        self.assertElementVisibility(self.tree_details_section, visible=True)
