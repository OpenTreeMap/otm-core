# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

# 3 tuples (error id, error descr, fatal)

######################################
# FILE LEVEL ERRORS
######################################
#
# Errors that are attributed to the file and prevent the
# rows from being loaded and validated.
#
EMPTY_FILE = (1, 'No rows found', True)
UNMATCHED_FIELDS = (3, "Unrecognized fields in header row", False)
MISSING_FIELD = (5, 'This field is required', True)
GENERIC_ERROR = (6, 'An exception was raised while uploading the file', True)

######################################
# ROW LEVEL ERRORS
######################################
#
# Errors that are attributed to rows
#
INVALID_GEOM = (10, 'Longitude must be between -180 and 180 and '
                'latitude must be betwen -90 and 90', True)

GEOM_OUT_OF_BOUNDS = (11, 'Geometry must be inside the map bounds', True)

EXCL_ZONE = (12, 'Geometry may not be in an exclusion zone', True)

INVALID_SPECIES = (20, 'Could not find species with the given '
                   'scientific name.', True)
DUPLICATE_SPECIES = (21, 'More than one species matches the given '
                     'scientific name.', True)

INVALID_OTM_ID = (30, 'The given Open Tree Map ID does not exist '
                  'in the system. This ID is automatically generated '
                  'by Open Tree Map and should only be used for '
                  'updating existing records', True)

FLOAT_ERROR = (40, 'Not formatted as a number', True)
POS_FLOAT_ERROR = (41, 'Not formatted as a positive number', True)
INT_ERROR = (42, 'Not formatted as an integer', True)
POS_INT_ERROR = (43, 'Not formatted as a positive integer', True)
BOOL_ERROR = (44, 'Not formatted as a boolean', True)
STRING_TOO_LONG = (45, 'Strings must be less than 255 characters', True)
INVALID_DATE = (46, 'Invalid date (must by YYYY-MM-DD', True)

INVALID_UDF_VALUE = (50, 'Invalid value for custom field', True)

INVALID_ITREE_REGION = (60, 'Unknown i-Tree region', True)
ITREE_REGION_NOT_IN_INSTANCE = (61, "i-Tree region not valid for this treemap",
                                True)
INVALID_ITREE_CODE = (62, 'Unknown i-Tree code', True)
ITREE_CODE_NOT_IN_REGION = (63, 'i-Tree code not defined for region', True)
INSTANCE_HAS_NO_ITREE_REGION = (64, 'This treemap intersects no i-Tree '
                                'regions and has no default region', True)
INSTANCE_HAS_MULTIPLE_ITREE_REGIONS = (65, 'This treemap intersects more than '
                                       'one i-Tree region', True)

MERGE_REQUIRED = (71, 'This row must be merged', False)

NEARBY_TREES = (1050, 'There are already trees very close to this one', False)

SPECIES_DBH_TOO_HIGH = (1060,
                        'The diameter is too large for this species',
                        False)

SPECIES_HEIGHT_TOO_HIGH = (1061,
                           'The height is too large for this species',
                           False)
