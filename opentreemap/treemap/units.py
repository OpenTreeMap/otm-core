from django.conf import settings

from django.utils.translation import ugettext as trans
from treemap.json_field import get_attr_from_json_field


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


def get_float_format(instance, category_name, value_name):
    _, digits = get_value_display_attr(
        instance, category_name, value_name, 'digits')
    fmt = '%.' + str(digits) + 'f'
    return digits, fmt
