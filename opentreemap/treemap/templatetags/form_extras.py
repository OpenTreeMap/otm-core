import re
from django import template
from django.template.loader import get_template
from django.db.models.fields import FieldDoesNotExist

register = template.Library()

# Used to whitelist the model.field values that are valid for the
# template tag
_identifier_regex = re.compile(
    r'^(?:tree|plot|instance|user|species)\.(?:udf\:)?[\w ]+$')


@register.tag('field')
def field_tag(parser, token):
    """
    Adds a "field" dictionary to the context with field metadata then
    renders the specified child template, which can use the metadata
    to build in-place editing and conditionally show elements based
    on user permissions.

    For instance, given the following template.html:

        <span data-field="{{field.identifier}}"
              data-class="display"
              data-value="{{field.value}}">{{field.display_value}}</span>
        {% if field.is_editable %}
            <input name="{{field.identifier}}"
                   data-field="{{field.identifier}}"
                   data-type="{{field.data_type}}"
                   data-class="edit"
                   type="text"
                   value="{{field.value}}"
                   style="display: none;" />
        {% endif %}

    The tag:

    {% field "Width" from "plot.width" for user withtemplate "template.html" %}

    Will render:

        <span data-field="plot.width"
              data-class="display"
              data-value="4">4</span>
        <input name="plot.width"
               data-field="plot.width"
               data-type="float"
               data-class="edit"
               type="text"
               value="4"
               style="display: none;" />

    If the specified user has permission to edit the 'width'
    field on 'plot'. If the user only has view permission on the
    field, the tag will render

        <span data-field="plot.width"
              data-class="display"
              data-value="4">4</span>

    If the user does not have permission to view plot width, nothing is
    rendered.

    To allow using the tag with models that are not Authorizable, the tag
    supports omitting the "for user" section.

    {% field "First" from "user.first_name" withtemplate "template.html" %}

    To allow using the tag with a more complex read-only representation, the
    label can be omitted, in which case the template is expected to provide
    a translated label.

    {% field from "user.first_name" withtemplate "template.html" %}
    {% field from "user.first_name" for user withtemplate "template.html" %}

    The template passed to the tag can use ``field.data_type`` to
    conditionally render different markup. This shows how choice fields
    can be rendered as <select> tags.

        {% if field.is_visible %}
            <span data-field="{{field.identifier}}"
                  data-class="display"
                  data-value="{{field.value}}">{{field.display_value}}</span>
        {% endif %}
        {% if field.is_editable %}

            {% if field.data_type == 'choice' %}
                <select name="{{field.identifier}}"
                        data-field="{{field.identifier}}"
                        data-type="{{field.data_type}}"
                        data-class="edit"
                        value="{{field.value}}"
                        style="display: none;" />
                    {% for option in field.options %}
                        <option value="{{option.value}}">
                            {{option.display_value}}
                        </option>
                    {% endfor %}
                </select>
            {% endif %}

            ... check for other field.data_type values ...

        {% endif %}
    """

    syntaxErrorWithFormatMessage = template.TemplateSyntaxError(
        'expected format is: '
        'field [{label}] from {model.property}'
        ' [for {user}] withtemplate {template}')

    try:
        tokens = token.split_contents()
    except ValueError:
        raise syntaxErrorWithFormatMessage

    if len(tokens) < 5:
        raise syntaxErrorWithFormatMessage

    field_token = tokens[0]

    if len(tokens) in {5, 7}:
        label = None
        from_token = tokens[1]
        identifier = tokens[2]
    elif len(tokens) in {6, 8}:
        label = tokens[1]
        from_token = tokens[2]
        identifier = tokens[3]

    if len(tokens) == 5:
        for_token = None
        user = None
        with_token = tokens[3]
        field_template = tokens[4]
    elif len(tokens) == 6:
        for_token = None
        user = None
        with_token = tokens[4]
        field_template = tokens[5]
    elif len(tokens) == 7:
        for_token = tokens[3]
        user = tokens[4]
        with_token = tokens[5]
        field_template = tokens[6]
    elif len(tokens) == 8:
        for_token = tokens[4]
        user = tokens[5]
        with_token = tokens[6]
        field_template = tokens[7]
    else:
        raise syntaxErrorWithFormatMessage

    if field_token != 'field' or from_token != 'from' \
    or with_token != 'withtemplate':  # NOQA
        raise syntaxErrorWithFormatMessage

    if for_token is not None and for_token != "for":
        raise syntaxErrorWithFormatMessage

    label = _token_to_variable(label)

    identifier = _token_to_variable(identifier)

    user = _token_to_variable(user)
    field_template = _token_to_variable(field_template)

    return FieldNode(label, identifier, user, field_template)


def _token_to_variable(token):
    """
    Either strip the double quotes from a literal token or convert
    it into a template.Variable.
    """
    if token is None:
        return None
    elif token[0] == '"' and token[0] == token[-1] and len(token) >= 2:
        return token[1:-1]
    else:
        return template.Variable(token)


def _resolve_variable(variable, context):
    """
    If `variable` has a resolve method, call it with the specified
    `context`, else return `variable`
    """
    if variable is None:
        return None
    elif hasattr(variable, 'resolve'):
        return variable.resolve(context)
    else:
        return variable


class FieldNode(template.Node):
    _field_mappings = {
        'IntegerField': 'int',
        'ForeignKey': 'int',
        'FloatField': 'float',
        'TextField': 'string',
        'CharField': 'string',
        'DateTimeField': 'date'
    }
    _valid_field_keys = ','.join([k for k, v in _field_mappings.iteritems()])

    def __init__(self, label, identifier, user, field_template):
        self.label = label
        self.identifier = identifier
        self.user = user
        self.field_template = field_template

    def render(self, context):
        label = _resolve_variable(self.label, context)
        identifier = _resolve_variable(self.identifier, context)
        model_name, field_name = identifier.split('.')
        model = context[model_name]
        user = _resolve_variable(self.user, context)
        field_template = get_template(_resolve_variable(
                                      self.field_template, context))

        if not isinstance(identifier, basestring):
            raise template.TemplateSyntaxError(
                'expected a string with the format "model.property"'
                'to follow "from"')

        if not _identifier_regex.match(identifier):
            raise template.TemplateSyntaxError(
                'expected a string with the format "model.property"'
                'to follow "from"')

        def _udf_dict(model, field_name):
            return model.get_user_defined_fields()\
                .filter(name=field_name.replace('udf:', ''))[0]\
                .datatype_dict

        def _field_type_to_string(model, field_name):
            try:
                field_type = model._meta.get_field(field_name)\
                    .get_internal_type()
                try:
                    field_type = FieldNode._field_mappings[field_type]
                except KeyError:
                    raise Exception('This template tag only supports %s not %s'
                                    % (FieldNode._valid_field_keys,
                                       field_type))
            except FieldDoesNotExist:
                field_type = _udf_dict(model, field_name)['type']

            return field_type

        def _field_value_and_choices(model, field_name):
            choices = None
            udf_field_name = field_name.replace('udf:', '')
            model_has_udfs = hasattr(model, 'udf_field_names')
            if model_has_udfs:
                field_is_udf = (udf_field_name in model.udf_field_names)
            else:
                field_is_udf = False

            if hasattr(model, field_name):
                val = getattr(model, field_name)
            elif model_has_udfs and field_is_udf:
                val = model.udf_scalar_values[udf_field_name]
                try:
                    choices = _udf_dict(model, udf_field_name)['choices']
                except KeyError:
                    choices = None
            else:
                raise ValueError('Could not find field: %s' % field_name)

            return val, choices

        field_value, choices = _field_value_and_choices(model, field_name)

        if user is not None:
            is_visible = model.field_is_visible(user, field_name)
            is_editable = model.field_is_editable(user, field_name)
        else:
            # This tag can be used without specifying a user. In that case
            # we assume that the content is visible and upstream code is
            # responsible for only showing the content to the appropriate
            # user
            is_visible = True
            is_editable = True

        context['field'] = {
            'label': label,
            'identifier': identifier,
            'value': field_value,
            # TODO: Support pluggable formatting instead of str()
            'display_value': str(field_value),
            'data_type': _field_type_to_string(model, field_name),
            'is_visible': is_visible,
            'is_editable': is_editable,
            'choices': choices
        }

        return field_template.render(context)
