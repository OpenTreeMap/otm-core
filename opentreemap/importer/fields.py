# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


class species(object):
    GENUS = 'genus'
    SPECIES = 'species'
    CULTIVAR = 'cultivar'
    OTHER_PART_OF_NAME = 'other part of name'
    COMMON_NAME = 'common name'
    USDA_SYMBOL = 'usda symbol'
    ITREE_CODE = 'i-tree code'

    # This is a pseudo field which is filled in
    # when a matching species is found, but before
    # a commit is made. It is a list of all species
    # that somehow match this one (usda, sci name)
    POSSIBLE_MATCHES = 'calc__species'

    # This is a pseudo field which is filled in
    # when a matching itree code is found
    ITREE_PAIRS = 'calc__itree'

    IS_NATIVE = 'is native'
    GENDER = 'gender'
    FALL_CONSPICUOUS = 'fall conspicuous'
    PALATABLE_HUMAN = 'palatable human'
    FLOWER_CONSPICUOUS = 'flower conspicuous'
    FLOWERING_PERIOD = 'flowering period'
    FRUIT_OR_NUT_PERIOD = 'fruit or nut period'
    HAS_WILDLIFE_VALUE = 'has wildlife value'
    MAX_DIAMETER = 'max diameter'
    MAX_HEIGHT = 'max height'
    FACT_SHEET_URL = 'fact sheet url'
    PLANT_GUIDE_URL = 'plant guide url'
    TREE_COUNT = 'number of trees in database'
    ID = 'database id of species'
    SCIENTIFIC_NAME = 'scientific name'

    # TODO: support i18n
    CHOICE_MAP = {
        FLOWERING_PERIOD: ['spring', 'summer', 'fall', 'winter'],
        FRUIT_OR_NUT_PERIOD: ['spring', 'summer', 'fall', 'winter'],
    }

    DATE_FIELDS = set()

    STRING_FIELDS = {GENUS, SPECIES, CULTIVAR, OTHER_PART_OF_NAME, COMMON_NAME,
                     USDA_SYMBOL, ITREE_CODE, GENDER, FACT_SHEET_URL,
                     PLANT_GUIDE_URL}

    POS_FLOAT_FIELDS = {MAX_DIAMETER, MAX_HEIGHT}

    FLOAT_FIELDS = set()

    POS_INT_FIELDS = set()

    BOOLEAN_FIELDS = {IS_NATIVE, FALL_CONSPICUOUS, PALATABLE_HUMAN,
                      FLOWER_CONSPICUOUS, HAS_WILDLIFE_VALUE}

    ALL = DATE_FIELDS | STRING_FIELDS | POS_FLOAT_FIELDS | \
        FLOAT_FIELDS | POS_INT_FIELDS | BOOLEAN_FIELDS | \
        set(CHOICE_MAP.keys())

    PLOT_CHOICES = set()


class trees(object):
    # X/Y are required
    POINT_X = 'point x'
    POINT_Y = 'point y'

    # This is a pseudo field which is filled in
    # when data is cleaned and contains a GEOS
    # point object
    POINT = 'calc__point'

    # This is a pseudo field which is filled in
    # when data is cleaned and may contain a
    # OTM Species object, if the species was
    # matched
    SPECIES_OBJECT = 'calc__species_object'

    # Plot Fields
    ADDRESS = 'address'
    PLOT_WIDTH = 'plot width'
    PLOT_LENGTH = 'plot length'

    READ_ONLY = 'read only'
    OPENTREEMAP_ID_NUMBER = 'opentreemap id number'
    ORIG_ID_NUMBER = 'original id number'

    TREE_PRESENT = 'tree present'  # TODO: Remove?

    # Choice fields
    PLOT_TYPE = 'plot type'  # TODO: Remove?
    POWERLINE_CONFLICT = 'powerline conflict'  # TODO: Remove?
    SIDEWALK = 'sidewalk'  # TODO: Remove?

    # Tree Fields
    GENUS = 'genus'
    SPECIES = 'species'
    CULTIVAR = 'cultivar'
    OTHER_PART_OF_NAME = 'other part of name'
    DIAMETER = 'diameter'
    TREE_HEIGHT = 'tree height'
    CANOPY_HEIGHT = 'canopy height'
    DATE_PLANTED = 'date planted'
    DATA_SOURCE = 'data source'
    OWNER = 'tree owner'  # TODO: Remove?
    SPONSOR = 'tree sponsor'  # TODO: Remove?
    STEWARD = 'tree steward'  # TODO: Remove?
    NOTES = 'notes'  # TODO: Remove?
    URL = 'tree url'  # TODO: Remove?

    # TODO: None of these are part of tree or plot anymore.  Remove?
    # Choice Fields
    TREE_CONDITION = 'condition'
    CANOPY_CONDITION = 'canopy condition'
    ACTIONS = 'actions'
    PESTS = 'pests and diseases'
    LOCAL_PROJECTS = 'local projects'

    # Some plot choice fields aren't automatically
    # converting to choice values. This set determine
    # which are pre-converted
    PLOT_CHOICES = {
        PLOT_TYPE,
        SIDEWALK,
        POWERLINE_CONFLICT
    }

    CHOICE_MAP = {
        PLOT_TYPE: 'plot_types',
        POWERLINE_CONFLICT: 'powerlines',
        SIDEWALK: 'sidewalks',
        TREE_CONDITION: 'conditions',
        CANOPY_CONDITION: 'canopy_conditions',
        ACTIONS: 'actions',
        PESTS: 'pests',
        LOCAL_PROJECTS: 'projects'
    }

    DATE_FIELDS = {DATE_PLANTED}

    STRING_FIELDS = {ADDRESS, GENUS, SPECIES, CULTIVAR, OTHER_PART_OF_NAME,
                     URL, NOTES, OWNER, SPONSOR, STEWARD, DATA_SOURCE,
                     LOCAL_PROJECTS, NOTES, ORIG_ID_NUMBER}

    POS_FLOAT_FIELDS = {PLOT_WIDTH, PLOT_LENGTH, DIAMETER, TREE_HEIGHT,
                        CANOPY_HEIGHT}

    FLOAT_FIELDS = {POINT_X, POINT_Y}

    POS_INT_FIELDS = {OPENTREEMAP_ID_NUMBER}

    BOOLEAN_FIELDS = {READ_ONLY, TREE_PRESENT}

    ALL = {POINT_X, POINT_Y, ADDRESS, PLOT_WIDTH, PLOT_LENGTH, READ_ONLY,
           OPENTREEMAP_ID_NUMBER, TREE_PRESENT, PLOT_TYPE, POWERLINE_CONFLICT,
           SIDEWALK, GENUS, SPECIES, CULTIVAR, OTHER_PART_OF_NAME, DIAMETER,
           ORIG_ID_NUMBER, CANOPY_HEIGHT, DATE_PLANTED, TREE_CONDITION,
           CANOPY_CONDITION, ACTIONS, PESTS, LOCAL_PROJECTS, URL, NOTES, OWNER,
           SPONSOR, STEWARD, DATA_SOURCE, TREE_HEIGHT}
