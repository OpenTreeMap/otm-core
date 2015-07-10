# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from selenium.common.exceptions import ElementNotVisibleException

from treemap.tests.ui import TreemapUITestCase

from treemap.models import Plot, Tree


class PlotDetailUITestCase(TreemapUITestCase):
    def setUp(self):
        super(PlotDetailUITestCase, self).setUp()
        self.login_workflow()

        self.plot = Plot(instance=self.instance, geom=self.instance.center)
        self.plot.save_with_user(self.user)
        self.assertEqual(Plot.objects.count(), 1)

    def _select_elements(self):
        self.delete_begin = self.find_id('delete-object')
        self.delete_confirm = self.find_id('delete-confirm')
        self.delete_cancel = self.find_id('delete-cancel')
        self.begin_add_tree = self.find_id('begin-add-tree')
        self.diameter_input = self.find('input[data-class="diameter-input"]')
        self.save_edit = self.find_id('save-edit-map-feature')
        self.cancel_edit = self.find_id('cancel-edit-map-feature')
        self.edit_plot = self.find_id('edit-map-feature')
        self.tree_details_section = self.find_id('tree-details')

    def _assert_plot_and_tree_counts(self, nplots, ntrees):
        self.assertEqual(Plot.objects.count(), nplots)
        self.assertEqual(Tree.objects.count(), ntrees)


class PlotDetailDeleteUITestCase(PlotDetailUITestCase):

    def _assertCantClickDeleteOrCancel(self):
        with self.assertRaises(ElementNotVisibleException):
            self.delete_confirm.click()
            self.delete_cancel.click()

    def _click_delete(self):
        self._select_elements()
        self.delete_begin.click()
        self.wait_until_visible(self.delete_confirm)
        self.delete_confirm.click()
        self.wait_until_invisible(self.delete_confirm)

    def _execute_delete_workflow(self, before_args, after_args):
        self._select_elements()
        self._assertCantClickDeleteOrCancel()
        self._assert_plot_and_tree_counts(*before_args)

        self.delete_begin.click()
        self.wait_until_visible(self.delete_cancel)
        self.delete_cancel.click()
        self._assertCantClickDeleteOrCancel()
        self._assert_plot_and_tree_counts(*before_args)

        self._click_delete()
        self._assert_plot_and_tree_counts(*after_args)
