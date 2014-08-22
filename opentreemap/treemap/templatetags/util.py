from django import template
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist

from treemap.models import MapFeature, Tree, TreePhoto, MapFeaturePhoto
from treemap.udf import UserDefinedCollectionValue
from treemap.util import get_filterable_audit_models

register = template.Library()


register.filter('get', lambda a, b: a[b])


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
    'mapfeaturephoto': _map_feature_photo_detail_link
}


@register.filter
def detail_link(thing):
    """
    Get a link to a detail view that can be shown for an
    object with this type

    For example, a 'treephoto' instance provides a link to
    the given tree.
    """
    name = thing.__class__.__name__.lower()
    if name in MODEL_DETAILS:
        return MODEL_DETAILS[name](thing)
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
def display_name(model_or_name):
    if isinstance(model_or_name, basestring):
        name = model_or_name
        if name.startswith('udf:'):
            name = UserDefinedCollectionValue.get_display_model_name(name)
    else:
        name = model_or_name.__class__.__name__

    if name.lower() == 'plot':
        return 'Planting Site'
    else:
        return name


@register.filter
def is_filterable_audit_model(model_name):
    allowed_models = get_filterable_audit_models()

    return model_name in allowed_models.values()


@register.filter
def tabindex(value, index):
    """
    Adds a tabindex to a Django forms widget
    """
    value.field.widget.attrs['tabindex'] = index
    return value
