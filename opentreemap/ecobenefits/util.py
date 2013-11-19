# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.utils.translation import ugettext as trans
from django.db.models.query import QuerySet

_benefit_labels = {
    # Translators: 'Energy' is the name of an eco benefit
    'energy':     trans('Energy'),
    # Translators: 'Stormwater' is the name of an eco benefit
    'stormwater': trans('Stormwater'),
    # Translators: 'Carbon Dioxide' is the name of an eco benefit
    'co2':        trans('Carbon Dioxide'),
    # Translators: 'Air Quality' is the name of an eco benefit
    'airquality': trans('Air Quality')
}


def get_benefit_label(benefit_name):
    return _benefit_labels[benefit_name]


def get_trees_for_eco(trees):
    """
    Converts a QuerySet of trees, a single tree, or any iterable of trees into
    input appropriate for _benefits_for_trees
    """
    if isinstance(trees, QuerySet):
        return trees.exclude(species__otm_code__isnull=True)\
                    .exclude(diameter__isnull=True)\
                    .values('diameter', 'species__otm_code', 'plot__geom')

    if not hasattr(trees, '__iter__'):
        trees = (trees,)

    return [{'diameter': tree.diameter,
             'species__otm_code': tree.species.otm_code,
             'plot__geom': tree.plot.geom}
            for tree in trees
            if tree.diameter is not None and tree.species is not None]
