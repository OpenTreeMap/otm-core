import importlib

from selenium import webdriver
from django.conf import settings


driver = None


def setUpModule():
    global driver

    if driver is None:
        driver = webdriver.Firefox()


def tearDownModule():
    global driver

    if driver is not None:
        driver.quit()


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

#from basic import *  # NOQA
from map import *  # NOQA
