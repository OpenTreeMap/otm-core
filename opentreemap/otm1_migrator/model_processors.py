# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import os
import pytz

from django.db.transaction import atomic
from django.contrib.contenttypes.models import ContentType

from treemap.species import otm_code_search
from treemap.models import User, InstanceUser, Tree
from treemap.util import to_object_name
from treemap.images import save_uploaded_image

from otm1_migrator import models
from otm1_migrator.models import (OTM1UserRelic, OTM1ModelRelic,
                                  OTM1CommentRelic)
from otm1_migrator.data_util import (MigrationException, sanitize_username,
                                     uniquify_username, inflate_date)


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
def process_reputation(migration_rules, migration_event,
                       model_dict, rep_obj, instance):

    iuser = InstanceUser.objects.get(user_id=model_dict['fields']['user'],
                                     instance_id=instance.id)
    iuser.reputation = model_dict['fields']['reputation']
    iuser.save()

    OTM1ModelRelic.objects.create(instance=instance,
                                  migration_event=migration_event,
                                  otm1_model_id=model_dict['pk'],
                                  otm2_model_name='reputation',
                                  otm2_model_id=models.UNBOUND_MODEL_ID)
    return None


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

    # after the initial save, `created` can be updated without
    # getting clobbered by `auto_now_add`.
    # save the object, then set the created time.
    audit_obj.save()
    audit_obj.created = inflate_date(fields['created'])
    audit_obj.save()

    OTM1ModelRelic.objects.create(
        instance=instance,
        migration_event=migration_event,
        otm1_model_id=model_dict['pk'],
        otm2_model_name='audit',
        otm2_model_id=audit_obj.pk)
    return audit_obj


@atomic
def save_treefavorite(migration_rules, migration_event,
                      fav_dict, fav_obj, instance):
    fav_obj.save()
    fav_obj.created = inflate_date(fav_dict['fields']['created'])
    fav_obj.save()

    OTM1ModelRelic.objects.create(
        instance=instance,
        migration_event=migration_event,
        otm1_model_id=fav_dict['pk'],
        otm2_model_name='treefavorite',
        otm2_model_id=fav_obj.pk)

    return fav_obj


def _base_process_comment(migration_rules, migration_event,
                          relic_ids, model_dict, comment_obj, instance):

    comment_obj.site_id = 1

    if comment_obj.content_type_id == models.UNBOUND_MODEL_ID:
        print("Can't import comment %s because "
              "it is assigned to a ContentType (model) "
              "that does not exist in OTM2 .. SKIPPING"
              % comment_obj.comment)
        return None
    content_type = ContentType.objects.get(pk=comment_obj.content_type_id)

    old_object_id = int(model_dict['fields']['object_pk'])
    try:
        new_object_id = relic_ids[content_type.model][old_object_id]
    except KeyError:
        raise MigrationException("threadedcomment dependency not met. "
                                 "did you import %s yet?"
                                 % comment_obj.content_type.model)

    if new_object_id == models.UNBOUND_MODEL_ID:
        print("Can't import comment '%s' because "
              "it's model object '%s:%s' does "
              "not exist in OTM2. It probably "
              "was marked as deleted in OTM1. .. SKIPPING"
              % (comment_obj.comment[:10] + '...',
                 content_type.model, old_object_id))
        return None

    # object_id is called object_pk in later versions
    comment_obj.object_pk = new_object_id

    return comment_obj


@atomic
def save_comment(migration_rules, migration_event,
                 relic_ids, model_dict, comment_obj, instance):

    comment_obj = _base_process_comment(migration_rules, migration_event,
                                        relic_ids, model_dict, comment_obj,
                                        instance)

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

    tcomment_obj = _base_process_comment(migration_rules, migration_event,
                                         relic_ids, model_dict, tcomment_obj,
                                         instance)

    tcomment_obj.save()

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
    otm1_email = user_dict['fields']['email']
    assert otm1_email != ''
    # don't save another user if this email address already exists.
    # just observe and report
    users_with_this_email = User.objects.filter(email__iexact=otm1_email)

    if users_with_this_email.exists():
        assert len(users_with_this_email) == 1
        user_obj = users_with_this_email[0]

        last_login = inflate_date(user_dict['fields']['last_login'])
        date_joined = inflate_date(user_dict['fields']['date_joined'])
        first_name = user_dict['fields']['first_name']
        last_name = user_dict['fields']['last_name']

        # coerce to UTC. This may not be perfectly correct, but
        # given how unlikely it is for a user to create a new account
        # on the same day they logged in with an existing account,
        # we can live with the ambiguity.
        if last_login.replace(tzinfo=pytz.UTC) > user_obj.last_login:
            user_obj.username = user_dict['fields']['username']
            user_obj.password = user_dict['fields']['password']
            user_obj.last_login = last_login

            # we're keeping the *login* info for the most recently used
            # account, but the *joined* info for the earliest created account.
            if date_joined.replace(tzinfo=pytz.UTC) < user_obj.date_joined:
                user_obj.date_joined = date_joined
            if first_name:
                user_obj.first_name = first_name
            if last_name:
                user_obj.last_name = last_name
            if user_dict['fields']['is_active']:
                user_obj.is_active = True
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
                          email=otm1_email)
    relic.save()
    return user_obj
