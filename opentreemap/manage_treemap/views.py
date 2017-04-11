from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.shortcuts import redirect


def management_root(request, instance_url_name):
    return redirect('site_config', instance_url_name=instance_url_name)
