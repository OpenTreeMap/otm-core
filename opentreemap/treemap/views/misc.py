# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import string
import re
import sass

from django.utils.translation import ugettext as trans
from django.core.urlresolvers import reverse
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404

from treemap.models import User, Species, StaticPage, MapFeature, Instance

from treemap.lib.user import get_audits, get_audits_params

from treemap.lib import COLOR_RE


_SCSS_VAR_NAME_RE = re.compile('^[_a-zA-Z][-_a-zA-Z0-9]*$')


def edits(request, instance):
    """
    Request a variety of different audit types.
    Params:
       - models
         Comma separated list of models (only Tree and Plot are supported)
       - model_id
         The ID of a specfici model. If specified, models must also
         be defined and have only one model

       - user
         Filter by a specific user

       - exclude (default: true)
         Set to false to ignore edits that are currently pending

       - page_size
         Size of each page to return (up to PAGE_MAX)
       - page
         The page to return
    """
    (page, page_size, models, model_id,
     exclude_pending) = get_audits_params(request)

    user_id = request.GET.get('user', None)
    user = None

    if user_id is not None:
        user = User.objects.get(pk=user_id)

    return get_audits(request.user, instance, request.REQUEST, user,
                      models, model_id, page, page_size, exclude_pending)


def index(request, instance):
    return HttpResponseRedirect(reverse('map', kwargs={
        'instance_url_name': instance.url_name}))


def get_map_view_context(request, instance):
    resource_classes = [MapFeature.get_subclass(type)
                        for type in instance.map_feature_types]
    return {
        'fields_for_add_tree': [
            (trans('Tree Height'), 'Tree.height')
        ],
        'resource_classes': resource_classes[1:]
    }


def static_page(request, instance, page):
    static_page = StaticPage.get_or_new(instance, page)

    return {'content': static_page.content,
            'title': static_page.name}


def boundary_to_geojson(request, instance, boundary_id):
    boundary = get_object_or_404(instance.boundaries, pk=boundary_id)
    geom = boundary.geom

    # Leaflet prefers to work with lat/lng so we do the transformation
    # here, since it way easier than doing it client-side
    geom.transform('4326')
    return HttpResponse(geom.geojson)


def boundary_autocomplete(request, instance):
    max_items = request.GET.get('max_items', None)

    boundaries = instance.boundaries.order_by('name')[:max_items]

    return [{'name': boundary.name,
             'category': boundary.category,
             'id': boundary.pk,
             'value': boundary.name,
             'tokens': boundary.name.split(),
             'sortOrder': boundary.sort_order}
            for boundary in boundaries]


def species_list(request, instance):
    max_items = request.GET.get('max_items', None)

    species_qs = instance.scope_model(Species)\
                         .order_by('common_name')\
                         .values('common_name', 'genus',
                                 'species', 'cultivar', 'id')

    if max_items:
        species_qs = species_qs[:max_items]

    # Split names by space so that "el" will match common_name="Delaware Elm"
    def tokenize(species):
        names = (species['common_name'],
                 species['genus'],
                 species['species'],
                 species['cultivar'])

        tokens = set()

        for name in names:
            if name:
                tokens = tokens.union(name.split())

        # Names are sometimes in quotes, which should be stripped
        return {token.strip(string.punctuation) for token in tokens}

    def annotate_species_dict(sdict):
        sci_name = Species.get_scientific_name(sdict['genus'],
                                               sdict['species'],
                                               sdict['cultivar'])

        display_name = "%s [%s]" % (sdict['common_name'],
                                    sci_name)

        tokens = tokenize(species)

        sdict.update({
            'scientific_name': sci_name,
            'value': display_name,
            'tokens': tokens})

        return sdict

    return [annotate_species_dict(species) for species in species_qs]


def compile_scss(request):
    """
    Reads key value pairs from the query parameters and adds them as scss
    variables with color values, then imports the main entry point to our scss
    file.

    Any variables provided will be put in the scss file, but only those which
    override variables with '!default' in our normal .scss files should have
    any effect
    """
    # We can probably be a bit looser with what we allow here in the future if
    # we need to, but we must do some checking so that libsass doesn't explode
    scss = ''
    for key, value in request.GET.items():
        if _SCSS_VAR_NAME_RE.match(key) and COLOR_RE.match(value):
            scss += '$%s: #%s;\n' % (key, value)
        else:
            raise ValidationError("Invalid SCSS values %s: %s" % (key, value))
    scss += '@import "%s";' % settings.SCSS_ENTRY
    scss = scss.encode('utf-8')

    return sass.compile(string=scss, include_paths=[settings.SCSS_ROOT])


def public_instances_geojson(request):
    def instance_geojson(instance):
        return {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [instance.center_lat_lng.x,
                                instance.center_lat_lng.y]
            },
            'properties': {
                'name': instance.name,
                'url': reverse(
                    'instance_index_view',
                    kwargs={'instance_url_name': instance.url_name}),
                'tree_count': instance.tree_count,
                'plot_count': instance.plot_count
            }
        }

    tree_query = "SELECT COUNT(*) FROM treemap_tree WHERE "\
        "treemap_tree.instance_id = treemap_instance.id"

    plot_query = "SELECT COUNT(*) FROM treemap_mapfeature"\
        " WHERE treemap_mapfeature.instance_id = treemap_instance.id"\
        " AND treemap_mapfeature.feature_type = 'Plot'"

    # You might think you can do .annotate(tree_count=Count('tree'))
    # But it is horribly slow due to too many group bys
    instances = (Instance.objects
                 .filter(is_public=True)
                 .extra(select={
                     'tree_count': tree_query,
                     'plot_count': plot_query
                 }))

    return [instance_geojson(instance) for instance in instances]
