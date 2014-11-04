from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import hashlib
from functools import partial
from datetime import datetime

from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry

from django.forms.models import model_to_dict
from django.utils.translation import ugettext as trans
from django.utils.dateformat import format as dformat
from django.dispatch import receiver
from django.db.models import OneToOneField
from django.db.models.signals import post_save, post_delete
from django.db.models.fields import FieldDoesNotExist
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError, connection, transaction
from django.conf import settings

from treemap.units import (is_convertible, is_convertible_or_formattable,
                           get_display_value, get_units, get_unit_name)
from treemap.util import all_subclasses
from treemap.lib.object_caches import (permissions, role_permissions,
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
    if isinstance(model_class._meta.pk, OneToOneField):
        # Model uses multi-table inheritance (probably a MapFeature subclass)
        model_class = model_class._meta.pk.related.parent_model

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


def add_default_permissions(instance, roles=None, models=None):
    # Audit is imported into models, so models can't be imported up top
    from treemap.models import MapFeature
    if roles is None:
        roles = Role.objects.filter(instance=instance)
    if models is None:
        # MapFeature is "Authorizable", but it is effectively abstract
        # Only it's subclasses should have permissions added
        models = all_subclasses(Authorizable) - {MapFeature, PendingAuditable}

    for role in roles:
        _add_default_permissions(models, role, instance)


def _add_default_permissions(models, role, instance):
    """
    Create FieldPermission entries for role using its default permission level.
    Make an entry for every tracked field of given models, as well as UDFs of
    given instance.
    """
    from udf import UserDefinedFieldDefinition

    perms = []
    for Model in models:
        mobj = Model(instance=instance)

        model_name = mobj._model_name
        udfs = [udf.canonical_name for udf in
                UserDefinedFieldDefinition.objects.filter(
                    instance=instance, model_type=model_name)]

        model_fields = set(mobj.tracked_fields + udfs)

        for field_name in model_fields:
            perms.append({
                'model_name': model_name,
                'field_name': field_name,
                'role': role,
                'instance': role.instance
            })

    existing = FieldPermission.objects.filter(role=role, instance=instance)
    if existing.exists():
        for perm in perms:
            perm['defaults'] = {'permission_level': role.default_permission}
            FieldPermission.objects.get_or_create(**perm)
    else:
        perms = [FieldPermission(**perm) for perm in perms]
        for perm in perms:
            perm.permission_level = role.default_permission
        FieldPermission.objects.bulk_create(perms)


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
    # This comingling here isn't really great...
    # However it allows us to have a pretty external interface in that
    # UDF collections can have a single permission based on the original
    # model, instead of having to assign a bunch of new ones.
    from udf import UserDefinedFieldDefinition

    if audit.model.startswith('udf:'):
        udf = UserDefinedFieldDefinition.objects.get(pk=audit.model[4:])
        field = 'udf:%s' % udf.name
        model = udf.model_type
    else:
        field = audit.field
        model = audit.model

    perms = permissions(user, audit.instance, model)

    foundperm = False
    for perm in perms:
        if perm.field_name == field:
            if perm.permission_level == FieldPermission.WRITE_DIRECTLY:
                foundperm = True
                break
            else:
                raise AuthorizeException(
                    "User %s can't edit field %s on model %s" %
                    (user, field, model))

    if not foundperm:
        raise AuthorizeException(
            "User %s can't edit field %s on model %s (No permissions found)" %
            (user, field, model))


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

        return hashlib.md5('|'.join(values)).hexdigest()


class UserTrackable(Dictable):
    def __init__(self, *args, **kwargs):
        self._do_not_track = set(['instance'])
        super(UserTrackable, self).__init__(*args, **kwargs)
        self.populate_previous_state()

    def apply_change(self, key, orig_value):
        # TODO: if a field has a default value, don't
        # set the original value when the original value
        # is none, set it to the default value of the field.
        setattr(self, key, orig_value)

    def _fields_required_for_create(self):
        return [field for field in self._meta.fields
                if (not field.null and
                    not field.blank and
                    not field.primary_key and
                    not field.name in self._do_not_track)]

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
        # reserving zero in case we want
        # to create a "null-permission" later
        (NONE, "None"),
        (READ_ONLY, "Read Only"),
        (WRITE_WITH_AUDIT, "Write with Audit"),
        (WRITE_DIRECTLY, "Write Directly"))
    permission_level = models.IntegerField(choices=choices, default=NONE)

    class Meta:
        unique_together = ('model_name', 'field_name', 'role', 'instance')

    def __unicode__(self):
        return "%s.%s - %s" % (self.model_name, self.field_name, self.role)

    @property
    def allows_reads(self):
        return self.permission_level >= self.READ_ONLY

    @property
    def allows_writes(self):
        return self.permission_level >= self.WRITE_WITH_AUDIT

    @property
    def display_field_name(self):
        if self.field_name.startswith('udf:'):
            base_name = self.field_name[4:]
        else:
            base_name = self.field_name

        return base_name.replace('_', ' ').title()

    def clean(self):
        try:
            cls = get_authorizable_class(self.model_name)
            cls._meta.get_field_by_name(self.field_name)
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


class Role(models.Model):
    # special role names, used in the app
    ADMINISTRATOR = 'administrator'
    EDITOR = 'editor'
    PUBLIC = 'public'

    name = models.CharField(max_length=255)
    instance = models.ForeignKey('Instance', null=True, blank=True)
    default_permission = models.IntegerField(choices=FieldPermission.choices,
                                             default=FieldPermission.NONE)
    rep_thresh = models.IntegerField()

    @property
    def tree_permissions(self):
        return self.model_permissions('Tree')

    @property
    def plot_permissions(self):
        return self.model_permissions('Plot')

    def model_permissions(self, model_name):
        return role_permissions(self, self.instance, model_name)

    def __unicode__(self):
        return '%s (%s)' % (self.name, self.pk)


class AuthorizeException(Exception):
    def __init__(self, name):
        super(Exception, self).__init__(name)


class Authorizable(UserTrackable):
    """
    Determines whether or not a user can save based on the
    edits they have attempted to make.
    """

    def __init__(self, *args, **kwargs):
        super(Authorizable, self).__init__(*args, **kwargs)

        self._has_been_masked = False

    def _get_perms_set(self, user, direct_only=False):

        if not self.instance:
            raise AuthorizeException(trans(
                "Cannot retrieve permissions for this object because "
                "it does not have an instance associated with it."))

        perms = permissions(user, self.instance, self._model_name)

        if direct_only:
            perm_set = {perm.field_name
                        for perm in perms
                        if perm.permission_level ==
                        FieldPermission.WRITE_DIRECTLY}
        else:
            perm_set = {perm.field_name for perm in perms
                        if perm.allows_writes}
        return perm_set

    def user_can_delete(self, user):
        """
        A user is able to delete an object if they have all
        field permissions on a model.
        """

        is_admin = user.get_role(self.instance).name == Role.ADMINISTRATOR
        if is_admin:
            return True
        else:
            #TODO: This isn't checking for UDFs... should it?
            return self._get_perms_set(user) >= set(self.tracked_fields)

    def user_can_create(self, user, direct_only=False):
        """
        A user is able to create an object if they have permission on
        all required fields of its model.

        If direct_only is False this method will return true
        if the user has either permission to create directly or
        create with audits
        """
        can_create = True

        perm_set = self._get_perms_set(user, direct_only)

        for field in self._fields_required_for_create():
            if field.name not in perm_set:
                can_create = False
                break

        return can_create

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
        perms = permissions(user, self.instance, self._model_name)
        fields_to_audit = []
        tracked_fields = self.tracked_fields
        for perm in perms:
            if ((perm.permission_level == FieldPermission.WRITE_WITH_AUDIT and
                 perm.field_name in tracked_fields)):

                fields_to_audit.append(perm.field_name)

        return fields_to_audit

    def mask_unauthorized_fields(self, user):
        perms = permissions(user, self.instance, self._model_name)
        readable_fields = {perm.field_name for perm
                           in perms
                           if perm.allows_reads}

        fields = set(self.get_previous_state().keys())
        unreadable_fields = fields - readable_fields

        for field_name in unreadable_fields:
            self.apply_change(field_name, None)

        self._has_been_masked = True

    def _perms_for_user(self, user):
        return permissions(user, self.instance, self._model_name)

    def visible_fields(self, user):
        perms = self._perms_for_user(user)
        return [perm.field_name for perm in perms if perm.allows_reads]

    def field_is_visible(self, user, field):
        return field in self.visible_fields(user)

    def editable_fields(self, user):
        perms = self._perms_for_user(user)
        return [perm.field_name for perm in perms if perm.allows_writes]

    def field_is_editable(self, user, field):
        return field in self.editable_fields(user)

    @staticmethod
    def mask_queryset(qs, user):
        for model in qs:
            model.mask_unauthorized_fields(user)
        return qs

    def save_with_user(self, user, *args, **kwargs):
        self._assert_not_masked()

        if self.pk is not None:
            writable_perms = self._get_perms_set(user)
            for field in self._updated_fields():
                if field not in writable_perms:
                    raise AuthorizeException("Can't edit field %s on %s" %
                                            (field, self._model_name))

        elif not self.user_can_create(user):
            raise AuthorizeException("%s does not have permission to "
                                     "create new %s objects." %
                                     (user, self._model_name))

        super(Authorizable, self).save_with_user(user, *args, **kwargs)

    def save_with_user_without_verifying_authorization(self, user,
                                                       *args, **kwargs):
        super(Authorizable, self).save_with_user(user, auth_bypass=True,
                                                 *args, **kwargs)

    def delete_with_user(self, user, *args, **kwargs):
        self._assert_not_masked()

        if self.user_can_delete(user):
            super(Authorizable, self).delete_with_user(user, *args, **kwargs)
        else:
            raise AuthorizeException("%s does not have permission to "
                                     "delete %s objects." %
                                     (user, self._model_name))


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
        audits = Audit.objects.filter(instance__pk=self.instance_id)\
                              .filter(model=self._model_name)\
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
                Audit.Type.Insert: trans('created a %(model)s'),
                Audit.Type.Update: trans('updated the %(model)s'),
                Audit.Type.Delete: trans('deleted the %(model)s'),
                Audit.Type.PendingApprove: trans('approved an '
                                                 'edit to the %(model)s'),
                Audit.Type.PendingReject: trans('rejected an '
                                                'edit to the %(model)s')
            }
        else:
            lang = {
                Audit.Type.Insert: trans('set %(field)s to %(value)s'),
                Audit.Type.Update: trans('set %(field)s to %(value)s'),
                Audit.Type.Delete: trans('deleted %(field)s'),
                Audit.Type.PendingApprove: trans('approved setting '
                                                 '%(field)s to %(value)s'),
                Audit.Type.PendingReject: trans('rejecting setting '
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
        if (self.user_can_create(user, direct_only=True)):
            exclude_fields = []
        else:
            # If we aren't making a real object then we shouldn't
            # check foreign key contraints. These will be checked
            # when the object is actually made. They are also enforced
            # a the database level
            exclude_fields = []
            for field in self._fields_required_for_create():
                if isinstance(field, models.ForeignKey):
                    exclude_fields.append(field.name)

        super(_PendingAuditable, self).full_clean(exclude=exclude_fields)

    def get_active_pending_audits(self):
        return self.audits()\
                   .filter(requires_auth=True)\
                   .filter(ref__isnull=True)\
                   .order_by('-created')

    def save_with_user_without_verifying_authorization(self, user,
                                                       *args, **kwargs):
        return self.save_with_user(user, auth_bypass=True, *args, **kwargs)

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
        for pending_field, (old_val, _) in pending_updates.iteritems():
            try:
                self.apply_change(pending_field, old_val)
            except ValueError:
                pass

        is_insert = self.pk is None

        if ((self.user_can_create(user, direct_only=True)
             or not is_insert or auth_bypass)):
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
    requires_auth = models.BooleanField(default=False)
    ref = models.ForeignKey('Audit', null=True)

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)

    # TODO: this does nothing because south manages this app
    # and we're still on 0.7.x, which doesn't support index_together
    # after an upgrade to south 0.8.x or, more likely, to django 1.7,
    # this will be kept in sync with database versioning. For now,
    # it is manually managed using migration 0081.
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
        Type.Insert: trans('Create'),
        Type.Delete: trans('Delete'),
        Type.Update: trans('Update'),
        Type.PendingApprove: trans('Approved Pending Edit'),
        Type.PendingReject: trans('Reject Pending Edit'),
        Type.ReviewReject: trans('Rejected Edit'),
        Type.ReviewApprove: trans('Approved Edit')
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
            field_name = self.field[4:]
            udfds = udf_defs(self.instance)

            if self.model.startswith('udf:'):
                udfd_pk = int(self.model[4:])
                udf_def = next((udfd for udfd in udfds if udfd.pk == udfd_pk),
                               None)
                datatype = udf_def.datatype_by_field[field_name]
            else:
                udf_def = next((udfd for udfd in udfds
                                if udfd.name == field_name), None)
                datatype = udf_def.datatype_dict
            if udf_def is not None:
                return udf_def.clean_value(value, datatype)
            else:
                raise Exception(
                    'Cannot format a UDF audit whose definition has been'
                    ' deleted! This audit should be deleted as well')

        cls = get_auditable_class(self.model)
        field_query = cls._meta.get_field_by_name(self.field)
        field_cls, fk_model_cls, is_local, m2m = field_query
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
        model_name = self.model.lower()

        if isinstance(value, GEOSGeometry):
            if value.geom_type == 'Point':
                return '%d,%d' % (value.x, value.y)
            if value.geom_type in {'MultiPolygon', 'Polygon'}:
                value = value.area
        elif isinstance(value, datetime):
            value = dformat(value, settings.SHORT_DATE_FORMAT)

        if is_convertible_or_formattable(model_name, self.field):
            _, value = get_display_value(
                self.instance, model_name, self.field, value)
            if value and is_convertible(model_name, self.field):
                units = get_unit_name(get_units(self.instance,
                                                model_name, self.field))
                value += (' %s' % units)

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
        name = self.field
        if name.startswith('udf:'):
            return name[4:]
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

        if hasattr(cls, 'display_name'):
            model_display_name = cls.display_name
        else:
            model_display_name = trans(self.model)

        return format_string % {'field': self.field_display_name,
                                'model': model_display_name.lower(),
                                'value': self.current_display_value}

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
        for c in all_subclasses(cls):
            class_dict[c.__name__] = c

    return class_dict[model_name]


_auditable_classes = {}
_authorizable_classes = {}

get_auditable_class = partial(_get_model_class, _auditable_classes, Auditable)
get_authorizable_class = partial(_get_model_class, _authorizable_classes,
                                 Authorizable)
