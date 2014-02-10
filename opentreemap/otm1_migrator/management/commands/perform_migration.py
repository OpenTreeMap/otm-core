# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from contextlib import contextmanager
from optparse import make_option
import json
import logging

from django.core.exceptions import ObjectDoesNotExist
from django.contrib.gis.geos import fromstr
from django.conf import settings
from django.db.transaction import commit_on_success

from treemap import SPECIES
from treemap.models import (User, Plot, Tree, Species, InstanceUser, Audit)
from treemap.audit import model_hasattr
from treemap.management.util import InstanceDataCommand

# TODO: should not require a utility from the tests
from treemap.tests import make_commander_role

from otm1_migrator.models import OTM1UserRelic, OTM1ModelRelic

logger = logging.getLogger('')

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

MIGRATION_RULES = {
    'tree': {
        'model_class': Tree,
        'dependencies': {'species': 'species',
                         'user': 'steward_user',
                         'plot': 'plot'},
        'common_fields': {'plot', 'species', 'readonly', 'canopy_height',
                          'date_planted', 'date_removed', 'height'},
        'renamed_fields': {'dbh': 'diameter'},
        'undecided_fields': set(),
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
    'audit': {
        'model_class': Audit,
        'dependencies': {'user': 'user'},
        # since audits are produced using a sanitized
        # fixture exporter, fewer fields are modified
        # on this end.
        'common_fields': {'model', 'model_id', 'field',
                          'previous_value', 'current_value',
                          'user',
                          'action', 'requires_auth',
                          'ref', 'created', 'updated'},
        'value_transformers': {
            'user': (lambda x: User.objects.get(pk=x))
        }
    },
    'plot': {
        'model_class': Plot,
        'dependencies': {'user': 'data_owner'},
        'common_fields': {'width', 'length', 'address_street', 'address_zip',
                          'address_city', 'owner_orig_id', 'readonly'},
        'renamed_fields': {'geometry': 'geom'},
        'undecided_fields': set(),
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
        'common_fields': {'bloom_period', 'common_name',
                          'fact_sheet', 'fall_conspicuous',
                          'flower_conspicuous', 'fruit_period', 'gender',
                          'genus', 'native_status', 'palatable_human',
                          'plant_guide', 'species', 'otm_code',
                          'wildlife_value'},
        'renamed_fields': {'v_max_height': 'max_height',
                           'v_max_dbh': 'max_dbh',
                           'cultivar_name': 'cultivar',
                           'other_part_of_name': 'other'},
        'missing_fields': {'instance', },
        'removed_fields': {'alternate_symbol', 'v_multiple_trunks',
                           'tree_count', 'resource', 'itree_code',
                           'family', 'scientific_name', 'symbol'},
        'value_transformers': {
            'v_max_height': (lambda x: x or 10000),
            'v_max_dbh': (lambda x: x or 10000),
            'native_status': (lambda x: x and x.lower() == 'true')
        },
    },
    'user': {
        'model_class': User,
        'common_fields': {'username', 'password', 'email', 'date_joined',
                          'first_name', 'last_name', 'is_active',
                          'is_superuser', 'is_staff', 'last_login'},
        'removed_fields': {'groups', 'user_permissions'},
        'missing_fields': {'roles', 'reputation'},
    },
}


def validate_model(model_name, data_hash):
    """
    Makes sure the fields specified in the MIGRATION_RULES global
    account for all of the provided data
    """
    common_fields = MIGRATION_RULES[model_name].get('common_fields', set())
    renamed_fields = MIGRATION_RULES[model_name].get('renamed_fields', {})
    removed_fields = MIGRATION_RULES[model_name].get('removed_fields', set())
    undecided_fields = (MIGRATION_RULES[model_name]
                        .get('undecided_fields', set()))
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
    Takes a model specified in the MIGRATION_RULES global and a
    hash of json data and attempts to populate a django
    model. Does not save.
    """

    validate_model(model_name, data_hash)

    common_fields = MIGRATION_RULES[model_name].get('common_fields', set())
    renamed_fields = MIGRATION_RULES[model_name].get('renamed_fields', {})

    model = MIGRATION_RULES[model_name]['model_class']()

    identity = (lambda x: x)

    for field in common_fields.union(renamed_fields):
        transformers = (MIGRATION_RULES[model_name]
                        .get('value_transformers', {}))
        transform_value_fn = transformers.get(field, identity)
        try:
            transformed_value = transform_value_fn(data_hash['fields'][field])
            field = renamed_fields.get(field, field)
            setattr(model, field, transformed_value)
        except ObjectDoesNotExist as d:
            logger.warning("Warning: %s ... SKIPPING" % d)

    if model_hasattr(model, 'instance'):
        model.instance = instance

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
    previous_role = iuser.role
    iuser.role = role
    iuser.save()
    yield user
    iuser.role = previous_role or instance.default_role
    iuser.save()


def save_user_hash_to_model(model_name, model_hash,
                            instance, system_user, commander_role):
    """
    Tries to save an object with the app user that should own
    the object. If not possible, falls back to the system_user.
    """
    model = hash_to_model(model_name, model_hash,
                          instance, system_user)

    user_field_to_try = (MIGRATION_RULES[model_name]
                         .get('dependencies', {})
                         .get('user', None))

    potential_user_id = model_hash['fields'].get(user_field_to_try, None)

    if potential_user_id:
        user = User.objects.get(pk=potential_user_id)
    else:
        user = system_user

    with more_permissions(user, instance, commander_role) as elevated_user:
        model.save_with_user(elevated_user)

    return model


def hashes_to_saved_objects(model_name, model_hashes, dependency_id_maps,
                            instance, system_user,
                            commander_role=None, save_with_user=False):

    model_key_map = dependency_id_maps.get(model_name, {})
    dependencies = (MIGRATION_RULES
                    .get(model_name, {})
                    .get('dependencies', {})
                    .items())

    # the model_key_map will be filled from the
    # database each time. combined with this statement,
    # the command becomes idempotent
    hashes_to_save = (hash for hash in model_hashes
                      if hash['pk'] not in model_key_map)

    for model_hash in hashes_to_save:

        # rewrite the fixture so that otm1 pks are replaced by
        # their corresponding otm2 pks
        if dependencies:
            for name, field in dependencies:
                old_id = model_hash['fields'][field]
                if old_id:
                    old_id_to_new_id = dependency_id_maps[name]
                    new_id = old_id_to_new_id[old_id]
                    model_hash['fields'][field] = new_id

        if save_with_user:
            if model_name == 'species':
                @commit_on_success
                def _save_species():
                    # Does this species already exist?
                    genus, species, cultivar, other = [
                        model_hash['fields'].get(thing, '')
                        for thing
                        in ['genus', 'species', 'cultivar',
                            'other_part_of_name']]

                    existingspecies = Species.objects.filter(
                        genus=genus,
                        species=species,
                        cultivar=cultivar,
                        other=other)

                    relicinfo = {
                        'instance': instance,
                        'otm1_model_id': model_hash['pk'],
                        'otm2_model_name': model_name
                    }

                    relics = OTM1ModelRelic.objects.filter(**relicinfo)

                    if len(relics) == 0:
                        relic = OTM1ModelRelic(**relicinfo)
                    else:
                        relic = relics[0]

                    if len(existingspecies) == 0:
                        for sp in SPECIES:
                            if ((sp['genus'] == genus and
                                 sp['species'] == species and
                                 sp['cultivar'] == cultivar and
                                 sp['other'] == other)):
                                fields = model_hash['fields']
                                fields['otm_code'] = sp['otm_code']

                                break

                        model = save_user_hash_to_model(
                            model_name, model_hash,
                            instance, system_user,
                            commander_role)

                        relic.otm2_model_id = model.pk
                    else:
                        model = None
                        relic.otm2_model_id = existingspecies[0].pk

                    relic.save()

                    return model


                model = _save_species()
            else:
                @commit_on_success
                def _save_with_user_portion():
                    model = save_user_hash_to_model(
                        model_name, model_hash,
                        instance, system_user,
                        commander_role)

                    OTM1ModelRelic.objects.create(
                        instance=instance,
                        otm1_model_id=model_hash['pk'],
                        otm2_model_name=model_name,
                        otm2_model_id=model.pk)
                    return model
                model = _save_with_user_portion()

        else:

            model = hash_to_model(model_name, model_hash,
                                  instance, system_user)

            if model_name == 'user':
                @commit_on_success
                def _user_save_portion(model):
                    try:
                        model = User.objects.get(email__iexact=model.email)
                    except User.DoesNotExist:
                        model.username = _uniquify_username(model.username)
                        model.set_unusable_password()
                        model.save()

                    try:
                        InstanceUser.objects.get(instance=instance,
                                                 user=model)
                    except InstanceUser.DoesNotExist:
                        InstanceUser.objects.create(
                            instance=instance,
                            user=model,
                            role=instance.default_role)

                    (OTM1UserRelic
                     .objects
                     .create(instance=instance,
                             otm1_username=model_hash['fields']['username'],
                             otm2_user=model,
                             otm1_id=model_hash['pk'],
                             email=model_hash['fields']['email']))
                _user_save_portion(model)

            else:
                @commit_on_success
                def _other_save_portion(model):
                    model.save()
                    OTM1ModelRelic.objects.create(
                        instance=instance,
                        otm1_model_id=model_hash['pk'],
                        otm2_model_name=model_name,
                        otm2_model_id=model.pk)
                _other_save_portion(model)

        if model_key_map is not None:
            model_key_map[model_hash['pk']] = model.pk


def _uniquify_username(username):
    username_template = '%s_%%d' % username
    i = 0
    while User.objects.filter(username=username).exists():
        username = username_template % i
        i += 1

    return username


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
        make_option('-a', '--audit-fixture',
                    action='store',
                    type='string',
                    dest='audit_fixture',
                    help='path to json dump containing audit data'),
    )

    def handle(self, *args, **options):

        if settings.DEBUG:
            print('In order to run this command you must manually'
                  'set DEBUG=False in your settings file.')
            return 1

        if options['instance']:
            instance, system_user = self.setup_env(*args, **options)
        else:
            self.stdout.write('Invalid instance provided.')
            return 1

        # look for fixtures of the form '<model>_fixture' that
        # were passed in as command line args and load them as
        # python objects
        json_hashes = {
            'species': [],
            'user': [],
            'plot': [],
            'tree': [],
            'audit': []
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

        # TODO: don't call this dependency anymore.
        # It's an idempotency checker too.
        dependency_id_maps = {
            'plot': {},
            'species': {},
            'user': {},
            'tree': {},
            'audit': {},
        }

        for relic in OTM1UserRelic.objects.filter(instance=instance):
            dependency_id_maps['user'][relic.otm1_id] = relic.otm2_user_id

        for relic in OTM1ModelRelic.objects.filter(instance=instance):
            map = dependency_id_maps[relic.otm2_model_name]
            map[relic.otm1_model_id] = relic.otm2_model_id

        for model in ('user', 'audit'):
            if json_hashes[model]:
                hashes_to_saved_objects(model, json_hashes[model],
                                        dependency_id_maps,
                                        instance, system_user)

        commander_role = make_commander_role(instance)

        for model in ('species', 'plot', 'tree'):
            if json_hashes[model]:
                hashes_to_saved_objects(model, json_hashes[model],
                                        dependency_id_maps,
                                        instance, system_user, commander_role,
                                        save_with_user=True)
