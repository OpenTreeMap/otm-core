from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
import re
from datetime import datetime

from django.core.exceptions import ValidationError, FieldError
from django.utils.translation import ugettext_lazy as _

from django.contrib.gis.db import models

from djorm_hstore.fields import DictionaryField, HStoreDictionary
from djorm_hstore.models import HStoreManager, HStoreQueryset

from treemap.instance import Instance
from treemap.audit import UserTrackable

from django.db.models.base import ModelBase
from django.db.models.sql.constants import ORDER_PATTERN

from django.contrib.gis.db.models.sql.where import GeoWhereNode
from django.contrib.gis.db.models.sql.query import GeoQuery


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
    # All of our models live in 'treemap.models', so
    # we can start with that namespace
    models_module = __import__('treemap.models')

    if not hasattr(models_module.models, model_string):
        raise ValidationError(_('invalid model type'))

    model_class = getattr(models_module.models, model_string)

    # It must have be a UDF subclass
    if not isinstance(model_class(), UDFModel):
        raise ValidationError(_('invalid model type - must subclass '
                                'UDFModel'))

    return model_class

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


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

        model_class = safe_get_udf_model_class(model_type)

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
            return datetime.strptime(value, DATETIME_FORMAT)
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
            return value.strftime(DATETIME_FORMAT)
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

    def create_proxy_field(self, name):
        f = UDFField()
        f.column = ('udf', name)
        setattr(f, 'model', None)
        return f


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
                    field, model, direct, m2m = orig('udf_scalar_values')
                    field = field.create_proxy_field(udfname)
                    return (field, model, direct, m2m)
                else:
                    raise

        setattr(new._meta, 'get_field_by_name', get_field_by_name)
        return new


class UDFModel(UserTrackable, models.Model):
    """
    Classes that extend this model gain support for scalar UDF
    fields via the `udf_scalar_values` field.

    This model works correctly with the Auditable and
    Authorizable mixins
    """

    __metaclass__ = UDFModelBase
    udf_scalar_values = UDFField(db_index=True, blank=True)

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super(UDFModel, self).__init__(*args, **kwargs)

        self._do_not_track.add('udf_scalar_values')

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


def quotesingle(string):
    "Quote a string with ' characters, replacing them with ''"
    return string.replace("'", "''")


class UDFWhereNode(GeoWhereNode):
    """
    This class allows us to write the where clauses for a
    query that looks something like:

    Plot.objects.filter(**{'udf:Plant Date': datetime(2000,1,2)})

    And transforms it into SQL looking something like:

    ("treemap_plot"."udf_scalar_values"->'Plant Date')::timestamp ==
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
            udf_field_def = (lvalue[0], 'udf_scalar_values', 'hstore')

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

            accessor = ("%s%s.udf_scalar_values->'%s'" %
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


class GeoHStoreManager(models.GeoManager, HStoreManager):
    """
    Merges the normal geo manager with the hstore manager backend
    """
    def get_query_set(self):
        return GeoHStoreUDFQuerySet(self.model, using=self._db)
