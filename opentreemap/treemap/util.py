# -*- coding: utf-8 -*-


import datetime
from collections import OrderedDict
import json

from urllib.parse import urlparse

from django.apps import apps
from django.shortcuts import get_object_or_404, resolve_url
from django.http import HttpResponse
from django.utils import dateformat
from django.utils.encoding import force_str
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.conf import settings
from django.core.exceptions import ValidationError, MultipleObjectsReturned, ObjectDoesNotExist
from django.utils.translation import ugettext_lazy as _

from opentreemap.util import dict_pop, dotted_split
from treemap.json_field import (is_json_field_reference,
                                get_attr_from_json_field)
from treemap.units import (get_digits_if_formattable, get_units_if_convertible,
                           is_convertible_or_formattable, format_value,
                           get_unit_abbreviation)
from treemap.instance import Instance


def safe_get_model_class(model_string):
    """
    In a couple of cases we want to be able to convert a string
    into a valid django model class. For instance, if we have
    'Plot' we want to get the actual class for 'treemap.models.Plot'
    in a safe way.

    This function returns the class represented by the given model
    if it exists in 'treemap.models'
    """
    from treemap.models import MapFeature

    # All of our base models live in 'treemap.models', so
    # we can start with that namespace
    models_module = __import__('treemap.models')

    if hasattr(models_module.models, model_string):
        return getattr(models_module.models, model_string)
    elif MapFeature.has_subclass(model_string):
        return MapFeature.get_subclass(model_string)
    else:
        raise ValidationError(
            _('invalid model type: "%s"') % model_string)


def get_model_for_instance(object_name, instance=None):
    Model = safe_get_model_class(to_model_name(object_name))

    if instance and hasattr(Model, 'instance'):
        return Model(instance=instance)
    else:
        return Model()


def add_visited_instance(request, instance):
    if not (hasattr(request, 'session') and request.session):
        return

    # get the visited instances as a list of tuples, read into
    # OrderedDict. OrderedDict has nice convenience methods for this
    # purpose, but doesn't serialize well, so we pass it through.
    visited_instances = request.session.get('visited_instances', [])
    visited_instances = OrderedDict(visited_instances)

    # delete the existing entry for this instance so it can be
    # reinserted as the most recent entry.
    if instance.pk in visited_instances:
        del visited_instances[instance.pk]

    stamp = datetime.datetime.now().isoformat()
    visited_instances[instance.pk] = stamp

    # turn back into a list of tuples
    request.session['visited_instances'] = list(visited_instances.items())
    request.session.modified = True


def get_last_visited_instance(request):
    if not hasattr(request, 'session'):
        instance = None
    else:
        visited_instances = request.session.get('visited_instances', [])
        if not visited_instances:
            instance = None
        else:
            # get the first tuple member of the last entry
            # visited_instances have entries '(<pk>, <timestamp>)'
            instance_id = visited_instances[-1][0]
            try:
                instance = Instance.objects.get(pk=instance_id)
            except (Instance.DoesNotExist, MultipleObjectsReturned):
                instance = None

    return instance


def get_login_redirect_path(request, resolved_login_url):
    # Reference: django/contrib/auth/decorators.py
    path = request.build_absolute_uri()
    # If the login url is the same scheme and net location then just
    # use the path as the "next" url.
    login_scheme, login_netloc = urlparse(resolved_login_url)[:2]
    current_scheme, current_netloc = urlparse(path)[:2]
    if (not login_scheme or login_scheme == current_scheme)\
    and (not login_netloc or login_netloc == current_netloc):  # NOQA
        path = request.get_full_path()
    return path


def login_redirect(request):
    # urlparse chokes on lazy objects in Python 3, force to str
    resolved_login_url = force_str(
        resolve_url(settings.LOGIN_URL))
    path = get_login_redirect_path(request, resolved_login_url)
    from django.contrib.auth.views import redirect_to_login
    return redirect_to_login(
        path, resolved_login_url, REDIRECT_FIELD_NAME)


def get_instance_or_404(**kwargs):
    url_name, found = dict_pop(kwargs, 'url_name')
    if found:
        kwargs['url_name__iexact'] = url_name
    return get_object_or_404(Instance, **kwargs)


def package_field_errors(model_name, validation_error):
    """
    validation_error contains a dictionary of error messages of the form
    {fieldname1: [messages], fieldname2: [messages]}.
    Return a version keyed by "objectname.fieldname" instead of "fieldname".
    """
    dict = {'%s.%s' % (to_object_name(model_name), field): msgs
            for (field, msgs) in validation_error.message_dict.items()}

    return dict


def _all_subclasses(cls):
    subclasses = set(cls.__subclasses__())
    return subclasses | {clz for s in subclasses for clz in _all_subclasses(s)}


def all_models_of_class(cls):
    """Return all Django models which are subclasses of given class"""
    # During unit tests many of the subclasses we see will be historical models
    # created by the migration system
    # We only look at subclasses of real Django models in order to exclude them
    all_models = set(apps.get_models())
    return all_models & _all_subclasses(cls)


def leaf_models_of_class(cls):
    """Return all Django models which are leaf subclasses of given class"""
    all = all_models_of_class(cls)
    leaves = {s for s in all if not s.__subclasses__()}
    return leaves


def to_object_name(model_name):
    """BenefitCurrencyConversion -> benefitCurrencyConversion

    works idempotently, eg:
    benefitCurrencyConversion -> benefitCurrencyConversion
    """
    return model_name[0].lower() + model_name[1:]


def to_model_name(object_name):
    """benefitCurrencyConversion -> BenefitCurrencyConversion

    works idempotently, eg:
    BenefitCurrencyConversion -> BenefitCurrencyConversion
    """
    return object_name[0].upper() + object_name[1:]


def get_filterable_audit_models():
    from treemap.models import MapFeature
    map_features = [c.__name__ for c in leaf_models_of_class(MapFeature)]
    models = map_features + ['Tree']

    return models


def get_csv_response(filename):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=%s;' % filename
    response['Cache-Control'] = 'no-cache'

    # add BOM to support CSVs in MS Excel
    # http://en.wikipedia.org/wiki/Byte_order_mark
    response.write('\ufeff'.encode('utf8'))
    return response


def get_json_response(filename):
    response = HttpResponse(content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename=%s;' % filename
    response['Cache-Control'] = 'no-cache'
    return response


def can_read_as_super_admin(request):
    if not hasattr(request.user, 'is_super_admin'):
        return False
    else:
        return request.user.is_super_admin() and request.method == 'GET'


# UDF utilitites

# Utilities for ways in which a UserDefinedFieldDefinition is identified.
# Please also see name related properties on that class.
# Note that audits refer to collection udfds as 'udf:{udfd.pk}',
# but to scalar udfds as 'udf:{udfd.name}', same as FieldPermissions
def get_pk_from_collection_audit_name(name):
    return int(name[4:])


def get_name_from_canonical_name(canonical_name):
    return canonical_name[4:]


def make_udf_name_from_key(key):
    return 'udf:{}'.format(key)


def make_udf_lookup_from_key(key):
    return 'udfs__{}'.format(key)


def num_format(num):
    if isinstance(num, float):
        # Allow for up to 10 digits of precision, but strip trailing '0' or '.'
        return '{0:.10f}'.format(num).rstrip('0').rstrip('.')
    return num


# Field Utilities
FIELD_MAPPINGS = {
    'IntegerField': 'int',
    'ForeignKey': 'foreign_key',
    'OneToOneField': 'int',
    'AutoField': 'int',
    'FloatField': 'float',
    'TextField': 'long_string',
    'CharField': 'string',
    'DateTimeField': 'datetime',
    'DateField': 'date',
    'BooleanField': 'bool',
    'NullBooleanField': 'bool',
    'FileField': 'string',
    'PointField': 'point',
    'MultiPolygonField': 'multipolygon',
}

VALID_FIELD_KEYS = ','.join(FIELD_MAPPINGS.keys())

# Should a blank choice be added for choice and multichoice fields?
ADD_BLANK_ALWAYS = 0
ADD_BLANK_NEVER = 1
ADD_BLANK_IF_CHOICE_FIELD = 2


def field_type_label_choices(model, field_name, label=None,
                             explanation=None,
                             add_blank=ADD_BLANK_IF_CHOICE_FIELD):
    choices = None
    udf_field_name = field_name.replace('udf:', '')
    if not _is_udf(model, udf_field_name):
        field = model._meta.get_field(field_name)
        field_type = field.get_internal_type()
        try:
            field_type = FIELD_MAPPINGS[field_type]
        except KeyError:
            raise Exception('This template tag only supports %s not %s'
                            % (VALID_FIELD_KEYS,
                               field_type))
        label = label if label else field.verbose_name
        explanation = explanation if explanation else field.help_text
        choices = [{'value': choice[0], 'display_value': choice[1]}
                for choice in field.choices or []]
        if choices and field.null:
            choices = [{'value': '', 'display_value': ''}] + choices
    else:
        udf_dict = _udf_dict(model, field_name)
        field_type = udf_dict['type']
        label = label if label else udf_field_name
        if 'choices' in udf_dict:
            choices = [{'value': value, 'display_value': value}
                       for value in udf_dict['choices']]
            if add_blank == ADD_BLANK_ALWAYS or (
                add_blank == ADD_BLANK_IF_CHOICE_FIELD and
                field_type == 'choice'
            ):
                choices.insert(0, {'value': "", 'display_value': ""})

    return field_type, label, explanation, choices

def _get_model(context, object_name, instance=None):
    return context[object_name]

def _is_udf(model, udf_field_name):
    return (hasattr(model, 'udf_field_names') and
            udf_field_name in model.udf_field_names)

def _udf_dict(model, field_name):
    matches = [field.datatype_dict
               for field in model.get_user_defined_fields()
               if field.name == field_name.replace('udf:', '')]
    if matches:
        return matches[0]
    else:
        raise Exception("Datatype for field %s not found" % field_name)


def get_field(context, label, identifier, user, instance,
              explanation=None, treat_multichoice_as_choice=False, model=None):
    is_required = False

    """
    if not isinstance(identifier, basestring)\
        or not _identifier_regex.match(identifier):
        raise template.TemplateSyntaxError(
            'expected a string with the format "object_name.property" '
            'to follow "from" %s' % identifier)
    """

    model_name_or_object_name, field_name = dotted_split(identifier, 2, maxsplit=1)

    if not model:
        model = _get_model(context, model_name_or_object_name, instance)

    object_name = to_object_name(model_name_or_object_name)

    identifier = "%s.%s" % (object_name, field_name)

    def _field_is_required(model, field_name):
        udf_field_name = field_name.replace('udf:', '')
        if _is_udf(model, udf_field_name):
            return udf_field_name in model.udf_required_fields
        return False

    def _field_value(model, field_name, data_type):
        udf_field_name = field_name.replace('udf:', '')
        val = None
        if field_name in [f.name for f in model._meta.get_fields()]:
            try:
                val = getattr(model, field_name)
            except (ObjectDoesNotExist, AttributeError):
                pass
        elif _is_udf(model, udf_field_name):
            if udf_field_name in model.udfs:
                val = model.udfs[udf_field_name]
                # multichoices place a json serialized data-value
                # on the dom element and client-side javascript
                # processes it into a view table and edit widget
                if data_type == 'multichoice':
                    val = json.dumps(val)
            elif data_type == 'multichoice':
                val = '[]'

        else:
            raise ValueError('Could not find field: %s' % field_name)

        return val

    if is_json_field_reference(field_name):
        field_value = get_attr_from_json_field(model, field_name)
        choices = None
        is_visible = is_editable = True
        data_type = "string"
    else:
        add_blank = (ADD_BLANK_ALWAYS if treat_multichoice_as_choice
                        else ADD_BLANK_IF_CHOICE_FIELD)
        data_type, label, explanation, choices = field_type_label_choices(
            model, field_name, label, explanation=explanation,
            add_blank=add_blank)
        is_required = _field_is_required(model, field_name)
        field_value = _field_value(model, field_name, data_type)

        if user is not None and hasattr(model, 'field_is_visible'):
            is_visible = model.field_is_visible(user, field_name)
            is_editable = model.field_is_editable(user, field_name)
        else:
            # This tag can be used without specifying a user. In that case
            # we assume that the content is visible and upstream code is
            # responsible for only showing the content to the appropriate
            # user
            is_visible = True
            is_editable = True

    digits = units = ''

    if hasattr(model, 'instance'):
        digits = get_digits_if_formattable(
            model.instance, object_name, field_name)

        units = get_units_if_convertible(
            model.instance, object_name, field_name)
        if units != '':
            units = get_unit_abbreviation(units)

    if data_type == 'foreign_key':
        # rendered clientside
        display_val = ''
    elif field_value is None:
        display_val = None
    elif data_type in ['date', 'datetime']:
        fmt = (model.instance.short_date_format if model.instance
                else settings.SHORT_DATE_FORMAT)
        display_val = dateformat.format(field_value, fmt)
    elif is_convertible_or_formattable(object_name, field_name):
        display_val = format_value(
            model.instance, object_name, field_name, field_value)
        if units != '':
            display_val += (' %s' % units)
    elif data_type == 'bool':
        display_val = _('Yes') if field_value else _('No')
    elif data_type == 'multichoice':
        # this is rendered clientside from data attributes so
        # there's no meaningful intermediate value to send
        # without rendering the same markup server-side.
        display_val = None
    elif choices:
        display_vals = [choice['display_value'] for choice in choices
                        if choice['value'] == field_value]
        display_val = display_vals[0] if display_vals else field_value
    elif data_type == 'float':
        display_val = num_format(field_value)
    else:
        display_val = str(field_value)

    if hasattr(model, 'REQUIRED_FIELDS'):
        is_required = is_required or field_name in model.REQUIRED_FIELDS

    return {
        'label': label,
        'explanation': explanation,
        'identifier': identifier,
        'value': field_value,
        'display_value': display_val,
        'units': units,
        'digits': digits,
        'data_type': data_type,
        'is_visible': is_visible,
        'is_editable': is_editable,
        'is_required': is_required,
        'choices': choices,
    }
