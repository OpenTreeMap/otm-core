from treemap.models import (User, Plot, Tree, Species,
                            Audit, TreePhoto, Boundary)

from threadedcomments.models import ThreadedComment

from otm1_migrator.data_util import (coerce_null_boolean,
                                     coerce_null_string,
                                     correct_none_string)

from django.contrib.gis.geos import fromstr

# model specification:
#
# model_class:        the django class object used to instantiate objects
#
# dependencies:       a mapping where keys are the names of models that
#                     must also be in the MIGRATION_RULES dict and values are
#                     the names of fields for the current OTM2 model that have
#                     foreign key relationships to their dependency OTM2 models
#
# common_fields:      fields that must be in the provided data and the otm2
#                     django model.
# renamed_fields:     a mapping where keys are fields in the provided data
#                     and values are their names in the otm2 model.
#
# removed_fields:     fields in the provided data that will be discarded.
#
# missing_fields:     fields in the otm2 django model that are not provided.
#
# value_transformers: a mapping where keys are the name of fields in the
#                     _provided_ data and and values are unary functions
#                     that take a value and transform it to some other value.

MIGRATION_RULES = {
    'treephoto': {
        'command_line_flag': '-f',
        'model_class': TreePhoto,
        'dependencies': {'tree': 'tree',
                         'user': 'reported_by'},
        'common_fields': {'photo'},
        'renamed_fields': {'tree': 'tree_id'},
        'removed_fields': {'title', 'reported', 'reported_by', 'comment'},
        'missing_fields': set()
    },
    'boundary': {
        'command_line_flag': '-b',
        'model_class': Boundary,
        'common_fields': {'name'},
        'renamed_fields': {'geometry': 'geom'},
        'removed_fields': {'region_id', 'city', 'state', 'county'},
        'value_transformers': {
            'geometry': (lambda x: fromstr(x, srid=4326)),
        },
    },
    'tree': {
        'command_line_flag': '-t',
        'model_class': Tree,
        'dependencies': {'species': 'species',
                         'user': 'steward_user',
                         'plot': 'plot'},
        'common_fields': {'readonly', 'canopy_height',
                          'date_planted', 'date_removed', 'height'},
        'renamed_fields': {'dbh': 'diameter'},
        'removed_fields': {'tree_owner', 'steward_name', 'sponsor',
                           'species_other1', 'species_other2',
                           'orig_species', 'present', 'last_updated',
                           'last_updated_by', 's_order', 'photo_count',
                           'projects', 'condition', 'canopy_condition',
                           'url', 'pests', 'steward_user',
                           'import_event'},
        'missing_fields': {'instance', },
        'value_transformers': {'readonly': coerce_null_boolean}
    },
    'audit': {
        'command_line_flag': '-a',
        'model_class': Audit,
        'dependencies': {'user': 'user'},
        # since audits are produced using a sanitized
        # fixture exporter, fewer fields are modified
        # on this end.
        'common_fields': {'model', 'model_id', 'field',
                          'previous_value', 'current_value',
                          'action', 'requires_auth',
                          'ref', 'created', 'updated'},
        'value_transformers': {
            'previous_value': correct_none_string,
            'current_value': correct_none_string,
        }
    },
    'plot': {
        'command_line_flag': '-p',
        'model_class': Plot,
        'dependencies': {'user': 'data_owner'},
        'common_fields': {'width', 'length', 'address_street', 'address_zip',
                          'address_city', 'owner_orig_id', 'readonly'},
        'renamed_fields': {'geometry': 'geom'},
        'removed_fields': {'type', 'powerline_conflict_potential',
                           'sidewalk_damage', 'neighborhood',
                           'neighborhoods', 'zipcode', 'geocoded_accuracy',
                           'geocoded_address', 'geocoded_lat', 'geocoded_lon',
                           'present', 'last_updated', 'last_updated_by',
                           'data_owner', 'owner_additional_id',
                           'owner_additional_properties',
                           'import_event'},
        'missing_fields': {'instance', },
        'value_transformers': {
            'readonly': coerce_null_boolean,
            'geometry': (lambda x: fromstr(x, srid=4326)),
        },
    },
    'species': {
        'command_line_flag': '-s',
        'model_class': Species,
        'common_fields': {'bloom_period', 'common_name',
                          'fact_sheet', 'fall_conspicuous',
                          'flower_conspicuous', 'fruit_period', 'gender',
                          'genus', 'native_status', 'palatable_human',
                          'plant_guide', 'species',
                          'wildlife_value'},
        'renamed_fields': {'v_max_height': 'max_height',
                           'v_max_dbh': 'max_dbh',
                           'cultivar_name': 'cultivar',
                           'other_part_of_name': 'other'},
        'missing_fields': {'instance', 'otm_code'},
        'removed_fields': {'alternate_symbol', 'v_multiple_trunks',
                           'tree_count', 'resource', 'itree_code',
                           'family', 'scientific_name', 'symbol'},
        'value_transformers': {
            'common_name': coerce_null_string,
            'v_max_height': (lambda x: x or 10000),
            'v_max_dbh': (lambda x: x or 10000),
            'native_status': (lambda x: x and x.lower() == 'true')
        },
    },
    'user': {
        'command_line_flag': '-u',
        'model_class': User,
        'common_fields': {'username', 'password', 'email', 'date_joined',
                          'first_name', 'last_name', 'is_active',
                          'is_superuser', 'is_staff', 'last_login'},
        'removed_fields': {'groups', 'user_permissions'},
        'missing_fields': {'roles', 'reputation'},
    },
    'contenttype': {
        'command_line_flag': '-c',
        'common_fields': {'model', 'name', 'app_label'}
    },
    'userprofile': {
        'command_line_flag': '-z',
        'dependencies': {'user': 'user'},
        'common_fields': {'photo'},
        'removed_fields': {'site_edits', 'uid', 'active',
                           'zip_code', 'updates', 'volunteer'}
    },
    'comment': {
        'command_line_flag': '-n',
        'model_class': ThreadedComment,
        'dependencies': {'user': 'user',
                         'contenttype': 'content_type'},
        'common_fields': {'comment', 'is_public',
                          'ip_address'},
        'renamed_fields': {'submit_date': 'date_submitted'},
        'removed_fields': {'is_removed', 'user_name', 'user_email',
                           'user_url', 'site', 'object_pk'},
    },
    'threadedcomment': {
        'command_line_flag': '-r',
        'model_class': ThreadedComment,
        'dependencies': {'user': 'user',
                         'contenttype': 'content_type'},
        'common_fields': {'comment', 'is_public', 'is_approved',
                          'ip_address', 'date_submitted',
                          'date_modified', 'date_approved'},
        'removed_fields': {'markup',  # this is no longer in the schema
                           # object_id and parent are not actually removed
                           # but they have to be processed manually so they
                           # are ignored the tools that use this config.
                           'object_id',
                           'parent'},
        'missing_fields': {'title',
                           'tree_path',
                           'last_child'}
    }
}

# This is a concession. It would be better, but more difficult, if
# users of MIGRATION_RULES would resolve a priority order based on
# dependencies in order to make this more DRY.
PRIORITY_ORDER = ['user', 'contenttype', 'species', 'plot', 'tree']
MODEL_ORDER = (PRIORITY_ORDER +
               [model for model in MIGRATION_RULES
                if model not in PRIORITY_ORDER])
