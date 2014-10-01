# 3 tuples (error id, error descr, fatal)
from importer.fields import trees


EMPTY_FILE = (1, 'No rows found', True)
MISSING_POINTS = (2, 'You must specify a "%s" and "%s" field' %\
                  (trees.POINT_X, trees.POINT_Y), True)

UNMATCHED_FIELDS = (3, "Some fields in the uploaded dataset "\
                    "didn't match the template", False)

MISSING_SPECIES_FIELDS = (4, 'You must specify i-Tree Code, Common Name '\
                          'Genus and Species', True)

MISSING_FIELD = (5, 'This field is required', True)
GENERIC_ERROR = (6, 'There was an exception', True)

INVALID_GEOM = (10, 'Longitude must be between -180 and 180 and '\
                'latitude must be betwen -90 and 90', True)

GEOM_OUT_OF_BOUNDS = (11, 'Geometry must be in a neighborhood', True)

EXCL_ZONE = (12, 'Geometry may not be in an exclusion zone', True)

INVALID_SPECIES = (20, 'Could not find matching species', True)

INVALID_OTM_ID = (30, 'The given Open Tree Map ID does not exist '\
                  'in the system. This ID is automatically generated '\
                  'by Open Tree Map and should only be used for '\
                  'updating existing records', True)

FLOAT_ERROR = (40, 'Not formatted as a number', True)
POS_FLOAT_ERROR = (41, 'Not formatted as a positive number', True)
INT_ERROR = (42, 'Not formatted as an integer', True)
POS_INT_ERROR = (43, 'Not formatted as a positive integer', True)
BOOL_ERROR = (44, 'Not formatted as a boolean', True)
STRING_TOO_LONG = (45, 'Strings must be less than 255 characters', True)
INVALID_DATE = (46, 'Invalid date (must by YYYY-MM-DD', True)

INVALID_CHOICE = (50, 'These fields must contain a choice value', True)

INVALID_ITREE_CODE = (60, "iTree doesn't exist", True)
MISSING_ITREE_CODE = (61, 'iTree code is missing', True)

TOO_MANY_SPECIES = (70, 'More than one species was matched by this row', False)
MERGE_REQ = (71, 'This row must be merged', False)

NEARBY_TREES = (1050, 'There are already trees very close to this one', False)

SPECIES_DBH_TOO_HIGH = (1060,
                        'The diameter is too large for this species',
                        False)

SPECIES_HEIGHT_TOO_HIGH = (1061,
                           'The height is too large for this species',
                           False)
