from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.gis.db import models
from django.forms.models import model_to_dict

import hashlib

class AuditException(Exception):
    pass

class Auditable(object):
    """
    Watches an object for changes and logs them
    """

    def __init__(self, *args, **kwargs):
        super(Auditable, self).__init__(*args, **kwargs)
        self.__initial = self._dict()

    def _dict(self):
        return model_to_dict(self, fields=[field.name for field in
                                           self._meta.fields])

    def _updated_fields(self):
        updated = {}
        d = self._dict()
        for key in d:
            old = self.__initial.get(key,None)
            new = d.get(key,None)

            if new != old:
                updated[key] = [old,new]

        return updated

    def _model_name(self):
        return self.__class__.__name__

    def save(self, *args, **kwargs):
        raise AuditException(
            'All changes to %s objects must be saved via "save_with_user"' %
            (self._model_name()))

    def delete(self, *args, **kwargs):
        raise AuditException(
            'All deletes to %s objects must be saved via "delete_with_user"' %
            (self._model_name()))

    def audits(self):
        return Audit.audits_for_object(self)

    def delete_with_user(self, user, *args, **kwargs):
        a = Audit(model=self._model_name(),
                  model_id=self.pk,
                  instance=self.instance,
                  user=user, action=Audit.Type.Delete)

        super(Auditable, self).delete(*args, **kwargs)

        a.save()
        self.__initial = {}

    def save_with_user(self, user, *args, **kwargs):

        if self.pk is None:
            action = Audit.Type.Insert

            # User created the object as "MyObj(field1=...,field2=...)"
            # the saved state will include these changes but the actual
            # "initial" state is empty so we clear it here
            self.__initial = {}
        else:
            action = Audit.Type.Update

        self.save_base(self, *args, **kwargs)

        audits = []
        for [field, values] in self._updated_fields().iteritems():
            audits.append(
                Audit(model=self._model_name(), model_id=self.pk,
                      instance=self.instance, field=field,
                      previous_value=values[0],
                      current_value=values[1],
                      user=user, action=action,
                      requires_auth=False,
                      ref_id=None))

        Audit.objects.bulk_create(audits)
        self.__initial = self._dict()

    @property
    def hash(self):
        """ Return a unique hash for this object """
        # Since this is an audited object each changes will
        # manifest itself in the audit log, essentially keeping
        # a revision id of this instance. Since each primary
        # key will be unique, we can just use that for the hash
        audits = self.instance.scope_model(Audit)\
                              .filter(model=self._model_name())\
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
            obj._model_name(), obj.instance, obj.pk)

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
