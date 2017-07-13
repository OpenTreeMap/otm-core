# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import copy

from functools import partial
from numbers import Number

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.formats import number_format

from treemap.json_field import get_attr_from_json_field
from treemap.DotDict import DotDict


class Convertible(object):

    def __init__(self, *args, **kwargs):
        self.unit_status = 'db'
        super(Convertible, self).__init__(*args, **kwargs)

    @classmethod
    def terminology(cls, instance=None):
        terms = copy.copy(cls._terminology)
        if instance:
            terms.update(instance.config
                         .get('terms', {})
                         .get(cls.__name__, {}))
        return terms

    @classmethod
    def display_name(cls, instance):
        return cls.terminology(instance)['singular']

    def _mutate_convertable_fields(self, f):
        from treemap.util import to_object_name
        # note that `to_object_name` is a helper function we use
        # for lowerCamelCase, but `._meta.object_name` is a django
        # internal that is represented as UpperCamelCase.
        model = to_object_name(self._meta.object_name)
        for field in self._meta.get_fields():
            if self.instance and is_convertible(model, field.name):
                value = getattr(self, field.name)

                try:
                    value = float(value)
                except Exception:
                    # These will be caught later in the cleaning process
                    pass

                converted_value = f(self.instance, model, field.name, value)

                setattr(self, field.name, converted_value)

    def convert_to_display_units(self):
        if self.unit_status != 'display':
            self.unit_status = 'display'

            self._mutate_convertable_fields(convert_storage_to_instance_units)

    def convert_to_database_units(self):
        self.clean()

        if self.unit_status != 'db':
            self.unit_status = 'db'
            self._mutate_convertable_fields(get_storage_value)


_unit_names = {
    "in": _("inches"),
    "ft": _("feet"),
    "cm": _("centimeters"),
    "m": _("meters"),
    "lbs/year": _("pounds per year"),
    "kg/year": _("kilograms per year"),
    "lbs": _("pounds"),
    "kg": _("kilograms"),
    "kwh/year": _("kilowatt-hours per year"),
    "gal": _("gallons"),
    "gal/year": _("gallons per year"),
    "L": _("liters"),
    "L/year": _("liters per year"),
    "sq_ft": _("feet²"),
    "sq_m": _("meters²")
}

_unit_abbreviations = {
    # Translators: "in" is an abbreviation for "inches"
    "in": _("in"),
    # Translators: "ft" is an abbreviation for "feet"
    "ft": _("ft"),
    # Translators: "cm" is an abbreviation for "centimeters"
    "cm": _("cm"),
    # Translators: "m" is an abbreviation for "meters"
    "m": _("m"),
    # Translators: "lbs/year" is an abbreviation for "pounds per year"
    "lbs/year": _("lbs/year"),
    # Translators: "kg/year" is an abbreviation for "kilograms per year"
    "kg/year": _("kg/year"),
    # Translators: "lbs" is an abbreviation for "pounds"
    "lbs": _("lbs"),
    # Translators: "kg" is an abbreviation for "kilograms"
    "kg": _("kg"),
    # Translators: "kwh/year" is an abbreviation for "kilowatt-hours per year"
    "kwh/year": _("kwh/year"),
    # Translators: "gal" is an abbreviation for "gallons"
    "gal": _("gal"),
    # Translators: "gal/year" is an abbreviation for "gallons per year"
    "gal/year": _("gal/year"),
    # Translators: "L" is an abbreviation for "liters"
    "L": _("L"),
    # Translators: "L/year" is an abbreviation for "liters per year"
    "L/year": _("L/year"),
    # Translators: "ft²" is an abbreviation for "square feet"
    "sq_ft": _("ft²"),
    # Translators: "m²" is an abbreviation for "square meters"
    "sq_m": _("m²")
}

_unit_conversions = {
    "in": {"in": 1, "ft": 1 / 12, "cm": 2.54, "m": .0254},
    "lbs/year": {"lbs/year": 1, "kg/year": 0.453592},
    "lbs": {"lbs": 1, "kg": 0.453592},
    "gal": {"gal": 1, "L": 3.785},
    "gal/year": {"gal/year": 1, "L/year": 3.785},
    "kwh/year": {"kwh/year": 1},
    "sq_m": {"sq_m": 1, "sq_ft": 10.7639}
}
_unit_conversions["ft"] = {u: v * 12 for (u, v)
                           in _unit_conversions["in"].iteritems()}
_unit_conversions["sq_ft"] = {
    u: v / _unit_conversions["sq_m"]["sq_ft"]
    for u, v in _unit_conversions["sq_m"].iteritems()}


def get_unit_name(abbrev):
    return _unit_names[abbrev]


def get_unit_abbreviation(abbrev):
    return _unit_abbreviations[abbrev]


def get_convertible_units(category_name, value_name):
    abbrev = _get_display_default(category_name, value_name, 'units')
    return _unit_conversions[abbrev].keys()


def _get_display_default(category_name, value_name, key):
    from treemap.ecobenefits import BenefitCategory
    defaults = settings.DISPLAY_DEFAULTS
    if category_name == 'eco' and value_name not in BenefitCategory.GROUPS:
        raise Exception('%s not in %s' % (value_name, BenefitCategory.GROUPS))
    return defaults[category_name][value_name][key]


def _get_storage_units(category_name, value_name):
    # We may specify a storage unit separately from display units
    # We do this for area, since GEOS returns m² but we want to display ft²
    # If there are no storage units specified, use the display units
    storage_defaults = DotDict(settings.STORAGE_UNITS)
    return storage_defaults.get(
        category_name + '.' + value_name,
        default=_get_display_default(category_name, value_name, 'units'))


def get_value_display_attr(instance, category_name, value_name, key):
    if not instance:
        raise Exception("Need an instance to format value %s.%s"
                        % (category_name, value_name))
    # 'key' is 'units' or 'digits'
    # Make e.g. 'config.value_display.plot.width.units'
    field_name = 'config.value_display.%s.%s.%s' \
                 % (category_name, value_name, key)
    # Get value from instance.config, or from defaults if not set
    value = get_attr_from_json_field(instance, field_name) \
        or _get_display_default(category_name, value_name, key)
    identifier = 'instance.' + field_name
    return identifier, value


def get_units_if_convertible(instance, category_name, value_name):
    if is_convertible(category_name, value_name):
        return get_units(instance, category_name, value_name)
    else:
        return ''


def get_digits_if_formattable(instance, category_name, value_name):
    if is_formattable(category_name, value_name):
        return get_digits(instance, category_name, value_name)
    else:
        return ''


def get_units(instance, category_name, value_name):
    __, units = get_value_display_attr(
        instance, category_name, value_name, 'units')
    return units


def get_digits(instance, category_name, value_name):
    __, digits = get_value_display_attr(
        instance, category_name, value_name, 'digits')
    return digits


def _is_configured_for(keys, category_name, value_name):
    defaults = settings.DISPLAY_DEFAULTS
    return (category_name in defaults
            and value_name in defaults[category_name]
            and keys & defaults[category_name][value_name].viewkeys())


is_convertible_or_formattable = partial(_is_configured_for,
                                        {'units', 'digits'})

is_convertible = partial(_is_configured_for, {'units'})

is_formattable = partial(_is_configured_for, {'digits'})


def storage_to_instance_units_factor(instance, category_name, value_name):
    """
    Return conversion factor from OTM storage units to instance's preferred
    units. Returned factor is the number of instance units per storage unit.
    """
    storage_unit = _get_storage_units(category_name, value_name)
    instance_unit = get_units(instance, category_name, value_name)
    conversion_dict = _unit_conversions.get(storage_unit)

    if instance_unit not in conversion_dict.keys():
        raise Exception("Cannot convert from [%s] to [%s]"
                        % (storage_unit, instance_unit))

    return conversion_dict[instance_unit]


def convert_storage_to_instance_units(instance, category_name, value_name,
                                      value):
    """
    Convert given value from storage units to instance units.
    """
    if isinstance(value, Number) and \
       is_convertible(category_name, value_name):
        conversion_factor = storage_to_instance_units_factor(
            instance, category_name, value_name)

        return value * conversion_factor
    else:
        return value


def get_display_value(instance, category_name, value_name, value, digits=None):
    if not isinstance(value, Number):
        return value, value

    converted_value = convert_storage_to_instance_units(
        instance, category_name, value_name, value)

    if digits is None:
        if is_formattable(category_name, value_name):
            digits = int(get_digits(instance, category_name, value_name))
        else:
            digits = 1

    rounded_value = round(converted_value, digits)

    return converted_value, number_format(rounded_value, decimal_pos=digits)


def format_value(instance, category_name, value_name, value):
    if is_formattable(category_name, value_name):
        digits = int(get_digits(instance, category_name, value_name))
    else:
        digits = 1

    rounded_value = round(value, digits)

    return number_format(rounded_value, decimal_pos=digits)


def get_storage_value(instance, category_name, value_name, value):
    if not isinstance(value, Number):
        return value
    return value / storage_to_instance_units_factor(instance, category_name,
                                                    value_name)
