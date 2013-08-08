from django import template

register = template.Library()


@register.tag('usercanread')
def usercanread_tag(parser, token):
    """
    Template tag that can wrap a block of code that executes only
    if the given model has 'viewing' permissions

    For instance,

    {% usercanread plot "width" as the_plot_width %}
    The plot's width is: {{ the_plot_width }}
    {% endusercanread %}

    Will render:

    The plot's width is: 10

    If the current user (defined as 'request.user') has permission
    to view the 'width' field on 'plot'

    If the user doesn't have that permission nothing is rendered
    """
    try:
        field_token, thing, field, as_token, binding = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError(
            'expected format is: '
            'field {python for model} "{field}" as {var}')

    if field_token != 'usercanread' or as_token != 'as':
        raise template.TemplateSyntaxError(
            'expected format is: '
            'field {python for model} "{field}" as {var}')

    if field[0] == '"' and field[0] == field[-1] and len(field) >= 2:
        field = field[1:-1]

    nodelist = parser.parse(('endusercanread',))
    parser.delete_first_token()
    return FieldVisibilityNode(nodelist, thing, field, binding)


class FieldVisibilityNode(template.Node):
    def __init__(self, nodelist, model_variable, field, binding):
        self.binding = binding
        self.model_variable = template.Variable(model_variable)
        self.nodelist = nodelist
        self.field = field

    def render(self, context):
        req_user = template.Variable('request.user').resolve(context)
        model = self.model_variable.resolve(context)

        if model and model.field_is_visible(req_user, self.field):
            val = getattr(model, self.field)
            context[self.binding] = val
            content = self.nodelist.render(context)
        else:
            content = ''

        return content
