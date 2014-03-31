# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import string
import re
import urllib
import json
import hashlib
import datetime
import collections

import sass

from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, render_to_response
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.views.decorators.http import etag
from django.conf import settings
from django.contrib.gis.geos import Point, MultiPolygon, Polygon
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as trans
from django.utils.formats import number_format
from django.db import transaction
from django.db.models import Q
from django.template import RequestContext
from django.template.loader import render_to_string

from opentreemap.util import json_from_request, route

from treemap.decorators import (json_api_call, render_template, login_or_401,
                                require_http_method, string_as_file_call,
                                requires_feature, get_instance_or_404,
                                creates_instance_user, instance_request,
                                username_matches_request_user)
from treemap.util import (package_validation_errors,
                          bad_request_json_response, to_object_name)
from treemap.images import save_image_from_request
from treemap.search import Filter
from treemap.audit import (Audit, approve_or_reject_existing_edit,
                           approve_or_reject_audits_and_apply)
from treemap.models import (Plot, Tree, User, Species, Instance,
                            TreePhoto, StaticPage, MapFeature)
from treemap.units import get_units, get_display_value, Convertible
from treemap.ecobackend import BAD_CODE_PAIR
from treemap.util import leaf_subclasses
from treemap.ecobenefits import get_benefits_for_filter


USER_EDIT_FIELDS = collections.OrderedDict([
    ('firstname',
     {'label': trans('First Name'),
      'identifier': 'user.firstname',
      'visibility': 'public'}),
    ('lastname',
     {'label': trans('Last Name'),
      'identifier': 'user.lastname',
      'visibility': 'public'}),
    ('organization',
     {'label': trans('Organization'),
      'identifier': 'user.organization',
      'visibility': 'public'}),
    ('email',
     {'label': trans('Email'),
      'identifier': 'user.email',
      'visibility': 'private'}),
    ('allow_email_contact',
     {'label': trans('Email Updates'),
      'identifier': 'user.allow_email_contact',
      'visibility': 'private',
      'template': "treemap/field/email_subscription_div.html"})
])


def _map_feature_hash(request, instance, feature_id, edit=False, tree_id=None):
    """
    Compute a unique hash for a given plot or tree

    tree_id is ignored since trees are included as a
    subset of the plot's hash. It is present here because
    this function is wrapped around views that can take
    tree_id as an argument
    """

    InstanceMapFeature = instance.scope_model(MapFeature)
    base = get_object_or_404(InstanceMapFeature, pk=feature_id).hash

    if request.user:
        pk = request.user.pk or ''

    return hashlib.md5(base + ':' + str(pk)).hexdigest()


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


def _get_map_feature_or_404(feature_id, instance, type=None):
    if type:
        MapFeatureSubclass = MapFeature.get_subclass(type)
        InstanceMapFeature = instance.scope_model(MapFeatureSubclass)
        return get_object_or_404(InstanceMapFeature, pk=feature_id)

    else:
        InstanceMapFeature = instance.scope_model(MapFeature)
        feature = get_object_or_404(InstanceMapFeature, pk=feature_id)

        # Use feature_type to get the appropriate object, e.g. feature.plot
        feature = getattr(feature, feature.feature_type.lower())
        return feature


def add_tree_photo(request, instance, feature_id, tree_id=None):
    plot = _get_map_feature_or_404(feature_id, instance, 'Plot')
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
        raise Http404('Tree id %s not found on plot %s'
                      % (tree_id, feature_id))

    #TODO: Validation Error
    #TODO: Auth Error
    if 'file' in request.FILES:
        data = request.FILES['file'].file
    else:
        data = request.body

    treephoto = tree.add_photo(data, request.user)

    return treephoto, tree


def add_tree_photo_view(request, instance, feature_id, tree_id=None):
    error = None
    try:
        _, tree = add_tree_photo(request, instance, feature_id, tree_id)
        photos = tree.photos()
    except ValidationError as e:
        trees = Tree.objects.filter(pk=tree_id)
        if len(trees) == 1:
            photos = trees[0].photos()
        else:
            photos = []
        error = '; '.join(e.messages)
    return {'photos': photos, 'error': error}


def map_feature_popup(request, instance, feature_id):
    feature = _get_map_feature_or_404(feature_id, instance)
    context = _context_dict_for_map_feature(instance, feature)
    return context


def render_map_feature_detail(request, instance, feature_id):
    feature = _get_map_feature_or_404(feature_id, instance)
    if feature.is_plot:
        template = 'treemap/plot_detail.html'
    else:
        template = 'map_features/%s_detail.html' % feature.feature_type
    context = _map_feature_detail(request, instance, feature)
    return render_to_response(template, context, RequestContext(request))


def render_map_feature_add(request, instance, type):
    if type in instance.map_feature_types[1:]:
        template = 'map_features/%s_add.html' % type
        return render_to_response(template, None, RequestContext(request))
    else:
        raise Http404('Instance does not support feature type ' + type)


def plot_detail(request, instance, feature_id, edit=False, tree_id=None):
    feature = _get_map_feature_or_404(feature_id, instance, 'Plot')
    return _map_feature_detail(request, instance, feature, edit, tree_id)


def _map_feature_detail(request, instance, feature, edit=False, tree_id=None):
    if feature.is_plot:
        if hasattr(request, 'instance_supports_ecobenefits'):
            supports_eco = request.instance_supports_ecobenefits
        else:
            supports_eco = instance.has_itree_region()

        context = context_dict_for_plot(
            instance,
            feature,
            tree_id,
            user=request.user,
            supports_eco=supports_eco)

        context['editmode'] = edit

    else:
        context = _context_dict_for_map_feature(instance, feature)

    return context


def _add_eco_benefits_to_context_dict(instance, feature, context):
    FeatureClass = feature.__class__

    if not hasattr(FeatureClass, 'benefits'):
        return

    benefits, basis, error = FeatureClass.benefits\
                                         .benefits_for_object(
                                             instance, feature)
    if error == BAD_CODE_PAIR:
        context['invalid_eco_pair'] = True
    elif benefits:
        context.update(_format_benefits(instance, benefits, basis))


def _context_dict_for_map_feature(instance, feature):
    if instance.pk != feature.instance_id:
        raise Exception("Invalid instance, does not match map feature")

    feature.instance = instance  # save a DB lookup

    if feature.is_plot:
        tree = feature.current_tree()
        if tree:
            if tree.species:
                title = tree.species.common_name
            else:
                title = trans("Missing Species")
        else:
            title = trans("Empty Planting Site")
    else:
        title = feature.display_name

    context = {
        'feature': feature,
        'feature_type': feature.feature_type,
        'title': title,
    }

    _add_eco_benefits_to_context_dict(instance, feature, context)

    return context


def context_dict_for_plot(instance, plot,
                          tree_id=None, user=None, supports_eco=False):
    context = _context_dict_for_map_feature(instance, plot)

    if tree_id:
        tree = get_object_or_404(Tree,
                                 instance=instance,
                                 plot=plot,
                                 pk=tree_id)
    else:
        tree = plot.current_tree()

    plot.convert_to_display_units()
    if tree:
        tree.convert_to_display_units()

    photos = []
    if tree is not None:
        for photo in list(tree.treephoto_set.all()):
            photo_dict = photo.as_dict()
            photo_dict['image'] = photo.image.url
            photo_dict['thumbnail'] = photo.thumbnail.url

            photos.append(photo_dict)

    context['photos'] = photos

    has_tree_diameter = tree is not None and tree.diameter is not None
    has_tree_species_with_code = tree is not None \
        and tree.species is not None and tree.species.otm_code is not None
    has_photo = tree is not None and len(photos) > 0

    total_progress_items = 4
    completed_progress_items = 1  # there is always a plot

    if has_tree_diameter:
        completed_progress_items += 1
    if has_tree_species_with_code:
        completed_progress_items += 1
    if has_photo:
        completed_progress_items += 1

    context['progress_percent'] = int(100 * (
        completed_progress_items / total_progress_items))

    context['progress_messages'] = []
    if not tree:
        context['progress_messages'].append(trans('Add a tree'))
    if not has_tree_diameter:
        context['progress_messages'].append(trans('Add the diameter'))
    if not has_tree_species_with_code:
        context['progress_messages'].append(trans('Add the species'))
    if not has_photo:
        context['progress_messages'].append(trans('Add a photo'))

    if tree:
        context['upload_tree_photo_url'] = \
            reverse('add_photo_to_tree',
                    kwargs={'instance_url_name': instance.url_name,
                            'feature_id': plot.pk,
                            'tree_id': tree.pk})
    else:
        context['upload_tree_photo_url'] = \
            reverse('add_photo_to_plot',
                    kwargs={'instance_url_name': instance.url_name,
                            'feature_id': plot.pk})

    if user and user.is_authenticated():
        plot.mask_unauthorized_fields(user)

    context['plot'] = plot
    context['has_tree'] = tree is not None
    # Give an empty tree when there is none in order to show tree fields easily
    context['tree'] = tree or Tree(plot=plot, instance=instance)

    audits = _plot_audits(user, instance, plot)

    def _audits_are_in_different_groups(prev_audit, audit):
        if prev_audit is None:
            return True
        elif prev_audit.user_id != audit.user_id:
            return True
        else:
            time_difference = last_audit.updated - audit.updated
            return time_difference > datetime.timedelta(days=1)

    audit_groups = []
    current_audit_group = None
    last_audit = None

    for audit in audits:
        if _audits_are_in_different_groups(last_audit, audit):
            current_audit_group = {
                'updated': audit.updated,
                'user': audit.user,
                'audits': []}
            audit_groups.append(current_audit_group)
        current_audit_group['audits'].append(audit)
        last_audit = audit
    # Converting the audit groups to tuples makes the template code cleaner
    context['recent_activity'] = [
        (ag['user'], ag['updated'], ag['audits']) for ag in audit_groups]

    if len(audits) > 0:
        context['latest_update'] = audits[0]
    else:
        context['latest_update'] = None

    return context


def add_map_feature(request, instance, type='Plot'):
    feature = MapFeature.create(type, instance)
    return _request_to_update_map_feature(request, instance, feature)


def update_map_feature_detail(request, instance, feature_id, type='Plot'):
    feature = _get_map_feature_or_404(feature_id, instance, type)
    return _request_to_update_map_feature(request, instance, feature)


def _request_to_update_map_feature(request, instance, feature):
    try:
        request_dict = json.loads(request.body)
        feature, tree = update_map_feature(request_dict, request.user, feature)

        # We need to reload the instance here since a new georev
        # may have been set
        instance = Instance.objects.get(pk=instance.pk)

        return {
            'ok': True,
            'geoRevHash': instance.geo_rev_hash,
            'featureId': feature.id,
            'treeId': tree.id if tree else None,
            'enabled': instance.feature_enabled('add_plot')
        }
    except ValidationError as ve:
        return bad_request_json_response(
            validation_error_dict=ve.message_dict)


@transaction.commit_on_success
def delete_tree(request, instance, feature_id, tree_id):
    InstanceTree = instance.scope_model(Tree)
    tree = get_object_or_404(InstanceTree, pk=tree_id, plot_id=feature_id)
    tree.delete_with_user(request.user)
    return {'ok': True}


def delete_map_feature(request, instance, feature_id, type='Plot'):
    feature = _get_map_feature_or_404(feature_id, instance, type)
    try:
        feature.delete_with_user(request.user)
        return {'ok': True}
    except ValidationError as ve:
        return "; ".join(ve.messages)


@transaction.commit_on_success
def update_map_feature(request_dict, user, feature):
    """
    Update a map feature. Expects JSON in the request body to be:
    {'model.field', ...}

    Where model is either 'tree', 'plot', or another map feature type
    and field is any field on the model.
    UDF fields should be prefixed with 'udf:'.

    This method can be used to create a new map feature by passing in
    an empty MapFeature object (i.e. Plot(instance=instance))
    """
    feature_object_names = [to_object_name(ft)
                            for ft in feature.instance.map_feature_types]

    if isinstance(feature, Convertible):
        # We're going to always work in display units here
        feature.convert_to_display_units()

    def split_model_or_raise(identifier):
        parts = identifier.split('.', 1)

        if (len(parts) != 2 or
                parts[0] not in feature_object_names + ['tree']):
            raise Exception(
                'Malformed request - invalid field %s' % identifier)
        else:
            return parts

    def set_attr_on_model(model, attr, val):
        field_classname = \
            model._meta.get_field_by_name(attr)[0].__class__.__name__

        if field_classname.endswith('PointField'):
            srid = val.get('srid', 3857)
            val = Point(val['x'], val['y'], srid=srid)
            val.transform(3857)
        elif field_classname.endswith('MultiPolygonField'):
            srid = val.get('srid', 4326)
            val = MultiPolygon(Polygon(val['polygon'], srid=srid), srid=srid)
            val.transform(3857)

        if attr == 'mapfeature_ptr':
            if model.mapfeature_ptr_id != value:
                raise Exception(
                    'You may not change the mapfeature_ptr_id')
        elif attr == 'id':
            if val != model.pk:
                raise Exception("Can't update id attribute")
        elif attr.startswith('udf:'):
            udf_name = attr[4:]

            if udf_name in [field.name
                            for field
                            in model.get_user_defined_fields()]:
                model.udfs[udf_name] = val
            else:
                raise KeyError('Invalid UDF %s' % attr)
        elif attr in model.fields():
            model.apply_change(attr, val)
        else:
            raise Exception('Malformed request - invalid field %s' % attr)

    def save_and_return_errors(thing, user):
        try:
            if isinstance(thing, Convertible):
                thing.convert_to_database_units()

            thing.save_with_user(user)
            return {}
        except ValidationError as e:
            return package_validation_errors(thing._model_name, e)

    tree = None

    for (identifier, value) in request_dict.iteritems():
        object_name, field = split_model_or_raise(identifier)

        if object_name in feature_object_names:
            model = feature
        elif object_name == 'tree' and feature.feature_type == 'Plot':
            # Get the tree or spawn a new one if needed
            tree = (tree or
                    feature.current_tree() or
                    Tree(instance=feature.instance))

            # We always edit in display units
            tree.convert_to_display_units()

            model = tree
            if field == 'species' and value:
                value = get_object_or_404(Species,
                                          instance=feature.instance, pk=value)
            elif field == 'plot' and value == unicode(feature.pk):
                value = feature
        else:
            raise Exception(
                'Malformed request - invalid model %s' % object_name)

        set_attr_on_model(model, field, value)

    errors = {}

    if feature.fields_were_updated():
        errors.update(save_and_return_errors(feature, user))
    if tree and tree.fields_were_updated():
        tree.plot = feature
        errors.update(save_and_return_errors(tree, user))

    if errors:
        raise ValidationError(errors)

    # Refresh feature.instance in case geo_rev_hash was updated
    feature.instance = Instance.objects.get(id=feature.instance.id)

    return feature, tree


def _get_audits(logged_in_user, instance, query_vars, user, models,
                model_id, page=0, page_size=20, exclude_pending=True,
                should_count=False):
    start_pos = page * page_size
    end_pos = start_pos + page_size

    model_filter = Q(model__in=models)

    # We only want to show the TreePhoto's image, not other fields
    # and we want to do it automatically if 'Tree' was specified as
    # a model
    if 'Tree' in models:
        model_filter = model_filter | Q(model='TreePhoto', field='image')

    if instance:
        if instance.is_accessible_by(logged_in_user):
            instance_filter = Q(pk=instance.pk)
        else:
            # Force no results
            return {'audits': [],
                    'next_page': None,
                    'prev_page': None}
    # If we didn't specify an instance we only want to
    # show audits where the user has permission
    else:
        public = Q(is_public=True)

        if logged_in_user is not None and not logged_in_user.is_anonymous():
            private_with_access = Q(instanceuser__user=logged_in_user)

            instance_filter = public | private_with_access
        else:
            instance_filter = public

    instances = Instance.objects.filter(instance_filter)

    # We need a filter per-instance in order to only show UDF collection
    # visible to the user
    for inst in Instance.objects.filter(instance_filter):
        # Only add UDF collections if their parent models are being shown
        for model in models:
            if model == 'Tree':
                fake_model = Tree(instance=inst)
            elif model == 'Plot':
                fake_model = Plot(instance=inst)
            else:
                continue

            model_collection_udfs_audit_names =\
                fake_model.visible_collection_udfs_audit_names(logged_in_user)

            # Don't show the fields that every collection UDF has, because they
            # are not very interesting
            model_filter = model_filter |\
                (Q(model__in=model_collection_udfs_audit_names) &
                 ~Q(field__in=('id', 'model_id', 'field_definition')))

    audits = Audit.objects.filter(model_filter)\
                          .filter(instance__in=instances)\
                          .order_by('-created', 'id')

    if user:
        audits = audits.filter(user=user)
    if model_id:
        audits = audits.filter(model_id=model_id)
    if exclude_pending:
        audits = audits.exclude(requires_auth=True, ref__isnull=True)

    total_count = audits.count() if should_count else 0
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
            'total_count': total_count,
            'next_page': next_page,
            'prev_page': prev_page}


def get_filterable_audit_models():
    map_features = [c.__name__ for c in leaf_subclasses(MapFeature)]
    models = map_features + ['Tree']

    return {model.lower(): model for model in models}


def _get_audits_params(request):
    PAGE_MAX = 100
    PAGE_DEFAULT = 20

    r = request.REQUEST

    page_size = min(int(r.get('page_size', PAGE_DEFAULT)), PAGE_MAX)
    page = int(r.get('page', 0))

    models = []

    allowed_models = get_filterable_audit_models()
    models_param = r.get('models', None)

    if models_param:
        for model in models_param.split(','):
            if model.lower() in allowed_models:
                models.append(allowed_models[model.lower()])
            else:
                raise Exception("Invalid model: %s" % model)
    else:
        models = allowed_models.values()

    model_id = r.get('model_id', None)

    if model_id is not None and len(models) != 1:
        raise Exception("You must specific one and only model "
                        "when looking up by id")

    exclude_pending = r.get('exclude_pending', "false") == "true"

    return (page, page_size, models, model_id, exclude_pending)


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
     exclude_pending) = _get_audits_params(request)

    user_id = request.GET.get('user', None)
    user = None

    if user_id is not None:
        user = User.objects.get(pk=user_id)

    return _get_audits(request.user, instance, request.REQUEST, user,
                       models, model_id, page, page_size, exclude_pending)


def _plot_audits(user, instance, plot):
    readable_plot_fields = plot.visible_fields(user)

    plot_filter = Q(model='Plot', model_id=plot.pk,
                    field__in=readable_plot_fields)

    plot_collection_udfs_filter = Q(
        model__in=plot.visible_collection_udfs_audit_names(user),
        model_id__in=plot.collection_udfs_audit_ids())

    fake_tree = Tree(instance=instance)
    tree_visible_fields = fake_tree.visible_fields(user)

    # Get a history of trees that were on this plot
    tree_history = plot.get_tree_history()

    tree_filter = Q(model='Tree',
                    field__in=tree_visible_fields,
                    model_id__in=tree_history)

    tree_delete_filter = Q(model='Tree',
                           action=Audit.Type.Delete,
                           model_id__in=tree_history)

    tree_collection_udfs_audit_names =\
        fake_tree.visible_collection_udfs_audit_names(user)

    tree_collection_udfs_filter = Q(
        model__in=tree_collection_udfs_audit_names,
        model_id__in=Tree.static_collection_udfs_audit_ids(
            (instance,), tree_history, tree_collection_udfs_audit_names))

    # Seems to be much faster to do three smaller
    # queries here instead of ORing them together
    # (about a 50% inprovement!)
    # TODO: Verify this is still the case now that we are also getting
    # collection udf audits
    iaudit = Audit.objects.filter(instance=instance)

    audits = []
    for afilter in [tree_filter, tree_delete_filter, plot_filter]:
        audits += list(iaudit.filter(afilter).order_by('-updated')[:5])

    # UDF collection audits have some fields which aren't very useful to show
    udf_collection_exclude_filter = Q(
        field__in=['model_id', 'field_definition'])

    for afilter in [plot_collection_udfs_filter, tree_collection_udfs_filter]:
        audits += list(iaudit.filter(afilter)
                             .exclude(udf_collection_exclude_filter)
                             .order_by('-updated')[:5])

    audits = sorted(audits, key=lambda audit: audit.updated, reverse=True)[:5]

    return audits


def user_audits(request, username):
    user = get_object_or_404(User, username=username)
    instance_id = request.GET.get('instance_id', None)

    instance = (get_instance_or_404(pk=instance_id)
                if instance_id else None)

    (page, page_size, models, model_id,
     exclude_pending) = _get_audits_params(request)

    return _get_audits(request.user, instance, request.REQUEST, user,
                       models, model_id, page, page_size, exclude_pending)


def instance_user_audits(request, instance_url_name, username):
    instance = get_instance_or_404(url_name=instance_url_name)
    return HttpResponseRedirect(
        reverse('user_audits', kwargs={'username': username})
        + '?instance_id=%s' % instance.pk)


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


def search_tree_benefits(request, instance):
    filter_str = request.REQUEST.get('q', '')
    display_str = request.REQUEST.get('show', '')

    hide_summary_text = request.REQUEST.get('hide_summary', 'false')
    hide_summary = hide_summary_text.lower() == 'true'

    filter = Filter(filter_str, display_str, instance)
    total_plots = filter.get_object_count(Plot)

    benefits, basis = get_benefits_for_filter(filter)

    # Inject the plot count as a basis for tree benefit calcs
    basis.get('plot', {})['n_plots'] = total_plots

    # We also want to inject the total currency amount saved
    # for plot-based items except CO2 stored
    total_currency_saved = 0

    for benefit_name, benefit in benefits.get('plot', {}).iteritems():
        if benefit_name != 'co2storage':
            total_currency_saved += benefit.get('currency', 0.0)

    # save it as if it were a normal benefit so we get formatting
    # and currency conversion
    benefits.get('plot', {})['totals'] = {
        'value': None,
        'currency': total_currency_saved,
        'label': trans('Total')
    }

    formatted = _format_benefits(instance, benefits, basis)
    formatted['hide_summary'] = hide_summary

    return formatted


def _format_benefits(instance, benefits, basis):
    currency_symbol = ''
    if instance.eco_benefits_conversion:
        currency_symbol = instance.eco_benefits_conversion.currency_symbol

    # FYI: this mutates the underlying benefit dictionaries
    for benefit_group in benefits.values():
        for key, benefit in benefit_group.iteritems():
            if benefit['currency'] is not None:
                # TODO: Use i18n/l10n to format currency
                benefit['currency_saved'] = currency_symbol + number_format(
                    benefit['currency'], decimal_pos=0)

            unit_key = benefit.get('unit-name')

            if unit_key:
                _, value = get_display_value(
                    instance, unit_key, key, benefit['value'])

                benefit['value'] = value
                benefit['unit'] = get_units(instance, unit_key, key)

    # Add total and percent to basis
    rslt = {'benefits': {k: v.values() for (k, v) in benefits.iteritems()},
            'currency_symbol': currency_symbol,
            'basis': basis}

    return rslt


def user(request, username):
    user = get_object_or_404(User, username=username)
    instance_id = request.GET.get('instance_id', None)

    instance = (get_instance_or_404(pk=instance_id)
                if instance_id else None)

    query_vars = {'instance_id': instance_id} if instance_id else {}

    audit_dict = _get_audits(request.user, instance, query_vars,
                             user, ['Plot', 'Tree'], 0, should_count=True)

    reputation = user.get_reputation(instance) if instance else None

    public_fields = []
    private_fields = []

    for field in USER_EDIT_FIELDS.values():
        field_tuple = (field['label'], field['identifier'],
                       field.get('template', "treemap/field/div.html"))
        if field['visibility'] == 'public':
            public_fields.append(field_tuple)
        else:
            private_fields.append(field_tuple)

    return {'user': user,
            'reputation': reputation,
            'instance_id': instance_id,
            'total_count': audit_dict['total_count'],
            'audits': audit_dict['audits'],
            'next_page': audit_dict['next_page'],
            'public_fields': public_fields,
            'private_fields': private_fields}


def update_user(request, user):
    new_values = json_from_request(request) or {}
    for key in new_values:
        try:
            model, field = key.split('.', 1)
            if model != 'user':
                return bad_request_json_response(
                    'All fields should be prefixed with "user."')
            if field not in USER_EDIT_FIELDS:
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


def upload_user_photo(request, user):
    """
    Saves a user profile photo whose data is in the request.
    The callee or decorator is reponsible for ensuring request.user == user
    """
    try:
        user.photo, user.thumbnail = save_image_from_request(
            request, name_prefix="user-%s" % user.pk, thumb_size=(85, 85))
        user.save_with_user(request.user)
    except ValidationError as e:
        # Most of these ValidationError are not field-errors and so their
        # messages are a Dict, which is why they simply joined together
        return bad_request_json_response('; '.join(e.messages))

    return {'url': user.thumbnail.url}


def _get_map_view_context(request, instance):
    resource_classes = [MapFeature.get_subclass(type)
                        for type in instance.map_feature_types]
    return {
        'fields_for_add_tree': [
            (trans('Tree Height'), 'Tree.height')
        ],
        'resource_classes': resource_classes[1:]
    }


def instance_user_view(request, instance_url_name, username):
    instance = get_instance_or_404(url_name=instance_url_name)
    url = reverse('user', kwargs={'username': username}) +\
        '?instance_id=%s' % instance.pk
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


PHOTO_PAGE_SIZE = 12


def _photo_audits(instance):
    unverified_actions = {Audit.Type.Insert,
                          Audit.Type.Delete,
                          Audit.Type.Update}

    # Only return audits for photos that haven't been deleted
    photo_ids = TreePhoto.objects.filter(instance=instance)\
                                 .values_list('id', flat=True)

    audits = Audit.objects.filter(instance=instance,
                                  model='TreePhoto',
                                  field='image',
                                  ref__isnull=True,
                                  action__in=unverified_actions,
                                  model_id__in=photo_ids)\
                          .order_by('-created')

    return audits


def next_photo(request, instance):
    audits = _photo_audits(instance)

    total = audits.count()
    page = int(request.REQUEST.get('n', '1'))
    total_pages = int(total / PHOTO_PAGE_SIZE + 0.5)

    startidx = (page-1) * PHOTO_PAGE_SIZE
    endidx = startidx + PHOTO_PAGE_SIZE

    # We're done!
    if total == 0:
        photo = None
    else:
        try:
            photo_id = audits[endidx].model_id
        except IndexError:
            # We may have finished an entire page
            # in that case, simply return the last image
            photo_id = audits[total-1].model_id

        photo = TreePhoto.objects.get(pk=photo_id)

    return {
        'photo': photo,
        'total_pages': total_pages
    }


def photo_review(request, instance):
    audits = _photo_audits(instance)

    total = audits.count()
    page = int(request.REQUEST.get('n', '1'))
    total_pages = int(total / PHOTO_PAGE_SIZE + 0.5)

    startidx = (page-1) * PHOTO_PAGE_SIZE
    endidx = startidx + PHOTO_PAGE_SIZE

    audits = audits[startidx:endidx]

    prev_page = page - 1
    if prev_page <= 0:
        prev_page = None

    next_page = page + 1
    if next_page > total_pages:
        next_page = None

    pages = range(1, total_pages+1)
    if len(pages) > 10:
        pages = pages[0:8] + [pages[-1]]

    return {
        'photos': [TreePhoto.objects.get(pk=audit.model_id)
                   for audit in audits],
        'pages': pages,
        'total_pages': total_pages,
        'cur_page': page,
        'next_page': next_page,
        'prev_page': prev_page
    }


@transaction.commit_on_success
def approve_or_reject_photo(
        request, instance, feature_id, tree_id, photo_id, action):

    approved = action == 'approve'

    if approved:
        msg = trans('Approved')
    else:
        msg = trans('Rejected')

    resp = HttpResponse(msg)

    tree = get_object_or_404(
        Tree, plot_id=feature_id, instance=instance, pk=tree_id)

    try:
        photo = TreePhoto.objects.get(pk=photo_id, tree=tree)
    except TreePhoto.DoesNotExist:
        # This may be a pending tree. Let's see if there
        # are pending audits
        pending_audits = Audit.objects\
                              .filter(instance=instance)\
                              .filter(model='TreePhoto')\
                              .filter(model_id=photo_id)\
                              .filter(requires_auth=True)

        if len(pending_audits) > 0:
            # Process as pending and quit
            approve_or_reject_audits_and_apply(
                pending_audits, request.user, approved)

            return resp
        else:
            # Error - no pending or regular
            raise Http404('Tree Photo Not Found')

    # Handle the id audit first
    all_audits = []
    for audit in photo.audits():
        if audit.field == 'id':
            all_audits = [audit] + all_audits
        else:
            all_audits.append(audit)

    for audit in all_audits:
        approve_or_reject_existing_edit(
            audit, request.user, approved)

    return resp


def static_page(request, instance, page):
    static_page = StaticPage.get_or_new(instance, page)

    return {'content': static_page.content,
            'title': static_page.name}


def index(request, instance):
    return HttpResponseRedirect(reverse('map', kwargs={
        'instance_url_name': instance.url_name}))


def tree_detail(request, instance, feature_id, tree_id):
    return HttpResponseRedirect(reverse('map_feature_detail', kwargs={
        'instance_url_name': instance.url_name,
        'feature_id': feature_id}))


def forgot_username(request):
    user_email = request.REQUEST['email']
    users = User.objects.filter(email=user_email)

    # Don't reveal if we don't have that email, to prevent email harvesting
    if len(users) == 1:
        user = users[0]

        password_reset_url = request.build_absolute_uri(
            reverse('auth_password_reset'))

        subject = trans('Account Recovery')
        body = render_to_string('treemap/partials/forgot_username_email.txt',
                                {'user': user,
                                 'password_url': password_reset_url})

        user.email_user(subject, body, settings.DEFAULT_FROM_EMAIL)

    return {'email': user_email}


tree_detail_view = instance_request(tree_detail)

edits_view = instance_request(
    requires_feature('recent_edits_report')(
        render_template('treemap/edits.html', edits)))

index_view = instance_request(index)

map_view = instance_request(
    render_template('treemap/map.html', _get_map_view_context))

get_map_feature_detail_view = instance_request(render_map_feature_detail)

get_map_feature_add_view = instance_request(render_map_feature_add)

edit_plot_detail_view = login_required(
    instance_request(
        creates_instance_user(
            render_template('treemap/plot_detail.html', plot_detail))))

update_map_feature_detail_view = login_or_401(
    json_api_call(
        instance_request(
            creates_instance_user(update_map_feature_detail))))

delete_tree_view = login_or_401(
    json_api_call(
        instance_request(
            creates_instance_user(delete_tree))))

delete_map_feature_view = login_or_401(
    json_api_call(
        instance_request(
            creates_instance_user(delete_map_feature))))

get_plot_eco_view = instance_request(etag(_map_feature_hash)(
    render_template('treemap/partials/plot_eco.html', plot_detail)))

get_map_feature_sidebar_view = instance_request(etag(_map_feature_hash)(
    render_template('treemap/partials/sidebar.html', plot_detail)))

map_feature_popup_view = instance_request(etag(_map_feature_hash)(
    render_template('treemap/partials/map_feature_popup.html',
                    map_feature_popup)))

plot_accordion_view = instance_request(
    render_template('treemap/plot_accordion.html', plot_detail))

add_map_feature_view = require_http_method("POST")(
    login_or_401(
        json_api_call(
            instance_request(
                creates_instance_user(add_map_feature)))))

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
        render_template('treemap/partials/eco_benefits.html',
                        search_tree_benefits)))

species_list_view = json_api_call(instance_request(species_list))

user_view = render_template("treemap/user.html", user)

update_user_view = require_http_method("PUT")(
    username_matches_request_user(
        json_api_call(update_user)))

user_audits_view = render_template("treemap/recent_user_edits.html",
                                   user_audits)

upload_user_photo_view = require_http_method("POST")(
    username_matches_request_user(
        json_api_call(upload_user_photo)))

instance_not_available_view = render_template(
    "treemap/instance_not_available.html")

unsupported_view = render_template("treemap/unsupported.html")

landing_view = render_template("base.html")

add_tree_photo_endpoint = require_http_method("POST")(
    login_or_401(
        instance_request(
            creates_instance_user(
                render_template("treemap/partials/tree_carousel.html",
                                add_tree_photo_view)))))

scss_view = require_http_method("GET")(
    string_as_file_call("text/css", compile_scss))

photo_review_endpoint = instance_request(
    route(
        GET=render_template("treemap/photo_review.html",
                            photo_review)))

photo_review_partial_endpoint = instance_request(
    route(
        GET=render_template("treemap/partials/photo_review.html",
                            photo_review)))

next_photo_endpoint = instance_request(
    route(
        GET=render_template("treemap/partials/photo.html",
                            next_photo)))

approve_or_reject_photo_view = login_required(
    instance_request(
        creates_instance_user(approve_or_reject_photo)))

static_page_view = instance_request(
    render_template("treemap/staticpage.html", static_page))

forgot_username_view = route(
    GET=render_template('treemap/forgot_username.html'),
    POST=render_template('treemap/forgot_username_done.html', forgot_username))

error_404_view = render_template('404.html', statuscode=404)
error_500_view = render_template('500.html', statuscode=500)
error_503_view = render_template('503.html', statuscode=503)
