# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from treemap.tests.ui import TreemapUITestCase, ui_test_urls
from treemap.models import Tree, Plot


class MapTest(TreemapUITestCase):
    # Use modified URL set (e.g. to mock out tiler requests)
    urls = 'treemap.tests.ui.ui_test_urls'

    def test_simple_add_plot_to_map(self):
        initial_tree_count = self.ntrees()
        initial_plot_count = self.nplots()

        self.login_and_go_to_map_page()
        self.start_add_tree(0, 10)

        # We don't have to put in any info to create a plot
        # So just add the plot!

        self.add_tree_done()

        # No trees were added
        self.assertEqual(initial_tree_count, self.ntrees())

        # But a plot should've been
        self.assertEqual(initial_plot_count + 1, self.nplots())

    def test_simple_add_tree_to_map(self):
        initial_tree_count = self.ntrees()
        initial_plot_count = self.nplots()

        self.login_and_go_to_map_page()
        self.start_add_tree(0, 10)

        diameter = self.find('input[data-class="diameter-input"]')
        diameter.send_keys('44.0')

        self.add_tree_done()

        # New plot and tree
        self.assertEqual(initial_tree_count + 1, self.ntrees())
        self.assertEqual(initial_plot_count + 1, self.nplots())

        # Assume that the most recent tree is ours
        tree = self.instance_trees().order_by('-id')[0]

        self.assertEqual(tree.diameter, 44.0)

    def test_add_trees_with_same_details_to_map(self):
        initial_tree_count = self.ntrees()
        initial_plot_count = self.nplots()

        self.login_and_go_to_map_page()
        self.start_add_tree(0, 15)

        diameter = self.driver.find_element_by_css_selector(
            'input[data-class="diameter-input"]')

        diameter.send_keys('33.0')

        # Add the first tree
        self.add_tree_done('copy')

        # Add the next tree
        self.drag_marker_on_map(15, 15)
        self.add_tree_done('copy')

        # One more
        self.drag_marker_on_map(-15, 15)
        self.add_tree_done()

        self.assertEqual(initial_tree_count + 3, self.ntrees())
        self.assertEqual(initial_plot_count + 3, self.nplots())

        # And all the recent trees should have a diameter of 33.0
        trees = self.instance_trees().order_by('-id')[0:3]

        for tree in trees:
            self.assertEqual(tree.diameter, 33.0)

    def test_add_trees_with_diff_details_to_map(self):
        initial_tree_count = self.ntrees()
        initial_plot_count = self.nplots()

        self.login_and_go_to_map_page()
        self.start_add_tree(0, 15)

        diameter = self.driver.find_element_by_css_selector(
            'input[data-class="diameter-input"]')

        diameter.send_keys('33.0')

        # Add the first tree
        self.add_tree_done('new')

        # Add the next tree
        # All fields should reset
        # This will generate a new plot but no tree
        self.drag_marker_on_map(15, 15)
        self.add_tree_done('new')

        # One more, setting the diameter again
        self.drag_marker_on_map(-15, 15)
        diameter.send_keys('99.0')
        self.add_tree_done()

        self.assertEqual(initial_tree_count + 2, self.ntrees())
        self.assertEqual(initial_plot_count + 3, self.nplots())

        # And all the recent trees should have a diameter of 33.0
        tree_diams = [tree.diameter
                      for tree in self.instance_trees().order_by('-id')[0:2]]

        self.assertEqual([99.0, 33.0], tree_diams)

    def test_add_trees_and_continue_to_edit(self):
        initial_tree_count = self.ntrees()
        initial_plot_count = self.nplots()

        self.login_and_go_to_map_page()
        self.start_add_tree(0, 15)

        self.add_tree_done('edit')

        plot = Plot.objects.order_by('-id')[0]

        # Expect to be on edit page for the plot
        self.assertTrue(
            self.driver.current_url.endswith(
                '/autotest-instance/features/%s/edit' % plot.pk))

        self.assertEqual(initial_tree_count, self.ntrees())
        self.assertEqual(initial_plot_count + 1, self.nplots())

    def test_edit_trees_on_map(self):
        # Since it is hard to determine where on the map to click
        # we add a tree, reload the page, and then click in the same
        # location
        initial_tree_count = self.ntrees()
        initial_plot_count = self.nplots()

        self.login_and_go_to_map_page()
        self.start_add_tree(20, 20)

        diameter = self.driver.find_element_by_css_selector(
            'input[data-class="diameter-input"]')

        diameter.send_keys('124.0')

        self.add_tree_done()

        self.assertEqual(initial_tree_count + 1, self.ntrees())
        self.assertEqual(initial_plot_count + 1, self.nplots())

        tree = self.instance_trees().order_by('-id')[0]

        self.assertEqual(tree.diameter, 124.0)

        ui_test_urls.testing_id = tree.plot.pk

        # Reload the page
        self.go_to_map_page()

        # Click on the tree we added
        self.click_point_on_map(20, 20)

        self.click_when_visible('#quick-edit-button')
        self.wait_until_visible('#save-details-button')

        diameter = self.driver.find_element_by_css_selector(
            'input[data-class="diameter-input"]')

        diameter.clear()
        diameter.send_keys('32.0')

        self.click('#save-details-button')
        self.wait_until_visible('#quick-edit-button')

        # Reload tree
        tree = Tree.objects.get(pk=tree.pk)

        self.assertEqual(tree.diameter, 32.0)


class ModeChangeTest(TreemapUITestCase):
    urls = 'treemap.tests.ui.ui_test_urls'

    def test_leave_page(self):
        self.login_and_go_to_map_page()
        self.browse_to_url('/autotest-instance/edits/')
        self.assertTrue(self.driver.current_url.endswith('edits/'),
                        "When no locks are present, browsing should succeed")

    def test_locked_leave_page_add_tree(self):
        self.login_workflow()
        self.browse_to_url("/autotest-instance/map/")
        self.click_add_tree()
        self.browse_to_url('/autotest-instance/edits/')

        self.driver.switch_to_alert().dismiss()

        self.assertFalse(self.driver.current_url.endswith('edits/'),
                         "Should not have left page after dismissing alert.")

    def test_locked_add_tree_in_edit_mode(self):

        self.login_and_go_to_map_page()
        self.start_add_tree(20, 20)
        self.add_tree_done()

        plot = self.instance_plots().order_by('-id')[0]
        ui_test_urls.testing_id = plot.pk

        # Reload the page
        self.go_to_map_page()

        # Click on the tree we added
        self.click_point_on_map(20, 20)

        # enter edit mode, which should lock
        self.click_when_visible('#quick-edit-button')

        expected_alert_text = ("You have begun entering data. "
                               "Any unsaved changes will be lost. "
                               "Are you sure you want to continue?")

        self.click_add_tree()
        alert = self.driver.switch_to_alert()
        self.assertEqual(alert.text, expected_alert_text)
        alert.dismiss()
        self.assertFalse(self.driver.current_url.endswith('addTree'))

        self.click_add_tree()
        alert = self.driver.switch_to_alert()
        self.assertEqual(alert.text, expected_alert_text)

        alert.accept()
        self.assertTrue(self.driver.current_url.endswith('addTree'))
