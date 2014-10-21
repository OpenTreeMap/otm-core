# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from treemap.models import Tree

from cases import PlotDetailUITestCase


class PlotAddTest(PlotDetailUITestCase):
    def assertTreePresenceSection(self, with_button):
        self.assertElementVisibility('tree-presence-section', True)
        self.assertElementVisibility('begin-add-tree', with_button)

    def test_add_tree_cleans_up_tree_section(self):
        "Addresses #1717 on github"
        self.go_to_feature_detail(self.plot.pk)
        self._select_elements()
        self.edit_plot.click()

        self.wait_until_visible(self.begin_add_tree)
        self.begin_add_tree.click()
        self.cancel_edit.click()

        self.wait_until_visible(self.edit_plot)
        self.assertElementVisibility(self.begin_add_tree, False)
        self.assertElementVisibility(self.tree_details_section, False)

        self.edit_plot.click()
        self.assertElementVisibility(self.begin_add_tree, True)
        self.assertElementVisibility(self.tree_details_section, False)

    def test_add_tree_cancel_cleans_up_form(self):
        "Addresses #1716 on github"
        self.assertFalse(Tree.objects.filter(plot=self.plot).exists())

        self.go_to_feature_detail(self.plot.pk)
        self._select_elements()
        self.edit_plot.click()
        self.wait_until_visible(self.begin_add_tree)
        self.begin_add_tree.click()

        self.find('input[name="tree.height"]').send_keys('11')

        self.cancel_edit.click()
        self.wait_until_visible(self.edit_plot)
        self.assertElementVisibility(self.begin_add_tree, False)
        self.assertElementVisibility(self.tree_details_section, False)

        self.edit_plot.click()
        self.assertElementVisibility(self.tree_details_section, False)
        self.save_edit.click()
        self.go_to_feature_detail(self.plot.pk)

        self.assertFalse(Tree.objects.filter(plot=self.plot).exists())

    def test_empty_plot_has_add_tree_section(self):
        "Address #1375 and #1027 on github"
        self.go_to_feature_detail(self.plot.pk)
        self._select_elements()
        self.assertTreePresenceSection(with_button=False)
        self.edit_plot.click()
        self.assertTreePresenceSection(with_button=True)
        self.cancel_edit.click()
        self.assertTreePresenceSection(with_button=False)
