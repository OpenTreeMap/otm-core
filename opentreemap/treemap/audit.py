from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.gis.db import models
from django.forms.models import model_to_dict

import hashlib

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
        super(Auditable, self).save_with_user(user, *args, **kwargs)

        if is_insert:
            action = Audit.Type.Insert
            updates['id'] = [None, self.pk]
        else:
            action = Audit.Type.Update
        
        audits = []
        for [field, values] in updates.iteritems():
            audits.append(
                Audit(model=self._model_name, model_id=self.pk,
                      instance=self.instance, field=field,
                      previous_value=values[0],
                      current_value=values[1],
                      user=user, action=action,
                      requires_auth=False,
                      ref_id=None))

        Audit.objects.bulk_create(audits)

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
    instance = models.ForeignKey('Instance')
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

    created = models.DateField(auto_now_add=True)
    updated = models.DateField(auto_now=True)

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
                 'instance_id': self.instance,
                 'field': self.field,
                 'previous_value': self.previous_value,
                 'current_value': self.current_value,
                 'user_id': self.user,
                 'action': self.action,
                 'requires_auth': self.requires_auth,
                 'ref_id': self.ref_id,
                 'created': self.created }


    def __unicode__(self):
        return u"ID: %s %s.%s (%s) %s => %s" % \
            (self.action, self.model, self.field, self.model_id,
             self.previous_value, self.current_value)
