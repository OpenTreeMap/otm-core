# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from optparse import make_option

import os
import importlib
import json
import operator
from functools import partial
from itertools import chain

from django.conf import settings
from django.db.transaction import atomic
from django.contrib.contenttypes.models import ContentType

from treemap import SPECIES
from treemap.models import User, Species, InstanceUser, Tree
from treemap.management.util import InstanceDataCommand
from treemap.images import save_uploaded_image

from otm1_migrator.models import (OTM1UserRelic, OTM1ModelRelic,
                                  OTM1CommentRelic)
from otm1_migrator.data_util import hash_to_model, MigrationException

USERPHOTO_ARGS = ('-y', '--userphoto-path')


def find_user_to_save_with(migration_rules, model):
    model_name = model.__class__.__name__.lower()

    user_field_to_try = (migration_rules[model_name]
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


def save_model_with_user(migration_rules, model, instance):
    user = find_user_to_save_with(migration_rules, model)
    model.save_with_user_without_verifying_authorization(user)
    return model


def overwrite_old_pks(migration_rules, model_hash, model_name, dependency_ids):
    dependencies = (migration_rules
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


@atomic
def save_species(migration_rules, model_hash, instance):
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

        model = hash_to_model(migration_rules,
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

        model = save_model_with_user(migration_rules, model, instance)

        relic.otm2_model_id = model.pk
    else:
        model = None
        relic.otm2_model_id = existingspecies[0].pk

    relic.save()

    return model


@atomic
def save_other_with_user(migration_rules, model_name, model_hash, instance):

    model = hash_to_model(migration_rules,
                          model_name, model_hash,
                          instance)

    model = save_model_with_user(migration_rules, model, instance)

    OTM1ModelRelic.objects.get_or_create(
        instance=instance,
        otm1_model_id=model_hash['pk'],
        otm2_model_name=model_name,
        otm2_model_id=model.pk)
    return model


@atomic
def process_userprofile(photo_basepath, model_hash, instance):
    """
    Read the otm1 user photo off userprofile fixture, load the file,
    create storage-backed image and thumbnail, attach to user.

    the workflow for user photos is:
    * get photo data from otm1 as tarball that matches relative path
    * get userprofile fixture from otm1 as usual
    * dump photo data locally
    * modify photo_path to match local path for imports
    * "migrate" userprofile using this migrator
      with photo_path matching local.
    """
    photo_path = model_hash['fields']['photo']
    if not photo_path:
        return None

    user = User.objects.get(pk=model_hash['fields']['user'])

    photo_full_path = os.path.join(photo_basepath, photo_path)
    try:
        photo_data = open(photo_full_path)
    except IOError:
        print("Failed to read photo %s ... SKIPPING USER %s %s" %
              (photo_full_path, user.id, user.username))
        return None
    user.photo, user.thumbnail = save_uploaded_image(
        photo_data, "user-%s" % user.pk, thumb_size=(85, 85))
    user.save()

    # cannot save a relic because unlike other models, we're not going
    # to ever put a UserProfile in the otm2 database, so there'll be
    # no otm2_model_id(required) to bind it to.


@atomic
def save_treephoto(migration_rules, treephoto_path, model_hash, instance):
    model = hash_to_model(migration_rules,
                          'treephoto', model_hash,
                          instance)

    image = open(os.path.join(treephoto_path,
                              model_hash['fields']['photo']))
    model.set_image(image)
    model.map_feature_id = Tree.objects.values_list('plot__id', flat=True)\
                                       .get(pk=model.tree_id)

    del model_hash['fields']['photo']

    model = save_model_with_user(migration_rules, model, instance)

    OTM1ModelRelic.objects.get_or_create(
        instance=instance,
        otm1_model_id=model_hash['pk'],
        otm2_model_name='treephoto',
        otm2_model_id=model.pk)
    return model


@atomic
def save_audit(migration_rules, dependency_ids, model_hash, instance):
    model = hash_to_model(migration_rules, 'audit', model_hash, instance)
    fields = model_hash['fields']

    # update the object_id
    audit_object_relic = OTM1ModelRelic.objects.get(
        instance=instance,
        otm2_model_name__iexact=model_hash['fields']['model'],
        otm1_model_id=model_hash['fields']['model_id'])
    model.model_id = audit_object_relic.otm2_model_id

    if ((fields['field'] == 'id' and
         fields['current_value'] == fields['model_id'])):
        model.current_value = audit_object_relic.otm2_model_id

    model.save()

    # should we save relics audits, or is this a lie?
    # TODO: make audit export ids have meaning, instead of just
    # serializing them.
    OTM1ModelRelic.objects.create(
        instance=instance,
        otm1_model_id=model_hash['pk'],
        otm2_model_name='audit',
        otm2_model_id=model.pk)


@atomic
def save_comment(migration_rules, dependency_ids, model_hash, instance):
    model = hash_to_model(migration_rules,
                          'comment', model_hash,
                          instance)

    model.site_id = 1

    if model.content_type_id == -1:
        print("Can't import comment %s because "
              "it is assigned to a ContentType (model) "
              "that does not exist in OTM2 .. SKIPPING"
              % model.comment)
        return None

    old_object_id = int(model_hash['fields']['object_pk'])
    new_object_id = dependency_ids[model.content_type.model][old_object_id]

    # object_id is called object_pk in later versions
    model.object_pk = new_object_id

    model.save()

    OTM1CommentRelic.objects.create(
        instance=instance,
        otm1_model_id=model_hash['pk'],
        otm2_model_id=model.pk)

    return model


@atomic
def save_threadedcomment(
        migration_rules, dependency_ids, model_hash, instance):

    model = hash_to_model(migration_rules,
                          'threadedcomment', model_hash,
                          instance)

    model.site_id = 1

    if model.content_type_id == -1:
        print("Can't import threadedcomment %s because "
              "it is assigned to a ContentType (model) "
              "that does not exist in OTM2 .. SKIPPING"
              % model.comment)
        return None
    model.save()

    old_object_id = model_hash['fields']['object_id']
    new_object_id = dependency_ids[model.content_type.model][old_object_id]
    # object_id is called object_pk in later versions
    model.object_pk = new_object_id

    # find relic/dependency id for the parent and set that.
    if model_hash['fields']['parent']:
        parent_relic = (OTM1CommentRelic.objects
                        .get(otm1_model_id=model_hash['fields']['parent']))
        model.parent_id = parent_relic.otm2_model_id

    else:
        parent_relic = None

    model.save()

    if ((parent_relic and
         parent_relic.otm1_last_child_id is not None and
         parent_relic.otm1_last_child_id == model_hash['pk'])):
        parent = parent_relic.summon()
        parent.last_child = model.pk
        parent.save()

    OTM1CommentRelic.objects.create(
        instance=instance,
        otm1_model_id=model_hash['pk'],
        otm2_model_id=model.pk,
        otm1_last_child_id=model_hash['fields'].get('last_child', None))

    return model


def make_contenttype_relics(model_hash, instance):
    """
    There must be a relic for ContentType because comments use them
    as foreign keys. However, unlike other migrations, there's no
    need to save the them, because they exist already.
    """
    fields = model_hash['fields']

    # user is a special case - it's auth.user in otm1
    # and treemap.user in otm2
    app_label = ('treemap' if fields['model'] == 'user'
                 else fields['app_label'])

    try:
        content_type_id = ContentType.objects.get(model=fields['model'],
                                                  app_label=app_label).pk

    except ContentType.DoesNotExist:
        print('SKIPPING ContentType: %s.%s'
              % (fields['app_label'], fields['model']))

        # set the content_type_id to a special number so a model's
        # conten_type can be validated before trying to import it.
        content_type_id = -1

    OTM1ModelRelic.objects.get_or_create(instance=instance,
                                         otm1_model_id=model_hash['pk'],
                                         otm2_model_name='contenttype',
                                         otm2_model_id=content_type_id)


def _uniquify_username(username):
    username_template = '%s_%%d' % username
    i = 0
    while User.objects.filter(username=username).exists():
        username = username_template % i
        i += 1

    return username


def _sanitize_username(username):
    return username.replace(' ', '_')


@atomic
def save_boundary(migration_rules, model_hash, instance):
    model = hash_to_model(migration_rules, 'boundary', model_hash, instance)
    model.save()
    OTM1ModelRelic.objects.get_or_create(
        instance=instance,
        otm1_model_id=model_hash['pk'],
        otm2_model_name='boundary',
        otm2_model_id=model.pk)

    instance.boundaries.add(model)
    return model


@atomic
def save_user(migration_rules, user_hash, instance):
    """
    Save otm1 user record into otm2.

    In the case of validation problems, username can be arbitrarily
    changed. Since we log the otm1_username in the relic, it's simple
    enough to query for all users that have a different username than
    the one stored in their relic and take further action as necessary.
    """
    user = hash_to_model(migration_rules, 'user', user_hash, instance)

    # don't save another user if this email address already exists.
    # just observe and report
    duplicate_email_qs = User.objects.filter(email__iexact=user.email)
    if duplicate_email_qs.exists():
        user = duplicate_email_qs[0]
    else:
        # replace spaces in the username.
        # then, if the sanitized username already exists,
        # uniquify it. This transformation order is important.
        # uniquification must happen as the last step.
        user.username = _uniquify_username(_sanitize_username(user.username))
        user.save()

    try:
        InstanceUser.objects.get(instance=instance,
                                 user=user)
    except InstanceUser.DoesNotExist:
        InstanceUser.objects.create(instance=instance,
                                    user=user,
                                    role=instance.default_role)

    (OTM1UserRelic
     .objects
     .get_or_create(instance=instance,
                    otm1_username=user_hash['fields']['username'],
                    otm2_user=user,
                    otm1_id=user_hash['pk'],
                    email=user_hash['fields']['email']))


def hashes_to_saved_objects(
        migration_rules, model_name, model_hashes, dependency_ids,
        model_save_fn, instance, message_receiver=None):

    model_key_map = dependency_ids.get(model_name, {})
    # the model_key_map will be filled from the
    # database each time. combined with this statement,
    # the command becomes idempotent
    hashes_to_save = (hash for hash in model_hashes
                      if hash['pk'] not in model_key_map)

    for model_hash in hashes_to_save:
        try:
            overwrite_old_pks(
                migration_rules, model_hash, model_name, dependency_ids)
            model = model_save_fn(model_hash, instance)

            if model_key_map is not None and model and model.pk:
                if callable(message_receiver):
                    message_receiver("saved model: %s" % model.pk)
                model_key_map[model_hash['pk']] = model.pk
        except Exception:
            raise


def make_model_option(migration_rules, model):
    shortflag = migration_rules[model]['command_line_flag']
    return make_option(shortflag,
                       '--%s-fixture' % model,
                       action='store',
                       type='string',
                       dest='%s_fixture' % model,
                       help='path to json dump containing %s data' % model)


from otm1_migrator.migration_rules.standard_otm1 \
    import MIGRATION_RULES as rules


class Command(InstanceDataCommand):

    option_list = (
        InstanceDataCommand.option_list +

        # add options for model fixtures
        tuple(make_model_option(rules, model) for model in rules) +

        # add other kinds of options
        (make_option('--config-file',
                     action='store',
                     dest='config_file',
                     default=None,
                     help='provide config by file instead of command line'),
         make_option(*USERPHOTO_ARGS,
                     action='store',
                     type='string',
                     dest='userphoto_path',
                     help='path to userphotos that will be imported'),
         make_option('-x', '--treephoto-path',
                     action='store',
                     type='string',
                     dest='treephoto_path',
                     help='path to treephotos that will be imported'),
         make_option('-l', '--rule-module',
                     action='store',
                     type='string',
                     dest='rule_module',
                     help='Name of the module to import rules from'))
    )

    def handle(self, *args, **options):

        if settings.DEBUG:
            self.stdout.write('In order to run this command you must manually'
                              'set DEBUG=False in your settings file. '
                              'Unfortunately, django runs out of memory when '
                              'this command is run in DEBUG mode.')
            return 1

        if options['config_file']:
            config_data = json.load(open(options['config_file'], 'r'))
            for k, v in config_data.items():
                if not options.get(k, None):
                    options[k] = v

        if options['instance']:
            # initialize system_user??
            instance, _ = self.setup_env(*args, **options)
        else:
            self.stdout.write('Invalid instance provided.')
            return 1

        rule_module = (options['rule_module'] or
                       'otm1_migrator.migration_rules.standard_otm1')
        migration_mod = importlib.import_module(rule_module)
        migration_rules = migration_mod.MIGRATION_RULES

        # look for fixtures of the form '<model>_fixture' that
        # were passed in as command line args and load them as
        # python objects
        json_hashes = {}
        for model_name in migration_rules:
            option_name = model_name + '_fixture'
            try:
                model_file = open(options[option_name], 'r')
                json_hashes[model_name] = json.load(model_file)
            except:
                json_hashes[model_name] = []
                self.stdout.write('No valid %s fixture provided ... SKIPPING'
                                  % model_name)

        # user photos live on userprofile in otm1
        userphoto_path = options.get('userphoto_path', None)
        user_photo_fixture_specified_but_not_base_path = (
            'userprofile' in json_hashes and
            json_hashes['userprofile'] and
            userphoto_path is None)

        if user_photo_fixture_specified_but_not_base_path:
            raise MigrationException('Must specify the user photo path to '
                                     'import photos. please include a %s or '
                                     '%s flag when importing.'
                                     % USERPHOTO_ARGS)

        treephoto_path = options.get('treephoto_path', None)
        treephoto_fixture_with_no_path = ('treephoto' in json_hashes and
                                          json_hashes['treephoto'] and
                                          treephoto_path is None)
        if treephoto_fixture_with_no_path:
            raise MigrationException('Must specify the tree photo path to '
                                     'import photo')

        # TODO: don't call this dependency anymore.
        # It's an idempotency checker too.
        dependency_ids = {model: {} for model in migration_rules}

        # TODO: should this be merged into MIGRATION_RULES?
        save_fns = {
            'boundary': partial(save_boundary, migration_rules),
            'user': partial(save_user, migration_rules),
            'audit': partial(save_audit, migration_rules, dependency_ids),
            'species': partial(save_species, migration_rules),
            'plot': partial(save_other_with_user, migration_rules, 'plot'),
            'tree': partial(save_other_with_user, migration_rules, 'tree'),
            'treephoto': partial(
                save_treephoto, migration_rules, treephoto_path),
            'contenttype': make_contenttype_relics,
            'userprofile': partial(process_userprofile, userphoto_path),
            'threadedcomment': partial(
                save_threadedcomment, migration_rules, dependency_ids),
            'comment': partial(
                save_comment, migration_rules, dependency_ids),
        }

        print("reading relics into memory...", end="")
        # depedency_ids is a cache of old pks to new pks, it is inflated
        # from database records for performance.
        instance_relics = OTM1UserRelic.objects.filter(instance=instance)
        for relic in instance_relics.iterator():
            dependency_ids['user'][relic.otm1_id] = relic.otm2_user_id

        model_relics =\
            OTM1ModelRelic.objects.filter(instance=instance).iterator()
        comment_relics =\
            OTM1CommentRelic.objects.filter(instance=instance).iterator()

        for relic in chain(model_relics, comment_relics):
            model_ids = dependency_ids[relic.otm2_model_name]
            model_ids[relic.otm1_model_id] = relic.otm2_model_id
        print("DONE")

        for model in migration_rules:
            if json_hashes[model]:
                # hashes must be sorted by pk for the case of models
                # that have foreign keys to themselves
                sorted_hashes = sorted(json_hashes[model],
                                       key=operator.itemgetter('pk'))
                hashes_to_saved_objects(migration_rules,
                                        model, sorted_hashes,
                                        dependency_ids,
                                        save_fns[model],
                                        instance,
                                        message_receiver=print)
