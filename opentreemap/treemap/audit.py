from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry

from django.forms.models import model_to_dict
from django.utils.translation import ugettext as _

from django.dispatch import receiver
from django.db.models.signals import pre_save
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, connection

import hashlib
import importlib


def model_hasattr(obj, name):
    # hasattr will not work here because it
    # just calls getattr and looks for exceptions
    # not differentiating between DoesNotExist
    # and AttributeError
    try:
        getattr(obj, name)
    except ObjectDoesNotExist:
        return True
    except AttributeError:
        return False


def get_id_sequence_name(model_class):
    """
    Takes a django model class and returns the name of the autonumber
    sequence for the id field.
    Tree => 'treemap_tree_id_seq'
    Plot => 'treemap_plot_id_seq'
    """
    table_name = model_class._meta.db_table
    pk_field = model_class._meta.pk
    # django fields only have a truthy db_column when it is
    # overriding the default
    pk_column_name = pk_field.db_column or pk_field.name
    id_seq_name = "%s_%s_seq" % (table_name, pk_column_name)
    return id_seq_name


def _reserve_model_id(model_class):
    """
    queries the database to get id from the audit id sequence.
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


def _audit_deserialization_value_transformer(audit):
    """
    A helper function to transform values.

    TODO: this needs to be worked into a toplevel thing.
    There is duplicate logic between this and the AuditUI.
    """
    if audit.field == 'geom':
        return GEOSGeometry(audit.current_value)
    elif audit.field == 'plot':
        from treemap.models import Plot
        return Plot(pk=audit.current_value)
    elif audit.field == 'readonly':
        return audit.current_value == 'True'
    else:
        return audit.current_value


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
        raise Exception('The pending status of an audit cannot be changed')

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

    TheModel = _lkp_model(audit.model)
    if approved:
        review_audit.action = Audit.Type.PendingApprove

        # use a try/catch to determine if the is a pending insert
        # or a pending update
        try:
            obj = TheModel.objects.get(pk=audit.model_id)
            obj.apply_change(audit.field,
                             _audit_deserialization_value_transformer(audit))
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
                         _audit_deserialization_value_transformer(
                             approved_audit))

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


def _lkp_model(modelname):
    """
    Convert a model name (as a string) into the model class

    If the model has no prefix, it is assumed to be in the
    'treemap.models' module.

    ex:
    'Tree' =(imports)=> treemap.models.Tree
    'treemap.audit.Audit' =(imports)=> treemap.audit.Audit
    """
    if "." in modelname:
        parts = modelname.split('.')
        modulename = '.'.join(parts[:-1])
        modelname = parts[-1]
    else:
        modulename = 'treemap.models'

    m = importlib.import_module(modulename)
    c = getattr(m, modelname)

    return c


def _verify_user_can_apply_audit(audit, user):
    """
    Make sure that user has "write direct" permissions
    for the given audit's fields
    """
    perms = user.get_instance_permissions(audit.instance,
                                          model_name=audit.model)

    foundperm = False
    for perm in perms:
        if perm.field_name == audit.field:
            if perm.permission_level == FieldPermission.WRITE_DIRECTLY:
                foundperm = True
                break
            else:
                raise AuthorizeException(
                    "User %s can't edit field %s on model %s" %
                    (user, audit.field, audit.model))

    if not foundperm:
        raise AuthorizeException(
            "User %s can't edit field %s on model %s (No permissions found)" %
            (user, audit.field, audit.model))


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
        self._do_not_track = set(['instance', 'udf_scalar_values'])
        super(UserTrackable, self).__init__(*args, **kwargs)

        if self.pk is None:
            # User created the object as "MyObj(field1=...,field2=...)"
            # the saved state will include these changes but the actual
            # "initial" state is empty so we clear it here
            self._previous_state = {}
        else:
            self._populate_previous_state()

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

    def _updated_fields(self):
        updated = {}
        d = self.as_dict()
        for key in d:
            if key not in self._do_not_track:
                old = self._previous_state.get(key, None)
                new = d.get(key, None)

                if new != old:
                    updated[key] = [old, new]

        return updated

    def fields_were_updated(self):
        return len(self._updated_fields()) > 0

    @property
    def _model_name(self):
        return self.__class__.__name__

    def delete_with_user(self, user, *args, **kwargs):
        super(UserTrackable, self).delete(*args, **kwargs)
        self._previous_state = {}

    def save_with_user(self, user, *args, **kwargs):
        self.save_base(self, *args, **kwargs)
        self._populate_previous_state()

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

    def _populate_previous_state(self):
        """
        A helper method for setting up a previous state dictionary
        without the elements that should remained untracked
        """
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


class Role(models.Model):
    name = models.CharField(max_length=255)
    instance = models.ForeignKey('Instance', null=True, blank=True)
    rep_thresh = models.IntegerField()

    def __unicode__(self):
        return '%s (%s)' % (self.name, self.pk)


class FieldPermission(models.Model):
    model_name = models.CharField(max_length=255)
    field_name = models.CharField(max_length=255)
    role = models.ForeignKey(Role)
    instance = models.ForeignKey('Instance')

    NONE = 0
    READ_ONLY = 1
    WRITE_WITH_AUDIT = 2
    WRITE_DIRECTLY = 3
    permission_level = models.IntegerField(
        choices=(
            # reserving zero in case we want
            # to create a "null-permission" later
            (NONE, "None"),
            (READ_ONLY, "Read Only"),
            (WRITE_WITH_AUDIT, "Write with Audit"),
            (WRITE_DIRECTLY, "Write Directly")),
        default=NONE)

    def __unicode__(self):
        return "%s.%s - %s" % (self.model_name, self.field_name, self.role)

    @property
    def allows_reads(self):
        return self.permission_level >= self.READ_ONLY

    @property
    def allows_writes(self):
        return self.permission_level >= self.WRITE_WITH_AUDIT


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

        self._has_been_clobbered = False

    def _write_perm_comparison_sets(self, user, direct_only=False):
        """
        Helper method for comparing a user's write
        permissions with the fields on the current model
        """
        perms = user.get_instance_permissions(self.instance, self._model_name)

        if direct_only:
            perm_set = {perm.field_name
                        for perm in perms
                        if perm.permission_level ==
                        FieldPermission.WRITE_DIRECTLY}
        else:
            perm_set = {perm.field_name for perm in perms
                        if perm.allows_writes}

        field_set = {field_name for field_name in self._previous_state.keys()}
        return perm_set, field_set

    def user_can_delete(self, user):
        """
        A user is able to delete an object if they have all
        field permissions on a model.
        """
        # TODO - this is cryptic.
        perm_set, field_set = self._write_perm_comparison_sets(user)
        return perm_set == field_set

    def _user_can_create(self, user, direct_only=False):
        """
        A user is able to create an object if they have permission on
        any of the fields in that model.

        If direct_only is False this method will return true
        if the user has either permission to create directly or
        create with audits
        """
        can_create = True

        perm_set, __ = self._write_perm_comparison_sets(user, direct_only)

        for field in self._fields_required_for_create():
            if field.name not in perm_set:
                can_create = False
                break

        return can_create

    def _assert_not_clobbered(self):
        """
        Raises an exception if the object has been clobbered.
        This assertion should be called by any method that
        shouldn't operate on clobbered models.
        """
        if self._has_been_clobbered:
            raise AuthorizeException(
                "Operation cannot be performed on a clobbered object.")

    def get_pending_fields(self, user):
        """
        Evaluates the permissions for the current user and collects
        fields that inheriting subclasses will want to treat as
        special pending_edit fields.
        """
        perms = user.get_instance_permissions(self.instance, self._model_name)
        fields_to_audit = []
        for perm in perms:
            if ((perm.permission_level == FieldPermission.WRITE_WITH_AUDIT and
                 perm.field_name in self._updated_fields())):

                fields_to_audit.append(perm.field_name)

        return fields_to_audit

    def clobber_unauthorized(self, user):
        perms = user.get_instance_permissions(self.instance, self._model_name)
        readable_fields = {perm.field_name for perm
                           in perms
                           if perm.allows_reads}

        fields = set(self._previous_state.keys())
        unreadable_fields = fields - readable_fields

        for field_name in unreadable_fields:
            self.apply_change(field_name, None)

        self._has_been_clobbered = True

    def _perms_for_user(self, user):
        if user is None or user.is_anonymous():
            perms = self.instance.default_role.fieldpermission_set
        else:
            perms = user.get_instance_permissions(
                self.instance, self._model_name)

        return perms.filter(model_name=self._model_name)

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
    def clobber_queryset(qs, user):
        for model in qs:
            model.clobber_unauthorized(user)
        return qs

    def save_with_user(self, user, *args, **kwargs):
        self._assert_not_clobbered()

        if self.pk is not None:
            writable_perms, __ = self._write_perm_comparison_sets(user)
            for field in self._updated_fields():
                if field not in writable_perms:
                    raise AuthorizeException("Can't edit field %s on %s" %
                                            (field, self._model_name))

        elif not self._user_can_create(user):
            raise AuthorizeException("%s does not have permission to "
                                     "create new %s objects." %
                                     (user, self._model_name))

        super(Authorizable, self).save_with_user(user, *args, **kwargs)

    def delete_with_user(self, user, *args, **kwargs):
        self._assert_not_clobbered()

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

    You probably want to inherit this mixin after
    Authorizable, and not before.

    Ex.
    class Foo(Authorizable, Auditable, models.Model):
        ...
    """
    def __init__(self, *args, **kwargs):
        super(Auditable, self).__init__(*args, **kwargs)
        self.is_pending_insert = False

    def full_clean(self, *args, **kwargs):
        if not isinstance(self, Authorizable):
            super(Auditable, self).full_clean(*args, **kwargs)
        else:
            raise TypeError("all calls to full clean must be done via "
                            "'full_clean_with_user'")

    def full_clean_with_user(self, user):
        if ((not isinstance(self, Authorizable) or
             self._user_can_create(user, direct_only=True))):
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

        super(Auditable, self).full_clean(exclude=exclude_fields)

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

    def get_active_pending_audits(self):
        return self.audits()\
                   .filter(requires_auth=True)\
                   .filter(ref__isnull=True)\
                   .order_by('-created')

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

            if is_fk:
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

    def save_with_user(self, user, *args, **kwargs):
        if self.is_pending_insert:
            raise Exception("You have already saved this object.")

        updates = self._updated_fields()

        is_insert = self.pk is None
        action = Audit.Type.Insert if is_insert else Audit.Type.Update

        pending_audits = []
        pending_fields = self.get_pending_fields(user)

        for pending_field in pending_fields:

            pending_audits.append((pending_field, updates[pending_field]))

            # Clear changes to object
            oldval = updates[pending_field][0]
            try:
                self.apply_change(pending_field, oldval)
            except ValueError:
                pass

            # If a field is a "pending field" then it should
            # be logically removed from the fields that are being
            # marked as "updated"
            del updates[pending_field]

        instance = self.instance if hasattr(self, 'instance') else None

        if ((not isinstance(self, Authorizable) or
             self._user_can_create(user, direct_only=True) or
             self.pk is not None)):
            super(Auditable, self).save_with_user(user, *args, **kwargs)
            model_id = self.pk
        else:
            model_id = _reserve_model_id(_lkp_model(self._model_name))
            self.pk = model_id
            self.is_pending_insert = True

        if is_insert:
            updates['id'] = [None, model_id]

        def make_audit_and_save(field, prev_val, cur_val, pending):

            Audit(model=self._model_name, model_id=model_id,
                  instance=instance, field=field,
                  previous_value=prev_val,
                  current_value=cur_val,
                  user=user, action=action,
                  requires_auth=pending,
                  ref=None).save()

        for [field, values] in updates.iteritems():
            make_audit_and_save(field, values[0], values[1], False)

        for (field, (prev_val, next_val)) in pending_audits:
            make_audit_and_save(field, prev_val, next_val, True)

    @property
    def hash(self):
        """ Return a unique hash for this object """
        # Since this is an audited object each changes will
        # manifest itself in the audit log, essentially keeping
        # a revision id of this instance. Since each primary
        # key will be unique, we can just use that for the hash
        audits = self.instance.scope_model(Audit)\
                              .filter(model=self._model_name)\
                              .filter(model_id=self.pk)\
                              .order_by('-updated')

        string_to_hash = str(audits[0].pk)

        return hashlib.md5(string_to_hash).hexdigest()


class AuditUI(object):
    """
    Audit UI provides useful accessors for getting the objects behind
    an audit.

    For example, the 'created_by' field of an audit is a user but is
    stored an integer. If this is an audit for a given 'created_by'
    field you can do something like:

    aui = AuditUI(audit)
    user_object = aui.previous_value_as_user

    If there is an invalid conversion it returns None:
    plot_object = aui.previous_value_as_plot
    """
    def __init__(self, audit):
        self.audit = audit

    def _value_as_thing(self, value, Thing):
        return Thing.objects.get(pk=value)

    def _value_as_user(self, value):
        # Delayed import since this is circular
        from treemap.models import User

        if self.audit.field == 'created_by':
            return self._value_as_thing(value, User)
        else:
            return None

    @property
    def current_value_as_user(self):
        return self._value_as_user(self.audit.current_value)

    @property
    def previous_value_as_user(self):
        return self._value_as_user(self.audit.previous_value)

    def _value_as_geom(self, value):
        if self.audit.field == 'geom':
            return GEOSGeometry(value)
        else:
            return None

    @property
    def current_value_as_geom(self):
        return self._value_as_geom(self.audit.current_value)

    @property
    def previous_value_as_geom(self):
        return self._value_as_geom(self.audit.previous_value)

    def _value_as_plot(self, value):
        # Delayed import since this is circular
        from treemap.models import Plot

        if self.audit.field == 'plot' and self.audit.model == 'Tree':
            return self._value_as_thing(value, Plot)
        else:
            return None

    @property
    def current_value_as_plot(self):
        return self._value_as_plot(self.audit.current_value)

    @property
    def previous_value_as_plot(self):
        return self._value_as_plot(self.audit.previous_value)

    def _value_as_species(self, value):
        # Delayed import since this is circular
        from treemap.models import Species

        if self.audit.field == 'species' and self.audit.model == 'Tree':
            return self._value_as_thing(value, Species)
        else:
            return None

    @property
    def current_value_as_species(self):
        return self._value_as_species(self.audit.current_value)

    @property
    def previous_value_as_species(self):
        return self._value_as_species(self.audit.previous_value)

    @property
    def previous_value(self):
        return self.audit.previous_value

    @property
    def current_value(self):
        return self.audit.current_value


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
    previous_value = models.CharField(max_length=255, null=True)
    current_value = models.CharField(max_length=255, null=True)

    user = models.ForeignKey('treemap.User')
    action = models.IntegerField()

    """
    These two fields are part of the pending edit system

    If requires_auth is True then this audit record represents
    a change that was *requested* but not applied.

    When an authorized user approves a pending edit
    it creates an audit record on this model with an action
    type of either "PendingApprove" or "PendingReject"
    """
    requires_auth = models.BooleanField(default=False)
    ref = models.ForeignKey('Audit', null=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Type:
        Insert = 1
        Delete = 2
        Update = 3
        PendingApprove = 4
        PendingReject = 5

    TYPES = {
        Type.Insert: 'Create',
        Type.Delete: 'Delete',
        Type.Update: 'Update',
        Type.PendingApprove: 'Approved Pending Edit',
        Type.PendingReject: 'Reject Pending Edit',
    }

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
        lang = {
            Audit.Type.Insert: _('%(username)s created a %(model)s'),
            Audit.Type.Update: _('%(username)s updated the %(model)s'),
            Audit.Type.Delete: _('%(username)s deleted the %(model)s'),
            Audit.Type.PendingApprove: _('%(username)s approved an '
                                         'edit on the %(model)s'),
            Audit.Type.PendingReject: _('%(username)s rejected an '
                                        'edit on the %(model)s')
        }

        return lang[self.action] % {'username': self.user,
                                    'model': _(self.model).lower()}

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
    def apply_adjustment(audit):
        try:
            rm = ReputationMetric.objects.get(instance=audit.instance,
                                              model_name=audit.model,
                                              action=audit.action)
        except ObjectDoesNotExist:
            return

        iuser = audit.user.get_instance_user(audit.instance)

        if audit.requires_auth and audit.ref:
            review_audit = audit.ref
            if review_audit.action == Audit.Type.PendingApprove:
                iuser.reputation += rm.approval_score
                iuser.save_base()
            elif review_audit.action == Audit.Type.PendingReject:
                new_score = iuser.reputation - rm.denial_score
                if new_score >= 0:
                    iuser.reputation = new_score
                else:
                    iuser.reputation = 0
                iuser.save_base()
            else:
                error_message = ("Referenced Audits must carry approval "
                                 "actions. They must have an action of "
                                 "PendingApprove or Pending Reject. "
                                 "Something might be very wrong with your "
                                 "database configuration.")
                raise IntegrityError(error_message)
        elif not audit.requires_auth:
            iuser.reputation += rm.direct_write_score
            iuser.save_base()


@receiver(pre_save, sender=Audit)
def audit_presave_actions(sender, instance, **kwargs):
    ReputationMetric.apply_adjustment(instance)
