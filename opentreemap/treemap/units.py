# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from functools import partial
from numbers import Number

from django.conf import settings
from django.utils.translation import ugettext as trans
from django.utils.formats import number_format

from treemap.json_field import get_attr_from_json_field


class Convertible(object):
    def clean(self):
        super(Convertible, self).clean()
        model = self._meta.object_name.lower()
        for field in self._meta.get_all_field_names():
            if self.instance and is_convertible(model, field):
                value = getattr(self, field)
                converted_value = get_storage_value(self.instance, model,
                                                    field, value)
                setattr(self, field, converted_value)


_unit_names = {
    "in":  trans("inches"),
    "ft":  trans("feet"),
    "cm":  trans("centimeters"),
    "m":   trans("meters"),
    "lbs/year": trans("pounds per year"),
    "kg/year":  trans("kilograms per year"),
    "kwh": trans("kilowatt-hours"),
    "gal": trans("gallons"),
    "L":   trans("liters")
}

_unit_conversions = {
    "in": {"in": 1, "ft": .083333333, "cm": 2.54, "m": .0254},
    "ft": {"in": 12, "ft": 1, "cm": 2.54, "m": 30.48},
    "lbs/year": {"lbs/year": 1, "kg/year": 0.453592},
    "gal": {"gal": 1, "L": 3.785},
    "kwh": {"kwh": 1}
}


def get_unit_name(abbrev):
    return _unit_names[abbrev]


def get_convertible_units(category_name, value_name):
    abbrev = _get_display_default(category_name, value_name, 'units')
    return _unit_conversions[abbrev].keys()


def _get_display_default(category_name, value_name, key):
    defaults = settings.DISPLAY_DEFAULTS
    return defaults[category_name][value_name][key]


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


def get_units(instance, category_name, value_name):
    _, units = get_value_display_attr(
        instance, category_name, value_name, 'units')
    return units


def get_digits(instance, category_name, value_name):
    _, digits = get_value_display_attr(
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


def _get_conversion_factor(instance, category_name, value_name):
    storage_unit = _get_display_default(category_name, value_name, 'units')
    instance_unit = get_units(instance, category_name, value_name)
    conversion_dict = _unit_conversions.get(storage_unit)

    if instance_unit not in conversion_dict.keys():
        raise Exception("Cannot convert from [%s] to [%s]"
                        % (storage_unit, instance_unit))

    return conversion_dict[instance_unit]


def get_display_value(instance, category_name, value_name, value):
    if not isinstance(value, Number):
        return value, value
    if is_convertible(category_name, value_name):
        conversion_factor = _get_conversion_factor(instance, category_name,
                                                   value_name)
        converted_value = value * conversion_factor
    else:
        converted_value = value

    if is_formattable(category_name, value_name):
        digits = int(get_digits(instance, category_name, value_name))
    else:
        digits = 1

    rounded_value = round(converted_value, digits)

    return converted_value, number_format(rounded_value, decimal_pos=digits)


def get_storage_value(instance, category_name, value_name, value):
    if not isinstance(value, Number):
        return value
    return value / _get_conversion_factor(instance, category_name,
                                          value_name)
