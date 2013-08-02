from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import urllib
from PIL import Image

from django.shortcuts import get_object_or_404
from django.http import (HttpResponse, HttpResponseServerError,
                         HttpResponseRedirect)
from django.views.decorators.http import etag
from django.conf import settings
from django.contrib.gis.geos.point import Point
from django.utils.translation import ugettext as _

from treemap.util import json_api_call, render_template, instance_request
from treemap.search import create_filter
from treemap.audit import Audit, AuditUI
from treemap.models import Plot, Tree, User, Boundary, Species

from ecobenefits.views import _benefits_for_trees


def _plot_hash(request, instance, plot_id):
    return instance.scope_model(Plot).get(pk=plot_id).hash


#
# These are calls made by the API that aren't currently implemented
# as we make these features, please use these functions to share the
# love with mobile
#
def add_tree_photo(user_id, plot_id, uploaded_image):
    class TPShim(object):

        def __init__(self):
            self.pk = 2
            self.title = 'shim'

    return TPShim()


def _rotate_image_based_on_exif(img_path):
    img = Image.open(img_path)
    try:
        orientation = img._getexif()[0x0112]
        if orientation == 6:  # Right turn
            img = img.rotate(-90)
        elif orientation == 5:  # Left turn
            img = img.rotate(90)
    except:
        pass

    return img


def get_tree_photos(plot_id, photo_id):
    return None


def add_user_photo(user_id, uploaded_image):
    return None


def create_user(*args, **kwargs):
    # Clearly this is just getting the api working
    # it shouldn't stay here when real user stuff happens
    from treemap.tests import make_system_user

    user = User(username=kwargs['username'], email=kwargs['email'])
    user.set_password(kwargs['password'])
    user.save_with_user(make_system_user())

    return user


def create_plot(user, instance, *args, **kwargs):
    if 'x' in kwargs and 'y' in kwargs:
        geom = Point(
            kwargs['x'],
            kwargs['y'])
    elif 'lon' in kwargs and 'lat' in kwargs:
        geom = Point(
            kwargs['lon'],
            kwargs['lat'])
    else:
        geom = Point(50, 50)

    p = Plot(geom=geom, instance=instance)
    p.save_with_user(user)

    if 'height' in kwargs:
        t = Tree(plot=p, instance=instance)
        t.height = kwargs['height']

        if t.height > 1000:
            return ["Height is too large."]

        t.save_with_user(user)
    return p


def plot_detail(request, instance, plot_id):
    InstancePlot = instance.scope_model(Plot)
    plot = get_object_or_404(InstancePlot, pk=plot_id)

    return {'plot': plot}


def audits(request, instance):
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

       - include_pending (default: true)
         Set to false to ignore edits that are currently pending

       - page_size
         Size of each page to return (up to PAGE_MAX)
       - page
         The page to return
    """

    PAGE_MAX = 100
    PAGE_DEFAULT = 20

    r = request.REQUEST

    page_size = min(int(r.get('page_size', PAGE_DEFAULT)), PAGE_MAX)
    page = int(r.get('page', 0))

    start_pos = page * page_size
    end_pos = start_pos + page_size

    models = []

    allowed_models = {
        'tree': 'Tree',
        'plot': 'Plot'
    }

    for model in r.get('models', "tree,plot").split(','):
        if model.lower() in allowed_models:
            models.append(allowed_models[model.lower()])
        else:
            raise Exception("Invalid model: %s" % model)

    model_id = r.get('model_id', None)

    if model_id is not None and len(models) != 1:
        raise Exception("You must specific one and only model "
                        "when looking up by id")

    user_id = r.get('user', None)
    user = None

    if user_id is not None:
        user = User.objects.get(pk=user_id)

    audits = Audit.objects.filter(instance=instance)\
                          .filter(model__in=models)\
                          .order_by('-created', 'id')

    if user_id:
        audits = audits.filter(user=user)

    if model_id:
        audits = audits.filter(model_id=model_id)

    if r.get('include_pending', "true") == "false":
        audits = audits.exclude(requires_auth=True, ref_id__isnull=True)

    audits = [AuditUI(a) for a in audits[start_pos:end_pos]]

    query_vars = {k: v for (k, v) in request.GET.iteritems() if k != 'page'}

    next_page = None
    prev_page = None

    if len(audits) == page_size:
        query_vars['page'] = page + 1
        next_page = "?" + urllib.urlencode(query_vars)

    if page > 0:
        query_vars['page'] = page - 1
        prev_page = "?" + urllib.urlencode(query_vars)

    return {'audits': audits,
            'next_page': next_page,
            'prev_page': prev_page}


def boundary_to_geojson(request, boundary_id):
    boundary = Boundary.objects.get(pk=boundary_id)
    return HttpResponse(boundary.geom.geojson)


def boundary_autocomplete(request, instance):
    max_items = request.GET.get('max_items', None)

    boundaries = instance.boundaries.order_by('name')[:max_items]

    return [{'name': boundary.name,
             'category': boundary.category,
             'id': boundary.pk,
             'value': boundary.name,
             'tokens': boundary.name.split()}
            for boundary in boundaries]


def species_list(request, instance):
    max_items = request.GET.get('max_items', None)

    species_set = Species.objects.order_by('common_name')[:max_items]

    # Split names by space so that "el" will match common_name="Delaware Elm"
    tokenize = lambda s: [token for name in
                          (s.common_name, s.genus, s.species, s.cultivar_name)
                          for token in (name.split() if name else [])]

    return [{'common_name': species.common_name,
             'id': species.pk,
             'scientific_name': species.scientific_name,
             'value': species.display_name,
             'tokens': tokenize(species)}
            for species in species_set]


def _execute_filter(instance, filter_str):
    return create_filter(filter_str).filter(instance=instance)


def search_tree_benefits(request, instance, region='PiedmtCLT'):
    try:
        filter_str = request.REQUEST['q']
    except KeyError:
        return HttpResponseServerError("Please supply a 'filter' parameter")

    plots = _execute_filter(instance, filter_str)
    trees = Tree.objects.filter(plot_id__in=plots)

    total_plots = plots.count()
    total_trees = trees.count()

    trees_for_eco = trees.exclude(species__itree_code__isnull=True)\
                         .exclude(diameter__isnull=True)\
                         .values('diameter', 'species__itree_code')

    benefits, num_calculated_trees = _benefits_for_trees(trees_for_eco, region)

    percent = 0
    if num_calculated_trees > 0 and total_trees > 0:
        # Extrapolate an average over the rest of the urban forest
        percent = float(num_calculated_trees) / total_trees
        for key in benefits:
            benefits[key]['value'] /= percent

    def displayize_benefit(key, label, format):
        benefit = benefits[key]
        benefit['label'] = label
        benefit['value'] = format % benefit['value']
        return benefit

    # TODO: i18n of labels
    # TODO: get units from locale, and convert value
    # TODO: how many decimal places do we really want? Is it unit-sensitive?
    benefits_for_display = [
        # Translators: 'Energy' is the name of an eco benefit
        displayize_benefit('energy', _('Energy'), '%.1f'),
        # Translators: 'Stormwater' is the name of an eco benefit
        displayize_benefit('stormwater', _('Stormwater'), '%.1f'),
        # Translators: 'Carbon Dioxide' is the name of an eco benefit
        displayize_benefit('co2', _('Carbon Dioxide'), '%.1f'),
        # Translators: 'Air Quaility' is the name of an eco benefit
        displayize_benefit('airquality', _('Air Quality'), '%.1f')
    ]

    rslt = {'benefits': benefits_for_display,
            'basis': {'n_trees_used': num_calculated_trees,
                      'n_trees_total': total_trees,
                      'n_plots': total_plots,
                      'percent': percent}}

    return rslt


def user(request, username):
    context = get_object_or_404(User, username=username).__dict__
    context['instance_id'] = request.GET.get('instance_id', None)
    return context


def instance_user_view(request, instance_id, username):
    url = '/users/%(username)s/?instance_id=%(instance_id)s' %\
        {'username': username, 'instance_id': instance_id}
    return HttpResponseRedirect(url)


def profile_to_user_view(request):
    if request.user and request.user.username:
        return HttpResponseRedirect('/users/%s/' % request.user.username)
    else:
        return HttpResponseRedirect(settings.LOGIN_URL)

audits_view = instance_request(
    render_template('treemap/recent_edits.html', audits))

index_view = instance_request(render_template('treemap/index.html'))
trees_view = instance_request(
    render_template('treemap/map.html',
                    {'bounds': Boundary.objects.all(),
                     'species': Species.objects.all()}))

plot_detail_view = instance_request(etag(_plot_hash)(
    render_template('treemap/plot_detail.html', plot_detail)))

plot_popup_view = instance_request(etag(_plot_hash)(
    render_template('treemap/plot_popup.html', plot_detail)))

root_settings_js_view = render_template('treemap/settings.js',
                                        {'BING_API_KEY':
                                         settings.BING_API_KEY},
                                        mimetype='application/javascript')

instance_settings_js_view = instance_request(
    render_template('treemap/settings.js',
                    {'BING_API_KEY': settings.BING_API_KEY},
                    mimetype='application/javascript'))


boundary_to_geojson_view = json_api_call(boundary_to_geojson)
boundary_autocomplete_view = instance_request(
    json_api_call(boundary_autocomplete))

search_tree_benefits_view = instance_request(
    render_template('treemap/eco_benefits.html', search_tree_benefits))

species_list_view = json_api_call(instance_request(species_list))

user_view = render_template("treemap/user.html", user)
