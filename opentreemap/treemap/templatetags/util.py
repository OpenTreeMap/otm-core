from django import template
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist

from treemap.models import Plot, Tree, TreePhoto
from treemap.udf import UserDefinedCollectionValue

register = template.Library()


register.filter('get', lambda a, b: a[b])


def _instance_reverse(name, thing, **kwargs):
    kwargs['instance_url_name'] = thing.instance.url_name
    return reverse(name, kwargs=kwargs)


MODEL_DETAILS = {
    'plot': lambda plot: _instance_reverse(
        'plot_detail', plot, plot_id=plot.pk),
    'tree': lambda tree: _instance_reverse(
        'tree_detail', tree, plot_id=tree.plot.pk, tree_id=tree.pk),
    'treephoto': lambda tp: MODEL_DETAILS['tree'](tp.tree)
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
    'plot': lambda id: Plot.objects.get(pk=id),
    'tree': lambda id: Tree.objects.get(pk=id),
    'treephoto': lambda id: TreePhoto.objects.get(pk=id),
}


@register.filter
def audit_detail_link(audit):
    """
    Get a link to a detail view that can be shown for this audit

    For example, an audit on 'treephoto' provides a link to
    the given tree.
    """
    model = audit.model.lower()

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
