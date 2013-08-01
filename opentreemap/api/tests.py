"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from StringIO import StringIO

from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.test.client import Client

from json import loads, dumps

from django.conf import settings
from urlparse import urlparse
import urllib
from api.test_utils import setupTreemapEnv, teardownTreemapEnv, mkPlot, mkTree

from treemap.models import Species, Plot, Tree, User
from treemap.tests import make_commander_role, make_apprentice_role
from treemap.audit import ReputationMetric, Audit

from api.models import APIKey, APILog
from api.views import (InvalidAPIKeyException, plot_or_tree_permissions,
                       plot_permissions,
                       _parse_application_version_header_as_dict)
from treemap.tests import create_mock_system_user

import os
import base64


API_PFX = "/api/v2"


create_mock_system_user()


def create_signer_dict(user):
    key = APIKey(user=user, key="TESTING", enabled=True, comment="")
    key.save()

    return {"HTTP_X_API_KEY": key.key}


def _get_path(parsed_url):
    """
    Taken from a class method in the Django test client
    """
    # If there are parameters, add them
    if parsed_url[3]:
        return urllib.unquote(parsed_url[2] + ";" + parsed_url[3])
    else:
        return urllib.unquote(parsed_url[2])


def send_json_body(url, body_object, client, method, sign_dict=None):
    """
    Serialize a list or dictionary to JSON then send it to an endpoint.
    The "post" method exposed by the Django test client assumes that you
    are posting form data, so you need to manually setup the parameters
    to override that default functionality.
    """
    body_string = dumps(body_object)
    body_stream = StringIO(body_string)
    parsed_url = urlparse(url)
    client_params = {
        'CONTENT_LENGTH': len(body_string),
        'CONTENT_TYPE': 'application/json',
        'PATH_INFO': _get_path(parsed_url),
        'QUERY_STRING': parsed_url[4],
        'REQUEST_METHOD': method,
        'wsgi.input': body_stream,
    }
    return _send_with_client_params(url, client, client_params, sign_dict)


def send_binary_body(url, body_stream, size, content_type,
                     client, method, sign_dict=None):
    parsed_url = urlparse(url)
    client_params = {
        'CONTENT_LENGTH': size,
        'CONTENT_TYPE': content_type,
        'PATH_INFO': _get_path(parsed_url),
        'QUERY_STRING': parsed_url[4],
        'REQUEST_METHOD': method,
        'wsgi.input': body_stream,
    }
    return _send_with_client_params(url, client, client_params, sign_dict)


def _send_with_client_params(url, client, client_params, sign_dict=None):
    if sign_dict is not None:
        client_params.update(sign_dict)

    return client.post(url, **client_params)


def post_json(url, body_object, client, sign_dict=None):
    """
    Serialize a list or dictionary to JSON then POST it to an endpoint.
    The "post" method exposed by the Django test client assumes that you
    are posting form data, so you need to manually setup the parameters
    to override that default functionality.
    """
    return send_json_body(url, body_object, client, 'POST', sign_dict)


def post_jpeg_file(url, file_path, client, sign_dict):
    return _post_binary_file(url, file_path, 'image/jpeg', client, sign_dict)


def post_png_file(url, file_path, client, sign_dict):
    return _post_binary_file(url, file_path, 'image/png', client, sign_dict)


def _post_binary_file(url, file_path, content_type, client, sign_dict=None):
    stat = os.stat(file_path)
    response = None
    f = open(file_path, 'rb')
    try:
        response = send_binary_body(
            url, f, stat.st_size, content_type, client, 'POST', sign_dict)
    finally:
        f.close()
    return response


def put_json(url, body_object, client, sign_dict=None):
    return send_json_body(url, body_object, client, 'PUT', sign_dict)


class Signing(TestCase):
    def setUp(self):
        settings.OTM_VERSION = "1.2.3"
        settings.API_VERSION = "2"

        setupTreemapEnv()

        self.u = User.objects.get(username="jim")

    def test_unsigned_will_fail(self):
        self.assertRaises(InvalidAPIKeyException,
                          self.client.get, "%s/version" % API_PFX)

    def test_signed_header(self):
        key = APIKey(user=self.u, key="TESTING", enabled=True, comment="")
        key.save()

        ret = self.client.get("%s/version" % API_PFX,
                              **{"HTTP_X_API_KEY": key.key})
        self.assertEqual(ret.status_code, 200)

    def test_url_param(self):
        key = APIKey(user=self.u, key="TESTING", enabled=True, comment="")
        key.save()

        ret = self.client.get("%s/version?apikey=%s" % (API_PFX, key.key))
        self.assertEqual(ret.status_code, 200)

    def test_disabled_keys_dont_work(self):
        key = APIKey(user=self.u, key="TESTING", enabled=False, comment="")
        key.save()

        self.assertRaises(InvalidAPIKeyException, self.client.get,
                          "%s/version" % API_PFX, **{"X-API-Key": key.key})

    def tearDown(self):
        teardownTreemapEnv()


class Authentication(TestCase):
    def setUp(self):
        setupTreemapEnv()

        self.u = User.objects.get(username="jim")
        self.u.set_password("password")
        self.u.save()

        amy = User.objects.get(username="amy")
        amy.set_password("password")
        amy.save()

        self.sign = create_signer_dict(self.u)

    def test_401(self):
        ret = self.client.get("%s/login" % API_PFX, **self.sign)
        self.assertEqual(ret.status_code, 401)

    def test_ok(self):
        auth = base64.b64encode("jim:password")
        withauth = dict(self.sign.items() +
                        [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        ret = self.client.get("%s/login" % API_PFX, **withauth)
        self.assertEqual(ret.status_code, 200)

    def test_malformed_auth(self):
        withauth = dict(self.sign.items() +
                        [("HTTP_AUTHORIZATION", "FUUBAR")])

        ret = self.client.get("%s/login" % API_PFX, **withauth)
        self.assertEqual(ret.status_code, 401)

        auth = base64.b64encode("foobar")
        withauth = dict(self.sign.items() +
                        [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        ret = self.client.get("%s/login" % API_PFX, **withauth)
        self.assertEqual(ret.status_code, 401)

    def test_bad_cred(self):
        auth = base64.b64encode("jim:passwordz")
        withauth = dict(self.sign.items() +
                        [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        ret = self.client.get("%s/login" % API_PFX, **withauth)
        self.assertEqual(ret.status_code, 401)

    def test_user_has_rep(self):

        carol = User(username='carol',
                     email="%s@test.org" % 'carol',
                     password='carol')

        carol.reputation = 1001
        carol.set_password('carol')
        carol.save()

        auth = base64.b64encode("%s:%s" %
                                (carol.username, carol.username))
        withauth = dict(create_signer_dict(carol).items() +
                        [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        ret = self.client.get("%s/login" % API_PFX, **withauth)

        self.assertEqual(ret.status_code, 200)

        json = loads(ret.content)

        self.assertEqual(json['username'], carol.username)
        self.assertEqual(json['status'], 'success')
        self.assertEqual(json['reputation'], 1001)

    def tearDown(self):
        teardownTreemapEnv()


class Logging(TestCase):
    def setUp(self):
        setupTreemapEnv()

        self.u = User.objects.get(username="jim")
        self.sign = create_signer_dict(self.u)

    def test_log_request(self):
        settings.SITE_ROOT = ''

        ret = self.client.get(
            "%s/version?rvar=4,rvar2=5" % API_PFX, **self.sign)
        self.assertEqual(ret.status_code, 200)

        logs = APILog.objects.all()

        self.assertTrue(logs is not None and len(logs) == 1)

        key = APIKey.objects.get(user=self.u)
        log = logs[0]

        self.assertEqual(log.apikey, key)
        self.assertTrue(
            log.url.endswith("%s/version?rvar=4,rvar2=5" % API_PFX))
        self.assertEqual(log.method, "GET")
        self.assertEqual(log.requestvars, "rvar=4,rvar2=5")

    def tearDown(self):
        teardownTreemapEnv()


class Version(TestCase):
    def setUp(self):
        setupTreemapEnv()

        self.u = User.objects.get(username="jim")
        self.sign = create_signer_dict(self.u)

    def test_version(self):
        settings.OTM_VERSION = "1.2.3"
        settings.API_VERSION = "2"

        ret = self.client.get("%s/version" % API_PFX, **self.sign)

        self.assertEqual(ret.status_code, 200)
        json = loads(ret.content)

        self.assertEqual(json["otm_version"], settings.OTM_VERSION)
        self.assertEqual(json["api_version"], settings.API_VERSION)

    def tearDown(self):
        teardownTreemapEnv()


class PlotListing(TestCase):
    def setUp(self):
        self.instance = setupTreemapEnv()

        self.u = User(username='user')
        self.u.save()
        self.u.roles.add(make_commander_role(self.instance))

        self.sign = create_signer_dict(self.u)
        self.client = Client()

    def tearDown(self):
        teardownTreemapEnv()

    def test_recent_edits(self):
        #TODO: Test recent edits
        return None
        user = self.u

        auth = base64.b64encode("%s:%s" % (user.username, user.username))
        withauth = dict(create_signer_dict(user).items() +
                        [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        self.client.get("%s/user/%s/edits" %
                        (API_PFX, user.pk), **withauth)

    def setup_edit_flags_test(self):
        ghost = AnonymousUser()
        self.ghost = ghost

        peon = User(username="peon")
        peon.save_with_user(self.u)

        duke = User(username="duke")
        duke.save_with_user(self.u)

        leroi = User(username="leroi")
        leroi.active = True
        leroi.save_with_user(self.u)

        p_peon_0 = mkPlot(self.instance, self.u)
        p_peon_1 = mkPlot(self.instance, self.u)
        p_duke_2 = mkPlot(self.instance, self.u)

        t_duke_0 = mkTree(self.instance, self.u, plot=p_peon_0)
        t_peon_1 = mkTree(self.instance, self.u, plot=p_peon_1)
        t_duke_2 = mkTree(self.instance, self.u, plot=p_duke_2)

        p_roi_3 = mkPlot(self.instance, self.u)
        t_roi_3 = mkTree(self.instance, self.u, plot=p_roi_3)

        self.plots = [p_peon_0, p_peon_1, p_duke_2, p_roi_3]
        self.trees = [t_duke_0, t_peon_1, t_duke_2, t_roi_3]
        self.users = [ghost, peon, duke, leroi]

    def mkd(self, e, d):
        return {"can_delete": d, "can_edit": e}

    def mkdp(self, pe, pd, te=None, td=None):
        d = {"plot": self.mkd(pe, pd)}
        if td is not None and te is not None:
            d["tree"] = self.mkd(te, td)

        return d

    def test_annon_user_cant_do_anything(self):
        self.setup_edit_flags_test()

        for p in self.plots:
            self.assertEqual(self.mkd(False, False),
                             plot_or_tree_permissions(p, self.ghost))

            self.assertEqual(self.mkdp(False, False, False, False),
                             plot_permissions(p, self.ghost))

            self.assertEqual(self.mkd(False, False),
                             plot_or_tree_permissions(p, None))

            self.assertEqual(self.mkdp(False, False, False, False),
                             plot_permissions(p, None))

        for t in self.trees:
            self.assertEqual(self.mkd(False, False),
                             plot_or_tree_permissions(t, self.ghost))

            self.assertEqual(self.mkd(False, False),
                             plot_or_tree_permissions(t, None))

    def test_a_user_with_delete_access_can_delete(self):
        self.setup_edit_flags_test()
        #TODO::: Fill out this test
        pass

    def test_noone_can_edit_readonly(self):
        self.setup_edit_flags_test()

        for p in self.plots:
            p.readonly = True
            p.save_with_user(self.u)
        for t in self.trees:
            t.readonly = True
            t.save_with_user(self.u)

        for p in self.plots:
            for u in self.users:
                self.assertEqual(self.mkd(False, False),
                                 plot_or_tree_permissions(p, u))
                self.assertEqual(self.mkdp(False, False, False, False),
                                 plot_permissions(p, u))

        for t in self.trees:
            for u in self.users:
                self.assertEqual(self.mkd(False, False),
                                 plot_or_tree_permissions(t, u))

    def test_basic_data(self):
        p = mkPlot(self.instance, self.u)
        p.width = 22
        p.length = 44
        p.geom = Point(55, 56)
        p.readonly = False
        p.save_with_user(self.u)

        info = self.client.get("%s/%s/plots" %
                               (API_PFX, self.instance.pk),
                               **self.sign)

        self.assertEqual(info.status_code, 200)

        json = loads(info.content)

        self.assertEqual(len(json), 1)
        record = json[0]

        self.assertEqual(record["id"], p.pk)
        self.assertEqual(record["plot_width"], 22)
        self.assertEqual(record["plot_length"], 44)
        self.assertEqual(record["readonly"], False)
        self.assertEqual(record["geom"]["srid"], 3857)
        self.assertEqual(record["geom"]["x"], 55)
        self.assertEqual(record["geom"]["y"], 56)
        self.assertEqual(record.get("tree"), None)

    def test_tree_data(self):
        #### TODO-- Don't leave me here
        return

        p = mkPlot(self.u)
        t = mkTree(self.u, plot=p)

        t.species = None
        t.dbh = None
        t.present = True
        t.save()

        info = self.client.get("%s/plots" % API_PFX, **self.sign)

        self.assertEqual(info.status_code, 200)

        json = loads(info.content)

        self.assertEqual(len(json), 1)
        record = json[0]

        self.assertEqual(record["tree"]["id"], t.pk)

        t.species = Species.objects.all()[0]
        t.dbh = 11.2
        t.save()

        info = self.client.get("%s/plots" % API_PFX, **self.sign)

        self.assertEqual(info.status_code, 200)

        json = loads(info.content)

        self.assertEqual(len(json), 1)
        record = json[0]

        self.assertEqual(record["tree"]["species"], t.species.pk)
        self.assertEqual(record["tree"]["dbh"], t.dbh)
        self.assertEqual(record["tree"]["id"], t.pk)

    def test_paging(self):
        ####TODO: Don't leave me here
        return
        p0 = mkPlot(self.u)
        p0.present = False
        p0.save()

        p1 = mkPlot(self.u)
        p2 = mkPlot(self.u)
        p3 = mkPlot(self.u)

        r = self.client.get("%s/plots?offset=0&size=2" % API_PFX, **self.sign)

        rids = set([p["id"] for p in loads(r.content)])
        self.assertEqual(rids, set([p1.pk, p2.pk]))

        r = self.client.get("%s/plots?offset=1&size=2" % API_PFX, **self.sign)

        rids = set([p["id"] for p in loads(r.content)])
        self.assertEqual(rids, set([p2.pk, p3.pk]))

        r = self.client.get("%s/plots?offset=2&size=2" % API_PFX, **self.sign)

        rids = set([p["id"] for p in loads(r.content)])
        self.assertEqual(rids, set([p3.pk]))

        r = self.client.get("%s/plots?offset=3&size=2" % API_PFX, **self.sign)

        rids = set([p["id"] for p in loads(r.content)])
        self.assertEqual(rids, set())

        r = self.client.get("%s/plots?offset=0&size=5" % API_PFX, **self.sign)

        rids = set([p["id"] for p in loads(r.content)])
        self.assertEqual(rids, set([p1.pk, p2.pk, p3.pk]))


class Locations(TestCase):
    def setUp(self):
        self.instance = setupTreemapEnv()

        self.user = User.objects.get(username="jim")
        self.user.roles.add(make_commander_role(self.instance))
        self.sign = create_signer_dict(self.user)

    def test_locations_plots_endpoint_with_auth(self):
        auth = base64.b64encode("%s:%s" %
                                (self.user.username, self.user.username))
        withauth = dict(create_signer_dict(self.user).items() +
                        [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        response = self.client.get(
            "%s/locations/0,0/plots" % API_PFX, **withauth)
        self.assertEqual(response.status_code, 200)

    def test_locations_plots_endpoint(self):
        response = self.client.get(
            "%s/locations/0,0/plots" % API_PFX, **self.sign)
        self.assertEqual(response.status_code, 200)

    def test_locations_plots_endpoint_max_plots_param_must_be_a_number(self):
        response = self.client.get(
            "%s/locations/0,0/plots?max_plots=foo" % API_PFX, **self.sign)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content,
                         'The max_plots parameter must be '
                         'a number between 1 and 500')

    def test_locations_plots_max_plots_param_cannot_be_greater_than_500(self):
        response = self.client.get(
            "%s/locations/0,0/plots?max_plots=501" % API_PFX, **self.sign)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content,
                         'The max_plots parameter must be '
                         'a number between 1 and 500')
        response = self.client.get("%s/locations/0,0/plots?max_plots=500" %
                                   API_PFX, **self.sign)
        self.assertEqual(response.status_code, 200)

    def test_locations_plots_endpoint_max_plots_param_cannot_be_less_than_1(
            self):
        response = self.client.get("%s/locations/0,0/plots?max_plots=0" %
                                   API_PFX, **self.sign)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content,
                         'The max_plots parameter must be a '
                         'number between 1 and 500')
        response = self.client.get("%s/locations/0,0/plots?max_plots=1" %
                                   API_PFX, **self.sign)
        self.assertEqual(response.status_code, 200)

    def test_locations_plots_endpoint_distance_param_must_be_a_number(self):
        response = self.client.get("%s/locations/0,0/plots?distance=foo" %
                                   API_PFX, **self.sign)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content,
                         'The distance parameter must be a number')

        response = self.client.get("%s/locations/0,0/plots?distance=42" %
                                   API_PFX, **self.sign)
        self.assertEqual(response.status_code, 200)

    def test_plots(self):
        plot = mkPlot(self.instance, self.user)
        plot.save_with_user(self.user)

        response = self.client.get("%s/locations/%s,%s/plots" %
                                   (API_PFX, plot.geom.x, plot.geom.y),
                                   **self.sign)

        self.assertEqual(response.status_code, 200)


class CreatePlotAndTree(TestCase):

    def setUp(self):
        self.instance = setupTreemapEnv()

        self.user = User.objects.get(username="jim")
        self.user.set_password("password")
        self.user.roles.add(make_commander_role(self.instance))
        self.user.save()

        self.sign = create_signer_dict(self.user)
        auth = base64.b64encode("jim:password")
        self.sign = dict(self.sign.items() +
                         [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        rm = ReputationMetric(instance=self.instance, model_name='Plot',
                              action=Audit.Type.Insert, direct_write_score=2,
                              approval_score=20, denial_score=5)
        rm.save()

    def test_create_plot_with_tree(self):
        data = {
            "lon": 35,
            "lat": 25,
            "geocode_address": "1234 ANY ST",
            "edit_address_street": "1234 ANY ST",
            "tree": {
                "height": 10
            }
        }

        ###TODO: Need to create reputation metrics

        plot_count = Plot.objects.count()
        reputation_count = self.user.reputation

        response = post_json("%s/%s/plots" % (API_PFX, self.instance.pk),
                             data, self.client, self.sign)

        self.assertEqual(201, response.status_code,
                         "Create failed:" + response.content)

        # Assert that a plot was added
        self.assertEqual(plot_count + 1, Plot.objects.count())
        # Assert that reputation went up
        reloaded_user_rep = User.objects.get(pk=self.user.pk).reputation
        self.assertEqual(reputation_count + 8, reloaded_user_rep)

        response_json = loads(response.content)
        self.assertTrue("id" in response_json)
        id = response_json["id"]
        plot = Plot.objects.get(pk=id)
        self.assertEqual(35.0, plot.geom.x)
        self.assertEqual(25.0, plot.geom.y)
        tree = plot.current_tree()
        self.assertIsNotNone(tree)
        self.assertEqual(10.0, tree.height)

    def test_create_plot_with_invalid_tree_returns_400(self):
        data = {
            "lon": 35,
            "lat": 25,
            "geocode_address": "1234 ANY ST",
            "edit_address_street": "1234 ANY ST",
            "tree": {
                "height": 1000000
            }
        }

        tree_count = Tree.objects.count()
        reputation_count = self.user.reputation

        response = post_json("%s/%s/plots" % (API_PFX, self.instance.pk),
                             data, self.client, self.sign)

        self.assertEqual(400,
                         response.status_code,
                         "Expected creating a million foot "
                         "tall tree to return 400:" + response.content)

        body_dict = loads(response.content)
        self.assertTrue('error' in body_dict,
                        "Expected the body JSON to contain an 'error' key")

        errors = body_dict['error']
        self.assertTrue(len(errors) == 1,
                        "Expected a single error message to be returned")

        self.assertEqual('Height is too large.', errors[0])

        # Assert that a tree was _not_ added
        self.assertEqual(tree_count, Tree.objects.count())
        # Assert that reputation was _not_ added
        self.assertEqual(reputation_count, self.user.reputation)

    def test_create_plot_with_geometry(self):
        data = {
            "geometry": {
                "x": 35,
                "y": 25,
            },
            "tree": {
                "height": 10
            }
        }

        plot_count = Plot.objects.count()
        reputation_count = self.user.reputation

        response = post_json("%s/%s/plots" % (API_PFX, self.instance.pk),
                             data, self.client, self.sign)

        self.assertEqual(201, response.status_code,
                         "Create failed:" + response.content)

        # Assert that a plot was added
        self.assertEqual(plot_count + 1, Plot.objects.count())
        # Assert that reputation was added
        reloaded_user_rep = User.objects.get(pk=self.user.pk).reputation
        self.assertEqual(reputation_count + 8, reloaded_user_rep)

        response_json = loads(response.content)
        self.assertTrue("id" in response_json)
        id = response_json["id"]
        plot = Plot.objects.get(pk=id)
        self.assertEqual(35.0, plot.geom.x)
        self.assertEqual(25.0, plot.geom.y)
        tree = plot.current_tree()
        self.assertIsNotNone(tree)
        self.assertEqual(10.0, tree.height)


class UpdatePlotAndTree(TestCase):
    def setUp(self):
        self.instance = setupTreemapEnv()

        self.user = User.objects.get(username="jim")
        self.user.set_password("password")
        self.user.roles.add(make_commander_role(self.instance))
        self.user.save()
        self.sign = create_signer_dict(self.user)
        auth = base64.b64encode("jim:password")
        self.sign = dict(self.sign.items() +
                         [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        self.public_user = User.objects.get(username="amy")
        self.public_user.set_password("password")
        self.public_user.roles = [make_apprentice_role(self.instance)]
        self.public_user.save()

        self.public_user_sign = create_signer_dict(self.public_user)
        public_user_auth = base64.b64encode("amy:password")
        self.public_user_sign = dict(
            self.public_user_sign.items() +
            [("HTTP_AUTHORIZATION", "Basic %s" % public_user_auth)])

        rm = ReputationMetric(instance=self.instance, model_name='Plot',
                              action=Audit.Type.Update, direct_write_score=2,
                              approval_score=5, denial_score=1)
        rm.save()

    def test_invalid_plot_id_returns_400_and_a_json_error(self):
        response = put_json("%s/%s/plots/0" %
                            (API_PFX, self.instance.pk),
                            {}, self.client, self.sign)

        self.assertEqual(400, response.status_code)
        response_json = loads(response.content)
        self.assertTrue("error" in response_json)
        # Received an error message as expected in response_json['error']

    def test_update_plot(self):
        test_plot = mkPlot(self.instance, self.user)
        test_plot.width = 1
        test_plot.length = 2
        test_plot.geocoded_address = 'foo'
        test_plot.save_with_user(self.user)
        self.assertEqual(50, test_plot.geom.x)
        self.assertEqual(50, test_plot.geom.y)
        self.assertEqual(1, test_plot.width)
        self.assertEqual(2, test_plot.length)

        reputation_count = self.user.reputation

        updated_values = {'geometry':
                          {'lat': 70, 'lon': 60},
                          'plot_width': 11,
                          'plot_length': 22}

        response = put_json("%s/%s/plots/%d" %
                            (API_PFX, self.instance.pk, test_plot.pk),
                            updated_values, self.client, self.sign)

        self.assertEqual(200, response.status_code)

        response_json = loads(response.content)
        self.assertEqual(70, response_json['geom']['y'])
        self.assertEqual(60, response_json['geom']['x'])
        self.assertEqual(11, response_json['plot_width'])
        self.assertEqual(22, response_json['plot_length'])

        updated_rep = User.objects.get(pk=self.user.pk).reputation
        self.assertEqual(reputation_count + 6, updated_rep)

    def test_update_plot_with_pending(self):
        test_plot = mkPlot(self.instance, self.user)
        test_plot.width = 1
        test_plot.length = 2
        test_plot.save_with_user(self.user)
        self.assertEqual(50, test_plot.geom.x)
        self.assertEqual(50, test_plot.geom.y)
        self.assertEqual(1, test_plot.width)
        self.assertEqual(2, test_plot.length)

        self.assertEqual(0, len(Audit.pending_audits()),
                         "Expected the test to start with no pending records")

        reputation_count = self.public_user.reputation

        updated_values = {'geometry':
                          {'lat': 70, 'lon': 60},
                          'plot_width': 11,
                          'plot_length': 22}

        # Send the edit request as a public user
        response = put_json("%s/%s/plots/%d" %
                            (API_PFX, self.instance.pk, test_plot.pk),
                            updated_values, self.client, self.public_user_sign)

        self.assertEqual(200, response.status_code)

        # Assert that nothing has changed.
        # Pends should have been created instead
        response_json = loads(response.content)

        self.assertEqual(50, response_json['geom']['y'])
        self.assertEqual(50, response_json['geom']['x'])
        self.assertEqual(1, response_json['plot_width'])
        self.assertEqual(2, response_json['plot_length'])

        updated_rep = User.objects.get(pk=self.public_user.pk).reputation
        self.assertEqual(reputation_count, updated_rep)

        self.assertEqual(3, len(Audit.pending_audits()),
                         "Expected 3 pends, one for each edited field")

        self.assertEqual(3, len(response_json['pending_edits'].keys()),
                         "Expected the json response to have a "
                         "pending_edits dict with 3 keys, one for each field")

    def test_invalid_field_returns_200_field_is_not_in_response(self):
        test_plot = mkPlot(self.instance, self.user)
        updated_values = {'foo': 'bar'}

        response = put_json("%s/%s/plots/%d" %
                            (API_PFX, self.instance.pk, test_plot.pk),
                            updated_values, self.client, self.sign)

        self.assertEqual(200, response.status_code)
        response_json = loads(response.content)
        self.assertFalse("error" in response_json.keys(),
                         "Did not expect an error")

        self.assertFalse("foo" in response_json.keys(),
                         "Did not expect foo to be added to the plot")

    def test_update_creates_tree(self):
        test_plot = mkPlot(self.instance, self.user)
        test_plot_id = test_plot.id
        self.assertIsNone(test_plot.current_tree())
        updated_values = {'tree': {'diameter': 1.2}}

        response = put_json("%s/%s/plots/%d" %
                            (API_PFX, self.instance.pk, test_plot.pk),
                            updated_values, self.client, self.sign)

        self.assertEqual(200, response.status_code)
        tree = Plot.objects.get(pk=test_plot_id).current_tree()
        self.assertIsNotNone(tree)
        self.assertEqual(1.2, tree.diameter)

    # TODO: Waiting for issue to be fixed
    # https://github.com/azavea/OTM2/issues/82
    # def test_update_creates_tree_with_pending(self):
    #     test_plot = mkPlot(self.instance, self.user)
    #     test_plot_id = test_plot.id

    #     self.assertIsNone(test_plot.current_tree())
    #     self.assertEqual(0, len(Audit.pending_audits()),
    #                   "Expected the test to start with no pending records")

    #     updated_values = {'tree': {'diameter': 1.2}}

    #     response = put_json("%s/%s/plots/%d" %
    #                      (API_PFX, self.instance.pk, test_plot.pk),
    #                      updated_values, self.client, self.public_user_sign)

    #     self.assertEqual(200, response.status_code)
    #     self.assertEqual(0, len(Pending.objects.all()),
    #                      "Expected a new tree to be created, "
    #                      "rather than creating pends")

    #     tree = Plot.objects.get(pk=test_plot_id).current_tree()
    #     self.assertIsNotNone(tree)
    #     self.assertEqual(1.2, tree.dbh)

    def test_update_tree(self):
        test_plot = mkPlot(self.instance, self.user)
        test_tree = mkTree(self.instance, self.user, plot=test_plot)
        test_tree_id = test_tree.id
        test_tree.diameter = 2.3
        test_tree.save_with_user(self.user)

        updated_values = {'tree': {'diameter': 3.9}}
        response = put_json("%s/%s/plots/%d" %
                            (API_PFX, self.instance.pk, test_plot.id),
                            updated_values, self.client, self.sign)

        self.assertEqual(200, response.status_code)

        tree = Tree.objects.get(pk=test_tree_id)
        self.assertIsNotNone(tree)
        self.assertEqual(3.9, tree.diameter)

    def test_update_tree_with_pending(self):
        test_plot = mkPlot(self.instance, self.user)
        test_tree = mkTree(self.instance, self.user, plot=test_plot)
        test_tree_id = test_tree.pk
        test_tree.diameter = 2.3
        test_tree.save_with_user(self.user)

        self.assertEqual(0, len(Audit.pending_audits()),
                         "Expected the test to start with no pending records")

        updated_values = {'tree': {'diameter': 3.9}}

        response = put_json("%s/%s/plots/%d" %
                            (API_PFX, self.instance.pk, test_plot.pk),
                            updated_values, self.client, self.public_user_sign)

        self.assertEqual(200, response.status_code)
        tree = Tree.objects.get(pk=test_tree_id)

        self.assertIsNotNone(tree)
        self.assertEqual(2.3, tree.diameter,
                         "A pend should have been created instead"
                         " of editing the tree value.")
        self.assertEqual(1, len(Audit.pending_audits()),
                         "Expected 1 pend record for the edited field.")

        response_json = loads(response.content)
        self.assertEqual(1, len(response_json['pending_edits'].keys()),
                         "Expected the json response to have a"
                         " pending_edits dict with 1 keys")

    def test_update_tree_species(self):
        test_plot = mkPlot(self.instance, self.user)
        test_tree = mkTree(self.instance, self.user, plot=test_plot)
        test_tree_id = test_tree.id

        first_species = Species.objects.all()[0]
        updated_values = {'tree': {'species': first_species.id}}

        response = put_json("%s/%s/plots/%d" %
                            (API_PFX, self.instance.pk, test_plot.pk),
                            updated_values, self.client, self.sign)

        self.assertEqual(200, response.status_code)
        tree = Tree.objects.get(pk=test_tree_id)
        self.assertIsNotNone(tree)
        self.assertEqual(first_species, tree.species)

    def test_update_tree_returns_400_on_invalid_species_id(self):
        test_plot = mkPlot(self.instance, self.user)
        mkTree(self.instance, self.user, plot=test_plot)

        invalid_species_id = -1
        self.assertRaises(Exception,
                          Species.objects.get, pk=invalid_species_id)

        updated_values = {'tree': {'species': invalid_species_id}}

        response = put_json("%s/%s/plots/%d" %
                            (API_PFX, self.instance.pk, test_plot.pk),
                            updated_values, self.client, self.sign)

        self.assertEqual(400, response.status_code)
        response_json = loads(response.content)
        self.assertTrue("error" in response_json.keys(),
                        "Expected an 'error' key in the JSON response")

    def test_approve_pending_edit_returns_404_for_invalid_pend_id(self):
        invalid_pend_id = -1
        self.assertRaises(Exception, Audit.objects.get, pk=invalid_pend_id)

        response = post_json("%s/%s/pending-edits/%d/approve/" %
                             (API_PFX, self.instance.pk, invalid_pend_id),
                             None, self.client, self.sign)

        self.assertEqual(404, response.status_code,
                         "Expected approving and invalid "
                         "pend id to return 404")

    def test_reject_pending_edit_returns_404_for_invalid_pend_id(self):
        invalid_pend_id = -1
        self.assertRaises(Exception, Audit.objects.get, pk=invalid_pend_id)

        response = post_json("%s/%s/pending-edits/%d/reject/" %
                             (API_PFX, self.instance.pk, invalid_pend_id),
                             None, self.client, self.sign)

        self.assertEqual(404, response.status_code,
                         "Expected approving and invalid pend "
                         " id to return 404")

    def test_approve_pending_edit(self):
        self.assert_pending_edit_operation(Audit.Type.PendingApprove)

    def test_reject_pending_edit(self):
        self.assert_pending_edit_operation(Audit.Type.PendingReject)

    def assert_pending_edit_operation(self, action,
                                      original_dbh=2.3, edited_dbh=3.9):
        test_plot = mkPlot(self.instance, self.user)
        test_tree = mkTree(self.instance, self.user, plot=test_plot)
        test_tree_id = test_tree.id
        test_tree.diameter = original_dbh
        test_tree.save_with_user(self.user)

        self.assertEqual(0, len(Audit.pending_audits()),
                         "Expected the test to start with no pending records")

        updated_values = {'tree': {'diameter': edited_dbh}}
        response = put_json("%s/%s/plots/%d" %
                            (API_PFX, self.instance.pk, test_plot.id),
                            updated_values, self.client,
                            self.public_user_sign)

        self.assertEqual(200, response.status_code)

        tree = Tree.objects.get(pk=test_tree_id)

        self.assertIsNotNone(tree)
        self.assertEqual(original_dbh, tree.diameter,
                         "A pend should have been created instead"
                         " of editing the tree value.")

        self.assertEqual(1, len(Audit.pending_audits()),
                         "Expected 1 pend record for the edited field.")

        pending_edit = Audit.pending_audits()[0]
        self.assertEqual(None, pending_edit.ref_id,
                         "Expected that the audit has not been applied")

        if action == Audit.Type.PendingApprove:
            action_str = 'approve'
        else:
            action_str = 'reject'

        response = post_json("%s/%s/pending-edits/%d/%s/" %
                             (API_PFX, self.instance.pk,
                              pending_edit.id, action_str),
                             None, self.client, self.sign)

        self.assertEqual(200, response.status_code)

        pending_edit = Audit.objects.get(pk=pending_edit.id)
        self.assertIsNotNone(pending_edit.ref_id,
                             "Expected the audit to be marked as processed")

        pending_edit_marked = pending_edit.ref_id
        self.assertEqual(pending_edit_marked.action,
                         action,
                         "Expected the type of the audit to be '%s'" %
                         action)

        test_tree = Tree.objects.get(pk=test_tree_id)

        if action == Audit.Type.PendingApprove:
            self.assertEqual(edited_dbh, test_tree.diameter,
                             "Expected dbh to have been updated on the Tree")
        elif action == Audit.Type.PendingReject:
            self.assertEqual(original_dbh, test_tree.diameter,
                             "Expected dbh to NOT have been "
                             "updated on the Tree")

        response_json = loads(response.content)
        self.assertTrue('tree' in response_json)
        self.assertTrue('dbh' in response_json['tree'])

        if action == Audit.Type.PendingApprove:
            self.assertEqual(edited_dbh,
                             response_json['tree']['dbh'],
                             "Expected dbh to have been updated"
                             " in the JSON response")
        elif action == Audit.Type.PendingReject:
            self.assertEqual(original_dbh,
                             response_json['tree']['dbh'],
                             "Expected dbh to NOT have been "
                             "updated in the JSON response")

    def test_approve_plot_pending_with_mutiple_pending_edits(self):
        test_plot = mkPlot(self.instance, self.user)
        test_plot.width = 100
        test_plot.length = 50
        test_plot.save_with_user(self.user)
        test_tree = mkTree(self.instance, self.user, plot=test_plot)
        test_tree.diameter = 2.3
        test_tree.save_with_user(self.user)

        updated_values = {
            "plot_width": 125,
            "plot_length": 25,
            "tree": {
                "dbh": 3.9
            }
        }

        response = put_json("%s/%s/plots/%d" %
                            (API_PFX, self.instance.pk, test_plot.id),
                            updated_values, self.client, self.public_user_sign)
        self.assertEqual(response.status_code, 200,
                         "Non 200 response when updating plot")

        updated_values = {
            "plot_width": 175,
        }

        response = put_json("%s/%s/plots/%d" %
                            (API_PFX, self.instance.pk, test_plot.id),
                            updated_values,
                            self.client, self.public_user_sign)

        self.assertEqual(response.status_code, 200,
                         "Non 200 response when updating plot")

        test_plot = Plot.objects.get(pk=test_plot.pk)
        pending_edit_count = len(test_plot.get_active_pending_audits())
        self.assertEqual(3, pending_edit_count,
                         "Expected three pending edits but got %d" %
                         pending_edit_count)

        pend = test_plot.get_active_pending_audits()[0]
        approved_pend_id = pend.id

        response = post_json("%s/%s/pending-edits/%d/approve/" %
                             (API_PFX, self.instance.pk, approved_pend_id),
                             None, self.client, self.sign)

        self.assertEqual(response.status_code, 200,
                         "Non 200 response when approving the pend")

        self.assertEqual(1, len(test_plot.get_active_pending_audits()),
                         "Expected there to be 1 pending edits after approval")

    def test_remove_plot(self):
        plot = mkPlot(self.instance, self.user)
        plot_id = plot.pk

        tree = mkTree(self.instance, self.user, plot=plot)
        tree_id = tree.pk

        response = self.client.delete("%s/%s/plots/%d" %
                                      (API_PFX, self.instance.pk, plot_id),
                                      **self.sign)

        self.assertEqual(200, response.status_code,
                         "Expected 200 status code after delete")

        response_dict = loads(response.content)
        self.assertTrue('ok' in response_dict,
                        'Expected a json object response with a "ok" key')

        self.assertTrue(response_dict['ok'],
                        'Expected a json object response with a "ok" key'
                        'set to True')

        plot = Plot.objects.filter(pk=plot_id)
        tree = Tree.objects.filter(pk=tree_id)

        self.assertTrue(len(plot) == 0, 'Expected plot to be gone')
        self.assertTrue(len(tree) == 0, 'Expected tree to be gone')

    def test_remove_tree(self):
        plot = mkPlot(self.instance, self.user)
        plot_id = plot.pk

        tree = mkTree(self.instance, self.user, plot=plot)
        tree_id = tree.pk

        response = self.client.delete("%s/%s/plots/%d/tree" %
                                      (API_PFX, self.instance.pk, plot_id),
                                      **self.sign)

        self.assertEqual(200, response.status_code,
                         "Expected 200 status code after delete")
        response_dict = loads(response.content)
        self.assertIsNone(response_dict['tree'],
                          'Expected a json object response to a None'
                          'value for "tree" key after the tree is deleted')

        plot = Plot.objects.filter(pk=plot_id)
        tree = Tree.objects.filter(pk=tree_id)

        self.assertTrue(len(plot) == 1, 'Expected plot to be here')
        self.assertTrue(len(tree) == 0, 'Expected tree to be gone')

    def test_get_current_tree(self):
        plot = mkPlot(self.instance, self.user)
        plot_id = plot.pk

        tree = mkTree(self.instance, self.user, plot=plot)
        tree.species = Species.objects.all()[0]
        tree.save_with_user(self.user)

        response = self.client.get("%s/%s/plots/%d/tree" %
                                   (API_PFX, self.instance.pk, plot_id),
                                   **self.sign)

        self.assertEqual(200, response.status_code,
                         "Expected 200 status code")
        response_dict = loads(response.content)
        self.assertTrue('species' in response_dict,
                        'Expected "species" to be a top level '
                        'key in the response object')
        self.assertEqual(tree.species.pk, response_dict['species'])

    def test_registration(self):
        self.assertTrue(
            User.objects.filter(username='foobar').count() == 0,
            "The test expects the foobar user to not exists.")
        data = {
            'username': 'foobar',
            'firstname': 'foo',
            'lastname': 'bar',
            'email': 'foo@bar.com',
            'password': 'drowssap',
            'zipcode': 19107
        }
        response = post_json("%s/user/" % API_PFX,
                             data, self.client, self.sign)
        self.assertEqual(200, response.status_code,
                         "Expected 200 status code after creating user")
        response_dict = loads(response.content)
        self.assertTrue('status' in response_dict,
                        'Expected "status" to be a top level '
                        'key in the response object')
        self.assertEqual('success', response_dict['status'],
                         'Expected "status" to be "success"')
        self.assertTrue(User.objects.filter(username='foobar').count() == 1,
                        'Expected the "foobar" user to be created.')

    def test_duplicate_registration(self):
        self.assertTrue(User.objects.filter(username='jim').count() == 1,
                        "The test expects the jim user to exist.")
        data = {
            'username': 'jim',
            'firstname': 'Jim',
            'lastname': 'User',
            'email': 'jim@user.com',
            'password': 'drowssap',
            'zipcode': 19107
        }
        response = post_json("%s/user/" % API_PFX,
                             data, self.client, self.sign)
        self.assertEqual(409, response.status_code,
                         "Expected 409 status code after attempting"
                         " to create duplicate username")
        response_dict = loads(response.content)
        self.assertTrue('status' in response_dict,
                        'Expected "status" to be a top level key'
                        'in the response object')
        self.assertEqual('failure', response_dict['status'],
                         'Expected "status" to be "failure"')
        self.assertTrue('detail' in response_dict,
                        'Expected "detail" to be a top level key'
                        'in the response object')
        self.assertEqual('Username jim exists', response_dict['detail'])


def _create_mock_request_without_version():
    return _create_mock_request_with_version_string(None)


def _create_mock_request_with_version_string(version_string):
    class MockRequest(object):
        def __init__(self):
            self.META = {}
            if version_string:
                self.META['HTTP_APPLICATIONVERSION'] = version_string
    return MockRequest()


class VersionHeaderParsing(TestCase):
    def test_missing_version_header(self):
        request = _create_mock_request_without_version()
        version_dict = _parse_application_version_header_as_dict(request)
        self.assertEqual({
            'platform': 'UNKNOWN',
            'version': 'UNKNOWN',
            'build': 'UNKNOWN'
        }, version_dict)

    def test_platform_only(self):
        request = _create_mock_request_with_version_string('ios')
        version_dict = _parse_application_version_header_as_dict(request)
        self.assertEqual({
            'platform': 'ios',
            'version': 'UNKNOWN',
            'build': 'UNKNOWN'
        }, version_dict)

    def test_platform_and_version_missing_build(self):
        request = _create_mock_request_with_version_string('ios-1.2')
        version_dict = _parse_application_version_header_as_dict(request)
        self.assertEqual({
            'platform': 'ios',
            'version': '1.2',
            'build': 'UNKNOWN'
        }, version_dict)

    def test_all(self):
        request = _create_mock_request_with_version_string('ios-1.2-b32')
        version_dict = _parse_application_version_header_as_dict(request)
        self.assertEqual({
            'platform': 'ios',
            'version': '1.2',
            'build': 'b32'
        }, version_dict)

    def test_extra_segments_dropped(self):
        request = _create_mock_request_with_version_string(
            'ios-1.2-b32-some-other junk')
        version_dict = _parse_application_version_header_as_dict(request)
        self.assertEqual({
            'platform': 'ios',
            'version': '1.2',
            'build': 'b32'
        }, version_dict)

    def test_non_numeric_version(self):
        request = _create_mock_request_with_version_string('ios-null-bnull')
        version_dict = _parse_application_version_header_as_dict(request)
        self.assertEqual({
            'platform': 'ios',
            'version': 'null',
            'build': 'bnull'
        }, version_dict)




# TODO: Add this back in when we really support
#       tree photos
# class TreePhoto(TestCase):

#     def setUp(self):
#         setupTreemapEnv()
#         self.user = User.objects.get(username="jim")
#         self.user.set_password("password")
#         self.user.save()
#         self.sign = create_signer_dict(self.user)
#         auth = base64.b64encode("jim:password")
#         self.sign = dict(self.sign.items() + [("HTTP_AUTHORIZATION",
#         "Basic %s" % auth)])

#         self.test_jpeg_path = os.path.join(os.path.dirname(__file__),
#          'test_resources', '2by2.jpeg')
#         self.test_png_path = os.path.join(os.path.dirname(__file__),
#       'test_resources', '2by2.png')

#         def assertSuccessfulResponse(response):
#             self.assertIsNotNone(response)
#             self.assertIsNotNone(response.content)
#             response_dict = loads(response.content)
#             self.assertTrue('status' in response_dict)
#             self.assertEqual('success', response_dict['status'])
#         self.assertSuccessfulResponse = assertSuccessfulResponse

#     def tearDown(self):
#         teardownTreemapEnv()

#     def test_jpeg_tree_photo_file_name(self):
#         plot = mkPlot(self.instance, self.user)
#         plot_id = plot.pk
#         response = post_jpeg_file("%s/plots/%d/tree/photo" %
#         (API_PFX, plot_id), self.test_jpeg_path,
#             self.client, self.sign)

#         self.assertSuccessfulResponse(response)

#         plot = Plot.objects.get(pk=plot_id)
#         tree = plot.current_tree()
#         self.assertIsNotNone(tree)
#         photo = tree.treephoto_set.all()[0]
#         self.assertEqual('plot_%d.jpeg' % plot_id, photo.title)

#     def test_png_tree_photo_file_name(self):
#         plot = mkPlot(self.instance, self.user)
#         plot_id = plot.pk
#         response = post_png_file("%s/plots/%d/tree/photo" %
#         (API_PFX, plot_id), self.test_png_path,
#             self.client, self.sign)

#         self.assertSuccessfulResponse(response)

#         plot = Plot.objects.get(pk=plot_id)
#         tree = plot.current_tree()
#         self.assertIsNotNone(tree)
#         photo = tree.treephoto_set.all()[0]
#         self.assertEqual('plot_%d.png' % plot_id, photo.title)
