# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
import copy
import re

from django.core.exceptions import ValidationError, FieldError
from django.utils.translation import ugettext_lazy as trans
from django.contrib.gis.db import models
from django.db import transaction
from django.db.models import Q
from django.db.models.fields.subclassing import Creator
from django.db.models.base import ModelBase
from django.db.models.sql.constants import ORDER_PATTERN
from django.db.models.signals import post_save, post_delete

from django.contrib.gis.db.models.sql.query import GeoQuery

from django_hstore.fields import DictionaryField, HStoreDict
from django_hstore.managers import HStoreManager, HStoreGeoManager
from django_hstore.query import HStoreGeoQuerySet, HStoreGeoWhereNode

from treemap.instance import Instance
from treemap.audit import (UserTrackable, Audit, UserTrackingException,
                           _reserve_model_id, FieldPermission,
                           AuthorizeException, Authorizable, Auditable)
from treemap.lib.object_caches import permissions, invalidate_adjuncts, \
    udf_defs
from treemap.lib.dates import (parse_date_string_with_or_without_time,
                               DATETIME_FORMAT)
from treemap.util import safe_get_model_class, to_object_name

# Allow anything except certain known problem characters.
# NOTE: Make sure to keep the validation error associated with this up-to-date
# '%' in general makes the Django ORM error out.
# '__' is also problematic for the Django ORM
# '.' is fine for the ORM, but made the template system unhappy.
_UDF_NAME_REGEX = re.compile(r'^[^_%.]+$')

# Used for collection UDF search on the web
# if we come to support more udfcs, we can add them here.
UDFC_MODELS = ('Tree', 'Plot')
UDFC_NAMES = ('Stewardship', 'Alerts')


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
        raise ValidationError(trans('invalid model type - must subclass '
                                    'UDFModel'))

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
        self._do_not_track.add('data')
        self.populate_previous_state()

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
                pk = int(audit_name[4:])
                if not instance:
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
                Audit.Type.Insert: trans('created a %(model)s entry'),
                Audit.Type.Update: trans('updated the %(model)s entry'),
                Audit.Type.Delete: trans('deleted the %(model)s entry'),
                Audit.Type.PendingApprove: trans('approved an edit '
                                                 'to the %(model)s entry'),
                Audit.Type.PendingReject: trans('rejected an '
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
            field = field[4:]

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
            key = key[4:]
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
        field = 'udf:%s' % self.field_definition.name
        perms = permissions(user, self.field_definition.instance,
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
            for field, (oldval, _) in updated_fields.iteritems():
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
                model='udf:%s' % self.field_definition.pk,
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
    Name of the UDFD
    """
    name = models.CharField(max_length=255)

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
        if datatype['type'] != 'choice':
            raise ValidationError(
                {'datatype': [trans("can't change choices "
                                    "on a non-choice field")]})

        if old_choice_value not in datatype['choices']:
            raise ValidationError(
                {'datatype': [trans("choice '%(choice)s' not found") % {
                    'choice': old_choice_value}]})

        choices = datatype['choices']
        if new_choice_value:
            choices = [c if c != old_choice_value else new_choice_value
                       for c in choices]
        else:
            choices = [c for c in choices if c != old_choice_value]

        datatype['choices'] = choices
        return datatype

    def _update_choice_scalar(self, old_choice_value, new_choice_value):
        datatype = self._validate_and_update_choice(
            self.datatype_dict, old_choice_value, new_choice_value)

        self.datatype = json.dumps(datatype)
        self.save()

        Model = safe_get_udf_model_class(self.model_type)
        for model in Model.objects\
                          .filter(**{'udf:%s' % self.name:
                                     old_choice_value}):
            model.udfs[self.name] = new_choice_value
            model.save_base()

        audits = Audit.objects.filter(
            model=self.model_type,
            field='udf:%s' % self.name,
            instance=self.instance)

        self._update_choices_on_audits(
            audits, old_choice_value, new_choice_value)

    def _update_choices_on_audits(
            self, audits, old_choice_value, new_choice_value):

        cval_audits = audits.filter(current_value=old_choice_value)
        pval_audits = audits.filter(previous_value=old_choice_value)

        if new_choice_value is None:
            cval_audits.delete()
            pval_audits.delete()
        else:
            cval_audits.update(current_value=new_choice_value)
            pval_audits.update(previous_value=new_choice_value)

    def add_choice(self, new_choice_value, name=None):
        if self.iscollection:
            if name is None:
                raise ValidationError({
                    'name': [trans('Name is required for collection fields')]})

            datatypes = {d['name']: d for d in self.datatype_dict}
            datatypes[name]['choices'].append(new_choice_value)

            self.datatype = json.dumps(datatypes.values())
            self.save()
        else:
            if name is not None:
                raise ValidationError({
                    'name': [trans(
                        'Name is allowed only for collection fields')]})

            datatype = self.datatype_dict
            datatype['choices'].append(new_choice_value)

            self.datatype = json.dumps(datatype)
            self.save()

    @transaction.atomic
    def update_choice(
            self, old_choice_value, new_choice_value, name=None):
        datatype = self.datatype_dict

        if self.iscollection:
            if name is None:
                raise ValidationError({
                    'name': [trans('Name is required for collection fields')]})

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
                model='udf:%s' % self.pk,
                field='udf:%s' % name)

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
                    'name': [trans(
                        'Name is allowed only for collection fields')]})

            self._update_choice_scalar(old_choice_value, new_choice_value)

    def validate(self):
        model_type = self.model_type

        model_class = safe_get_udf_model_class(model_type)

        field_names = [field.name for field in model_class._meta.fields]

        if self.name in field_names:
            raise ValidationError(
                {'name': [trans('cannot use fields that already '
                                'exist on the model')]})
        if not self.name:
            raise ValidationError(
                {'name': [trans('name cannot be blank')]})

        if not _UDF_NAME_REGEX.match(self.name):
            raise ValidationError(
                {'name': [trans("A field name may not contain percent (%), "
                                "period (.) or underscore (_) characters.")]})

        existing_objects = UserDefinedFieldDefinition\
            .objects\
            .filter(
                model_type=model_type,
                instance=self.instance,
                name=self.name)\
            .exclude(
                pk=self.pk)

        if existing_objects.count() != 0:
            raise ValidationError(trans('a field already exists on this model '
                                        'with that name'))

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
                        errors['name'] = [trans('Name must not be empty')]

                names = {datatype.get('name') for datatype in datatypes}

                if len(names) != len(datatypes):
                    if 'name' not in errors:
                        errors['name'] = []

                    errors['name'].append(
                        trans('Names must not be duplicates'))

                if 'id' in names:
                    if 'name' not in errors:
                        errors['name'] = []
                    errors['name'].append(trans('Id is an invalid name'))
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
            raise ValidationError(trans('type required data type definition'))

        if datatype['type'] not in ['float', 'int', 'string',
                                    'user', 'choice', 'date']:
            raise ValidationError(trans('invalid datatype'))

        if datatype['type'] == 'choice':
            choices = datatype.get('choices', None)

            if choices is None:
                raise ValidationError(trans('missing choices key for key'))

            for choice in choices:
                if not isinstance(choice, basestring):
                    raise ValidationError(trans('Choice must be a string'))
                if choice is None or choice == '':
                    raise ValidationError(trans('empty choice not allowed'))

            if len(choices) == 0:
                raise ValidationError(trans('empty choice list'))

            if len(choices) != len(set(choices)):
                raise ValidationError(trans('duplicate choices'))

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

    @transaction.atomic
    def delete(self, *args, **kwargs):

        if self.iscollection:
            UserDefinedCollectionValue.objects.filter(field_definition=self)\
                                              .delete()

            Audit.objects.filter(instance=self.instance)\
                         .filter(model='udf:%s' % self.pk)\
                         .delete()
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

        # remove field permissions for this udf
        FieldPermission.objects.filter(
            model_name=self.model_type,
            field_name=self.canonical_name,
            instance=self.instance).delete()

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

        if value:
            return str(value)
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
                raise ValidationError(trans('%(fieldname)s '
                                            'must be a real number') %
                                      {'fieldname': self.name})
        elif datatype == 'int':
            try:
                if float(value) != int(value):
                    raise ValueError

                return int(value)
            except ValueError:
                raise ValidationError(trans('%(fieldname)s '
                                            'must be an integer') %
                                      {'fieldname': self.name})
        elif datatype == 'user':
            if isinstance(value, User):
                return value

            try:
                pk = int(value)
            except ValueError:
                raise ValidationError(trans('%(fieldname)s '
                                            'must be an integer') %
                                      {'fieldname': self.name})
            try:
                return User.objects.get(pk=pk)
            except User.DoesNotExist:
                raise ValidationError(trans('%(fieldname)s '
                                            'user not found') %
                                      {'fieldname': self.name})

        elif datatype == 'date':
            return parse_date_string_with_or_without_time(value)
        elif datatype == 'choice':
            if value in datatype_dict['choices']:
                return value
            else:
                raise ValidationError(
                    trans('Invalid choice (%(given)s). '
                          'Expecting %(allowed)s') %
                    {'given': value,
                     'allowed': ', '.join(datatype_dict['choices'])})
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
                        errors['udf:%s' % self.name] = msgs
                else:
                    errors['udf:%s' % self.name] = ['Invalid subfield %s' %
                                                    subfield_name]

        if errors:
            raise ValidationError(errors)

    @property
    def canonical_name(self):
        return 'udf:%s' % self.name

    @property
    def full_name(self):
        return to_object_name(self.model_type) + '.' + self.canonical_name


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

    @property
    def fields(self):
        # Django loads fields in the order they're defined on a given
        # class. For instance,
        #
        # class A(models.Model):
        #   a = models.IntField()
        #   b = models.IntField()
        #
        # Will first load 'a', create the attribute dictionary, add it
        # to the object and continue.
        #
        # Since UDFModel specifies the UDFField first, no other fields
        # are available on the subclassed object (Plot, Tree, etc) in
        # the constructor
        #
        # The solution is to simply cache the instance and grab the data
        # in a lazy way
        if self._fields is None:
            self._fields = self.instance.get_user_defined_fields()

        return self._fields

    def _get_udf_or_error(self, key):
        for field in self.fields:
            if field.name == key:
                return field

        raise KeyError("Couldn't find UDF for field '%s'" % key)

    def __contains__(self, key):
        return key in [field.name for field in self.fields]

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
            self.instance.dirty_collection_udfs = True
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

from south.modelsinspector import add_introspection_rules
add_introspection_rules([], ["^treemap\.udf\.UDFField"])


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
        self._do_not_track.add('udfs')
        # Collection UDF audits are handled by the UDFCollectionValue class
        self._do_not_track |= {udfd.canonical_name
                               for udfd in self.collection_udfs}
        self.populate_previous_state()

        self.dirty_collection_udfs = False

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
            udf_field_name = key[4:]
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
        model_name = self.__class__.__name__.lower()
        return [(field.name, model_name + ".udf:" + field.name)
                for field in self.get_user_defined_fields()
                if not field.iscollection]

    @property
    def collection_udf_names_and_fields(self):
        model_name = self.__class__.__name__.lower()
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
        return ['udf:%s' % udf.pk for udf in self.collection_udfs]

    def collection_udfs_search_names(self):
        object_name = to_object_name(self.__class__.__name__)
        return ['udf:%s:%s' % (object_name, udf.pk)
                for udf in self.collection_udfs]

    def visible_collection_udfs_audit_names(self, user):
        if isinstance(self, Authorizable):
            visible_fields = self.visible_fields(user)
            return ['udf:%s' % udf.pk for udf in self.collection_udfs
                    if udf.canonical_name in visible_fields]
        return self.collection_udfs_audit_names()

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

        for field in self.udf_field_names:
            value = self.udfs[field]

            if isinstance(value, list):
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
            field = fields[field_name]

            ids_specified = []
            for value_dict in values:
                if 'id' in value_dict:
                    id = value_dict['id']
                    del value_dict['id']

                    udcv = UserDefinedCollectionValue.objects.get(
                        pk=id,
                        field_definition=field,
                        model_id=self.pk)
                else:
                    udcv = UserDefinedCollectionValue(
                        field_definition=field,
                        model_id=self.pk)

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

        self.dirty_collection_udfs = False

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
                    errors['udf:%s' % key] = e.messages
            else:
                errors['udf:%s' % key] = [trans(
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
                    errors['udf:%s' % collection_field_name] = [trans(
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


def _is_scalar_udf(lvalue):
    return isinstance(lvalue.col, tuple) and lvalue.col[0] == 'udf'


class UDFWhereNode(HStoreGeoWhereNode):
    """
    This class allows us to write the where clauses for a
    query that looks something like:

    Plot.objects.filter(**{'udf:Plant Date': datetime(2000,1,2)})

    And transforms it into something like:
    Plot.objects.filter(udfs={'Plant Date': datetime(2000,1,2)})

    This will allow django-hstore to transform it into SQL similar to:

    ("treemap_plot"."udfs"->'Plant Date')::timestamp = '2000-01-02'::timestamp
    """

    def add(self, child, *args, **kwargs):
        """
        Converts the 'udf:Field Name' syntax to the syntax expected by
        django-hstore. e.g. filter(**{'udf:Field Name__gt': 17}) will be
        converted into filter(udfs__gt={'Field Name': 17})
        """
        if not isinstance(child, tuple):
            return super(UDFWhereNode, self).add(child, *args, **kwargs)
        lvalue, lookup, param = child

        # contains and icontains are handled below in make_atom
        if _is_scalar_udf(lvalue) and lookup not in ('contains', 'icontains'):
            # For exact searches on scalar UDFs, we actually want contains,
            # because we don't care about other UDF values
            if lookup == 'exact':
                lookup = 'contains'
            hstore_key = lvalue.col[1]
            lvalue.col = 'udfs'
            wrapped_param = {}
            wrapped_param[hstore_key] = param

            child = (lvalue, lookup, wrapped_param)

        return super(UDFWhereNode, self).add(child, *args, **kwargs)

    def make_atom(self, child, qn, connection):
        """
        django-hstore overloads contains to mean an *exact* search for subsets
        of key value pairs.  Because of this, to make our udf:field Name syntax
        work we have to handle generating SQL for contains and icontains here,
        instead of modifying the query and delegating it to django-hstore
        """
        if not isinstance(child, tuple):
            return super(UDFWhereNode, self).make_atom(child, qn, connection)

        lvalue, lookup, value_annot, value = child

        if _is_scalar_udf(lvalue) and lookup in ('contains', 'icontains'):
            hstore_key = lvalue.col[1]
            lvalue.col = 'udfs'

            lvalue, params = lvalue.process(lookup, value, connection)
            field = self.sql_for_columns(lvalue, qn, connection)

            op = 'LIKE' if lookup == 'contains' else 'ILIKE'
            sql = '(%s->\'%s\') %s %%s' % (field, hstore_key, op)
            return (sql, params)

        return super(UDFWhereNode, self).make_atom(child, qn, connection)

UDF_ORDER_PATTERN = re.compile(r'(-?)([a-zA-Z]+)\.udf\:(.+)$')


class UDFQuery(GeoQuery):
    """
    UDF Query encapsulates query compilation changes. In particular,
    it injects UDFWhereNode as the default WhereNode type (which can
    not be overwritten)
    NOTE: This class *must* inherit from GeoQuery, not HstoreGeoQuery
          HStoreGeoQuery will overwrite our WhereNode with it's own
    """

    def __init__(self, model):
        super(UDFQuery, self).__init__(model, UDFWhereNode)

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
    def __init__(self, model=None, query=None, using=None):
        super(UDFQuerySet, self).__init__(
            model=model, query=query, using=using)
        self.query = query or UDFQuery(model)


class GeoHStoreUDFManager(HStoreGeoManager):
    """
    Merges the normal geo manager with the hstore manager backend
    """
    def get_queryset(self):
        return UDFQuerySet(self.model, using=self._db)
