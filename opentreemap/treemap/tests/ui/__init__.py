# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import importlib
from time import sleep

from django.test.utils import override_settings
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from registration.models import RegistrationProfile

from selenium.common.exceptions import (WebDriverException,
                                        StaleElementReferenceException)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.firefox.webdriver import WebDriver
from selenium.webdriver.support.wait import WebDriverWait

from treemap.tests import make_commander_user, create_mock_system_user
from treemap.tests.base import test_settings
from treemap.models import Instance, Tree, Plot
from treemap.lib.object_caches import clear_caches
from treemap.plugin import setup_for_ui_test
from treemap.instance import create_stewardship_udfs


DISPLAY_WIDTH = 1280
DISPLAY_HEIGHT = 1024


class UITestCase(StaticLiveServerTestCase):
    def use_xvfb(self):
        from pyvirtualdisplay import Display
        self.display = Display('xvfb',
                               visible=1,
                               size=(DISPLAY_WIDTH, DISPLAY_HEIGHT))
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

        self.driver.set_window_size(DISPLAY_WIDTH, DISPLAY_HEIGHT)

        self.driver.implicitly_wait(10)

        clear_caches()
        setup_for_ui_test()

        super(UITestCase, self).setUp()

    def tearDown(self):
        self.driver.quit()
        if hasattr(self, 'display'):
            self.display.stop()

        ContentType.objects.clear_cache()

        super(UITestCase, self).tearDown()

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

    def is_visible(self, selector):
        element = self.find(selector)
        return element is not None and element.is_displayed()

    def process_login_form(self, username, password):
        username_elmt = self.wait_until_present('[name="username"]')
        password_elmt = self.find_name('password')

        username_elmt.send_keys(username)
        password_elmt.send_keys(password)

        self.click('form * button')

    def browse_to_url(self, url):
        self.driver.get(self.live_server_url + url)

    def browse_to_instance_url(self, url, instance=None):
        instance = instance if instance is not None else self.instance
        self.driver.get('%s/%s/%s' % (self.live_server_url,
                                      instance.url_name,
                                      url))

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
            return element[0] is not None and element[0].is_displayed()

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

    def wait_for_input_value(self, element_or_selector, value, timeout=10):
        """
        Wait until 'element_or_selector' input has the specified value
        """
        element = self._get_element(element_or_selector)
        WebDriverWait(self.driver, timeout).until(
            # It seems wrong, but selenium fetches the value of an input
            # element using get_attribute('value')
            lambda driver: element.get_attribute('value') == value)
        return element

    def _get_element(self, element_or_selector):
        if isinstance(element_or_selector, basestring):
            return self.find(element_or_selector)
        else:
            return element_or_selector


@override_settings(**test_settings)
class TreemapUITestCase(UITestCase):
    def assertElementVisibility(self, element, visible):
        if isinstance(element, basestring):
            element = self.find_id(element)
        wait = (self.wait_until_visible if visible
                else self.wait_until_invisible)
        wait(element)
        self.assertEqual(visible, element.is_displayed())

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
            url_name='autotest-instance',
            edge_length=20000)
        create_stewardship_udfs(self.instance)

        self.user = make_commander_user(instance=self.instance,
                                        username='username')

        self.profile = RegistrationProfile.objects.create_profile(self.user)

    def login_workflow(self, user=None):
        if user is None:
            user = self.user
        self.browse_to_url('/accounts/logout/')
        self.browse_to_url('/accounts/login/')
        self.process_login_form(user.username, 'password')

        def url_is_user_page(driver):
            return driver.current_url.endswith('/users/%s/' % user.username)

        WebDriverWait(self.driver, 10).until(url_is_user_page)

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
        self.click('.subhead [data-feature="add_plot"]')

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
        self.browse_to_instance_url("map/")

    def go_to_feature_detail(self, feature_id, edit=False):
        self.browse_to_instance_url("features/%s/%s"
                                    % (feature_id,
                                       "edit" if edit else ""))

    def go_to_tree_detail(self, plot_id, tree_id):
        self.browse_to_instance_url("features/%s/trees/%s/"
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
            self.wait_until_visible('#save-edit-map-feature', 30)
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
