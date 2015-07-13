# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from unittest.case import skip

from treemap.models import Tree

from cases import PlotDetailDeleteUITestCase


class PlotEditDeleteTest(PlotDetailDeleteUITestCase):
    def test_add_tree_then_delete(self):
        self.go_to_feature_detail(self.plot.pk, edit=True)

        self._select_elements()
        self.begin_add_tree.click()
        self.diameter_input.clear()
        self.diameter_input.send_keys('11')
        self.save_edit.click()
        self.wait_until_visible(self.edit_plot)

        self.assertEqual(Tree.objects.count(), 1)

        self._click_delete()
        self.assertEqual(Tree.objects.count(), 0)


class PlotDeleteTest(PlotDetailDeleteUITestCase):
    def test_delete_tree(self):
        tree = Tree(instance=self.instance, plot=self.plot)
        tree.save_with_user(self.user)
        self.go_to_feature_detail(self.plot.pk)
        self._execute_delete_workflow((1, 1), (1, 0))

    def test_delete_plot(self):
        self.go_to_feature_detail(self.plot.pk)
        self._execute_delete_workflow((1, 0), (0, 0))

    def test_delete_tree_then_plot(self):
        tree = Tree(instance=self.instance, plot=self.plot)
        tree.save_with_user(self.user)
        self.go_to_feature_detail(self.plot.pk)
        self._execute_delete_workflow((1, 1), (1, 0))
        self._execute_delete_workflow((1, 0), (0, 0))

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
        self._execute_delete_workflow((1, 1), (1, 0))
        self.wait_until_invisible(self.delete_confirm)
        self.assertTrue(
            self.driver.current_url.endswith(
                '/%s/features/%s/' % (self.instance.url_name,
                                      self.plot.pk)))

        # make another tree to reestablish test case
        tree2 = Tree(instance=self.instance, plot=self.plot)
        tree2.save_with_user(self.user)
        self.go_to_tree_detail(self.plot.pk, tree2.pk)
        self._execute_delete_workflow((1, 1), (1, 0))
        self.assertTrue(
            self.driver.current_url.endswith(
                '/%s/features/%s/' % (self.instance.url_name, self.plot.pk)))

        # finally, delete the plot too
        self._execute_delete_workflow((1, 0), (0, 0))
        self.assertTrue(
            self.driver.current_url.endswith('/%s/map/'
                                             % self.instance.url_name))
