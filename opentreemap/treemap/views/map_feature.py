# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
import hashlib
from functools import wraps

from django.http import HttpResponse
from django.template import RequestContext, TemplateDoesNotExist
from django.template.loader import get_template
from django.shortcuts import get_object_or_404, render_to_response
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import transaction
from django.contrib.gis.geos import Point, MultiPolygon, Polygon
from django.contrib.gis.db.models import GeometryField

from opentreemap.util import dotted_split
from treemap.lib.hide_at_zoom import (update_hide_at_zoom_after_move,
                                      update_hide_at_zoom_after_delete)

from treemap.units import Convertible
from treemap.models import (Tree, Species, MapFeature,
                            MapFeaturePhoto, Favorite)
from treemap.util import (package_field_errors, to_object_name)

from treemap.images import get_image_from_request
from treemap.lib.photo import context_dict_for_photo
from treemap.lib.object_caches import udf_defs
from treemap.lib.map_feature import (get_map_feature_or_404,
                                     raise_non_instance_404,
                                     context_dict_for_plot,
                                     context_dict_for_resource,
                                     context_dict_for_map_feature)
from treemap.lib.perms import map_feature_is_deletable
from treemap.views.misc import add_map_info_to_context


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
    return feature.add_photo(data, request.user)


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
                'error': error}

    return wrapper


def map_feature_detail(request, instance, feature_id,
                       render=False, edit=False):
    feature = get_map_feature_or_404(feature_id, instance)

    ctx_fn = (context_dict_for_plot if feature.is_plot
              else context_dict_for_resource)
    context = ctx_fn(request, feature, edit=edit)
    add_map_info_to_context(context, instance)

    if render:
        if feature.is_plot:
            template = 'treemap/plot_detail.html'
        else:
            app = feature.__module__.split('.')[0]
            try:
                template = '%s/%s_detail.html' % (app, feature.feature_type)
                get_template(template)
            except TemplateDoesNotExist:
                template = 'treemap/resource_detail.html'
        return render_to_response(template, context,
                                  RequestContext(request))
    else:
        return context


def render_map_feature_detail(request, instance, feature_id, **kwargs):
    return map_feature_detail(request, instance, feature_id, render=True,
                              **kwargs)


def context_map_feature_detail(request, instance, feature_id, **kwargs):
    return map_feature_detail(request, instance, feature_id, render=False,
                              **kwargs)


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
            get_template(template)
        except:
            template = 'treemap/resource_add.html'
        return render_to_response(template,
                                  {'object_name': to_object_name(type)},
                                  RequestContext(request))
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
    if not map_feature_is_deletable(request.user.get_instance_user(instance),
                                    feature):
        raise ValidationError("map feature not deletable")
    feature.delete_with_user(request.user)
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
            return package_field_errors(thing._model_name, e)

    tree = None

    rev_updates = ['universal_rev']
    old_geom = feature.geom
    for (identifier, value) in request_dict.iteritems():
        split_template = 'Malformed request - invalid field %s'
        object_name, field = dotted_split(identifier, 2,
                                          failure_format_string=split_template)
        if (object_name not in feature_object_names + ['tree']):
            raise Exception(split_template % identifier)

        tree_udfc_names = [fdef.canonical_name
                           for fdef in udf_defs(feature.instance, 'Tree')
                           if fdef.iscollection]

        if ((field in tree_udfc_names and
             feature.safe_get_current_tree() is None and
             value == [])):
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
            raise Exception(
                'Malformed request - invalid model %s' % object_name)

        set_attr_on_model(model, field, value)

        field_class = model._meta.get_field_by_name(field)[0]
        if isinstance(field_class, GeometryField):
            rev_updates.append('geo_rev')
            rev_updates.append('eco_rev')
        elif identifier in ['tree.species', 'tree.diameter']:
            rev_updates.append('eco_rev')

    errors = {}

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
    orientation = request.REQUEST.get('degrees', None)
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


def map_feature_popup(request, instance, feature_id):
    feature = get_map_feature_or_404(feature_id, instance)
    context = context_dict_for_map_feature(request, feature)
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
            return render_to_response('treemap/partials/canopy_popup.html',
                                      {'boundaries_with_canopy': result},
                                      RequestContext(request))
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
