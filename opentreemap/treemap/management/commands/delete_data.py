# -*- coding: utf-8 -*-


from treemap.management.util import InstanceDataCommand


class Command(InstanceDataCommand):

    def handle(self, *args, **options):
        """ Delete all map feature data """
        # The superclass handles deleting data if the 'delete' option is true
        options['delete'] = True
        self.setup_env(*args, **options)
