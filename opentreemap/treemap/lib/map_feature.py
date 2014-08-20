# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import datetime

from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as trans
from django.db.models import Q

from treemap.audit import Audit
from treemap.ecobackend import BAD_CODE_PAIR
from treemap.models import Tree, MapFeature, User

from treemap.lib import format_benefits
from treemap.lib.photo import context_dict_for_photo


def _map_feature_audits(user, instance, feature, filters=None,
                        cudf_filters=None):
    if filters is None:
        filters = []
    if cudf_filters is None:
        cudf_filters = []

    readable_plot_fields = feature.visible_fields(user)

    feature_filter = Q(model=feature.feature_type, model_id=feature.pk,
                       field__in=readable_plot_fields)
    filters.append(feature_filter)

    feature_collection_udfs_filter = Q(
        model__in=feature.visible_collection_udfs_audit_names(user),
        model_id__in=feature.collection_udfs_audit_ids())
    cudf_filters.append(feature_collection_udfs_filter)

    # Seems to be much faster to do three smaller
    # queries here instead of ORing them together
    # (about a 50% inprovement!)
    # TODO: Verify this is still the case now that we are also getting
    # collection udf audits
    iaudit = Audit.objects\
        .filter(instance=instance)\
        .exclude(user=User.system_user())

    audits = []
    for afilter in filters:
        audits += list(iaudit.filter(afilter).order_by('-created')[:5])

    # UDF collection audits have some fields which aren't very useful to show
    udf_collection_exclude_filter = Q(
        field__in=['model_id', 'field_definition'])

    for afilter in cudf_filters:
        audits += list(iaudit.filter(afilter)
                             .exclude(udf_collection_exclude_filter)
                             .order_by('-created')[:5])

    audits = sorted(audits, key=lambda audit: audit.updated, reverse=True)[:5]

    return audits


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
        context.update(format_benefits(instance, benefits, basis))


def _plot_audits(user, instance, plot):
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

    filters = [tree_filter, tree_delete_filter]
    cudf_filters = [tree_collection_udfs_filter]

    audits = _map_feature_audits(user, instance, plot, filters, cudf_filters)

    return audits


def _add_audits_to_context(audits, context):
    def _audits_are_in_different_groups(prev_audit, audit):
        if prev_audit is None:
            return True
        elif prev_audit.user_id != audit.user_id:
            return True
        else:
            time_difference = last_audit.created - audit.created
            return time_difference > datetime.timedelta(days=1)

    audit_groups = []
    current_audit_group = None
    last_audit = None

    for audit in audits:
        if _audits_are_in_different_groups(last_audit, audit):
            current_audit_group = {
                'created': audit.created,
                'user': audit.user,
                'audits': []}
            audit_groups.append(current_audit_group)
        current_audit_group['audits'].append(audit)
        last_audit = audit
    # Converting the audit groups to tuples makes the template code cleaner
    context['recent_activity'] = [
        (ag['user'], ag['created'], ag['audits']) for ag in audit_groups]

    if len(audits) > 0:
        context['latest_update'] = audits[0]
    else:
        context['latest_update'] = None


def get_map_feature_or_404(feature_id, instance, type=None):
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


def context_dict_for_plot(request, plot, edit=False, tree_id=None):
    context = context_dict_for_map_feature(request, plot)

    if edit:
        context['editmode'] = edit

    instance = request.instance
    user = request.user

    if tree_id:
        tree = get_object_or_404(Tree,
                                 instance=instance,
                                 plot=plot,
                                 pk=tree_id)
    else:
        tree = plot.current_tree()

    if tree:
        tree.convert_to_display_units()

    if tree is not None:
        photos = tree.photos()
        # can't send a regular photo qs because the API will
        # serialize this to JSON, which is not supported for qs
        context['photos'] = map(context_dict_for_photo, photos)
    else:
        photos = []

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

    url_kwargs = {'instance_url_name': instance.url_name,
                  'feature_id': plot.pk}
    if tree:
        url_name = 'add_photo_to_tree'
        url_kwargs = dict(url_kwargs.items() + [('tree_id', tree.pk)])
    else:
        url_name = 'add_photo_to_plot'

    context['upload_photo_endpoint'] = reverse(url_name, kwargs=url_kwargs)

    context['plot'] = plot
    context['has_tree'] = tree is not None
    # Give an empty tree when there is none in order to show tree fields easily
    context['tree'] = tree or Tree(plot=plot, instance=instance)

    audits = _plot_audits(user, instance, plot)

    _add_audits_to_context(audits, context)

    return context


def context_dict_for_resource(request, resource):
    context = context_dict_for_map_feature(request, resource)
    instance = request.instance

    # Give them 2 for adding the resource and answering its questions
    total_progress_items = 3
    completed_progress_items = 2

    photos = resource.photos()
    context['photos'] = map(context_dict_for_photo, photos)

    has_photos = len(photos) > 0

    if has_photos:
        completed_progress_items += 1

    context['upload_photo_endpoint'] = reverse(
        'add_photo_to_map_feature',
        kwargs={'instance_url_name': instance.url_name,
                'feature_id': resource.pk})

    context['progress_percent'] = int(100 * (
        completed_progress_items / total_progress_items) + .5)

    context['progress_messages'] = []
    if not has_photos:
        context['progress_messages'].append(trans('Add a photo'))

    audits = _map_feature_audits(request.user, request.instance, resource)

    _add_audits_to_context(audits, context)

    return context


def context_dict_for_map_feature(request, feature):
    instance = request.instance
    if instance.pk != feature.instance_id:
        raise Exception("Invalid instance, does not match map feature")

    feature.instance = instance  # save a DB lookup

    user = request.user
    if user and user.is_authenticated():
        feature.mask_unauthorized_fields(user)

    feature.convert_to_display_units()

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
        'upload_photo_endpoint': None,
        'photos': None,
    }

    _add_eco_benefits_to_context_dict(instance, feature, context)

    return context
