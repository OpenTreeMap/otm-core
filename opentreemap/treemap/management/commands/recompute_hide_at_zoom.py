from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count

from treemap.instance import Instance
from treemap.lib.hide_at_zoom import recompute_hide_at_zoom
from treemap.models import MapFeature

MIN_FEATURE_COUNT = 100


class Command(BaseCommand):
    args = '<[instance_url_name]>'
    help = 'Recomputes hide_at_zoom for all instances or specified instance'

    def handle(self, *args, **options):
        if len(args) > 1:
            raise CommandError('Command takes 0 or 1 argument')

        elif len(args) == 0:
            _update_all_instances()

        else:
            url_name = args[0]
            try:
                instance = Instance.objects.get(url_name=url_name)
            except ObjectDoesNotExist:
                raise CommandError('Instance "%s" not found' % url_name)

            recompute_hide_at_zoom(instance, verbose=True)


def _update_all_instances():
    instance_ids = MapFeature.objects \
        .values('instance_id') \
        .annotate(n=Count('instance_id')) \
        .filter(n__gt=MIN_FEATURE_COUNT) \
        .values_list('instance_id', flat=True)

    for id in instance_ids:
        instance = Instance.objects.get(id=id)
        recompute_hide_at_zoom(instance, verbose=True)
