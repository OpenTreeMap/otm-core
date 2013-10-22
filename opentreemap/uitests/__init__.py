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


def _get_create_instance():
    create_instance_fn_str = settings.UITEST_CREATE_INSTANCE_FUNCTION
    parts = create_instance_fn_str.split('.')
    create_instance_mod = '.'.join(parts[0:-1])
    create_instance_fn = parts[-1]

    create_instance = getattr(
        importlib.import_module(create_instance_mod),
        create_instance_fn)

    return create_instance

create_instance = _get_create_instance()

from basic import *  # NOQA
