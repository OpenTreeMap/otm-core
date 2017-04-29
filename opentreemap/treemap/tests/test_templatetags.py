# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import tempfile
import json
import os
from shutil import rmtree

from django.template import Template, Context, TemplateSyntaxError
from django.test.utils import override_settings
from django.contrib.auth.models import AnonymousUser

from treemap.audit import FieldPermission, Role
from treemap.json_field import set_attr_on_json_field
from treemap.templatetags.partial import PartialNode
from treemap.udf import UserDefinedFieldDefinition
from treemap.models import Plot, Tree, InstanceUser
from treemap.tests import (make_instance, make_observer_user,
                           make_commander_user, make_user, make_request,
                           make_conjurer_user, make_tweaker_user)
from treemap.tests.base import OTMTestCase
from treemap.templatetags.util import display_name


class UserCanReadTagTest(OTMTestCase):

    def setUp(self):
        self.instance = make_instance()

        self.user = make_user(username='user', password='user')

        self.role = Role(name='role', instance=self.instance, rep_thresh=0)
        self.role.save()

        self.user_perm, __ = FieldPermission.objects.get_or_create(
            model_name='Plot', field_name='width',
            permission_level=FieldPermission.NONE,
            role=self.role, instance=self.instance)

        iuser = InstanceUser(instance=self.instance, user=self.user,
                             role=self.role)
        iuser.save_with_user(self.user)

        inst_role = Role(name='inst def role',
                         instance=self.instance,
                         rep_thresh=0)
        inst_role.save()

        self.inst_perm, __ = FieldPermission.objects.get_or_create(
            model_name='Plot', field_name='width',
            permission_level=FieldPermission.NONE,
            role=inst_role, instance=self.instance)

        self.instance.default_role = inst_role
        self.instance.save()

        self.plot = Plot(instance=self.instance)

    basic_template = Template(
        """
        {% load auth_extras %}
        {% usercanread plot "width" as w %}
        plot width {{ w }}
        {% endusercanread %}
        """)

    def _render_basic_template_with_vars(self, user, plot):
        return UserCanReadTagTest.basic_template.render(
            Context({
                'request': {'user': user},
                'plot': plot})).strip()

    def test_works_with_empty_user_no_perm(self):
        self.assertEqual(
            self._render_basic_template_with_vars(None, self.plot), '')

    def test_works_with_empty_user_with_perm(self):
        perms = [FieldPermission.READ_ONLY,
                 FieldPermission.WRITE_WITH_AUDIT,
                 FieldPermission.WRITE_DIRECTLY]

        self.plot.width = 9

        for plevel in perms:
            self.inst_perm.permission_level = plevel
            self.inst_perm.save()

            self.assertEqual(
                self._render_basic_template_with_vars(None, self.plot),
                'plot width 9')

    def test_works_with_user_with_role_no_perm(self):
        self.assertEqual(
            self._render_basic_template_with_vars(self.user, self.plot), '')

    def test_works_with_user_with_role_with_perm(self):
        perms = [FieldPermission.READ_ONLY,
                 FieldPermission.WRITE_WITH_AUDIT,
                 FieldPermission.WRITE_DIRECTLY]

        self.plot.width = 9

        for plevel in perms:
            self.user_perm.permission_level = plevel
            self.user_perm.save()

            self.assertEqual(
                self._render_basic_template_with_vars(self.user, self.plot),
                'plot width 9')

    def test_works_with_udf(self):
        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'choice',
                                 'choices': ['a', 'b', 'c']}),
            iscollection=False,
            name='Test choice')

        udf_perm, __ = FieldPermission.objects.get_or_create(
            model_name='Plot', field_name='udf:Test choice',
            permission_level=FieldPermission.NONE,
            role=self.role, instance=self.instance)
        udf_perm.save()

        plot = self.plot
        plot.udfs['Test choice'] = 'b'

        def render():
            return Template(
                """
                {% load auth_extras %}
                {% usercanread plot the_key as w %}
                plot udf {{ w }}
                {% endusercanread %}
                """)\
                .render(Context({
                    'request': {'user': self.user},
                    'plot': plot,
                    'the_key': 'udf:Test choice'})).strip()

        self.assertEqual(render(), '')

        udf_perm.permission_level = FieldPermission.READ_ONLY
        udf_perm.save()

        self.assertEqual(render(), 'plot udf b')


class UserCanCreateTagTest(OTMTestCase):

    def setUp(self):
        self.instance = make_instance()
        self.plot = Plot(instance=self.instance)

    basic_template = Template(
        """
        {% load auth_extras %}
        {% usercancreate plot %}
        true
        {% endusercancreate %}
        """)

    def _render_basic_template_with_vars(self, user, plot):
        return UserCanCreateTagTest.basic_template.render(
            Context({
                'request': {'user': user},
                'plot': plot})).strip()

    def test_works_with_empty_user(self):
        self.assertEqual(
            self._render_basic_template_with_vars(None, self.plot), '')

    def test_works_with_anonymous_user(self):
        self.assertEqual(
            self._render_basic_template_with_vars(AnonymousUser, self.plot),
            '')

    def test_works_with_user_with_no_create_perms(self):
        user = make_tweaker_user(self.instance)
        self.assertEqual(
            self._render_basic_template_with_vars(user, self.plot), '')

    def test_works_with_user_with_create_perms(self):
        user = make_conjurer_user(self.instance)
        self.assertEqual(
            self._render_basic_template_with_vars(user, self.plot), 'true')


class UserContentTagTests(OTMTestCase):

    def setUp(self):
        self.instance = make_instance()

        self.user = make_user(username='someone', password='someone')

        self.public_user = make_user(username='public', password='public')

    def _render_template_with_user(self, template, req_user, content_user):
        return template.render(Context({
            'request': {'user': req_user},
            'user': content_user
        })).strip()

    def render_user_template(self, req_user, content_user):
        user_template = Template("""
        {% load auth_extras %}
        {% usercontent for user %}
        SECRETS!
        {% endusercontent %}
        """)
        return self._render_template_with_user(
            user_template, req_user, content_user)

    def render_username_template(self, req_user, content_user):
        username_template = Template("""
        {% load auth_extras %}
        {% usercontent for user.username %}
        SECRETS!
        {% endusercontent %}
        """)
        return self._render_template_with_user(
            username_template, req_user, content_user)

    def render_user_id_template(self, req_user, content_user):
        user_id_template = Template("""
        {% load auth_extras %}
        {% usercontent for user.pk %}
        SECRETS!
        {% endusercontent %}
        """)
        return self._render_template_with_user(
            user_id_template, req_user, content_user)

    def render_literal_username_template(self, req_user, content_user):
        literal_username_template = Template("""
        {% load auth_extras %}
        {% usercontent for "someone" %}
        SECRETS!
        {% endusercontent %}
        """)
        return self._render_template_with_user(
            literal_username_template, req_user, content_user)

    def render_literal_user_id_template(self, req_user, content_user):
        literal_username_template = Template("""
        {% load auth_extras %}
        {% usercontent for """ + str(content_user.pk) + """ %}
        SECRETS!
        {% endusercontent %}
        """)
        return self._render_template_with_user(
            literal_username_template, req_user, content_user)

    def test_username_in_tag_shows_content_to_user(self):
        self.assertEqual(
            self.render_username_template(self.user, self.user), 'SECRETS!')

    def test_username_in_tag_hides_content_from_others(self):
        self.assertEqual(
            self.render_username_template(self.public_user, self.user), '')

    def test_user_in_tag_shows_content_to_user(self):
        self.assertEqual(
            self.render_user_template(self.user, self.user), 'SECRETS!')

    def test_user_in_tag_hides_content_from_others(self):
        self.assertEqual(
            self.render_user_template(self.public_user, self.user), '')

    def test_user_id_in_tag_shows_content_to_user(self):
        self.assertEqual(
            self.render_user_id_template(self.user, self.user), 'SECRETS!')

    def test_user_id_in_tag_hides_content_from_others(self):
        self.assertEqual(
            self.render_user_id_template(self.public_user, self.user), '')

    def test_literal_username_in_tag_shows_content_to_user(self):
        content = self.render_literal_username_template(self.user, self.user)
        self.assertEqual(content, 'SECRETS!')

    def test_literal_username_in_tag_hides_content_from_others(self):
        content = self.render_literal_username_template(self.public_user,
                                                        self.user)
        self.assertEqual(content, '')

    def test_literal_user_id_in_tag_shows_content_to_user(self):
        content = self.render_literal_user_id_template(self.user, self.user)
        self.assertEqual(content, 'SECRETS!')

    def test_literal_user_id_in_tag_hides_content_from_others(self):
        content = self.render_literal_user_id_template(self.public_user,
                                                       self.user)
        self.assertEqual(content, '')


class LoginForwardingTests(OTMTestCase):

    def setUp(self):
        self.instance = make_instance()
        self.literal_template = Template(
            '{% load auth_extras %}{% login_forward %}')

    def render_template(self, template, path, instance=None):
        return template.render(Context({'request':
                               make_request(path=path, instance=instance)}))

    def test_request_has_instance(self):
        path = '/{}/anything/goes/'.format(self.instance.url_name)
        self.assertEqual(
            self.render_template(
                self.literal_template, path, self.instance),
            '?next=%2F{}%2Fanything%2Fgoes%2F'.format(
                self.instance.url_name))

    def test_request_path_redirect(self):
        path = '/users/anything/goes/'
        self.assertEqual(
            self.render_template(self.literal_template, path),
            '?next=%2Fusers%2Fanything%2Fgoes%2F')

        path = '/comments/anything/goes/'
        self.assertEqual(
            self.render_template(self.literal_template, path),
            '?next=%2Fcomments%2Fanything%2Fgoes%2F')

        path = '/create/'
        self.assertEqual(
            self.render_template(self.literal_template, path),
            '?next=%2Fcreate%2F')

    def test_default_redirect(self):
        path = '/anything/else/'
        self.assertEqual(
            self.render_template(self.literal_template, path), '')


@override_settings(TEMPLATE_LOADERS=(
    'django.template.loaders.filesystem.Loader',))
class InlineFieldTagTests(OTMTestCase):

    def setUp(self):
        self.instance = make_instance()
        self.instance.save()
        self.role = Role(name='role', instance=self.instance, rep_thresh=0)
        self.role.save()

        self.observer = make_observer_user(self.instance)

        self.udf_role = Role(name='udf', instance=self.instance, rep_thresh=0)
        self.udf_role.save()

        self.template_dir = tempfile.mkdtemp()
        self.template_file_path = os.path.join(self.template_dir,
                                               "field_template.html")

        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'choice',
                                 'choices': ["a", "b", "c"]}),
            iscollection=False,
            name='Test choice')

        udf_perm, __ = FieldPermission.objects.get_or_create(
            model_name='Plot', field_name='udf:Test choice',
            permission_level=FieldPermission.READ_ONLY,
            role=self.role, instance=self.instance)
        udf_perm.save()
        udf_write_perm, __ = FieldPermission.objects.get_or_create(
            model_name='Plot', field_name='udf:Test choice',
            permission_level=FieldPermission.WRITE_DIRECTLY,
            role=self.udf_role, instance=self.instance)
        udf_write_perm.save()

    def tearDown(self):
        rmtree(self.template_dir)

    def _form_template_with_request_user_for(self, identifier):
        field_name = '"' + identifier + '"'
        template_text = """{% load form_extras %}""" +\
            """{% field "Test Field" from """ + field_name +\
            """ for request.user withtemplate "field_template.html" %}"""
        return Template(template_text)

    def _form_template_for(self, identifier):
        field_name = '"' + identifier + '"'
        template_text = """{% load form_extras %}""" +\
            """{% field "Test Field" from """ + field_name +\
            """ withtemplate "field_template.html" %}"""
        return Template(template_text)

    def _form_template_labelless_with_request_user_for(self, identifier):
        field_name = '"' + identifier + '"'
        template_text = """{% load form_extras %}""" +\
            """{% field from """ + field_name +\
            """ for request.user withtemplate "field_template.html" %}"""
        return Template(template_text)

    def _form_template_labelless_for(self, identifier):
        field_name = '"' + identifier + '"'
        template_text = """{% load form_extras %}""" +\
            """{% field from """ + field_name +\
            """ withtemplate "field_template.html" %}"""
        return Template(template_text)

    def _form_template_create(self, identifier):
        field_name = '"' + identifier + '"'
        template_text = """{% load form_extras %}""" +\
            """{% create from """ + field_name +\
            """ in request.instance""" +\
            """ withtemplate "field_template.html" %}"""
        return Template(template_text)

    def _form_template_search(self):
        template_text = """{% load form_extras %}""" +\
            """{% search from search_json""" +\
            """ for request.user in request.instance """ +\
            """ withtemplate "field_template.html" %}"""
        return Template(template_text)

    def _write_field_template(self, text):
        with open(self.template_file_path, 'w') as f:
                f.write(text)

    def assert_plot_length_context_value(self, user, name, value,
                                         template_fn=None):
        if template_fn is None:
            template_fn = (self._form_template_with_request_user_for
                           if user else self._form_template_for)
        plot = Plot(length=12.3, instance=self.instance)
        plot.convert_to_display_units()

        template = template_fn('plot.length')
        self._write_field_template("{{" + name + "}}")
        with self.settings(TEMPLATE_DIRS=(self.template_dir,)):
            content = template.render(Context({
                'request': {'user': user, 'instance': self.instance},
                'plot': plot})).strip()
            self.assertEqual(content, value)

    def assert_search_context_value(self, user, name, value, search_json):
        template = self._form_template_search()
        self._write_field_template("{{" + name + "}}")
        with self.settings(TEMPLATE_DIRS=(self.template_dir,)):
            content = template.render(Context({
                'request': {'user': user, 'instance': self.instance},
                'search_json': search_json})).strip()
            self.assertEqual(content, value)

    def assert_plot_udf_context_value(self, user, name, value):
        self.assert_plot_udf_template(user, "{{" + name + "}}", value)

    def assert_plot_udf_template(self, user, template_text, value):
        plot = Plot(length=12.3, instance=self.instance)
        plot.udfs['Test choice'] = 'b'
        template = self._form_template_with_request_user_for(
            'plot.udf:Test choice')
        self._write_field_template(template_text)
        with self.settings(TEMPLATE_DIRS=(self.template_dir,)):
            content = template.render(Context({
                'request': {'user': user},
                'plot': plot})).strip()
            self.assertEqual(content, value)

    def test_sets_is_visible_to_true_if_user_is_not_specified(self):
        # A user without permissions would normaly not be able to
        # view the field, but using the tag without "for user" allows
        # anyone to get the rendered markup
        self.assert_plot_length_context_value(None, 'field.is_visible',
                                              'True')

    def test_sets_is_editable_to_true_if_user_is_not_specified(self):
        # A user without permissions would normaly not be able to
        # edit the field, but using the tag without "for user" allows
        # anyone to get the rendered markup
        self.assert_plot_length_context_value(None, 'field.is_editable',
                                              'True')

    def test_labelless_sets_is_visible_to_true_if_user_is_not_specified(self):
        # A user without permissions would normaly not be able to
        # view the field, but using the tag without "for user" allows
        # anyone to get the rendered markup
        self.assert_plot_length_context_value(
            None, 'field.is_visible', 'True',
            self._form_template_labelless_for)

    def test_sets_is_visible_to_false_for_user_without_perms(self):
        user = make_user(username='testuser')
        self.assert_plot_length_context_value(user, 'field.is_visible',
                                              'False')

    def test_sets_is_visible_to_true_for_user_with_perms(self):
        self.assert_plot_length_context_value(
            self.observer, 'field.is_visible', 'True')

    def test_sets_is_editable_to_false_for_user_without_perms(self):
        user = make_user(username='testuser')
        self.assert_plot_length_context_value(user, 'field.is_editable',
                                              'False')

    def test_sets_is_editable_to_true_for_user_with_perms(self):
        user = make_commander_user(self.instance)
        self.assert_plot_length_context_value(user, 'field.is_editable',
                                              'True')

    def test_udf_sets_is_visible_to_false_for_user_without_perms(self):
        user = make_user(username='testuser')
        self.assert_plot_udf_context_value(user, 'field.is_visible', 'False')

    def test_udf_sets_is_visible_to_true_for_user_with_perms(self):
        user = make_user(self.instance, username='udf_user',
                         make_role=lambda _: self.udf_role)
        self.assert_plot_udf_context_value(user, 'field.is_visible', 'True')

    def test_udf_sets_is_editable_to_false_for_user_without_perms(self):
        user = make_user(username='testuser')
        self.assert_plot_udf_context_value(user, 'field.is_editable', 'False')

    def test_udf_sets_is_editable_to_true_for_user_with_perms(self):
        user = make_user(self.instance, username='udf_user',
                         make_role=lambda _: self.udf_role)
        self.assert_plot_udf_context_value(user, 'field.is_editable', 'True')

    def test_sets_label(self):
        self.assert_plot_length_context_value(
            self.observer, 'field.label', 'Test Field')

    def test_sets_identifier(self):
        self.assert_plot_length_context_value(
            self.observer, 'field.identifier', 'plot.length')

    def test_sets_value(self):
        self.assert_plot_length_context_value(
            self.observer, 'field.value', '12,3')

    def test_sets_units(self):
        self.assert_plot_length_context_value(
            self.observer, 'field.units', 'in')

    def test_sets_digits(self):
        self.assert_plot_length_context_value(
            self.observer, 'field.digits', '1')

    def test_sets_display_value(self):
        self.assert_plot_length_context_value(
            self.observer, 'field.display_value', '12,3 in')

    PLOT_LENGTH_DISPLAY_DEFAULTS = {'plot':
                                    {'length': {'units': 'in', 'digits': 1}}}

    @override_settings(DISPLAY_DEFAULTS=PLOT_LENGTH_DISPLAY_DEFAULTS)
    def test_uses_custom_units_and_digits(self):
        set_attr_on_json_field(
            self.instance, 'config.value_display.plot.length.units', 'm')
        set_attr_on_json_field(
            self.instance, 'config.value_display.plot.length.digits', '3')
        self.assert_plot_length_context_value(
            self.observer, 'field.display_value', '0,312 m')

    def test_sets_data_type(self):
        self.assert_plot_length_context_value(
            self.observer, 'field.data_type', 'float')

    def test_sets_value_for_udf_field(self):
        self.assert_plot_udf_context_value(self.observer, 'field.value', 'b')

    def test_sets_display_value_for_udf_field(self):
        self.assert_plot_udf_context_value(
            self.observer, 'field.display_value', 'b')

    def test_sets_data_type_for_udf_field(self):
        self.assert_plot_udf_context_value(
            self.observer, 'field.data_type', 'choice')

    def test_sets_choices_for_udf_field(self):
        template_string = """
            {% for c in field.choices %}{{c.value}}-{% endfor %}"""
        self.assert_plot_udf_template(
            self.observer, template_string, '-a-b-c-')

    def test_sets_choices_to_empty_if_not_set(self):
        self.assert_plot_length_context_value(
            self.observer, 'field.choices', '[]')

    def test_labelless_sets_label_to_default(self):
        self.assert_plot_length_context_value(
            self.observer, 'field.label',
            Plot._meta.get_field('length').verbose_name,
            self._form_template_labelless_with_request_user_for)

    def test_labelless_sets_identifier(self):
        self.assert_plot_length_context_value(
            self.observer, 'field.identifier', 'plot.length',
            self._form_template_labelless_with_request_user_for)

    def test_create_uses_new_model(self):
        template = self._form_template_create('Plot.length')
        self._write_field_template("{{ field.value }}")

        with self.settings(TEMPLATE_DIRS=(self.template_dir,)):
            content = template.render(Context({
                'request': {'user': self.observer, 'instance': self.instance}
            })).strip()
            self.assertEqual(content, unicode(Plot().length))

    def test_search_uses_new_model(self):
        self.assert_search_context_value(
            self.observer, 'field.value', unicode(Plot().length),
            {'identifier': 'Plot.length'})

    def test_search_adds_field_config(self):
        search = {'identifier': 'Plot.length',
                  'label': 'testing',
                  'search_type': 'range',
                  'default': [0, 100]}
        self.assert_search_context_value(
            self.observer, 'field.identifier', 'plot.length', search)

        self.assert_search_context_value(
            self.observer, 'field.label', 'testing', search)

        self.assert_search_context_value(
            self.observer, 'field.search_type', 'range', search)

        self.assert_search_context_value(
            self.observer, 'field.default', '[0, 100]', search)

    def test_search_gets_default_label_when_none_given(self):
        self.assert_search_context_value(
            self.observer, 'field.label',
            unicode(Plot._meta.get_field('length').verbose_name),
            {'identifier': 'Plot.length', 'label': None})

    def test_search_fields_get_added_only_for_valid_json_matches(self):
        with self.assertRaises(TemplateSyntaxError):
            with self.settings(TEMPLATE_DIRS=(self.template_dir,)):
                self._write_field_template("{{ field.identifier }}")
                self._form_template_search().render(Context({
                    'request': {'user': self.observer,
                                'instance': self.instance},
                    'search_json': {'identifiers': 'Plot.width'}}
                )).strip()


class PartialTagTest(OTMTestCase):
    def _assert_renders_as(self, template_text, subdict_name, expected):
        context = Context({
            'mine': {'val': 'yes'},
            'yours': {'val': 'no'}
        })
        template = Template(template_text)
        partialNode = PartialNode(template, subdict_name)
        text = partialNode.render(context)
        self.assertEqual(text, expected)

    def test_template_can_reference_subdict_value(self):
        self._assert_renders_as("{{ val }}", 'mine', 'yes')

    def test_template_cannot_reference_dict_value(self):
        self._assert_renders_as("{{ yours }}", 'mine', '')


class DisplayValueTagTest(OTMTestCase):
    def test_display_value_converts_string_plot(self):
        self.assertEqual('Planting Site', display_name('Plot'))

    def test_display_value_converts_plot_model(self):
        self.assertEqual('Planting Site', display_name(Plot()))

    def test_display_value_converts_model_name(self):
        self.assertEqual('Tree', display_name(Tree()))
