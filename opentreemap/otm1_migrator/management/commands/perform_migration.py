# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import os
import importlib
import json
import operator
from functools import partial
from itertools import chain

from django.conf import settings

from treemap.management.util import InstanceDataCommand

from otm1_migrator import models
from otm1_migrator.models import (OTM1UserRelic, OTM1ModelRelic,
                                  OTM1CommentRelic, MigrationEvent)
from otm1_migrator.data_util import (dict_to_model, MigrationException,
                                     add_udfs_to_migration_rules, create_udfs)

from otm1_migrator import data_util
from otm1_migrator.model_processors import (save_boundary, save_user,
                                            save_audit, save_species,
                                            save_plot, save_tree,
                                            save_treephoto,
                                            process_contenttype,
                                            process_reputation,
                                            process_userprofile,
                                            save_registrationprofile,
                                            save_threadedcomment,
                                            save_comment, save_treefavorite)

USERPHOTO_ARGS = ('-y', '--userphoto-path')


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

        old_model_dict = model_dict.copy()
        old_model_dict['fields'] = model_dict['fields'].copy()
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
            model = model_process_fn(model_dict, model, instance,
                                     old_model_dict=old_model_dict)
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


from otm1_migrator.migration_rules.standard_otm1 \
    import MIGRATION_RULES as RULES
from otm1_migrator.migration_rules.standard_otm1 \
    import MODEL_ORDER as ORDER


class Command(InstanceDataCommand):

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        # add options for model fixtures
        for model in RULES:
            parser.add_argument(
                RULES[model]['command_line_flag'],
                '--%s-fixture' % model,
                action='store',
                dest='%s_fixture' % model,
                help='path to json dump containing %s data' % model)

        # add other kinds of options
        parser.add_argument(
            '--config-file',
            action='store',
            dest='config_file',
            default=None,
            help='provide config by file instead of command line'),
        parser.add_argument(
            *USERPHOTO_ARGS,
            action='store',
            dest='userphoto_path',
            help='path to userphotos that will be imported'),
        parser.add_argument(
            '-x', '--treephoto-path',
            action='store',
            dest='treephoto_path',
            help='path to treephotos that will be imported'),
        parser.add_argument(
            '-l', '--rule-module',
            action='store',
            dest='rule_module',
            help='Name of the module to import rules from')

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
            instance, __ = self.setup_env(*args, **options)
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
            'reputation': default_partial(process_reputation),
            'registrationprofile': default_partial(save_registrationprofile),
            'userprofile': default_partial(process_userprofile,
                                           userphoto_path),
            'threadedcomment': default_partial(save_threadedcomment,
                                               relic_ids),
            'comment': default_partial(save_comment, relic_ids),
            'treefavorite': default_partial(save_treefavorite),
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
