from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from contextlib import contextmanager
from optparse import make_option
import json

from django.core.exceptions import ObjectDoesNotExist
from django.contrib.gis.geos import fromstr
from django.conf import settings

from treemap.models import (User, Plot, Tree, Species, InstanceUser)
from ._private import InstanceDataCommand

# model specification:
#
# model_class:        the django class object used to instantiate objects
#
# dependencies:       a mapping where keys are the names of models that
#                     must also be in the MODELS dict and values are the
#                     names of fields for the currently model that have
#                     foreign key relationships to the dependency model
#
# common_fields:      fields that must be in the provided data and the otm2
#                     django model.
# renamed_fields:     a mapping where keys are fields in the provided data
#                     and values are their names in the otm2 model.
#
# undecided_fields:   fields that we're not sure what to do with. These should
#                     be resolved into other categories before this is used
#                     for a production migration.
# removed_fields:     fields in the provided data that will be discarded.
#
# missing_fields:     fields in the otm2 django model that are not provided.
#
# value_transformers: a mapping where keys are the name of fields in the
#                     _provided_ data and and values are unary functions
#                     that take a value and transform it to some other value.

MODELS = {
    'tree': {
        'model_class': Tree,
        'dependencies': {'species': 'species',
                         'user': 'steward_user',
                         'plot': 'plot'},
        'common_fields': {'plot', 'species', 'readonly', 'canopy_height',
                          'date_planted', 'date_removed', 'height'},
        'renamed_fields': {'dbh': 'diameter'},
        'undecided_fields': {'import_event'},
        'removed_fields': {'tree_owner', 'steward_name', 'sponsor',
                           'species_other1', 'species_other2',
                           'orig_species', 'present', 'last_updated',
                           'last_updated_by', 's_order', 'photo_count',
                           'projects', 'condition', 'canopy_condition',
                           'url', 'pests', 'steward_user'},
        'missing_fields': {'instance', },
        'value_transformers': {
            'plot': (lambda x: Plot.objects.get(pk=x)),
            'species': (lambda x: Species.objects.get(pk=x)),
            }
    },
    'plot': {
        'model_class': Plot,
        'dependencies': {'user': 'data_owner'},
        'common_fields': {'width', 'length', 'address_street', 'address_zip',
                          'address_city', 'owner_orig_id', 'readonly'},
        'renamed_fields': {'geometry': 'geom'},
        'undecided_fields': {'import_event'},
        'removed_fields': {'type', 'powerline_conflict_potential',
                           'sidewalk_damage', 'neighborhood',
                           'neighborhoods', 'zipcode', 'geocoded_accuracy',
                           'geocoded_address', 'geocoded_lat', 'geocoded_lon',
                           'present', 'last_updated', 'last_updated_by',
                           'data_owner', 'owner_additional_id',
                           'owner_additional_properties'},
        'missing_fields': {'instance', },
        'value_transformers': {
            'geometry': (lambda x: fromstr(x, srid=4326)),
        },
    },
    'species': {
        'model_class': Species,
        'dependencies': {},
        'common_fields': {'bloom_period', 'common_name', 'cultivar_name',
                          'fact_sheet', 'fall_conspicuous',
                          'flower_conspicuous', 'fruit_period', 'gender',
                          'genus', 'native_status', 'palatable_human',
                          'plant_guide', 'species', 'symbol',
                          'wildlife_value'},
        'renamed_fields': {'v_max_height': 'max_height',
                           'v_max_dbh': 'max_dbh'},
        'undecided_fields': set(),
        'removed_fields': {'alternate_symbol', 'v_multiple_trunks',
                           'tree_count', 'resource', 'itree_code',
                           'other_part_of_name', 'family',
                           'scientific_name'},
        'value_transformers': {
            'v_max_height': (lambda x: x or 10000),
            'v_max_dbh': (lambda x: x or 10000),
        },
    },
    'user': {
        'model_class': User,
        'dependencies': {},
        'common_fields': {'username', 'password', 'email', 'date_joined',
                          'first_name', 'last_name', 'is_active',
                          'is_superuser', 'is_staff', 'last_login'},
        'renamed_fields': {},
        'undecided_fields': set(),
        'removed_fields': {'groups', 'user_permissions'},
        'missing_fields': {'roles', 'reputation'},
        'value_transformers': {},
    },
}


def validate_model(model_name, data_hash):
    """
    Makes sure the fields specified in the MODELS global
    account for all of the provided data
    """
    common_fields = MODELS[model_name]['common_fields']
    renamed_fields = MODELS[model_name]['renamed_fields']
    removed_fields = MODELS[model_name]['removed_fields']
    undecided_fields = MODELS[model_name]['undecided_fields']
    expected_fields = (common_fields |
                       set(renamed_fields.keys()) |
                       removed_fields |
                       undecided_fields)

    provided_fields = set(data_hash['fields'].keys())

    if expected_fields != provided_fields:
        raise Exception('model validation failure. \n\n'
                        'Expected: %s \n\n'
                        'Got %s\n\n'
                        'Symmetric Difference: %s'
                        % (expected_fields, provided_fields,
                           expected_fields.
                           symmetric_difference(provided_fields)))


def hash_to_model(model_name, data_hash, instance, user):
    """
    Takes a model specified in the MODELS global and a
    hash of json data and attempts to populate a django
    model. Does not save.
    """

    validate_model(model_name, data_hash)

    common_fields = MODELS[model_name]['common_fields']
    renamed_fields = MODELS[model_name]['renamed_fields']

    model = MODELS[model_name]['model_class']()

    identity = (lambda x: x)

    for field in common_fields.union(renamed_fields):
        transform_value_fn = MODELS[model_name]['value_transformers']\
            .get(field, identity)
        try:
            transformed_value = transform_value_fn(data_hash['fields'][field])
            field = renamed_fields.get(field, field)
            setattr(model, field, transformed_value)
        except ObjectDoesNotExist as d:
            print("Warning: %s ... SKIPPING" % d)

    # hasattr will not work here because it
    # just calls getattr and looks for exceptions
    # not differentiating between DoesNotExist
    # and AttributeError
    try:
        getattr(model, 'instance')
    except ObjectDoesNotExist:
        model.instance = instance
    except AttributeError:
        pass

    return model


@contextmanager
def more_permissions(user, instance, role):
    """
    Temporarily assign role to a user

    This is useful for odd CRUD events that take place
    outside of the normal context of the app, like imports
    and migrations.
    """
    iuser = user.get_instance_user(instance)
    iuser.roles = role
    iuser.save()
    yield user
    iuser.roles = instance.default_role
    iuser.save()


def try_save_user_hash_to_model(model_name, model_hash,
                                instance, system_user, god_role,
                                user_field_to_try):
    """
    Tries to save an object with the app user that should own
    the object. If not possible, falls back to the system_user.
    """
    model = hash_to_model(model_name, model_hash,
                          instance, system_user)

    potential_user_id = model_hash['fields'][user_field_to_try]
    if potential_user_id:
        user = User.objects.get(pk=potential_user_id)
    else:
        user = system_user

    with more_permissions(user, instance, god_role) as elevated_user:
        model.save_with_user(elevated_user)

    return model


def hashes_to_saved_objects(model_name, model_hashes, dependency_id_maps,
                            instance, system_user,
                            god_role=None, save_with_user=False,
                            save_with_system_user=False):

    for model_hash in model_hashes:
        for dependency_name, dependency_field in \
            MODELS[model_name]['dependencies'].iteritems():  # NOQA
            dependency_map = dependency_id_maps[dependency_name]
            dependency_id = model_hash['fields'][dependency_field]
            if dependency_id:
                new_id = dependency_map[model_hash['fields'][dependency_field]]
                model_hash['fields'][dependency_field] = new_id

        if save_with_user:
            user_field = MODELS[model_name]['dependencies']['user']
            fn = try_save_user_hash_to_model
            model = fn(model_name, model_hash, instance, system_user,
                       god_role, user_field)
        else:
            model = hash_to_model(model_name, model_hash,
                                  instance, system_user)
            if save_with_system_user:
                model.save_with_user(system_user)
            else:
                model.save()

        model_key_map = dependency_id_maps.get(model_name, None)
        if model_key_map is not None:
            model_key_map[model_hash['pk']] = model.pk


def create_instance_users(instance):
    for user in User.objects.all():
        iuser = InstanceUser(instance=instance, user=user,
                             role=instance.default_role)
        iuser.save()


class Command(InstanceDataCommand):

    option_list = InstanceDataCommand.option_list + (
        make_option('-s', '--species-fixture',
                    action='store',
                    type='string',
                    dest='species_fixture',
                    help='path to json dump containing species data'),
        make_option('-u', '--user-fixture',
                    action='store',
                    type='string',
                    dest='user_fixture',
                    help='path to json dump containing user data'),
        make_option('-p', '--plot-fixture',
                    action='store',
                    type='string',
                    dest='plot_fixture',
                    help='path to json dump containing plot data'),
        make_option('-t', '--tree-fixture',
                    action='store',
                    type='string',
                    dest='tree_fixture',
                    help='path to json dump containing tree data'),
    )

    def handle(self, *args, **options):

        if settings.DEBUG:
            print('In order to run this command you must manually'
                  'set DEBUG=False in your settings file.')
            return 1

        if options['instance']:
            instance, system_user = self.setup_env(*args, **options)
        else:
            print('Invalid instance provided.')
            return 1

        # look for fixtures of the form '<model>_fixture' that
        # were passed in as command line args and load them as
        # python objects
        json_hashes = {
            'species': [],
            'user': [],
            'plot': [],
            'tree': []
        }

        for model_name in json_hashes:
            option_name = model_name + '_fixture'
            try:
                model_file = open(options[option_name], 'r')
                json_hashes[model_name] = json.load(model_file)
            except:
                print('No valid %s fixture provided ... SKIPPING'
                      % model_name)

        # iterate over the fixture hashes and save them as database
        # records.
        #
        # a few important things happen here:
        # #
        # # for models that server as dependencies for other models,
        # # their previous ids are stored in a map so that when dependant
        # # models are made, the correct pk can be retreived.
        # #
        # # for models that must be saved with a user, they are either
        # # saved immediately with a system_user, or an app user is tried
        # # first, depending on the model.
        dependency_id_maps = {
            'plot': {},
            'species': {},
            'user': {},
        }

        if json_hashes['user']:
            hashes_to_saved_objects('user', json_hashes['user'],
                                    dependency_id_maps,
                                    instance, system_user,
                                    save_with_system_user=True)
            create_instance_users(instance)

        if json_hashes['species']:
            hashes_to_saved_objects('species', json_hashes['species'],
                                    dependency_id_maps, instance, system_user)

        from treemap.tests import make_god_role
        god_role = make_god_role(instance)

        if json_hashes['plot']:
            hashes_to_saved_objects('plot', json_hashes['plot'],
                                    dependency_id_maps,
                                    instance, system_user, god_role,
                                    save_with_user=True)

        if json_hashes['tree']:
            hashes_to_saved_objects('tree', json_hashes['tree'],
                                    dependency_id_maps,
                                    instance, system_user, god_role,
                                    save_with_user=True)
