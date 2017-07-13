# Modified from https://djangosnippets.org/snippets/1302/

from django.template import Library, Node, Variable, loader
from django.template.context import Context

register = Library()


class PartialNode(Node):
    def __init__(self, template, context_item):
        self.template = template
        self.context_item = Variable(context_item)

    def render(self, context):
        item = self.context_item.resolve(context)
        template_context = Context(item)
        return self.template.render(template_context)


@register.tag
def partial(parser, token):
    """
    Renders a template using a sub-dict of the current context.
    For example, if the context is:
       {'car': {'mileage': 9000, 'doors': 4},
        'house': {'sqft': 1800, 'baths': 2}}
    and the template "myApp/partials/house.html" contains:
        <div>Area: {{ sqft }} sq. ft.</div>
        <div>Bathrooms: {{ baths }}</div>
    you could render it like this:
        {% load partial %}
        {% partial myApp/partials/house.html house %}
    """
    tag, template_name, context_item = token.split_contents()
    template = loader.get_template(template_name).template
    return PartialNode(template, context_item)
