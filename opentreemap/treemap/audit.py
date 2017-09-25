from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
import hashlib
from functools import partial
from datetime import datetime

from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry

from django.forms.models import model_to_dict
from django.utils.translation import ugettext_lazy as _
from django.utils.dateformat import format as dformat
from django.dispatch import receiver
from django.db import models as django_models
from django.db.models.signals import post_save, post_delete
from django.db.models.fields import FieldDoesNotExist
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError, connection, transaction
from django.conf import settings
from django.contrib.auth.models import Permission

from treemap.units import (is_convertible, is_convertible_or_formattable,
                           get_display_value, get_units, get_unit_name,
                           Convertible)
from treemap.util import (all_models_of_class, leaf_models_of_class,
                          to_object_name, safe_get_model_class,
                          get_pk_from_collection_audit_name,
                          get_name_from_canonical_name,
                          make_udf_name_from_key, num_format)
from treemap.decorators import classproperty

from treemap.lib.object_caches import (field_permissions,
                                       invalidate_adjuncts, udf_defs)
from treemap.lib.dates import datesafe_eq


def model_hasattr(obj, name):
    # hasattr will not work here because it
    # just calls getattr and looks for exceptions
    # not differentiating between DoesNotExist
    # and AttributeError
    try:
        getattr(obj, name)
        return True
    except ObjectDoesNotExist:
        return True
    except AttributeError:
        return False


def get_id_sequence_name(model_class):
    """
    Takes a django model class and returns the name of the autonumber
    sequence for the id field.
    Tree => 'treemap_tree_id_seq'
    Plot => 'treemap_mapfeature_id_seq'
    """
    if isinstance(model_class._meta.pk, django_models.OneToOneField):
        # Model uses multi-table inheritance (probably a MapFeature subclass)
        model_class = model_class._meta.get_parent_list()[-1]

    table_name = model_class._meta.db_table
    pk_field = model_class._meta.pk
    # django fields only have a truthy db_column when it is
    # overriding the default
    pk_column_name = pk_field.db_column or pk_field.name
    id_seq_name = "%s_%s_seq" % (table_name, pk_column_name)
    return id_seq_name


def _reserve_model_id(model_class):
    """
    queries the database to get id from the model_class's id sequence.
    this is used to reserve an id for a record that hasn't been
    created yet, in order to make references to that record.
    """
    try:
        id_seq_name = get_id_sequence_name(model_class)
        cursor = connection.cursor()
        cursor.execute("select nextval('%s');" % id_seq_name)
        results = cursor.fetchone()
        model_id = results[0]
        assert(type(model_id) in [int, long])
    except:
        msg = "There was a database error while retrieving a unique audit ID."
        raise IntegrityError(msg)

    return model_id


def _reserve_model_id_range(model_class, num):
    """
    queries the db to get a range of ids from the model_class's id sequence.
    this is used to reserve an id for a record that hasn't been
    created yet, in order to make references to that record.
    """
    try:
        id_seq_name = get_id_sequence_name(model_class)
        cursor = connection.cursor()
        cursor.execute(
            "select nextval(%(seq)s) from generate_series( 1, %(num)s) id;",
            {'seq': id_seq_name, 'num': num})

        model_ids = [row[0] for row in cursor]
        assert(type(model_id) in [int, long] for model_id in model_ids)
    except:
        msg = "There was a database error while retrieving a unique audit ID."
        raise IntegrityError(msg)

    return model_ids


@transaction.atomic
def approve_or_reject_audits_and_apply(audits, user, approved):
    """
    Approve or reject a series of audits. This method provides additional
    logic to make sure that creation audits (id audits) get applied last.

    It also performs 'Plot' audits before 'Tree' audits, since a tree
    cannot be made concrete until the corresponding plot has been created

    This method runs inside of a transaction, so if any applications fail
    we can bail without an inconsistent state
    """
    model_order = ['Plot', 'Tree']
    id_audits = []

    for audit in audits:
        if audit.field == 'id':
            id_audits.append(audit)
        else:
            approve_or_reject_audit_and_apply(audit, user, approved)

    for model in model_order:
        remaining = []
        for audit in id_audits:
            if audit.model == model:
                approve_or_reject_audit_and_apply(audit, user, approved)
            else:
                remaining.append(audit)
        id_audits = list(remaining)

    for audit in remaining:
        approve_or_reject_audit_and_apply(audit, user, approved)


def add_instance_permissions(roles):
    """
    Add all the instance permissions to all the roles passed in.
    """
    from treemap.plugin import get_instance_permission_spec
    for spec in get_instance_permission_spec():
        perm = Permission.objects.get(codename=spec['codename'])
        for role in roles:
            if role.name in spec['default_role_names']:
                role.instance_permissions.add(perm)


def add_default_permissions(instance, roles=None, models=None):
    """
    If no models are specified, use all authorizable models.

    If no roles are specified, use all roles for the specified instance.

    Add field permissions for the set of fields on each model that
    `requires_authorization` for each role, specifying the
    `role.default_permission_level`.

    For roles whose `default_permission_level` permits writes,
    also add all the `add` and `delete` model permissions for all the models,
    and their associated photo models.
    """
    # Audit is imported into models, so models can't be imported up top
    from treemap.models import MapFeaturePhoto
    if roles is None:
        roles = Role.objects.filter(instance=instance)

    if models is None:
        # We need permissions only on those subclasses of Authorizable
        # which we instantiate. Those are the leaf nodes of the
        # subclass tree, plus MapFeaturePhoto (which has subclass
        # TreePhoto).
        models = leaf_models_of_class(Authorizable) | {MapFeaturePhoto}

    for role in roles:
        _add_default_field_permissions(models, role, instance)

    _add_default_add_and_delete_permissions(models, roles)


def _add_default_add_and_delete_permissions(models, roles):
    # Each of the 'models' has built-in "add" and "delete" permissions
    # (from django.contrib.auth, e.g. Plot has "add_plot" and "delete_plot").
    # Bulk create those permissions for all 'roles' whose default permission
    # level allows write.
    role_ids = [
        role.id for role in roles
        if role.default_permission_level > FieldPermission.READ_ONLY]

    ThroughModel = Role.instance_permissions.through
    existing = ThroughModel.objects.filter(role_id__in=role_ids)
    existing_pairs = [(e.role_id, e.permission_id) for e in existing]

    perms = Role.model_permissions(models)

    role_perms = [ThroughModel(role_id=role_id, permission_id=perm.id)
                  for role_id in role_ids for perm in perms
                  if (role_id, perm.id) not in existing_pairs]

    ThroughModel.objects.bulk_create(role_perms)


def _add_default_field_permissions(models, role, instance):
    """
    Create FieldPermission entries for role using its default permission level.
    Make an entry for every tracked field of given models, as well as UDFs of
    given instance.
    """
    perms = []
    for Model in models:
        mobj = Model(instance=instance)

        model_name = mobj._model_name
        udfs = {udf.canonical_name for udf in udf_defs(instance, model_name)}

        perms += [{'model_name': model_name,
                   'field_name': field_name,
                   'role': role,
                   'instance': instance}
                  for field_name in Model.requires_authorization | udfs]

    existing = FieldPermission.objects.filter(role=role, instance=instance)
    if existing.exists():
        for perm in perms:
            perm['defaults'] = {
                'permission_level': role.default_permission_level
            }
            FieldPermission.objects.get_or_create(**perm)
    else:
        perms = [FieldPermission(**perm) for perm in perms]
        for perm in perms:
            perm.permission_level = role.default_permission_level

        FieldPermission.objects.bulk_create(perms)
        # Because we use bulk_create, we must manually trigger the save signal
        # invalidate_adjuncts would get passed a FieldPermission object if we
        # called save directly, but it doesn't use it for anything other than
        # to get the associated instance, which is the same here for all perms,
        # so just passing it the first FieldPermission should be fine
        invalidate_adjuncts(instance=perms[0])


def approve_or_reject_existing_edit(audit, user, approved):
    """
    Approve or reject a given audit that has already been
    applied

    audit    - Audit record to update
    user     - The user who is approving or rejecting
    approved - True to generate an approval, False to
               revert the change

    Note that reverting is done outside of the audit system
    to make it appear as if the change had never happend
    """

    # If the ref has already been set, this audit has
    # already been accepted or rejected so we can't do anything
    if audit.ref:
        raise Exception('This audit has already been approved or rejected')

    # If this is a 'pending' audit, you must use the pending system
    if audit.requires_auth:
        raise Exception("This audit is pending, so it can't be approved")

    # this audit will be attached to the main audit via
    # the refid
    review_audit = Audit(model=audit.model, model_id=audit.model_id,
                         instance=audit.instance, field=audit.field,
                         previous_value=audit.previous_value,
                         current_value=audit.current_value,
                         user=user)

    # Regardless of what we're doing, we need to make sure
    # 'user' is authorized to approve this edit
    _verify_user_can_apply_audit(audit, user)

    TheModel = get_auditable_class(audit.model)

    # If we want to 'review approve' this audit nothing
    # happens to the model, we're just saying "looks good!"
    if approved:
        review_audit.action = Audit.Type.ReviewApprove
    else:
        # If we are 'review rejecting' this audit we want to revert
        # the change
        #
        # note that audits cannot be pending before they have been
        # reviewed. That means that all of these audits are
        # concrete and thus can be reverted.
        review_audit.action = Audit.Type.ReviewReject

        # If the audit that we're reverting is an 'id' audit
        # it reverts the *entire* object (i.e. deletes it)
        #
        # This leads to an awkward sitution that must be handled
        # elsewhere where there are audits that appear to have
        # been applied but are on objects that have been
        # deleted.
        try:
            obj = TheModel.objects.get(pk=audit.model_id)

            # Delete the object, outside of the audit system
            if audit.field == 'id':
                models.Model.delete(obj)
            else:
                # For non-id fields we want to know if this is
                # the most recent audit on the field. If it isn't
                # the most recent then rejecting this audit doesn't
                # actually change the data
                most_recent_audits = Audit.objects\
                                          .filter(model=audit.model,
                                                  model_id=audit.model_id,
                                                  instance=audit.instance,
                                                  field=audit.field)\
                                          .order_by('-created')

                is_most_recent_audit = False
                try:
                    most_recent_audit_pk = most_recent_audits[0].pk
                    is_most_recent_audit = most_recent_audit_pk == audit.pk

                    if is_most_recent_audit:
                        obj.apply_change(audit.field,
                                         audit.clean_previous_value)
                        models.Model.save(obj)
                except IndexError:
                    pass
        except ObjectDoesNotExist:
            # As noted above, this is okay. Just mark the audit as
            # rejected
            pass

    review_audit.save()
    audit.ref = review_audit
    audit.save()

    return review_audit


def approve_or_reject_audit_and_apply(audit, user, approved):
    """
    Approve or reject a given audit and apply it to the
    underlying model if "approved" is True

    audit    - Audit record to apply
    user     - The user who is approving or rejecting
    approved - True to generate an approval, False to
               generate a rejection
    """

    # If the ref has already been set, this audit has
    # already been accepted or rejected so we can't do anything
    if audit.ref:
        raise Exception('This audit has already been approved or rejected')

    # Regardless of what we're doing, we need to make sure
    # 'user' is authorized to approve this edit
    _verify_user_can_apply_audit(audit, user)

    # Create an additional audit record to track the act of
    # the privileged user applying either PendingApprove or
    # pendingReject to the original audit.
    review_audit = Audit(model=audit.model, model_id=audit.model_id,
                         instance=audit.instance, field=audit.field,
                         previous_value=audit.previous_value,
                         current_value=audit.current_value,
                         user=user)

    TheModel = get_auditable_class(audit.model)
    if approved:
        review_audit.action = Audit.Type.PendingApprove

        # use a try/catch to determine if the is a pending insert
        # or a pending update
        try:
            obj = TheModel.objects.get(pk=audit.model_id)
            obj.apply_change(audit.field,
                             audit.clean_current_value)
            # TODO: consider firing the save signal here
            # save this object without triggering any kind of
            # UserTrackable actions. There is no straightforward way to
            # call save on the object's parent here.

            obj.save_base()

        except ObjectDoesNotExist:
            if audit.field == 'id':
                _process_approved_pending_insert(TheModel, user, audit)

    else:  # Reject
        review_audit.action = Audit.Type.PendingReject

        if audit.field == 'id':
            related_audits = get_related_audits(audit)

            for related_audit in related_audits:
                related_audit.ref = None
                related_audit.save()
                approve_or_reject_audit_and_apply(related_audit, user, False)

    review_audit.save()
    audit.ref = review_audit
    audit.save()

    return review_audit


def _process_approved_pending_insert(model_class, user, audit):
    # get all of the audits
    obj = model_class(pk=audit.model_id)
    if model_hasattr(obj, 'instance'):
        obj.instance = audit.instance

    approved_audits = get_related_audits(audit, approved_only=True)

    for approved_audit in approved_audits:
        obj.apply_change(approved_audit.field,
                         approved_audit.clean_current_value)

    obj.validate_foreign_keys_exist()
    obj.save_base()


def get_related_audits(insert_audit, approved_only=False):
    """
    Takes a pending insert audit and retrieves all *other*
    records that were part of that insert.
    """
    related_audits = Audit.objects.filter(instance=insert_audit.instance,
                                          model_id=insert_audit.model_id,
                                          model=insert_audit.model,
                                          action=Audit.Type.Insert)\
                                  .exclude(pk=insert_audit.pk)
    if approved_only:
        related_audits = related_audits.filter(
            ref__action=Audit.Type.PendingApprove)

    return related_audits


def _verify_user_can_apply_audit(audit, user):
    """
    Make sure that user has "write direct" permissions
    for the given audit's fields.

    If the model is a udf collection, verify the user has
    write directly permission on the UDF
    """

    model, field = _get_model_and_field(audit)
    Model = safe_get_model_class(model)

    if field in Model.bypasses_authorization:
        return

    perms = [perm for perm in field_permissions(user, audit.instance, model)
             if perm.field_name == field]
    if len(perms) == 1:
        if perms[0].permission_level != FieldPermission.WRITE_DIRECTLY:
                raise AuthorizeException(
                    "User %s can't edit field %s on model %s" %
                    (user, field, model))
    elif len(perms) == 0:
        raise AuthorizeException(
            "User %s can't edit field %s on model %s"
            " (No permissions found)" %
            (user, field, model))


def _get_model_and_field(audit):
    if audit.model.startswith('udf:'):
        # This comingling here isn't really great...
        # However it allows us to have a pretty external interface in that
        # UDF collections can have a single permission based on the original
        # model, instead of having to assign a bunch of new ones.
        key = get_pk_from_collection_audit_name(audit.model)
        udf = [defn for defn in udf_defs(audit.instance)
               if defn.pk == key][0]
        field = make_udf_name_from_key(udf.name)
        model = udf.model_type
    else:
        field = audit.field
        model = audit.model
    return model, field


@transaction.atomic
def bulk_create_with_user(auditables, user):
    if not auditables or len({a._model_name for a in auditables}) != 1:
        raise Exception('Auditables must be a nonempty list of the same model')

    ModelClass = get_auditable_class(auditables[0]._model_name)
    model_ids = _reserve_model_id_range(ModelClass, len(auditables))

    audits = []
    for model, model_id in zip(auditables, model_ids):
        model.pk = model_id
        model.id = model_id

        updates = model._updated_fields()
        audits.extend(model._make_audits(user, Audit.Type.Insert, updates))

    ModelClass.objects.bulk_create(auditables)
    Audit.objects.bulk_create(audits)


class UserTrackingException(Exception):
    pass


class Dictable(object):
    def as_dict(self):
        return model_to_dict(self, fields=[field.name for field in
                                           self._meta.fields])

    @property
    def hash(self):
        values = ['%s:%s' % (k, v) for (k, v) in self.as_dict().iteritems()]
        string = '|'.join(values).encode('utf-8')
        return hashlib.md5(string).hexdigest()


class UserTrackable(Dictable):
    '''
    Track `tracked_fields` with `Audit` records.

    Leaf classes should implement an `__init__` method, and
    call `self.populate_previous_state()` after initialization
    is otherwise complete.

    If changes to a model instance fail to produce `Audit` records,
    chances are the model's `__init__` did not call
    `self.populate_previous_state()`.

    Rationale (tl;dr)
    -----------------

    `populate_previous_state` calls `as_dict`.

    If a class further down the `super` chain has not been initialized,
    `as_dict` may raise an `AttributeError` due to attributes not
    having been set yet.

    After the leaf class calls `super(...).__init__()`, it can be
    assured that all super classes have initialized themselves,
    at which point `as_dict` will succeed.

    There are ways to get around this, such as subclassing
    a field to have a `contribute_to_class` method that
    sets a descriptor on the model class.

    That approach is very deep tinkering with the model
    instantiation procedure, and is best avoided by preventing
    circular dependencies in the initialization process
    in the first place.
    '''
    def __init__(self, *args, **kwargs):
        # _do_not_track returns the static do_not_track set unioned
        # with any fields that are added during instance initialization.
        self._do_not_track = self.do_not_track
        super(UserTrackable, self).__init__(*args, **kwargs)

        # It is the leaf class' responsibility to call
        # `self.populate_previous_state()` after initialization is
        # otherwise complete.

    def apply_change(self, key, orig_value):
        # TODO: if a field has a default value, don't
        # set the original value when the original value
        # is none, set it to the default value of the field.
        setattr(self, key, orig_value)

    @classproperty
    def do_not_track(cls):
        '''
        do_not_track returns the set of statically defined field names
        on the model that should not be tracked.

        Subclasses of UserTrackable should return their own field names
        unioned with those of their immediate superclass.
        '''
        # updated_at and updated_by are "metadata" and
        # it does not make sense to redundantly track when they change,
        # assign reputation for editing them, etc.
        return {'instance', 'updated_at', 'updated_by'}

    @property
    def tracked_fields(self):
        return [field.name
                for field
                in self._meta.fields
                if field.name not in self._do_not_track]

    def _direct_updates(self, updates, user):
        pending_fields = self.get_pending_fields(user)
        return {key: val for key, val in updates.iteritems()
                if key not in pending_fields}

    def _pending_updates(self, updates, user):
        pending_fields = self.get_pending_fields(user)
        return {key: val for key, val in updates.iteritems()
                if key in pending_fields}

    def _updated_fields(self):
        updated = {}
        d = self.as_dict()
        for key in d:
            if key not in self._do_not_track:
                old = self.get_previous_state().get(key, None)
                new = d.get(key, None)

                if isinstance(new, datetime) or isinstance(old, datetime):
                    if not datesafe_eq(new, old):
                        updated[key] = (old, new)
                else:
                    if new != old:
                        updated[key] = (old, new)

        return updated

    def fields_were_updated(self):
        return len(self._updated_fields()) > 0

    @property
    def _model_name(self):
        return self.__class__.__name__

    def delete_with_user(self, user, *args, **kwargs):
        models.Model.delete(self, *args, **kwargs)
        self.clear_previous_state()

    def save_with_user(self, user, *args, **kwargs):
        models.Model.save(self, *args, **kwargs)
        self.populate_previous_state()

    def save(self, *args, **kwargs):
        raise UserTrackingException(
            'All changes to %s objects must be saved via "save_with_user"' %
            (self._model_name))

    def delete(self, *args, **kwargs):
        raise UserTrackingException(
            'All deletes to %s objects must be saved via "delete_with_user"' %
            (self._model_name))

    def is_user_administrator(self, user):
        try:
            instance = self.get_instance()
        except AuthorizeException:
            return False
        if not user or not user.is_authenticated():
            return False
        return user.get_role(instance).name == Role.ADMINISTRATOR

    def fields(self):
        return self.as_dict().keys()

    def get_previous_state(self):
        return self._previous_state

    def clear_previous_state(self):
        self._previous_state = {}

    def populate_previous_state(self):
        """
        A helper method for setting up a previous state dictionary
        without the elements that should remained untracked
        """
        if self.pk is None:
            # User created the object as "MyObj(field1=...,field2=...)"
            # the saved state will include these changes but the actual
            # "initial" state is empty so we clear it here
            self.clear_previous_state()
        else:
            self._previous_state = {k: v for k, v in self.as_dict().iteritems()
                                    if k not in self._do_not_track}

    def get_pending_fields(self, user=None):
        """
        Get a list of fields that are currently being updated which would
        require a pending edit.

        Should return a list-like object. An empty list is a no-op.

        Note: Since Authorizable doesn't control what happens to "pending" or
        "write with audit" fields it is the subclasses responsibility to
        handle the difference. A naive implementation (i.e. just subclassing
        Authorizable) treats "write with audit" that same as "write directly"
        """
        return []


class FieldPermission(models.Model):
    model_name = models.CharField(max_length=255)
    field_name = models.CharField(max_length=255)
    role = models.ForeignKey('Role')
    instance = models.ForeignKey('Instance')

    NONE = 0
    READ_ONLY = 1
    WRITE_WITH_AUDIT = 2
    WRITE_DIRECTLY = 3
    choices = (
        (NONE, _("Invisible")),
        (READ_ONLY, _("Read Only")),
        (WRITE_WITH_AUDIT, _("Pending Write Access")),
        (WRITE_DIRECTLY, _("Full Write Access")))
    permission_level = models.IntegerField(choices=choices, default=NONE)

    class Meta:
        unique_together = ('model_name', 'field_name', 'role', 'instance')

    def __unicode__(self):
        return "%s.%s - %s - %s" % (self.model_name,
                                    self.field_name,
                                    self.role,
                                    self.choices[self.permission_level][1])

    @property
    def allows_reads(self):
        return self.permission_level >= self.READ_ONLY

    @property
    def allows_writes(self):
        return self.permission_level >= self.WRITE_WITH_AUDIT

    @property
    def display_field_name(self):
        if self.field_name.startswith('udf:'):
            base_name = get_name_from_canonical_name(self.field_name)
        else:
            Model = safe_get_model_class(self.model_name)
            field = Model._meta.get_field(self.field_name)
            base_name = getattr(field, 'verbose_name', self.field_name)

        return base_name.replace('_', ' ').title()

    @property
    def full_name(self):
        return "{}.{}".format(self.model_name, self.field_name)

    def clean(self):
        try:
            cls = get_authorizable_class(self.model_name)
            cls._meta.get_field(self.field_name)
            assert issubclass(cls, Authorizable)
        except KeyError:
            raise ValidationError(
                "Model '%s' does not exist or is not Authorizable." %
                self.model_name)
        except FieldDoesNotExist as e:
            raise ValidationError("%s: Model '%s' does not have field '%s'"
                                  % (e.__class__.__name__,
                                     self.model_name,
                                     self.field_name))
        except AssertionError as e:
            raise ValidationError("%s: '%s' is not an Authorizable model. "
                                  "FieldPermissions can only be set "
                                  "on Authorizable models." %
                                  (e.__class__.__name__,
                                   self.model_name))

    def save(self, *args, **kwargs):
        self.full_clean()
        super(FieldPermission, self).save(*args, **kwargs)


post_save.connect(invalidate_adjuncts, sender=FieldPermission)
post_delete.connect(invalidate_adjuncts, sender=FieldPermission)


class RoleManager(models.Manager):
    def get_role(self, instance, user=None):
        if user is None or user.is_anonymous():
            return instance.default_role
        return user.get_role(instance)


class Role(models.Model):
    # special role names, used in the app
    DEFAULT_ROLE_NAMES = ('administrator', 'editor', 'public')
    ADMINISTRATOR, EDITOR, PUBLIC = DEFAULT_ROLE_NAMES

    objects = RoleManager()

    name = models.CharField(max_length=255)
    instance = models.ForeignKey('Instance', null=True, blank=True)

    default_permission_level = models.IntegerField(
        db_column='default_permission',
        choices=FieldPermission.choices,
        default=FieldPermission.NONE)

    instance_permissions = models.ManyToManyField(Permission)

    rep_thresh = models.IntegerField()

    def can_create(self, Model):
        return self._can_do_action(Model, 'add')

    def can_delete(self, Model):
        return self._can_do_action(Model, 'delete')

    def _can_do_action(self, Model, action):
        codename = self.permission_codename(Model, action)
        return self.has_permission(codename, Model)

    @classmethod
    def permission_codename(clz, Model, action, photo=False):
        """
        Return name of built-in permission (django.contrib.auth) for
        performing 'action' on 'Model'.
        """
        photo = 'photo' if photo else ''
        return '{}_{}{}'.format(action, Model.__name__.lower(), photo)

    @classmethod
    def model_permissions(clz, models, actions=None,
                          include_photos=True):
        if actions is None:
            actions = ['add', 'delete']
        perm_names = [Role.permission_codename(Model, action)
                      for Model in models for action in actions]
        if include_photos:
            perm_names += [
                Role.permission_codename(Model, action, photo=True)
                for Model in models for action in ['add', 'delete']
                if Model.__name__ != 'Plot']
        return Permission.objects.filter(codename__in=perm_names)

    def has_permission(self, codename, Model=None):
        """
        Return true if role has permission 'codename' for 'Model';
        otherwise return false. 'Model' may be None.
        """
        qs = self.instance_permissions.filter(codename=codename)
        if Model is not None:
            content_type = ContentType.objects.get_for_model(Model)
            qs = qs.filter(content_type=content_type)
        return qs.exists()

    def __unicode__(self):
        return '{} ({})'.format(self.name, self.pk)


class AuthorizeException(Exception):
    def __init__(self, name):
        super(AuthorizeException, self).__init__(name)


class Authorizable(UserTrackable):
    """
    Determines whether or not a user can save based on the
    edits they have attempted to make.
    """

    # `always_writable` fields are also always readable.
    @classproperty
    def always_writable(cls):
        return {'id'}

    def __init__(self, *args, **kwargs):
        super(Authorizable, self).__init__(*args, **kwargs)

        self._has_been_masked = False

    def get_instance(self):
        instance = getattr(self, 'instance', None)
        if not instance:
            raise AuthorizeException(_(
                "Cannot retrieve permissions for {} with id {} because "
                "it does not have an instance associated with it.".format(
                    self.__class__.__name__, self.pk)))
        return instance

    def _get_writable_perms_set(self, user, direct_only=False):

        perms = self._perms_for_user(user)

        if direct_only:
            perm_set = {perm.field_name
                        for perm in perms
                        if perm.permission_level ==
                        FieldPermission.WRITE_DIRECTLY}
        else:
            perm_set = {perm.field_name for perm in perms
                        if perm.allows_writes}

        return perm_set.union(self.bypasses_authorization)

    def user_can_delete(self, user):
        can_delete = user.get_role(self.get_instance()).can_delete(
            self.__class__)
        if not can_delete:
            if getattr(self, 'users_can_delete_own_creations', False):
                can_delete = self.was_created_by(user)
        return can_delete

    def was_created_by(self, user):
        fields_created_by_user = Audit.objects.filter(
            model=self.__class__.__name__,
            model_id=self.id,
            action=Audit.Type.Insert,
            user=user,
        )
        return fields_created_by_user.exists()

    def user_can_create(self, user):
        return user.get_role(self.get_instance()).can_create(self.__class__)

    def _assert_not_masked(self):
        """
        Raises an exception if the object has been masked.
        This assertion should be called by any method that
        shouldn't operate on masked models.
        """
        if self._has_been_masked:
            raise AuthorizeException(
                "Operation cannot be performed on a masked object.")

    def get_pending_fields(self, user):
        """
        Evaluates the permissions for the current user and collects
        fields that inheriting subclasses will want to treat as
        special pending_edit fields.
        """
        perms = self._perms_for_user(user)
        fields_to_audit = []
        tracked_fields = self.tracked_fields
        for perm in perms:
            if ((perm.permission_level == FieldPermission.WRITE_WITH_AUDIT and
                 perm.field_name in tracked_fields and
                 perm.field_name not in self.bypasses_authorization)):

                fields_to_audit.append(perm.field_name)

        return fields_to_audit

    def mask_unauthorized_fields(self, user):
        readable_fields = self.visible_fields(user)

        fields = set(self.get_previous_state().keys())
        unreadable_fields = fields - readable_fields

        for field_name in unreadable_fields:
            self.apply_change(field_name, None)

        self._has_been_masked = True

    def _perms_for_user(self, user):
        return field_permissions(user, self.get_instance(), self._model_name)

    def visible_fields(self, user):
        perms = self._perms_for_user(user)
        always_readable = self.bypasses_authorization

        return always_readable | \
            {perm.field_name for perm in perms if perm.allows_reads}

    def field_is_visible(self, user, field):
        return field in self.visible_fields(user)

    def editable_fields(self, user):
        perms = self._perms_for_user(user)

        return self.bypasses_authorization | \
            {perm.field_name for perm in perms if perm.allows_writes}

    def field_is_editable(self, user, field):
        return field in self.editable_fields(user)

    def save_with_user(self, user, *args, **kwargs):
        self._assert_not_masked()

        if self.pk is not None:
            for field in self._updated_fields():
                if field not in self._get_writable_perms_set(user):
                    raise AuthorizeException("Can't edit field %s on %s" %
                                             (field, self._model_name))

        # If `WRITE_WITH_AUDIT` (i.e. pending write) is resurrected,
        # this test will prevent `_PendingAuditable` from getting called
        # and making the audit objects required for approval or rejection.
        elif not self.user_can_create(user):
            raise AuthorizeException("%s does not have permission to "
                                     "create new %s objects." %
                                     (user, self._model_name))

        super(Authorizable, self).save_with_user(user, *args, **kwargs)

    def save_with_system_user_bypass_auth(self,
                                          *args,
                                          **kwargs):
        from treemap.models import User
        super(Authorizable, self).save_with_user(User.system_user(),
                                                 auth_bypass=True,
                                                 *args, **kwargs)

    def delete_with_user(self, user, *args, **kwargs):
        self._assert_not_masked()

        if self.user_can_delete(user):
            super(Authorizable, self).delete_with_user(user, *args, **kwargs)
        else:
            raise AuthorizeException("%s does not have permission to "
                                     "delete %s %s." %
                                     (user, self._model_name, self.id))

    @classproperty
    def bypasses_authorization(cls):
        return cls.do_not_track | cls.always_writable

    @classproperty
    def requires_authorization(cls):
        """
        Return the set of fieldnames that require FieldPermission
        in order to read or write.
        """
        return {f.name for f in cls._meta.fields
                if f.name not in cls.bypasses_authorization}


class AuditException(Exception):
    pass


class Auditable(UserTrackable):
    """
    Watches an object for changes and logs them

    If you want to use this with Authorizable, you should mixin
    PendingAuditable, which joins both classes together nicely
    """
    def audits(self):
        return Audit.audits_for_object(self)

    def delete_with_user(self, user, *args, **kwargs):
        a = Audit(
            model=self._model_name,
            model_id=self.pk,
            instance=self.instance if hasattr(self, 'instance') else None,
            user=user, action=Audit.Type.Delete)

        super(Auditable, self).delete_with_user(user, *args, **kwargs)
        a.save()

    def validate_foreign_keys_exist(self):
        """
        This method walks each field in the
        model to see if any foreign keys are available.

        There are cases where an object has a reference
        to a pending foreign key that is not caught during
        the django field validation process. Running this
        validation protects against these.
        """
        for field in self._meta.fields:

            is_fk = isinstance(field, models.ForeignKey)
            is_required = (field.null is False or field.blank is False)

            if is_fk and field != self._meta.pk:
                try:
                    related_model = getattr(self, field.name)
                    if related_model is not None:
                        id = related_model.pk
                        cls = field.rel.to
                        cls.objects.get(pk=id)
                    elif is_required:
                        raise IntegrityError(
                            "%s has null required field %s" %
                            (self, field.name))
                except ObjectDoesNotExist:
                    raise IntegrityError("%s has non-existent %s" %
                                         (self, field.name))

    def save_with_user(self, user, updates=None, *args, **kwargs):
        action = Audit.Type.Insert if self.pk is None else Audit.Type.Update

        # We need to stash the updated fields, because `save` will change them
        if updates is None:
            updates = self._updated_fields()
        elif 'updates' in kwargs:
            del kwargs['updates']

        # We need to run the super method to get a pk to put in the audits
        super(Auditable, self).save_with_user(user, *args, **kwargs)
        audits = list(self._make_audits(user, action, updates))

        Audit.objects.bulk_create(audits)
        ReputationMetric.apply_adjustment(*audits)

    def _make_audits(self, user, audit_type, updates):
        """Creates Audit objects suitable for using in a bulk_create
        The object must have a pk set (this may be a reserved id)

        user - The user making the change
        audit_type - This should be Audit.Type.Insert or Audit.Type.Update
        """
        if self.pk is None:
            raise AuditException('Cannot create audits for a model with no pk')

        direct_updates = self._direct_updates(updates, user)

        # If this is an insert we need to make an Audit record for id
        # (This field is normally not tracked)
        if audit_type == Audit.Type.Insert:
            direct_updates['id'] = (None, self.pk)

        instance = self.instance if hasattr(self, 'instance') else None

        def make_audit(field, prev_val, cur_val):
            return Audit(model=self._model_name, model_id=self.pk,
                         instance=instance, field=field,
                         previous_value=prev_val,
                         current_value=cur_val,
                         user=user, action=audit_type,
                         requires_auth=False,
                         ref=None)

        for [field, (prev_value, next_value)] in direct_updates.iteritems():
            yield make_audit(field, prev_value, next_value)

    @property
    def hash(self):
        """ Return a unique hash for this object """
        # Since this is an audited object each change will
        # manifest itself in the audit log, essentially keeping
        # a revision id of this instance. Since each primary
        # key will be unique, we can just use that for the hash
        audits = Audit.objects.filter(model=self._model_name)\
                              .filter(model_id=self.pk)\
                              .order_by('-updated')

        # Occasionally Auditable objects will have no audit records,
        # this can happen if it was imported without using save_with_user
        try:
            audit_string = str(audits[0].pk)
        except IndexError:
            audit_string = 'none'

        string_to_hash = '%s:%s:%s' % (self._model_name, self.pk, audit_string)

        return hashlib.md5(string_to_hash).hexdigest()

    @classmethod
    def action_format_string_for_audit(clz, audit):
        if audit.field == 'id' or audit.field is None:
            lang = {
                Audit.Type.Insert: _('created a %(model)s'),
                Audit.Type.Update: _('updated the %(model)s'),
                Audit.Type.Delete: _('deleted the %(model)s'),
                Audit.Type.PendingApprove: _('approved an '
                                             'edit to the %(model)s'),
                Audit.Type.PendingReject: _('rejected an '
                                            'edit to the %(model)s')
            }
        else:
            lang = {
                Audit.Type.Insert: _('set %(field)s to %(value)s'),
                Audit.Type.Update: _('set %(field)s to %(value)s'),
                Audit.Type.Delete: _('deleted %(field)s'),
                Audit.Type.PendingApprove: _('approved setting '
                                             '%(field)s to %(value)s'),
                Audit.Type.PendingReject: _('rejecting setting '
                                            '%(field)s to %(value)s')
            }
        return lang[audit.action]


class _PendingAuditable(Auditable):
    """Subclasses Auditable to add support for pending audits.
    You should never use this directly, since it requires Authorizable.
    Instead use PendingAuditable (no underscore)
    """
    def __init__(self, *args, **kwargs):
        super(_PendingAuditable, self).__init__(*args, **kwargs)
        self.is_pending_insert = False

    def full_clean(self, *args, **kwargs):
        raise TypeError("all calls to full clean must be done via "
                        "'full_clean_with_user'")

    def full_clean_with_user(self, user):
        if self.user_can_create(user):
            exclude_fields = []
        else:
            # If we aren't making a real object then we shouldn't
            # check foreign key contraints. These will be checked
            # when the object is actually made. They are also enforced
            # at the database level
            exclude_fields = [
                field for field in self._meta.fields
                if isinstance(field, models.ForeignKey)]

        super(_PendingAuditable, self).full_clean(exclude=exclude_fields)

    def get_active_pending_audits(self):
        return self.audits()\
                   .filter(requires_auth=True)\
                   .filter(ref__isnull=True)\
                   .order_by('-created')

    def save_with_system_user_bypass_auth(self, *args, **kwargs):
        from treemap.models import User
        return self.save_with_user(User.system_user(),
                                   auth_bypass=True, *args, **kwargs)

    @transaction.atomic
    def save_with_user(self, user, auth_bypass=False, *args, **kwargs):
        if self.is_pending_insert:
            raise Exception("You have already saved this object.")

        if auth_bypass in kwargs:
            del kwargs['auth_bypass']

        updates = self._updated_fields()
        pending_updates = self._pending_updates(updates, user)

        # Before saving we need to restore any pending values to their
        # previous state
        for pending_field, (old_val, __) in pending_updates.iteritems():
            try:
                self.apply_change(pending_field, old_val)
            except ValueError:
                pass

        is_insert = self.pk is None

        if ((self.user_can_create(user) or not is_insert or auth_bypass)):
            # Auditable will make the audits for us (including pending audits)
            return super(_PendingAuditable, self).save_with_user(
                user, updates=updates, *args, **kwargs)
        else:
            # In the pending insert case we never save the model, only audits
            # Thus we need to reserve a PK to place in the Audit row
            model_id = _reserve_model_id(
                get_authorizable_class(self._model_name))
            self.pk = model_id
            self.id = model_id  # for e.g. Plot, where pk != id
            self.is_pending_insert = True

            action = Audit.Type.Insert if is_insert else Audit.Type.Update
            audits = list(self._make_audits(user, action, updates))

            Audit.objects.bulk_create(audits)
            ReputationMetric.apply_adjustment(*audits)

    def _make_audits(self, user, audit_type, updates):
        """Creates Audit objects suitable for using in a bulk_create
        The object must have a pk set (this may be a reserved id)

        user - The user making the change
        audit_type - This should be Audit.Type.Insert or Audit.Type.Update
        """
        normal_audits = super(_PendingAuditable, self)._make_audits(
            user, audit_type, updates)

        for audit in normal_audits:
            if self.is_pending_insert and audit.field == 'id':
                audit.requires_auth = True
            yield audit

        pending_updates = self._pending_updates(updates, user)

        instance = self.instance if hasattr(self, 'instance') else None

        def make_pending_audit(field, prev_val, cur_val):
            return Audit(model=self._model_name, model_id=self.pk,
                         instance=instance, field=field,
                         previous_value=prev_val,
                         current_value=cur_val,
                         user=user, action=audit_type,
                         requires_auth=True,
                         ref=None)

        for [field, (prev_value, next_value)] in pending_updates.iteritems():
            yield make_pending_audit(field, prev_value, next_value)


class PendingAuditable(Authorizable, _PendingAuditable):
    """
    Ties together Authorizable and Auditable, mainly for the purpose of making
    pending Audits when the user does not have permission to directly update
    a field

    You should probably be using this class instead of mixing in both
    Auditable and Authorizable
    """
    pass


###
# TODO:
# Test fail in saving on base object
# Test null values
###
class Audit(models.Model):
    model = models.CharField(max_length=255, null=True, db_index=True)
    model_id = models.IntegerField(null=True, db_index=True)
    instance = models.ForeignKey(
        'Instance', null=True, blank=True, db_index=True)

    field = models.CharField(max_length=255, null=True)
    previous_value = models.TextField(null=True)
    current_value = models.TextField(null=True, db_index=True)

    user = models.ForeignKey('treemap.User')
    action = models.IntegerField()

    """
    These two fields are part of the pending edit system

    If requires_auth is True then this audit record represents
    a change that was *requested* but not applied.

    When an authorized user approves a pending edit
    it creates an audit record on this model with an action
    type of either "PendingApprove" or "PendingReject"

    ref can be set on *any* audit to note that it has been looked
    at and approved or rejected. If this is the case, the ref
    audit will be of type "ReviewApproved" or "ReviewRejected"

    An audit that is "PendingApproved/Rejected" cannot be be
    "ReviewApproved/Rejected"
    """

    def __init__(self, *args, **kwargs):
        super(Audit, self).__init__(*args, **kwargs)
        # attempting to store a list in a text field will produce a
        # printed representation of a python object, which cannot be
        # safely deserialized (without using eval). For audits on
        # multichoice udfs, we need to store JSON in order to be able
        # to work with these values. Since the audit object doesn't
        # carry a direct reference to the udfd in question, it should
        # be sufficient to just inspect the type and encode lists.
        if isinstance(self.previous_value, list):
            self.previous_value = json.dumps(self.previous_value)
        if isinstance(self.current_value, list):
            self.current_value = json.dumps(self.current_value)

    requires_auth = models.BooleanField(default=False)
    ref = models.ForeignKey('Audit', null=True)

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        index_together = [
            ['instance', 'user', 'updated']
        ]

    class Type:
        Insert = 1
        Delete = 2
        Update = 3
        PendingApprove = 4
        PendingReject = 5
        ReviewApprove = 6
        ReviewReject = 7

    TYPES = {
        Type.Insert: _('Create'),
        Type.Delete: _('Delete'),
        Type.Update: _('Update'),
        Type.PendingApprove: _('Approved Pending Edit'),
        Type.PendingReject: _('Reject Pending Edit'),
        Type.ReviewReject: _('Rejected Edit'),
        Type.ReviewApprove: _('Approved Edit')
    }

    def _deserialize_value(self, value):
        """
        A helper method to transform deserialized audit strings

        When an audit record is written to the audit table, the
        value is stored as a string. When deserializing these values
        for presentation purposes or constructing objects, they
        need to be converted to their correct python value.

        Where possible, django model field classes are used to
        convert the value.
        """
        # some django fields can't handle .to_python(None), but
        # for insert audits (None -> <value>) this method will
        # still be called.
        if value is None:
            return None

        # get the model/field class for each audit record and convert
        # the value to a python object
        if self.field.startswith('udf:'):
            field_name = get_name_from_canonical_name(self.field)
            udfds = udf_defs(self.instance)

            if self.model.startswith('udf:'):
                udfd_pk = get_pk_from_collection_audit_name(self.model)
                udf_def = next((udfd for udfd in udfds if udfd.pk == udfd_pk),
                               None)
                if udf_def is not None:
                    datatype = udf_def.datatype_by_field[field_name]
            else:
                udf_def = next((udfd for udfd in udfds
                                if udfd.name == field_name and
                                udfd.model_type == self.model), None)
                if udf_def is not None:
                    datatype = udf_def.datatype_dict
            if udf_def is not None:
                return udf_def.clean_value(value, datatype)
            else:
                raise Exception(
                    'Cannot format a UDF audit whose definition has been'
                    ' deleted! This audit should be deleted as well')

        cls = get_auditable_class(self.model)
        field_cls = cls._meta.get_field(self.field)
        field_modified_value = field_cls.to_python(value)

        # handle edge cases
        if isinstance(field_cls, models.GeometryField):
            field_modified_value = GEOSGeometry(field_modified_value)
        elif isinstance(field_cls, models.ForeignKey):
            if isinstance(field_modified_value, (str, unicode)):
                # sometimes audit records have descriptive string values
                # stored in what should be a foreign key field.
                # these cannot be resolved to foreign key models.
                # unfortunately, django accepts strings as pks and
                # converts them implicitly, so it will choke on an
                # audit value with a non-parseable string, without
                # providing a decipherable error message.
                # Here we explicitly try that conversion and if
                # parsing fails, it should be the case that a readable
                # string is stored instead of a PK, so return that
                # without trying to resolve a foreign key model.
                try:
                    pk = int(field_modified_value)
                    field_modified_value = field_cls.rel.to.objects.get(
                        pk=pk)
                except ValueError:
                    pass

        return field_modified_value

    def _unit_format(self, value):
        from stormwater.models import PolygonalMapFeature

        field = self.field
        model_name = to_object_name(self.model)

        if isinstance(value, GEOSGeometry):
            if value.geom_type == 'Point':
                return '%d,%d' % (value.x, value.y)
            if value.geom_type in {'MultiPolygon', 'Polygon'}:
                value = PolygonalMapFeature.polygon_area(value)
                field = 'area'
                model_name = 'greenInfrastructure'
        elif isinstance(value, datetime):
            value = dformat(value, settings.SHORT_DATE_FORMAT)
        elif isinstance(value, list):
            # Translators: 'none' in this case refers to clearing the
            # list. Should be a human-friendly translation of 'null'
            value = '(%s)' % ', '.join(value) if value else _('none')

        if is_convertible_or_formattable(model_name, field):
            __, value = get_display_value(
                self.instance, model_name, field, value)
            if value and is_convertible(model_name, field):
                units = get_unit_name(get_units(self.instance,
                                                model_name, field))
                value += (' %s' % units)
        elif isinstance(value, float):
            return num_format(value)

        return value

    @property
    def clean_current_value(self):
        return self._deserialize_value(self.current_value)

    @property
    def clean_previous_value(self):
        return self._deserialize_value(self.previous_value)

    @property
    def current_display_value(self):
        return self._unit_format(self.clean_current_value)

    @property
    def previous_display_value(self):
        return self._unit_format(self.clean_previous_value)

    @property
    def field_display_name(self):
        if not self.field:
            return ''

        cls = get_auditable_class(self.model)
        if hasattr(cls, 'field_display_name'):
            name = cls.field_display_name(self.field)
        else:
            name = self.field

        if name.startswith('udf:'):
            return get_name_from_canonical_name(name)
        else:
            return name.replace('_', ' ')

    @property
    def display_action(self):
        return Audit.TYPES[self.action]

    @classmethod
    def audits_for_model(clz, model_name, inst, pk):
        return Audit.objects.filter(model=model_name,
                                    model_id=pk,
                                    instance=inst).order_by('created')

    @classmethod
    def pending_audits(clz):
        return Audit.objects.filter(requires_auth=True)\
                            .filter(ref__isnull=True)\
                            .order_by('created')

    @classmethod
    def audits_for_object(clz, obj):
        return clz.audits_for_model(
            obj._model_name, obj.instance, obj.pk)

    def short_descr(self):
        cls = get_auditable_class(self.model)
        # If a model has a defined short_descr method, use that
        if hasattr(cls, 'short_descr'):
            return cls.short_descr(self)

        format_string = cls.action_format_string_for_audit(self)

        model_display_name = self.model_display_name()

        return format_string % {'field': self.field_display_name,
                                'model': model_display_name.lower(),
                                'value': self.current_display_value}

    def model_display_name(self):
        cls = get_auditable_class(self.model)
        if issubclass(cls, Convertible):
            return cls.display_name(self.instance)
        else:
            return cls.__name__

    def dict(self):
        return {'model': self.model,
                'model_id': self.model_id,
                'instance_id': self.instance.pk,
                'field': self.field,
                'previous_value': self.previous_value,
                'current_value': self.current_value,
                'user_id': self.user.pk,
                'action': self.action,
                'requires_auth': self.requires_auth,
                'ref': self.ref.pk if self.ref else None,
                'created': str(self.created)}

    def __unicode__(self):
        return u"pk=%s - action=%s - %s.%s:(%s) - %s => %s" % \
            (self.pk, self.TYPES[self.action], self.model,
             self.field, self.model_id,
             self.previous_value, self.current_value)

    def is_pending(self):
        return self.requires_auth and not self.ref


class ReputationMetric(models.Model):
    """
    Assign integer scores for each model that determine
    how many reputation points are awarded/deducted for an
    approved/denied audit.
    """
    instance = models.ForeignKey('Instance')
    model_name = models.CharField(max_length=255)
    action = models.CharField(max_length=255)
    direct_write_score = models.IntegerField(null=True, blank=True)
    approval_score = models.IntegerField(null=True, blank=True)
    denial_score = models.IntegerField(null=True, blank=True)

    def __unicode__(self):
        return "%s - %s - %s" % (self.instance, self.model_name, self.action)

    @staticmethod
    def apply_adjustment(*audits):
        iusers = {}
        for audit in audits:
            try:
                rm = ReputationMetric.objects.get(instance=audit.instance,
                                                  model_name=audit.model,
                                                  action=audit.action)
            except ObjectDoesNotExist:
                return

            key = (audit.user.pk, audit.instance.pk)
            if key in iusers:
                iuser = iusers[key]
            else:
                iuser = audit.user.get_instance_user(audit.instance)
                iusers[key] = iuser

            if audit.requires_auth and audit.ref:
                review_audit = audit.ref
                if review_audit.action == Audit.Type.PendingApprove:
                    iuser.reputation += rm.approval_score
                elif review_audit.action == Audit.Type.PendingReject:
                    new_score = iuser.reputation - rm.denial_score
                    if new_score >= 0:
                        iuser.reputation = new_score
                    else:
                        iuser.reputation = 0
                else:
                    error_message = ("Referenced Audits must carry approval "
                                     "actions. They must have an action of "
                                     "PendingApprove or Pending Reject. "
                                     "Something might be very wrong with your "
                                     "database configuration.")
                    raise IntegrityError(error_message)
            elif not audit.requires_auth:
                iuser.reputation += rm.direct_write_score

        for iuser in iusers.itervalues():
            iuser.save_base()


@receiver(post_save, sender=Audit)
def audit_presave_actions(sender, instance, **kwargs):
    ReputationMetric.apply_adjustment(instance)


def _get_model_class(class_dict, cls, model_name):
    """
    Convert a model name (as a string) into the model class
    """
    if model_name.startswith('udf:'):
        from udf import UserDefinedCollectionValue
        return UserDefinedCollectionValue

    if not class_dict:
        # One-time load of class dictionary
        for c in all_models_of_class(cls):
            class_dict[c.__name__] = c

    return class_dict[model_name]


_auditable_classes = {}
_authorizable_classes = {}

get_auditable_class = partial(_get_model_class, _auditable_classes, Auditable)
get_authorizable_class = partial(_get_model_class, _authorizable_classes,
                                 Authorizable)
