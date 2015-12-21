# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext_noop

import copy

from treemap.DotDict import DotDict
from treemap.lib.object_caches import udf_defs

DEFAULT_MOBILE_SEARCH_FIELDS = {
    'standard': [{'search_type': 'SPECIES',
                  'identifier': 'species.id',
                  'label': 'Species'},
                 {'search_type': 'RANGE',
                  'identifier': 'tree.diameter',
                  'label': 'Diameter'},
                 {'search_type': 'RANGE',
                  'identifier': 'tree.height',
                  'label': 'Height'}],
    'missing': [{'identifier': 'species.id',
                 'label': 'Missing Species'},
                {'identifier': 'tree.diameter',
                 'label': 'Missing Diameter'},
                {'identifier': 'mapFeaturePhoto.id',
                 'label': 'Missing Photo'}]
}

DEFAULT_SEARCH_FIELDS = {
    'general': [
        {'identifier': 'mapFeature.updated_at'}
    ],
    'missing': [
        {'identifier': 'species.id'},
        {'identifier': 'tree.diameter'},
        {'identifier': 'mapFeaturePhoto.id'}
    ],
    'Tree': [
        {'identifier': 'tree.diameter'},
        {'identifier': 'tree.date_planted'},
    ]
}

DEFAULT_MOBILE_API_FIELDS = (
    {'header': ugettext_noop('Tree Information'),
     'model': 'tree',
     'field_keys': ['tree.species', 'tree.diameter',
                    'tree.height', 'tree.date_planted']},
    {'header': ugettext_noop('Planting Site Information'),
     'model': 'plot',
     'field_keys': ['plot.width', 'plot.length']},
    {'header': ugettext_noop('Stewardship'),
     'collection_udf_keys': ['plot.udf:Stewardship', 'tree.udf:Stewardship'],
     'sort_key': 'Date'}
)

API_FIELD_ERRORS = {
    'no_field_groups': _('Must be a non-empty list'),

    'group_has_no_header': _(
        'Every mobile field group must have a non-empty header'),

    'group_has_no_keys': _(
        'All mobile field groups must have either a "field_keys" or '
        '"collection_udf_keys" containing a non-empty list'),

    'group_has_both_keys': _(
        'Mobile field groups cannot contain both "field_keys" and '
        '"collection_udf_keys" properties'),

    'group_has_no_sort_key': _(
        'Collection field groups must have a non-empty "sort_key" property '
        'defined'),

    'group_has_missing_cudf': _(
        'Collection field groups can only contain existing custom collection '
        'fields'),

    'group_has_invalid_sort_key': _(
        'The "sort_key" property of a collection field group must be the name '
        'of a field on present on every collection field in the group'),

    'duplicate_fields': _('Fields cannot be specified more than once'),

    'group_missing_model': _(
        'Normal field groups need a model property of either "tree" or "plot"'
    ),

    'group_invalid_model': _(
        'Normal field groups can only have keys that match their "model"'
    ),

    'missing_field': _(
        'Normal field groups may only contain existing fields. If you specify '
        'a custom field, it cannot be a collection field'),
}


def advanced_search_fields(instance, user):
    from treemap.util import get_model_for_instance
    from treemap.templatetags.form_extras import field_type_label_choices
    from treemap.models import Tree, MapFeature  # prevent circular import

    def make_display_filter(feature_name):
        if feature_name == 'Plot':
            plural = _('empty planting sites')
            feature_name = 'EmptyPlot'
        else:
            plural = get_plural_feature_name(feature_name)

        return {
            'label': _('Show %(models)s') % {'models': plural.lower()},
            'model': feature_name
        }

    def get_plural_feature_name(feature_name):
        if feature_name == 'Tree':
            Feature = Tree
        else:
            Feature = MapFeature.get_subclass(feature_name)
        return Feature.terminology(instance)['plural']

    def parse_field_info(field_info):
        model_name, field_name = field_info['identifier'].split('.', 2)
        model = get_model_for_instance(model_name, instance)
        return model, field_name

    def get_visible_fields(fields, user):
        visible_fields = []
        for field in fields:
            model, field_name = parse_field_info(field)
            if model.field_is_visible(user, field_name):
                visible_fields.append(field)
        return visible_fields

    fields = copy.deepcopy(instance.search_config)
    fields = {model: get_visible_fields(fields, user)
              for model, fields in fields.iteritems()}

    for field_info in fields.get('missing', []):
        model, field_name = parse_field_info(field_info)

        if field_name == 'id':
            if hasattr(model, 'terminology'):
                label = model.terminology(instance)['plural']
            else:
                label = model._meta.verbose_name_plural
        else:
            __, label, __ = field_type_label_choices(model, field_name, '')

        field_info['label'] = _('Show missing %(field)s') % {
            'field': label.lower()}
        field_info['search_type'] = 'ISNULL'
        field_info['value'] = 'true'

    fields['display'] = [make_display_filter('Tree'),
                         make_display_filter('Plot')]
    fields['display'] += [
        make_display_filter(feature)
        for feature in sorted(instance.map_feature_types) if feature != 'Plot']

    num = 0
    for filters in fields.itervalues():
        for field in filters:
            # It makes styling easier if every field has an identifier
            field['id'] = "%s_%s" % (field.get('identifier', ''), num)
            num += 1

    more = []
    for feature_name in sorted(instance.map_feature_types):
        if feature_name in fields and feature_name != 'Plot':
            filters = fields.pop(feature_name)
            filters = get_visible_fields(filters, user)

            if len(filters) > 0:
                more.append({
                    'name': feature_name,
                    'title': get_plural_feature_name(feature_name),
                    'fields': filters
                })
    fields['more'] = more

    return fields


def get_udfc_search_fields(instance, user):
    from treemap.models import InstanceUser
    from treemap.udf import UDFModel
    from treemap.util import to_object_name, leaf_models_of_class
    from treemap.lib.perms import udf_write_level, READ, WRITE

    try:
        iu = instance.instanceuser_set.get(user__pk=user.pk)
    except InstanceUser.DoesNotExist:
        iu = None

    data = DotDict({'models': set(), 'udfc': {}})
    for clz in leaf_models_of_class(UDFModel):
        model_name = clz.__name__
        if model_name not in ['Tree'] + instance.map_feature_types:
            continue
        for k, v in clz.collection_udf_settings.items():
            udfds = (u for u in udf_defs(instance, model_name) if u.name == k)
            for udfd in udfds:
                if udf_write_level(iu, udfd) in (READ, WRITE):
                    _base_nest_path = 'udfc.%s.' % (to_object_name(k))
                    ids_nest_path = ('%sids.%s'
                                     % (_base_nest_path,
                                        to_object_name(model_name)))
                    models_nest_path = ('%smodels.%s' %
                                        (_base_nest_path,
                                         to_object_name(model_name)))
                    data[ids_nest_path] = udfd.pk
                    data[models_nest_path] = {
                        'udfd': udfd,
                        'fields': udfd.datatype_dict[0]['choices']
                    }
                    p = 'udfc.%s.' % to_object_name(k)
                    data[p + 'action_verb'] = v['action_verb']
                    data[p + 'range_field_key'] = v['range_field_key']
                    data[p + 'action_field_key'] = v['action_field_key']
                    data['models'] |= {clz}

    return data
