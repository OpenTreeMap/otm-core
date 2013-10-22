from unittest import TestCase
from time import sleep

from selenium.webdriver.common.action_chains import ActionChains

from django.conf import settings

from registration.models import RegistrationProfile

from uitests import create_instance
import uitests

from treemap.tests import make_commander_user
from treemap.models import Tree, Plot, User


userUUID = 1
DATABASE_COMMIT_DELAY = 2


class MapTest(TestCase):
    def setUp(self):
        self.driver = uitests.driver

        self.driver.implicitly_wait(10)

        self.instance = create_instance(
            name='autotest_instance',
            is_public=False,
            url_name='autotest-instance')

        self.user = self._create_user(self.instance)
        self.profile = RegistrationProfile.objects.create_profile(self.user)

    def tearDown(self):
        self.instance.delete()
        self.user.delete_with_user(User.system_user())

    def _create_user(self, instance):
        global userUUID

        username = 'autotest_%s' % userUUID
        email = '%s@testing.org' % username
        userUUID += 1

        User.objects.filter(email=email).delete()

        u = make_commander_user(instance, username)

        u.set_password(username)
        u.save()
        setattr(u, 'plain_password', username)

        return u

    def _process_login_form(self, username, password):
        username_elmt = self.driver.find_element_by_name('username')
        password_elmt = self.driver.find_element_by_name('password')

        username_elmt.send_keys(username)
        password_elmt.send_keys(password)

        submit = self.driver.find_element_by_css_selector('form * button')
        submit.click()

    def _login_workflow(self):
        self.driver.get("http://localhost:%s/accounts/logout/" %
                        settings.UITESTS_PORT)

        self.driver.get("http://localhost:%s/accounts/login/" %
                        settings.UITESTS_PORT)

        # find the element that's name attribute is q (the google search box)
        login = self.driver.find_element_by_id("login")
        login.click()

        self._process_login_form(
            self.user.username, self.user.plain_password)

    def _action_chain_for_moving_to_map_at_offset(self, x, y):
        # We're in add tree mode, now we need to click somewhere
        # on the map
        map_div = self.driver.find_element_by_id('map')

        actions = ActionChains(self.driver)
        # move to the center of the map
        actions.move_to_element(map_div)

        # move away from the center
        actions.move_by_offset(x, y)

        return actions

    def ntrees(self):
        return Tree.objects.filter(instance=self.instance).count()

    def nplots(self):
        return Plot.objects.filter(instance=self.instance).count()

    def _go_to_map_page(self):
        self.driver.get("http://localhost:%s/autotest-instance/map/" %
                        settings.UITESTS_PORT)

    def _start_add_tree_workflow(self):
        add_tree = self.driver.find_elements_by_css_selector(
            ".subhead .addBtn")[0]

        add_tree.click()

    def _end_add_tree_workflow_by_clicking_add_tree(self):
        add_this_tree = self.driver.find_elements_by_css_selector(
            ".add-step-final .addBtn")[0]

        add_this_tree.click()

    def test_simple_add_plot_to_map(self):
        initial_tree_count = self.ntrees()
        initial_plot_count = self.nplots()

        self._login_workflow()
        self._go_to_map_page()

        self._start_add_tree_workflow()

        actions = self._action_chain_for_moving_to_map_at_offset(10, 10)

        # Click on the map
        actions.click()
        actions.perform()

        # NOTE: We shouldn't have to put in ANY info to create a plot
        self._end_add_tree_workflow_by_clicking_add_tree()

        # Need to wait for change in database
        sleep(DATABASE_COMMIT_DELAY)

        # No trees were added
        self.assertEqual(initial_tree_count, self.ntrees())

        # But a plot should've been
        self.assertEqual(initial_plot_count + 1, self.nplots())

    def test_simple_add_tree_to_map(self):
        initial_tree_count = self.ntrees()
        initial_plot_count = self.nplots()

        self._login_workflow()
        self._go_to_map_page()

        self._start_add_tree_workflow()

        actions = self._action_chain_for_moving_to_map_at_offset(0, 10)

        # Click on the map
        actions.click()
        actions.perform()

        diameter = self.driver.find_element_by_css_selector(
            'input[data-class="diameter-input"]')

        diameter.send_keys('44.0')

        self._end_add_tree_workflow_by_clicking_add_tree()

        # Need to wait for change in database
        sleep(DATABASE_COMMIT_DELAY)

        # New plot and tree
        self.assertEqual(initial_tree_count + 1, self.ntrees())
        self.assertEqual(initial_plot_count + 1, self.nplots())

        # Assume that the most recent tree is ours
        tree = Tree.objects.order_by('-id')[0]

        self.assertEqual(tree.diameter, 44.0)
