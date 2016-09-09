# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import hashlib

from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.http import HttpResponseRedirect

from treemap.search import Filter
from treemap.models import Tree
from treemap.audit import Audit
from treemap.ecobenefits import get_benefits_for_filter
from treemap.ecobenefits import BenefitCategory
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
    filter_str = request.REQUEST.get('q', '')
    display_str = request.REQUEST.get('show', '')

    hide_summary_text = request.REQUEST.get('hide_summary', 'false')
    hide_summary = hide_summary_text.lower() == 'true'

    filter = Filter(filter_str, display_str, instance)
    total_plots = get_cached_plot_count(filter)

    benefits, basis = get_benefits_for_filter(filter)

    # Inject the plot count as a basis for tree benefit calcs
    basis.get('plot', {})['n_plots'] = total_plots

    # We also want to inject the total currency amount saved
    # for plot-based items except CO2 stored
    total_currency_saved = 0

    for benefit_name, benefit in benefits.get('plot', {}).iteritems():
        if benefit_name != BenefitCategory.CO2STORAGE:
            currency = benefit.get('currency', 0.0)
            if currency:
                total_currency_saved += currency

    # save it as if it were a normal benefit so we get formatting
    # and currency conversion
    benefits.get('plot', {})['totals'] = {
        'value': None,
        'currency': total_currency_saved,
        'label': _('Total annual benefits')
    }

    formatted = format_benefits(instance, benefits, basis, digits=0)

    n_trees = basis['plot']['n_total']
    n_plots = basis['plot']['n_plots']
    n_empty_plots = n_plots - n_trees
    n_resources = 0

    tree_count_label = _('tree') if n_trees == 1 else _('trees')
    tree_count_label += ','
    empty_plot_count_label = (
        _('empty planting site') if n_empty_plots == 1 else
        _('empty planting sites'))
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
        'hide_summary': hide_summary
    }
    context.update(formatted)
    return context


def search_hash(request, instance):
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

    map_features = ','.join(instance.map_feature_types)

    string_to_hash = audit_id_str + ":" + eco_str + ":" + map_features

    return hashlib.md5(string_to_hash).hexdigest()
