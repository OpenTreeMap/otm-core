# -*- coding: utf-8 -*-


from django import template
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import ValidationError
from django.shortcuts import resolve_url
from django.utils.encoding import force_str
from django.utils.http import urlencode
from django.utils.translation import ugettext_lazy as _

from treemap.util import get_login_redirect_path

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

        if (model and req_user and req_user.is_authenticated
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

    if isinstance(user_identifier, int):
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
        if isinstance(user_identifier, int):
            if req_user.pk == user_identifier:
                return user_content
        elif isinstance(user_identifier, str):
            if req_user.username == user_identifier:
                return user_content
        else:
            if req_user == user_identifier:
                return user_content

        # If there was a user match, the function would have
        # previously returned the protected content
        return ''


@register.simple_tag(takes_context=True)
def login_forward(context, query_prefix='?'):
    """
    If the current page is an instance page and the user is not logged in,
    return the `?next=` query param with a value that is the sanitized
    version of the current page url.

    `login_forward` should not be called if the user is already logged in.

    Return an empty string if the current page is not an instance page.
    """
    request = template.Variable('request').resolve(context)

    if getattr(request, 'user', None) and request.user.is_authenticated:
        raise ValidationError(
            _('Can\'t forward login if already logged in'))
    # urlparse chokes on lazy objects in Python 3, force to str
    resolved_login_url = force_str(resolve_url(settings.LOGIN_URL))
    path = get_login_redirect_path(request, resolved_login_url)
    if not getattr(request, 'instance', None):
        maxsplit = 2 if path.startswith('/') else 1
        root = path.split('/', maxsplit)[:maxsplit][-1]
        # Could get fancy and make a setting, to decouple from other modules
        if root not in ('comments', 'users', 'create'):
            # Anything else, probably better off with the default redirect
            return ''
    return query_prefix + urlencode([(REDIRECT_FIELD_NAME, path)])
