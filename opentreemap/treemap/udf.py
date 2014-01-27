# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
import re
from datetime import datetime

from django.core.exceptions import ValidationError, FieldError
from django.utils.translation import ugettext_lazy as trans
from django.contrib.gis.db import models
from django.db.models import Q
from django.db.models.base import ModelBase
from django.db.models.sql.constants import ORDER_PATTERN
from django.db.models.signals import post_save
from django.dispatch import receiver

from django.contrib.gis.db.models.sql.where import GeoWhereNode
from django.contrib.gis.db.models.sql.query import GeoQuery

from djorm_hstore.fields import DictionaryField, HStoreDictionary
from djorm_hstore.models import HStoreManager, HStoreQueryset

from treemap.instance import Instance
from treemap.audit import (UserTrackable, Audit, UserTrackingException,
                           _reserve_model_id, FieldPermission,
                           AuthorizeException, Authorizable, Auditable)
from treemap.util import safe_get_model_class

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
DATE_FORMAT = '%Y-%m-%d'


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
    def get_display_model_name(audit_name):
        if audit_name.startswith('udf:'):
            try:
                # UDF Collections store their model names in the audit table as
                # udf:<pk of UserDefinedFieldDefinition>
                pk = int(audit_name[4:])
                udf_def = UserDefinedFieldDefinition.objects.get(pk=pk)
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
        perms = user.get_instance_permissions(self.field_definition.instance,
                                              model_name=model)
        for perm in perms:
            if perm.field_name == field and perm.allows_writes:
                field_perm = perm
                break

        if field_perm is None:
            raise AuthorizeException('')

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
    objects if 'ismulti' is true, or a single dictionary otherwise.
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

    def validate(self):
        model_type = self.model_type

        model_class = safe_get_udf_model_class(model_type)

        field_names = [field.name for field in model_class._meta.fields]

        if self.name in field_names:
            raise ValidationError(
                {'name': trans('cannot use fields that already '
                               'exist on the model')})
        if not self.name:
            raise ValidationError(
                {'name': trans('name cannot be blank')})

        existing_objects = UserDefinedFieldDefinition.objects.filter(
            model_type=model_type,
            instance=self.instance,
            name=self.name)

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
                errors['datatype'] = 'Must provide a list with a collection'

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

    def save(self, *args, **kwargs):
        self.validate()
        super(UserDefinedFieldDefinition, self).save(*args, **kwargs)

    @property
    def datatype_dict(self):
        return json.loads(self.datatype)

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

        For instance, this is a 'user' field this function will take
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
            try:
                return datetime.strptime(value.strip(), DATETIME_FORMAT)
            except ValueError:
                # If the time is not included, try again with date only
                return datetime.strptime(value.strip(), DATE_FORMAT)
        elif datatype == 'choice':
            if value in datatype_dict['choices']:
                return value
            else:
                raise ValidationError(
                    trans('Invalid choice (%(given)s).'
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
                    errors['udf:%s' % self.name] = ('Invalid subfield %s' %
                                                    subfield_name)

        if errors:
            raise ValidationError(errors)

    @property
    def canonical_name(self):
        return 'udf:%s' % self.name


class UDFDictionary(HStoreDictionary):

    def __init__(self, value, field, obj, *args, **kwargs):
        super(UDFDictionary, self).__init__(value, field, *args, **kwargs)
        self.model = field.model
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

        if self._collection_fields is None:
            self._collection_fields = {}
            udfs_on_model = self.instance.get_user_defined_fields()

            values = UserDefinedCollectionValue.objects.filter(
                model_id=self.instance.pk,
                field_definition__in=udfs_on_model)

            for value in values:
                name = value.field_definition.name

                # Grab each datatype and assign the sub-name to the
                # definition. These are used to clean the data
                datatypes_raw = value.field_definition.datatype_dict
                datatypes = {}

                for datatype_dict in datatypes_raw:
                    datatypes[datatype_dict['name']] = datatype_dict

                if name not in self._collection_fields:
                    self._collection_fields[name] = []

                cleaned_data = {}
                for subfield_name in value.data:
                    sub_value = value.data.get(subfield_name, None)
                    try:
                        sub_value = value.field_definition.clean_value(
                            sub_value, datatypes[subfield_name])
                    except ValidationError:
                        # If there was an error coming from the database
                        # just continue with whatever the value was.
                        pass

                    cleaned_data[subfield_name] = sub_value

                cleaned_data['id'] = value.pk
                self._collection_fields[name].append(cleaned_data)

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
            self.collection_fields[key] = val
        else:
            val = udf.reverse_clean(val)

            super(UDFDictionary, self).__setitem__(key, val)


class UDFField(DictionaryField):

    _attribute_class = UDFDictionary

    # Overriden because we do our own string transformations
    # directly via the UDFDictionary
    def get_prep_value(self, data):
        return data


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


class UDFDCache(object):
    """
    Cache user defined field defintions
    """
    def __init__(self, max_size=10000):
        self.reset()
        self.max_size = max_size

    def reset(self):
        self.cache = {}

    def put(self, k, v):
        if len(self.cache) == self.max_size:
            self.reset()

        self.cache[k] = v
        return v

    def _cache_key(self, model_name, instance_id):
        return (model_name, instance_id)

    def get_defs_for_model(self, model_name, instance_id=None):
        key = self._cache_key(model_name, instance_id)

        if key not in self.cache:
            udfs = UserDefinedFieldDefinition.objects.filter(
                model_type=model_name)

            if instance_id:
                udfs = udfs.filter(instance__pk=instance_id)

            # Iterating over a queryset isn't theadsafe
            # so we need to force it here
            return self.put(key, list(udfs))
        else:
            return self.cache[key]

udf_cache = UDFDCache()


@receiver(post_save, sender=UserDefinedFieldDefinition)
def clear_udf_cache(*args, **kwargs):
    udf_cache.reset()


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
        self.populate_previous_state()

        self.dirty_collection_udfs = False

    def fields_were_updated(self):
        normal_fields = super(UDFModel, self).fields_were_updated()

        return normal_fields or self.dirty_collection_udfs

    def get_user_defined_fields(self):
        return udf_cache.get_defs_for_model(
            self._model_name, self.instance_id)

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
            self.instance, [self.pk], self.collection_udfs_audit_names())

    @staticmethod
    def static_collection_udfs_audit_ids(instance, pks, audit_names):
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
        return Audit.objects.filter(instance=instance)\
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
        base_model_dict = super(UDFModel, self).as_dict(*args, **kwargs)

        for field in self.scalar_udf_field_names:
            base_model_dict['udf:' + field] = self.udfs[field]

        return base_model_dict

    def save_with_user(self, user, *args, **kwargs):
        """
        Saving a UDF model now involves saving all of collection-based
        udf fields, we do this here. They are validated in
        "clean_collection_udfs"
        """
        # We may need to get a primary key here before we continue
        super(UDFModel, self).save_with_user(user, *args, **kwargs)

        collection_values = self.udfs.collection_fields

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

                udcv.data = value_dict
                udcv.save_with_user(user)

                ids_specified.append(udcv.pk)

            # Delete all values that weren't presented here
            field.userdefinedcollectionvalue_set\
                 .filter(model_id=self.pk)\
                 .exclude(id__in=ids_specified)\
                 .delete()

        self.dirty_collection_udfs = False

    def clean_udfs(self):
        errors = {}

        scalar_fields = {field.name: field
                         for field in self.get_user_defined_fields()
                         if not field.iscollection}

        collection_fields = {field.name: field
                             for field in self.get_user_defined_fields()
                             if field.iscollection}

        # Clean scalar udfs
        for (key, val) in self.udfs.iteritems():
            field = scalar_fields.get(key, None)
            if field:
                try:
                    field.clean_value(val)
                except ValidationError as e:
                    errors['udf:%s' % key] = e.messages
            else:
                errors['udf:%s' % key] = trans(
                    'Invalid user defined field name')

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
                    errors['udf:%s' % collection_field_name] = trans(
                        'Invalid user defined field name')

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


class UDFWhereNode(GeoWhereNode):
    """
    This class allows us to write the where clauses for a
    query that looks something like:

    Plot.objects.filter(**{'udf:Plant Date': datetime(2000,1,2)})

    And transforms it into SQL looking something like:

    ("treemap_plot"."udfs"->'Plant Date')::timestamp ==
    '2000-01-02'::timestamp

    """

    def get_udf_if_field_is_udf(self, field):
        """
        Since the field system is mostly stateless we would normally
        lose the actual udf info rather quickly. To prevent this
        we store the udf as a tuple with the first element being a
        marker. The last element may optionally be a sql datatype:

        ('udf', 'Plant Date', 'timestamp')
        ('udf', 'Nickname')

        If the input field matches the spec a tuple of:

        (field name, datatype)

        ...will be returned (where datatype may be empty, but will
        not None)
        """
        try:
            udfmarker, udffield = field[:2]
            datatype = field[2] if len(field) is 3 else ''

            if udfmarker == 'udf':
                return (udffield, datatype)
        except:
            pass

        return None

    def sql_for_columns(self, lvalue, qn, connection):
        """
        Most of the interesting stuff happens here. In particular,
        this method checks if the field is a udf, and if so
        does the transformation described above (in docs for UDFWhereNode)
        """
        udffield = self.get_udf_if_field_is_udf(lvalue[1])

        if udffield:
            udffieldname, datatype = udffield

            # Update the field to the concrete data field
            # and force the type to 'hstore', just in case
            udf_field_def = (lvalue[0], 'udfs', 'hstore')

            # Apply normal quoting and alias rules
            field = super(UDFWhereNode, self).sql_for_columns(
                udf_field_def, qn, connection)

            # If a datatype can in, apply it as a cast
            if datatype:
                datatype = '::' + datatype

            accessor = ("(%s->'%s')%s" %
                        (field, quotesingle(udffieldname), datatype))

            return accessor
        else:
            return super(UDFWhereNode, self)\
                .sql_for_columns(lvalue, qn, connection)

    def udf_sql_type(self, thing):
        """
        Attempt to convert a python value into a sql
        equivalent
        """
        if isinstance(thing, datetime):
            return 'timestamp'
        elif isinstance(thing, (int, long)):
            return 'integer'
        elif isinstance(thing, float):
            return 'numeric'
        else:
            return ''

    def make_atom(self, child, qn, connection):
        """
        Add type information to udf definitions

        Since we don't have much info about UDFs (besides the name)
        we try to tease out the datatype by looking at the
        target value (i.e. filter(field=value), looking at value)

        Since there isn't a good way to pass the datatype that we
        slurped up, it is appended to the field definition.
        """
        constraint, lookup, _, param_or_value = child

        # Note that 'isnull' means that `param_or_value` will always
        # be boolean (True, False). If this is the case, we don't
        # want to update the datatype
        if ((self.get_udf_if_field_is_udf(constraint.col) and
             lookup != 'isnull')):
            constraint.col += (self.udf_sql_type(param_or_value), )

        return super(UDFWhereNode, self).make_atom(child, qn, connection)

UDF_ORDER_PATTERN = re.compile(r'(-?)([a-zA-Z]+)\.udf\:(.+)$')


class UDFQuery(GeoQuery):
    """
    UDF Query encapsulates query compilation changes. In particular,
    it injects UDFWhereNode as the default WhereNode type (which can
    not be overwritten)
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


class UDFQuerySet(models.query.GeoQuerySet):
    """
    A query set that supports udf-based filter queries

    This class exists mainly to provide an injection point
    for UDFQuery
    """
    def __init__(self, model=None, query=None, using=None):
        super(UDFQuerySet, self).__init__(
            model=model, query=query, using=using)
        self.query = query or UDFQuery(model)


class GeoHStoreUDFQuerySet(HStoreQueryset, UDFQuerySet):
    """
    Merges hstore with the UDFQuerySet which includes the standard
    GeoQuerySet
    """
    pass


class GeoHStoreUDFManager(models.GeoManager, HStoreManager):
    """
    Merges the normal geo manager with the hstore manager backend
    """
    def get_query_set(self):
        return GeoHStoreUDFQuerySet(self.model, using=self._db)
