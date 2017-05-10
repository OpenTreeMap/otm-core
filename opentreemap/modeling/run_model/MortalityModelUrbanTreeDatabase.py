# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from copy import deepcopy
from random import random

from modeling.run_model.schema_helpers import (make_schema, obj,
                                               obj_list, string, number)

INCH_TO_CM = 2.54

DEFAULT_MORTALITY = 5
DIAMETER_BREAKS_COUNT = 4
DIAMETER_BREAKS = [
    5 * INCH_TO_CM,
    15 * INCH_TO_CM,
    25 * INCH_TO_CM,
    # Last break is implicitly >25
]

diameter_tuple_schema = {
    'type': 'array',
    'items': number,
    'minItems': DIAMETER_BREAKS_COUNT,
    'maxItems': DIAMETER_BREAKS_COUNT,
}


class MortalityModelUrbanTreeDatabase(object):
    schema = make_schema(obj({
        'default': number,
        'diameterBreaksCount': number,
        'mode': {
            'enum': ['default', 'speciesAndDiameters'],
        },
        'speciesAndDiameters': obj_list({
            'otmCode': string,
            'mortalityRates': diameter_tuple_schema,
        }),
    }))

    @classmethod
    def get_default_params(cls, instance):
        return deepcopy({
            'model_name': 'UrbanTreeDatabase',
            'version': 1,
            'params': {
                'default': DEFAULT_MORTALITY,
                'diameterBreaksCount': DIAMETER_BREAKS_COUNT,
                'mode': 'default',
                'speciesAndDiameters': [],
            }
        })

    def __init__(self, params, instance):
        self.mode = params['mode']
        self.default_mortality = params['default']
        self.mortality_bins_by_species = {}
        for row in params['speciesAndDiameters']:
            otm_code = row['otmCode']
            mortality_rates = row['mortalityRates']
            if otm_code == 'default':
                self.mortality_bins_default = mortality_rates
            else:
                self.mortality_bins_by_species[otm_code] = mortality_rates

    def init_tree(self, tree):
        pass

    # Kill trees for one year of the simulation.
    # Track the "remainder" for each category of trees. For example, if a
    # category has 48 trees and a mortality rate of 5%, instead of killing 2.4
    # trees we kill 2 and remember a remainder of .4 for next year.
    # Note that remainders can be negative since we round rather than truncate:
    #
    # year   tree count   float_to_kill   int_to_kill   remainder
    #   1        48         2.4 + 0            2           0.4
    #   2        46         2.3 + 0.4          3          -0.3

    def kill_trees(self, trees, remainders):
        categories = self._categorize(trees)
        new_remainders = {}
        for key, c in categories.iteritems():
            remainder = remainders.get(key, 0)
            float_to_kill = c.mortality * len(c.trees) + remainder
            int_to_kill = int(round(float_to_kill))
            new_remainders[key] = float_to_kill - int_to_kill

            for i in range(0, int_to_kill):
                index = int(random() * len(c.trees))
                tree = c.trees.pop(index)
                tree.is_alive = False

        live_trees = [t for t in trees if t.is_alive]
        dead_trees = [t for t in trees if not t.is_alive]

        return live_trees, dead_trees, new_remainders

    class Category(object):
        def __init__(self, mortality):
            self.trees = []
            self.mortality = mortality / 100.0

    def _categorize(self, trees):
        categories = {}
        for tree in trees:
            otm_code = tree.species.otm_code
            index = self._get_diameter_index(tree)
            key = (otm_code, index)
            if key not in categories:
                mortality = self._get_mortality(otm_code, index)
                categories[key] = self.Category(mortality)
            categories[key].trees.append(tree)
        return categories

    def _get_diameter_index(self, tree):
        i = 0
        while i < len(DIAMETER_BREAKS):
            if tree.diameter <= DIAMETER_BREAKS[i]:
                return i
            i += 1
        return i

    def _get_mortality(self, otm_code, index):
        if self.mode == 'default':
            return self.default_mortality
        elif self.mode == 'speciesAndDiameters':
            if otm_code in self.mortality_bins_by_species:
                return self.mortality_bins_by_species[otm_code][index]
            else:
                return self.mortality_bins_default[index]

        raise Exception('Mortality rate mode not supported "{}"'
                        .format(self.mode))
