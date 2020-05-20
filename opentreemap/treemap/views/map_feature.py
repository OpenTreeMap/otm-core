# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import datetime
import json
import hashlib
import re
import time
from functools import wraps

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import connection, transaction
from django.contrib.gis.geos import Point, MultiPolygon, Polygon
from django.contrib.gis.db.models import GeometryField
from django.utils.translation import ugettext as _

from opentreemap.util import dotted_split
from opentreemap.integrations import inaturalist
from treemap.lib.hide_at_zoom import (update_hide_at_zoom_after_move,
                                      update_hide_at_zoom_after_delete)

from treemap.units import Convertible
from treemap.models import (Tree, Species, MapFeature,
                            MapFeaturePhoto, TreePhoto, Favorite,
                            MapFeaturePhotoLabel, INaturalistPhoto, INaturalistObservation)
from treemap.util import (package_field_errors, to_object_name)

from treemap.images import get_image_from_request
from treemap.lib.photo import context_dict_for_photo
from treemap.lib.map_feature import (get_map_feature_or_404,
                                     raise_non_instance_404,
                                     context_dict_for_plot,
                                     context_dict_for_resource)
from treemap.views.misc import add_map_info_to_context, add_plot_field_groups


def _request_to_update_map_feature(request, feature):
    request_dict = json.loads(request.body)
    feature, tree = update_map_feature(request_dict, request.user, feature)

    ctx_fn = (context_dict_for_plot if feature.is_plot
              else context_dict_for_resource)

    return {
        'ok': True,
        'geoRevHash': feature.instance.geo_rev_hash,
        'universalRevHash': feature.instance.universal_rev_hash,
        'featureId': feature.id,
        'treeId': tree.id if tree else None,
        'feature': ctx_fn(request, feature),
        'enabled': feature.instance.feature_enabled('add_plot'),
    }


def _add_map_feature_photo_helper(request, instance, feature_id):
    feature = get_map_feature_or_404(feature_id, instance)
    data = get_image_from_request(request)
    photo = feature.add_photo(data, request.user)
    # We must update a rev so that missing photo searches are up to date
    instance.update_universal_rev()
    return photo


def get_photo_context_and_errors(fn):
    @wraps(fn)
    def wrapper(request, instance, feature_id, *args, **kwargs):
        error = None
        try:
            fn(request, instance, feature_id, *args, **kwargs)
        except ValidationError as e:
            error = '; '.join(e.messages)
        feature = get_map_feature_or_404(feature_id, instance)
        photos = feature.photos()
        return {'photos': [context_dict_for_photo(request, photo)
                           for photo in photos],
                'feature': feature,
                'error': error}

    return wrapper


def map_feature_detail(request, instance, feature_id,
                       should_render=False, edit=False):
    context, partial = _map_feature_detail_context(
        request, instance, feature_id, edit)
    add_map_info_to_context(context, instance)

    if should_render:
        template = 'treemap/map_feature_detail.html'
        context['map_feature_partial'] = partial
        latlon = context['feature'].latlon
        context['map_query'] = '?z=%s/%s/%s' % (18, latlon.y, latlon.x)
        return render(request, template, context)
    else:
        return context


def _map_feature_detail_context(request, instance, feature_id, edit=False):
    feature = get_map_feature_or_404(feature_id, instance)
    ctx_fn = (context_dict_for_plot if feature.is_plot
              else context_dict_for_resource)
    context = ctx_fn(request, feature, edit=edit)

    if feature.is_plot:
        partial = 'treemap/partials/plot_detail.html'
        add_plot_field_groups(context, instance)
    else:
        app = feature.__module__.split('.')[0]
        partial = '%s/%s_detail.html' % (app, feature.feature_type)

    return context, partial


def render_map_feature_detail_partial(request, instance, feature_id, **kwargs):
    context, partial = _map_feature_detail_context(
        request, instance, feature_id)
    return render(request, partial, context)


def render_map_feature_detail(request, instance, feature_id, **kwargs):
    return map_feature_detail(request, instance, feature_id,
                              should_render=True, **kwargs)


def context_map_feature_detail(request, instance, feature_id, **kwargs):
    return map_feature_detail(request, instance, feature_id,
                              should_render=False, **kwargs)


def map_feature_photo_detail(request, instance, feature_id, photo_id):
    feature = get_map_feature_or_404(feature_id, instance)
    photo = get_object_or_404(MapFeaturePhoto, pk=photo_id,
                              map_feature=feature)
    return {'photo': context_dict_for_photo(request, photo)}


def plot_detail(request, instance, feature_id, edit=False, tree_id=None):
    feature = get_map_feature_or_404(feature_id, instance, 'Plot')
    return context_dict_for_plot(request, feature, edit=edit, tree_id=tree_id)


def render_map_feature_add(request, instance, type):
    if type in instance.map_feature_types[1:]:
        app = MapFeature.get_subclass(type).__module__.split('.')[0]
        try:
            template = '%s/%s_add.html' % (app, type)
        except:
            template = 'treemap/resource_add.html'
        return render(request, template, {'object_name': to_object_name(type)})
    else:
        raise_non_instance_404(type)


def add_map_feature(request, instance, type='Plot'):
    if type not in instance.map_feature_types:
        raise_non_instance_404(type)
    feature = MapFeature.get_subclass(type)(instance=instance)
    return _request_to_update_map_feature(request, feature)


def update_map_feature_detail(request, instance, feature_id):
    feature = get_map_feature_or_404(feature_id, instance)
    return _request_to_update_map_feature(request, feature)


def delete_map_feature(request, instance, feature_id):
    feature = get_map_feature_or_404(feature_id, instance)
    feature.delete_with_user(request.user)  # may raise AuthorizeException
    update_hide_at_zoom_after_delete(feature)
    return {'ok': True}


@transaction.atomic
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

    def value_is_redundant(model, field_name, value):
        # The iOS app sends a key in `data` for every udf definition,
        # even if it hasn't changed.
        # If it is trying to delete a custom field that is not defined
        # for the model, flag it as redundant,
        # to avoid a `KeyError` when the update tries to delete them.
        if field_name.startswith('udf:') and \
                value in [[], '[]', '', None]:
            udf_name = field_name.replace('udf:', '')
            if udf_name not in model.udfs:
                return True
        return False

    def set_attr_on_model(model, attr, val):
        field_classname = \
            model._meta.get_field(attr).__class__.__name__

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
            return package_field_errors(thing._model_name, e)

    def check_if_species_is_set(request_dict):
        # If we have a field that explicitly checks for empty site,
        # called is_empty_site, and that is False, and either
        # tree.species is empty or not set, then we have a problem
        if 'is_empty_site' not in request_dict:
            return

        # if we don't remove it, we will get failures as OTM tries to find
        # this field on the model
        is_empty_site = request_dict.pop('is_empty_site')
        tree_species = request_dict.get('tree.species')
        if not is_empty_site and not tree_species:
            raise ValidationError(
                {'tree.species': 'Either set a species or set to an empty planting site'}
            )

        # if both are set, that is also a problem
        if is_empty_site and tree_species:
            raise ValidationError(
                {'tree.species': 'Cannot set both species and empty planting site'}
            )

    def check_all_photos(request_dict):
        # check that we have a shape, bark and leaf photo
        # we need all to be valid

        has_shape_photo = request_dict.pop('has_shape_photo', False)
        has_bark_photo = request_dict.pop('has_bark_photo', False)
        has_leaf_photo = request_dict.pop('has_leaf_photo', False)
        if not (has_shape_photo and has_bark_photo and has_leaf_photo):
            # FIXME eventually, do not put a validation error on the species
            raise ValidationError(
                {'tree.species': 'Please submit all photos'}
            )

    def skip_setting_value_on_tree(value, tree):
        # If the tree is not None, we always set a value.  If the tree
        # is None (meaning that we would be creating a new Tree
        # object) then we only want to set a value if the value is
        # non-empty.
        return (tree is None) and (value in ([], '[]', '', None))

    tree = None
    errors = {}

    # validate species before checking any fields
    # but only validate on creation, which means the feature.id is not set
    if (not feature.id):
        check_if_species_is_set(request_dict)
        check_all_photos(request_dict)

    rev_updates = ['universal_rev']
    old_geom = feature.geom
    for (identifier, value) in request_dict.iteritems():
        split_template = 'Malformed request - invalid field %s'
        object_name, field = dotted_split(identifier, 2,
                                          failure_format_string=split_template)
        if (object_name not in feature_object_names + ['tree']):
            raise ValueError(split_template % identifier)

        if (object_name == 'tree'
            and skip_setting_value_on_tree(
                value, feature.safe_get_current_tree())):
            continue
        elif object_name in feature_object_names:
            model = feature
        elif object_name == 'tree' and feature.feature_type == 'Plot':
            # Get the tree or spawn a new one if needed
            tree = (tree or
                    feature.safe_get_current_tree() or
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
            raise ValueError(
                'Malformed request - invalid model %s' % object_name)

        if not value_is_redundant(model, field, value):
            set_attr_on_model(model, field, value)

        field_class = model._meta.get_field(field)
        if isinstance(field_class, GeometryField):
            rev_updates.append('geo_rev')
            rev_updates.append('eco_rev')
        elif identifier in ['tree.species', 'tree.diameter']:
            rev_updates.append('eco_rev')

    if feature.fields_were_updated():
        errors.update(save_and_return_errors(feature, user))
    if tree and tree.fields_were_updated():
        tree.plot = feature
        errors.update(save_and_return_errors(tree, user))

    if errors:
        # It simplifies the templates and client-side logic if the geometry
        # field errors are returned under the generic name
        if feature.geom_field_name in errors:
            errors['mapFeature.geom'] = errors[feature.geom_field_name]
        raise ValidationError(errors)

    if old_geom is not None and feature.geom != old_geom:
        update_hide_at_zoom_after_move(feature, user, old_geom)

    feature.instance.update_revs(*rev_updates)

    return feature, tree


def map_feature_hash(request, instance, feature_id, edit=False, tree_id=None):
    """
    Compute a unique hash for a given plot or tree

    tree_id is ignored since trees are included as a
    subset of the plot's hash. It is present here because
    this function is wrapped around views that can take
    tree_id as an argument
    """
    feature = get_map_feature_or_404(feature_id, instance)

    if request.user:
        pk = request.user.pk or ''

    return hashlib.md5(feature.hash + ':' + str(pk)).hexdigest()


@get_photo_context_and_errors
def add_map_feature_photo(request, instance, feature_id):
    _add_map_feature_photo_helper(request, instance, feature_id)


@get_photo_context_and_errors
def rotate_map_feature_photo(request, instance, feature_id, photo_id):
    orientation = request.POST.get('degrees', None)
    if orientation not in {'90', '180', '270', '-90', '-180', '-270'}:
        raise ValidationError('"degrees" must be a multiple of 90°')

    degrees = int(orientation)
    feature = get_map_feature_or_404(feature_id, instance)
    mf_photo = get_object_or_404(MapFeaturePhoto,
                                 pk=photo_id,
                                 map_feature=feature)

    image_data = mf_photo.image.read(settings.MAXIMUM_IMAGE_SIZE)
    mf_photo.set_image(image_data, degrees_to_rotate=degrees)
    mf_photo.save_with_user(request.user)


@get_photo_context_and_errors
def add_map_feature_photo_label(request, instance, feature_id, photo_id):
    feature = get_map_feature_or_404(feature_id, instance)
    photo_class = TreePhoto if feature.is_plot else MapFeaturePhoto
    mf_photo = get_object_or_404(photo_class, pk=photo_id, map_feature=feature)
    label_dict = json.loads(request.body)
    map_feature_photo_label = MapFeaturePhotoLabel()
    map_feature_photo_label.map_feature_photo = mf_photo
    map_feature_photo_label.name = label_dict['label']
    map_feature_photo_label.save()
    return


@get_photo_context_and_errors
def delete_photo(request, instance, feature_id, photo_id):
    feature = get_map_feature_or_404(feature_id, instance)
    photo_class = TreePhoto if feature.is_plot else MapFeaturePhoto
    mf_photo = get_object_or_404(photo_class, pk=photo_id, map_feature=feature)
    mf_photo.delete_with_user(request.user)  # may raise AuthorizeException


def map_feature_popup(request, instance, feature_id):
    feature = get_map_feature_or_404(feature_id, instance)
    context = {}
    context['features'] = [feature] + list(feature.nearby_map_features())
    if instance.canopy_enabled:
        context['boundaries_with_canopy'] = \
            _get_boundaries_with_canopy(instance, feature.geom)
    return context


def canopy_popup(request, instance):
    if instance.canopy_enabled:
        lng = request.GET['lng']
        lat = request.GET['lat']
        point = Point(float(lng), float(lat), srid=4326)
        result = _get_boundaries_with_canopy(instance, point)
        if result:
            return render(request, 'treemap/partials/canopy_popup.html',
                          {'boundaries_with_canopy': result})
    return HttpResponse('')


def _get_boundaries_with_canopy(instance, point):
    boundaries = instance.boundaries \
        .filter(geom__contains=point) \
        .exclude(canopy_percent__isnull=True) \
        .order_by('-sort_order')
    for boundary in boundaries:
        boundary.canopy_percent *= 100
    return boundaries


def favorite_map_feature(request, instance, feature_id):
    feature = get_map_feature_or_404(feature_id, instance)
    Favorite.objects.get_or_create(user=request.user, map_feature=feature)

    return {'success': True}


def unfavorite_map_feature(request, instance, feature_id):
    feature = get_map_feature_or_404(feature_id, instance)
    Favorite.objects.filter(user=request.user, map_feature=feature).delete()

    return {'success': True}


def get_photo_id_from_photo_detail_url(url, feature_id):
    """
    """
    return int(re.match(r'.*/{}/photo/(\d+)/detail'.format(feature_id), url).groups()[0])


def inaturalist_add(request, instance, *args, **kwargs):
    try:
        token = request.session['inaturalist_token']
    except KeyError:
        return {'success': False}

    # INaturalistPhoto, INaturalistObservation

    body = json.loads(request.body)
    feature_id = body['featureId']
    feature = get_map_feature_or_404(feature_id, instance)
    tree = feature.safe_get_current_tree()
    photo_id = get_photo_id_from_photo_detail_url(body['photoDetailUrl'], feature_id)
    photo_class = TreePhoto if feature.is_plot else MapFeaturePhoto
    photo = get_object_or_404(photo_class, pk=photo_id, map_feature=feature)

    (longitude, latitude) = feature.latlon.coords

    observation = inaturalist.create_observation(token, latitude, longitude)
    photo_info = inaturalist.add_photo_to_observation(token, observation['id'], photo)

    return {'success': True}


def inaturalist_create_observations(request, instance, *args, **kwargs):

    features = inaturalist.get_features_for_inaturalist()
    if not features:
        return

    token = inaturalist.get_inaturalist_auth_token()

    for feature in features:
        feature = get_map_feature_or_404(feature['feature_id'], instance)
        tree = feature.safe_get_current_tree()

        photos = feature.photos()
        (longitude, latitude) = feature.latlon.coords

        # create the observation
        _observation = inaturalist.create_observation(
            token,
            latitude,
            longitude,
            tree.species.common_name
        )
        observation = INaturalistObservation(
            observation_id=_observation['id'],
            map_feature=feature,
            tree=tree,
            submitted_at=datetime.datetime.now()
        )
        observation.save()

        for photo in tree.photos():
            time.sleep(10)
            photo_info = inaturalist.add_photo_to_observation(token, _observation['id'], photo)

            photo_observation = INaturalistPhoto(
                tree_photo=photo,
                observation=observation,
                inaturalist_photo_id=photo_info['photo_id']
            )
            photo_observation.save()

        # let's not get rate limited
        time.sleep(30)

    return


def inaturalist_sync(request, instance):
    inaturalist.sync_identifications()
