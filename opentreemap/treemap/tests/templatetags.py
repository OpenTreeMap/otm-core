from django.template import Template, Context
from django.test import TestCase

import json

from treemap.audit import FieldPermission, Role
from treemap.udf import UserDefinedFieldDefinition
from treemap.models import User, Plot, InstanceUser
from treemap.tests import make_instance


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
        {% load audit_extras %}
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
            model_name='Plot', field_name='Test choice',
            permission_level=FieldPermission.NONE,
            role=self.role, instance=self.instance)
        udf_perm.save()

        plot = self.plot
        plot.udf_scalar_values['Test choice'] = 'b'

        def render():
            return Template(
                """
                {% load audit_extras %}
                {% usercanread plot the_key as w %}
                plot udf {{ w }}
                {% endusercanread %}
                """)\
                .render(Context({
                    'request': {'user': self.user},
                    'plot': plot,
                    'the_key': 'Test choice'})).strip()

        self.assertEqual(render(), '')

        udf_perm.permission_level = FieldPermission.READ_ONLY
        udf_perm.save()

        self.assertEqual(render(), 'plot udf b')


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
        {% load audit_extras %}
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
