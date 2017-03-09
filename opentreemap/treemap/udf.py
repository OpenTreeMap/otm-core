# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
import copy
import re
from datetime import date, datetime

from django.core.exceptions import ValidationError, FieldError
from django.utils.translation import ugettext_lazy as _
from django.contrib.gis.db import models
from django.db import transaction
from django.db.models import Q
from django.db.models.fields.subclassing import Creator
from django.db.models.base import ModelBase
from django.db.models.lookups import Lookup
from django.db.models.sql.constants import ORDER_PATTERN
from django.db.models.signals import post_save, post_delete

from django.db.models.sql.query import Query

from django_hstore.fields import DictionaryField, HStoreDict
from django_hstore.managers import HStoreManager, HStoreGeoManager
from django_hstore.query import HStoreGeoQuerySet

from treemap.instance import Instance
from treemap.audit import (UserTrackable, Audit, UserTrackingException,
                           _reserve_model_id, FieldPermission,
                           AuthorizeException, Authorizable, Auditable)
from treemap.lib.object_caches import (field_permissions,
                                       invalidate_adjuncts, udf_defs)
from treemap.lib.dates import (parse_date_string_with_or_without_time,
                               DATETIME_FORMAT)
# Import utilities for ways in which a UserDefinedFieldDefinition
# is identified
# They have to be defined in `util` to avoid cyclical
# import dependencies.
# Please also see name related properties on that class.
# Note that audits refer to collection udfds as 'udf:{udfd.pk}',
# but to scalar udfds as 'udf:{udfd.name}', same as FieldPermissions
from treemap.util import (safe_get_model_class, to_object_name,
                          get_pk_from_collection_audit_name,
                          get_name_from_canonical_name,
                          make_udf_name_from_key)

from treemap.decorators import classproperty


# Allow anything except certain known problem characters.
# NOTE: Make sure to keep the validation error associated with this up-to-date
# * '%' in general makes the Django ORM error out.
# * '__' is also problematic for the Django ORM
# * '.' is fine for the ORM, but made the template system unhappy.
# * '"' makes the ORM error out when building 'AS' clauses and wrapping
#   them with quotes.
_UDF_NAME_REGEX = re.compile(r'^[^_"%.]+$')


def safe_get_udf_model_class(model_string):
    """
    In a couple of cases we want to be able to convert a string
    into a valid django model class. For instance, if we have
    'Plot' we want to get the actual class for 'treemap.models.Plot'
    in a safe way.

    This function returns the class represented by the given model
    if it exists in 'treemap.models' and the class's objects are a
    subtype of UDFModel
    """
    model_class = safe_get_model_class(model_string)

    # It must have be a UDF subclass
    if not isinstance(model_class(), UDFModel):
        raise ValidationError(_('invalid model type - must subclass UDFModel'))

    return model_class


class UserDefinedCollectionValue(UserTrackable, models.Model):
    """
    UserDefinedCollectionValue does not inherit either the authorizable
    or auditable traits, however it does participate in those systems.

    In particular, the authorization for a collection UDF is based on
    the udf name and model. So if there is a collection udf called
    'Stewardship' on 'Plot' then the only field permission that matters
    is 'Plot'/'udf:Stewardship'

    Each UserDefinedCollectionValue represents a new entry in a
    particular collection field. We audit all of the fields on this
    object and expand the audits in the same way that scalar udfs work.
    """
    field_definition = models.ForeignKey('UserDefinedFieldDefinition')
    model_id = models.IntegerField()
    data = DictionaryField()

    objects = HStoreManager()

    def __unicode__(self):
        return repr(self.data)

    def __init__(self, *args, **kwargs):
        super(UserDefinedCollectionValue, self).__init__(*args, **kwargs)
        self._do_not_track |= self.do_not_track
        self.populate_previous_state()

    @classproperty
    def do_not_track(cls):
        return UserTrackable.do_not_track | {'data'}

    @property
    def tracked_fields(self):
        return super(UserDefinedCollectionValue, self).tracked_fields + \
            ['udf:' + name for name in self.udf_field_names]

    def validate_foreign_keys_exist(self):
        """
        This is used to check if a given foreign key exists as part of
        the audit system. However, this is no foreign key coupling to
        other auditable/pending models, so we can skip this validation
        step
        """
        pass

    @staticmethod
    def get_display_model_name(audit_name, instance=None):
        if audit_name.startswith('udf:'):
            try:
                # UDF Collections store their model names in the audit table as
                # udf:<pk of UserDefinedFieldDefinition>
                pk = get_pk_from_collection_audit_name(audit_name)
                if not instance:
                    # TODO: should use caching (udf_defs)
                    udf_def = UserDefinedFieldDefinition.objects.get(pk=pk)
                    return udf_def.name
                else:
                    for udf_def in udf_defs(instance):
                        if udf_def.pk == pk:
                            return udf_def.name
            except (ValueError, UserDefinedFieldDefinition.DoesNotExist):
                pass  # If something goes wrong, just use the defaults
        return audit_name

    @classmethod
    def action_format_string_for_audit(cls, audit):
        if audit.field == 'id' or audit.field is None:
            lang = {
                Audit.Type.Insert: _('created a %(model)s entry'),
                Audit.Type.Update: _('updated the %(model)s entry'),
                Audit.Type.Delete: _('deleted the %(model)s entry'),
                Audit.Type.PendingApprove: _('approved an edit '
                                             'to the %(model)s entry'),
                Audit.Type.PendingReject: _('rejected an '
                                            'edit to the %(model)s entry')
            }
            return lang[audit.action]
        return Auditable.action_format_string_for_audit(audit)

    @classmethod
    def short_descr(cls, audit):
        # model_id and field_definition aren't very useful changes to see
        if audit.field in {'model_id', 'field_definition'}:
            return None

        format_string = cls.action_format_string_for_audit(audit)

        model_name = audit.model
        field = audit.field
        if audit.field == 'id':
            model_name = cls.get_display_model_name(audit.model)

        if field.startswith('udf:'):
            field = get_name_from_canonical_name(field)

        return format_string % {'field': field,
                                'model': model_name,
                                'value': audit.current_display_value}

    def get_cleaned_data(self):
        # Grab each datatype and assign the sub-name to the
        # definition. These are used to clean the data
        cleaned_data = {}
        for subfield_name in self.data:
            sub_value = self.data.get(subfield_name, None)

            datatype = self.field_definition.datatype_by_field[subfield_name]
            try:
                sub_value = self.field_definition.clean_value(sub_value,
                                                              datatype)
            except ValidationError:
                # If there was an error coming from the database
                # just continue with whatever the value was.
                pass

            cleaned_data[subfield_name] = sub_value

        cleaned_data['id'] = self.pk

        return cleaned_data

    def as_dict(self, *args, **kwargs):
        base_model_dict = super(
            UserDefinedCollectionValue, self).as_dict(*args, **kwargs)

        for field, value in self.data.iteritems():
            base_model_dict['udf:' + field] = value

        return base_model_dict

    def apply_change(self, key, val):
        if key.startswith('udf:'):
            key = get_name_from_canonical_name(key)
            self.data[key] = val
        else:
            try:
                super(UserDefinedCollectionValue, self)\
                    .apply_change(key, val)
            except ValueError:
                pass

    def save(self, *args, **kwargs):
        raise UserTrackingException(
            'All changes to %s objects must be saved via "save_with_user"' %
            (self._model_name))

    def save_with_user(self, user, *args, **kwargs):
        updated_fields = self._updated_fields()

        if self.pk is None:
            audit_type = Audit.Type.Insert
        else:
            audit_type = Audit.Type.Update

        field_perm = None
        model = self.field_definition.model_type
        field = self.field_definition.canonical_name
        perms = field_permissions(user, self.field_definition.instance,
                                  model_name=model)
        for perm in perms:
            if perm.field_name == field and perm.allows_writes:
                field_perm = perm
                break

        if field_perm is None:
            raise AuthorizeException("Cannot save UDF field '%s.%s': "
                                     "No sufficient permission found."
                                     % (model, self.field_definition.name))

        if field_perm.permission_level == FieldPermission.WRITE_WITH_AUDIT:
            model_id = _reserve_model_id(UserDefinedCollectionValue)
            pending = True
            for field, (oldval, __) in updated_fields.iteritems():
                self.apply_change(field, oldval)
        else:
            pending = False
            super(UserDefinedCollectionValue, self).save_with_user(
                user, *args, **kwargs)
            model_id = self.pk

        if audit_type == Audit.Type.Insert:
            updated_fields['id'] = [None, model_id]

        for field, (old_val, new_val) in updated_fields.iteritems():
            Audit.objects.create(
                current_value=new_val,
                previous_value=old_val,
                model=self.field_definition.collection_audit_name,
                model_id=model_id,
                field=field,
                instance=self.field_definition.instance,
                user=user,
                action=audit_type,
                requires_auth=pending)


class UserDefinedFieldDefinition(models.Model):
    """
    These models represent user defined fields that are attached to
    specific model types. For instance, if a user wanted to record
    a planting date for a tree she should create a UDFD to support
    that.
    """

    """
    The instance that this field is bound to
    """
    instance = models.ForeignKey(Instance)

    """
    The type of model that this should bind to
    """
    model_type = models.CharField(max_length=255)

    """
    Datatype is a json string. It must be an array of dictionary
    objects if 'iscollection' is true, or a single dictionary otherwise.
    Each dictionary object has the following required keys:

    'type' - Field type (float, int, string, user, choice, date)

    All types allow a 'description' and key:

    'description' - A text description of the field

    If the type is a collection, you must provide a 'name' key
    to each element:

    'name' - Name of this particular field

    In addition, if the 'type' is 'choice' a 'choices' key is
    required:

    'choices' - An array of choice options

    Specify choices that may not be modified with the 'protected_choices'
    key (optional):

    'protected_choices' - An array of choice options
    """
    datatype = models.TextField()

    """
    If this is set to True the UDFD represents a 'Collection' of data,
    if set to False the UDFD represents a scalar value

    Depending on this flag, the values for the UDFD will either live
    on the model or in a collections value table
    """
    iscollection = models.BooleanField()

    """
    Protected UDFs cannot be deleted.
    """
    # TODO: Change to BooleanField after production deployment
    is_protected = models.NullBooleanField(default=False)

    """
    Name of the UDFD
    """
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = ('instance', 'model_type', 'name')

    @property
    def all_choices(self):
        if self.iscollection:
            raise ValueError(_('Property "all_choices" is invalid '
                               'for collection UDFs'))
        return UserDefinedFieldDefinition._all_choices(self.datatype_dict)

    @classmethod
    def _all_choices(cls, datatype):
        if datatype['type'] in ('choice', 'multichoice'):
            # There are situations where "choices" and "protected_choices"
            # may exist, but the values are None. Default to an empty list
            # so we can concatenate them.
            choices = datatype['choices'] or []
            protected_choices = datatype.get('protected_choices', None) or []
            return protected_choices + choices
        return None

    def __unicode__(self):
        return ('%s.%s%s' %
                (self.model_type, self.name,
                 ' (collection)' if self.iscollection else ''))

    def delete_choice(self, choice_value, name=None):
        update_to = None

        # Collection udfs use the empty string
        if name is not None:
            update_to = ""

        self.update_choice(choice_value, update_to, name=name)

    def _validate_and_update_choice(
            self, datatype, old_choice_value, new_choice_value):

        # Prevent validation errors when the choice value is numeric.
        old_choice_value = unicode(old_choice_value)

        if datatype['type'] not in ('choice', 'multichoice'):
            raise ValidationError(
                {'datatype': [_("Can't change choices "
                                "on a non-choice field")]})

        choices = datatype['choices']
        protected_choices = datatype.get('protected_choices', None) or []
        all_choices = UserDefinedFieldDefinition._all_choices(datatype)

        if old_choice_value not in all_choices:
            raise ValidationError(
                {'datatype': [_("Choice '%(choice)s' not found") % {
                    'choice': old_choice_value}]})

        if old_choice_value in protected_choices:
            raise ValidationError({
                'datatype': [
                    _("Can't modify protected choice '%(choice)s'") % {
                        'choice': old_choice_value}]})

        choices = self._list_replace_or_remove(choices,
                                               old_choice_value,
                                               new_choice_value)

        datatype['choices'] = choices
        return datatype

    @property
    def model_config(self):
        Model = safe_get_udf_model_class(self.model_type)
        return getattr(Model, 'udf_settings', {}).get(self.name, {})

    def _update_choice_scalar(self, old_choice_value, new_choice_value):
        Model = safe_get_udf_model_class(self.model_type)

        if self.datatype_dict['type'] == 'choice':
            for model in Model.objects\
                              .filter(**{'instance': self.instance,
                                         self.canonical_name:
                                         old_choice_value}):
                model.udfs[self.name] = new_choice_value
                model.save_base()

        else:  # multichoice
            udf_filter = {'instance': self.instance,
                          # grab anything with that key
                          'udfs__contains': [self.name]}
            models = Model.objects.filter(**udf_filter)

            for model in models:
                newval = self._list_replace_or_remove(
                    model.udfs[self.name],
                    old_choice_value,
                    new_choice_value)
                model.udfs[self.name] = newval
                model.save_base()

        datatype = self._validate_and_update_choice(
            self.datatype_dict, old_choice_value, new_choice_value)

        self.datatype = json.dumps(datatype)
        self.save()

        audits = Audit.objects.filter(
            model=self.model_type,
            field=self.canonical_name,
            instance=self.instance)

        self._update_choices_on_audits(
            audits, old_choice_value, new_choice_value)

    def _update_choices_on_audits(
            self, audits, old_choice_value, new_choice_value):

        if self.iscollection or self.datatype_dict['type'] == 'choice':
            cval_audits = audits.filter(current_value=old_choice_value)
            pval_audits = audits.filter(previous_value=old_choice_value)
            if new_choice_value is None:
                cval_audits.delete()
                pval_audits.delete()
            else:
                cval_audits.update(current_value=new_choice_value)
                pval_audits.update(previous_value=new_choice_value)
        else:
            for audit in audits.filter(field=self.canonical_name,
                                       model=self.model_type):
                audit.current_value = json.dumps(
                    self._list_replace_or_remove(
                        json.loads(audit.current_value or '[]'),
                        old_choice_value,
                        new_choice_value))
                audit.previous_value = json.dumps(
                    self._list_replace_or_remove(
                        json.loads(audit.previous_value or '[]'),
                        old_choice_value,
                        new_choice_value))
                audit.save()

    def _list_replace_or_remove(self, l, old, new):
        if l is None:
            return None
        new_l = filter(
            None,
            [(new if choice == old else choice)
             for choice in l])
        return new_l or None

    def add_choice(self, new_choice_value, name=None, is_protected=False):
        choices_key = 'protected_choices' if is_protected else 'choices'

        def _list_append(datatype, key, value):
            lst = datatype.get(key, None) or []
            lst.append(value)
            datatype[key] = lst

        if self.iscollection:
            if name is None:
                raise ValidationError({
                    'name': [_('Name is required for collection fields')]})

            datatypes = {d['name']: d for d in self.datatype_dict}
            datatype = datatypes[name]
            _list_append(datatype, choices_key, new_choice_value)

            self.datatype = json.dumps(datatypes.values())
            self.save()
        else:
            if name is not None:
                raise ValidationError({
                    'name': [_(
                        'Name is allowed only for collection fields')]})

            datatype = self.datatype_dict
            _list_append(datatype, choices_key, new_choice_value)

            self.datatype = json.dumps(datatype)
            self.save()

    @transaction.atomic
    def replace_collection_field_choices(self, field_name, new_choices):
        datatypes = {d['name']: d for d in self.datatype_dict}
        field = datatypes[field_name]
        for choice in field['choices']:
            if choice not in new_choices:
                self.delete_choice(choice, field_name)
        field['choices'] = new_choices
        self.datatype = json.dumps(datatypes.values())
        self.save()

    @transaction.atomic
    def update_choice(
            self, old_choice_value, new_choice_value, name=None):
        datatype = self.datatype_dict

        if self.iscollection:
            if name is None:
                raise ValidationError({
                    'name': [_('Name is required for collection fields')]})

            datatypes = {info['name']: info for info in datatype}
            datatype = self._validate_and_update_choice(
                datatypes[name], old_choice_value, new_choice_value)

            datatypes[name] = datatype
            self.datatype = json.dumps(datatypes.values())
            self.save()

            vals = UserDefinedCollectionValue\
                .objects\
                .filter(field_definition=self)\
                .extra(where=["data ? %s AND data->%s = %s"],
                       params=[name, name, old_choice_value])

            if new_choice_value is None:
                vals.hremove('data', name)
            else:
                vals.hupdate('data', {name: new_choice_value})

            audits = Audit.objects.filter(
                model=self.collection_audit_name,
                field=make_udf_name_from_key(name))

            # If the string is empty we want to delete the audits
            # _update_choices_on_audits only does nf new_choice_value
            # is none
            if new_choice_value == '':
                new_choice_value = None

            self._update_choices_on_audits(
                audits, old_choice_value, new_choice_value)
        else:
            if name is not None:
                raise ValidationError({
                    'name': [_(
                        'Name is allowed only for collection fields')]})

            self._update_choice_scalar(old_choice_value, new_choice_value)

    def validate(self):
        model_type = self.model_type

        if model_type not in {cls.__name__ for cls
                              in self.instance.editable_udf_models()['all']}:
            raise ValidationError(
                {'udf.model': [_("Invalid model '%(model_type)s'") %
                               {'model_type': model_type}]})

        model_class = safe_get_udf_model_class(model_type)

        field_names = [field.name for field in model_class._meta.fields]

        if self.name in field_names:
            raise ValidationError(
                {'name': [_('Cannot use fields that already '
                            'exist on the model')]})
        if not self.name:
            raise ValidationError(
                {'name': [_('Name cannot be blank')]})

        if not _UDF_NAME_REGEX.match(self.name):
            raise ValidationError(
                {'name': [_('A field name may not contain percent (%), '
                            'period (.), underscore (_), or quote (") '
                            'characters.')]})

        existing_objects = UserDefinedFieldDefinition\
            .objects\
            .filter(
                model_type=model_type,
                instance=self.instance,
                name=self.name)\
            .exclude(
                pk=self.pk)

        if existing_objects.exists():
            template = _("There is already a custom %(model_type)s field with"
                         " name '%(name)s'")
            raise ValidationError(template % {
                'model_type': model_class.display_name(self.instance),
                'name': self.name})

        datatype = self.datatype_dict

        if self.iscollection:
            errors = {}
            datatypes = self.datatype_dict
            if isinstance(datatypes, list):
                for datatype in datatypes:
                    try:
                        self._validate_single_datatype(datatype)
                    except ValidationError as e:
                        errors['datatype'] = e.messages

                    if not datatype.get('name', None):
                        errors['name'] = [_('Name must not be empty')]

                names = {datatype.get('name') for datatype in datatypes}

                if len(names) != len(datatypes):
                    if 'name' not in errors:
                        errors['name'] = []

                    errors['name'].append(
                        _('Names must not be duplicates'))

                if 'id' in names:
                    if 'name' not in errors:
                        errors['name'] = []
                    errors['name'].append(_('Id is an invalid name'))
            else:
                errors['datatype'] = ['Must provide a list with a collection']

            if errors:
                raise ValidationError(errors)

        else:
            datatype = self.datatype_dict
            if isinstance(datatype, dict):
                self._validate_single_datatype(datatype)
            else:
                raise ValidationError('Must be a dictionary')

    def _validate_single_datatype(self, datatype):
        if 'type' not in datatype:
            raise ValidationError(_('type required data type definition'))

        if datatype['type'] not in ['float', 'int', 'string',
                                    'user', 'choice', 'date',
                                    'multichoice']:
            raise ValidationError(_('invalid datatype'))

        if datatype['type'] in ('choice', 'multichoice'):
            choices = datatype.get('choices', None)

            if choices is None:
                raise ValidationError(_('Missing choices key'))

            choices = UserDefinedFieldDefinition._all_choices(datatype)

            for choice in choices:
                if not isinstance(choice, basestring):
                    raise ValidationError(_('Choice must be a string'))
                if choice is None or choice.strip() == '':
                    raise ValidationError(_('Empty choice is not allowed'))

            if len(choices) == 0:
                raise ValidationError(_('There must be at least one choice'))

            if len(choices) != len(set(choices)):
                raise ValidationError(_('Duplicate choices are not allowed'))

        if 'default' in datatype:
            try:
                self.clean_value(datatype['default'], datatype)
            except ValidationError as e:
                raise ValidationError(
                    'Default must be valid for field: %(underlying_error)s' %
                    {'underlying_error': e.message})

    def save(self, *args, **kwargs):
        if self.name is not None:
            self.name = self.name.strip()
        self.validate()
        super(UserDefinedFieldDefinition, self).save(*args, **kwargs)

    def can_be_deleted(self, user):
        """
        Return True if user is able to delete this UDF.
        """
        # Deleting collection UDFs is not supported
        if self.iscollection:
            return False
        if self.is_protected:
            return False
        return True

    @transaction.atomic
    def delete(self, *args, **kwargs):
        save_instance = False

        if self.is_protected:
            raise AuthorizeException("Cannot delete protected UDF '%s'"
                                     % (self.name))

        if self.iscollection:
            UserDefinedCollectionValue.objects.filter(field_definition=self)\
                                              .delete()

            Audit.objects.filter(instance=self.instance)\
                         .filter(model=self.collection_audit_name)\
                         .delete()

            for prop in ('mobile_api_fields', 'web_detail_fields'):
                if prop not in self.instance.config:
                    pass

                for group in getattr(self.instance, prop):
                    if self.full_name in group.get('collection_udf_keys', []):
                        # If this is the only collection UDF with this name,
                        # we remove the entire group, since there would be no
                        # eligible items to go *in* the group after deletion
                        if len([udf for udf in udf_defs(self.instance)
                                if udf.name == self.name]) == 1:
                            getattr(self.instance, prop).remove(group)
                        # Otherwise, just remove this UDF from the group
                        else:
                            group['collection_udf_keys'].remove(self.full_name)
                    self.instance.save()
        else:
            Model = safe_get_udf_model_class(self.model_type)
            objects_with_udf_data = (Model
                                     .objects
                                     .filter(instance=self.instance)
                                     .filter(udfs__contains=[self.name]))

            for obj in objects_with_udf_data:
                del obj.udfs[self.name]
                # save_base instead of save_with_user,
                # we delete the audits anyways
                obj.save_base()

            Audit.objects.filter(instance=self.instance)\
                         .filter(model=self.model_type)\
                         .filter(field=self.canonical_name)\
                         .delete()

            # For mobile_api_fields, mobile_search_fields, and search_config,
            # and web_detail_fields
            # If the field is not in the config, that means the instance is
            # using the default, which should not be mutated
            for prop in ('mobile_api_fields', 'web_detail_fields'):
                if prop in self.instance.config:
                    for group in getattr(self.instance, prop):
                        if self.full_name in group.get('field_keys', []):
                            group['field_keys'].remove(self.full_name)
                            save_instance = True

            if 'search_config' in self.instance.config:
                for key in (self.model_type, 'missing'):
                    if key in self.instance.search_config:
                        self.instance.search_config[key] = [
                            o for o in self.instance.search_config[key]
                            if o.get('identifier') != self.full_name]
                        save_instance = True

            if 'mobile_search_fields' in self.instance.config:
                for key in ('standard', 'missing'):
                    if key in self.instance.mobile_search_fields:
                        self.instance.mobile_search_fields[key] = [
                            o for o in self.instance.mobile_search_fields[key]
                            if o.get('identifier') != self.full_name]
                        save_instance = True

        if save_instance:
            self.instance.save()

        # remove field permissions for this udf
        perms = FieldPermission.objects.filter(model_name=self.model_type,
                                               field_name=self.canonical_name,
                                               instance=self.instance)
        # iterating instead of doing a bulk delete in order to trigger signals
        for perm in perms:
            perm.delete()

        super(UserDefinedFieldDefinition, self).delete(*args, **kwargs)

    @property
    def datatype_dict(self):
        return json.loads(self.datatype)

    @property
    def datatype_by_field(self):
        datatypes_raw = self.datatype_dict
        datatypes = {}

        for datatype_dict in datatypes_raw:
            datatypes[datatype_dict['name']] = datatype_dict

        return datatypes

    @property
    def permissions_for_udf(self):
        return FieldPermission.objects.filter(
            instance=self.instance,
            model_name=self.model_type,
            field_name=self.canonical_name)

    def reverse_clean(self, value):
        if self.datatype_dict['type'] == 'user':
            if hasattr(value, 'pk'):
                value = str(value.pk)
        elif self.datatype_dict['type'] == 'multichoice':
            if value and len(value) > 0:
                value = json.dumps(value, ensure_ascii=False)
            else:
                value = None  # so "missing data" searches will work
        if value:
            return value if isinstance(value, unicode) else str(value)
        else:
            return None

    def clean_value(self, value, datatype_dict=None):
        """
        Given a value for this data type, validate and return the
        correct python/django representation.

        For instance, if this is a 'user' field this function will take
        in a user id (as a string) from the UDF dictionary and return
        a 'User' object.

        If that user doesn't exist a ValidationError will be raised

        If datatype_dict isn't passed specifically it will use the
        standard one for this model.
        """
        from treemap.models import User  # Circular ref issue

        if value is None:
            return None

        if datatype_dict is None:
            datatype_dict = self.datatype_dict

        datatype = datatype_dict['type']
        if datatype == 'float':
            try:
                return float(value)
            except ValueError:
                raise ValidationError(_('%(fieldname)s '
                                        'must be a real number') %
                                      {'fieldname': self.name})
        elif datatype == 'int':
            try:
                if float(value) != int(value):
                    raise ValueError

                return int(value)
            except ValueError:
                raise ValidationError(_('%(fieldname)s must be an integer') %
                                      {'fieldname': self.name})
        elif datatype == 'user':
            if isinstance(value, User):
                return value

            try:
                pk = int(value)
            except ValueError:
                raise ValidationError(_('%(fieldname)s must be an integer') %
                                      {'fieldname': self.name})
            try:
                return User.objects.get(pk=pk)
            except User.DoesNotExist:
                raise ValidationError(_('%(fieldname)s user not found') %
                                      {'fieldname': self.name})

        elif datatype == 'date':
            if isinstance(value, (date, datetime)):
                return value

            try:
                valid_date = parse_date_string_with_or_without_time(value)
            except ValueError:
                raise ValidationError(_('%(fieldname)s must be formatted as '
                                        'YYYY-MM-DD') %
                                      {'fieldname': self.name})

            # Ensure date UDF values contain a year >= 1900 so that
            # date formatting with `strftime` will work correctly.
            if valid_date.year < 1900:
                raise ValidationError(_('%(fieldname)s year must be >= 1900')
                                      % {'fieldname': self.name})

            return valid_date

        elif 'choices' in datatype_dict:
            choices = UserDefinedFieldDefinition._all_choices(datatype_dict)

            def _validate(val):
                if val not in choices:
                    raise ValidationError(
                        _('Invalid choice (%(given)s). Expecting %(allowed)s')
                        % {'given': val,
                           'allowed': ', '.join(choices)})

            if datatype == 'choice':
                _validate(value)
                return value
            else:  # 'multichoice'
                try:
                    values = json.loads(value)
                except ValueError:
                    raise ValidationError(
                        _('%(fieldname)s must be valid JSON') %
                        {'fieldname': self.name})
                if isinstance(values, basestring):
                    # A single string is valid JSON. Wrap as a list for
                    # consistency
                    values = [values]
                map(_validate, values)
                return values
        else:
            return value

    def clean_collection(self, data):
        datatypes = {datatype['name']: datatype
                     for datatype
                     in self.datatype_dict}
        errors = {}

        for entry in data:
            for subfield_name, subfield_val in entry.iteritems():
                if subfield_name == 'id':
                    continue

                datatype = datatypes.get(subfield_name, None)
                if datatype:
                    try:
                        subfield_val = self.clean_value(
                            subfield_val, datatype)

                    except ValidationError as e:
                        msgs = e.messages
                        errors[self.canonical_name] = msgs
                else:
                    errors[self.canonical_name] = ['Invalid subfield %s' %
                                                   subfield_name]

        if errors:
            raise ValidationError(errors)

    @property
    def canonical_name(self):
        return make_udf_name_from_key(self.name)

    @property
    def full_name(self):
        return to_object_name(self.model_type) + '.' + self.canonical_name

    @property
    def collection_audit_name(self):
        return make_udf_name_from_key(self.pk)


post_save.connect(invalidate_adjuncts, sender=UserDefinedFieldDefinition)
post_delete.connect(invalidate_adjuncts, sender=UserDefinedFieldDefinition)


class UDFDictionary(HStoreDict):

    def __init__(self, value, field, obj=None, *args, **kwargs):
        super(UDFDictionary, self).__init__(value, field, *args, **kwargs)
        self.instance = obj

        self._fields = None
        self._collection_fields = None

    @property
    def collection_data_loaded(self):
        return self._collection_fields is not None

    @property
    def collection_fields(self):
        """
        Lazy loading of collection fields
        """
        return self._base_collection_fields(clean=True)

    def force_reload_of_collection_fields(self):
        self._collection_fields = None

    def _base_collection_fields(self, clean):

        if self._collection_fields is None:
            self._collection_fields = {}
            udfs_on_model = self.instance.get_user_defined_fields()

            values = UserDefinedCollectionValue.objects.filter(
                model_id=self.instance.pk,
                field_definition__in=udfs_on_model)

            for value in values:
                if clean:
                    data = value.get_cleaned_data()
                else:
                    data = value.data
                    data['id'] = value.pk

                name = value.field_definition.name

                if name not in self._collection_fields:
                    self._collection_fields[name] = []

                self._collection_fields[name].append(data)

        return self._collection_fields

    def _get_udf_or_error(self, key):
        for field in self.instance.get_user_defined_fields():
            if field.name == key:
                return field

        raise KeyError("Couldn't find UDF for field '%s'" % key)

    def __contains__(self, key):
        return key in [field.name for field
                       in self.instance.get_user_defined_fields()]

    def __getitem__(self, key):
        udf = self._get_udf_or_error(key)

        if udf.iscollection:
            return self.collection_fields.get(key, [])
        else:
            if super(UDFDictionary, self).__contains__(key):
                v = super(UDFDictionary, self).__getitem__(key)
                try:
                    return udf.clean_value(v)
                except:
                    return v
            else:
                return None

    def __setitem__(self, key, val):
        udf = self._get_udf_or_error(key)

        if udf.iscollection:
            self.instance.dirty_collection_udfs[key] = True
            # HStoreDict cleans values in-place, so we need to do a deep-copy
            self.collection_fields[key] = copy.deepcopy(val)
        else:
            val = udf.reverse_clean(val)
            super(UDFDictionary, self).__setitem__(key, val)


class UDFDescriptor(Creator):
    def __get__(self, obj, type=None):
        if obj is None:
            return None
        # UDFDictionary needs a reference to the model instance to lookup
        # collection UDFs
        udf_dict = obj.__dict__[self.field.name]
        # Workaround for test failure on some dev machines
        if udf_dict == '':
            udf_dict = UDFDictionary({}, self.field, obj)
        udf_dict.instance = obj

        return udf_dict

    def __set__(self, obj, value):
        value = self.field.to_python(value)
        if isinstance(value, dict):
            value = UDFDictionary(
                value=value, field=self.field, instance=obj
            )
        # setattr goes into infinite recursion, so fish in `__dict__`
        obj.__dict__[self.field.name] = value


class UDFField(DictionaryField):
    # Overridden to convert HStoreDict values to UDFDictionary values
    def get_default(self):
        hstore_dict = super(UDFField, self).get_default()
        if isinstance(hstore_dict, HStoreDict):
            return UDFDictionary(hstore_dict, self)
        else:
            return hstore_dict

    # Overridden to convert HStoreDict values to UDFDictionary values
    def get_prep_value(self, value):
        if isinstance(value, dict) and not isinstance(value, UDFDictionary):
            return UDFDictionary(value, self)
        else:
            return value

    # Overridden to convert HStoreDict values to UDFDictionary values
    def contribute_to_class(self, cls, name):
        super(UDFField, self).contribute_to_class(cls, name)
        setattr(cls, self.name, UDFDescriptor(self))


class _UDFProxy(UDFField):
    def __init__(self, name, *args, **kwargs):
        super(_UDFProxy, self).__init__(*args, **kwargs)
        self.column = ('udf', name)
        self.model = None

    def to_python(self, value):
        return value


class UDFModelBase(ModelBase):

    def __new__(clazz, *args, **kwargs):
        new = super(UDFModelBase, clazz).__new__(clazz, *args, **kwargs)

        orig = new._meta.get_field_by_name

        def get_field_by_name(name):
            try:
                return orig(name)
            except Exception:
                if name.startswith('udf:'):
                    udf, udfname = name.split(':', 1)
                    field, model, direct, m2m = orig('udfs')
                    field = _UDFProxy(udfname)
                    return (field, model, direct, m2m)
                else:
                    raise

        setattr(new._meta, 'get_field_by_name', get_field_by_name)
        return new


class UDFModel(UserTrackable, models.Model):
    """
    Classes that extend this model gain support for scalar UDF
    fields via the `udfs` field.

    This model works correctly with the Auditable and
    Authorizable mixins
    """

    __metaclass__ = UDFModelBase
    udfs = UDFField(db_index=True, blank=True)

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super(UDFModel, self).__init__(*args, **kwargs)
        # Collection UDF audits are handled by the UDFCollectionValue class
        self._collection_field_names = {udfd.canonical_name
                                        for udfd in self.collection_udfs}
        # This is the whole reason for keeping _do_not_track
        # in addition to the do_not_track class property.
        self._do_not_track |= self.do_not_track | self._collection_field_names
        self.populate_previous_state()

        self.dirty_collection_udfs = {}

    @classproperty
    def do_not_track(cls):
        return UserTrackable.do_not_track | {'udfs'}

    def fields_were_updated(self):
        normal_fields = super(UDFModel, self).fields_were_updated()

        return normal_fields or self.dirty_collection_udfs

    def get_user_defined_fields(self):
        if hasattr(self, 'instance'):
            return udf_defs(self.instance, self._model_name)
        else:
            return []

    def audits(self):
        regular_audits = Q(model=self._model_name,
                           model_id=self.pk,
                           instance=self.instance)

        udf_collection_audits = Q(
            model__in=self.collection_udfs_audit_names(),
            model_id__in=self.collection_udfs_audit_ids())

        all_audits = udf_collection_audits | regular_audits
        return Audit.objects.filter(all_audits).order_by('created')

    def search_slug(self):
        return to_object_name(self.__class__.__name__)

    def collection_udfs_audit_ids(self):
        return self.static_collection_udfs_audit_ids(
            (self.instance,), (self.pk,), self.collection_udfs_audit_names())

    @staticmethod
    def static_collection_udfs_audit_ids(instances, pks, audit_names):
        """
        We want to get the collection udfs of deleted objects.

        We can get the instance and pk of an object from the Audit table,

        Generally you will get the audit_names by instantiating a new model
        instance like so and calling the appropriate method on it:
            tree = Tree(instance=instance)
            tree.collection_udfs_audit_names()
        """
        # Because current_value is a string, if we want to do an IN query,
        # we need to cast all of the pks to strings
        pks = [str(pk) for pk in pks]
        return Audit.objects.filter(instance__in=instances)\
                            .filter(model__in=audit_names)\
                            .filter(field='model_id')\
                            .filter(current_value__in=pks)\
                            .distinct('model_id')\
                            .values_list('model_id', flat=True)

    def apply_change(self, key, val):
        if key.startswith('udf:'):
            udf_field_name = get_name_from_canonical_name(key)
            if udf_field_name in self.udf_field_names:
                self.udfs[udf_field_name] = val
            else:
                raise Exception("cannot find udf field" % udf_field_name)
        else:
            super(UDFModel, self).apply_change(key, val)

    def save(self, *args, **kwargs):
        raise UserTrackingException(
            'All changes to %s objects must be saved via "save_with_user"' %
            (self._model_name))

    @property
    def udf_field_names(self):
        return [field.name for field in self.get_user_defined_fields()]

    @property
    def scalar_udf_names_and_fields(self):
        model_name = to_object_name(self.__class__.__name__)
        return [(field.name, model_name + ".udf:" + field.name)
                for field in self.get_user_defined_fields()
                if not field.iscollection]

    @property
    def collection_udf_names_and_fields(self):
        model_name = to_object_name(self.__class__.__name__)
        return [(field.name, model_name + ".udf:" + field.name)
                for field in self.collection_udfs]

    @property
    def scalar_udf_field_names(self):
        return [field.name for field
                in self.get_user_defined_fields()
                if not field.iscollection]

    @property
    def collection_udfs(self):
        return [field
                for field in self.get_user_defined_fields()
                if field.iscollection]

    def collection_udfs_audit_names(self):
        return [udf.collection_audit_name for udf in self.collection_udfs]

    def collection_udfs_search_names(self):
        object_name = to_object_name(self.__class__.__name__)
        return ['udf:%s:%s' % (object_name, udf.pk)
                for udf in self.collection_udfs]

    def visible_collection_udfs_audit_names(self, user):
        if isinstance(self, Authorizable):
            visible_fields = self.visible_fields(user)
            return [udf.collection_audit_name for udf in self.collection_udfs
                    if udf.canonical_name in visible_fields]
        return self.collection_udfs_audit_names()

    @classproperty
    def collection_udf_settings(cls):
        return {
            k: v for k, v in
            getattr(cls, 'udf_settings', {}).items()
            if v.get('iscollection')}

    @property
    def tracked_fields(self):
        return super(UDFModel, self).tracked_fields + \
            ['udf:' + name for name in self.scalar_udf_field_names]

    def as_dict(self, *args, **kwargs):

        def _format_value(value):
            # Format dates. Always use datetime for dict serialzation
            if hasattr(value, 'strftime'):
                return value.strftime(DATETIME_FORMAT)
            return value

        base_model_dict = super(UDFModel, self).as_dict(*args, **kwargs)

        for field_obj in self.get_user_defined_fields():
            field = field_obj.name
            value = self.udfs[field]

            if field_obj.iscollection:
                # For colllection UDFs, we need to format each subvalue inside
                # each dictionary
                value = [{k: _format_value(val)
                         for k, val in sub_dict.iteritems()}
                         for sub_dict in value]
            else:
                value = _format_value(value)

            base_model_dict['udf:' + field] = value

        # Torch the "udfs" dictionary
        del base_model_dict['udfs']

        return base_model_dict

    def save_with_user(self, user, *args, **kwargs):
        """
        Saving a UDF model now involves saving all of collection-based
        udf fields, we do this here.
        """
        # We may need to get a primary key here before we continue
        super(UDFModel, self).save_with_user(user, *args, **kwargs)

        collection_values = self.udfs._base_collection_fields(clean=False)

        fields = {field.name: field
                  for field in self.get_user_defined_fields()}

        for field_name, values in collection_values.iteritems():
            if self.dirty_collection_udfs.get(field_name):
                field = fields[field_name]

                ids_specified = []
                for value_dict in values:
                    kwargs = {'field_definition': field,
                              'model_id': self.pk}
                    if 'id' in value_dict:
                        id = value_dict['id']
                        del value_dict['id']

                        kwargs['pk'] = id
                        udcv = UserDefinedCollectionValue.objects.get(**kwargs)
                    else:
                        udcv = UserDefinedCollectionValue(**kwargs)

                    if udcv.data != value_dict:
                        udcv.data = value_dict
                        udcv.save_with_user(user)

                    ids_specified.append(udcv.pk)

                # Delete all values that weren't presented here
                field.userdefinedcollectionvalue_set\
                    .filter(model_id=self.pk)\
                    .exclude(id__in=ids_specified)\
                    .delete()

        # We need to reload collection UDFs in order to have their IDs set
        self.udfs.force_reload_of_collection_fields()

        self.dirty_collection_udfs = {}

    def clean_udfs(self):
        scalar_fields = {field.name: field
                         for field in self.get_user_defined_fields()
                         if not field.iscollection}

        collection_fields = {field.name: field
                             for field in self.get_user_defined_fields()
                             if field.iscollection}

        errors = {}
        # Clean scalar udfs
        for (key, val) in self.udfs.iteritems():
            field = scalar_fields.get(key, None)
            if field:
                try:
                    field.clean_value(val)
                except ValidationError as e:
                    errors[make_udf_name_from_key(key)] = e.messages
            else:
                errors[make_udf_name_from_key(key)] = [_(
                    'Invalid user defined field name')]

        # Clean collection values, but only if they were loaded
        if self.udfs.collection_data_loaded:
            collection_data = self.udfs.collection_fields
            for collection_field_name, data in collection_data.iteritems():
                collection_field = collection_fields.get(
                    collection_field_name, None)

                if collection_field:
                    try:
                        collection_field.clean_collection(data)
                    except ValidationError as e:
                        errors.update(e.message_dict)
                else:
                    errors[make_udf_name_from_key(collection_field_name)] = [_(
                        'Invalid user defined field name')]

        if errors:
            raise ValidationError(errors)

    def clean_fields(self, exclude):
        exclude = exclude + ['udfs']
        errors = {}
        try:
            super(UDFModel, self).clean_fields(exclude)
        except ValidationError as e:
            errors = e.message_dict

        try:
            self.clean_udfs()
        except ValidationError as e:
            errors.update(e.message_dict)

        if errors:
            raise ValidationError(errors)


def quotesingle(string):
    "Quote a string with ' characters, replacing them with ''"
    return string.replace("'", "''")


UDF_LOOKUP_PATTERN = re.compile(r'(.*?__)?udf\:(.+?)(__[a-zA-z]+)?$')
UDF_ORDER_PATTERN = re.compile(r'(-?)([a-zA-Z]+)\.udf\:(.+)$')


class UDFBaseContains(Lookup):
    def as_postgresql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)

        op = 'LIKE' if self.lookup_name == 'udf_contains' else 'ILIKE'

        if len(rhs_params) == 1 and isinstance(rhs_params[0], dict):
            param = rhs_params[0]
            param_keys = list(param.keys())
            conditions = []

            # Need to wrap every value in percents, since Django isn't
            # doing it for us
            values = ['%' + val + '%' for val in param.values()]

            for key in param_keys:
                conditions.append(
                    '%s->\'%s\' %s %%s' % (lhs, quotesingle(key), op))

            return (" AND ".join(conditions), values)

        raise ValueError('invalid value')


@UDFField.register_lookup
class UDFContains(UDFBaseContains):
    lookup_name = 'udf_contains'


@UDFField.register_lookup
class UDFIContains(UDFBaseContains):
    lookup_name = 'udf_icontains'


class UDFQuery(Query):
    """
    UDF Query encapsulates query compilation changes.

    This class allows us to write the where clauses for a
    query that looks something like:

    Plot.objects.filter(**{'udf:Plant Date': datetime(2000,1,2)})

    And transforms it into something like:
    Plot.objects.filter(udfs={'Plant Date': datetime(2000,1,2)})

    This will allow django-hstore to transform it into SQL similar to:

    ("treemap_plot"."udfs"->'Plant Date')::timestamp = '2000-01-02'::timestamp

    Insert text 'bout contains/icontains

    TODO: Is this true?
    NOTE: This class *must* inherit from Query, not HstoreQuery
          HStoreQuery will overwrite our WhereNode with it's own
    """
    def build_filter(self, filter_expr, *args, **kwargs):
        arg, value = filter_expr
        match = UDF_LOOKUP_PATTERN.match(arg)

        if match:
            model, udf_name, lookup = match.groups()

            if model is None:
                model = ''

            # For contains searches on UDFs we need to switch to our custom
            # lookup class, because django-hstore defines contains as subset
            #
            # For exact searches on scalar UDFs, we actually want contains,
            # because we don't care about other UDF values
            if lookup == '__contains':
                lookup = '__udf_contains'
            elif lookup == '__icontains':
                lookup = '__udf_icontains'
            elif lookup is None or lookup == '__exact':
                lookup = '__contains'

            arg = model + 'udfs' + lookup
            wrapped_param = {}
            wrapped_param[udf_name] = value

            filter_expr = (arg, wrapped_param)
        return super(UDFQuery, self).build_filter(filter_expr, *args, **kwargs)

    def process_as_udf(self, field):
        """
        Determine if a given field is a UDF definition for
        ordering.

        If not, return False.

        A udf definition must match the UDF_ORDER_PATTERN regular
        expression. Generally looks something like:

        `Plot.udf:Nickname`
        `-Tree.udf:Secret ID``

        The return value will work with normal quoting rules to
        generate the proper SQL

        WARNING: Since we don't know the datatype of a sort field
        we cannot cast it. Dates will sort correctly since dates are
        lexicographically ordered. Numbers will not.
        """
        udf = UDF_ORDER_PATTERN.match(field)

        if udf:
            sign, model, udffield = udf.groups()

            sign = sign or ''

            model_class = safe_get_udf_model_class(model)
            table_name = model_class._meta.db_table

            accessor = ("%s%s.udfs->'%s'" %
                        (sign, table_name, quotesingle(udffield)))

            return accessor
        else:
            return False

    def add_ordering(self, *ordering):
        """
        This method was copied and modified from django core. In
        particular, each field should be checked against UDF_ORDER_PATTERN
        via 'process_as_udf'
        """
        fields = []
        errors = []
        for item in ordering:
            udf = self.process_as_udf(item)
            if udf:
                fields.append(udf)
            elif ORDER_PATTERN.match(item):
                fields.append(item)
            else:
                errors.append(item)
        if errors:
            raise FieldError('Invalid order_by arguments: %s' % errors)
        if ordering:
            self.order_by.extend(fields)
        else:
            self.default_ordering = False


class UDFQuerySet(HStoreGeoQuerySet):
    """
    A query set that supports udf-based filter queries

    This class exists mainly to provide an injection point
    for UDFQuery
    """
    def __init__(self, model=None, query=None, using=None, hints=None):
        super(UDFQuerySet, self).__init__(
            model=model, query=query, using=using, hints=hints)
        self.query = query or UDFQuery(model)


class GeoHStoreUDFManager(HStoreGeoManager):
    """
    Merges the normal geo manager with the hstore manager backend
    """
    def get_queryset(self):
        return UDFQuerySet(self.model, using=self._db)
