from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
from datetime import datetime

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from django.contrib.gis.db import models

from djorm_hstore.fields import DictionaryField, HStoreDictionary
from djorm_hstore.models import HStoreManager, HStoreQueryset

from treemap.instance import Instance
from treemap.audit import UserTrackable


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

    All types allow a 'description' key:

    'description' - A text description of the field

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

        # All of our models live in 'treemap.models', so
        # we can start with that namespace
        models_module = __import__('treemap.models')

        if not hasattr(models_module.models, model_type):
            raise ValidationError(_('invalid model type'))

        model_class = getattr(models_module.models, model_type)

        # It must have be a UDF subclass
        if not isinstance(model_class(), UDFModel):
            raise ValidationError(_('invalid model type - must subclass '
                                    'UDFModel'))

        field_names = [field.name for field in model_class._meta.fields]

        if self.name in field_names:
            raise ValidationError(_('cannot use fields that already '
                                    'exist on the model'))

        existing_objects = UserDefinedFieldDefinition.objects.filter(
            model_type=model_type,
            name=self.name)

        if existing_objects.count() != 0:
            raise ValidationError(_('a field already exists on this model '
                                    'with that name'))

        datatype = self.datatype_dict

        if 'type' not in datatype:
            raise ValidationError(_('type required data type definition'))

        if datatype['type'] not in ['float', 'int', 'string',
                                    'user', 'choice', 'date']:
            raise ValidationError(_('invalid datatype'))

        if datatype['type'] == 'choice':
            choices = datatype.get('choices', None)

            if choices is None:
                raise ValidationError(_('missing choices key for key'))

            if len(choices) == 0:
                raise ValidationError(_('empty choice list'))

    def save(self, *args, **kwargs):
        self.validate()
        super(UserDefinedFieldDefinition, self).save(*args, **kwargs)

    @property
    def datatype_dict(self):
        return json.loads(self.datatype)

    def from_string_to_python(self, value):
        """
        Given a value for this data type, validate and return the
        correct python/django representation.

        For instance, this is a 'user' field this function will take
        in a user id (as a string) from the UDF dictionary and return
        a 'User' object.

        If that user doesn't exist a ValidationError will be raised
        """
        from treemap.models import User  # Circular ref issue

        if self.datatype_dict['type'] == 'float':
            try:
                return float(value)
            except ValueError:
                raise ValidationError(_('%(fieldname)s '
                                        'must be a real number') %
                                      {'fieldname': self.name})
        elif self.datatype_dict['type'] == 'int':
            try:
                return int(value)
            except ValueError:
                raise ValidationError(_('%(fieldname)s '
                                        'must be an integer') %
                                      {'fieldname': self.name})
        elif self.datatype_dict['type'] == 'user':
            return User.objects.get(pk=value)
        elif self.datatype_dict['type'] == 'date':
            return datetime.strptime(value, '%Y%m%d%H%M%S')
        elif self.datatype_dict['type'] == 'choice':
            if value in self.datatype_dict['choices']:
                return value
            else:
                raise ValidationError(_('Invalid choice'))
        else:
            return value

    def from_python_to_string(self, value):
        """
        Given a value for this data type, return a string representation
        to be stored in the hstore.
        """
        from treemap.models import User  # Circular ref issue

        # We only support scalar UDFs right now
        # so we can just grab the first one
        if self.datatype_dict['type'] == 'user':
            if isinstance(value, User):
                return str(value.pk)
            else:
                raise ValidationError(_('Expected a User object'))
        elif self.datatype_dict['type'] == 'date':
            return value.strftime('%Y%m%d%H%M%S')
        else:
            return str(value)


class UDFDictionary(HStoreDictionary):

    def __init__(self, value, field, obj, *args, **kwargs):
        super(UDFDictionary, self).__init__(value, field, *args, **kwargs)
        self.model = field.model
        self.instance = obj

        self._fields = None

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
        if super(UDFDictionary, self).__contains__(key):
            return udf.from_string_to_python(
                super(UDFDictionary, self).__getitem__(key))
        else:
            return None

    def __setitem__(self, key, val):
        udf = self._get_udf_or_error(key)
        val = udf.from_python_to_string(val)
        super(UDFDictionary, self).__setitem__(key, val)

    def raw_items(self):
        "Get iterable string key, values"
        return super(UDFDictionary, self).iteritems()

    def set_raw(self, key, val):
        "Set a key to a string value without conversion"
        super(UDFDictionary, self).__setitem__(key, val)


class UDFField(DictionaryField):

    _attribute_class = UDFDictionary

    # Overriden because we do our own string transformations
    # directly via the UDFDictionary
    def get_prep_value(self, data):
        return data


from south.modelsinspector import add_introspection_rules
add_introspection_rules([], ["^treemap\.udf\.UDFField"])


class UDFModel(UserTrackable, models.Model):
    """
    Classes that extend this model gain support for scalar UDF
    fields via the `udf_scalar_values` field.

    This model works correctly with the Auditable and
    Authorizable mixins
    """

    udf_scalar_values = UDFField(db_index=True, blank=True)

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super(UDFModel, self).__init__(*args, **kwargs)

        self._do_not_track = ['udf_scalar_values']

    def get_user_defined_fields(self):
        return UserDefinedFieldDefinition.objects.filter(
            instance=self.instance,
            model_type=self._model_name)

    def apply_change(self, key, oldval):
        if key in self.udf_field_names:
            self.udf_scalar_values.set_raw(key, oldval)
        else:
            super(UDFModel, self).apply_change(key, oldval)

    @property
    def udf_field_names(self):
        return [field.name for field in self.get_user_defined_fields()]

    def as_dict(self, *args, **kwargs):
        base_model_dict = super(UDFModel, self).as_dict(*args, **kwargs)

        for (name, val) in self.udf_scalar_values.raw_items():
            base_model_dict[name] = val

        return base_model_dict


class GeoHStoreQuerySet(models.query.GeoQuerySet, HStoreQueryset):
    pass


class GeoHStoreManager(models.GeoManager, HStoreManager):

    def get_query_set(self):
        return GeoHStoreQuerySet(self.model, using=self._db)
