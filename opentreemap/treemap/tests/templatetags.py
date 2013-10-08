# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.template import Template, Context, TemplateSyntaxError
from django.test import TestCase
from django.test.utils import override_settings
from django.contrib.auth.models import AnonymousUser

import unittest
import tempfile
import json
import os
from shutil import rmtree

from treemap.audit import FieldPermission, Role
from treemap.udf import UserDefinedFieldDefinition
from treemap.models import User, Plot, InstanceUser
from treemap.tests import (make_instance, make_observer_user,
                           make_commander_user, make_user)


class UserCanReadTagTest(TestCase):

    def setUp(self):
        self.instance = make_instance()

        self.user = User(username='user', password='user')
        self.user.save()

        self.role = Role(name='role', instance=self.instance, rep_thresh=0)
        self.role.save()

        self.user_perm, _ = FieldPermission.objects.get_or_create(
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

        self.inst_perm, _ = FieldPermission.objects.get_or_create(
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

        udf_perm, _ = FieldPermission.objects.get_or_create(
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


class UserCanCreateTagTest(TestCase):

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
        user = make_observer_user(self.instance)
        self.assertEqual(
            self._render_basic_template_with_vars(user, self.plot), '')

    def test_works_with_user_with_create_perms(self):
        user = make_commander_user(self.instance)
        self.assertEqual(
            self._render_basic_template_with_vars(user, self.plot), 'true')


class UserContentTagTests(TestCase):

    def setUp(self):
        self.instance = make_instance()

        self.user = User(username='someone', password='someone')
        self.user.save()

        self.public_user = User(username='public', password='public')
        self.public_user.save()

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


@override_settings(TEMPLATE_LOADERS=(
    'django.template.loaders.filesystem.Loader',))
class InlineFieldTagTests(TestCase):

    def setUp(self):
        self.instance = make_instance()
        self.instance.config['advanced_search_fields'] = {}
        self.instance.save()
        self.role = Role(name='role', instance=self.instance, rep_thresh=0)
        self.role.save()

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

        udf_perm, _ = FieldPermission.objects.get_or_create(
            model_name='Plot', field_name='udf:Test choice',
            permission_level=FieldPermission.READ_ONLY,
            role=self.role, instance=self.instance)
        udf_perm.save()
        udf_write_perm, _ = FieldPermission.objects.get_or_create(
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
            """ withtemplate "field_template.html" %}"""
        return Template(template_text)

    def _form_template_search(self, identifier):
        template_text = """{% load form_extras %}""" +\
            """{% search from""" +\
            """ request.instance.advanced_search_fields.standard.0""" +\
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
        template = template_fn('plot.length')
        self._write_field_template("{{" + name + "}}")
        with self.settings(TEMPLATE_DIRS=(self.template_dir,)):
            content = template.render(Context({
                'request': {'user': user, 'instance': self.instance},
                'plot': plot})).strip()
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
        user = User(username='testuser')
        self.assert_plot_length_context_value(user, 'field.is_visible',
                                              'False')

    def test_sets_is_visible_to_true_for_user_with_perms(self):
        user = make_observer_user(self.instance)
        self.assert_plot_length_context_value(user, 'field.is_visible',
                                              'True')

    def test_sets_is_editable_to_false_for_user_without_perms(self):
        user = User(username='testuser')
        self.assert_plot_length_context_value(user, 'field.is_editable',
                                              'False')

    def test_sets_is_editable_to_true_for_user_with_perms(self):
        user = make_commander_user(self.instance)
        self.assert_plot_length_context_value(user, 'field.is_editable',
                                              'True')

    def test_udf_sets_is_visible_to_false_for_user_without_perms(self):
        user = User(username='testuser')
        self.assert_plot_udf_context_value(user, 'field.is_visible', 'False')

    def test_udf_sets_is_visible_to_true_for_user_with_perms(self):
        user = make_user(self.instance, username='udf_user',
                         make_role=lambda _: self.udf_role)
        self.assert_plot_udf_context_value(user, 'field.is_visible', 'True')

    def test_udf_sets_is_editable_to_false_for_user_without_perms(self):
        user = User(username='testuser')
        self.assert_plot_udf_context_value(user, 'field.is_editable', 'False')

    def test_udf_sets_is_editable_to_true_for_user_with_perms(self):
        user = make_user(self.instance, username='udf_user',
                         make_role=lambda _: self.udf_role)
        self.assert_plot_udf_context_value(user, 'field.is_editable', 'True')

    def test_sets_label(self):
        user = make_observer_user(self.instance)
        self.assert_plot_length_context_value(user, 'field.label',
                                              'Test Field')

    def test_sets_identifier(self):
        user = make_observer_user(self.instance)
        self.assert_plot_length_context_value(user, 'field.identifier',
                                              'plot.length')

    def test_sets_value(self):
        user = make_observer_user(self.instance)
        self.assert_plot_length_context_value(user, 'field.value', '12.3')

    def test_sets_display_value(self):
        user = make_observer_user(self.instance)
        self.assert_plot_length_context_value(user, 'field.display_value',
                                              '12.3')

    def test_sets_data_type(self):
        user = make_observer_user(self.instance)
        self.assert_plot_length_context_value(user, 'field.data_type', 'float')

    def test_sets_value_for_udf_field(self):
        user = make_observer_user(self.instance)
        self.assert_plot_udf_context_value(user, 'field.value', 'b')

    def test_sets_display_value_for_udf_field(self):
        user = make_observer_user(self.instance)
        self.assert_plot_udf_context_value(user, 'field.display_value', 'b')

    def test_sets_data_type_for_udf_field(self):
        user = make_observer_user(self.instance)
        self.assert_plot_udf_context_value(user, 'field.data_type', 'choice')

    def test_sets_choices_for_udf_field(self):
        user = make_observer_user(self.instance)
        template_string = """
            {% for c in field.choices %}{{c.value}}-{% endfor %}"""
        self.assert_plot_udf_template(user, template_string, '-a-b-c-')

    def test_sets_choices_to_none_for_normal_field(self):
        user = make_observer_user(self.instance)
        self.assert_plot_length_context_value(user, 'field.choices', 'None')

    def test_labelless_sets_label_to_default(self):
        user = make_observer_user(self.instance)
        self.assert_plot_length_context_value(
            user, 'field.label', Plot._meta.get_field('length').help_text,
            self._form_template_labelless_with_request_user_for)

    def test_labelless_sets_identifier(self):
        user = make_observer_user(self.instance)
        self.assert_plot_length_context_value(
            user, 'field.identifier', 'plot.length',
            self._form_template_labelless_with_request_user_for)

    def test_create_uses_new_model(self):
        user = make_observer_user(self.instance)
        self.assert_plot_length_context_value(
            user, 'field.value', unicode(Plot().length),
            self._form_template_create)

    def test_search_uses_new_model(self):
        user = make_observer_user(self.instance)
        self.instance.config['advanced_search_fields'] = {
            'standard': [
                {'identifier': 'plot.length'}
            ]
        }
        self.assert_plot_length_context_value(
            user, 'field.value', unicode(Plot().length),
            self._form_template_search)

    def test_search_adds_field_config(self):
        user = make_observer_user(self.instance)
        self.instance.config['advanced_search_fields'] = {
            'standard': [
                {'identifier': 'plot.length',
                 'label': 'testing',
                 'search_type': 'range',
                 'default': [0, 100]}
            ]
        }
        self.assert_plot_length_context_value(
            user, 'field.identifier', 'plot.length',
            self._form_template_search)

        self.assert_plot_length_context_value(
            user, 'field.label', 'testing',
            self._form_template_search)

        self.assert_plot_length_context_value(
            user, 'field.search_type', 'range',
            self._form_template_search)

        self.assert_plot_length_context_value(
            user, 'field.default', '[0, 100]',
            self._form_template_search)

    def test_search_gets_default_label_when_none_given(self):
        user = make_observer_user(self.instance)
        self.instance.config['advanced_search_fields'] = {
            'standard': [
                {'identifier': 'plot.length',
                 'label': None}
            ]
        }
        self.assert_plot_length_context_value(
            user, 'field.label',
            unicode(Plot._meta.get_field('length').help_text),
            self._form_template_search)

    def test_search_fields_get_added_only_for_valid_json_matches(self):
        user = make_observer_user(self.instance)
        self.instance.config['advanced_search_fields'] = {
            'standard': [
                {'identifiers': 'plot.width'}
            ]
        }
        with self.assertRaises(TemplateSyntaxError):
            with self.settings(TEMPLATE_DIRS=(self.template_dir,)):
                self._write_field_template("{{ field.identifier }}")
                self._form_template_search(None).render(Context({
                    'request': {'user': user, 'instance': self.instance}}
                )).strip()


class DiameterTagsTest(unittest.TestCase):
    def setUp(self):
        self.template = Template("{% load diameter %}"
                                 "{{ value|to_circumference }}")

    def test_none_yields_none(self):
        """
        Test that a None value will return the empty string.

        This test is in response to a bug observed in github issue #463
        """
        rt = self.template.render(Context({'value': None}))
        self.assertEqual(rt, '')
