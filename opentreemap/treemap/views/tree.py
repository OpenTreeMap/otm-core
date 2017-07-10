# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import hashlib

from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.utils.translation import ungettext
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.http import HttpResponseRedirect

from treemap.search import Filter
from treemap.models import Tree, Plot
from treemap.ecobenefits import get_benefits_for_filter
from treemap.ecocache import get_cached_plot_count
from treemap.lib import format_benefits
from treemap.lib.tree import add_tree_photo_helper
from treemap.lib.photo import context_dict_for_photo


def tree_detail(request, instance, feature_id, tree_id):
    return HttpResponseRedirect(reverse('map_feature_detail', kwargs={
        'instance_url_name': instance.url_name,
        'feature_id': feature_id}))


def add_tree_photo(request, instance, feature_id, tree_id=None):
    error = None
    try:
        __, tree = add_tree_photo_helper(
            request, instance, feature_id, tree_id)
        photos = tree.photos()
    except ValidationError as e:
        trees = Tree.objects.filter(pk=tree_id)
        if len(trees) == 1:
            photos = trees[0].photos()
        else:
            photos = []
        # TODO: Better display error messages in the view
        error = '; '.join(e.messages)
    return {'photos': [context_dict_for_photo(request, photo)
                       for photo in photos],
            'error': error}


@transaction.atomic
def delete_tree(request, instance, feature_id, tree_id):
    InstanceTree = instance.scope_model(Tree)
    tree = get_object_or_404(InstanceTree, pk=tree_id, plot_id=feature_id)
    tree.delete_with_user(request.user)
    return {'ok': True}


def search_tree_benefits(request, instance):
    filter_str = request.GET.get('q', '')
    display_str = request.GET.get('show', '')

    hide_summary_text = request.GET.get('hide_summary', 'false')
    hide_summary = hide_summary_text.lower() == 'true'

    filter = Filter(filter_str, display_str, instance)
    total_plots = get_cached_plot_count(filter)

    benefits, basis = get_benefits_for_filter(filter)

    # Inject the plot count as a basis for tree benefit calcs
    basis.get('plot', {})['n_plots'] = total_plots

    formatted = format_benefits(instance, benefits, basis, digits=0)

    n_trees = basis['plot']['n_total']
    n_plots = basis['plot']['n_plots']
    n_empty_plots = n_plots - n_trees
    n_resources = 0

    tree_count_label = ungettext('tree', 'trees', n_trees) + ','
    empty_plot_count_label = ungettext(
        'empty planting site', 'empty planting sites', n_empty_plots)
    has_resources = instance.has_resources and 'resource' in basis
    if has_resources:
        n_resources = basis['resource']['n_total']
        empty_plot_count_label += ','

    context = {
        'n_trees': n_trees,
        'n_empty_plots': n_empty_plots,
        'n_resources': n_resources,
        'tree_count_label': tree_count_label,
        'empty_plot_count_label': empty_plot_count_label,
        'has_resources': has_resources,
        'hide_summary': hide_summary,
        'single_result': _single_result_context(instance, n_plots, n_resources,
                                                filter)
    }
    context.update(formatted)
    return context


def _single_result_context(instance, n_plots, n_resources, filter):
    # If search found just one feature, return its id and location
    if n_plots + n_resources != 1:
        return None
    else:
        if n_plots == 1:
            qs = filter.get_objects(Plot)
        else:  # n_resources == 1
            for Resource in instance.resource_classes:
                qs = filter.get_objects(Resource)
                if qs.count() == 1:
                    break
        feature = qs[0]
        latlon = feature.latlon
        return {
            'id': feature.id,
            'lon': latlon.x,
            'lat': latlon.y,
        }


def ecobenefits_hash(request, instance):
    universal_rev = str(instance.universal_rev)

    eco_conversion = instance.eco_benefits_conversion

    if eco_conversion:
        eco_str = eco_conversion.hash
    else:
        eco_str = 'none'

    map_features = ','.join(instance.map_feature_types)

    string_to_hash = universal_rev + ":" + eco_str + ":" + map_features

    return hashlib.md5(string_to_hash).hexdigest()
