# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
import re
from modgrammar import Grammar, OPTIONAL, G, WORD, OR, ParseError

from django import template
from django.template.loader import get_template
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.utils import dateformat
from django.utils.translation import ugettext as _
from django.conf import settings

from opentreemap.util import dotted_split

from treemap.util import get_model_for_instance, to_object_name, num_format
from treemap.json_field import (is_json_field_reference,
                                get_attr_from_json_field)
from treemap.units import (get_digits_if_formattable, get_units_if_convertible,
                           is_convertible_or_formattable, format_value,
                           get_unit_abbreviation)

register = template.Library()

# Used to check that the identifier follows the format model.field or
# model.udf:field name, can't be done in the grammar as it can't be checked
# until looked up in the context
#
# We are being a little looser with our restrictions on UDF names here than
# we are in the UDFD validation methods.  This regex is a sanity check, so it
# is not essential that we are 100% accurate here
_identifier_regex = re.compile(
    r"^[a-zA-Z_.\-]+(?:udf\:.+|[a-zA-Z0-9_\-]+)$")

FIELD_MAPPINGS = {
    'IntegerField': 'int',
    'ForeignKey': 'foreign_key',
    'OneToOneField': 'int',
    'AutoField': 'int',
    'FloatField': 'float',
    'TextField': 'long_string',
    'CharField': 'string',
    'DateTimeField': 'datetime',
    'DateField': 'date',
    'BooleanField': 'bool',
    'NullBooleanField': 'bool',
    'FileField': 'string',
    'PointField': 'point',
    'MultiPolygonField': 'multipolygon',
}

FOREIGN_KEY_PREDICATE = 'IS'

VALID_FIELD_KEYS = ','.join(FIELD_MAPPINGS.keys())


class Variable(Grammar):
    grammar = (G(b'"', WORD(b'^"'), b'"') | G(b"'", WORD(b"^'"), b"'")
               | WORD(b"a-zA-Z_", b"a-zA-Z0-9_."))


class Label(Grammar):
    grammar = (G(b'_("', WORD(b'^"'), b'")') | G(b"_('", WORD(b"^'"), b"')")
               | Variable)


class InlineEditGrammar(Grammar):
    grammar = (OR(G(OR(b"field", b"create"), OPTIONAL(Label)), b"search"),
               b"from", Variable, OPTIONAL(b"for", Variable),
               OPTIONAL(b"in", Variable), b"withtemplate", Variable,
               OPTIONAL(b"withhelp", Label))
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
    Note that the model name part of the identifier must match the class name
    and is case-sensitive

    {% create "Width" from "Plot.width" for user withtemplate "field.html" %}

    If used by the alternate field name of "search" the tag will behave
    similarly to "edit", but will get its label and identifier from a
    dictionary, and pass along any other values in the dictionary to the
    template as part of the field object.

    {% search from dict for user in instance withtemplate "index.html" %}

    To allow using the tag with models that are not Authorizable, the tag
    supports omitting the "for user" section.

    {% field "First" from "user.first_name" withtemplate "template.html" %}

    For simple use cases, the label can be omitted, in which case the
    translated verbose_name property (for Django fields) or the name (for UDFs)
    of the underlying field is provided as the label.

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
        help_text = _token_to_variable(one_or_none(elems[7]))

        return Node(label, identifier, user, field_template, instance,
                    help_text)

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


def _is_udf(model, udf_field_name):
    return (hasattr(model, 'udf_field_names') and
            udf_field_name in model.udf_field_names)


def _udf_dict(model, field_name):
    matches = [field.datatype_dict
               for field in model.get_user_defined_fields()
               if field.name == field_name.replace('udf:', '')]
    if matches:
        return matches[0]
    else:
        raise Exception("Datatype for field %s not found" % field_name)


# Should a blank choice be added for choice and multichoice fields?
ADD_BLANK_ALWAYS = 0
ADD_BLANK_NEVER = 1
ADD_BLANK_IF_CHOICE_FIELD = 2


def field_type_label_choices(model, field_name, label=None,
                             explanation=None,
                             add_blank=ADD_BLANK_IF_CHOICE_FIELD):
    choices = None
    udf_field_name = field_name.replace('udf:', '')
    if not _is_udf(model, udf_field_name):
        field = model._meta.get_field(field_name)
        field_type = field.get_internal_type()
        try:
            field_type = FIELD_MAPPINGS[field_type]
        except KeyError:
            raise Exception('This template tag only supports %s not %s'
                            % (VALID_FIELD_KEYS,
                               field_type))
        label = label if label else field.verbose_name
        explanation = explanation if explanation else field.help_text
        choices = [{'value': choice[0], 'display_value': choice[1]}
                   for choice in field.choices]
        if choices and field.null:
            choices = [{'value': '', 'display_value': ''}] + choices
    else:
        udf_dict = _udf_dict(model, field_name)
        field_type = udf_dict['type']
        label = label if label else udf_field_name
        if 'choices' in udf_dict:
            choices = [{'value': value, 'display_value': value}
                       for value in udf_dict['choices']]
            if add_blank == ADD_BLANK_ALWAYS or (
                add_blank == ADD_BLANK_IF_CHOICE_FIELD and
                field_type == 'choice'
            ):
                choices.insert(0, {'value': "", 'display_value': ""})

    return field_type, label, explanation, choices


class AbstractNode(template.Node):
    def __init__(self, label, identifier, user, field_template, instance,
                 explanation):
        self.label = label
        self.identifier = identifier
        self.user = user
        self.instance = instance
        self.field_template = field_template
        self.explanation = explanation

    # Overriden in SearchNode
    def resolve_label_and_identifier(self, context):
        label = _resolve_variable(self.label, context)
        identifier = _resolve_variable(self.identifier, context)

        return label, identifier

    # Overriden in SearchNode
    def get_additional_context(self, field, *args):
        return field

    # Overriden in SearchNode
    @property
    def treat_multichoice_as_choice(self):
        return False

    def render(self, context):
        explanation = _resolve_variable(self.explanation, context)
        label, identifier = self.resolve_label_and_identifier(context)
        user = _resolve_variable(self.user, context)
        instance = _resolve_variable(self.instance, context)
        field_template = get_template(_resolve_variable(
                                      self.field_template, context)).template

        if not isinstance(identifier, basestring)\
           or not _identifier_regex.match(identifier):
            raise template.TemplateSyntaxError(
                'expected a string with the format "object_name.property" '
                'to follow "from" %s' % identifier)

        model_name_or_object_name, field_name = dotted_split(identifier, 2,
                                                             maxsplit=1)
        model = self.get_model(context, model_name_or_object_name, instance)

        object_name = to_object_name(model_name_or_object_name)

        identifier = "%s.%s" % (object_name, field_name)

        def _field_value(model, field_name, data_type):
            udf_field_name = field_name.replace('udf:', '')
            val = None
            if field_name in [f.name for f in model._meta.get_fields()]:
                try:
                    val = getattr(model, field_name)
                except (ObjectDoesNotExist, AttributeError):
                    pass
            elif _is_udf(model, udf_field_name):
                if udf_field_name in model.udfs:
                    val = model.udfs[udf_field_name]
                    # multichoices place a json serialized data-value
                    # on the dom element and client-side javascript
                    # processes it into a view table and edit widget
                    if data_type == 'multichoice':
                        val = json.dumps(val)
                elif data_type == 'multichoice':
                    val = '[]'
            else:
                raise ValueError('Could not find field: %s' % field_name)

            return val

        if is_json_field_reference(field_name):
            field_value = get_attr_from_json_field(model, field_name)
            choices = None
            is_visible = is_editable = True
            data_type = "string"
        else:
            add_blank = (ADD_BLANK_ALWAYS if self.treat_multichoice_as_choice
                         else ADD_BLANK_IF_CHOICE_FIELD)
            data_type, label, explanation, choices = field_type_label_choices(
                model, field_name, label, explanation=explanation,
                add_blank=add_blank)
            field_value = _field_value(model, field_name, data_type)

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

        digits = units = ''

        if hasattr(model, 'instance'):
            digits = get_digits_if_formattable(
                model.instance, object_name, field_name)

            units = get_units_if_convertible(
                model.instance, object_name, field_name)
            if units != '':
                units = get_unit_abbreviation(units)

        if data_type == 'foreign_key':
            # rendered clientside
            display_val = ''
        elif field_value is None:
            display_val = None
        elif data_type in ['date', 'datetime']:
            fmt = (model.instance.short_date_format if model.instance
                   else settings.SHORT_DATE_FORMAT)
            display_val = dateformat.format(field_value, fmt)
        elif is_convertible_or_formattable(object_name, field_name):
            display_val = format_value(
                model.instance, object_name, field_name, field_value)
            if units != '':
                display_val += (' %s' % units)
        elif data_type == 'bool':
            display_val = _('Yes') if field_value else _('No')
        elif data_type == 'multichoice':
            # this is rendered clientside from data attributes so
            # there's no meaningful intermediate value to send
            # without rendering the same markup server-side.
            display_val = None
        elif choices:
            display_vals = [choice['display_value'] for choice in choices
                            if choice['value'] == field_value]
            display_val = display_vals[0] if display_vals else field_value
        elif data_type == 'float':
            display_val = num_format(field_value)
        else:
            display_val = unicode(field_value)

        context['field'] = {
            'label': label,
            'explanation': explanation,
            'identifier': identifier,
            'value': field_value,
            'display_value': display_val,
            'units': units,
            'digits': digits,
            'data_type': data_type,
            'is_visible': is_visible,
            'is_editable': is_editable,
            'choices': choices,
        }
        self.get_additional_context(
            context['field'], model, field_name, context.get('q', ''))

        return field_template.render(context)


class FieldNode(AbstractNode):
    def get_model(self, context, object_name, instance=None):
        return context[object_name]


class CreateNode(AbstractNode):
    def get_model(self, __, object_name, instance=None):
        return get_model_for_instance(object_name, instance)


class SearchNode(CreateNode):
    def __init__(self, __, identifier, user, template, instance, explanation):
        super(SearchNode, self).__init__(None, None, user, template, instance,
                                         explanation)
        self.json = identifier

    def resolve_label_and_identifier(self, context):
        self.search_json = _resolve_variable(self.json, context)
        label = self.search_json.get('label')
        identifier = self.search_json.get('identifier')

        return label, identifier

    def _fill_in_typeahead(self, field, field_name, model, search_query):
        def get_search_query_value(column, display, identifier,
                                   related_class, search_query):
            if not search_query:
                return ''
            search_map = json.loads(search_query) or {}
            model_name, field_name = tuple(dotted_split(
                identifier, 2, maxsplit=1))
            search_field = '{}.{}'.format(model_name, column)
            pred = search_map.get(search_field)
            if not pred:
                return ''

            query_value = pred[FOREIGN_KEY_PREDICATE]
            related_model = related_class.objects.get(id=query_value)
            return getattr(related_model, display)

        relation_lookup_infos = {
            'treemap.models.User': {
                # /<instance>/users/?q=<query> returns JSON
                # with a list of objects with properties
                # `username`, `first_name`, and `last_name`.
                # This corresponds to a JavaScript
                # `otmTypeahead` widget for looking up users
                # by username. The widget requires a wildcard
                # to tell it where to put the query param.
                # The wildcard defined in the JavaScript is `'%Q%'`.
                'url': reverse(
                    'users', kwargs={
                        'instance_url_name': model.instance.url_name
                    }
                ) + '?q=%Q%',
                'placeholder': _('Please type a username'),
                'display': 'username'
            }
        }
        field_instance = model._meta.get_field(field_name)
        related_model = field_instance.related_model
        model_name = '{}.{}'.format(
            related_model.__module__, related_model.__name__)
        info = relation_lookup_infos.get(model_name)
        if info:
            display = info['display']
            field['typeahead_url'] = info['url']
            field['placeholder'] = info['placeholder']
            field['display'] = display
            field['qualifier'] = field_name
            field['column'] = field_instance.column

            if search_query:
                field['display_value'] = get_search_query_value(
                    field_instance.column, display,
                    field['identifier'], related_model, search_query)

    def get_additional_context(self, field, model, field_name, search_query):
        def update_field(settings):
            # Identifier is lower-cased above to match the calling convention
            # of update endpoints, so we shouldn't overwrite it :(
            field.update({k: v for k, v in settings.items()
                          if v is not None and k != 'identifier'})

        search_settings = getattr(model, 'search_settings', {}).get(field_name)
        if search_settings:
            update_field(search_settings)

        update_field(self.search_json)

        data_type = field['data_type']
        if 'search_type' not in field:
            if data_type in {'int', 'float', 'date', 'datetime'}:
                field['search_type'] = 'RANGE'
            elif data_type in {'long_string', 'string', 'multichoice'}:
                field['search_type'] = 'LIKE'
            elif data_type == 'foreign_key':
                field['search_type'] = FOREIGN_KEY_PREDICATE
                self._fill_in_typeahead(field, field_name, model, search_query)
            else:
                field['search_type'] = 'IS'

        if data_type == 'multichoice':
            field['data_type'] = 'choice'
            # Choices will be used to search multichoice values (stored as
            # JSON) using a LIKE query. Add quotes around the choice values
            # so e.g. a search for "car" will match "car" but not "carp".
            for choice in field['choices']:
                if choice['value']:
                    choice['value'] = '"%s"' % choice['value']

        return field

    @property
    def treat_multichoice_as_choice(self):
        # When used for searching, multichoice and choice fields act the same
        return True

register.tag('field', inline_edit_tag('field', FieldNode))
register.tag('create', inline_edit_tag('create', CreateNode))
register.tag('search', inline_edit_tag('search', SearchNode))
register.filter('to_object_name', to_object_name)
