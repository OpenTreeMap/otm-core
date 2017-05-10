# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import random
from copy import copy

from jsonschema import validate

from modeling.run_model.GrowthModelUrbanTreeDatabase import \
    GrowthModelUrbanTreeDatabase
from modeling.run_model.MortalityModelUrbanTreeDatabase import \
    MortalityModelUrbanTreeDatabase
from modeling.run_model.Tree import Tree


class GrowthAndMortalityModel(object):

    @classmethod
    def get_default_params(cls, instance):
        return {
            'growth': GrowthModelUrbanTreeDatabase.get_default_params(instance),  # NOQA
            'mortality': MortalityModelUrbanTreeDatabase.get_default_params(instance),  # NOQA
        }

    @classmethod
    def get_species_for_planting(cls, instance):
        return GrowthModelUrbanTreeDatabase.get_species_for_planting(instance)

    def __init__(self, params, instance):
        self.growth_model = self._init_growth_model(params['growth'], instance)
        self.mortality_model = self._init_mortality_model(params['mortality'],
                                                          instance)

    def _init_growth_model(self, params, instance):
        growth_params = params['params']
        model_name = params['model_name']
        if model_name == 'UrbanTreeDatabase':
            growth_model = GrowthModelUrbanTreeDatabase(growth_params,
                                                        instance)
        else:
            raise Exception('Invalid growth model name "%s"' % model_name)

        if growth_model.schema:
            validate(growth_params, growth_model.schema)

        return growth_model

    def _init_mortality_model(self, params, instance):
        mortality_params = params['params']
        model_name = params['model_name']
        if model_name == 'UrbanTreeDatabase':
            mortality_model = MortalityModelUrbanTreeDatabase(mortality_params,
                                                              instance)
        else:
            raise Exception('Invalid mortality model name "%s"' % model_name)

        if mortality_model.schema:
            validate(mortality_params, mortality_model.schema)

        return mortality_model

    def run(self, scenario):
        """
        Input scenario dictionary:
        { 'groups': [{
                     'name': optional identifier,
                     'species': species object,
                     'diameter': diameter (cm),
                     'count',
                     }, ...],
          'trees': [{
                     'name': optional identifier,
                     'species': species object,
                     'diameter': diameter (cm),
          'years': number of years to run,
          'replant_years': number of years to replant dead trees
        }

        Output:
            yearly_counts - number of living trees in each of years 0-n
            planted_trees - Tree object for each planted tree (if a tree dies
                            and is replanted, both will be in this list)
        """
        tree_specs = scenario['trees']
        group_specs = scenario['groups']
        n_years = int(scenario['years'])
        n_replant_years = int(scenario['replant_years'])

        # Use a fixed seed so results will be repeatable
        random.seed(42)

        # Build list of live trees
        live_trees = [Tree(self.growth_model, self.mortality_model, spec=spec)
                      for spec in tree_specs]
        for group in group_specs:
            live_trees += self._make_trees_for_group(group)

        for i, tree in enumerate(live_trees):
            tree.id = i

        return self._growth_kill_cycle(
            n_years, n_replant_years, live_trees)

    # ------------------------------------------------------------------------
    # Create trees

    def _make_trees_for_group(self, spec):
        n_trees = int(spec['count'])
        trees = [
            Tree(self.growth_model, self.mortality_model, spec=spec)
            for i in range(n_trees)
        ]
        return trees

    # ------------------------------------------------------------------------
    # Run model

    def _growth_kill_cycle(self, n_years, n_replant_years,
                           live_trees):
        planted_trees = copy(live_trees)
        yearly_counts = [len(live_trees)]
        remainders = {}

        for year in range(1, n_years + 1):
            # Select and kill trees
            live_trees, dead_trees, remainders = self.mortality_model \
                .kill_trees(live_trees, remainders)

            # Add growth to living trees
            for tree in live_trees:
                self.growth_model.grow_tree(tree, year)

            # Replant
            if year <= n_replant_years:
                new_trees = self._replant(dead_trees, year)
                planted_trees.extend(new_trees)
                live_trees.extend(new_trees)

            yearly_counts.append(len(live_trees))

        return yearly_counts, planted_trees

    def _replant(self, dead_trees, year):
        new_trees = [Tree(self.growth_model, self.mortality_model, tree=tree,
                          year_planted=year)
                     for tree in dead_trees]
        return new_trees
