from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.gis.db import models
from django.forms.models import model_to_dict

from django.dispatch import receiver
from django.db.models.signals import pre_save
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError

import hashlib

def approve_or_reject_audit_and_apply(audit, user, approved):
    """
    Approve or reject a given audit and apply it to the
    underlying model if "approved" is True

    audit    - Audit record to apply
    user     - The user who is approving or rejecting
    approved - True to generate an approval, False to
               generate a rejection
    """
    # If the ref_id has already been set, this audit has
    # already been accepted or rejected so we can't do anything
    if audit.ref_id:
        raise Exception('The pending status of an audit cannot be changed')

    # Regardless of what we're doing, we need to make sure
    # 'user' is authorized to approve this edit
    _verify_user_can_apply_audit(audit, user)

    pdgaudit = Audit(model=audit.model, model_id=audit.model_id,
                     instance=audit.instance, field=audit.field,
                     previous_value=audit.previous_value,
                     current_value=audit.current_value,
                     user=user)

    if approved:
        pdgaudit.action = Audit.Type.PendingApprove

        TheModel = _lkp_model(audit.model)
        obj = TheModel.objects.get(pk=audit.model_id)
        setattr(obj, audit.field, audit.current_value)

        # Not sure this is really great here, but we want to
        # bypass all of the safety measures and simply apply
        # the edit without generating any additional audits
        # or triggering the auth system
        obj.save_base()
        pdgaudit.save()

        audit.ref_id = pdgaudit
        audit.save()

    else: # Reject
        pdgaudit.action = Audit.Type.PendingReject
        pdgaudit.save()

        audit.ref_id = pdgaudit
        audit.save()

    return pdgaudit

def _lkp_model(modelname):
    """
    Convert a model name (as a string) into the model class
    If the model has no prefix, it is assumed to be in the
    'treemap.models' module
    """
    import importlib

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

class UserTrackable(object):
    def __init__(self, *args, **kwargs):
        super(UserTrackable, self).__init__(*args, **kwargs)

        if self.pk is None:
            # User created the object as "MyObj(field1=...,field2=...)"
            # the saved state will include these changes but the actual
            # "initial" state is empty so we clear it here
            self._previous_state = {}
        else:
            self._previous_state = self._dict()

    def _dict(self):
        return model_to_dict(self, fields=[field.name for field in
                                           self._meta.fields])

    def _updated_fields(self):
        updated = {}
        d = self._dict()
        for key in d:
            old = self._previous_state.get(key,None)
            new = d.get(key,None)

            if new != old:
                updated[key] = [old,new]

        return updated

    @property
    def _model_name(self):
        return self.__class__.__name__

    def delete_with_user(self, user, *args, **kwargs):
        super(UserTrackable, self).delete(*args, **kwargs)
        self._previous_state = {}

    def save_with_user(self, user, *args, **kwargs):
        self.save_base(self, *args, **kwargs)
        self._previous_state = self._dict()

    def save(self, *args, **kwargs):
        raise UserTrackingException(
            'All changes to %s objects must be saved via "save_with_user"' %
            (self._model_name))

    def delete(self, *args, **kwargs):
        raise UserTrackingException(
            'All deletes to %s objects must be saved via "delete_with_user"' %
            (self._model_name))

class Role(models.Model):
    name = models.CharField(max_length=255)
    instance = models.ForeignKey('Instance', null=True, blank=True)
    rep_thresh = models.IntegerField()

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
            (NONE, "None"), # reserving zero in case we want to create a "null-permission" later
            (READ_ONLY, "Read Only"),
            (WRITE_WITH_AUDIT, "Write with Audit"),
            (WRITE_DIRECTLY, "Write Directly")),
        default=NONE)

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

        self._exempt_field_names = { 'instance','created_by','id' }
        self._has_been_clobbered = False

    def _write_perm_comparison_sets(self, user):
        """
        Helper method for comparing a user's write
        permissions with the fields on the current model
        """
        perms = user.get_instance_permissions(self.instance, self._model_name)
        perm_set = { perm.field_name for perm in perms if perm.allows_writes }
        field_set = { field_name for field_name in self._previous_state.keys() }
        return perm_set, field_set

    def _user_can_delete(self, user):
        """
        A user is able to delete an object if they have all
        field permissions on a model.
        """
        perm_set, field_set = self._write_perm_comparison_sets(user)
        field_set = field_set - self._exempt_field_names
        return perm_set == field_set

    def _user_can_create(self, user):
        """
        A user is able to create an object if they have permission on
        any of the fields in that model.
        """
        can_create = True

        perm_set, _ = self._write_perm_comparison_sets(user)

        for field in self._meta.fields:
            if (not field.null and
                not field.blank and
                not field.primary_key and
                field.name not in self._exempt_field_names):
                if field.name not in perm_set:
                    can_create =  False
                    break

        return can_create

    def _assert_not_clobbered(self):
        """
        Raises an exception if the object has been clobbered.
        This assertion should be called by any method that
        shouldn't operate on clobbered models.
        """
        if self._has_been_clobbered:
            raise AuthorizeException("Operation cannot be performed on a clobbered object.")

    def get_pending_fields(self, user):
        """
        Get a list of fields that are currently being update which would
        require a pending edit

        Note: Since Authorizable doesn't control what happens to "pending" or
        "write with audit" fields it is the subclasses responsibility to handle
        the difference. A naive implementation (i.e. just subclassing Authorizable)
        treats "write with audit" that same as "write directly"
        """
        perms = user.get_instance_permissions(self.instance, self._model_name)
        fields_to_audit = []
        for perm in user.get_instance_permissions(self.instance, self._model_name):
            if (perm.permission_level == FieldPermission.WRITE_WITH_AUDIT and
                perm.field_name in self._updated_fields()):
                fields_to_audit.append(perm.field_name)

        return fields_to_audit

    def clobber_unauthorized(self, user):
        perms = user.get_instance_permissions(self.instance, self._model_name)
        readable_fields = { perm.field_name for perm in perms if perm.allows_reads }
        fields = set(self._previous_state.keys())
        unreadable_fields = fields - readable_fields

        for field_name in unreadable_fields:
            if field_name not in self._exempt_field_names:
                setattr(self, field_name, None)

        self._has_been_clobbered = True

    @staticmethod
    def clobber_queryset(qs, user):
        for model in qs:
            model.clobber_unauthorized(user)
        return qs

    def save_with_user(self, user, *args, **kwargs):
        self._assert_not_clobbered()

        if self.pk is not None:
            writable_perms, _ = self._write_perm_comparison_sets(user)
            for field in self._updated_fields():
                if field not in writable_perms:
                    raise AuthorizeException("Can't edit field %s on %s" %
                                            ( field, self._model_name))

        elif not self._user_can_create(user):
            raise AuthorizeException("%s does not have permission to create new %s objects." %
                                     (user, self._model_name))

        super(Authorizable, self).save_with_user(user, *args, **kwargs)


    def delete_with_user(self, user, *args, **kwargs):
        self._assert_not_clobbered()

        if self._user_can_delete(user):
            super(Authorizable, self).delete_with_user(user, *args, **kwargs)
        else:
            raise AuthorizeException("%s does not have permission to delete %s objects." %
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

    def audits(self):
        return Audit.audits_for_object(self)

    def delete_with_user(self, user, *args, **kwargs):
        a = Audit(model=self._model_name,
                  model_id=self.pk,
                  instance=self.instance,
                  user=user, action=Audit.Type.Delete)

        super(Auditable, self).delete_with_user(user, *args, **kwargs)
        a.save()

    def save_with_user(self, user, *args, **kwargs):

        updates = self._updated_fields()

        is_insert = self.pk is None
        if is_insert:
            action = Audit.Type.Insert
        else:
            action = Audit.Type.Update

        # This field is populated if a given object is both
        # auditable and authorizable. It is sort of a leaky
        # abstraction - given that it is tightly coupling
        # Auditable and Authorizable
        pending_audits = []
        if hasattr(self, 'get_pending_fields'):
            pending = self.get_pending_fields(user)
            for pending_field in pending:
                pending_audits.append((pending_field, updates[pending_field]))

                # Clear changes to object
                oldval = updates[pending_field][0]
                setattr(self, pending_field, oldval)


                # If a field is a "pending field" then it should
                # be logically removed from the fields that are being
                # marked as "updated"
                del updates[pending_field]

        super(Auditable, self).save_with_user(user, *args, **kwargs)

        if is_insert:
            updates['id'] = [None, self.pk]

        def make_audit_and_save(field, prev_val, cur_val, pending):
            instance = None
            if hasattr(self, 'instance'):
                instance = self.instance

            Audit(model=self._model_name, model_id=self.pk,
                  instance=instance, field=field,
                  previous_value=prev_val,
                  current_value=cur_val,
                  user=user, action=action,
                  requires_auth=pending,
                  ref_id=None).save()

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


###
# TODO:
# Test fail in saving on base object
# Test null values
###
class Audit(models.Model):
    model = models.CharField(max_length=255,null=True)
    model_id = models.IntegerField(null=True)
    instance = models.ForeignKey('Instance', null=True, blank=True)
    field = models.CharField(max_length=255,null=True)
    previous_value = models.CharField(max_length=255,null=True)
    current_value = models.CharField(max_length=255,null=True)

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
    ref_id = models.ForeignKey('Audit', null=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Type:
        Insert = 1
        Delete = 2
        Update = 3
        PendingApprove = 4
        PendingReject = 5

    @classmethod
    def audits_for_model(clz, model_name, inst, pk):
        return Audit.objects.filter(model=model_name,
                                    model_id=pk,
                                    instance=inst).order_by('created')

    @classmethod
    def audits_for_object(clz, obj):
        return clz.audits_for_model(
            obj._model_name, obj.instance, obj.pk)

    def dict(self):
        return { 'model': self.model,
                 'model_id': self.model_id,
                 'instance_id': self.instance.pk,
                 'field': self.field,
                 'previous_value': self.previous_value,
                 'current_value': self.current_value,
                 'user_id': self.user.pk,
                 'action': self.action,
                 'requires_auth': self.requires_auth,
                 'ref_id': self.ref_id.pk if self.ref_id else None,
                 'created': str(self.created) }


    def __unicode__(self):
        return u"ID: %s %s.%s (%s) %s => %s" % \
            (self.action, self.model, self.field, self.model_id,
             self.previous_value, self.current_value)

    def is_pending(self):
        return self.requires_auth and not self.ref_id

    def was_reviewed(self):
        return self.requires_auth and self.ref_id

class ReputationMetric(models.Model):
    """
    Assign integer scores for each model that determine
    how many reputation points are awarded/deducted for an
    approved/denied audit.
    """
    # instance is nullable because some auditables don't have instances
    instance = models.ForeignKey('Instance', null=True, blank=True)
    model_name = models.CharField(max_length=255)
    action = models.CharField(max_length=255)
    direct_write_score = models.IntegerField(null=True, blank=True)
    approval_score = models.IntegerField(null=True, blank=True)
    denial_score = models.IntegerField(null=True, blank=True)

    @staticmethod
    def apply_adjustment(audit):
        try:
            rm = ReputationMetric.objects.get(instance=audit.instance,
                                              model_name=audit.model,
                                              action=audit.action)
        except ObjectDoesNotExist:
            return


        if audit.was_reviewed():
            review_audit = Audit.objects.get(id=audit.ref_id)
            if review_audit.action == Audit.Type.PendingApprove:
                audit.user.reputation += rm.approval_score
                audit.user.save_base()
            elif review_audit.action == Audit.Type.PendingReject:
                new_score = audit.user.reputation - rm.denial_score
                if new_score >= 0:
                    audit.user.reputation = new_score
                else:
                    audit.user.reputation = 0
                audit.user.save_base()
            else:
                error_message = "Referenced Audits must carry approval actions. "\
                    "They must have an action of PendingApprove or Pending Reject. "\
                    "Something might be very wrong with your database configuration."
                raise IntegrityError(error_message)
        elif not audit.requires_auth:
            audit.user.reputation += rm.direct_write_score
            audit.user.save_base()


@receiver(pre_save, sender=Audit)
def audit_presave_actions(sender, instance, **kwargs):
    ReputationMetric.apply_adjustment(instance)
