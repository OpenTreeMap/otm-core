# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


class Tree(object):
    def __init__(self, growth_model, mortality_model,
                 spec=None, tree=None, year_planted=0):

        if spec:
            self.name = spec.get('name')
            self.initial_diameter = spec['diameter']
            self.species = spec['species']

        elif tree:  # replant
            self.name = tree.name
            self.initial_diameter = tree.initial_diameter
            self.species = tree.species

        else:
            raise Exception('Internal error, no spec or tree')

        self.id = None  # set by caller
        self.is_alive = True
        self.year_planted = year_planted
        self.yearly_diameters = []

        growth_model.init_tree(self)
        mortality_model.init_tree(self)

    @property
    def diameter(self):
        if len(self.yearly_diameters) == 0:
            return self.initial_diameter
        else:
            return self.yearly_diameters[-1]

    def grow(self, rate):
        self.yearly_diameters.append(self.diameter + rate)

    def diameters_for_eco(self):
        """
        Return list of diameters by year, starting with year 1 and
        excluding initial diameter.
        For example, if planted in year 2 with diameter 1.0, returns
            [0, 0, 1.43, 1.91, ...]
        """
        if self.year_planted == 0:
            return self.yearly_diameters
        else:
            diameters = [0 for i in range(0, self.year_planted)]
            diameters.extend(self.yearly_diameters)
            return diameters

    def diameters_for_export(self):
        """
        Return list of diameters by year, starting with year 0 and
        including initial diameter.
        For example, if planted in year 2 with diameter 1.0, returns
            [0, 0, 1.0, 1.43, 1.91, ...]
        """
        if self.year_planted == 0:
            diameters = [self.initial_diameter]
        else:
            diameters = [0 for i in range(0, self.year_planted)]
            diameters.append(self.initial_diameter)

        diameters.extend(self.yearly_diameters)
        return diameters

    def summary(self):
        return {
            'id': self.id,
            'name': self.name,
            'species': self.species,
            'diameter': self.diameter,
        }
