from selenium import webdriver

driver = None


def setUpModule():
    global driver

    if driver is None:
        driver = webdriver.Firefox()


def tearDownModule():
    global driver

    if driver is not None:
        driver.quit()


from basic import *  # NOQA
