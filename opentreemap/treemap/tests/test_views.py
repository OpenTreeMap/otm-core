# -*- coding: utf-8 -*-


import os
import json
from io import StringIO
import psycopg2

from django.test.utils import override_settings
from django.test.client import RequestFactory
from django.http import Http404, HttpResponse
from django.core.exceptions import ValidationError
from django.db import connection
from django.core import mail
from django.template.loader import get_template

from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import Point

from treemap import ecobackend
from treemap.decorators import return_400_if_validation_errors
from treemap.json_field import set_attr_on_json_field
from treemap.udf import UserDefinedFieldDefinition
from treemap.audit import (Audit, approve_or_reject_audit_and_apply,
                           add_default_permissions, AuthorizeException)
from treemap.models import (Instance, Species, User, Plot, Tree, TreePhoto,
                            InstanceUser, StaticPage, ITreeRegion, Boundary)
from treemap.routes import (root_settings_js, instance_settings_js,
                            instance_user_page)

from treemap.lib.external_link import validate_token_template
from treemap.instance import PERMISSION_VIEW_EXTERNAL_LINK
from treemap.lib.tree import add_tree_photo_helper
from treemap.lib.user import get_user_instances
from treemap.views.misc import (public_instances_geojson, species_list,
                                boundary_autocomplete, boundary_to_geojson,
                                edits, compile_scss, static_page,
                                add_anonymous_boundary)
from treemap.views.map_feature import (update_map_feature, delete_map_feature,
                                       rotate_map_feature_photo, plot_detail,
                                       delete_photo)
from treemap.views.user import (user_audits, upload_user_photo, update_user,
                                forgot_username, user, users)
from manage_treemap.views.photo import approve_or_reject_photos
from treemap.views.tree import delete_tree
from treemap.tests import (ViewTestCase, make_instance, make_officer_user,
                           make_commander_user, make_apprentice_user,
                           make_simple_boundary, make_request, make_user,
                           set_write_permissions, MockSession,
                           set_read_permissions, make_tweaker_user,
                           make_plain_user, LocalMediaTestCase, media_dir,
                           make_instance_user, set_invisible_permissions,
                           make_observer_role, make_anonymous_boundary)
from treemap.tests.base import OTMTestCase
from treemap.tests.test_udfs import make_collection_udf


class InstanceValidationTest(OTMTestCase):

    def setUp(self):

        p = Point(-8515941.0, 4953519.0)

        self.instance1 = Instance(name='i1', geo_rev=0, center=p)
        self.instance1.seed_with_dummy_default_role()
        self.instance1.save()

        self.instance2 = Instance(name='i2', geo_rev=0, center=p)
        self.instance2.seed_with_dummy_default_role()
        self.instance2.save()


class StaticPageViewTest(ViewTestCase):
    def setUp(self):
        super(StaticPageViewTest, self).setUp()

        self.staticPage = StaticPage(content="content",
                                     name="faq",
                                     instance=self.instance)
        self.staticPage.save()

        self.otherInstance = make_instance()

    def test_can_get_page(self):
        # Note- case insensitive match
        rslt = static_page(None, self.instance, "FaQ")

        self.assertEqual(rslt['content'], self.staticPage.content)
        self.assertEqual(rslt['title'], self.staticPage.name)

    def test_instance_mismatch(self):
        self.assertRaises(Http404,
                          static_page, None, self.otherInstance, "blah")

    def test_missing_name(self):
        self.assertRaises(Http404,
                          static_page, None, self.instance, "missing")

    def test_can_get_pre_defined_page(self):
        # Note- case insensitive match
        rslt = static_page(None, self.instance, "AbOUt")
        content = get_template(StaticPage.DEFAULT_CONTENT['about']).render()

        self.assertIsNotNone(rslt['content'])
        self.assertIsNotNone(rslt['title'])
        self.assertEqual(len(rslt['content']), len(content))


class BoundaryViewTest(ViewTestCase):

    def setUp(self):
        super(BoundaryViewTest, self).setUp()

        self.test_boundaries = [
            'alabama',
            'arkansas',
            'far',
            'farquaad\'s castle',
            'farther',
            'farthest',
            'ferenginar',
            'romulan star empire',
        ]
        self.test_boundary_hashes = [
            {'tokens': ['alabama']},
            {'tokens': ['arkansas']},
            {'tokens': ['far']},
            {'tokens': ['farquaad\'s', 'castle']},
            {'tokens': ['farther']},
            {'tokens': ['farthest']},
            {'tokens': ['ferenginar']},
            {'tokens': ['romulan', 'star', 'empire']},
        ]
        for i, v in enumerate(self.test_boundaries):
            boundary = make_simple_boundary(v, i)
            self.instance.boundaries.add(boundary)
            self.instance.save()
            js_boundary = self.test_boundary_hashes[i]

            js_boundary['id'] = boundary.id
            js_boundary['name'] = boundary.name
            js_boundary['category'] = boundary.category
            js_boundary['value'] = boundary.name
            js_boundary['sortOrder'] = boundary.sort_order

    def test_boundary_to_geojson_view(self):
        distance = 1.0
        boundary = make_simple_boundary("Hello, World", distance)
        self.instance.boundaries.add(boundary)
        self.instance.save()
        response = boundary_to_geojson(
            make_request(),
            self.instance,
            boundary.pk)

        self.assertEqual(response.content.decode('utf-8'),
                         boundary.geom.transform(4326, clone=True).geojson)

        self._assert_response_is_srid_3857_distance(response, distance)

    def test_anonymous_boundary_to_geojson_view(self):
        distance = 1.0
        boundary = make_anonymous_boundary(distance)
        # Anonymous boundaries do not get added to instance.boundaries
        response = boundary_to_geojson(
            make_request(),
            self.instance,
            boundary.pk)

        self.assertEqual(response.content.decode('utf-8'),
                         boundary.geom.transform(4326, clone=True).geojson)

        self._assert_response_is_srid_3857_distance(response, distance)

    def test_add_anonymous_boundary_view(self):
        distance3857 = 1.0
        point3857 = Point(distance3857, distance3857, srid=3857)
        point4326 = point3857.transform(4326, clone=True)
        n = point4326.x
        request_dict = {
            'polygon': [[n, n], [n, n+1], [n+1, n+1], [n+1, n], [n, n]]
        }
        content = add_anonymous_boundary(make_request(
            body=json.dumps(request_dict)))

        self.assertIn('id', content)
        boundary_id = content['id']
        anonymous_boundary = Boundary.all_objects.get(pk=boundary_id)

        gjs_response = boundary_to_geojson(
            make_request(),
            self.instance,
            boundary_id)

        self.assertEqual(gjs_response.content.decode('utf-8'),
                         anonymous_boundary.geom.transform(
                             4326, clone=True).geojson)

        self._assert_response_is_srid_3857_distance(gjs_response, distance3857)

    def test_autocomplete_view(self):
        response = boundary_autocomplete(make_request(), self.instance)

        self.assertEqual(response, self.test_boundary_hashes)

    def test_autocomplete_view_scoped(self):
        # make a boundary that is not tied to this
        # instance, should not be in the search
        # results
        make_simple_boundary("fargo", 1)
        response = boundary_autocomplete(make_request(), self.instance)

        self.assertEqual(response, self.test_boundary_hashes)

    def test_autocomplete_view_limit(self):
        response = boundary_autocomplete(
            make_request({'max_items': 2}),
            self.instance)

        self.assertEqual(response, self.test_boundary_hashes[0:2])

    def _assert_response_is_srid_3857_distance(self, response, distance):
        upper_left_3857 = Point(distance, distance, srid=3857)
        upper_left_4326 = upper_left_3857.transform(4326, clone=True)
        json_response = json.loads(response.content)
        response_upper_left = Point(json_response['coordinates'][0][0][0],
                                    srid=4326)
        self.assertAlmostEqual(response_upper_left.x,
                               upper_left_4326.x)


class TreePhotoTestCase(LocalMediaTestCase):
    def setUp(self):
        super(TreePhotoTestCase, self).setUp()

        self.p1 = Point(-7615441.0, 5953519.0)

        self.instance = make_instance(point=self.p1)
        self.user = make_commander_user(self.instance)
        self.plot = Plot(geom=self.p1, instance=self.instance)
        self.plot.save_with_user(self.user)

        self.tree = Tree(plot=self.plot, instance=self.instance)
        self.tree.save_with_user(self.user)

        self.image = self.load_resource('tree1.gif')


class TreePhotoAffectsPlotUpdatedAtTestCase(TreePhotoTestCase):
    def setUp(self):
        super(TreePhotoAffectsPlotUpdatedAtTestCase, self).setUp()
        self.fellow = make_commander_user(self.instance, 'other-commander')
        self.initial_updated = self.plot.updated_at

    def test_add_photo_sets_updated(self):
        self.tree.add_photo(self.image, self.fellow)
        self.plot.refresh_from_db()
        self.assertGreater(self.plot.updated_at, self.initial_updated)
        self.assertEqual(self.plot.updated_by, self.fellow)

    def test_delete_photo_sets_updated(self):
        self.tree.add_photo(self.image, self.user)
        self.plot.refresh_from_db()
        self.initial_updated = self.plot.updated_at

        photo = self.plot.current_tree().photos()[0]
        photo.delete_with_user(self.fellow)

        self.plot.refresh_from_db()
        self.assertGreater(self.plot.updated_at, self.initial_updated)
        self.assertEqual(self.plot.updated_by, self.fellow)


class DeleteOwnPhotoTest(TreePhotoTestCase):
    def setUp(self):
        super(DeleteOwnPhotoTest, self).setUp()
        tp = self.tree.add_photo(self.image, self.user)
        tp.save_with_user(self.user)

    def _delete_photo(self, user):
        old_photo = self.tree.photos()[0]
        return delete_photo(
            make_request(method='DELETE',
                         user=user, instance=self.instance),
            self.instance, self.plot.pk, old_photo.pk)

    def test_delete_own_photo(self):
        self._delete_photo(self.user)
        self.assertEqual(len(self.tree.photos()), 0)

    def test_admin_can_delete_photo(self):
        self._delete_photo(self.user)
        self.assertEqual(len(self.tree.photos()), 0)

    def test_delete_own_photo_after_role_demotion(self):
        admin = make_user(self.instance, username='headhoncho',
                          make_role=self.user.get_role)
        observer_role = make_observer_role(self.instance)
        iu = self.user.get_effective_instance_user(self.instance)
        iu.role = observer_role
        iu.save_with_user(admin)

        self._delete_photo(self.user)
        self.assertEqual(len(self.tree.photos()), 0)

    def test_cannot_delete_others_photo(self):
        other = make_tweaker_user(self.instance, username="other")
        self.assertRaises(AuthorizeException, self._delete_photo, other)
        self.assertEqual(len(self.tree.photos()), 1)


class TreePhotoRotationTest(TreePhotoTestCase):
    def setUp(self):
        super(TreePhotoRotationTest, self).setUp()
        self.tree.add_photo(self.image, self.user)

    def test_tree_photo_rotation(self):
        old_photo = self.tree.photos()[0]
        self.assertNotEqual(old_photo.image.width, old_photo.image.height)

        context = rotate_map_feature_photo(
            make_request({'degrees': '-90'}, user=self.user, method='POST'),
            self.instance, self.plot.pk, old_photo.pk)

        rotated_photo = TreePhoto.objects.get(pk=old_photo.pk)

        self.assertEqual(None, context['error'])
        self.assertEqual(1, len(context['photos']))
        self.assertEqual(old_photo.pk, context['photos'][0]['id'])

        self.assertAlmostEqual(old_photo.image.width,
                               rotated_photo.image.height, delta=1)
        self.assertAlmostEqual(old_photo.image.height,
                               rotated_photo.image.width, delta=1)

        self.assertAlmostEqual(old_photo.thumbnail.width,
                               rotated_photo.thumbnail.height, delta=1),
        self.assertAlmostEqual(old_photo.thumbnail.height,
                               rotated_photo.thumbnail.width, delta=1)


class ApproveOrRejectPhotoTest(TreePhotoTestCase):

    @media_dir
    def test_approve_photo_no_pending(self):
        self.assertEqual(TreePhoto.objects.count(), 0)

        self.tree.add_photo(self.image, self.user)

        tp = TreePhoto.objects.all()[0]
        all_audits = list(tp.audits())

        approve_or_reject_photos(
            make_request({'ids': str(tp.pk)}, user=self.user),
            self.instance, 'approve')

        for audit in all_audits:
            audit = Audit.objects.get(pk=audit.pk)
            self.assertEqual(audit.ref.action, Audit.Type.ReviewApprove)

    @media_dir
    def test_approve_multiple_photos(self):
        self.assertEqual(TreePhoto.objects.count(), 0)

        self.tree.add_photo(self.image, self.user)

        self.tree.add_photo(self.image, self.user)

        tp_ids = ','.join(str(tp.pk) for tp in TreePhoto.objects.all())
        all_audits = list(audit for tp in TreePhoto.objects.all()
                          for audit in tp.audits())

        approve_or_reject_photos(
            make_request({'ids': tp_ids}, user=self.user),
            self.instance, 'approve')

        for audit in all_audits:
            audit = Audit.objects.get(pk=audit.pk)
            self.assertEqual(audit.ref.action, Audit.Type.ReviewApprove)

    @media_dir
    def test_reject_photo_no_pending(self):
        self.assertEqual(TreePhoto.objects.count(), 0)

        self.tree.add_photo(self.image, self.user)

        self.assertEqual(TreePhoto.objects.count(), 1)

        tp = TreePhoto.objects.all()[0]
        audit_list = list(tp.audits())

        approve_or_reject_photos(
            make_request({'ids': str(tp.pk)}, user=self.user),
            self.instance, 'reject')

        for audit in audit_list:
            audit = Audit.objects.get(pk=audit.pk)
            self.assertEqual(audit.ref.action, Audit.Type.ReviewReject)

        self.assertEqual(TreePhoto.objects.count(), 0)


class PlotImageUpdateTest(LocalMediaTestCase):
    def setUp(self):
        super(PlotImageUpdateTest, self).setUp()

        self.instance = make_instance()
        self.user = make_commander_user(self.instance)

        # Give this plot a unique number so we can check for
        # correctness
        self.plot = Plot(
            geom=self.instance.center, instance=self.instance, pk=449293)

        self.plot.save_with_user(self.user)

        self.tree = Tree(instance=self.instance, plot=self.plot)
        self.tree.save_with_user(self.user)

    def _run_basic_test_with_image_file(self, image_file):
        tp = TreePhoto(tree=self.tree, instance=self.instance)
        tp.set_image(image_file)
        tp.save_with_user(self.user)

        reloaded_tp = TreePhoto.objects.get(pk=tp.pk)

        # Verify our settings context manager worked and that
        # things are where they say they are
        image_path = reloaded_tp.image.path
        thumb_path = reloaded_tp.thumbnail.path

        image_url = reloaded_tp.image.url
        thumb_url = reloaded_tp.thumbnail.url

        all_of_em = [image_path, thumb_path, image_url, thumb_url]

        # ids should be in all paths and urls
        for path_or_url in all_of_em:
            self.assertNotEqual(path_or_url.find('%s-' % self.tree.pk), -1)
            self.assertNotEqual(path_or_url.find('%s-' % self.plot.pk), -1)

        # media prefix and files should exist
        for path in [image_path, thumb_path]:
            self.assertEqual(path.index(self.photoDir), 0)
            # File should be larger than 100 bytes
            self.assertGreater(os.stat(path).st_size, 100)

        for url in [image_url, thumb_url]:
            self.assertEqual(url.index(self.mediaUrl), 0)

        # Delete should remove objects
        reloaded_tp.delete_with_user(self.user)

        for path in [image_path, thumb_path]:
            self.assertFalse(os.path.exists(path))

    @media_dir
    def test_photos_save_with_thumbnails_gif(self):
        image_file = self.load_resource('tree1.gif')
        self._run_basic_test_with_image_file(image_file)

    @media_dir
    def test_photos_save_with_thumbnails_jpg(self):
        image_file = self.load_resource('tree2.jpg')
        self._run_basic_test_with_image_file(image_file)

    @media_dir
    def test_photos_save_with_thumbnails_png(self):
        image_file = self.load_resource('tree3.png')
        self._run_basic_test_with_image_file(image_file)

    def assertTreePhotoExists(self, tp):
        self.assertPathExists(tp.image.path)
        self.assertPathExists(tp.thumbnail.path)

    def _make_tree_photo_request(self, file, plot_id, tree_id=None):
        return add_tree_photo_helper(make_request(user=self.user,
                                                  file=file),
                                     self.instance, plot_id, tree_id)

    @media_dir
    def test_add_photo_to_tree(self):
        self.assertEqual(TreePhoto.objects.count(), 0)

        tree_image = self.load_resource('tree1.gif')

        self._make_tree_photo_request(
            tree_image, self.plot.pk, self.tree.pk)

        objects = self.tree.treephoto_set.all()
        self.assertEqual(len(objects), 1)

        tp = objects[0]

        self.assertTreePhotoExists(tp)

    @media_dir
    def test_invalid_ids(self):
        self.assertEqual(TreePhoto.objects.count(), 0)

        tree_image = self.load_resource('tree1.gif')

        self.assertRaises(
            Http404,
            self._make_tree_photo_request, tree_image, -1, None)

        self.assertEqual(TreePhoto.objects.count(), 0)

        # Reload
        tree_image.seek(0)

        self.assertRaises(
            Http404,
            self._make_tree_photo_request, tree_image, self.plot.pk, -1)

        self.assertEqual(TreePhoto.objects.count(), 0)

    @media_dir
    def test_creates_tree_if_needed(self):
        pass

    @media_dir
    def test_assigns_to_tree_if_exists(self):
        tree_image = self.load_resource('tree1.gif')

        # Note: No tree id given - will do a lookup
        self._make_tree_photo_request(
            tree_image, self.plot.pk, None)

        objects = self.tree.treephoto_set.all()
        self.assertEqual(len(objects), 1)

        tp = objects[0]

        self.assertTreePhotoExists(tp)

    @media_dir
    def test_rejects_non_image_files(self):
        invalid_thing = StringIO()
        invalid_thing.write('booyah')
        invalid_thing.seek(0)
        setattr(invalid_thing, 'name', 'blah.jpg')

        self.assertEqual(TreePhoto.objects.count(), 0)

        self.assertRaises(ValidationError,
                          self._make_tree_photo_request,
                          invalid_thing, self.plot.pk, self.tree.pk)

        self.assertEqual(TreePhoto.objects.count(), 0)

    @media_dir
    def test_non_authorized_users_cant_create_images(self):
        pass


class UserPhotoUpdateTest(LocalMediaTestCase):
    def setUp(self):
        super(UserPhotoUpdateTest, self).setUp()
        self.user = make_commander_user()

    def upload_photo(self, filename):
        file = self.load_resource(filename)
        return upload_user_photo(
            make_request(user=self.user, file=file), self.user)

    @media_dir
    def test_upload_user_photo(self):
        self.upload_photo('tree1.gif')
        self.assertPathExists(self.user.photo.path)

        self.upload_photo('tree2.jpg')
        self.assertPathExists(self.user.photo.path)

    @media_dir
    def test_non_image(self):
        with self.assertRaises(ValidationError):
            self.upload_photo('nonImage.jpg')

    @media_dir
    @override_settings(MAXIMUM_IMAGE_SIZE=10)
    def test_rejects_large_files(self):
        with self.assertRaises(ValidationError):
            self.upload_photo('tree2.jpg')


class PlotUpdateTest(OTMTestCase):
    def setUp(self):
        User._system_user.save_base()

        self.instance = make_instance()
        self.user = make_commander_user(self.instance)
        set_write_permissions(self.instance, self.user,
                              'Plot', ['udf:Test choice', 'udf:Test col'])
        set_write_permissions(self.instance, self.user,
                              'Tree', ['udf:Test choice', 'udf:Test col'])

        self.choice_field = UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'choice',
                                 'choices': ['a', 'b', 'c']}),
            iscollection=False,
            name='Test choice')

        self.tree_choice_field = UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Tree',
            datatype=json.dumps({'type': 'choice',
                                 'choices': ['foo', 'bar', 'baz']}),
            iscollection=False,
            name='Test choice')

        self.col_field_plot = UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps([{'name': 'pick',
                                  'type': 'choice',
                                  'choices': ['a', 'b', 'c']},
                                 {'name': 'num',
                                  'type': 'int'}]),
            iscollection=True,
            name='Test col')

        self.col_field_tree = UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Tree',
            datatype=json.dumps([{'name': 'pick',
                                  'type': 'choice',
                                  'choices': ['a', 'b', 'c']},
                                 {'name': 'num',
                                  'type': 'int'}]),
            iscollection=True,
            name='Test col')

        self.plot = Plot(instance=self.instance, geom=self.instance.center)
        self.plot.save_with_user(self.user)

        psycopg2.extras.register_hstore(connection.cursor(), globally=True)

    def test_creates_new_plot(self):
        plot = Plot(instance=self.instance)

        update = {'plot.geom': {'x': 4, 'y': 9},
                  'plot.readonly': False}

        created_plot, __ = update_map_feature(update, self.user, plot)

        created_plot_update = Plot.objects.get(pk=created_plot.pk)
        self.assertIsNotNone(created_plot_update, created_plot_update.pk)
        self.assertEqual(created_plot_update.geom.x, 4.0)
        self.assertEqual(created_plot_update.geom.y, 9.0)
        self.assertIsNone(created_plot_update.current_tree())

        created_plot_update.delete_with_user(self.user)

    def test_creates_new_plot_and_tree(self):
        plot = Plot(instance=self.instance)

        update = {'plot.geom': {'x': 4, 'y': 9},
                  'plot.readonly': False,
                  'tree.readonly': False}

        created_plot, __ = update_map_feature(update, self.user, plot)

        created_plot_update = Plot.objects.get(pk=created_plot.pk)
        self.assertIsNotNone(created_plot_update, created_plot_update.pk)
        self.assertEqual(created_plot_update.geom.x, 4.0)
        self.assertEqual(created_plot_update.geom.y, 9.0)
        self.assertIsNotNone(created_plot_update.current_tree())

        created_plot_update.current_tree().delete_with_user(self.user)
        created_plot_update.delete_with_user(self.user)

    def test_does_not_create_tree_if_tree_field_value_is_an_empty_string(self):
        plot = Plot(instance=self.instance)

        update = {'plot.geom': {'x': 4, 'y': 9},
                  'plot.readonly': False,
                  'tree.udf:Test choice': ''}

        created_plot, __ = update_map_feature(update, self.user, plot)

        created_plot_update = Plot.objects.get(pk=created_plot.pk)
        self.assertIsNone(created_plot_update.current_tree())

        created_plot_update.delete_with_user(self.user)

    def test_does_create_tree_when_one_tree_field_is_non_empty(self):
        plot = Plot(instance=self.instance)

        update = {'plot.geom': {'x': 4, 'y': 9},
                  'plot.readonly': False,
                  'tree.udf:Test choice': '',
                  'tree.diameter': 7}

        created_plot, updated_tree = update_map_feature(update, self.user,
                                                        plot)

        created_plot_update = Plot.objects.get(pk=created_plot.pk)
        self.assertIsNotNone(created_plot_update.current_tree())
        self.assertEqual(None, updated_tree.udfs['Test choice'])
        self.assertEqual(7, updated_tree.diameter)

        created_plot_update.current_tree().delete_with_user(self.user)
        created_plot_update.delete_with_user(self.user)

    def test_does_clear_field_if_tree_already_exists(self):
        tree = Tree(plot=self.plot, instance=self.instance)
        tree.udfs['Test choice'] = 'bar'
        tree.save_with_user(self.user)

        tree.refresh_from_db()
        self.assertEqual('bar', tree.udfs['Test choice'])

        update = {'plot.geom': {'x': 4, 'y': 9},
                  'plot.readonly': False,
                  'tree.udf:Test choice': None}

        updated_plot, created_tree = update_map_feature(update, self.user,
                                                        self.plot)

        self.assertIsNotNone(created_tree)
        self.assertEqual(None, created_tree.udfs['Test choice'])

        updated_plot.current_tree().delete_with_user(self.user)
        updated_plot.delete_with_user(self.user)

    def test_invalid_udf_name_fails(self):
        update = {'plot.udf:INVaLiD UTF': 'z'}

        self.assertRaises(KeyError,
                          update_map_feature,
                          update, self.user, self.plot)

    def test_collection_udf_works(self):
        plot_data = [{'pick': 'a', 'num': 4},
                     {'pick': 'b', 'num': 9}]
        tree_data = [{'pick': 'c', 'num': 1},
                     {'pick': 'a', 'num': 33}]

        update = {'plot.udf:Test col': plot_data,
                  'tree.udf:Test col': tree_data}

        update_map_feature(update, self.user, self.plot)

        updated_plot = Plot.objects.get(pk=self.plot.pk)

        plotudf = updated_plot.udfs['Test col']
        for exp, act in zip(plot_data, plotudf):
            self.assertDictContainsSubset(exp, act)

        treeudf = updated_plot.current_tree().udfs['Test col']

        for exp, act in zip(tree_data, treeudf):
            self.assertDictContainsSubset(exp, act)

    def test_collection_udf_errors_show_up_as_validations(self):
        plot_data = [{'pick': 'invalid choice', 'num': 4}]

        update = {'plot.udf:Test col':
                  plot_data}

        self.assertRaises(ValidationError,
                          update_map_feature,
                          update, self.user, self.plot)

    def test_malformed_udf_fails(self):
        update = {'plot.udf:Test choice': 'z'}

        try:
            update_map_feature(update, self.user, self.plot)
            raise AssertionError('expected update to raise validation error')
        except ValidationError as e:

            self.assertIn('plot.udf:Test choice', e.message_dict)

    def test_grouping_failed_udf(self):
        update = {'plot.udf:Test choice': 'z',
                  'plot.length': 'bad'}

        try:
            update_map_feature(update, self.user, self.plot)
            raise AssertionError('expected update to raise validation error')
        except ValidationError as e:
            self.assertIn('plot.udf:Test choice', e.message_dict)
            self.assertIn('plot.length', e.message_dict)

    def test_simple_update(self):
        self.assertNotEqual(self.plot.length, 20)
        self.assertNotEqual(self.plot.width, 25)

        update = {'plot.length': 20,
                  'plot.width': 25,
                  'plot.udf:Test choice': 'b'}

        rslt, __ = update_map_feature(update, self.user, self.plot)

        self.assertEqual(rslt.pk, self.plot.pk)

        plot = Plot.objects.get(pk=self.plot.pk)

        self.assertEqual(plot.length, 20)
        self.assertEqual(plot.width, 25)
        self.assertEqual(plot.udfs['Test choice'], 'b')

    def test_validates_numeric_fields(self):
        update = {'plot.length': 'length'}

        try:
            update_map_feature(update, self.user, self.plot)
            raise AssertionError('expected update to raise validation error')
        except ValidationError as e:
            self.assertIn('plot.length', e.message_dict)

    def test_edit_tree_creates_tree(self):
        self.assertIsNone(self.plot.current_tree())

        update = {'tree.height': 9}
        update_map_feature(update, self.user, self.plot)

        self.assertIsNotNone(
            Plot.objects.get(pk=self.plot.pk).current_tree())

    def test_doesnt_edit_tree_if_plot_fails(self):
        tree = Tree(plot=self.plot, instance=self.plot.instance)
        tree.height = 92
        tree.save_with_user(self.user)

        update = {'plot.length': 'length',
                  'tree.height': 42}

        try:
            update_map_feature(update, self.user, self.plot)
            raise AssertionError('expected update to raise validation error')
        except ValidationError as e:
            self.assertIn('plot.length', e.message_dict)

        updated_tree = Tree.objects.get(pk=tree.pk)

        self.assertEqual(updated_tree.height, 92)

    def test_doesnt_edit_plot_if_tree_fails(self):
        self.plot.length = 100
        self.plot.save_with_user(self.user)

        tree = Tree(plot=self.plot, instance=self.plot.instance)
        tree.height = 92
        tree.save_with_user(self.user)

        update = {'plot.length': 92,
                  'tree.height': 'height'}

        try:
            update_map_feature(update, self.user, self.plot)
            raise AssertionError('expected update to raise validation error')
        except ValidationError as e:
            self.assertIn('tree.height', e.message_dict)

        updated_plot = Plot.objects.get(pk=self.plot.pk)

        self.assertEqual(updated_plot.length, 100)


class PlotViewTestCase(ViewTestCase):

    def setUp(self):
        super(PlotViewTestCase, self).setUp()

        region = ITreeRegion.objects.get(code='NoEastXXX')
        self.p = region.geometry.point_on_surface

        self.instance = make_instance(point=self.p)
        self.user = make_commander_user(self.instance)

    def get_plot_context(self, plot):
        context = plot_detail(make_request(user=self.user,
                                           instance=self.instance),
                              self.instance, plot.pk)
        return context


class PlotViewTest(PlotViewTestCase):

    def setUp(self):
        super(PlotViewTest, self).setUp()

        def mockbenefits(*args, **kwargs):
            benefits = {
                "Benefits": {
                    "aq_nox_avoided": 0.6792,
                    "aq_nox_dep": 0.371,
                    "aq_ozone_dep": 0.775,
                    "aq_pm10_avoided": 0.0436,
                    "aq_pm10_dep": 0.491,
                    "aq_sox_avoided": 0.372,
                    "aq_sox_dep": 0.21,
                    "aq_voc_avoided": 0.0254,
                    "bvoc": -0.077,
                    "co2_avoided": 255.5,
                    "co2_sequestered": 0,
                    "co2_storage": 6575,
                    "electricity": 187,
                    "hydro_interception": 12.06,
                    "natural_gas": 5834.1
                }
            }
            return (benefits, None)

        self.origBenefitFn = ecobackend.json_benefits_call
        ecobackend.json_benefits_call = mockbenefits

    def tearDown(self):
        ecobackend.json_benefits_call = self.origBenefitFn

    def test_simple_audit_history(self):
        plot = Plot(instance=self.instance, geom=self.p)
        plot.save_with_user(self.user)

        plot.width = 9
        plot.save_with_user(self.user)

        details = self.get_plot_context(plot)

        self.assertIn('recent_activity', details)

        audit_groups = details['recent_activity']

        __, __, audit_list = audit_groups[0]
        audit = audit_list[0]

        self.assertEqual(audit.model, 'Plot')
        self.assertEqual(audit.field, 'width')

    def test_tree_audits_show_up_too(self):
        plot = Plot(instance=self.instance, geom=self.p)
        plot.save_with_user(self.user)

        tree = Tree(instance=self.instance, plot=plot)
        tree.save_with_user(self.user)

        tree.readonly = True
        tree.save_with_user(self.user)

        details = self.get_plot_context(plot)

        self.assertIn('recent_activity', details)

        audit_groups = details['recent_activity']
        __, __, audit_list = audit_groups[0]
        readonly_audit = audit_list[0]
        insert_audit = audit_list[1]

        self.assertEqual(readonly_audit.model, 'Tree')
        self.assertEqual(readonly_audit.field, 'readonly')
        self.assertEqual(readonly_audit.model_id, tree.pk)
        self.assertEqual(readonly_audit.action, Audit.Type.Update)

        self.assertEqual(insert_audit.model, 'Tree')
        self.assertEqual(insert_audit.model_id, tree.pk)
        self.assertEqual(insert_audit.action, Audit.Type.Insert)

    def test_plot_with_tree(self):
        species = Species(instance=self.instance, otm_code='BDM OTHER')
        species.save_with_user(self.user)

        plot_w_tree = Plot(geom=self.p, instance=self.instance)
        plot_w_tree.save_with_user(self.user)

        tree = Tree(plot=plot_w_tree, instance=self.instance,
                    diameter=10, species=species)
        tree.save_with_user(self.user)

        request = make_request(user=self.user, instance=self.instance)
        request.instance_supports_ecobenefits = self.instance\
                                                    .has_itree_region()
        context = plot_detail(request, self.instance, plot_w_tree.pk)

        self.assertEqual(plot_w_tree, context['plot'])
        self.assertIn('benefits', context)

    def test_plot_without_tree(self):
        plot_wo_tree = Plot(geom=self.p, instance=self.instance)
        plot_wo_tree.save_with_user(self.user)

        context = self.get_plot_context(plot_wo_tree)

        self.assertEqual(plot_wo_tree, context['plot'])
        self.assertNotIn('benefits', context)

    def test_system_user_hidden_from_audit_history(self):
        plot = Plot(instance=self.instance, geom=self.p)
        plot.save_with_user(self.user)

        plot.width = 9
        plot.save_with_user(self.user)

        details = self.get_plot_context(plot)

        self.assertIn('recent_activity', details)

        audit_groups = details['recent_activity']

        __, __, audit_list = audit_groups[0]
        audit = audit_list[0]

        self.assertEqual(audit.model, 'Plot')
        self.assertEqual(audit.field, 'width')

        # Add the system user to the instance with "commander" permissions
        system_user = User.system_user()
        InstanceUser(instance=self.instance, user=system_user,
                     role=self.user.get_role(self.instance)
                     ).save_with_user(system_user)

        plot.length = 9
        plot.save_with_user(system_user)

        # There is now a system user audit on the plot
        self.assertEqual(1, len(Audit.objects.filter(model_id=plot.pk,
                                                     model='Plot',
                                                     user=system_user)))

        # But the audits returned by the view are the same
        new_details = self.get_plot_context(plot)

        self.assertIn('recent_activity', new_details)

        new_audit_groups = new_details['recent_activity']

        self.assertEqual(audit_groups, new_audit_groups)


class PlotViewProgressTest(PlotViewTestCase):

    def setUp(self):
        super(PlotViewProgressTest, self).setUp()
        self.plot_wo_tree = Plot(geom=self.p, instance=self.instance)
        self.plot_wo_tree.save_with_user(self.user)

        self.plot_w_tree = Plot(geom=self.p, instance=self.instance)
        self.plot_w_tree.save_with_user(self.user)

        tree = Tree(plot=self.plot_w_tree, instance=self.instance)
        tree.save_with_user(self.user)

        context = self.get_plot_context(self.plot_w_tree)

        self.initial_progress = context['progress_percent']
        self.initial_message_count = len(context['progress_messages'])

    def test_progress_starts_at_25(self):
        # Having a plot location counts at 25%
        context = self.get_plot_context(self.plot_wo_tree)

        self.assertEqual(25, context['progress_percent'])
        self.assertEqual(4, len(context['progress_messages']))

    def test_progress_messages_decrease_when_plot_has_tree(self):
        wo_tree_context = self.get_plot_context(self.plot_wo_tree)
        w_tree_context = self.get_plot_context(self.plot_w_tree)

        self.assertTrue(len(wo_tree_context['progress_messages']) >
                        len(w_tree_context['progress_messages']))
        # Adding a tree without and details does not add progress
        self.assertTrue(wo_tree_context['progress_percent'] ==
                        w_tree_context['progress_percent'])

    def test_progress_increases_when_diameter_is_added(self):
        tree = self.plot_w_tree.current_tree()
        tree.diameter = 2
        tree.save_with_user(self.user)

        context = self.get_plot_context(self.plot_w_tree)

        self.assertTrue(context['progress_percent'] > self.initial_progress)
        self.assertTrue(len(context['progress_messages']) <
                        self.initial_message_count)

    def test_progress_increases_when_species_is_added(self):
        species = Species(common_name="test",
                          otm_code="TEST",
                          instance=self.instance)
        species.save_with_user(self.user)
        tree = self.plot_w_tree.current_tree()
        tree.species = species
        tree.save_with_user(self.user)

        context = self.get_plot_context(self.plot_w_tree)

        self.assertTrue(context['progress_percent'] > self.initial_progress)
        self.assertTrue(len(context['progress_messages']) <
                        self.initial_message_count)


class PlotViewPhotoProgressTest(TreePhotoTestCase):

    def setUp(self):
        super(PlotViewPhotoProgressTest, self).setUp()
        context = plot_detail(make_request(user=self.user,
                                           instance=self.instance),
                              self.instance, self.plot.pk)

        self.initial_progress = context['progress_percent']
        self.initial_message_count = len(context['progress_messages'])

    @media_dir
    def test_progress_increases_when_photo_is_added(self):
        photo = TreePhoto(tree=self.tree, instance=self.instance)
        photo.set_image(self.image)
        photo.save_with_user(self.user)
        self.tree.save_with_user(self.user)

        context = plot_detail(make_request(user=self.user,
                                           instance=self.instance),
                              self.instance, self.plot.pk)

        self.assertTrue(context['progress_percent'] >
                        self.initial_progress)
        self.assertTrue(len(context['progress_messages']) <
                        self.initial_message_count)


class PlotExternalLinkTest(OTMTestCase):

    def move(self, pt, x, y):
        return Point(pt.x + x, pt.y + y)

    def _add_instance_permission(self, role):
        content_type = ContentType.objects.get_for_model(Instance)
        perm = Permission.objects.get(content_type=content_type,
                                      codename=PERMISSION_VIEW_EXTERNAL_LINK)
        role.instance_permissions.add(perm)

    def setUp(self):
        super(PlotExternalLinkTest, self).setUp()
        self.p1 = Point(-7615441.0, 5953519.0)

        self.instance = make_instance(is_public=True, point=self.p1)
        set_attr_on_json_field(self.instance,
                               'config.externalLink.text', 'some text')
        self.instance.save()

        self.creator = make_commander_user(self.instance, username='creator')
        self.commander = make_commander_user(self.instance)

        self.empty_plot = Plot(instance=self.instance,
                               geom=self.move(self.p1, 0.5, 0))
        self.empty_plot.save_with_user(self.creator)
        self.planted_plot = Plot(instance=self.instance,
                                 geom=self.move(self.p1, 0, 0.5))
        self.planted_plot.save_with_user(self.creator)

        self.tree = Tree(instance=self.instance, plot=self.planted_plot)
        self.tree.save_with_user(self.creator)

    def test_validate_token_template(self):
        self.assertTrue(validate_token_template('no tokens'))
        self.assertTrue(validate_token_template(
            '#{tree.id} #{planting_site.id} #{planting_site.custom_id}' * 2))
        self.assertFalse(validate_token_template(
            '#{tree.id} #{}'))
        self.assertFalse(validate_token_template(
            '#{tree.id} #{ tree.id }'))
        self.assertFalse(validate_token_template(
            '#{tree.id} #{bioswale.id}'))

    def test_tree_external_link_shows(self):
        set_attr_on_json_field(self.instance,
                               'config.externalLink.url',
                               'something#{tree.id}/#hash')
        self.instance.save()
        self._add_instance_permission(self.commander.get_role(self.instance))

        context = plot_detail(make_request(user=self.commander,
                                           instance=self.instance),
                              self.instance, self.planted_plot.pk)

        self.assertEqual(context['external_link'],
                         'something{}/#hash'.format(str(self.tree.pk)))

    def test_plot_external_link_shows(self):
        set_attr_on_json_field(self.instance,
                               'config.externalLink.url',
                               'something#{planting_site.id}/#hash')
        self.instance.save()
        self._add_instance_permission(self.commander.get_role(self.instance))

        context = plot_detail(make_request(user=self.commander,
                                           instance=self.instance),
                              self.instance, self.empty_plot.pk)

        self.assertEqual(context['external_link'],
                         'something{}/#hash'.format(str(self.empty_plot.pk)))

    def test_plot_external_link_custom_id_shows(self):
        set_attr_on_json_field(self.instance,
                               'config.externalLink.url',
                               'something#{planting_site.custom_id}/#hash')
        self.instance.save()
        self._add_instance_permission(self.commander.get_role(self.instance))

        self.empty_plot.owner_orig_id = 'AN_ID'
        self.empty_plot.save_with_user(self.creator)

        context = plot_detail(make_request(user=self.commander,
                                           instance=self.instance),
                              self.instance, self.empty_plot.pk)

        self.assertEqual(context['external_link'],
                         'something{}/#hash'.format(
                             str(self.empty_plot.owner_orig_id)))

    def test_no_tree_no_external_link(self):
        set_attr_on_json_field(self.instance,
                               'config.externalLink.url',
                               'something#{tree.id}/more')
        self.instance.save()
        self._add_instance_permission(self.commander.get_role(self.instance))

        context = plot_detail(make_request(user=self.commander,
                                           instance=self.instance),
                              self.instance, self.empty_plot.pk)

        self.assertIsNone(context['external_link'])

    def test_no_config_no_external_link(self):
        context = plot_detail(make_request(user=self.commander,
                                           instance=self.instance),
                              self.instance, self.empty_plot.pk)

        self.assertIsNone(context['external_link'])

    def test_no_permission_no_external_link(self):
        set_attr_on_json_field(self.instance,
                               'config.externalLink.url',
                               'something#{planting_site.id}/more')
        self.instance.save()

        context = plot_detail(make_request(user=self.commander,
                                           instance=self.instance),
                              self.instance, self.empty_plot.pk)

        self.assertIsNone(context['external_link'])


class RecentEditsViewTest(ViewTestCase):

    def setUp(self):
        self.longMessage = True

        self.p1 = Point(-7615441.0, 5953519.0)

        self.instance = make_instance(is_public=True, point=self.p1)
        self.instance2 = make_instance('i2', is_public=True, point=self.p1)
        add_default_permissions(self.instance, [self.instance.default_role])
        add_default_permissions(self.instance2, [self.instance2.default_role])

        self.officer = make_officer_user(self.instance)
        self.commander = make_commander_user(self.instance)
        self.pending_user = make_apprentice_user(self.instance)
        iuser = InstanceUser(instance=self.instance2, user=self.commander,
                             role=self.commander.get_role(self.instance))
        iuser.save_with_user(self.commander)

        self.factory = RequestFactory()

        self.plot = Plot(geom=self.p1, instance=self.instance)

        self.dif_instance_plot = Plot(geom=self.p1, instance=self.instance2)
        self.dif_instance_plot.save_with_user(self.commander)

        self.plot.save_with_user(self.commander)

        self.tree = Tree(plot=self.plot, instance=self.instance)

        self.tree.save_with_user(self.officer)

        self.tree.diameter = 4
        self.tree.save_with_user(self.officer)

        self.tree.diameter = 5
        self.tree.save_with_user(self.officer)

        self.plot.width = 9
        self.plot.save_with_user(self.commander)

        self.plot_delta = {
            "model": "Plot",
            "model_id": self.plot.pk,
            "ref": None,
            "action": Audit.Type.Update,
            "previous_value": None,
            "current_value": "9.0",
            "requires_auth": False,
            "user_id": self.commander.pk,
            "instance_id": self.instance.pk,
            "field": "width"
        }

        self.next_plot_delta = self.plot_delta.copy()
        self.next_plot_delta["current_value"] = "44.0"
        self.next_plot_delta["previous_value"] = "9.0"

        self.plot.width = 44
        self.plot.save_with_user(self.commander)

        self.dif_instance_plot.width = '22'
        self.dif_instance_plot.save_with_user(self.commander)
        self.dif_plot_delta = {
            "model": "Plot",
            "model_id": self.dif_instance_plot.pk,
            "ref": None,
            "action": Audit.Type.Update,
            "previous_value": None,
            "current_value": '22.0',
            "requires_auth": False,
            "user_id": self.commander.pk,
            "instance_id": self.instance2.pk,
            "field": "width"
        }

    def _assert_dicts_equal(self, expected, actual):
        self.assertEqual(len(expected), len(actual), "Number of dicts")

        for expected, generated in zip(expected, actual):
            for k, v in expected.items():
                self.assertEqual(v, generated[k], "key [%s]" % k)

    def check_audits(self, url, dicts, user=None):
        req = self.factory.get(url)
        req.user = user if user else AnonymousUser()
        resulting_audits = [audit
                            for audit
                            in edits(req, self.instance)['audits']]

        self._assert_dicts_equal(dicts, [a.dict() for a in resulting_audits])
        return resulting_audits

    def check_user_audits(self, url, username, dicts):
        req = self.factory.get(url)
        req.user = AnonymousUser()
        resulting_audits = [audit.dict()
                            for audit
                            in user_audits(req, username)['audits']]

        self._assert_dicts_equal(dicts, resulting_audits)

    def test_multiple_deltas(self):
        self.check_audits('/blah/?page_size=2',
                          [self.next_plot_delta, self.plot_delta])
        self.check_user_audits('/blah/?page_size=2&instance_id=%s'
                               % self.instance.pk, self.commander.username,
                               [self.next_plot_delta, self.plot_delta])

    def test_paging(self):
        # Test that navigating next->next->prev gives the same results for page
        # 2 both times (no off-by-one errors)
        req = self.factory.get('/blah/?page_size=1')
        req.user = AnonymousUser()
        page_one_result = edits(req, self.instance)
        self._assert_dicts_equal([self.next_plot_delta],
                                 [a.dict() for a in page_one_result['audits']])

        req = self.factory.get('/blah/' + page_one_result['next_page'])
        req.user = AnonymousUser()
        page_two_result = edits(req, self.instance)
        self._assert_dicts_equal([self.plot_delta],
                                 [a.dict() for a in page_two_result['audits']])

        req = self.factory.get('/blah/' + page_two_result['next_page'])
        req.user = AnonymousUser()
        page_three_result = edits(req, self.instance)

        req = self.factory.get('/blah/' + page_three_result['prev_page'])
        req.user = AnonymousUser()
        page_two_again_result = edits(req, self.instance)
        self.assertEqual(page_two_result['audits'],
                         page_two_again_result['audits'])

    def test_model_filtering_errors(self):
        self.assertRaises(Exception,
                          self.check_audits,
                          "/blah/?model_id=%s&page_size=1" %
                          self.tree.pk, [])

        self.assertRaises(Exception,
                          self.check_audits,
                          "/blah/?model_id=%s&"
                          "models=Tree&models=Plot&page_size=1" %
                          self.tree.pk, [])

        self.assertRaises(Exception,
                          self.check_audits,
                          "/blah/?models=User&page_size=1", [])

        self.assertRaises(Exception,
                          self.check_user_audits,
                          "/blah/?model_id=%s&page_size=1&instance_id=%s"
                          % (self.tree.pk, self.instance.pk),
                          self.commander.username, [])

        self.assertRaises(Exception,
                          self.check_user_audits,
                          "/blah/?model_id=%s&models=Tree&models=Plot"
                          "&page_size=1&instance_id=%s"
                          % (self.tree.pk, self.instance.pk),
                          self.commander.username, [])

        self.assertRaises(Exception,
                          self.check_user_audits,
                          "/blah/?models=User&page_size=1&instance_id=%s"
                          % self.instance.pk,
                          self.commander.username, [])

    def test_model_filtering(self):

        specific_tree_delta = {
            "model": "Tree",
            "model_id": self.tree.pk,
            "action": Audit.Type.Update,
            "user_id": self.officer.pk,
        }

        generic_tree_delta = {
            "model": "Tree"
        }

        generic_plot_delta = {
            "model": "Plot"
        }

        self.check_audits(
            "/blah/?model_id=%s&models=Tree&page_size=1" % self.tree.pk,
            [specific_tree_delta])

        self.check_audits(
            "/blah/?model_id=%s&models=Plot&page_size=1" % self.plot.pk,
            [self.next_plot_delta])

        self.check_audits(
            "/blah/?models=Plot&models=Tree&page_size=3",
            [generic_plot_delta, generic_plot_delta, generic_tree_delta])

        self.check_audits(
            "/blah/?models=Plot&page_size=5",
            [generic_plot_delta] * 5)

        self.check_audits(
            "/blah/?models=Tree&page_size=5",
            [generic_tree_delta] * 5)

    def test_model_user_filtering(self):

        specific_tree_delta = {
            "model": "Tree",
            "model_id": self.tree.pk,
            "action": Audit.Type.Update,
            "user_id": self.officer.pk,
        }

        generic_tree_delta = {
            "model": "Tree"
        }

        generic_plot_delta = {
            "model": "Plot"
        }

        self.check_user_audits(
            "/blah/?model_id=%s&models=Tree&page_size=1" % self.tree.pk,
            self.officer.username, [specific_tree_delta])

        self.check_user_audits(
            "/blah/?model_id=%s&models=Plot&page_size=1&instance_id=%s"
            % (self.plot.pk, self.instance.pk),
            self.commander.username, [self.next_plot_delta])

        self.check_user_audits(
            "/blah/?models=Plot&page_size=3&instance_id=%s"
            % self.instance.pk, self.commander.username,
            [generic_plot_delta] * 3)

        self.check_user_audits(
            "/blah/?models=Tree&page_size=3", self.officer.username,
            [generic_tree_delta] * 3)

    def test_user_filtering(self):

        generic_officer_delta = {
            "user_id": self.officer.pk
        }

        generic_commander_delta = {
            "user_id": self.commander.pk
        }

        self.check_audits(
            "/blah/?user=%s&page_size=3" % self.officer.pk,
            [generic_officer_delta] * 3)

        self.check_audits(
            "/blah/?user=%s&page_size=3" % self.commander.pk,
            [generic_commander_delta] * 3)

    def test_user_id_ignored(self):

        generic_officer_delta = {
            "user_id": self.officer.pk
        }

        generic_commander_delta = {
            "user_id": self.commander.pk
        }

        self.check_user_audits(
            "/blah/?user=%s&page_size=3" % self.officer.pk,
            self.commander.username, [generic_commander_delta] * 3)

        self.check_user_audits(
            "/blah/?user=%s&page_size=3" % self.commander.pk,
            self.officer.username, [generic_officer_delta] * 3)

    def test_user_audits_multiple_instances(self):
        self.check_user_audits(
            "/blah/?page_size=2", self.commander.username,
            [self.dif_plot_delta, self.next_plot_delta])

        self.check_user_audits(
            "/blah/?instance_id=%s&page_size=1" % self.instance2.pk,
            self.commander.username, [self.dif_plot_delta])

    def test_pending_filtering(self):
        self.plot.width = 22
        self.plot.save_with_user(self.pending_user)

        pending_plot_delta = {
            "model": "Plot",
            "model_id": self.plot.pk,
            "ref": None,
            "action": Audit.Type.Update,
            "previous_value": "44.0",
            "current_value": "22.0",
            "requires_auth": True,
            "user_id": self.pending_user.pk,
            "instance_id": self.instance.pk,
            "field": "width"
        }

        approve_delta = {
            "action": Audit.Type.PendingApprove,
            "user_id": self.commander.pk,
            "instance_id": self.instance.pk,
        }

        self.check_audits(
            "/blah/?page_size=2&exclude_pending=false",
            [pending_plot_delta, self.next_plot_delta])

        self.check_audits(
            "/blah/?page_size=2&exclude_pending=true",
            [self.next_plot_delta, self.plot_delta])

        a = approve_or_reject_audit_and_apply(
            Audit.objects.all().order_by("-created")[0],
            self.commander, approved=True)

        pending_plot_delta["ref"] = a.pk

        self.check_audits(
            "/blah/?page_size=4&exclude_pending=true",
            [approve_delta, pending_plot_delta,
             self.next_plot_delta, self.plot_delta])

    def test_udf_collection_audits_appear(self):
        cudf = make_collection_udf(self.instance, 'Stew')
        set_write_permissions(self.instance, self.commander, 'Plot',
                              ['udf:Stew'])
        set_read_permissions(self.instance, self.officer, 'Plot', ['udf:Stew'])

        self.plot.udfs['Stew'] = [{'action': 'water', 'height': 343}]
        self.plot.save_with_user(self.commander)

        self.check_audits(
            "/blah/?page_size=2&exclude_pending=true",
            [{
                "model": "udf:%s" % cudf.pk,
                "ref": None,
                "action": Audit.Type.Insert,
                "previous_value": None,
                "current_value": "343",
                "requires_auth": False,
                "user_id": self.commander.pk,
                "instance_id": self.instance.pk,
                "field": "udf:height"
            }, {
                "model": "udf:%s" % cudf.pk,
                "ref": None,
                "action": Audit.Type.Insert,
                "previous_value": None,
                "current_value": "water",
                "requires_auth": False,
                "user_id": self.commander.pk,
                "instance_id": self.instance.pk,
                "field": "udf:action"
            }],
            user=self.officer)

    def test_udf_collection_audits_not_shown_with_no_permissions(self):
        make_collection_udf(self.instance, 'Stew')
        set_write_permissions(self.instance, self.commander, 'Plot',
                              ['udf:Stew'])
        set_read_permissions(self.instance, self.officer, 'Plot',
                             self.plot.tracked_fields)

        self.plot.udfs['Stew'] = [{'action': 'water', 'height': 343}]
        self.plot.save_with_user(self.commander)

        self.check_audits(
            "/blah/?page_size=2&exclude_pending=true",
            [self.next_plot_delta, self.plot_delta], user=self.officer)

    def test_only_show_audits_for_permitted_fields(self):
        set_invisible_permissions(self.instance, self.commander, 'Plot',
                                  self.plot.tracked_fields)
        set_invisible_permissions(self.instance, self.commander, 'Tree',
                                  self.tree.tracked_fields)

        req = self.factory.get('/blah/')
        req.user = self.commander
        result = edits(req, self.instance)['audits']
        tree_audit_fields = {
            audit.field for audit in result if audit.model == 'tree'}
        plot_audit_fields = {
            audit.field for audit in result if audit.model == 'plot'}

        self.assertLessEqual(tree_audit_fields,
                             self.tree.visible_fields(self.commander))
        self.assertLessEqual(plot_audit_fields,
                             self.plot.visible_fields(self.commander))

    def test_system_user_edits_hidden(self):
        self.check_audits('/blah/?page_size=2',
                          [self.next_plot_delta, self.plot_delta])
        self.check_user_audits('/blah/?page_size=2&instance_id=%s'
                               % self.instance.pk, self.commander.username,
                               [self.next_plot_delta, self.plot_delta])

        # Add the system user to the instance with "commander" permissions
        system_user = User.system_user()
        InstanceUser(instance=self.instance, user=system_user,
                     role=self.commander.get_role(self.instance)
                     ).save_with_user(system_user)

        self.plot.width += 42
        self.plot.save_with_user(system_user)

        # There is now a system user audit on the plot
        self.assertEqual(1, len(Audit.objects.filter(model_id=self.plot.pk,
                                                     model='Plot',
                                                     user=system_user)))

        # But the audits returned by the view are the same
        self.check_audits('/blah/?page_size=2',
                          [self.next_plot_delta, self.plot_delta])
        self.check_user_audits('/blah/?page_size=2&instance_id=%s'
                               % self.instance.pk, self.commander.username,
                               [self.next_plot_delta, self.plot_delta])


class SpeciesViewTests(ViewTestCase):

    def setUp(self):
        super(SpeciesViewTests, self).setUp()
        self.instance = make_instance()
        self.commander = make_commander_user(self.instance)

        self.species_dict = [
            {'common_name': "apple 'Red Devil'", 'genus': 'applesauce'},
            {'common_name': 'asian cherry', 'genus': 'cherrificus'},
            {'common_name': 'cherrytree', 'genus': 'cherritius',
             'cultivar': 'asian'},
            {'common_name': 'elm', 'genus': 'elmitius'},
            {'common_name': 'oak', 'genus': 'acorn',
             'species': 'oakenitus'}
        ]
        self.species_json = [
            {'tokens': {'apple', 'Red', 'Devil', 'applesauce'}},
            {'tokens': {'asian', 'cherry', 'cherrificus'}},
            {'tokens': {'cherrytree', 'cherritius', 'asian'}},
            {'tokens': {'elm', 'elmitius'}},
            {'tokens': {'oak', 'acorn', 'oakenitus'}}
        ]
        for i, item in enumerate(self.species_dict):
            species = Species(common_name=item.get('common_name', ''),
                              genus=item.get('genus', ''),
                              species=item.get('species', ''),
                              cultivar=item.get('cultivar', ''),
                              otm_code=str(i),
                              instance=self.instance)
            species.save_with_user(self.commander)

            js_species = self.species_json[i]
            js_species['id'] = species.id
            js_species['common_name'] = species.common_name
            js_species['scientific_name'] = species.scientific_name
            js_species['value'] = species.display_name
            js_species['genus'] = species.genus
            js_species['species'] = species.species
            js_species['cultivar'] = species.cultivar
            js_species['other_part_of_name'] = species.other_part_of_name

    def test_get_species_list(self):
        self.assertEqual(species_list(make_request(), self.instance),
                         self.species_json)

    def test_get_species_list_max_items(self):
        self.assertEqual(
            species_list(make_request({'max_items': 3}), self.instance),
            self.species_json[:3])


class UserViewTests(ViewTestCase):

    def setUp(self):
        super(UserViewTests, self).setUp()
        self.instance.is_public = True
        self.instance.save()

        self.joe = make_commander_user(self.instance, 'joe')
        add_default_permissions(self.instance, [self.instance.default_role])

    def test_get_by_username(self):
        context = user(make_request(), self.joe.username)
        self.assertEqual(self.joe.username, context['user'].username,
                         'the user view should return a dict with user with '
                         '"username" set to %s ' % self.joe.username)
        self.assertEqual(list, type(context['audits']),
                         'the user view should return a list of audits')

    def test_get_with_invalid_username_returns_404(self):
        self.assertRaises(Http404, user, make_request(),
                          'no_way_this_is_a_username')

    def test_all_private_audits_are_filtered_out(self):
        plot = Plot(instance=self.instance, geom=self.instance.center)
        plot.save_with_user(self.joe)

        context = user(make_request(), self.joe.username)

        # Can always see public audits
        self.assertTrue(len(context['audits']) > 0)

        self.instance.is_public = False
        self.instance.save()

        # Can't see private audits
        context = user(make_request(), self.joe.username)
        self.assertTrue(len(context['audits']) == 0)

        # Can see audits if the 'logged in' user has an
        # InstanceUser on that instance
        self.assertTrue(self.instance.is_accessible_by(self.joe))

        context = user(make_request(user=self.joe), self.joe.username)
        self.assertTrue(len(context['audits']) > 0)


class UserUpdateViewTests(ViewTestCase):

    def setUp(self):
        super(UserUpdateViewTests, self).setUp()
        self.instance.is_public = True
        self.instance.save()
        self.public = make_apprentice_user(self.instance, 'public')
        self.joe = make_commander_user(self.instance, 'joe')

    def assertOk(self, response):
        if (issubclass(response.__class__, HttpResponse)):
            context = json.loads(response.content)
            self.assertEqual(200, response.status_code)
        else:
            context = response
        self.assertTrue('ok' in context)
        self.assertFalse('globalErrors' in context)
        self.assertFalse('validationErrors' in context)

    def assertBadRequest(self, response):
        self.assertTrue(issubclass(response.__class__, HttpResponse))
        self.assertEqual(400, response.status_code)
        context = json.loads(response.content)
        self.assertFalse('ok' in context)
        self.assertTrue('globalErrors' in context)

    def test_empty_update_returns_ok(self):
        self.assertOk(update_user(
            make_request(user=self.joe), self.joe))

    def test_change_first_name(self):
        self.joe.first_name = 'Joe'
        self.joe.save()
        update = b'{"user.first_name": "Joseph"}'
        self.assertOk(update_user(
            make_request(user=self.joe, body=update), self.joe))
        self.assertEqual('Joseph',
                         User.objects.get(username='joe').first_name,
                         'The first_name was not updated')

    def test_expects_keys_prefixed_with_user(self):
        self.joe.name = 'Joe'
        self.joe.save()
        update = b'{"name": "Joseph"}'
        response = return_400_if_validation_errors(update_user)(
            make_request(user=self.joe, body=update), self.joe)
        self.assertBadRequest(response)
        context = json.loads(response.content)
        self.assertFalse('validationErrors' in context)

    def test_email_validation(self):
        self.joe.email = 'joe@gmail.com'
        self.joe.save()
        update = b'{"user.email": "@not_valid@"}'
        response = return_400_if_validation_errors(update_user)(
            make_request(user=self.joe, body=update), self.joe)
        self.assertBadRequest(response)
        context = json.loads(response.content)
        self.assertTrue('fieldErrors' in context)
        self.assertTrue('user.email' in context['fieldErrors'])

    def test_cant_change_password_through_update_view(self):
        self.joe.set_password = 'joe'
        self.joe.save()
        update = b'{"user.password": "sekrit"}'
        self.assertBadRequest(return_400_if_validation_errors(update_user)(
            make_request(user=self.joe, body=update), self.joe))


class InstanceUserViewTests(ViewTestCase):

    def setUp(self):
        super(InstanceUserViewTests, self).setUp()

        self.commander = make_user(username="commander", password='pw')

    def test_get_by_username_redirects(self):
        res = instance_user_page(make_request(),
                                 self.instance.url_name,
                                 self.commander.username)
        expected_url = '/users/%s/?instance_id=%d' %\
            (self.commander.username, self.instance.id)
        self.assertEqual(res.status_code, 302, "should be a 302 Found \
            temporary redirect")
        self.assertEqual(expected_url, res['Location'],
                         'the view should redirect to %s not %s ' %
                         (expected_url, res['Location']))

    def test_get_with_invalid_username_redirects(self):
        test_username = 'no_way_username'
        res = instance_user_page(make_request(),
                                 self.instance.url_name,
                                 test_username)
        expected_url = '/users/%s/?instance_id=%d' %\
            (test_username, self.instance.id)
        self.assertEqual(res.status_code, 302, "should be a 302 Found \
            temporary redirect")
        self.assertEqual(expected_url, res['Location'],
                         'the view should redirect to %s not %s ' %
                         (expected_url, res['Location']))


class SettingsJsViewTests(ViewTestCase):

    def assertInResponse(self, text, res):
        self.assertIn(text, str(res),
                      'expected %s to be in the response:\n%s' %
                      (text, str(res)))

    def assertNotInResponse(self, text, res):
        self.assertNotIn(text, str(res),
                         'expected %s to NOT be in the response:\n%s' %
                         (text, str(res)))

    def setUp(self):
        super(SettingsJsViewTests, self).setUp()
        self.user = make_commander_user(self.instance)
        self.req = make_request(user=self.user)
        self.req.session = MockSession()
        self.get_response = lambda: root_settings_js(self.req)

    @override_settings(TILE_HOST=None)
    def test_none_tile_hosts_omits_tilehosts_setting(self):
        self.assertNotInResponse('otm.settings.tileHosts',
                                 self.get_response().content.decode('utf-8'))

    @override_settings(TILE_HOST='{s}.a')
    def test_single_tile_host_in_tilehosts_setting(self):
        self.assertInResponse('otm.settings.tileHost = "{s}.a";',
                              self.get_response().content.decode('utf-8'))


class InstanceSettingsJsViewTests(SettingsJsViewTests):
    """
    The settings.js view for an instance contains all the same
    settings as the root settings.js view, so this inherited
    test case ensures that we run all the root tests on the
    instance versision of the view as well.
    """
    def setUp(self):
        super(InstanceSettingsJsViewTests, self).setUp()
        self.get_response = lambda: instance_settings_js(
            self.req, self.instance.url_name)


class ScssCompilationTests(ViewTestCase):
    def test_css_content_differs_by_argument(self):
        request1 = self.factory.get("", {"primary-color": "fff",
                                         "secondary-color": "fff"})
        request2 = self.factory.get("", {"primary-color": "000000",
                                         "secondary-color": "000"})
        css1 = compile_scss(request1)
        css2 = compile_scss(request2)

        self.assertNotEqual(css1, css2)

    def test_compile_scss_raises_on_invalid_values(self):
        request = self.factory.get("", {"primary-color": "ffg"})
        with self.assertRaises(ValidationError):
            compile_scss(request)

        request = self.factory.get("", {"-color": "fff"})
        with self.assertRaises(ValidationError):
            compile_scss(request)


class DeleteViewTests(ViewTestCase):
    def setUp(self):
        super(DeleteViewTests, self).setUp()
        self.p1 = Point(-7615441.0, 5953519.0)

        self.instance = make_instance(point=self.p1)
        self.user = make_commander_user(self.instance)

        self.request = self.factory.get('')
        self.request.user = self.user

    def test_delete_plot_view_failure(self):
        plot = Plot(geom=self.p1, instance=self.instance)
        plot.save_with_user(self.user)
        self.assertEqual(Plot.objects.count(), 1)

        Tree(plot=plot, instance=self.instance,
             diameter=10).save_with_user(self.user)

        with self.assertRaises(ValidationError):
            delete_map_feature(self.request, self.instance, plot.pk)

        self.assertEqual(Plot.objects.count(), 1)

    def test_delete_plot_view_success(self):
        plot = Plot(geom=self.p1, instance=self.instance)
        plot.save_with_user(self.user)
        self.assertEqual(Plot.objects.count(), 1)

        raw_response = delete_map_feature(self.request, self.instance, plot.pk)

        self.assertEqual(raw_response, {'ok': True})
        self.assertEqual(Plot.objects.count(), 0)

    def test_delete_tree_view_failure(self):
        with self.assertRaises(Http404):
            delete_tree(self.request, self.instance, 1, 1)

    def test_delete_tree_view_success(self):
        plot = Plot(geom=self.p1, instance=self.instance)
        plot.save_with_user(self.user)

        tree = Tree(plot=plot, instance=self.instance, diameter=10)
        tree.save_with_user(self.user)

        self.assertEqual(Tree.objects.count(), 1)

        raw_response = delete_tree(self.request, self.instance,
                                   plot.pk, tree.pk)

        self.assertEqual(raw_response, {'ok': True})
        self.assertEqual(Tree.objects.count(), 0)


class ForgotUsernameTests(ViewTestCase):
    def setUp(self):
        super(ForgotUsernameTests, self).setUp()
        self.user = make_plain_user('joe')

    def test_sends_email_for_existing_user(self):
        resp = forgot_username(make_request({'email': self.user.email},
                                            method='POST'))

        self.assertEqual(resp, {'email': self.user.email})

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.username, mail.outbox[0].body)

    def test_no_email_if_doesnt_exist(self):
        resp = forgot_username(make_request({'email': 'doesnt@exist.co.uk'},
                                            method='POST'))

        self.assertEqual(resp, {'email': 'doesnt@exist.co.uk'})

        self.assertEqual(len(mail.outbox), 0)


class UserInstancesViewTests(OTMTestCase):
    def setUp(self):
        self.user_a = make_plain_user('a')
        self.user_b = make_plain_user('b')

        # User a belongs to instance a
        self.a = make_instance('a')
        make_instance_user(self.a, self.user_a)

        # User b belongs to instances b and b_public
        self.b = make_instance('b')
        self.b_public = make_instance('b_public', is_public=True)
        make_instance_user(self.b, self.user_b)
        make_instance_user(self.b_public, self.user_b)

        # Users a and b belong to instance ab
        self.ab = make_instance('ab')
        make_instance_user(self.ab, self.user_a)
        make_instance_user(self.ab, self.user_b)

        self.c = make_instance('c')

    def test_a_views_a(self):
        # User a views their own instances
        instances = get_user_instances(self.user_a, self.user_a, self.c)
        self.assertEqual(list(instances), [self.a, self.ab, self.c])

    def test_a_views_b(self):
        # User a views b's instances
        instances = get_user_instances(self.user_a, self.user_b, self.c)
        self.assertEqual(list(instances), [self.ab, self.b_public])

    def test_anonymous_views_b(self):
        # User anonymous views b's instances
        instances = get_user_instances(None, self.user_b, self.c)
        self.assertEqual(list(instances), [self.b_public])


@override_settings(VIEWABLE_INSTANCES_FUNCTION=None)
class InstanceListTest(OTMTestCase):
    def setUp(self):
        self.i1 = make_instance()
        self.i1.is_public = True
        self.i1.save()

        commander = make_commander_user(instance=self.i1)

        plot1 = Plot(instance=self.i1, geom=self.i1.center)
        plot1.save_with_user(commander)

        plot2 = Plot(instance=self.i1, geom=self.i1.center)
        plot2.save_with_user(commander)

        tree = Tree(plot=plot1, instance=self.i1)
        tree.save_with_user(commander)

    def test_instance_list_results(self):
        instance_list = public_instances_geojson(make_request())

        self.assertEqual(1, len(instance_list))

        instance_dict = instance_list[0]

        # Is GeoJSON
        self.assertIn('type', instance_dict)
        self.assertIn('geometry', instance_dict)
        self.assertIn('properties', instance_dict)

        self.assertEqual(self.i1.name, instance_dict['properties']['name'])
        self.assertEqual(2, instance_dict['properties']['plot_count'])

    def test_instance_list_only_public(self):
        private_instance = make_instance()

        private_instance.is_public = False
        private_instance.save()

        other_instance = make_instance()
        other_instance.is_public = True
        other_instance.save()

        self.assertEqual(2, len(public_instances_geojson(make_request())))


class UserAutocompleteTest(OTMTestCase):
    def setUp(self):
        self.i1 = make_instance()
        self.i2 = make_instance()

        self.mike = make_user(instance=self.i1, username='mike')
        self.also_mike = make_user(instance=self.i1, username='i-am-mike')
        self.maria = make_user(instance=self.i1, username='Maria')
        self.matt = make_user(instance=self.i2, username='MATT')

    def assert_users_in_list(self, instance, params, *expected_users):
        users_list = users(make_request(params), instance)
        self.assertEqual(len(users_list), len(expected_users))

        for i in range(0, len(expected_users)):
            user_dict = users_list[i]
            user = expected_users[i]
            self.assertIn('username', user_dict)
            self.assertIn('id', user_dict)
            self.assertEqual(user.username, user_dict['username'])
            self.assertEqual(user.pk, user_dict['id'])

    def test_full_results(self):
        self.assert_users_in_list(self.i2, {}, self.matt)

    def test_filtering_and_sorting(self):
        self.assert_users_in_list(self.i1, {}, self.also_mike, self.maria,
                                  self.mike)
        self.assert_users_in_list(self.i1, {'q': 'M'}, self.mike, self.maria,
                                  self.also_mike)
        self.assert_users_in_list(self.i1, {'q': 'Mi'}, self.mike,
                                  self.also_mike)

    def test_max(self):
        self.assert_users_in_list(self.i1, {}, self.also_mike, self.maria,
                                  self.mike)
        self.assert_users_in_list(self.i1, {'max_items': '1'}, self.also_mike)
