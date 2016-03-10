# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


class species(object):
    # Fields of the OTM Species object
    GENUS = 'genus'
    SPECIES = 'species'
    CULTIVAR = 'cultivar'
    OTHER_PART_OF_NAME = 'other part of name'
    COMMON_NAME = 'common name'
    IS_NATIVE = 'is native'
    FLOWERING_PERIOD = 'flowering period'
    FRUIT_OR_NUT_PERIOD = 'fruit or nut period'
    FALL_CONSPICUOUS = 'fall conspicuous'
    FLOWER_CONSPICUOUS = 'flower conspicuous'
    PALATABLE_HUMAN = 'palatable human'
    HAS_WILDLIFE_VALUE = 'has wildlife value'
    FACT_SHEET_URL = 'fact sheet url'
    PLANT_GUIDE_URL = 'plant guide url'
    MAX_DIAMETER = 'max diameter'
    MAX_HEIGHT = 'max height'

    # Other import and/or export fields
    ID = 'database id of species'
    ITREE_CODE = 'i-tree code'

    # This is a pseudo field which is filled in
    # when a matching species is found, but before
    # a commit is made. It is a list of all species
    # that somehow match this one (usda, sci name)
    POSSIBLE_MATCHES = 'calc__species'

    # This is a pseudo field which is filled in
    # when a matching itree code is found
    ITREE_PAIRS = 'calc__itree'

    DATE_FIELDS = set()

    STRING_FIELDS = {GENUS, SPECIES, CULTIVAR, OTHER_PART_OF_NAME,
                     COMMON_NAME, ITREE_CODE, FLOWERING_PERIOD,
                     FRUIT_OR_NUT_PERIOD, FACT_SHEET_URL,
                     PLANT_GUIDE_URL}

    POS_FLOAT_FIELDS = {MAX_DIAMETER, MAX_HEIGHT}

    FLOAT_FIELDS = set()

    POS_INT_FIELDS = set()

    BOOLEAN_FIELDS = {IS_NATIVE, FALL_CONSPICUOUS, PALATABLE_HUMAN,
                      FLOWER_CONSPICUOUS, HAS_WILDLIFE_VALUE}

    # Note: this is a tuple and not a set so it will be ordered in exports
    ALL = (GENUS, SPECIES, CULTIVAR, OTHER_PART_OF_NAME, ITREE_CODE,
           COMMON_NAME, IS_NATIVE, FLOWERING_PERIOD, FRUIT_OR_NUT_PERIOD,
           FALL_CONSPICUOUS, FLOWER_CONSPICUOUS, PALATABLE_HUMAN,
           HAS_WILDLIFE_VALUE, FACT_SHEET_URL, PLANT_GUIDE_URL, MAX_DIAMETER,
           MAX_HEIGHT)

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
    STREET_ADDRESS = 'street address'
    CITY_ADDRESS = 'city'
    POSTAL_CODE = 'postal code'
    PLOT_WIDTH = 'planting site width'
    PLOT_LENGTH = 'planting site length'

    # TODO: READONLY restore when implemented
    # READ_ONLY = 'read only'

    OPENTREEMAP_PLOT_ID = 'planting site id'
    EXTERNAL_ID_NUMBER = 'owner original id'

    TREE_PRESENT = 'tree present'

    # Tree Fields (species matching)
    GENUS = species.GENUS
    SPECIES = species.SPECIES
    CULTIVAR = species.CULTIVAR
    OTHER_PART_OF_NAME = species.OTHER_PART_OF_NAME
    COMMON_NAME = species.COMMON_NAME

    # Tree fields
    DIAMETER = 'diameter'
    TREE_HEIGHT = 'tree height'
    CANOPY_HEIGHT = 'canopy height'
    DATE_PLANTED = 'date planted'
    DATE_REMOVED = 'date removed'

    # order matters, so this is a tuple and not a set
    SPECIES_FIELDS = (GENUS, SPECIES, CULTIVAR, OTHER_PART_OF_NAME,
                      COMMON_NAME)

    DATE_FIELDS = {DATE_PLANTED, DATE_REMOVED}

    STRING_FIELDS = {STREET_ADDRESS, CITY_ADDRESS, POSTAL_CODE, GENUS,
                     SPECIES, CULTIVAR, OTHER_PART_OF_NAME, COMMON_NAME,
                     EXTERNAL_ID_NUMBER}

    POS_FLOAT_FIELDS = {PLOT_WIDTH, PLOT_LENGTH, DIAMETER, TREE_HEIGHT,
                        CANOPY_HEIGHT}

    FLOAT_FIELDS = {POINT_X, POINT_Y}

    POS_INT_FIELDS = {OPENTREEMAP_PLOT_ID}

    # TODO: READONLY restore when implemented
    BOOLEAN_FIELDS = {TREE_PRESENT}

    EXPORTER_PAIRS = (
        ('geom__x', POINT_X),
        ('geom__y', POINT_Y),
        ('address_street', STREET_ADDRESS),
        ('address_city', CITY_ADDRESS),
        ('address_zip', POSTAL_CODE),
        ('width', PLOT_WIDTH),
        ('length', PLOT_LENGTH),
        ('id', OPENTREEMAP_PLOT_ID),
        ('owner_orig_id', EXTERNAL_ID_NUMBER),
        ('tree_present', TREE_PRESENT),
        ('tree__species__genus', GENUS),
        ('tree__species__species', SPECIES),
        ('tree__species__cultivar', CULTIVAR),
        ('tree__species__other_part_of_name', OTHER_PART_OF_NAME),
        ('tree__species__common_name', COMMON_NAME),
        ('tree__diameter', DIAMETER),
        ('tree__height', TREE_HEIGHT),
        ('tree__canopy_height', CANOPY_HEIGHT),
        ('tree__date_planted', DATE_PLANTED),
        ('tree__date_removed', DATE_REMOVED),
    )

    # TODO: READONLY restore when implemented
    # Note: this is a tuple and not a set so it will be ordered in exports
    ALL = tuple([p[1] for p in EXPORTER_PAIRS])
