# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from optparse import make_option

import os
import json
from functools import partial

from django.conf import settings
from django.db.transaction import commit_on_success

from treemap import SPECIES
from treemap.models import User, Species, InstanceUser
from treemap.management.util import InstanceDataCommand

from otm1_migrator.models import OTM1UserRelic, OTM1ModelRelic
from otm1_migrator.migration_rules import MIGRATION_RULES
from otm1_migrator.data_util import hash_to_model, MigrationException


def find_user_to_save_with(model):
    model_name = model.__class__.__name__.lower()

    user_field_to_try = (MIGRATION_RULES[model_name]
                         .get('dependencies', {})
                         .get('user', None))

    if user_field_to_try:
        potential_user_id = getattr(model, user_field_to_try, None)
    else:
        potential_user_id = None

    try:
        user = User.objects.get(pk=potential_user_id)
    except User.DoesNotExist:
        user = User.system_user()

    return user


def save_model_with_user(model, instance):
    user = find_user_to_save_with(model)
    model.save_with_user_without_verifying_authorization(user)
    return model


def overwrite_old_pks(model_hash, model_name, dependency_ids):

    dependencies = (MIGRATION_RULES
                    .get(model_name, {})
                    .get('dependencies', {})
                    .items())

    # rewrite the fixture so that otm1 pks are replaced by
    # their corresponding otm2 pks
    if dependencies:
        for name, field in dependencies:
            old_id = model_hash['fields'][field]
            if old_id:
                old_id_to_new_id = dependency_ids[name]
                try:
                    new_id = old_id_to_new_id[old_id]
                except KeyError:
                    raise MigrationException("Dependency not found. "
                                             "Have you imported %s yet?"
                                             % name)
                model_hash['fields'][field] = new_id


@commit_on_success
def save_species(model_hash, instance):
    # Does this species already exist?
    genus, species, cultivar, other = [
        model_hash['fields'].get(thing, '')
        for thing in ['genus', 'species', 'cultivar', 'other_part_of_name']]

    existingspecies = Species.objects.filter(genus=genus,
                                             species=species,
                                             cultivar=cultivar,
                                             other=other)

    relicinfo = {
        'instance': instance,
        'otm1_model_id': model_hash['pk'],
        'otm2_model_name': 'species'
    }

    relics = OTM1ModelRelic.objects.filter(**relicinfo)

    if len(relics) == 0:
        relic = OTM1ModelRelic(**relicinfo)
    else:
        relic = relics[0]

    if len(existingspecies) == 0:

        model = hash_to_model(MIGRATION_RULES,
                              'species', model_hash,
                              instance)

        for sp in SPECIES:
            if ((sp['genus'] == genus and
                 sp['species'] == species and
                 sp['cultivar'] == cultivar and
                 sp['other'] == other)):
                model.otm_code = sp['otm_code']
                break

        # this field can be null in otm1, but not otm2
        if not model.common_name:
            model.common_name = ''

        model = save_model_with_user(model, instance)

        relic.otm2_model_id = model.pk
    else:
        model = None
        relic.otm2_model_id = existingspecies[0].pk

    relic.save()

    return model


@commit_on_success
def save_other_with_user(model_name, model_hash, instance):

    model = hash_to_model(MIGRATION_RULES,
                          model_name, model_hash,
                          instance)

    model = save_model_with_user(model, instance)

    OTM1ModelRelic.objects.create(
        instance=instance,
        otm1_model_id=model_hash['pk'],
        otm2_model_name=model_name,
        otm2_model_id=model.pk)
    return model


@commit_on_success
def save_other(model_name, model_hash, instance):
    model = hash_to_model(model_name, model_hash, instance)

    model.save()
    OTM1ModelRelic.objects.create(
        instance=instance,
        otm1_model_id=model_hash['pk'],
        otm2_model_name=model_name,
        otm2_model_id=model.pk)


@commit_on_success
def save_treephoto(treephoto_path, model_hash, instance):
    model = hash_to_model(MIGRATION_RULES,
                          'treephoto', model_hash,
                          instance)

    image = open(os.path.join(treephoto_path,
                              model_hash['fields']['photo']))
    model.set_image(image)

    del model_hash['fields']['photo']

    model = save_model_with_user(model, instance)

    OTM1ModelRelic.objects.create(
        instance=instance,
        otm1_model_id=model_hash['pk'],
        otm2_model_name='treephoto',
        otm2_model_id=model.pk)
    return model


def _uniquify_username(username):
    username_template = '%s_%%d' % username
    i = 0
    while User.objects.filter(username=username).exists():
        username = username_template % i
        i += 1

    return username


@commit_on_success
def save_user(model_hash, instance):
    model = hash_to_model(MIGRATION_RULES, 'user', model_hash, instance)

    try:
        # TODO: this is REALLY ambiguous. If the try fails,
        # does the previously assigned value of 'model' persist?
        model = User.objects.get(email__iexact=model.email)
    except User.DoesNotExist:
        model.username = _uniquify_username(model.username)
        model.save()

    try:
        InstanceUser.objects.get(instance=instance,
                                 user=model)
    except InstanceUser.DoesNotExist:
        InstanceUser.objects.create(instance=instance,
                                    user=model, role=instance.default_role)

    (OTM1UserRelic
     .objects
     .create(instance=instance,
             otm1_username=model_hash['fields']['username'],
             otm2_user=model,
             otm1_id=model_hash['pk'],
             email=model_hash['fields']['email']))


def hashes_to_saved_objects(model_name, model_hashes, dependency_ids,
                            model_save_fn, instance):

    model_key_map = dependency_ids.get(model_name, {})
    # the model_key_map will be filled from the
    # database each time. combined with this statement,
    # the command becomes idempotent
    hashes_to_save = (hash for hash in model_hashes
                      if hash['pk'] not in model_key_map)

    for model_hash in hashes_to_save:
        overwrite_old_pks(model_hash, model_name, dependency_ids)
        model = model_save_fn(model_hash, instance)

        if model_key_map is not None and model and model.pk:
            model_key_map[model_hash['pk']] = model.pk


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
            # initialize system_user??
            instance, _ = self.setup_env(*args, **options)
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
                json_hashes[model_name] = []
                print('No valid %s fixture provided ... SKIPPING'
                      % model_name)

        treephoto_path = options.get('treephoto_path', None)
        treephoto_fixture_with_no_path = ('treephoto' in json_hashes and
                                          json_hashes['treephoto'] and
                                          treephoto_path is None)
        if treephoto_fixture_with_no_path:
            raise MigrationException('Must specify the tree photo path to '
                                     'import photo')

        # TODO: don't call this dependency anymore.
        # It's an idempotency checker too.
        dependency_ids = {model: {} for model in MIGRATION_RULES}

        # TODO: should this be merged into MIGRATION_RULES?
        save_fns = {
            'user': save_user,
            'audit': partial(save_other, 'audit'),
            'species': save_species,
            'plot': partial(save_other_with_user, 'plot'),
            'tree': partial(save_other_with_user, 'tree'),
            'treephoto': partial(save_treephoto, treephoto_path),
        }

        for relic in OTM1UserRelic.objects.filter(instance=instance):
            dependency_ids['user'][relic.otm1_id] = relic.otm2_user_id

        for relic in OTM1ModelRelic.objects.filter(instance=instance):
            model_ids = dependency_ids[relic.otm2_model_name]
            model_ids[relic.otm1_model_id] = relic.otm2_model_id

        for model in MIGRATION_RULES:
            if json_hashes[model]:
                hashes_to_saved_objects(model, json_hashes[model],
                                        dependency_ids,
                                        save_fns[model],
                                        instance)
