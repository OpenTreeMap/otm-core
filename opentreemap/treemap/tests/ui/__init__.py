import importlib

from django.test import LiveServerTestCase
from django.conf import settings
from django.db import connection
from psycopg2._psycopg import InterfaceError

from selenium.common.exceptions import (WebDriverException,
                                        StaleElementReferenceException)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.firefox.webdriver import WebDriver
from selenium.webdriver.support.wait import WebDriverWait

from treemap.tests import create_mock_system_user, make_commander_user

from treemap.models import Tree, Plot, Instance


def patch_broken_pipe_error():
    """
    Monkey Patch BaseServer.handle_error to not write
    a stacktrace to stderr on broken pipe.
    http://stackoverflow.com/a/21788372/362702
    """
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

# In many tests we close the browser when there are still pending requests,
# such as for map tiles. When running on a dev machine that leads to messy
# output about "broken pipe" errors. Muzzle it.
patch_broken_pipe_error()


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

        # I believe this line is no longer necessary, but I'm leaving it here
        # until the UI tests have run many times without deadlocking.
        # -RM 20140522
        #self.kill_pending_transactions()

        super(UITestCase, self).tearDown()

    def kill_pending_transactions(self):
        # The super.tearDown sometimes hangs when truncating tables
        # because of lingering pending transactions with locks on those tables.
        # Kill them to avoid deadlock!
        try:
            dbname = settings.DATABASES['default']['NAME']
            sql = "select pg_terminate_backend(procpid)" + \
                " from pg_stat_activity where datname='%s'" % dbname + \
                " and current_query='<IDLE> in transaction';"
            connection.cursor().execute(sql)
        except InterfaceError:
            # Sometimes we get "connection already closed"
            pass

    def click(self, selector):
        self.find(selector).click()

    def click_when_visible(self, selector):
        element = self.find(selector)
        self.wait_until_visible(element)
        element.click()

    def find(self, selector):
        return self.driver.find_element_by_css_selector(selector)

    def find_name(self, name):
        return self.driver.find_element_by_name(name)

    def find_id(self, id):
        return self.driver.find_element_by_id(id)

    def process_login_form(self, username, password):
        username_elmt = self.wait_until_present('[name="username"]')
        password_elmt = self.find_name('password')

        username_elmt.send_keys(username)
        password_elmt.send_keys(password)

        self.click('form * button')

    def browse_to_url(self, url):
        self.driver.get(self.live_server_url + url)

    def find_anchor_by_url(self, url):
        return self.find("[href='%s']" % url)

    def wait_until_present(self, selector, timeout=10):
        """
        Wait until an element with CSS 'selector' exists on the page.
        Useful for detecting that an operation loads the page you're expecting.
        """
        element = [None]  # use list so it can be set by inner scope

        def is_present(driver):
            element[0] = self.find(selector)
            return element[0] is not None

        WebDriverWait(self.driver, timeout).until(is_present)
        return element[0]

    def wait_until_text_present(self, text, timeout=10):
        """
        Wait until 'text' exists on the page.
        Useful for detecting that an operation loads the page you're expecting.
        """
        WebDriverWait(self.driver, timeout).until(
            lambda driver: text in driver.page_source)

    def wait_until_enabled(self, element_or_selector, timeout=10):
        """
        Wait until 'element_or_selector' is enabled.
        """
        element = self._get_element(element_or_selector)
        WebDriverWait(self.driver, timeout).until(
            lambda driver: element.get_attribute("disabled") is None)
        return element

    def wait_until_visible(self, element_or_selector, timeout=10):
        """
        Wait until 'element_or_selector' (known to already exist on the page)
        is displayed.
        """
        element = self._get_element(element_or_selector)
        WebDriverWait(self.driver, timeout).until(
            lambda driver: element.is_displayed())
        return element

    def wait_until_invisible(self, element_or_selector, timeout=10):
        """
        Wait until 'element_or_selector' (known to already exist on the page)
        is not displayed.
        """
        element = self._get_element(element_or_selector)

        def is_invisible(driver):
            try:
                return not element.is_displayed()
            except StaleElementReferenceException:
                return True

        WebDriverWait(self.driver, timeout).until(is_invisible)
        return element

    def _get_element(self, element_or_selector):
        if isinstance(element_or_selector, basestring):
            return self.find(element_or_selector)
        else:
            return element_or_selector


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

        # Note: tables are truncated between tests (because LiveServerTestCase
        # inherits from TransactionTestCase, which does the truncation).
        # So there's no need to delete the objects we've created.

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

        self._click_add_tree_next_step(0)

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

    def click_add_tree(self):
        # Enter add tree mode
        self.click(".subhead .addBtn")

    def _click_add_tree_next_step(self, n):
        button = self.driver.find_elements_by_css_selector(
            '#sidebar-add-tree .add-step-footer li.next a')[n]
        self.wait_until_enabled(button)
        button.click()
        sleep(1)  # wait for animation to show the next step

    def start_add_tree(self, x, y):
        self.click_add_tree()
        self.click_point_on_map(x, y)
        self._click_add_tree_next_step(0)

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

    def go_to_feature_detail(self, feature_id, edit=False):
        self.browse_to_url("/autotest-instance/features/%s/%s"
                           % (feature_id,
                              "edit" if edit else ""))

    def go_to_tree_detail(self, plot_id, tree_id):
        self.browse_to_url("/autotest-instance/features/%s/trees/%s/"
                           % (plot_id, tree_id))

    def add_tree_done(self, whenDone='close'):
        # Move to "Finalize" step
        self._click_add_tree_next_step(1)

        if whenDone == 'copy':
            self.click('#addtree-addsame')
        elif whenDone == 'new':
            self.click('#addtree-addnew')
        elif whenDone == 'edit':
            self.click('#addtree-viewdetails')
        elif whenDone == 'close':
            self.click('#addtree-done')

        # Click "Done"
        self._click_add_tree_next_step(2)

        if whenDone == 'close':
            # Wait for "browse trees" mode
            self.wait_until_visible('#sidebar-browse-trees')
        elif whenDone == 'edit':
            # Wait for "save" button on "plot detail" page
            self.wait_until_visible('#save-edit-plot', 30)
        else:
            # Wait for "Add Tree" step 1
            self.wait_until_visible('#sidebar-add-tree .form-search')

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
