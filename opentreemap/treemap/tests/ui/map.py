# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from time import sleep

from selenium.webdriver.common.action_chains import ActionChains

from registration.models import RegistrationProfile

from treemap.tests.ui import create_instance, UITestCase, ui_test_urls

from treemap.tests import make_commander_user, create_mock_system_user
from treemap.models import Tree, Plot, User, Instance


DATABASE_COMMIT_DELAY = 2


class MapTest(UITestCase):
    urls = 'treemap.tests.ui.ui_test_urls'

    def setUp(self):

        # for some reason, the call to this helper
        # in setup_databases() on the test runner
        # is not executing in this context.
        # this is required to make the test work.
        create_mock_system_user()

        super(MapTest, self).setUp()

        instance_name = 'autotest_instance'

        Instance.objects.filter(name=instance_name).delete()

        self.instance = create_instance(
            name=instance_name,
            is_public=False,
            url_name='autotest-instance')

        self.user = make_commander_user(instance=self.instance,
                                        username='username')

        self.profile = RegistrationProfile.objects.create_profile(self.user)

    def tearDown(self):
        self.instance.delete()
        self.user.delete_with_user(User.system_user())
        super(MapTest, self).tearDown()

    def _browse_to_url(self, url):
        self.driver.get(self.live_server_url + url)

    def _process_login_form(self, username, password):
        username_elmt = self.driver.find_element_by_name('username')
        password_elmt = self.driver.find_element_by_name('password')

        username_elmt.send_keys(username)
        password_elmt.send_keys(password)

        submit = self.driver.find_element_by_css_selector('form * button')
        submit.click()

    def _login_workflow(self):
        self._browse_to_url('/accounts/logout/')
        self._browse_to_url('/accounts/login/')

        login = self.driver.find_element_by_id("login")
        login.click()

        self._process_login_form(self.user.username, 'password')

    def _drag_marker_on_map(self, endx, endy):
        actions = ActionChains(self.driver)
        marker = self.driver.find_elements_by_css_selector(
            '.leaflet-marker-pane img')[0]

        actions.drag_and_drop_by_offset(marker, endx, endy)
        actions.perform()

    def _click_point_on_map(self, x, y):
        # We're in add tree mode, now we need to click somewhere on the map
        map_div = self.driver.find_element_by_id('map')

        actions = ActionChains(self.driver)
        # move to the center of the map
        actions.move_to_element(map_div)

        # move away from the center
        actions.move_by_offset(x, y)

        actions.click()
        actions.perform()

    def _start_add_tree_and_click_point(self, x, y):
        # Enter add tree mode

        add_tree = self.driver.find_elements_by_css_selector(
            ".subhead .addBtn")[0]

        add_tree.click()

        self._click_point_on_map(x, y)

    def instance_trees(self):
        return Tree.objects.filter(instance=self.instance)

    def ntrees(self):
        return self.instance_trees().count()

    def instance_plots(self):
        return Plot.objects.filter(instance=self.instance)

    def nplots(self):
        return self.instance_plots().count()

    def _go_to_map_page(self):
        self._browse_to_url("/autotest-instance/map/")

    def _end_add_tree_by_clicking_add_tree(self):
        add_this_tree = self.driver.find_elements_by_css_selector(
            ".add-step-final .addBtn")[0]

        add_this_tree.click()

    def _login_and_go_to_map_page(self):
        self._login_workflow()
        self._go_to_map_page()

    def test_simple_add_plot_to_map(self):
        initial_tree_count = self.ntrees()
        initial_plot_count = self.nplots()

        self._login_and_go_to_map_page()
        self._start_add_tree_and_click_point(0, 10)

        # We don't have to put in any info to create a plot
        # So just add the plot!

        self._end_add_tree_by_clicking_add_tree()

        # Need to wait for change in database
        sleep(DATABASE_COMMIT_DELAY)

        # No trees were added
        self.assertEqual(initial_tree_count, self.ntrees())

        # But a plot should've been
        self.assertEqual(initial_plot_count + 1, self.nplots())

    def test_simple_add_tree_to_map(self):
        initial_tree_count = self.ntrees()
        initial_plot_count = self.nplots()

        self._login_and_go_to_map_page()
        self._start_add_tree_and_click_point(0, 10)

        diameter = self.driver.find_element_by_css_selector(
            'input[data-class="diameter-input"]')

        diameter.send_keys('44.0')

        self._end_add_tree_by_clicking_add_tree()

        # Need to wait for change in database
        sleep(DATABASE_COMMIT_DELAY)

        # New plot and tree
        self.assertEqual(initial_tree_count + 1, self.ntrees())
        self.assertEqual(initial_plot_count + 1, self.nplots())

        # Assume that the most recent tree is ours
        tree = self.instance_trees().order_by('-id')[0]

        self.assertEqual(tree.diameter, 44.0)

    def test_add_trees_with_same_details_to_map(self):
        initial_tree_count = self.ntrees()
        initial_plot_count = self.nplots()

        self._login_and_go_to_map_page()
        self._start_add_tree_and_click_point(0, 15)

        diameter = self.driver.find_element_by_css_selector(
            'input[data-class="diameter-input"]')

        diameter.send_keys('33.0')

        copy_radio_button = self.driver.find_element_by_css_selector(
            'input[value="copy"]')

        copy_radio_button.click()

        add_this_tree = self.driver.find_elements_by_css_selector(
            ".add-step-final .addBtn")[0]

        # Add the first tree
        add_this_tree.click()
        # Wait for change in database
        sleep(DATABASE_COMMIT_DELAY)

        # Add the next tree
        self._drag_marker_on_map(15, 15)
        add_this_tree.click()
        # Wait for change in database
        sleep(DATABASE_COMMIT_DELAY)

        # One more
        self._drag_marker_on_map(-15, 15)
        add_this_tree.click()
        # Wait for change in database
        sleep(DATABASE_COMMIT_DELAY)

        self.assertEqual(initial_tree_count + 3, self.ntrees())
        self.assertEqual(initial_plot_count + 3, self.nplots())

        # And all the recent trees should have a diameter of 33.0
        trees = self.instance_trees().order_by('-id')[0:3]

        for tree in trees:
            self.assertEqual(tree.diameter, 33.0)

    def test_add_trees_with_diff_details_to_map(self):
        initial_tree_count = self.ntrees()
        initial_plot_count = self.nplots()

        self._login_and_go_to_map_page()
        self._start_add_tree_and_click_point(0, 15)

        diameter = self.driver.find_element_by_css_selector(
            'input[data-class="diameter-input"]')

        diameter.send_keys('33.0')

        new_radio_button = self.driver.find_element_by_css_selector(
            'input[value="new"]')

        new_radio_button.click()

        add_this_tree = self.driver.find_elements_by_css_selector(
            ".add-step-final .addBtn")[0]

        # Add the first tree
        add_this_tree.click()
        # Wait for change in database
        sleep(DATABASE_COMMIT_DELAY)

        # Add the next tree
        # All fields should reset
        # since we don't set anything, this will generate a new
        # plot but no tree
        self._drag_marker_on_map(15, 15)
        add_this_tree.click()
        # Wait for change in database
        sleep(DATABASE_COMMIT_DELAY)

        # One more, setting the diameter again
        self._drag_marker_on_map(-15, 15)
        diameter.send_keys('99.0')
        add_this_tree.click()
        # Wait for change in database
        sleep(DATABASE_COMMIT_DELAY)

        self.assertEqual(initial_tree_count + 2, self.ntrees())
        self.assertEqual(initial_plot_count + 3, self.nplots())

        # And all the recent trees should have a diameter of 33.0
        tree_diams = [tree.diameter
                      for tree in self.instance_trees().order_by('-id')[0:2]]

        self.assertEqual([99.0, 33.0], tree_diams)

    def test_add_trees_and_continue_to_edit(self):
        initial_tree_count = self.ntrees()
        initial_plot_count = self.nplots()

        self._login_and_go_to_map_page()
        self._start_add_tree_and_click_point(0, 15)

        add_this_tree = self.driver.find_elements_by_css_selector(
            ".add-step-final .addBtn")[0]

        copy_radio_button = self.driver.find_element_by_css_selector(
            'input[value="edit"]')

        copy_radio_button.click()

        add_this_tree.click()

        # Need to wait for change in database
        sleep(DATABASE_COMMIT_DELAY)

        plot = Plot.objects.order_by('-id')[0]

        # Expect to be on edit page for the plot
        self.assertTrue(
            self.driver.current_url.endswith(
                '/autotest-instance/plots/%s/edit' % plot.pk))

        self.assertEqual(initial_tree_count, self.ntrees())
        self.assertEqual(initial_plot_count + 1, self.nplots())

    def test_edit_trees_on_map(self):
        # Since it is hard to determine where on the map to click
        # we add a tree, reload the page, and then click in the same
        # location
        initial_tree_count = self.ntrees()
        initial_plot_count = self.nplots()

        self._login_and_go_to_map_page()
        self._start_add_tree_and_click_point(20, 20)

        diameter = self.driver.find_element_by_css_selector(
            'input[data-class="diameter-input"]')

        diameter.send_keys('124.0')

        self._end_add_tree_by_clicking_add_tree()

        # Need to wait for change in database
        sleep(DATABASE_COMMIT_DELAY)

        self.assertEqual(initial_tree_count + 1, self.ntrees())
        self.assertEqual(initial_plot_count + 1, self.nplots())

        tree = self.instance_trees().order_by('-id')[0]

        self.assertEqual(tree.diameter, 124.0)

        ui_test_urls.testing_id = tree.plot.pk

        # Reload the page
        self._go_to_map_page()

        # Click on the tree we added
        self._click_point_on_map(20, 20)

        # Click on "quick edit"
        quick_edit_button = self.driver.find_element_by_id(
            'quick-edit-button')

        quick_edit_button.click()

        diameter = self.driver.find_element_by_css_selector(
            'input[data-class="diameter-input"]')

        diameter.clear()
        diameter.send_keys('32.0')

        save_details_button = self.driver.find_element_by_id(
            'save-details-button')

        save_details_button.click()

        # Need to wait for change in database
        sleep(DATABASE_COMMIT_DELAY)

        # Reload tree
        tree = Tree.objects.get(pk=tree.pk)

        self.assertEqual(tree.diameter, 32.0)
