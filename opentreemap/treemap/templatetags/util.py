from django import template
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist

import json
import re

from opentreemap.util import dotted_split

from treemap.models import MapFeature, Tree, TreePhoto, MapFeaturePhoto, Audit
from treemap.udf import UserDefinedCollectionValue
from treemap.util import (get_filterable_audit_models, to_model_name,
                          safe_get_model_class, num_format as util_num_format)
from treemap.units import Convertible


_external_tree_id_url_re = re.compile(r'#{tree.id}')


register = template.Library()


register.filter('get', lambda a, b: a[b])


# From https://djangosnippets.org/snippets/545/
# Found from http://bit.ly/2c37Fgz on stackoverflow
# /questions/15073695/assigning-blocktrans-output-to-variable
#
# The correct answer to the stackoverflow question is to use the
# blocktrans `asvar` parameter, but that only works in django v 1.9+.
# `captureas` seems more generally useful than just for blocktrans.
@register.tag(name='captureas')
def do_captureas(parser, token):
    try:
        tag_name, var_name = token.contents.split(None, 1)
    except ValueError:
        var_name = 'captured'
    nodelist = parser.parse(('endcaptureas',))
    parser.delete_first_token()
    return CaptureasNode(nodelist, var_name)


class CaptureasNode(template.Node):
    def __init__(self, nodelist, varname):
        self.nodelist = nodelist
        self.varname = varname

    def render(self, context):
        context[self.varname] = self.nodelist.render(context)
        return ''


def _instance_reverse(name, thing, **kwargs):
    kwargs['instance_url_name'] = thing.instance.url_name
    return reverse(name, kwargs=kwargs)


def _map_feature_photo_detail_link(photo):
    if hasattr(photo, 'treephoto'):
        return MODEL_DETAILS['tree'](photo.treephoto.tree)
    else:
        return MODEL_DETAILS['mapfeature'](photo.map_feature)


MODEL_DETAILS = {
    'mapfeature': lambda feature: _instance_reverse(
        'map_feature_detail', feature, feature_id=feature.pk),
    'tree': lambda tree: _instance_reverse(
        'tree_detail', tree, feature_id=tree.plot.pk, tree_id=tree.pk),
    'treephoto': lambda tp: MODEL_DETAILS['tree'](tp.tree),
    'mapfeaturephoto': _map_feature_photo_detail_link,
    'user': lambda user: reverse('user', args=(user.username,))
}


@register.filter
def detail_link(thing):
    """
    Get a link to a detail view that can be shown for an
    object with this type

    For example, a 'treephoto' instance provides a link to
    the given tree.
    """
    name = thing.__class__.__name__
    nameLower = name.lower()
    if nameLower in MODEL_DETAILS:
        return MODEL_DETAILS[nameLower](thing)
    elif MapFeature.has_subclass(name):
        return MODEL_DETAILS['mapfeature'](thing)
    else:
        return None

AUDIT_MODEL_LOOKUP_FNS = {
    'mapfeature': lambda id: MapFeature.objects.get(pk=id),
    'tree': lambda id: Tree.objects.get(pk=id),
    'treephoto': lambda id: TreePhoto.objects.get(pk=id),
    'mapfeaturephoto': lambda id: MapFeaturePhoto.objects.get(pk=id),
}


@register.filter
def audit_detail_link(audit):
    """
    Get a link to a detail view that can be shown for this audit

    For example, an audit on 'treephoto' provides a link to
    the given tree.
    """
    model = audit.model

    if model in MapFeature.subclass_dict().keys():
        model = 'mapfeature'

    model = model.lower()

    if model in AUDIT_MODEL_LOOKUP_FNS:
        try:
            lkp_fn = AUDIT_MODEL_LOOKUP_FNS[model]
            obj = lkp_fn(audit.model_id)
            return detail_link(obj)
        except ObjectDoesNotExist:
            return None
    else:
        return None


@register.filter
def terminology(model, instance):
    return model.terminology(instance)


@register.filter
def display_name(audit_or_model_or_name, instance=None):
    audit = None
    if isinstance(audit_or_model_or_name, (Audit, basestring)):
        if isinstance(audit_or_model_or_name, Audit):
            audit = audit_or_model_or_name
            name = audit.model
            extra_args = [audit.instance]
        else:
            name = audit_or_model_or_name
            extra_args = []
        if name.startswith('udf:'):
            return UserDefinedCollectionValue.get_display_model_name(
                name, *extra_args)
    else:
        name = audit_or_model_or_name.__class__.__name__

    if audit:
        return audit.model_display_name()

    cls = safe_get_model_class(name)
    if issubclass(cls, Convertible):
        # Sometimes instance will be None here, so we'll use the default name
        return cls.display_name(instance)
    else:
        return name


@register.filter
def is_filterable_audit_model(model_name):
    allowed_models = get_filterable_audit_models()

    return model_name in allowed_models


@register.filter
def tabindex(value, index):
    """
    Adds a tabindex to a Django forms widget
    """
    value.field.widget.attrs['tabindex'] = index
    return value


@register.filter
def identifier_model_name(identifier):
    """
    Takes an identifier like "model.field" and returns the model's display name
    """
    object_name, __ = dotted_split(identifier, 2, maxsplit=1)

    return display_name(to_model_name(object_name))


@register.filter
def lat_lng_coordinates_json(geom):
    if not geom:
        return "''"
    else:
        return json.dumps(geom.transform(4326, clone=True).tuple[0][0])


@register.filter
def udf_name(udf_identifier):
    if 'udf:' not in udf_identifier:
        raise ValueError('Unrecognized identifier %(id)s' % udf_identifier)

    return udf_identifier.split("udf:", 1)[1]


@register.filter
def num_format(num):
    return util_num_format(num)
