from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import string
import re
import urllib
import json
import locale
import hashlib

from PIL import Image
import sass

from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.http import (HttpResponse, HttpResponseRedirect,
                         HttpResponseForbidden, Http404)
from django.views.decorators.http import etag
from django.conf import settings
from django.contrib.gis.geos.point import Point
from django.utils.translation import ugettext as trans
from django.db import transaction
from django.db.models import Q

from treemap.util import (json_api_call, render_template, instance_request,
                          require_http_method, package_validation_errors,
                          bad_request_json_response, string_as_file_call)
from treemap.search import create_filter
from treemap.audit import Audit
from treemap.models import (Plot, Tree, User, Species, Instance,
                            BenefitCurrencyConversion)

from ecobenefits.models import ITreeRegion
from ecobenefits.views import _benefits_for_trees

from opentreemap.util import json_from_request


def _plot_hash(request, instance, plot_id, tree_id=None):
    """
    Compute a unique hash for a given plot or tree

    tree_id is ignored since trees are included as a
    subset of the plot's hash. It is present here because
    this function is wrapped around views that can take
    tree_id as an argument
    """
    instance_plots = instance.scope_model(Plot)
    return get_object_or_404(instance_plots, pk=plot_id).hash


def _search_hash(request, instance):
    audits = instance.scope_model(Audit)\
                     .order_by('-updated')

    try:
        audit_id_str = str(audits[0].pk)
    except IndexError:
        audit_id_str = 'none'

    eco_conversion = instance.eco_benefits_conversion

    if eco_conversion:
        eco_str = eco_conversion.hash
    else:
        eco_str = 'none'

    string_to_hash = audit_id_str + ":" + eco_str

    return hashlib.md5(string_to_hash).hexdigest()


def add_tree_photo(request, instance, plot_id, tree_id=None):
    plot = get_object_or_404(Plot, pk=plot_id, instance=instance)
    tree_ids = [t.pk for t in plot.tree_set.all()]

    if tree_id and int(tree_id) in tree_ids:
        tree = Tree.objects.get(pk=tree_id)
    elif tree_id is None:
        # See if a tree already exists on this plot
        tree = plot.current_tree()

        if tree is None:
            # A tree doesn't exist, create a new tree create a
            # new tree, and attach it to this plot
            tree = Tree(plot=plot, instance=instance)

            # TODO: it is possible that a user has the ability to
            # 'create tree photos' but not trees. In this case we
            # raise an authorization exception here.
            # It is, however, possible to have both a pending
            # tree and a pending tree photo
            # This will be added later, when auth/admin work
            # correctly with this system
            tree.save_with_user(request.user)

    else:
        # Tree id is invalid or not in this plot
        raise Http404('Tree id %s not found on plot %s' % (tree_id, plot_id))

    #TODO: Validation Error
    #TODO: Auth Error
    if 'file' in request.FILES:
        #TODO: Check size before reading
        data = request.FILES['file'].file
    else:
        data = request.body

    photo = tree.add_photo(data, request.user)

    return photo


def add_tree_photo_view(request, instance, plot_id, tree_id=None):
    errors = ''

    try:
        add_tree_photo(request, instance, plot_id, tree_id)
    except ValidationError as e:
        errors = '?errors=%s' % urllib.quote(json.dumps(e.message_dict))

    url = reverse('plot_detail',
                  kwargs={
                      'instance_url_name': instance.url_name,
                      'plot_id': plot_id})

    url += errors

    return HttpResponseRedirect(url)

#
# These are calls made by the API that aren't currently implemented
# as we make these features, please use these functions to share the
# love with mobile
#


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
    user = User(username=kwargs['username'], email=kwargs['email'])
    user.set_password(kwargs['password'])
    user.save()

    return user


def create_plot(user, instance, *args, **kwargs):
    if 'height' in kwargs and kwargs['height'] > 1000:
        return ["Height is too large."]

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
        t.save_with_user(user)
    return p


def plot_detail(request, instance, plot_id, tree_id=None):
    InstancePlot = instance.scope_model(Plot)
    plot = get_object_or_404(InstancePlot, pk=plot_id)

    if tree_id:
        tree = get_object_or_404(Tree,
                                 instance=instance,
                                 plot=plot,
                                 pk=tree_id)
    else:
        tree = plot.current_tree()

    context = {}
    # If the the benefits calculation can't be done or fails, still display the
    # plot details

    has_tree_diameter = tree is not None and tree.diameter is not None
    has_tree_species_with_code = tree is not None \
        and tree.species is not None and tree.species.itree_code is not None

    if has_tree_diameter and has_tree_species_with_code:
        try:
            eco_tree = {'species__itree_code': tree.species.itree_code,
                        'diameter': tree.diameter,
                        'itree_region_code': ITreeRegion.objects.get(
                            geometry__contains=plot.geom).code}
            context = _tree_benefits_helper([eco_tree], 1, 1, instance)
        except Exception:
            pass

    if 'errors' in request.REQUEST:
        context['errors'] = json.loads(request.REQUEST['errors'])

    context['plot'] = plot
    context['tree'] = tree
    context['recent_activity'] = _plot_audits(request.user, instance, plot)

    return context


def add_plot(request, instance):
    return update_plot_and_tree_request(request, Plot(instance=instance))


def update_plot_detail(request, instance, plot_id):
    InstancePlot = instance.scope_model(Plot)
    plot = get_object_or_404(InstancePlot, pk=plot_id)
    return update_plot_and_tree_request(request, plot)


def update_plot_and_tree_request(request, plot):
    try:
        plot = update_plot_and_tree(request, plot)
        # Refresh plot.instance in case geo_rev_hash was updated
        plot.instance = Instance.objects.get(id=plot.instance.id)
        return {
            'ok': True,
            'geoRevHash': plot.instance.geo_rev_hash,
            'plotId': plot.id
        }
    except ValidationError as ve:
        return bad_request_json_response(
            validation_error_dict=ve.message_dict)


@transaction.commit_on_success
def update_plot_and_tree(request, plot):
    """
    Update a plot. Expects JSON in the request body to be:
    {'model.field', ...}

    Where model is either 'tree' or 'plot' and field is any field
    on the model. UDF fields should be prefixed with 'udf:'.

    This method can be used to create a new plot by passing in
    an empty plot object (i.e. Plot(instance=instance))
    """
    def split_model_or_raise(model_and_field):
        model_and_field = model_and_field.split('.', 1)

        if ((len(model_and_field) != 2 or
             model_and_field[0] not in ['plot', 'tree'])):
            raise Exception(
                'Malformed request - invalid field %s' % model_and_field)
        else:
            return model_and_field

    def set_attr_on_model(model, attr, val):
        if attr == 'geom':
            val = Point(val['x'], val['y'])

        if attr in model.fields() and attr != 'id':
            model.apply_change(attr, val)
        elif attr.startswith('udf:'):
            udf_name = attr[4:]

            if udf_name in [field.name
                            for field
                            in model.get_user_defined_fields()]:
                model.udfs[udf_name] = val
            else:
                raise KeyError('Invalid UDF %s' % attr)
        else:
            raise Exception('Maformed request - invalid field %s' % attr)

    def save_and_return_errors(thing, user):
        try:
            thing.save_with_user(user)
            return {}
        except ValidationError as e:
            return package_validation_errors(thing._model_name, e)

    def get_tree():
        return plot.current_tree() or Tree(instance=plot.instance)

    tree = None

    request_dict = json.loads(request.body)

    for (model_and_field, value) in request_dict.iteritems():
        model, field = split_model_or_raise(model_and_field)

        if model == 'plot':
            model = plot
        elif model == 'tree':
            # Get the tree or spawn a new one if needed
            tree = tree or get_tree()
            model = tree
            if field == 'species' and value:
                value = Species.objects.get(pk=value)
        else:
            raise Exception('Malformed request - invalid model %s' % model)

        set_attr_on_model(model, field, value)

    errors = {}

    if plot.fields_were_updated():
        errors.update(save_and_return_errors(plot, request.user))
    if tree and tree.fields_were_updated():
        tree.plot = plot
        errors.update(save_and_return_errors(tree, request.user))

    if errors:
        raise ValidationError(errors)

    return plot


def _get_audits(logged_in_user, instance, query_vars, user, models,
                model_id, page=0, page_size=20, exclude_pending=True):
    start_pos = page * page_size
    end_pos = start_pos + page_size

    model_filter = Q(model__in=models)

    # We only want to show the TreePhoto's image, not other fields
    # and we want to do it automatically if 'Tree' was specified as
    # a model
    if 'Tree' in models:
        model_filter = model_filter | Q(model='TreePhoto', field='image')

    audits = Audit.objects.filter(model_filter)\
                          .order_by('-created', 'id')

    if instance:
        if instance.is_accessible_by(logged_in_user):
            audits = audits.filter(instance=instance)
        else:
            # Force no results
            audits = Audit.objects.none()
    # If we didn't specify an instance we only want to
    # show audits where the user has permission
    else:
        public = Q(instance__is_public=True)

        if logged_in_user is not None and not logged_in_user.is_anonymous():
            private_with_access = Q(instance__instanceuser__user=
                                    logged_in_user)

            audit_instance_filter = public | private_with_access
        else:
            audit_instance_filter = public

        audits = audits.filter(audit_instance_filter)

    if user:
        audits = audits.filter(user=user)
    if model_id:
        audits = audits.filter(model_id=model_id)
    if exclude_pending:
        audits = audits.exclude(requires_auth=True, ref__isnull=True)

    audits = audits[start_pos:end_pos]

    query_vars = {k: v for (k, v) in query_vars.iteritems() if k != 'page'}
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


def _get_audits_params(request):
    PAGE_MAX = 100
    PAGE_DEFAULT = 20

    r = request.REQUEST

    page_size = min(int(r.get('page_size', PAGE_DEFAULT)), PAGE_MAX)
    page = int(r.get('page', 0))

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

    exclude_pending = r.get('exclude_pending', "false") == "true"

    return (page, page_size, models, model_id, exclude_pending)


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

       - exclude (default: true)
         Set to false to ignore edits that are currently pending

       - page_size
         Size of each page to return (up to PAGE_MAX)
       - page
         The page to return
    """
    (page, page_size, models, model_id,
     exclude_pending) = _get_audits_params(request)

    user_id = request.GET.get('user', None)
    user = None

    if user_id is not None:
        user = User.objects.get(pk=user_id)

    return _get_audits(request.user, instance, request.REQUEST, user,
                       models, model_id, page, page_size, exclude_pending)


def _plot_audits(user, instance, plot):
    readable_plot_fields = plot.visible_fields(user)

    plot_filter = Q(model='Plot', field__in=readable_plot_fields)

    tree_visible_fields = Tree(instance=instance)\
        .visible_fields(user)

    # Get a history of trees that were on this plot
    tree_history = plot.get_tree_history()

    tree_filter = Q(model='Tree',
                    field__in=tree_visible_fields,
                    model_id__in=tree_history)

    audits = Audit.objects.filter(instance=instance)\
                          .filter(tree_filter | plot_filter)\
                          .order_by('-updated')[:5]

    return audits


def user_audits(request, username):
    user = get_object_or_404(User, username=username)
    instance_id = request.GET.get('instance_id', None)

    instance = (get_object_or_404(Instance, pk=instance_id)
                if instance_id else None)

    (page, page_size, models, model_id,
     exclude_pending) = _get_audits_params(request)

    return _get_audits(request.user, instance, request.REQUEST, user,
                       models, model_id, page, page_size, exclude_pending)


def instance_user_audits(request, instance_url_name, username):
    instance = get_object_or_404(Instance, url_name=instance_url_name)
    return HttpResponseRedirect('/users/%s/recent_edits?instance_id=%s'
                                % (username, instance.pk))


def boundary_to_geojson(request, instance, boundary_id):
    boundary = get_object_or_404(instance.boundaries, pk=boundary_id)
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
    def tokenize(species):
        names = (species.common_name, species.genus,
                 species.species, species.cultivar)

        tokens = []

        for name in names:
            if name:
                tokens.extend(name.split())

        # Names are sometimes in quotes, which should be stripped
        return [token.strip(string.punctuation) for token in tokens]

    return [{'common_name': species.common_name,
             'id': species.pk,
             'scientific_name': species.scientific_name,
             'value': species.display_name,
             'tokens': tokenize(species)}
            for species in species_set]


def _execute_filter(instance, filter_str):
    return create_filter(filter_str).filter(instance=instance)


def search_tree_benefits(request, instance):
    # locale.format does not insert grouping chars unless
    # the locale is set
    locale.setlocale(locale.LC_ALL, '')

    try:
        filter_str = request.REQUEST['q']
    except KeyError:
        filter_str = ''

    plots = _execute_filter(instance, filter_str)
    trees = Tree.objects.filter(plot_id__in=plots)

    total_plots = plots.count()
    total_trees = trees.count()

    trees_for_eco = trees.exclude(species__itree_code__isnull=True)\
                         .exclude(diameter__isnull=True)\
                         .extra(select={'itree_region_code':
                                        'ecobenefits_itreeregion.code'},
                                where=['ST_Contains('
                                       'ecobenefits_itreeregion.geometry, '
                                       'treemap_plot.the_geom_webmercator)'],
                                tables=['ecobenefits_itreeregion'])\
                         .values('diameter',
                                 'species__itree_code',
                                 'itree_region_code',
                                 'plot__geom')

    return _tree_benefits_helper(trees_for_eco, total_plots, total_trees,
                                 instance)


def _tree_benefits_helper(trees_for_eco, total_plots, total_trees, instance):
    benefits, num_calculated_trees = _benefits_for_trees(trees_for_eco)

    percent = 0
    if num_calculated_trees > 0 and total_trees > 0:
        # Extrapolate an average over the rest of the urban forest
        percent = float(num_calculated_trees) / total_trees
        for key in benefits:
            benefits[key]['value'] /= percent

    def displayize_benefit(key, currency_factor, label, format):
        benefit = benefits[key]
        if currency_factor:
            benefit['currency_saved'] = locale.format(
                '%d', benefit['value'] * currency_factor, grouping=True)

        benefit['label'] = label
        benefit['value'] = locale.format(format, benefit['value'],
                                         grouping=True)

        return benefit

    conversion = instance.eco_benefits_conversion
    if conversion is None:
        conversion = BenefitCurrencyConversion()

    # TODO: i18n of labels
    # TODO: get units from locale, and convert value
    # TODO: how many decimal places do we really want? Is it unit-sensitive?
    benefits_for_display = [
        # Translators: 'Energy' is the name of an eco benefit
        displayize_benefit(
            'energy',
            conversion.kwh_to_currency,
            trans('Energy'), '%.1f'),

        # Translators: 'Stormwater' is the name of an eco benefit
        displayize_benefit(
            'stormwater',
            conversion.stormwater_gal_to_currency,
            trans('Stormwater'), '%.1f'),

        # Translators: 'Carbon Dioxide' is the name of an eco benefit
        displayize_benefit(
            'co2',
            conversion.carbon_dioxide_lb_to_currency,
            trans('Carbon Dioxide'), '%.1f'),

        # Translators: 'Air Quaility' is the name of an eco benefit
        displayize_benefit(
            'airquality',
            conversion.airquality_aggregate_lb_to_currency,
            trans('Air Quality'), '%.1f')
    ]

    rslt = {'benefits': benefits_for_display,
            'currency_symbol': conversion.currency_symbol,
            'basis': {'n_trees_used': num_calculated_trees,
                      'n_trees_total': total_trees,
                      'n_plots': total_plots,
                      'percent': percent}}

    return rslt


def user(request, username):
    user = get_object_or_404(User, username=username)
    instance_id = request.GET.get('instance_id', None)

    instance = (get_object_or_404(Instance, pk=instance_id)
                if instance_id else None)

    query_vars = {'instance_id': instance_id} if instance_id else {}

    audit_dict = _get_audits(request.user, instance, query_vars,
                             user, ['Plot', 'Tree'], 0)

    reputation = user.get_reputation(instance) if instance else None

    public_fields = [
        (trans('First Name'), 'user.first_name'),
        (trans('Last Name'), 'user.last_name')
    ]

    private_fields = [
        (trans('Email'), 'user.email')
    ]

    return {'user': user,
            'reputation': reputation,
            'instance_id': instance_id,
            'audits': audit_dict['audits'],
            'next_page': audit_dict['next_page'],
            'public_fields': public_fields,
            'private_fields': private_fields}


def update_user(request, username):
    user = get_object_or_404(User, username=username)
    if user != request.user:
        return HttpResponseForbidden()

    new_values = json_from_request(request) or {}
    for key in new_values:
        try:
            model, field = key.split('.', 1)
            if model != 'user':
                return bad_request_json_response(
                    'All fields should be prefixed with "user."')
            if field not in ['first_name', 'last_name', 'email']:
                return bad_request_json_response(
                    field + ' is not an updatable field')
        except ValueError:
            return bad_request_json_response(
                'All fields should be prefixed with "user."')
        setattr(user, field, new_values[key])
    try:
        user.save()
        return {"ok": True}
    except ValidationError, ve:
        return bad_request_json_response(
            validation_error_dict=package_validation_errors('user', ve))


def _get_map_view_context(request, instance_id):
    fields_for_add_tree = [
        (trans('Trunk Diameter (inches)'), 'tree.diameter'),
        (trans('Tree Height (feet)'), 'tree.height')
    ]
    return {'fields_for_add_tree': fields_for_add_tree}


def instance_user_view(request, instance_url_name, username):
    instance = get_object_or_404(Instance, url_name=instance_url_name)
    url = '/users/%(username)s?instance_id=%(instance_id)s' %\
        {'username': username, 'instance_id': instance.pk}
    return HttpResponseRedirect(url)


def profile_to_user_view(request):
    if request.user and request.user.username:
        return HttpResponseRedirect('/users/%s/' % request.user.username)
    else:
        return HttpResponseRedirect(settings.LOGIN_URL)


_scss_var_name_re = re.compile('^[_a-zA-Z][-_a-zA-Z0-9]*$')
_color_re = re.compile(r'^(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')


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
        if _scss_var_name_re.match(key) and _color_re.match(value):
            scss += '$%s: #%s;\n' % (key, value)
        else:
            raise ValidationError("Invalid SCSS values %s: %s" % (key, value))
    scss += '@import "%s";' % settings.SCSS_ENTRY
    scss = scss.encode('utf-8')

    return sass.compile(string=scss, include_paths=[settings.SCSS_ROOT])


audits_view = instance_request(
    render_template('treemap/recent_edits.html', audits))

index_view = instance_request(render_template('treemap/index.html'))

map_view = instance_request(
    render_template('treemap/map.html', _get_map_view_context))

get_plot_detail_view = instance_request(etag(_plot_hash)(
    render_template('treemap/plot_detail.html', plot_detail)))

update_plot_detail_view = json_api_call(instance_request(update_plot_detail))

plot_popup_view = instance_request(etag(_plot_hash)(
    render_template('treemap/plot_popup.html', plot_detail)))

plot_accordion_view = instance_request(etag(_plot_hash)(
    render_template('treemap/plot_accordion.html', plot_detail)))

add_plot_view = require_http_method("POST")(
    json_api_call(instance_request(add_plot)))

root_settings_js_view = render_template('treemap/settings.js',
                                        {'BING_API_KEY':
                                         settings.BING_API_KEY},
                                        mimetype='application/javascript')

instance_settings_js_view = instance_request(
    render_template('treemap/settings.js',
                    {'BING_API_KEY': settings.BING_API_KEY},
                    mimetype='application/javascript'))

boundary_to_geojson_view = json_api_call(instance_request(boundary_to_geojson))
boundary_autocomplete_view = instance_request(
    json_api_call(boundary_autocomplete))

search_tree_benefits_view = instance_request(
    etag(_search_hash)(
        render_template('treemap/eco_benefits.html',
                        search_tree_benefits)))

species_list_view = json_api_call(instance_request(species_list))

user_view = render_template("treemap/user.html", user)

update_user_view = require_http_method("PUT")(json_api_call(update_user))

user_audits_view = render_template("treemap/recent_user_edits.html",
                                   user_audits)

instance_not_available_view = render_template(
    "treemap/instance_not_available.html")

unsupported_view = render_template("treemap/unsupported.html")

landing_view = render_template("base.html")

add_tree_photo_endpoint = require_http_method("POST")(
    instance_request(add_tree_photo_view))

scss_view = require_http_method("GET")(
    string_as_file_call("text/css", compile_scss))
