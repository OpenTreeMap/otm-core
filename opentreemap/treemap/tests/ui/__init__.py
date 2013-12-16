import importlib

from django.test import LiveServerTestCase

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.firefox.webdriver import WebDriver

from django.conf import settings

from treemap.tests import create_mock_system_user, make_commander_user

from treemap.models import Tree, Plot, Instance, User


class UITestCase(LiveServerTestCase):
    def use_xvfb(self):
        from pyvirtualdisplay import Display
        self.display = Display('xvfb',
                               visible=1,
                               size=(1280, 1024))
        self.display.start()
        self.driver = WebDriver()

    def setUp(self):
        try:
            self.driver = WebDriver()
            ui_is_not_available = False
        except WebDriverException:
            ui_is_not_available = True

        if ui_is_not_available:
            self.use_xvfb()

        self.driver.implicitly_wait(10)
        super(UITestCase, self).setUp()

    def tearDown(self):
        self.driver.quit()
        if hasattr(self, 'display'):
            self.display.stop()

        super(UITestCase, self).tearDown()


class TreemapUITestCase(UITestCase):
    def setUp(self):
        # for some reason, the call to this helper
        # in setup_databases() on the test runner
        # is not executing in this context.
        # this is required to make the test work.
        create_mock_system_user()

        super(TreemapUITestCase, self).setUp()

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
        super(TreemapUITestCase, self).tearDown()

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


def parse_function_string(module_and_function_string):
    """
    Given a string like:
    a.b.c.f

    Return the function 'f' from module 'a.b.c'
    """
    parts = module_and_function_string.split('.')
    mod = '.'.join(parts[0:-1])
    fn = parts[-1]

    return getattr(importlib.import_module(mod), fn)


def _get_create_instance():
    return parse_function_string(
        settings.UITEST_CREATE_INSTANCE_FUNCTION)

create_instance = _get_create_instance()

from basic import *  # NOQA
from map import *  # NOQA
from plot_detail import *  # NOQA
