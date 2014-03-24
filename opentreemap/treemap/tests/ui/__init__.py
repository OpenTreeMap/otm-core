import importlib

from django.test import LiveServerTestCase
from django.conf import settings

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.firefox.webdriver import WebDriver

from treemap.tests import create_mock_system_user, make_commander_user

from treemap.models import Tree, Plot, Instance, User


def patch_broken_pipe_error():
    """Monkey Patch BaseServer.handle_error to not write
    a stacktrace to stderr on broken pipe.
    http://stackoverflow.com/a/21788372/362702"""
    import sys
    from SocketServer import BaseServer
    from wsgiref import handlers

    handle_error = BaseServer.handle_error
    log_exception = handlers.BaseHandler.log_exception

    def is_broken_pipe_error():
        type, err, tb = sys.exc_info()
        return repr(err) == "error(32, 'Broken pipe')"

    def my_handle_error(self, request, client_address):
        if not is_broken_pipe_error():
            handle_error(self, request, client_address)

    def my_log_exception(self, exc_info):
        if not is_broken_pipe_error():
            log_exception(self, exc_info)

    BaseServer.handle_error = my_handle_error
    handlers.BaseHandler.log_exception = my_log_exception


patch_broken_pipe_error() # Muzzle annoying output from UI tests


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

    def click(self, selector):
        self.find(selector).click()

    def find(self, selector):
        return self.driver.find_element_by_css_selector(selector)

    def find_name(self, name):
        return self.driver.find_element_by_name(name)

    def find_id(self, id):
        return self.driver.find_element_by_id(id)

    def process_login_form(self, username, password):
        username_elmt = self.find_name('username')
        password_elmt = self.find_name('password')

        username_elmt.send_keys(username)
        password_elmt.send_keys(password)

        self.click('form * button')

    def browse_to_url(self, url):
        self.driver.get(self.live_server_url + url)

    def find_anchor_by_url(self, url):
        return self.find("[href='%s']" % url)



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

    def login_workflow(self):
        self.browse_to_url('/accounts/logout/')
        self.browse_to_url('/accounts/login/')

        login = self.find_id("login")
        login.click()

        self.process_login_form(self.user.username, 'password')

    def drag_marker_on_map(self, endx, endy):
        actions = ActionChains(self.driver)
        marker = self.find('.leaflet-marker-pane img')

        actions.drag_and_drop_by_offset(marker, endx, endy)
        actions.perform()

    def click_point_on_map(self, x, y):
        # We're in add tree mode, now we need to click somewhere on the map
        map_div = self.find_id('map')

        actions = ActionChains(self.driver)
        # move to the center of the map
        actions.move_to_element(map_div)

        # move away from the center
        actions.move_by_offset(x, y)

        actions.click()
        actions.perform()

    def start_add_tree(self):
        # Enter add tree mode

        add_tree = self.driver.find_elements_by_css_selector(
            ".subhead .addBtn")[0]

        add_tree.click()

    def start_add_tree_and_click_point(self, x, y):
        self.start_add_tree()
        self.click_point_on_map(x, y)

    def instance_trees(self):
        return Tree.objects.filter(instance=self.instance)

    def ntrees(self):
        return self.instance_trees().count()

    def instance_plots(self):
        return Plot.objects.filter(instance=self.instance)

    def nplots(self):
        return self.instance_plots().count()

    def go_to_map_page(self):
        self.browse_to_url("/autotest-instance/map/")

    def end_add_tree_by_clicking_add_tree(self):
        add_this_tree = self.driver.find_elements_by_css_selector(
            ".add-step-final .addBtn")[0]

        add_this_tree.click()

    def login_and_go_to_map_page(self):
        self.login_workflow()
        self.go_to_map_page()


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

from registration_views import *  # NOQA
from map import *  # NOQA
from plot_detail import *  # NOQA
