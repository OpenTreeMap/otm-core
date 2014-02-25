# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from contextlib import contextmanager
from optparse import make_option

import os
import json
import logging

from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from django.db.transaction import commit_on_success

from treemap import SPECIES
from treemap.models import User, Species, InstanceUser
from treemap.audit import model_hasattr
from treemap.management.util import InstanceDataCommand

# TODO: should not require a utility from the tests
from treemap.tests import make_commander_role

from otm1_migrator.models import OTM1UserRelic, OTM1ModelRelic
from otm1_migrator.data_util import validate_model, hash_to_model
from otm1_migrator.migration_rules import MIGRATION_RULES

logger = logging.getLogger('')


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
                            instance, system_user, commander_role,
                            treephoto_path=None):
    """
    Tries to save an object with the app user that should own
    the object. If not possible, falls back to the system_user.
    """
    model = hash_to_model(MIGRATION_RULES,
                          model_name, model_hash,
                          instance, system_user)

    user_field_to_try = (MIGRATION_RULES[model_name]
                         .get('dependencies', {})
                         .get('user', None))

    potential_user_id = model_hash['fields'].get(user_field_to_try, None)

    if potential_user_id:
        user = User.objects.get(pk=potential_user_id)
    else:
        user = system_user

    if model_name == 'treephoto':
        image = open(os.path.join(treephoto_path,
                                  model_hash['fields']['photo']))
        model.set_image(image)

        del model_hash['fields']['photo']

    with more_permissions(user, instance, commander_role) as elevated_user:
        model.save_with_user(elevated_user)

    return model


def hashes_to_saved_objects(model_name, model_hashes, dependency_id_maps,
                            instance, system_user,
                            commander_role=None, save_with_user=False,
                            treephoto_path=None):

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

        try:
            # rewrite the fixture so that otm1 pks are replaced by
            # their corresponding otm2 pks
            if dependencies:
                for name, field in dependencies:
                    old_id = model_hash['fields'][field]
                    if old_id:
                        old_id_to_new_id = dependency_id_maps[name]
                        new_id = old_id_to_new_id[old_id]
                        model_hash['fields'][field] = new_id
        except Exception as e:
            logger.error("Error: %s" % e)
            continue

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
                        commander_role,
                        treephoto_path=treephoto_path)

                    OTM1ModelRelic.objects.create(
                        instance=instance,
                        otm1_model_id=model_hash['pk'],
                        otm2_model_name=model_name,
                        otm2_model_id=model.pk)
                    return model

                try:
                    model = _save_with_user_portion()
                except Exception as e:
                    logger.error("Error: %s" % e)
                    model = None
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

        if model_key_map is not None and model and model.pk:
            model_key_map[model_hash['pk']] = model.pk


def _uniquify_username(username):
    username_template = '%s_%%d' % username
    i = 0
    while User.objects.filter(username=username).exists():
        username = username_template % i
        i += 1

    return username

def make_model_option(model):
    shortflag = MIGRATION_RULES[model]['command_line_flag']
    return make_option(shortflag,
                       '--%s-fixture' % model,
                       action='store',
                       type='string',
                       dest='%s_fixture' % model,
                       help='path to json dump containing %s data' % model)

class Command(InstanceDataCommand):


    option_list = (
        InstanceDataCommand.option_list +

        # add options for model fixtures
        tuple(make_model_option(model) for model in MIGRATION_RULES) +

        # add other kinds of options
        (make_option('-x', '--photo-path',
                     action='store',
                     type='string',
                     dest='treephoto_path',
                     help='path to photos that will be imported'),)
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
        json_hashes = {}
        for model_name in MIGRATION_RULES:
            option_name = model_name + '_fixture'
            try:
                model_file = open(options[option_name], 'r')
                json_hashes[model_name] = json.load(model_file)
            except:
                print('No valid %s fixture provided ... SKIPPING'
                      % model_name)

        treephoto_path = options.get('treephoto_path', None)
        treephoto_fixture_with_no_path = ('treephoto' in json_hashes and
                                          json_hashes['treephoto'] and
                                          treephoto_path is None)
        if treephoto_fixture_with_no_path:
            raise Exception('Must specify the tree photo path to '
                            'import photo')


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
        dependency_id_maps = {model: {} for model in MIGRATION_RULES}

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

        for model in ('species', 'plot', 'tree', 'treephoto'):
            if json_hashes[model]:
                hashes_to_saved_objects(model, json_hashes[model],
                                        dependency_id_maps,
                                        instance, system_user, commander_role,
                                        save_with_user=True,
                                        treephoto_path=treephoto_path)
