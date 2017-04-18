# -*- coding: utf-8 -*-
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils.translation import ugettext as _

from opentreemap.context_processors import REPLACEABLE_TERMS
from opentreemap.util import json_from_request, dotted_split

from treemap.json_field import (get_attr_from_json_field,
                                set_attr_on_json_field)
from treemap.models import Plot, MapFeature
from treemap.util import package_field_errors, leaf_models_of_class
from treemap.units import get_units, get_display_value, get_storage_value


def _get_replaceable_models(instance):
    all_classes = leaf_models_of_class(MapFeature) - {Plot}
    root_classes = {Cls for Cls in all_classes
                    if not Cls.__name__.endswith('LA')}
    la_classes = {Cls for Cls in all_classes
                  if Cls.__name__.endswith('LA')}
    if instance.url_name == 'latreemap':
        classes = la_classes | {Cls for Cls in root_classes
                                if not
                                {LACls for LACls in la_classes
                                 if LACls.__name__.startswith(Cls.__name__)}}
    else:
        classes = root_classes

    return sorted(classes, key=lambda Cls: Cls.terminology()['singular'])


def site_config_green_infrastructure(request, instance):
    def _get_form_fields(defaults, thing):
        form_fields = []
        for form in ('singular', 'plural'):
            term_getter = 'terms.%s.%s' % (thing, form)
            val = instance.config.get(term_getter, defaults.get(form))
            form_fields.append({
                'display_value': val,
                'value': val,
                'data_type': 'text',
                'identifier': 'instance.config.%s' % term_getter,
            })
        return form_fields

    terminology_fields = {thing: _get_form_fields(defaults, thing)
                          for thing, defaults in REPLACEABLE_TERMS.items()}

    __, annual_rainfall_display_value = get_display_value(
        instance, 'greenInfrastructure', 'rainfall',
        instance.annual_rainfall_inches)
    annual_rainfall_fields = [(
        _('Annual Rainfall'),
        {
            'identifier': 'instance.config.annual_rainfall_inches',
            'data_type': 'float',
            'display_value': annual_rainfall_display_value,
            'value': annual_rainfall_display_value
        },
        get_units(instance, 'greenInfrastructure', 'rainfall'))]

    customizable_models = _get_replaceable_models(instance)

    gsi_model_fields = []
    for Cls in customizable_models:
        thing = Cls.__name__
        defaults = Cls.terminology()
        config = Cls.get_config(instance)

        gsi_model = {'label': defaults.get('singular', thing),
                     'model_name': thing,
                     'checked': thing in instance.map_feature_types,
                     'fields': _get_form_fields(defaults, thing),
                     'is_la_model': thing.lower().endswith('la')}
        gsi_model['diversion_rate'], gsi_model['diversion_rate_applies'] = \
            _get_diversion_rate_for_display(config)
        (gsi_model['should_show_eco'], gsi_model['should_show_eco_applies'],
         gsi_model['should_show_eco_indicator']) = \
            _get_should_show_eco(config)

        gsi_model_fields.append(gsi_model)

    return {
        'instance': instance,
        'terminology_fields': terminology_fields,
        'annual_rainfall_fields': annual_rainfall_fields,
        'gsi_model_fields': gsi_model_fields,
    }


def _get_diversion_rate_for_display(config):
    diversion_rate = config.get('diversion_rate')
    diversion_rate_applies = diversion_rate is not None
    if not diversion_rate_applies:
        diversion_rate = _('not applicable')
    return diversion_rate, diversion_rate_applies


def _get_should_show_eco(config):
    should_show_eco = config.get('should_show_eco')
    should_show_eco_applies = should_show_eco is not None
    should_show_eco_indicator = ''
    if not should_show_eco_applies:
        should_show_eco_indicator = _('not applicable')
    return should_show_eco, should_show_eco_applies, should_show_eco_indicator


def _map_feature_config_validator(field_name, value, instance):
    acceptable_terms = [
        Cls.__name__ for Cls in _get_replaceable_models(instance)]

    __, __, term, key = dotted_split(field_name, 4, maxsplit=3)
    field_name_valid = (term in acceptable_terms and
                        key in ('should_show_eco', 'diversion_rate'))
    if not field_name_valid:
        return [_("An invalid key was sent in the request")]

    plural = get_attr_from_json_field(instance, 'config.terms.{}.plural'
                                      .format(term))

    if key == 'should_show_eco':
        if term == 'RainBarrel':
            return [_("Showing Ecobenefits is not applicable to {RainBarrels}")
                    .format(RainBarrels=plural)]
    elif key == 'diversion_rate':
        if term == 'RainBarrel':
            return [_(
                "The runoff coefficient is not applicable to {RainBarrels}")
                .format(RainBarrels=plural)]
        error_message = ("Please enter a number between 0 and 1 "
                         "for the runoff coefficient")

        if value is None or value == '':
            return [_(error_message)]

        try:
            float_value = float(value)
        except ValueError:
            return [_(error_message)]

        if not 0.0 <= float_value <= 1.0:
            return [_(error_message)]

    return None


def _map_feature_cross_validator(field_name, value, instance):
    __, __, model_name, setting = dotted_split(field_name, 4, maxsplit=3)
    Classes = _get_replaceable_models(instance)
    Cls = next(Cls for Cls in Classes if Cls.__name__ == model_name)
    config = Cls.get_config(instance)

    if setting == 'should_show_eco':
        value = config.get(setting)
        if value:
            rainfall_inches = instance.annual_rainfall_inches
            if rainfall_inches is None or rainfall_inches == '':
                return [_("Ecobenefits cannot be calculated unless "
                          "annual rainfall is given")]
            diversion_rate = config.get('diversion_rate')
            if diversion_rate is None or diversion_rate == '':
                return [_("Ecobenefits cannot be calculated unless "
                          "a runoff coefficient is given")]


def _terminology_validator(field_name, value, instance):
    acceptable_terms = REPLACEABLE_TERMS.keys() + [
        Cls.__name__ for Cls in _get_replaceable_models(instance)]

    __, terms, term, form = dotted_split(field_name, 4, maxsplit=3)
    field_name_valid = (terms == 'terms' and
                        term in acceptable_terms and
                        form in ('singular', 'plural'))
    if not field_name_valid:
        return [_("An invalid key was sent in the request")]

    if term == 'Resource' and len(value) > 20:
        return [_('Please limit replacement text to 20 characters.')]

    return None


def _annual_rainfall_validator(value):
    INVALID_RAINFALL_MESSAGE = _(
        "Please enter a positive number for annual rainfall")
    if value is None or value == "":
        return [INVALID_RAINFALL_MESSAGE]

    try:
        rainfall_inches = float(value)
    except ValueError:
        return [INVALID_RAINFALL_MESSAGE]

    if rainfall_inches < 0.0:
        return [INVALID_RAINFALL_MESSAGE]

    return None


def _set_annual_rainfall(value, instance):
    value = get_storage_value(instance, 'greenInfrastructure', 'rainfall',
                              float(value))
    instance.annual_rainfall_inches = value


def _set_map_feature_config(field_name, value, instance):
    __, __, model_name, setting = dotted_split(field_name, 4, maxsplit=3)
    Classes = _get_replaceable_models(instance)
    Cls = next(Cls for Cls in Classes if Cls.__name__ == model_name)
    if setting == 'diversion_rate':
        value = float(value)
    elif setting == 'should_show_eco':
        value = bool(value)
    Cls.set_config_property(instance, setting, value, save=False)


# mutates error_dict
def _validate_and_set_individual_values(json_data, instance, error_dict):
    errors = None
    INVALID_KEY_MESSAGE = _("An invalid key was sent in the request")
    for identifier, value in json_data.iteritems():
        if not '.' in identifier:
            error_dict[identifier] = [INVALID_KEY_MESSAGE]
        __, field_name = dotted_split(identifier, 2, maxsplit=1)

        if not identifier.startswith('instance.config.'):
            error_dict[field_name] = [INVALID_KEY_MESSAGE]
            continue

        if field_name == 'config.annual_rainfall_inches':
            errors = _annual_rainfall_validator(value)
            if errors is None:
                _set_annual_rainfall(value, instance)
        elif field_name.startswith('config.map_feature_config'):
            errors = _map_feature_config_validator(field_name, value,
                                                   instance)
            if errors is None:
                _set_map_feature_config(field_name, value, instance)
        elif field_name.startswith('config.terms'):
            errors = _terminology_validator(field_name, value, instance)
            if errors is None:
                set_attr_on_json_field(instance, field_name, value)
        else:
            errors = [INVALID_KEY_MESSAGE]

        if errors is not None:
            error_dict[field_name] = errors


# mutates error_dict
def _cross_validate_values(json_data, instance, error_dict):
    errors = None
    for identifier, value in json_data.iteritems():
        __, field_name = dotted_split(identifier, 2, maxsplit=1)
        if field_name in error_dict:
            continue

        if field_name.startswith('config.map_feature_config'):
            errors = _map_feature_cross_validator(field_name, value, instance)

        if errors is not None:
            error_dict[field_name] = errors


@transaction.atomic
def green_infrastructure(request, instance):
    json_data = json_from_request(request)
    new_data = {}
    increment_universal_rev = False
    for identifier, value in json_data.iteritems():
        model, field_name = dotted_split(identifier, 2, maxsplit=1)
        if field_name.startswith('config.map_feature_types') or \
           field_name.startswith('config.map_feature_config'):
            if not instance.feature_enabled('green_infrastructure'):
                raise PermissionDenied("The Green Infrastructure module is "
                                       "not enabled for this tree map")
            increment_universal_rev = True
        if field_name.startswith('config.map_feature_types'):
            __, __, mft_name = dotted_split(field_name, 3, maxsplit=2)
            if value:
                instance.add_map_feature_types([mft_name])
            else:
                instance.remove_map_feature_types([mft_name])
        else:
            new_data[identifier] = value

    error_dict = {}
    _validate_and_set_individual_values(new_data, instance, error_dict)
    _cross_validate_values(new_data, instance, error_dict)
    if error_dict:
        raise ValidationError(package_field_errors('instance',
                              ValidationError(error_dict)))
    if increment_universal_rev:
        instance.update_universal_rev()
    instance.save()
    return {'ok': True}
