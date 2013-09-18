import re

from modgrammar import Grammar, OPTIONAL, G, WORD, OR, ParseError

from django import template
from django.template.loader import get_template
from django.db.models.fields import FieldDoesNotExist

from treemap.util import safe_get_model_class
from treemap.json_field import (is_json_field_reference,
                                get_attr_from_json_field)

register = template.Library()

# Used to whitelist the model.field values that are valid for the
# template tag, can't be done in the grammar as it can't be checked
# until looked up in the context
_identifier_regex = re.compile(
    r"^(?:tree|plot|instance|user|species)\.(?:udf\:)?[\w '|]+$")


class Variable(Grammar):
    grammar = (G('"', WORD('^"'), '"') | G("'", WORD("^'"), "'")
               | WORD("a-zA-Z_", "a-zA-Z0-9_."))


class InlineEditGrammar(Grammar):
    grammar = (OR("field", "create", "search"), OPTIONAL(Variable),
               "from", Variable, OPTIONAL("for", Variable),
               OPTIONAL("in", Variable), "withtemplate", Variable)
    grammar_whitespace = True


_inline_edit_parser = InlineEditGrammar.parser()


def inline_edit_tag(tag, Node):
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

    If used by the alternate field name of "create" the tag will not look in
    the current template context for field values, and instead just give the
    default for that field.

    {% create "Width" from "plot.width" for user withtemplate "field.html" %}

    If used by the alternate field name of "search" the tag will behave
    similarly to "edit", but will also look up search parameters by field name
    from a required instance parameter

    {% search from field for user in instance withtemplate "index.html" %}

    To allow using the tag with models that are not Authorizable, the tag
    supports omitting the "for user" section.

    {% field "First" from "user.first_name" withtemplate "template.html" %}

    For simple use cases, the label can be omitted, in which case the
    translated help_text property (for Django fields) or the name (for UDFs) of
    the underlying field is provided as the label.

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

    Like the standard {% include %} tag, you can pass data into the template:

    {% field from "plot.width" withtemplate "plot.html" with units="inches" %}

    Which will be available in the template context:
        {{ field.value }} {{ units }}
    """
    def tag_parser(parser, token):
        try:
            results = _inline_edit_parser.parse_string(token.contents,
                                                       reset=True, eof=True)
        except ParseError as e:
            raise template.TemplateSyntaxError(
                'expected format: %s [{label}] from {model.property}'
                ' [for {user}] in {instance} withtemplate {template}, %s'
                % (tag, e.message))

        elems = results.elements

        label = _token_to_variable(elems[1].string if elems[1] else None)
        identifier = _token_to_variable(elems[3].string)
        user = _token_to_variable(elems[4][1].string if elems[4] else None)
        instance = _token_to_variable(elems[5][1].string if elems[5] else None)
        field_template = _token_to_variable(elems[7].string)

        return Node(label, identifier, user, field_template, instance)

    return tag_parser


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


class AbstractNode(template.Node):
    _field_mappings = {
        'IntegerField': 'int',
        'ForeignKey': 'int',
        'FloatField': 'float',
        'TextField': 'string',
        'CharField': 'string',
        'DateTimeField': 'date',
        'BooleanField': 'bool'
    }
    _valid_field_keys = ','.join([k for k, v in _field_mappings.iteritems()])

    def __init__(self, label, identifier, user, field_template, instance):
        self.label = label
        self.identifier = identifier
        self.user = user
        self.field_template = field_template
        self.instance = instance

    def get_additional_context(field, *args):
        return field  # Overriden in SearchNode

    def render(self, context):
        label = _resolve_variable(self.label, context)
        identifier = _resolve_variable(self.identifier, context)

        if not isinstance(identifier, basestring) or '.' not in identifier:
            raise template.TemplateSyntaxError(
                'expected a string with the format "model.property" '
                'to follow "from"')

        model_name, field_name = identifier.split('.')
        instance = _resolve_variable(self.instance, context)
        model = self.get_model(context, model_name, instance)
        user = _resolve_variable(self.user, context)
        field_template = get_template(_resolve_variable(
                                      self.field_template, context))

        if not _identifier_regex.match(identifier):
            raise template.TemplateSyntaxError(
                'expected a string with the format "model.property" '
                'to follow "from" %s' % identifier)

        def _udf_dict(model, field_name):
            return model.get_user_defined_fields()\
                .filter(name=field_name.replace('udf:', ''))[0]\
                .datatype_dict

        def _field_type_and_label(model, field_name, label):
            try:
                field = model._meta.get_field(field_name)
                field_type = field.get_internal_type()
                try:
                    field_type = FieldNode._field_mappings[field_type]
                except KeyError:
                    raise Exception('This template tag only supports %s not %s'
                                    % (FieldNode._valid_field_keys,
                                       field_type))
                label = label if label else field.help_text
            except FieldDoesNotExist:
                field_type = _udf_dict(model, field_name)['type']
                label = label if label else field_name.replace('udf:', '')

            return field_type, label

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
                val = model.udfs[udf_field_name]
                try:
                    choices = _udf_dict(model, udf_field_name)['choices']
                except KeyError:
                    choices = None
            else:
                raise ValueError('Could not find field: %s' % field_name)

            return val, choices

        if is_json_field_reference(field_name):
            field_value = get_attr_from_json_field(model, field_name)
            choices = None
            is_visible = is_editable = True
            data_type = "TextField"

        else:
            field_value, choices = _field_value_and_choices(model, field_name)
            data_type, label = _field_type_and_label(model, field_name, label)

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

        # TODO: Support pluggable formatting instead of unicode()
        display_val = unicode(field_value) if field_value is not None else None

        context['field'] = {
            'label': label,
            'identifier': identifier,
            'value': field_value,
            'display_value': display_val,
            'data_type': data_type,
            'is_visible': is_visible,
            'is_editable': is_editable,
            'choices': choices
        }
        self.get_additional_context(context['field'], identifier, instance)

        return field_template.render(context)


class FieldNode(AbstractNode):
    def get_model(self, context, model_name, instance=None):
        return context[model_name]


class CreateNode(AbstractNode):
    def get_model(self, context, model_name, instance=None):
        Model = safe_get_model_class(model_name.capitalize())

        return Model(instance=instance) if instance else Model()


class SearchNode(CreateNode):
    def get_additional_context(self, field, identifier, instance):
        json = next((json for json in instance.advanced_search_fields
                     if json['identifier'] == identifier), {})

        # Only overwrite field values when there is a new value
        field.update({key: value for key, value in json.iteritems()
                      if key not in field or value is not None})

        return field

register.tag('field', inline_edit_tag('field', FieldNode))
register.tag('create', inline_edit_tag('create', CreateNode))
register.tag('search', inline_edit_tag('search', SearchNode))
