# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

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
            'usercanread {python for model} "{field}" as {var}')

    if field_token != 'usercanread' or as_token != 'as':
        raise template.TemplateSyntaxError(
            'expected format is: '
            'usercanread {python for model} "{field}" as {var}')

    if field[0] == '"' and field[0] == field[-1] and len(field) >= 2:
        field = field[1:-1]
    else:
        field = template.Variable(field)

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
        if hasattr(self.field, 'resolve'):
            field = self.field.resolve(context)
        else:
            field = self.field

        req_user = template.Variable('request.user').resolve(context)
        model = self.model_variable.resolve(context)

        if model and model.field_is_visible(req_user, field):
            if hasattr(model, field):
                val = getattr(model, field)
            else:
                prefix, udf_field_name = field.split(':', 1)
                is_valid_udf_field = (hasattr(model, 'udf_field_names') and
                                      prefix == 'udf' and
                                      udf_field_name in model.udf_field_names)
                if is_valid_udf_field:
                    val = model.udfs[udf_field_name]
                else:
                    raise ValueError('Could not find field: %s' % field)

            context[self.binding] = val
            content = self.nodelist.render(context)
        else:
            content = ''

        return content


@register.tag('usercancreate')
def usercancreate_tag(parser, token):
    """
    Template tag that can wrap a block of code that executes only
    if the current user has permission to create the given model

    For instance,

    {% usercancreate tree %}
    <a>Create A Tree</a>
    {% endusercancreate %}

    If the user doesn't have that permission nothing is rendered
    """
    try:
        tag_token, model = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError(
            'expected format is: usercancreate {model}')

    if tag_token != 'usercancreate':
        raise template.TemplateSyntaxError(
            'expected format is: usercancreate {model}')

    nodelist = parser.parse(('endusercancreate',))
    parser.delete_first_token()
    return CreateVisibilityNode(nodelist, model)


class CreateVisibilityNode(template.Node):
    def __init__(self, nodelist, model_variable):
        self.model_variable = template.Variable(model_variable)
        self.nodelist = nodelist

    def render(self, context):
        req_user = template.Variable('request.user').resolve(context)
        model = self.model_variable.resolve(context)

        if (model and req_user and req_user.is_authenticated()
           and model.user_can_create(req_user)):
            content = self.nodelist.render(context)
        else:
            content = ''

        return content


@register.tag('usercontent')
def usercontent_tag(parser, token):
    """
    Template tag that can wrap a block of code that executes only
    if the logged in user matched user specified in the
    tag

        {% usercontent for "joe" %}
            Email: {{ email }}
        {% endusercontent %}

    Will render the email address only if the username of the logged in user
    (defined as 'request.user.username') is 'joe'

        {% usercontent for user %}
            Email: {{ email }}
        {% endusercontent %}

    will render the email address only if user == request.user

        {% usercontent for 1 %}
            Email: {{ email }}
        {% endusercontent %}

    will render the email address only if request.user.pk == 1
    """
    try:
        field_token, for_token, user_identifier = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError(
            'expected format is: '
            'usercontent for {user_identifier}')

    if field_token != 'usercontent' or for_token != 'for':
        raise template.TemplateSyntaxError(
            'expected format is: '
            'usercontent for {user_identifier}')

    if isinstance(user_identifier, (int, long)):
        user_identifier = user_identifier
    else:
        if user_identifier[0] == '"'\
        and user_identifier[0] == user_identifier[-1]\
        and len(user_identifier) >= 2:  # NOQA
            user_identifier = user_identifier[1:-1]
        else:
            user_identifier = template.Variable(user_identifier)

    nodelist = parser.parse(('endusercontent',))
    parser.delete_first_token()
    return UserContentNode(nodelist, user_identifier)


class UserContentNode(template.Node):
    def __init__(self, nodelist, user_identifier):
        self.user_identifier = user_identifier
        self.nodelist = nodelist

    def render(self, context):
        req_user = template.Variable('request.user').resolve(context)

        if hasattr(self.user_identifier, 'resolve'):
            user_identifier = self.user_identifier.resolve(context)
        else:
            user_identifier = self.user_identifier

        user_content = self.nodelist.render(context)
        if isinstance(user_identifier, (int, long)):
            if req_user.pk == user_identifier:
                return user_content
        elif isinstance(user_identifier, basestring):
            if req_user.username == user_identifier:
                return user_content
        else:
            if req_user == user_identifier:
                return user_content

        # If there was a user match, the function would have
        # previously returned the protected content
        return ''
