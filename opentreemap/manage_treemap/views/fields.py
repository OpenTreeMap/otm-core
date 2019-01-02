# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from copy import deepcopy

from django.utils.translation import ugettext as _

from opentreemap.util import json_from_request

from treemap.models import Species, Tree
from treemap.util import to_model_name, safe_get_model_class, to_object_name
from treemap.lib.object_caches import udf_defs
from treemap.search_fields import (
    set_search_field_label, ALERT_IDENTIFIER_PATTERN, get_alert_field_info)


def set_fields(request, instance):
    data = json_from_request(request)
    instance.web_detail_fields = data['web_detail_fields']
    instance.mobile_api_fields = data['mobile_api_fields']
    instance.save()

    return {'success': True}


def set_fields_page(request, instance):
    mobile_field_groups = deepcopy(instance.mobile_api_fields)
    web_field_groups = deepcopy(instance.web_detail_fields)

    collection_groups = ('Stewardship', 'Alerts')

    def get_disabled_fields(group):
        model_name = to_model_name(group['model'])
        Model = safe_get_model_class(model_name)
        mobj = Model(instance=instance)

        model_fields = {field for field in mobj.tracked_fields
                        if _should_show_field(Model, field)}
        model_fields = {'%s.%s' % (group['model'], f) for f in model_fields}
        disabled_fields = model_fields - set(group['field_keys'])

        return sorted(disabled_fields)

    def get_disabled_cudfs(group):
        if 'model' in group:
            models = (to_model_name(group['model']), )
        else:
            models = ('Tree', 'Plot')

        udfs = {udf.full_name for udf in udf_defs(instance)
                if udf.iscollection and udf.model_type in models and
                (group['header'] not in collection_groups
                 or udf.name == group['header'])}

        disabled_cudfs = udfs - set(group['collection_udf_keys'])
        return sorted(disabled_cudfs)

    for field_groups in (web_field_groups, mobile_field_groups):
        for group in field_groups:
            if 'field_keys' in group:
                group['disabled_fields'] = get_disabled_fields(group)
                group['category'] = group['model']
            if 'collection_udf_keys' in group:
                group['disabled_cudf_fields'] = get_disabled_cudfs(group)

    return {
        'instance': instance,
        'mobile_field_groups': mobile_field_groups,
        'web_field_groups': web_field_groups,
    }


def set_search_config(request, instance):
    search_fields = json_from_request(request)
    for prop in ('search_config', 'mobile_search_fields'):
        config = deepcopy(getattr(instance, prop))
        for key, val in search_fields[prop].iteritems():
            config[key] = search_fields[prop][key]

        setattr(instance, prop, config)
    instance.save()


def search_config(request, instance):
    return {
        'instance': instance,
        'website_field_groups': _website_search_config(instance),
        'mobile_field_groups': _mobile_search_config(instance),
    }


def _website_search_config(instance):
    map_feature_types = sorted(instance.map_feature_types)
    map_feature_types.remove('Plot')
    model_names = ['Tree', 'Plot']
    model_names.extend(map_feature_types)

    fields_by_model = {model_name: sorted(_get_fields(instance, model_name))
                       for model_name in model_names}

    def get_context_for_model(model_name):
        model_fields = fields_by_model[model_name]
        enabled, disabled = get_enabled_and_disabled_fields(model_name,
                                                            model_fields)

        display_name = safe_get_model_class(model_name).display_name(instance)

        return {
            'field_keys': enabled,
            'disabled_fields': disabled,
            'header': _('%(model)s Filters') % {'model': display_name},
            'category': model_name,
        }

    def get_context_for_missing():
        all_fields = ['species.id', 'mapFeaturePhoto.id']
        for model_name in model_names:
            all_fields.extend(fields_by_model[model_name])

        enabled, disabled = get_enabled_and_disabled_fields('missing',
                                                            all_fields)
        enabled = _add_field_info(instance, enabled)
        disabled = _add_field_info(instance, disabled)
        return {
            'field_keys': enabled,
            'disabled_fields': disabled,
            'header': _('Missing Data Filters'),
            'category': 'missing'
        }

    def get_enabled_and_disabled_fields(category, fields):
        current_search_fields = instance.search_config.get(category, [])
        enabled_fields = [f['identifier'] for f in current_search_fields]
        disabled_fields = (set(fields) - set(enabled_fields))
        return enabled_fields, sorted(disabled_fields)

    field_groups = [get_context_for_model(model_name)
                    for model_name in model_names]
    field_groups.append(get_context_for_missing())

    return field_groups


def _mobile_search_config(instance):
    all_fields = []
    for model_name in ['Tree', 'Plot', 'Species']:
        all_fields += _get_fields(instance, model_name)

    def get_context_for_group(category, header):
        fields = list(all_fields)
        if category == 'missing':
            fields += ['species.id', 'mapFeaturePhoto.id']
        else:
            fields += ['species.id']
            if contains_alerts():
                fields += alert_identifiers()

        enabled, disabled = get_enabled_and_disabled_fields(category, fields)

        return {
            'field_keys': enabled,
            'disabled_fields': disabled,
            'header': header,
            'category': category
        }

    def get_enabled_and_disabled_fields(category, fields):
        current_search_fields = instance.mobile_search_fields.get(category, [])
        enabled_fields = [f['identifier'] for f in current_search_fields]
        disabled_fields = set(fields) - set(enabled_fields)

        return (_add_field_info(instance, enabled_fields),
                sorted(_add_field_info(instance, disabled_fields)))

    def contains_alerts():
        return instance.url_name == 'latreemap'

    def alert_identifiers():
        def identifier(udf):
            model_name = udf.model_type.lower()
            return 'udf:%(model)s:%(pk)s.Status' % {
                'model': model_name, 'pk': udf.pk}

        return [identifier(udf) for udf in udf_defs(instance)
                if udf.iscollection and udf.name == 'Alerts']

    def add_alert_info(field_identifiers):
        return [get_alert_field_info(id)
                if ALERT_IDENTIFIER_PATTERN.match(id) else id
                for id in field_identifiers]

    return [
        get_context_for_group('standard', _('Detail Filters')),
        get_context_for_group('missing', _('Missing Data Filters'))
    ]


def _add_field_info(instance, field_names):
    def field_context(identifier):
        if ALERT_IDENTIFIER_PATTERN.match(identifier):
            return get_alert_field_info(identifier, instance)
        else:
            return set_search_field_label(instance, {'identifier': field_name})

    return [field_context(field_name) for field_name in field_names]


def _should_show_field(model, field_name):
    if field_name.startswith('udf:'):
        return True
    elif field_name == 'id' and model != Tree:
        # We show tree.id on the detail and have special handling for it so we
        # do not want to filter it out. Other id fields are always hidden.
        return False
    elif model == Species:
        # latreemap shows these; it's easiest to include them for all maps
        return field_name in ['is_native', 'palatable_human']

    field = model._meta.get_field(field_name)
    return getattr(field, '_verbose_name', None) is not None


def _get_fields(instance, model_name):
    Model = safe_get_model_class(model_name)
    mobj = Model(instance=instance)
    udfs = {udf.canonical_name
            for udf in udf_defs(instance, model_name)
            if not udf.iscollection}
    concrete_fields = {
        f.name for f in mobj._meta.get_fields(include_parents=False)
        if _should_show_field(Model, f.name) and not f.is_relation}
    model_fields = concrete_fields | udfs
    model_fields = {'%s.%s' % (to_object_name(model_name), f)
                    for f in model_fields}
    return model_fields
