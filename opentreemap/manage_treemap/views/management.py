# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import locale
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.core.validators import URLValidator, validate_email
from django.shortcuts import redirect
from django.utils.translation import ugettext as _

from manage_treemap.views import update_instance_fields
from manage_treemap.views.photo import get_photos
from opentreemap.util import json_from_request, dotted_split
from otm_comments.views import get_comments
from stormwater.models import Bioswale, RainBarrel, RainGarden
from treemap.ecobenefits import benefit_labels, BenefitCategory
from treemap.images import save_image_from_request
from treemap.lib import COLOR_RE
from treemap.lib.external_link import (get_url_tokens_for_display,
                                       validate_token_template)
from treemap.models import BenefitCurrencyConversion, Plot, Tree
from treemap.units import get_value_display_attr, get_convertible_units, \
    get_unit_name
from treemap.util import package_field_errors


def management_root(request, instance_url_name):
    return redirect('site_config', instance_url_name=instance_url_name)


def admin_counts(request, instance):
    humanize = lambda n: '' if n == 0 else n if n < 100 else '99+'

    comment_count = get_comments({}, instance).count()
    photo_count = get_photos(instance).count()
    udf_notifications = instance.config.get('udf_notifications', [])

    return {
        'admin_notifications': {
            'comments': humanize(comment_count),
            'photos': humanize(photo_count),
            'community': humanize(photo_count + comment_count),
            'udfs': humanize(len(udf_notifications))
        },
        'udf_notifications': udf_notifications
    }


def site_config_basic_info(request, instance):
    info = {
        'url': request.build_absolute_uri(
            settings.SITE_ROOT + instance.url_name),
        'fields': [
            (_('Tree Map Title'), 'instance.name'),
            (_('Publicly Visible'), 'instance.is_public')]}

    info['fields'].append(
        (_('Contact E-Mail'), 'instance.config.linkData.contact'))

    info['fields'].append(
        (_('Tree ID URL'), 'instance.config.linkData.treekey'))

    info['fields'].append(
        (_('Allow Data Exports For Non-Administrators'),
         'instance.non_admins_can_export'))

    return {
        'instance': instance,
        'site_config': info}


def site_config_validator(field_name, value, model_name):
    if model_name != 'instance':
        return [_('Invalid model name, must be a field on instance')]

    if field_name not in {'config.linkData.contact',
                          'config.linkData.treekey',
                          'name',
                          'is_public',
                          'non_admins_can_export'}:
        return [_('Invalid field name')]

    elif field_name == 'config.linkData.treekey':
        try:
            if value and len(value) > 0:
                URLValidator()(value)
        except ValidationError:
            return [_('You must specify a valid url')]

    elif field_name == 'config.linkData.contact':
        try:
            if value and len(value) > 0:
                validate_email(value)
        except ValidationError:
            return [_('You must specify a valid email')]

    return None


def external_link(request, instance):
    return {
        'instance': instance,
        'tokens': get_url_tokens_for_display(True)
    }


def update_external_link(request, instance):

    def validator(field_name, value, model_name):
        if model_name != 'instance':
            return [_('Invalid model name, must be a field on instance')]

        if field_name not in {'config.externalLink.text',
                              'config.externalLink.url'}:
            return [_('Invalid field name')]
        elif field_name == 'config.externalLink.url':
            try:
                if value and len(value) > 0:
                    URLValidator()(value)
            except ValidationError:
                return [_('You must specify a valid url')]

            if not validate_token_template(value):
                return [_('Invalid token, the allowed values are'
                          ': %(list_of_url_tokens)s') %
                        {'list_of_url_tokens': get_url_tokens_for_display()}]

        return None

    data = json_from_request(request)
    url = data.get('instance.config.externalLink.url',
                   instance.config.get('externalLink.url'))
    text = data.get('instance.config.externalLink.text',
                    instance.config.get('externalLink.text'))
    if bool(url) ^ bool(text):
        if text:
            field, other_field = 'url', _('Link Text')
        else:
            field, other_field = 'text', _('Link URL')

        raise ValidationError(
            {'instance.config.externalLink.%s' % field:
             [_("This field is required when %(other_field)s is present") %
              {'other_field': other_field}]})

    return update_instance_fields(request, instance, validator)


def branding(request, instance):
    prefix = 'instance.config.scss_variables.'
    info = {
        'color_fields': [
            (_('Primary Color'), prefix + 'primary-color'),
            (_('Secondary Color'), prefix + 'secondary-color')]
    }
    return {
        'instance': instance,
        'branding': info,
        'logo_endpoint': reverse('logo_endpoint', args=(instance.url_name,))
    }


def branding_validator(field_name, value, model_name):
    if model_name != 'instance':
        return [_('Invalid model name, must be a field on instance')]

    if field_name not in {'config.scss_variables.primary-color',
                          'config.scss_variables.secondary-color'}:

        return [_('Invalid field name')]

    elif not COLOR_RE.match(value):
        return [_('Please enter 3 or 6 digits of 0-9 and/or A-F')]

    return None


def update_logo(request, instance):
    name_prefix = "logo-%s" % instance.url_name
    instance.logo, __ = save_image_from_request(request, name_prefix)
    instance.save()

    return {'url': instance.logo.url}


def embed(request, instance):
    embed_endpoint = reverse('map', args=(instance.url_name,))
    embed_url = request.build_absolute_uri(embed_endpoint)
    iframe = '<iframe src="{}?embed=1" width="%s" height="%s"></iframe>'\
        .format(embed_url)
    wide = {'w': '1280', 'h': '888'}
    standard = {'w': '900', 'h': '600'}
    return {
        'iframe_custom': iframe,
        'iframe_wide': iframe % (wide['w'], wide['h']),
        'iframe_standard': iframe % (standard['w'], standard['h']),
        'iframe_wide_width': wide['w'],
        'iframe_wide_height': wide['h'],
        'iframe_standard_width': standard['w'],
        'iframe_standard_height': standard['h'],
        'iframe_custom_min_width': '768',
        'iframe_custom_min_height': '450',
    }


def benefits_convs(request, instance):
    conv = instance.eco_benefits_conversion or _get_default_conversions()

    field_groups = {
        _('Energy Factors'): {
            _('per kWh of electricity'):
            'benefitCurrencyConversion.electricity_kwh_to_currency',
            _('per kBTU of natural gas'):
            'benefitCurrencyConversion.natural_gas_kbtu_to_currency',
        },
        _('Stormwater Factors'): {
            _('per gallon of stormwater reduced'):
            'benefitCurrencyConversion.h20_gal_to_currency',
        },
        _('CO₂ Factors'): {
            _('per lb of CO₂'):
            'benefitCurrencyConversion.co2_lb_to_currency',
        },
        _('Air Quality Factors'): {
            _('per lb of O₃'):
            'benefitCurrencyConversion.o3_lb_to_currency',
            _('per lb of NOₓ'):
            'benefitCurrencyConversion.nox_lb_to_currency',
            _('per lb of PM10'):
            'benefitCurrencyConversion.pm10_lb_to_currency',
            _('per lb of SOₓ'):
            'benefitCurrencyConversion.sox_lb_to_currency',
            _('per lb of VOC'):
            'benefitCurrencyConversion.voc_lb_to_currency'
        }
    }

    pfx = ('<span class="currency-value">' +
           conv.currency_symbol + '</span> ')

    for group_title, fields in field_groups.iteritems():
        fields_with_pfx = [((pfx + label), value)
                           for label, value in fields.iteritems()]
        field_groups[group_title] = fields_with_pfx

    return {'benefitCurrencyConversion': conv,
            'benefit_fields': field_groups}


def update_benefits(request, instance):
    conv = instance.eco_benefits_conversion or _get_default_conversions()

    valid_fields = ('currency_symbol',
                    'electricity_kwh_to_currency',
                    'natural_gas_kbtu_to_currency',
                    'h20_gal_to_currency',
                    'co2_lb_to_currency',
                    'o3_lb_to_currency',
                    'nox_lb_to_currency',
                    'pm10_lb_to_currency',
                    'sox_lb_to_currency',
                    'voc_lb_to_currency')

    valid_fields = ["benefitCurrencyConversion." + field
                    for field in valid_fields]

    updated_values = json_from_request(request)

    for field, value in updated_values.iteritems():
        if field in valid_fields:
            field_part = dotted_split(field, 2)[1]
            setattr(conv, field_part, value)
        else:
            raise Exception(
                'invalid field specified %s for benefit conversion' % field)

    try:
        conv.save()
    except ValidationError as e:
        raise ValidationError(
            package_field_errors('benefitCurrencyConversion', e))

    instance.eco_benefits_conversion = conv
    instance.update_eco_rev()
    instance.save()

    return {'ok': True}


def _get_default_conversions():
    currency_symbol = locale.localeconv()['currency_symbol'] or '$'
    return BenefitCurrencyConversion(currency_symbol=currency_symbol)


class GreenInfrastructureCategory(object):
    RAINFALL = 'rainfall'
    AREA = 'area'

    GROUPS = (RAINFALL, AREA)


def units(request, instance):
    """
    Build context for "Units" tab, which allows specifying units and number of
    decimal digits for values like plot.width or eco.stormwater.
    For each such value we build a "field spec" for "units" and for "digits",
    which drive the creation of display/edit fields on the tab form.
    """
    value_names = [
        {'title': _("Planting Site Fields"),
         'category_name': 'plot',
         'model': Plot,
         'value_names': ['width', 'length']},
        {'title': _("Tree Fields"),
         'category_name': 'tree',
         'model': Tree,
         'value_names': ['diameter', 'height', 'canopy_height']},
        {'title': _("Eco Benefits"),
         'category_name': 'eco',
         'label_dict': benefit_labels,
         'value_names': BenefitCategory.GROUPS},
        {'title': _("{bioswale} Fields")
         .format(bioswale=Bioswale.display_name(instance)),
         'category_name': 'bioswale',
         'model': Bioswale,
         'value_names': ['drainage_area']},
        {'title': _("{rainBarrel} Fields")
         .format(rainBarrel=RainBarrel.display_name(instance)),
         'category_name': 'rainBarrel',
         'model': RainBarrel,
         'value_names': ['capacity']},
        {'title': _("{rainGarden} Fields")
         .format(rainGarden=RainGarden.display_name(instance)),
         'category_name': 'rainGarden',
         'model': RainGarden,
         'value_names': ['drainage_area']},
        {'title': _("Green Infrastructure"),
         'category_name': 'greenInfrastructure',
         'inclusion_test': lambda:
            instance.feature_enabled('green_infrastructure'),
         'label_dict': {
             GreenInfrastructureCategory.RAINFALL: _('Annual Rainfall'),
             GreenInfrastructureCategory.AREA:     _('Area')
         },
         'value_names': GreenInfrastructureCategory.GROUPS},
    ]

    def get_label_getter(attrs):
        inclusion_test = attrs.get('inclusion_test')
        if inclusion_test:
            if not inclusion_test():
                return None
        Model = attrs.get('model')
        if Model:
            name = Model.__name__
            if name == 'Tree' or name in instance.map_feature_types:
                return lambda value_name: \
                    Model._meta.get_field(value_name).verbose_name
        else:
            label_dict = attrs.get('label_dict')
            if label_dict:
                return label_dict.get
        return None

    specs_by_category = []
    for attrs in value_names:
        get_label = get_label_getter(attrs)
        if not get_label:
            continue
        category_name = attrs['category_name']
        category_specs = []
        for value_name in attrs['value_names']:
            def identifier_and_value(key):
                return get_value_display_attr(
                    instance, category_name, value_name, key)

            label = get_label(value_name)

            # Make a dropdown choice for each unit we can convert to
            abbrevs = get_convertible_units(category_name, value_name)
            choices = [{'value': abbrev,
                        'display_value': get_unit_name(abbrev)}
                       for abbrev in abbrevs]

            # Make field spec for units
            identifier, abbrev = identifier_and_value('units')
            units_field_spec = {
                'identifier': identifier,
                'value': abbrev,
                'display_value': get_unit_name(abbrev),
                'data_type': 'choice',
                'choices': choices
            }

            # Make field spec for number of decimal digits
            identifier, value = identifier_and_value('digits')
            digits_field_spec = {
                'identifier': identifier,
                'value': value,
                'display_value': value
            }

            category_specs.append({
                'label': label,
                'units': units_field_spec,
                'digits': digits_field_spec})

        if category_specs:
            specs_by_category.append({'title': attrs['title'],
                                      'items': category_specs})

    return {'value_specs': specs_by_category}


_unit_re = re.compile(r'config\.value_display\.\w+\.\w+\.(?:units|digits)')


def units_validator(field_name, value, model_name):
    if model_name != 'instance':
        return [_('Invalid model name, must be a field on instance')]

    if not _unit_re.match(field_name):
        return [_('Invalid field name')]

    elif field_name.endswith('digits') and not value.isdigit():
        return [_('Please enter a number that is 0 or greater')]

    return None
