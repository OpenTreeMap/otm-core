# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import re
from modgrammar import Grammar, OPTIONAL, G, WORD, OR, ParseError

from django import template
from django.template.loader import get_template
from django.core.exceptions import ObjectDoesNotExist
from django.utils import dateformat
from django.conf import settings

from treemap.util import safe_get_model_class
from treemap.json_field import (is_json_field_reference,
                                get_attr_from_json_field)
from treemap.units import (get_digits, get_units, is_formattable,
                           is_convertible_or_formattable, is_convertible,
                           get_display_value)

register = template.Library()

# Used to check that the identifier follows the format model.field or
# model.udf:field name, can't be done in the grammar as it can't be checked
# until looked up in the context
_identifier_regex = re.compile(
    r"^[a-zA-Z_.\-]+(?:udf\:[\w '\._-]+|[a-zA-Z_\-]+)$")


class Variable(Grammar):
    grammar = (G(b'"', WORD(b'^"'), b'"') | G(b"'", WORD(b"^'"), b"'")
               | WORD(b"a-zA-Z_", b"a-zA-Z0-9_."))


class InlineEditGrammar(Grammar):
    grammar = (OR(G(OR(b"field", b"create"), OPTIONAL(Variable)), b"search"),
               b"from", Variable, OPTIONAL(b"for", Variable),
               OPTIONAL(b"in", Variable), b"withtemplate", Variable)
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
    similarly to "edit", but will get it's label and identifier from a
    dictionary, and pass along any other values in the dictionary to the
    template as part of the field object.

    {% search from dict for user in instance withtemplate "index.html" %}

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

        one_or_none = lambda e: e[1].string if e else None

        label = _token_to_variable(
            elems[0][1].string
            if len(elems[0].elements) > 1 and elems[0][1]
            else None)
        identifier = _token_to_variable(elems[2].string)
        user = _token_to_variable(one_or_none(elems[3]))
        instance = _token_to_variable(one_or_none(elems[4]))
        field_template = _token_to_variable(elems[6].string)

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
        'AutoField': 'int',
        'FloatField': 'float',
        'TextField': 'string',
        'CharField': 'string',
        'DateTimeField': 'date',
        'DateField': 'date',
        'BooleanField': 'bool'
    }
    _valid_field_keys = ','.join([k for k, v in _field_mappings.iteritems()])

    def __init__(self, label, identifier, user, field_template, instance):
        self.label = label
        self.identifier = identifier
        self.user = user
        self.instance = instance
        self.field_template = field_template

    # Overriden in SearchNode
    def resolve_label_and_identifier(self, context):
        label = _resolve_variable(self.label, context)
        identifier = _resolve_variable(self.identifier, context)

        return label, identifier

    # Overriden in SearchNode
    def get_additional_context(self, field, *args):
        return field

    def render(self, context):
        label, identifier = self.resolve_label_and_identifier(context)
        user = _resolve_variable(self.user, context)
        instance = _resolve_variable(self.instance, context)
        field_template = get_template(_resolve_variable(
                                      self.field_template, context))

        if not isinstance(identifier, basestring)\
           or not _identifier_regex.match(identifier):
            raise template.TemplateSyntaxError(
                'expected a string with the format "model.property" '
                'to follow "from" %s' % identifier)

        model_name, field_name = identifier.split('.', 1)
        model = self.get_model(context, model_name, instance)

        def _is_udf(model, udf_field_name):
            return (hasattr(model, 'udf_field_names') and
                    udf_field_name in model.udf_field_names)

        def _udf_dict(model, field_name):
            return model.get_user_defined_fields()\
                .filter(name=field_name.replace('udf:', ''))[0]\
                .datatype_dict

        def _field_type_label_choices(model, field_name, label):
            choices = None
            udf_field_name = field_name.replace('udf:', '')
            if not _is_udf(model, udf_field_name):
                field = model._meta.get_field(field_name)
                field_type = field.get_internal_type()
                try:
                    field_type = FieldNode._field_mappings[field_type]
                except KeyError:
                    raise Exception('This template tag only supports %s not %s'
                                    % (FieldNode._valid_field_keys,
                                       field_type))
                label = label if label else field.help_text
                choices = [{'value': choice[0], 'display_value': choice[1]}
                           for choice in field.choices]
                if choices and field.null:
                    choices = [{'value': '', 'display_value': ''}] + choices
            else:
                udf_dict = _udf_dict(model, field_name)
                field_type = udf_dict['type']
                label = label if label else udf_field_name
                if 'choices' in udf_dict:
                    values = [''] + udf_dict['choices']
                    choices = [{'value': value, 'display_value': value}
                               for value in values]

            return field_type, label, choices

        def _field_value(model, field_name):
            udf_field_name = field_name.replace('udf:', '')
            if field_name in model._meta.get_all_field_names():
                try:
                    val = getattr(model, field_name)
                except ObjectDoesNotExist:
                    val = None
            elif _is_udf(model, udf_field_name):
                val = model.udfs[udf_field_name]
            else:
                raise ValueError('Could not find field: %s' % field_name)

            return val

        if is_json_field_reference(field_name):
            field_value = get_attr_from_json_field(model, field_name)
            choices = None
            is_visible = is_editable = True
            data_type = "string"
        else:
            field_value = _field_value(model, field_name)
            data_type, label, choices = _field_type_label_choices(
                model, field_name, label)

            if user is not None and hasattr(model, 'field_is_visible'):
                is_visible = model.field_is_visible(user, field_name)
                is_editable = model.field_is_editable(user, field_name)
            else:
                # This tag can be used without specifying a user. In that case
                # we assume that the content is visible and upstream code is
                # responsible for only showing the content to the appropriate
                # user
                is_visible = True
                is_editable = True

        digits = (get_digits(model.instance, model_name, field_name)
                  if is_formattable(model_name, field_name) else '')

        units = ''
        if is_convertible(model_name, field_name):
            units = get_units(model.instance, model_name, field_name)

        if field_value is None:
            display_val = None
        elif data_type == 'date' and model.instance:
            display_val = dateformat.format(field_value,
                                            model.instance.short_date_format)
        elif data_type == 'date':
            display_val = dateformat.format(field_value,
                                            settings.SHORT_DATE_FORMAT)
        elif is_convertible_or_formattable(model_name, field_name):
            field_value, display_val = get_display_value(
                model.instance, model_name, field_name, field_value)
            if units is not '':
                display_val += (' %s' % units)
        else:
            display_val = unicode(field_value)

        context['field'] = {
            'label': label,
            'identifier': identifier,
            'value': field_value,
            'display_value': display_val,
            'units': units,
            'digits': digits,
            'data_type': data_type,
            'is_visible': is_visible,
            'is_editable': is_editable,
            'choices': choices
        }
        self.get_additional_context(context['field'])

        return field_template.render(context)


class FieldNode(AbstractNode):
    def get_model(self, context, model_name, instance=None):
        return context[model_name]


class CreateNode(AbstractNode):
    def get_model(self, _, model_name, instance=None):
        Model = safe_get_model_class(model_name.capitalize())

        if instance and hasattr(Model, 'instance'):
            return Model(instance=instance)
        else:
            return Model()


class SearchNode(CreateNode):
    def __init__(self, _, identifier, user, template, instance):
        super(SearchNode, self).__init__(None, None, user, template, instance)
        self.json = identifier

    def resolve_label_and_identifier(self, context):
        self.search_json = _resolve_variable(self.json, context)
        label = self.search_json.get('label')
        identifier = self.search_json.get('identifier')

        return label, identifier

    def get_additional_context(self, field):
        field.update({k: v for k, v in self.search_json.items()
                      if v is not None})
        return field

register.tag('field', inline_edit_tag('field', FieldNode))
register.tag('create', inline_edit_tag('create', CreateNode))
register.tag('search', inline_edit_tag('search', SearchNode))
