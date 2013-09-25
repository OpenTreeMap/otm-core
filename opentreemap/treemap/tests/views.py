from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import os.path
import shutil
import tempfile
import json
import unittest
from StringIO import StringIO

from django.test import TestCase
from django.test.utils import override_settings
from django.test.client import RequestFactory
from django.http import Http404, HttpResponse
from django.core.exceptions import ValidationError
from django.db import connection

from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import Point, MultiPolygon

from ecobenefits.models import ITreeRegion

from treemap.udf import UserDefinedFieldDefinition

from treemap.audit import (Role, Audit, approve_or_reject_audit_and_apply,
                           approve_or_reject_audits_and_apply,
                           FieldPermission)

from treemap.models import (Instance, Species, User, Plot, Tree, TreePhoto,
                            InstanceUser, BenefitCurrencyConversion)

from treemap.views import (species_list, boundary_to_geojson, plot_detail,
                           boundary_autocomplete, audits, user_audits,
                           search_tree_benefits, user, instance_user_view,
                           update_plot_and_tree, update_user, add_tree_photo,
                           root_settings_js_view, instance_settings_js_view,
                           compile_scss)

from treemap.tests import (ViewTestCase, make_instance, make_officer_user,
                           make_commander_user, make_apprentice_user,
                           make_simple_boundary, make_request,
                           add_field_permissions, MockSession)

import psycopg2

from django.db.models.query import QuerySet


class InstanceValidationTest(TestCase):

    def setUp(self):

        global_role = Role(name='global', rep_thresh=0)
        global_role.save()

        p = Point(-8515941.0, 4953519.0)
        self.instance1 = Instance(name='i1', geo_rev=0, center=p,
                                  default_role=global_role)

        self.instance1.save()

        self.instance2 = Instance(name='i2', geo_rev=0, center=p,
                                  default_role=global_role)

        self.instance2.save()


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

    def test_boundary_to_geojson_view(self):
        boundary = make_simple_boundary("Hello, World", 1)
        self.instance.boundaries.add(boundary)
        self.instance.save()
        response = boundary_to_geojson(
            make_request(),
            self.instance,
            boundary.pk)

        self.assertEqual(response.content, boundary.geom.geojson)

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


def media_dir(f):
    "Helper method for MediaTest classes to force a specific media dir"
    def m(self):
        with self._media_dir():
            f(self)
    return m


class MediaTest(TestCase):
    def setUp(self):
        self.imageDir = tempfile.mkdtemp()
        self.mediaUrl = '/testingmedia/'
        self.instance = make_instance()

    def tearDown(self):
        shutil.rmtree(self.imageDir)

    def load_resource(self, name):
        module_dir = os.path.dirname(__file__)
        path = os.path.join(module_dir, 'resources', name)
        return file(path)

    def _media_dir(self):
        return self.settings(DEFAULT_FILE_STORAGE=
                             'django.core.files.storage.FileSystemStorage',
                             MEDIA_ROOT=self.imageDir,
                             MEDIA_URL=self.mediaUrl)

    def assertPathExists(self, path):
        self.assertTrue(os.path.exists(path), '%s does not exist' % path)

    def assertPathDoesNotExist(self, path):
        self.assertFalse(os.path.exists(path), '%s exists' % path)


class PlotImageUpdateTest(MediaTest):
    def setUp(self):
        super(PlotImageUpdateTest, self).setUp()

        self.user = make_commander_user(self.instance)

        # Give this plot a unique number so we can check for
        # correctness
        self.plot = Plot(
            geom=Point(0, 0), instance=self.instance, pk=449293)

        self.plot.save_with_user(self.user)

        self.tree = Tree(instance=self.instance, plot=self.plot)
        self.tree.save_with_user(self.user)

    def _make_audited_request(self):
        # Update user to only have pending permission
        perms = self.user.get_instance_permissions(self.instance)

        def update_perms(plevel):
            for perm in perms:
                perm.permission_level = plevel
                perm.save()

        update_perms(FieldPermission.WRITE_WITH_AUDIT)

        # Delete any audits already in the system
        Audit.objects.all().delete()

        self.assertEqual(TreePhoto.objects.count(), 0)

        tree_image = self.load_resource('tree1.gif')

        photo = self._make_tree_photo_request(
            tree_image, self.plot.pk, self.tree.pk)

        # Restore permissions
        update_perms(FieldPermission.WRITE_DIRECTLY)

        return photo

    @media_dir
    def test_can_create_pending_image(self):
        objects = self.tree.treephoto_set.all()
        self.assertEqual(len(objects), 0)

        self._make_audited_request()

        objects = self.tree.treephoto_set.all()
        self.assertEqual(len(objects), 0)

        # Approve audits
        approve_or_reject_audits_and_apply(
            Audit.objects.all(), self.user, approved=True)

        # Verify tree photo exists
        objects = self.tree.treephoto_set.all()
        self.assertEqual(len(objects), 1)

        photo = objects[0]

        self.assertTreePhotoExists(photo)

    @media_dir
    def test_can_reject_pending_image(self):
        objects = self.tree.treephoto_set.all()
        self.assertEqual(len(objects), 0)

        self._make_audited_request()

        objects = self.tree.treephoto_set.all()
        self.assertEqual(len(objects), 0)

        # Reject audits
        approve_or_reject_audits_and_apply(
            Audit.objects.all(), self.user, approved=False)

        # Verify no tree photos were created
        objects = self.tree.treephoto_set.all()
        self.assertEqual(len(objects), 0)

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
            self.assertEqual(path.index(self.imageDir), 0)
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
        return add_tree_photo(make_request(user=self.user,
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
    def test_can_create_and_apply_pending_images(self):
        pass

    @media_dir
    def test_non_authorized_users_cant_create_images(self):
        pass


class PlotUpdateTest(unittest.TestCase):
    def setUp(self):
        User._system_user.save_base()

        self.instance = make_instance()
        self.user = make_commander_user(self.instance)
        add_field_permissions(self.instance, self.user,
                              'Plot', ['udf:Test choice', 'udf:Test col'])
        add_field_permissions(self.instance, self.user,
                              'Tree', ['udf:Test col'])

        self.p = Point(-7615441.0, 5953519.0)

        self.choice_field = UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'choice',
                                 'choices': ['a', 'b', 'c']}),
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

        self.plot = Plot(instance=self.instance, geom=self.p)
        self.plot.save_with_user(self.user)

        psycopg2.extras.register_hstore(connection.cursor(), globally=True)

    def tearDown(self):
        self.plot.delete_with_user(self.user)
        self.choice_field.delete()
        self.user.delete_with_user(User._system_user)

    def test_creates_new_plot(self):
        plot = Plot(instance=self.instance)

        update = json.dumps({'plot.geom': {'x': 4, 'y': 9},
                             'plot.readonly': False})

        created_plot = update_plot_and_tree(make_request(user=self.user,
                                                         body=update),
                                            plot)

        created_plot_update = Plot.objects.get(pk=created_plot.pk)
        self.assertIsNotNone(created_plot_update, created_plot_update.pk)
        self.assertEqual(created_plot_update.geom.x, 4.0)
        self.assertEqual(created_plot_update.geom.y, 9.0)
        self.assertIsNone(created_plot_update.current_tree())

        created_plot_update.delete_with_user(self.user)

    def test_creates_new_plot_and_tree(self):
        plot = Plot(instance=self.instance)

        update = json.dumps({'plot.geom': {'x': 4, 'y': 9},
                             'plot.readonly': False,
                             'tree.readonly': False})

        created_plot = update_plot_and_tree(make_request(user=self.user,
                                                         body=update),
                                            plot)

        created_plot_update = Plot.objects.get(pk=created_plot.pk)
        self.assertIsNotNone(created_plot_update, created_plot_update.pk)
        self.assertEqual(created_plot_update.geom.x, 4.0)
        self.assertEqual(created_plot_update.geom.y, 9.0)
        self.assertIsNotNone(created_plot_update.current_tree())

        created_plot_update.current_tree().delete_with_user(self.user)
        created_plot_update.delete_with_user(self.user)

    def test_invalid_udf_name_fails(self):
        update = json.dumps({'plot.udf:INVaLiD UTF': 'z'})

        self.assertRaises(KeyError,
                          update_plot_and_tree,
                          make_request(user=self.user, body=update),
                          self.plot)

    def test_collection_udf_works(self):
        plot_data = [{'pick': 'a', 'num': 4},
                     {'pick': 'b', 'num': 9}]
        tree_data = [{'pick': 'c', 'num': 1},
                     {'pick': 'a', 'num': 33}]

        update = json.dumps({'plot.udf:Test col': plot_data,
                             'tree.udf:Test col': tree_data})

        update_plot_and_tree(
            make_request(user=self.user, body=update), self.plot)

        updated_plot = Plot.objects.get(pk=self.plot.pk)

        plotudf = updated_plot.udfs['Test col']
        for exp, act in zip(plot_data, plotudf):
            self.assertDictContainsSubset(exp, act)

        treeudf = updated_plot.current_tree().udfs['Test col']

        for exp, act in zip(tree_data, treeudf):
            self.assertDictContainsSubset(exp, act)

    def test_collection_udf_errors_show_up_as_validations(self):
        plot_data = [{'pick': 'invalid choice', 'num': 4}]

        update = json.dumps({'plot.udf:Test col':
                             plot_data})

        self.assertRaises(ValidationError,
                          update_plot_and_tree,
                          make_request(user=self.user, body=update),
                          self.plot)

    def test_malformed_udf_fails(self):
        update = json.dumps({'plot.udf:Test choice': 'z'})

        try:
            update_plot_and_tree(make_request(user=self.user,
                                              body=update),
                                 self.plot)
            raise AssertionError('expected update to raise validation error')
        except ValidationError as e:

            self.assertIn('plot.udf:Test choice', e.message_dict)

    def test_grouping_failed_udf(self):
        update = json.dumps({'plot.udf:Test choice': 'z',
                             'plot.length': 'bad'})

        try:
            update_plot_and_tree(make_request(user=self.user,
                                              body=update),
                                 self.plot)
            raise AssertionError('expected update to raise validation error')
        except ValidationError as e:
            self.assertIn('plot.udf:Test choice', e.message_dict)
            self.assertIn('plot.length', e.message_dict)

    def test_simple_update(self):
        self.assertNotEqual(self.plot.length, 20)
        self.assertNotEqual(self.plot.width, 25)

        update = json.dumps({'plot.length': 20,
                             'plot.width': 25,
                             'plot.udf:Test choice': 'b'})

        rslt = update_plot_and_tree(make_request(user=self.user,
                                                 body=update),
                                    self.plot)

        self.assertEqual(rslt.pk, self.plot.pk)

        plot = Plot.objects.get(pk=self.plot.pk)

        self.assertEqual(plot.length, 20)
        self.assertEqual(plot.width, 25)
        self.assertEqual(plot.udfs['Test choice'], 'b')

    def test_validates_numeric_fields(self):
        update = json.dumps({'plot.length': 'length'})

        try:
            update_plot_and_tree(make_request(user=self.user,
                                              body=update),
                                 self.plot)
            raise AssertionError('expected update to raise validation error')
        except ValidationError as e:
            self.assertIn('plot.length', e.message_dict)

    def test_edit_tree_creates_tree(self):
        self.assertIsNone(self.plot.current_tree())

        update = json.dumps({'tree.height': 9})
        update_plot_and_tree(make_request(user=self.user,
                                          body=update),
                             self.plot)

        self.assertIsNotNone(
            Plot.objects.get(pk=self.plot.pk).current_tree())

    def test_doesnt_edit_tree_if_plot_fails(self):
        tree = Tree(plot=self.plot, instance=self.plot.instance)
        tree.height = 92
        tree.save_with_user(self.user)

        update = json.dumps({'plot.length': 'length',
                             'tree.height': 42})

        try:
            update_plot_and_tree(make_request(user=self.user,
                                              body=update),
                                 self.plot)
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

        update = json.dumps({'plot.length': 92,
                             'tree.height': 'height'})

        try:
            update_plot_and_tree(make_request(user=self.user,
                                              body=update),
                                 self.plot)
            raise AssertionError('expected update to raise validation error')
        except ValidationError as e:
            self.assertIn('tree.height', e.message_dict)

        updated_plot = Plot.objects.get(pk=self.plot.pk)

        self.assertEqual(updated_plot.length, 100)


class PlotViewTest(ViewTestCase):

    def setUp(self):
        super(PlotViewTest, self).setUp()

        self.instance = make_instance()
        self.user = make_commander_user(self.instance)

        self.p = Point(-7615441.0, 5953519.0)

        ITreeRegion.objects.create(
            code='PiedmtCLT',
            geometry=MultiPolygon((self.p.buffer(10),)))

    def test_eco_benefits_change_based_on_zone(self):
        p1 = Point(5000, 5000)
        p1b = Point(5001, 5001)
        p2 = Point(-5000, -5000)
        m1 = MultiPolygon([p1.buffer(50)])
        m2 = MultiPolygon([p2.buffer(50)])

        s = Species.objects.create(
            symbol='BDM OTHER',
            common_name='other',
            itree_code='BDM OTHER')

        ITreeRegion.objects.all().delete()
        ITreeRegion.objects.create(code='NoEastXXX', geometry=m1)
        ITreeRegion.objects.create(code='PiedmtCLT', geometry=m2)

        plot1 = Plot(instance=self.instance, geom=p1)
        plot1.save_with_user(self.user)
        tree1 = Tree(plot=plot1,
                     instance=plot1.instance,
                     diameter=20.0,
                     species=s)

        tree1.save_with_user(self.user)

        def get_benefits_from_request():
            details = plot_detail(make_request(user=self.user),
                                  self.instance,
                                  plot1.pk)

            self.assertIn('benefits', details)
            self.assertTrue(len(details['benefits']) > 2)
            return details['benefits']

        benefits1 = get_benefits_from_request()

        plot1.geom = p2
        plot1.save_with_user(self.user)

        benefits2 = get_benefits_from_request()

        self.assertNotEqual(benefits1, benefits2)

        plot1.geom = p1b
        plot1.save_with_user(self.user)

        benefits3 = get_benefits_from_request()

        self.assertEqual(benefits1, benefits3)

    def test_simple_audit_history(self):
        plot = Plot(instance=self.instance, geom=self.p)
        plot.save_with_user(self.user)

        plot.width = 9
        plot.save_with_user(self.user)

        details = plot_detail(make_request(user=self.user),
                              self.instance,
                              plot.pk)

        self.assertIn('recent_activity', details)

        recent_activity = details['recent_activity']

        audit = recent_activity[0]
        self.assertEqual(audit.model, 'Plot')
        self.assertEqual(audit.field, 'width')

    def test_tree_audits_show_up_too(self):
        plot = Plot(instance=self.instance, geom=self.p)
        plot.save_with_user(self.user)

        tree = Tree(instance=self.instance, plot=plot)
        tree.save_with_user(self.user)

        tree.readonly = True
        tree.save_with_user(self.user)

        details = plot_detail(make_request(user=self.user),
                              self.instance,
                              plot.pk)

        self.assertIn('recent_activity', details)

        recent_activity = details['recent_activity']
        readonly_audit = recent_activity[0]
        insert_audit = recent_activity[1]

        self.assertEqual(readonly_audit.model, 'Tree')
        self.assertEqual(readonly_audit.field, 'readonly')
        self.assertEqual(readonly_audit.model_id, tree.pk)
        self.assertEqual(readonly_audit.action, Audit.Type.Update)

        self.assertEqual(insert_audit.model, 'Tree')
        self.assertEqual(insert_audit.model_id, tree.pk)
        self.assertEqual(insert_audit.action, Audit.Type.Insert)

    def test_plot_with_tree(self):
        species = Species(itree_code='CEM OTHER')
        species.save()

        plot_w_tree = Plot(geom=self.p, instance=self.instance)
        plot_w_tree.save_with_user(self.user)

        tree = Tree(plot=plot_w_tree, instance=self.instance,
                    diameter=10, species=species)
        tree.save_with_user(self.user)

        context = plot_detail(make_request(user=self.user),
                              self.instance, plot_w_tree.pk)

        self.assertEquals(plot_w_tree, context['plot'])
        self.assertIn('benefits', context)

    def test_plot_without_tree(self):
        plot_wo_tree = Plot(geom=self.p, instance=self.instance)
        plot_wo_tree.save_with_user(self.user)

        context = plot_detail(make_request(user=self.user),
                              self.instance, plot_wo_tree.pk)

        self.assertEquals(plot_wo_tree, context['plot'])
        self.assertNotIn('benefits', context)


class RecentEditsViewTest(ViewTestCase):

    def setUp(self):
        self.longMessage = True

        self.instance = make_instance(is_public=True)
        self.instance2 = make_instance('i2', is_public=True)
        self.officer = make_officer_user(self.instance)
        self.commander = make_commander_user(self.instance)
        self.pending_user = make_apprentice_user(self.instance)
        iuser = InstanceUser(instance=self.instance2, user=self.commander,
                             role=self.commander.get_role(self.instance))
        iuser.save_with_user(self.commander)

        self.p1 = Point(-7615441.0, 5953519.0)
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
            for k, v in expected.iteritems():
                self.assertEqual(v, generated[k], "key [%s]" % k)

    def check_audits(self, url, dicts):
        req = self.factory.get(url)
        req.user = AnonymousUser()
        resulting_audits = [audit.dict()
                            for audit
                            in audits(req, self.instance)['audits']]

        self._assert_dicts_equal(dicts, resulting_audits)

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
        self.check_audits('/blah/?page_size=1&page=1', [self.plot_delta])
        self.check_user_audits('/eblah/?page_size=1&page=1&instance_id=%s'
                               % self.instance.pk,
                               self.commander.username, [self.plot_delta])

    def test_model_filtering_errors(self):
        self.assertRaises(Exception,
                          self.check_audits,
                          "/blah/?model_id=%s&page=0&page_size=1" %
                          self.tree.pk, [])

        self.assertRaises(Exception,
                          self.check_audits,
                          "/blah/?model_id=%s&"
                          "models=Tree,Plot&page=0&page_size=1" %
                          self.tree.pk, [])

        self.assertRaises(Exception,
                          self.check_audits,
                          "/blah/?models=User&page=0&page_size=1", [])

        self.assertRaises(Exception,
                          self.check_user_audits,
                          "/blah/?model_id=%s&page=0&page_size=1"
                          "&instance_id=%s"
                          % (self.instance.pk, self.tree.pk),
                          self.commander.username, [])

        self.assertRaises(Exception,
                          self.check_user_audits,
                          "/blah/?model_id=%s&"
                          "models=Tree,Plot&page=0&page_size=1"
                          "&instance_id=%s"
                          % (self.instance.pk, self.tree.pk),
                          self.commander.username, [])

        self.assertRaises(Exception,
                          self.check_user_audits,
                          "/blah/?models=User&page=0&page_size=1",
                          "&instance_id=%s" % self.instance.pk,
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
            "/blah/?model_id=%s&models=Tree&page=0&page_size=1" % self.tree.pk,
            [specific_tree_delta])

        self.check_audits(
            "/blah/?model_id=%s&models=Plot&page=0&page_size=1" % self.plot.pk,
            [self.next_plot_delta])

        self.check_audits(
            "/blah/?models=Plot,Tree&page=0&page_size=3",
            [generic_plot_delta, generic_plot_delta, generic_tree_delta])

        self.check_audits(
            "/blah/?models=Plot&page=0&page_size=5",
            [generic_plot_delta] * 5)

        self.check_audits(
            "/blah/?models=Tree&page=0&page_size=5",
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
            "/blah/?model_id=%s&models=Tree&page=0&page_size=1" % self.tree.pk,
            self.officer.username, [specific_tree_delta])

        self.check_user_audits(
            "/blah/?model_id=%s&models=Plot&page=0&page_size=1&instance_id=%s"
            % (self.plot.pk, self.instance.pk),
            self.commander.username, [self.next_plot_delta])

        self.check_user_audits(
            "/blah/?models=Plot&page=0&page_size=3&instance_id=%s"
            % self.instance.pk, self.commander.username,
            [generic_plot_delta] * 3)

        self.check_user_audits(
            "/blah/?models=Tree&page=0&page_size=3", self.officer.username,
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


class SpeciesViewTests(ViewTestCase):

    def setUp(self):
        super(SpeciesViewTests, self).setUp()

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
            {'tokens': ['apple', 'Red', 'Devil', 'applesauce']},
            {'tokens': ['asian', 'cherry', 'cherrificus']},
            {'tokens': ['cherrytree', 'cherritius', 'asian']},
            {'tokens': ['elm', 'elmitius']},
            {'tokens': ['oak', 'acorn', 'oakenitus']}
        ]
        for i, item in enumerate(self.species_dict):
            species = Species(common_name=item.get('common_name'),
                              genus=item.get('genus'),
                              species=item.get('species'),
                              cultivar=item.get('cultivar'),
                              symbol=str(i))
            species.save()

            js_species = self.species_json[i]
            js_species['id'] = species.id
            js_species['common_name'] = species.common_name
            js_species['scientific_name'] = species.scientific_name
            js_species['value'] = species.display_name

    def test_get_species_list(self):
        self.assertEquals(species_list(make_request(), None),
                          self.species_json)

    def test_get_species_list_max_items(self):
        self.assertEquals(
            species_list(make_request({'max_items': 3}), None),
            self.species_json[:3])


class SearchTreeBenefitsTests(ViewTestCase):

    def setUp(self):
        super(SearchTreeBenefitsTests, self).setUp()
        self.instance = make_instance()
        self.commander = make_commander_user(self.instance)
        self.p1 = Point(-7615441.0, 5953519.0)

        ITreeRegion.objects.create(
            code='PiedmtCLT',
            geometry=MultiPolygon((self.p1.buffer(10),)))

        self.species_good = Species(itree_code='CEM OTHER')
        self.species_good.save()
        self.species_bad = Species()
        self.species_bad.save()

    def make_tree(self, diameter, species):
        plot = Plot(geom=self.p1, instance=self.instance)
        plot.save_with_user(self.commander)
        tree = Tree(plot=plot, instance=self.instance,
                    diameter=diameter, species=species)
        tree.save_with_user(self.commander)

    def search_benefits(self):
        request = make_request(
            {'q': json.dumps({'tree.readonly': {'IS': False}})})  # all trees
        result = search_tree_benefits(request, self.instance)
        return result

    def test_tree_with_species_and_diameter_included(self):
        self.make_tree(10, self.species_good)
        benefits = self.search_benefits()
        self.assertEqual(benefits['basis']['n_trees_used'], 1)

    def test_tree_without_diameter_ignored(self):
        self.make_tree(None, self.species_good)
        benefits = self.search_benefits()
        self.assertEqual(benefits['basis']['n_trees_used'], 0)

    def test_tree_without_species_ignored(self):
        self.make_tree(10, None)
        benefits = self.search_benefits()
        self.assertEqual(benefits['basis']['n_trees_used'], 0)

    def test_tree_without_itree_code_ignored(self):
        self.make_tree(10, self.species_bad)
        benefits = self.search_benefits()
        self.assertEqual(benefits['basis']['n_trees_used'], 0)

    def test_extrapolation_increases_benefits(self):
        self.make_tree(10, self.species_good)
        self.make_tree(20, self.species_good)
        self.make_tree(30, self.species_good)
        benefits = self.search_benefits()
        value = float(benefits['benefits'][0]['value'])

        self.make_tree(None, self.species_good)
        self.make_tree(10, None)
        benefits = self.search_benefits()
        value_with_extrapolation = float(benefits['benefits'][0]['value'])

        self.assertEqual(benefits['basis']['percent'], 0.6)
        self.assertGreater(self, value_with_extrapolation, value)

    def test_currency_is_empty_if_not_set(self):
        self.make_tree(10, self.species_good)
        benefits = self.search_benefits()

        for benefit in benefits['benefits']:
            self.assertNotIn('currency_saved', benefit)

    def test_currency_is_not_empty(self):
        benefit = BenefitCurrencyConversion(
            kwh_to_currency=2.0,
            stormwater_gal_to_currency=2.0,
            carbon_dioxide_lb_to_currency=2.0,
            airquality_aggregate_lb_to_currency=2.0,
            currency_symbol='$')

        benefit.save()
        self.instance.eco_benefits_conversion = benefit
        self.instance.save()

        self.make_tree(10, self.species_good)
        benefits = self.search_benefits()

        for benefit in benefits['benefits']:
            self.assertEqual(
                benefit['currency_saved'],
                '%d' % (float(benefit['value']) * 2.0))

        self.assertEqual(benefits['currency_symbol'], '$')


class UserViewTests(ViewTestCase):

    def setUp(self):
        super(UserViewTests, self).setUp()
        self.instance.is_public = True
        self.instance.save()

        self.joe = make_commander_user(self.instance, 'joe')

    def test_get_by_username(self):
        context = user(make_request(), self.joe.username)
        self.assertEquals(self.joe.username, context['user'].username,
                          'the user view should return a dict with user with '
                          '"username" set to %s ' % self.joe.username)
        self.assertEquals(QuerySet, type(context['audits']),
                          'the user view should return a queryset')

    def test_get_with_invalid_username_returns_404(self):
        self.assertRaises(Http404, user, make_request(),
                          'no_way_this_is_a_username')

    def test_all_private_audits_are_filtered_out(self):
        p = Point(-7615441.0, 5953519.0)
        plot = Plot(instance=self.instance, geom=p)
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
            self.assertEquals(200, response.status_code)
        else:
            context = response
        self.assertTrue('ok' in context)
        self.assertFalse('error' in context)
        self.assertFalse('validationErrors' in context)

    def assertForbidden(self, response):
        self.assertTrue(issubclass(response.__class__, HttpResponse))
        self.assertEquals(403, response.status_code)
        try:
            context = json.loads(response.content)
            self.assertFalse('ok' in context)
            self.assertTrue('error' in context)
        except ValueError:
            pass  # It is ok for the response to have no content

    def assertBadRequest(self, response):
        self.assertTrue(issubclass(response.__class__, HttpResponse))
        self.assertEquals(400, response.status_code)
        context = json.loads(response.content)
        self.assertFalse('ok' in context)
        self.assertTrue('error' in context)

    def test_empty_update_returns_ok(self):
        self.assertOk(update_user(
            make_request(user=self.joe), self.joe.username))

    def test_updating_someone_else_is_forbidden(self):
        self.assertForbidden(update_user(
            make_request(user=self.public), self.joe.username))

    def test_change_first_name(self):
        self.joe.first_name = 'Joe'
        self.joe.save()
        update = b'{"user.first_name": "Joseph"}'
        self.assertOk(update_user(
            make_request(user=self.joe, body=update), self.joe.username))
        self.assertEquals('Joseph',
                          User.objects.get(username='joe').first_name,
                          'The first_name was not updated')

    def test_expects_keys_prefixed_with_user(self):
        self.joe.name = 'Joe'
        self.joe.save()
        update = b'{"name": "Joseph"}'
        response = update_user(
            make_request(user=self.joe, body=update), self.joe.username)
        self.assertBadRequest(response)
        context = json.loads(response.content)
        self.assertFalse('validationErrors' in context)

    def test_email_validation(self):
        self.joe.email = 'joe@gmail.com'
        self.joe.save()
        update = b'{"user.email": "@not_valid@"}'
        response = update_user(
            make_request(user=self.joe, body=update), self.joe.username)
        self.assertBadRequest(response)
        context = json.loads(response.content)
        self.assertTrue('validationErrors' in context)
        self.assertTrue('user.email' in context['validationErrors'])

    def test_cant_change_password_through_update_view(self):
        self.joe.set_password = 'joe'
        self.joe.save()
        update = b'{"user.password": "sekrit"}'
        self.assertBadRequest(update_user(
            make_request(user=self.joe, body=update), self.joe.username))


class InstanceUserViewTests(ViewTestCase):

    def setUp(self):
        super(InstanceUserViewTests, self).setUp()

        self.commander = User(username="commander", password='pw')
        self.commander.save()

    def test_get_by_username_redirects(self):
        res = instance_user_view(make_request(),
                                 self.instance.url_name,
                                 self.commander.username)
        expected_url = '/users/%s?instance_id=%d' %\
            (self.commander.username, self.instance.id)
        self.assertEquals(res.status_code, 302, "should be a 302 Found \
            temporary redirect")
        self.assertEquals(expected_url, res['Location'],
                          'the view should redirect to %s not %s ' %
                          (expected_url, res['Location']))

    def test_get_with_invalid_username_redirects(self):
        test_username = 'no_way_username'
        res = instance_user_view(make_request(),
                                 self.instance.url_name,
                                 test_username)
        expected_url = '/users/%s?instance_id=%d' %\
            (test_username, self.instance.id)
        self.assertEquals(res.status_code, 302, "should be a 302 Found \
            temporary redirect")
        self.assertEquals(expected_url, res['Location'],
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
        self.get_response = lambda: root_settings_js_view(self.req)

    @override_settings(TILE_HOSTS=None)
    def test_none_tile_hosts_omits_tilehosts_setting(self):
        self.assertNotInResponse('otm.settings.tileHosts',
                                 self.get_response())

    @override_settings(TILE_HOSTS=[])
    def test_empty_tile_hosts_omits_empty_string_host(self):
        self.assertInResponse('otm.settings.tileHosts = [""];',
                              self.get_response())

    @override_settings(TILE_HOSTS=['a'])
    def test_single_tile_host_in_tilehosts_setting(self):
        self.assertInResponse('otm.settings.tileHosts = ["a"];',
                              self.get_response())

    @override_settings(TILE_HOSTS=['a', 'b:81'])
    def test_multiple_tile_hosts_in_tilehosts_setting(self):
        self.assertInResponse('otm.settings.tileHosts = ["a", "b:81"];',
                              self.get_response())


class InstanceSettingsJsViewTests(SettingsJsViewTests):
    """
    The settings.js view for an instance contains all the same
    settings as the root settings.js view, so this inherited
    test case ensures that we run all the root tests on the
    instance versision of the view as well.
    """
    def setUp(self):
        super(InstanceSettingsJsViewTests, self).setUp()
        self.get_response = lambda: instance_settings_js_view(
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
