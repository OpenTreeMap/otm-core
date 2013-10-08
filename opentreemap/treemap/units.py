from django.utils.translation import ugettext as trans

_unit_names = {
    "in":  trans("inches"),
    "ft":  trans("feet"),
    "cm":  trans("centimeters"),
    "m":   trans("meters"),
    "lbs": trans("pounds"),
    "kg":  trans("kilograms"),
    "kwh": trans("kilowatt-hours"),
    "gal": trans("gallons"),
    "L":   trans("liters")
}

_unit_conversions = {
    "in": {"in": 1, "ft": .083333333, "cm": 2.54, "m": .0254},
    "ft": {"in": 12, "ft": 1, "cm": 2.54, "m": 30.48},
    "lbs": {"lbs": 1, "kg": 0.453592},
    "gal": {"gal": 1, "L": 3.785},
    "kwh": {"kwh": 1}
}


def get_unit_name(abbrev):
    if abbrev in _unit_names:
        return _unit_names[abbrev]
    else:
        raise Exception("Unexpected unit abbrev: " + abbrev)


def get_convertible_units(abbrev):
    if abbrev in _unit_conversions:
        return _unit_conversions[abbrev].keys()
    else:
        raise Exception("Unexpected unit abbrev: " + abbrev)
