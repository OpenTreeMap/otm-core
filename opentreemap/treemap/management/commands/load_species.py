from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.core.management.base import BaseCommand

from treemap.models import Species

import json


class Command(BaseCommand):
    """
    This command expects the output from an OTM1 species file and
    attempts to insert each record into the database
    """

    def _process_record(self, rec):
        pk = rec['pk']
        fields = rec['fields']

        fields['max_height'] = fields['v_max_height'] or 10000
        del fields['v_max_height']

        fields['max_dbh'] = fields['v_max_dbh'] or 10000
        del fields['v_max_dbh']

        removed_fields = ['alternate_symbol', 'v_multiple_trunks',
                          'tree_count', 'resource', 'itree_code']

        for f in removed_fields:
            del fields[f]

        s = Species(**fields)
        s.pk = pk

        s.save()

    def handle(self, *args, **options):
        if len(args) != 1:
            print("Expecting a json file of OTM1 species")

        for rec in json.loads(open(args[0]).read()):
            self._process_record(rec)
