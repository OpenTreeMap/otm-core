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

from treemap.species import otm_code_search
from treemap.models import User, InstanceUser, Tree
from treemap.util import to_object_name
from treemap.management.util import InstanceDataCommand
from treemap.images import save_uploaded_image

from otm1_migrator import models
from otm1_migrator.models import (OTM1UserRelic, OTM1ModelRelic,
                                  OTM1CommentRelic, MigrationEvent)
from otm1_migrator.data_util import (dict_to_model, MigrationException,
                                     sanitize_username, uniquify_username,
                                     add_udfs_to_migration_rules, create_udfs)
from otm1_migrator import data_util

USERPHOTO_ARGS = ('-y', '--userphoto-path')


@atomic
def save_species(migration_rules, migration_event,
                 species_dict, species_obj, instance):

    species_obj.otm_code = otm_code_search(species_dict['fields']) or ''
    species_obj.save_with_user_without_verifying_authorization(
        User.system_user())

    OTM1ModelRelic.objects.create(
        instance=instance,
        migration_event=migration_event,
        otm1_model_id=species_dict['pk'],
        otm2_model_name='species',
        otm2_model_id=species_obj.pk)

    return species_obj


@atomic
def save_plot(migration_rules, migration_event,
              plot_dict, plot_obj, instance):

    if plot_dict['fields']['present'] is False:
        plot_obj = None
        pk = models.UNBOUND_MODEL_ID
    else:
        plot_obj.save_with_user_without_verifying_authorization(
            User.system_user())
        pk = plot_obj.pk

    OTM1ModelRelic.objects.create(
        instance=instance,
        migration_event=migration_event,
        otm1_model_id=plot_dict['pk'],
        otm2_model_name='plot',
        otm2_model_id=pk)
    return plot_obj


@atomic
def save_tree(migration_rules, migration_event,
              tree_dict, tree_obj, instance):

    if ((tree_dict['fields']['present'] is False or
         tree_dict['fields']['plot'] == models.UNBOUND_MODEL_ID)):
        tree_obj = None
        pk = models.UNBOUND_MODEL_ID
    else:
        tree_obj.save_with_user_without_verifying_authorization(
            User.system_user())
        pk = tree_obj.pk

    OTM1ModelRelic.objects.create(
        instance=instance,
        migration_event=migration_event,
        otm1_model_id=tree_dict['pk'],
        otm2_model_name='tree',
        otm2_model_id=pk)
    return tree_obj


@atomic
def process_userprofile(migration_rules, migration_event,
                        photo_basepath, model_dict, up_obj, instance):
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
    photo_path = model_dict['fields']['photo']
    if not photo_path:
        return None

    user = User.objects.get(pk=model_dict['fields']['user'])

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

    OTM1ModelRelic.objects.create(instance=instance,
                                  migration_event=migration_event,
                                  otm1_model_id=model_dict['pk'],
                                  otm2_model_name='userprofile',
                                  otm2_model_id=models.UNBOUND_MODEL_ID)
    return None


@atomic
def save_treephoto(migration_rules, migration_event,
                   treephoto_path, model_dict, treephoto_obj, instance):

    if model_dict['fields']['tree'] == models.UNBOUND_MODEL_ID:
        treephoto_obj = None
        pk = models.UNBOUND_MODEL_ID
    else:
        image = open(os.path.join(treephoto_path,
                                  model_dict['fields']['photo']))
        treephoto_obj.set_image(image)
        treephoto_obj.map_feature_id = (Tree
                                        .objects
                                        .values_list('plot__id', flat=True)
                                        .get(pk=treephoto_obj.tree_id))

        del model_dict['fields']['photo']

        treephoto_obj.save_with_user_without_verifying_authorization(
            User.system_user())
        pk = treephoto_obj.pk

    OTM1ModelRelic.objects.create(
        instance=instance,
        migration_event=migration_event,
        otm1_model_id=model_dict['pk'],
        otm2_model_name='treephoto',
        otm2_model_id=pk)
    return treephoto_obj


@atomic
def save_audit(migration_rules, migration_event,
               relic_ids, model_dict, audit_obj, instance):

    fields = model_dict['fields']

    # the migrator uses downcase names
    model_name = to_object_name(fields['model'])

    model_id = relic_ids[model_name][fields['model_id']]

    if model_id == models.UNBOUND_MODEL_ID:
        print("cannot save this audit. "
              "The underlying model '%s' was discarded."
              % model_name)
        return None

    audit_obj.model_id = model_id

    if ((fields['field'] == 'id' and
         fields['current_value'] == fields['model_id'])):
        audit_obj.current_value = model_id

    audit_obj.save()

    OTM1ModelRelic.objects.create(
        instance=instance,
        migration_event=migration_event,
        otm1_model_id=model_dict['pk'],
        otm2_model_name='audit',
        otm2_model_id=audit_obj.pk)
    return audit_obj


@atomic
def save_comment(migration_rules, migration_event,
                 relic_ids, model_dict, comment_obj, instance):

    comment_obj.site_id = 1

    if comment_obj.content_type_id == models.UNBOUND_MODEL_ID:
        print("Can't import comment %s because "
              "it is assigned to a ContentType (model) "
              "that does not exist in OTM2 .. SKIPPING"
              % comment_obj.comment)
        return None

    old_object_id = int(model_dict['fields']['object_pk'])
    new_object_id = relic_ids[comment_obj.content_type.model][old_object_id]

    # object_id is called object_pk in later versions
    comment_obj.object_pk = new_object_id

    comment_obj.save()

    OTM1CommentRelic.objects.create(
        instance=instance,
        migration_event=migration_event,
        otm1_model_id=model_dict['pk'],
        otm2_model_id=comment_obj.pk)

    return comment_obj


@atomic
def save_threadedcomment(migration_rules, migration_event,
                         relic_ids, model_dict, tcomment_obj, instance):

    tcomment_obj.site_id = 1

    if tcomment_obj.content_type_id == models.UNBOUND_MODEL_ID:
        print("Can't import threadedcomment %s because "
              "it is assigned to a ContentType (model) "
              "that does not exist in OTM2 .. SKIPPING"
              % tcomment_obj.comment)
        return None
    content_type = ContentType.objects.get(pk=tcomment_obj.content_type_id)

    old_object_id = model_dict['fields']['object_id']
    try:
        new_object_id = relic_ids[content_type.model][old_object_id]
    except KeyError:
        raise MigrationException("threadedcomment dependency not met. "
                                 "did you import %s yet?"
                                 % tcomment_obj.content_type.model)

    if new_object_id == models.UNBOUND_MODEL_ID:
        print("Can't import threadedcomment %s because "
              "it is assigned to a model object '%s:%s' that does "
              "not exist in OTM2. It is probably the case that it "
              "was marked as deleted in OTM1. .. SKIPPING"
              % (model_dict['pk'], content_type.model, old_object_id))
        return None

    tcomment_obj.save()

    # object_id is called object_pk in later versions
    tcomment_obj.object_pk = new_object_id

    # find relic/dependency id for the parent and set that.
    if model_dict['fields']['parent']:
        parent_relic = (OTM1CommentRelic.objects
                        .get(instance=instance,
                             otm1_model_id=model_dict['fields']['parent']))
        tcomment_obj.parent_id = parent_relic.otm2_model_id

    else:
        parent_relic = None

    tcomment_obj.save()

    if ((parent_relic and
         parent_relic.otm1_last_child_id is not None and
         parent_relic.otm1_last_child_id == model_dict['pk'])):
        parent = parent_relic.summon()
        parent.last_child = tcomment_obj.pk
        parent.save()

    OTM1CommentRelic.objects.create(
        instance=instance,
        migration_event=migration_event,
        otm1_model_id=model_dict['pk'],
        otm2_model_id=tcomment_obj.pk,
        otm1_last_child_id=model_dict['fields'].get('last_child', None))

    return tcomment_obj


@atomic
def process_contenttype(migration_rules, migration_event,
                        model_dict, ct_obj, instance):
    """
    There must be a relic for ContentType because comments use them
    as foreign keys. However, unlike other migrations, there's no
    need to save the them, because they exist already.
    """
    fields = model_dict['fields']

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
        content_type_id = models.UNBOUND_MODEL_ID

    OTM1ModelRelic.objects.create(instance=instance,
                                  migration_event=migration_event,
                                  otm1_model_id=model_dict['pk'],
                                  otm2_model_name='contenttype',
                                  otm2_model_id=content_type_id)
    return None


@atomic
def save_boundary(migration_rules, migration_event,
                  model_dict, boundary_obj, instance):
    boundary_obj.save()
    OTM1ModelRelic.objects.create(
        instance=instance,
        migration_event=migration_event,
        otm1_model_id=model_dict['pk'],
        otm2_model_name='boundary',
        otm2_model_id=boundary_obj.pk)

    instance.boundaries.add(boundary_obj)
    return boundary_obj


@atomic
def save_user(migration_rules, migration_event, user_dict, user_obj, instance):
    """
    Save otm1 user record into otm2.

    In the case of validation problems, username can be arbitrarily
    changed. Since we log the otm1_username in the relic, it's simple
    enough to query for all users that have a different username than
    the one stored in their relic and take further action as necessary.
    """
    # don't save another user if this email address already exists.
    # just observe and report
    users_with_this_email = User.objects.filter(
        email__iexact=user_dict['fields']['email'])
    if users_with_this_email.exists():
        user_obj = users_with_this_email[0]
    else:
        # replace spaces in the username.
        # then, if the sanitized username already exists,
        # uniquify it. This transformation order is important.
        # uniquification must happen as the last step.
        user_obj = user_obj
        user_obj.username = uniquify_username(
            sanitize_username(user_obj.username))
        user_obj.save()

    try:
        InstanceUser.objects.get(instance=instance, user=user_obj)
    except InstanceUser.DoesNotExist:
        InstanceUser.objects.create(instance=instance,
                                    user=user_obj,
                                    role=instance.default_role)

    relic = OTM1UserRelic(instance=instance,
                          migration_event=migration_event,
                          otm2_model_id=user_obj.pk,
                          otm1_model_id=user_dict['pk'],
                          otm1_username=user_dict['fields']['username'],
                          email=user_dict['fields']['email'])
    relic.save()
    return user_obj


def save_objects(migration_rules, model_name, model_dicts, relic_ids,
                 model_process_fn, instance, message_receiver=None):

    if model_name not in relic_ids:
        relic_ids[model_name] = {}
    model_key_map = relic_ids[model_name]
    # the model_key_map will be filled from the
    # database each time. combined with this statement,
    # the command becomes idempotent
    dicts_to_save = (dict for dict in model_dicts
                     if dict['pk'] not in model_key_map)

    for model_dict in dicts_to_save:
        dependencies = (migration_rules
                        .get(model_name, {})
                        .get('dependencies', {})
                        .items())

        # rewrite the fixture so that otm1 pks are replaced by
        # their corresponding otm2 pks
        if dependencies:
            for name, field in dependencies:
                old_id = model_dict['fields'][field]
                if old_id:
                    old_id_to_new_id = relic_ids[name]
                    try:
                        new_id = old_id_to_new_id[old_id]
                    except KeyError:
                        raise MigrationException("Dependency not found. "
                                                 "Have you imported %s yet?"
                                                 % name)
                    model_dict['fields'][field] = new_id

        model = dict_to_model(migration_rules, model_name,
                              model_dict, instance)

        if model == data_util.DO_NOT_PROCESS:
            continue
        else:
            model = model_process_fn(model_dict, model, instance)
            if model != data_util.PROCESS_WITHOUT_SAVE and model is not None:
                pk = model.pk
                for fn in migration_rules[model_name].get(
                        'postsave_actions', []):
                    fn(model, model_dict)
                if callable(message_receiver):
                    message_receiver("saved model: %s - %s" %
                                     (model_name, model.pk))
            else:
                pk = models.UNBOUND_MODEL_ID
            model_key_map[model_dict['pk']] = pk


def make_model_option(migration_rules, model):
    shortflag = migration_rules[model]['command_line_flag']
    return make_option(shortflag,
                       '--%s-fixture' % model,
                       action='store',
                       type='string',
                       dest='%s_fixture' % model,
                       help='path to json dump containing %s data' % model)


from otm1_migrator.migration_rules.standard_otm1 \
    import MIGRATION_RULES as RULES
from otm1_migrator.migration_rules.standard_otm1 \
    import MODEL_ORDER as ORDER


class Command(InstanceDataCommand):

    option_list = (
        InstanceDataCommand.option_list +

        # add options for model fixtures
        tuple(make_model_option(RULES, model) for model in RULES) +

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

        rule_module = (options['rule_module'] or
                       'otm1_migrator.migration_rules.standard_otm1')
        migration_mod = importlib.import_module(rule_module)
        migration_rules = migration_mod.MIGRATION_RULES
        try:
            model_order = migration_mod.MODEL_ORDER
        except AttributeError:
            model_order = ORDER
        try:
            udfs = migration_mod.UDFS
        except AttributeError:
            udfs = {}

        # user photos live on userprofile in otm1
        userphoto_path = options.get('userphoto_path', None)
        user_photo_fixture_specified_but_not_base_path = (
            userphoto_path is None and
            options.get('userphoto_fixture') is not None)

        if user_photo_fixture_specified_but_not_base_path:
            raise MigrationException('Must specify the user photo path to '
                                     'import photos. please include a %s or '
                                     '%s flag when importing.'
                                     % USERPHOTO_ARGS)

        treephoto_path = options.get('treephoto_path', None)
        treephoto_fixture_with_no_path = (
            treephoto_path is None and
            options.get('treephoto_fixture') is not None)

        if treephoto_fixture_with_no_path:
            raise MigrationException('Must specify the tree photo path to '
                                     'import photo')

        ################################################
        # BEGIN SIDE EFFECTS
        ################################################

        migration_event = MigrationEvent.objects.create()

        if options['instance']:
            # initialize system_user??
            instance, _ = self.setup_env(*args, **options)
        else:
            migration_event.status = MigrationEvent.FAILURE
            migration_event.save()
            self.stdout.write('Invalid instance provided.')
            return 1

        create_udfs(udfs, instance)
        add_udfs_to_migration_rules(migration_rules, udfs, instance)

        relic_ids = {model: {} for model in migration_rules}

        def default_partial(fn, *args):
            return partial(fn, migration_rules, migration_event, *args)

        # TODO: should this be merged into MIGRATION_RULES?
        process_fns = {
            'boundary': default_partial(save_boundary),
            'user': default_partial(save_user),
            'audit': default_partial(save_audit, relic_ids),
            'species': default_partial(save_species),
            'plot': default_partial(save_plot),
            'tree': default_partial(save_tree),
            'treephoto': default_partial(save_treephoto, treephoto_path),
            'contenttype': default_partial(process_contenttype),
            'userprofile': default_partial(process_userprofile,
                                           userphoto_path),
            'threadedcomment': default_partial(save_threadedcomment,
                                               relic_ids),
            'comment': default_partial(save_comment, relic_ids),
        }

        user_relics = OTM1UserRelic.objects.filter(instance=instance)
        model_relics = (OTM1ModelRelic
                        .objects
                        .filter(instance=instance)
                        .iterator())

        comment_relics = (OTM1CommentRelic
                          .objects
                          .filter(instance=instance)
                          .iterator())

        def _rpad_string(desired_length, pad_char, string):
            return string + (desired_length - len(string)) * pad_char

        self.stdout.write(_rpad_string(50, ".", "Reading relics into memory"))
        # depedency_ids is a cache of old pks to new pks, it is inflated
        # from database records for performance.
        for relic in chain(user_relics, model_relics, comment_relics):
            model = relic.otm2_model_name
            otm1_id = relic.otm1_model_id
            relic_ids[model][otm1_id] = relic.otm2_model_id
        self.stdout.write(_rpad_string(50, ".",
                                       "Done reading relics into memory"))

        def _get_json_dict(model_name):
            """
            look for fixtures of the form '<model>_fixture' that
            were passed in as command line args and load them as
            python objects
            """
            option_name = model_name + '_fixture'
            if options[option_name] and os.path.exists(options[option_name]):
                model_file = open(options[option_name], 'r')
                self.stdout.write(
                    "%sSUCCESS" %
                    _rpad_string(50, ".",
                                 "Loaded fixture '%s'" % option_name))
                json_dict = json.load(model_file)
                model_file.close()
            else:
                self.stdout.write(
                    "%sSKIPPING" %
                    _rpad_string(50, ".",
                                 "No valid '%s' fixture " % model_name))
                json_dict = None
            return json_dict

        for model in model_order:
            json_dict = _get_json_dict(model)
            if json_dict:
                # dicts must be sorted by pk for the case of models
                # that have foreign keys to themselves
                sorted_dicts = sorted(json_dict,
                                      key=operator.itemgetter('pk'))
                try:
                    save_objects(migration_rules,
                                 model, sorted_dicts,
                                 relic_ids,
                                 process_fns[model],
                                 instance,
                                 message_receiver=print)
                except MigrationException:
                    migration_event.status = MigrationEvent.FAILURE
                    migration_event.save()
                    raise

        migration_event.status = MigrationEvent.SUCCESS
        migration_event.save()
