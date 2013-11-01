from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import unittest
import sys
import importlib

from optparse import make_option

from django.core.management.base import BaseCommand
from django.conf import settings

from pyvirtualdisplay import Display


class Command(BaseCommand):
    """
    Uses a custom test runner to run UI acceptance tests
    from the 'tests' package
    """
    option_list = BaseCommand.option_list + (
        make_option('-s', '--skip-debug-check',
                    action='store_true',
                    dest='skip_debug',
                    help='skip the debug'),
        make_option('-x', '--use-x',
                    action='store_true',
                    dest='use_x',
                    help='use X windows rather '
                         'than a virtual distplay'), )

    def handle(self, *args, **options):
        if settings.DEBUG is False and not options['skip_debug']:
            raise Exception('These tests add data to the currently '
                            'select database backend. If this is a '
                            'production database a failing test could '
                            'leave extra data behind (such as users) or '
                            'delete data that already exists.')

        if not options['use_x']:
            disp = Display(visible=0, size=(800, 600))
            disp.start()

        errors = False
        for module in settings.UITESTS:
            uitests = importlib.import_module(module)
            suite = unittest.TestLoader().loadTestsFromModule(uitests)

            try:
                if hasattr(uitests, 'setUpModule'):
                    uitests.setUpModule()

                rslt = unittest.TextTestRunner(verbosity=2).run(suite)
            finally:
                if hasattr(uitests, 'tearDownModule'):
                    uitests.tearDownModule()
                if not options['use_x']:
                    disp.stop()

            if not rslt.wasSuccessful():
                errors = True

        if errors:
            sys.exit(1)
