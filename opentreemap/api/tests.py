# -*- coding: utf-8 -*-


from io import BytesIO
from json import loads, dumps
from urllib.parse import urlparse

import urllib.request
import urllib.parse
import urllib.error
import os
import json
import base64
import datetime
import psycopg2
from unittest.case import skip
from django_tinsel.exceptions import HttpBadRequestException

from django.db import connection
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import Point
from django.test.utils import override_settings
from django.test.client import Client, RequestFactory, ClientHandler
from django.http import HttpRequest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.core.files import File

from treemap.lib.udf import udf_create
from treemap.models import Species, Plot, Tree, User, FieldPermission
from treemap.instance import create_stewardship_udfs
from treemap.audit import ReputationMetric, Audit
from treemap.udf import UserDefinedFieldDefinition
from treemap.tests import (make_user, make_request, set_invisible_permissions,
                           make_instance, LocalMediaTestCase, media_dir,
                           make_commander_user, set_write_permissions)
from treemap.tests.base import OTMTestCase

from exporter.tests import UserExportsTestCase

from api.test_utils import setupTreemapEnv, mkPlot, mkTree
from api.models import APIAccessCredential
from api.views import (add_photo_endpoint, update_profile_photo_endpoint,
                       instance_info_endpoint)
from api.instance import (instances_closest_to_point, instance_info,
                          public_instances)
from api.user import create_user
from api.auth import get_signature_for_request
from api.decorators import (check_signature, SIG_TIMESTAMP_FORMAT,
                            API_VERSIONS)

LATEST_API = str(max(API_VERSIONS))
API_PFX = "/api/v%s" % LATEST_API


def sign_request_as_user(request, user):
    try:
        cred = APIAccessCredential.objects.get(user=user)
    except APIAccessCredential.DoesNotExist:
        cred = APIAccessCredential.create(user=user)

    return sign_request(request, cred)


def sign_request(request, cred=None):
    if cred is None:
        cred = APIAccessCredential.create()

    nowstr = datetime.datetime.now().strftime(SIG_TIMESTAMP_FORMAT)

    request.GET = request.GET.copy()
    request.GET['timestamp'] = nowstr
    request.GET['access_key'] = cred.access_key

    sig = get_signature_for_request(request, cred.secret_key)
    request.GET['signature'] = sig

    return request


def _get_path(parsed_url):
    """
    Taken from a class method in the Django test client
    """
    # If there are parameters, add them
    if parsed_url[3]:
        return urllib.parse.unquote(parsed_url[2] + ";" + parsed_url[3])
    else:
        return urllib.parse.unquote(parsed_url[2])


def send_json_body(url, body_object, client, method, user=None):
    """
    Serialize a list or dictionary to JSON then send it to an endpoint.
    The "post" method exposed by the Django test client assumes that you
    are posting form data, so you need to manually setup the parameters
    to override that default functionality.
    """
    body_binary_string = dumps(body_object).encode()
    body_stream = BytesIO(body_binary_string)
    parsed_url = urlparse(url)
    client_params = {
        'CONTENT_LENGTH': len(body_binary_string),
        'CONTENT_TYPE': 'application/json',
        'PATH_INFO': _get_path(parsed_url),
        'QUERY_STRING': parsed_url[4],
        'REQUEST_METHOD': method,
        'wsgi.input': body_stream,
    }
    return _send_with_client_params(url, client, client_params, user)


class SignedClientHandler(ClientHandler):
    def __init__(self, sign, sign_as, *args, **kwargs):
        self.sign = sign
        self.sign_as = sign_as

        super(SignedClientHandler, self).__init__(*args, **kwargs)

    def get_response(self, req):
        if self.sign:
            req = sign_request_as_user(req, self.sign_as)

        return super(SignedClientHandler, self).get_response(req)


def get_signed(client, *args, **kwargs):
    handler = client.handler
    client.handler = SignedClientHandler(True, kwargs.get('user', None))

    resp = client.get(*args, **kwargs)

    client.handler = handler

    return resp


def _send_with_client_params(url, client, client_params, user=None):
    handler = client.handler
    client.handler = SignedClientHandler(True, user)

    resp = client.post(url, **client_params)

    client.handler = handler

    return resp


def post_json(url, body_object, client, user=None):
    """
    Serialize a list or dictionary to JSON then POST it to an endpoint.
    The "post" method exposed by the Django test client assumes that you
    are posting form data, so you need to manually setup the parameters
    to override that default functionality.
    """
    return send_json_body(url, body_object, client, 'POST', user)


def put_json(url, body_object, client, user=None):
    return send_json_body(url, body_object, client, 'PUT', user)


def assert_reputation(test_case, expected_reputation):
    """
    'test_case' object should have attributes 'user' and 'instance'
    Tests whether user's reputation is as expected.
    Reloads user object from database since reputation may have changed.
    """
    user = User.objects.get(pk=test_case.user.id)
    reputation = user.get_reputation(test_case.instance)
    test_case.assertEqual(expected_reputation, reputation,
                          'Reputation is %s but %s was expected'
                          % (reputation, expected_reputation))


class Version(OTMTestCase):
    def setUp(self):
        setupTreemapEnv()

        self.u = User.objects.get(username="jim")

    def test_version(self):
        settings.OTM_VERSION = "1.2.3"
        settings.API_VERSION = "2"

        ret = get_signed(self.client, "%s/version" % API_PFX)

        self.assertEqual(ret.status_code, 200)
        content = loads(ret.content)

        self.assertEqual(content["otm_version"], settings.OTM_VERSION)
        self.assertEqual(content["api_version"], settings.API_VERSION)


class PlotListing(OTMTestCase):
    def setUp(self):
        self.instance = setupTreemapEnv()
        self.u = User.objects.get(username="commander")
        self.client = Client()

    def test_edits(self):
        # TODO: Test recent edits
        return None
        user = self.u

        get_signed(self.cliend, "%s/user/%s/edits" %
                   (API_PFX, user.pk))

    def setup_edit_flags_test(self):
        ghost = AnonymousUser()
        self.ghost = ghost

        peon = make_user(username="peon", password='pw')
        peon.save_with_user(self.u)

        duke = make_user(username="duke", password='pw')
        duke.save_with_user(self.u)

        leroi = make_user(username="leroi", password='pw')
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

    @skip("wait until this api is real")
    def test_basic_data(self):
        p = mkPlot(self.instance, self.u)
        p.width = 22
        p.length = 44
        p.geom = Point(55, 56)
        p.readonly = False
        p.save_with_user(self.u)

        info = self.client.get("%s/instance/%s/plots" %
                               (API_PFX, self.instance.url_name))

        self.assertEqual(info.status_code, 200)

        content = loads(info.content)

        self.assertEqual(len(content), 1)
        record = content[0]

        self.assertEqual(record["id"], p.pk)
        self.assertEqual(record["plot_width"], 22)
        self.assertEqual(record["plot_length"], 44)
        self.assertEqual(record["readonly"], False)
        self.assertEqual(record["geom"]["srid"], 3857)
        self.assertEqual(record["geom"]["x"], 55)
        self.assertEqual(record["geom"]["y"], 56)
        self.assertEqual(record.get("tree"), None)

    @skip("wait for endpoint to be done")
    def test_tree_data(self):

        p = mkPlot(self.u)
        t = mkTree(self.u, plot=p)

        t.species = None
        t.dbh = None
        t.present = True
        t.save()

        info = self.client.get("%s/plots" % API_PFX)

        self.assertEqual(info.status_code, 200)

        content = loads(info.content)

        self.assertEqual(content(json), 1)
        record = content[0]

        self.assertEqual(record["tree"]["id"], t.pk)

        t.species = Species.objects.all()[0]
        t.dbh = 11.2
        t.save()

        info = self.client.get("%s/plots" % API_PFX)

        self.assertEqual(info.status_code, 200)

        content = loads(info.content)

        self.assertEqual(len(content), 1)
        record = content[0]

        self.assertEqual(record["tree"]["species"], t.species.pk)
        self.assertEqual(record["tree"]["dbh"], t.dbh)
        self.assertEqual(record["tree"]["id"], t.pk)

    @skip("wait for endpoint to be done")
    def test_paging(self):
        p0 = mkPlot(self.u)
        p0.present = False
        p0.save()

        p1 = mkPlot(self.u)
        p2 = mkPlot(self.u)
        p3 = mkPlot(self.u)

        r = self.client.get("%s/plots?offset=0&size=2" % API_PFX)

        rids = set([p["id"] for p in loads(r.content)])
        self.assertEqual(rids, set([p1.pk, p2.pk]))

        r = self.client.get("%s/plots?offset=1&size=2" % API_PFX)

        rids = set([p["id"] for p in loads(r.content)])
        self.assertEqual(rids, set([p2.pk, p3.pk]))

        r = self.client.get("%s/plots?offset=2&size=2" % API_PFX)

        rids = set([p["id"] for p in loads(r.content)])
        self.assertEqual(rids, set([p3.pk]))

        r = self.client.get("%s/plots?offset=3&size=2" % API_PFX)

        rids = set([p["id"] for p in loads(r.content)])
        self.assertEqual(rids, set())

        r = self.client.get("%s/plots?offset=0&size=5" % API_PFX)

        rids = set([p["id"] for p in loads(r.content)])
        self.assertEqual(rids, set([p1.pk, p2.pk, p3.pk]))


class Locations(OTMTestCase):
    def setUp(self):
        self.instance = setupTreemapEnv()
        self.user = User.objects.get(username="commander")

    def test_locations_plots_endpoint_with_auth(self):
        response = get_signed(
            self.client,
            "%s/instance/%s/locations/0,0/plots" % (API_PFX,
                                                    self.instance.url_name),
            user=self.user)
        self.assertEqual(response.status_code, 200)

    def test_locations_plots_endpoint(self):
        response = get_signed(
            self.client,
            "%s/instance/%s/locations/0,0/plots" % (API_PFX,
                                                    self.instance.url_name))
        self.assertEqual(response.status_code, 200)

    def test_locations_plots_endpoint_max_plots_param_must_be_a_number(self):
        response = get_signed(
            self.client,
            "%s/instance/%s/locations/0,0/plots?max_plots=foo" % (
                API_PFX, self.instance.url_name))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content,
                         b'The max_plots parameter must be '
                         b'a number between 1 and 500')

    def test_locations_plots_max_plots_param_cannot_be_greater_than_500(self):
        response = get_signed(
            self.client,
            "%s/instance/%s/locations/0,0/plots?max_plots=501" % (
                API_PFX, self.instance.url_name))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content,
                         b'The max_plots parameter must be '
                         b'a number between 1 and 500')
        response = get_signed(
            self.client,
            "%s/instance/%s/locations/0,0/plots?max_plots=500" %
            (API_PFX, self.instance.url_name))
        self.assertEqual(response.status_code, 200)

    def test_locations_plots_endpoint_max_plots_param_cannot_be_less_than_1(
            self):
        response = get_signed(
            self.client,
            "%s/instance/%s/locations/0,0/plots?max_plots=0" %
            (API_PFX, self.instance.url_name))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content,
                         b'The max_plots parameter must be a '
                         b'number between 1 and 500')
        response = get_signed(
            self.client,
            "%s/instance/%s/locations/0,0/plots?max_plots=1" %
            (API_PFX, self.instance.url_name))

        self.assertEqual(response.status_code, 200)

    def test_locations_plots_endpoint_distance_param_must_be_a_number(self):
        response = get_signed(
            self.client,
            "%s/instance/%s/locations/0,0/plots?distance=foo" %
            (API_PFX, self.instance.url_name))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content,
                         b'The distance parameter must be a number')

        response = get_signed(
            self.client,
            "%s/instance/%s/locations/0,0/plots?distance=42" %
            (API_PFX, self.instance.url_name))

        self.assertEqual(response.status_code, 200)

    def test_plots(self):
        plot = mkPlot(self.instance, self.user)
        plot.save_with_user(self.user)

        response = get_signed(
            self.client,
            "%s/instance/%s/locations/%s,%s/plots" %
            (API_PFX, self.instance.url_name,
             plot.geom.x, plot.geom.y))

        self.assertEqual(response.status_code, 200)


class CreatePlotAndTree(OTMTestCase):
    def setUp(self):
        self.instance = setupTreemapEnv()

        self.user = User.objects.get(username="commander")

        rm = ReputationMetric(instance=self.instance, model_name='Plot',
                              action=Audit.Type.Insert, direct_write_score=2,
                              approval_score=20, denial_score=5)
        rm.save()

    def test_create_plot_with_tree(self):
        data = {
            "plot":
            {'geom': {"y": 25,
                      "x": 35,
                      "srid": 3857}},
            "tree": {
                "height": 10.0
            }}

        # TODO: Need to create reputation metrics

        plot_count = Plot.objects.count()
        reputation_count = self.user.get_reputation(self.instance)

        response = post_json("%s/instance/%s/plots" % (API_PFX,
                                                       self.instance.url_name),
                             data, self.client, self.user)

        self.assertEqual(200, response.status_code,
                         "Create failed:" + response.content.decode())

        # Assert that a plot was added
        self.assertEqual(plot_count + 1, Plot.objects.count())
        # Assert that reputation went up
        assert_reputation(self, reputation_count + 6)

        response_json = loads(response.content)
        self.assertTrue("id" in response_json['plot'])
        id = response_json['plot']["id"]
        plot = Plot.objects.get(pk=id)
        self.assertEqual(35.0, plot.geom.x)
        self.assertEqual(25.0, plot.geom.y)
        tree = plot.current_tree()
        self.assertIsNotNone(tree)
        self.assertEqual(10.0, tree.height)

    def test_create_plot_with_invalid_tree_returns_400(self):
        data = {
            "plot":
            {'geom': {"y": 25,
                      "x": 35,
                      "srid": 3857}},
            "tree": {
                "height": 1000000
            }}

        tree_count = Tree.objects.count()
        reputation_count = self.user.get_reputation(self.instance)

        response = post_json("%s/instance/%s/plots" % (API_PFX,
                                                       self.instance.url_name),
                             data, self.client, self.user)

        self.assertEqual(400,
                         response.status_code,
                         "Expected creating a million foot "
                         "tall tree to return 400:" + response.content.decode())

        body_dict = loads(response.content)
        self.assertTrue('fieldErrors' in body_dict,
                        "Expected the body JSON to have a 'fieldErrors' key")

        fieldErrors = body_dict['fieldErrors']
        self.assertTrue('tree.height' in fieldErrors,
                        'Expected "treeHeight" to be in "fieldErrors"')

        self.assertEqual('The height is too large',
                         fieldErrors['tree.height'][0])

        # Assert that a tree was _not_ added
        self.assertEqual(tree_count, Tree.objects.count())
        # Assert that reputation was _not_ added
        assert_reputation(self, reputation_count)

    def test_create_plot_with_geometry(self):
        data = {
            "plot": {
                "geom": {
                    "x": 35,
                    "y": 25,
                    "srid": 3857
                },
            },
            "tree": {
                "height": 10
            }}

        plot_count = Plot.objects.count()
        reputation_count = self.user.get_reputation(self.instance)

        response = post_json("%s/instance/%s/plots" % (API_PFX,
                                                       self.instance.url_name),
                             data, self.client, self.user)

        self.assertEqual(200, response.status_code,
                         "Create failed:" + response.content.decode())

        # Assert that a plot was added
        self.assertEqual(plot_count + 1, Plot.objects.count())
        # Assert that reputation was added
        assert_reputation(self, reputation_count + 6)

        response_json = loads(response.content)
        self.assertTrue("id" in response_json['plot'])
        id = response_json['plot']["id"]
        plot = Plot.objects.get(pk=id)
        self.assertEqual(35.0, plot.geom.x)
        self.assertEqual(25.0, plot.geom.y)
        tree = plot.current_tree()
        self.assertIsNotNone(tree)
        self.assertEqual(10.0, tree.height)


class UpdatePlotAndTree(OTMTestCase):
    def setUp(self):
        psycopg2.extras.register_hstore(connection.cursor(), globally=True)

        self.instance = setupTreemapEnv()

        self.user = User.objects.get(username="commander")
        self.public_user = User.objects.get(username="apprentice")

        rm = ReputationMetric(instance=self.instance, model_name='Plot',
                              action=Audit.Type.Update, direct_write_score=2,
                              approval_score=5, denial_score=1)
        rm.save()

    def _makeUdfd(self, name, data_type, model_type='Plot', choices=None):
        set_write_permissions(self.instance, self.user, model_type,
                              ['udf:' + name])
        datatype_dict = {'type': data_type}
        if choices:
            datatype_dict['choices'] = choices
        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type=model_type,
            datatype=json.dumps(datatype_dict),
            iscollection=False,
            name=name)

    def test_invalid_plot_id_returns_404_and_a_json_error(self):
        response = put_json("%s/instance/%s/plots/0" %
                            (API_PFX, self.instance.url_name),
                            {}, self.client, self.user)

        self.assertEqual(404, response.status_code)

    def test_update_plot(self):
        test_plot = mkPlot(self.instance, self.user)
        test_plot.width = 1
        test_plot.length = 2
        test_plot.geocoded_address = 'foo'
        test_plot.save_with_user(self.user)
        self.assertEqual(0, test_plot.geom.x)
        self.assertEqual(0, test_plot.geom.y)
        self.assertEqual(1, test_plot.width)
        self.assertEqual(2, test_plot.length)

        reputation_count = self.user.get_reputation(self.instance)

        # Include `updated_by` because the app does send it,
        # and the endpoint must ignore it.
        updated_values = {'plot':
                          {'geom': {'y': 0.001, 'x': 0.001, 'srid': 4326},
                           'width': 11,
                           'length': 22,
                           'updated_by': self.user.pk}}

        response = put_json("%s/instance/%s/plots/%d" %
                            (API_PFX, self.instance.url_name, test_plot.pk),
                            updated_values, self.client, self.user)

        self.assertEqual(200, response.status_code)

        response_json = loads(response.content)
        self.assertAlmostEqual(0.001, response_json['plot']['geom']['y'])
        self.assertAlmostEqual(0.001, response_json['plot']['geom']['x'])
        self.assertEqual(11, response_json['plot']['width'])
        self.assertEqual(22, response_json['plot']['length'])

        assert_reputation(self, reputation_count + 6)

    def test_update_plot_with_udfs(self):
        self._makeUdfd('abc', 'choice', choices=['a', 'b', 'c'])
        self._makeUdfd('def', 'choice', choices=['d', 'e', 'f'])
        self._makeUdfd('multi-ghi', 'multichoice', choices=['g', 'h', 'i'])
        self._makeUdfd('multi-jkl', 'multichoice', choices=['j', 'k', 'l'])
        test_plot = mkPlot(self.instance, self.user)
        test_plot.width = 1
        test_plot.length = 2
        test_plot.geocoded_address = 'foo'
        test_plot.udfs['abc'] = 'a'
        test_plot.udfs['multi-ghi'] = ['g', 'h']
        test_plot.save_with_user(self.user)

        self.assertEqual(test_plot.udfs['abc'], 'a')
        self.assertEqual(test_plot.udfs['multi-ghi'], ['g', 'h'])
        self.assertNotIn('def', test_plot.udfs)
        self.assertNotIn('multi-jkl', test_plot.udfs)

        # Include `updated_by` because the app does send it,
        # and the endpoint must ignore it.
        # Likewise, include `udf:def` set to empty string and
        # `udf:multi-jkl` set to empty list, for the same reason.
        updated_values = {'plot':
                          {'geom': {'y': 0.001, 'x': 0.001, 'srid': 4326},
                           'width': 11,
                           'length': 22,
                           'udf:abc': 'b',
                           'udf:def': '',
                           'udf:multi-ghi': '["g"]',
                           'udf:multi-jkl': '[]',
                           'updated_by': self.user.pk}}

        response = put_json("%s/instance/%s/plots/%d" %
                            (API_PFX, self.instance.url_name, test_plot.pk),
                            updated_values, self.client, self.user)

        self.assertEqual(200, response.status_code)

        response_json = loads(response.content)

        test_plot.refresh_from_db()

        # It should have updated the plot.
        self.assertEqual(test_plot.udfs['abc'], 'b')
        # It should have sent the new value in the response.
        self.assertEqual(response_json['plot']['udf:abc'], 'b')

        self.assertEqual(test_plot.udfs['multi-ghi'], ['g'])
        # It should have sent the new value in the response.
        self.assertEqual(response_json['plot']['udf:multi-ghi'], ['g'])

        # It should not have added 'def' to the plot udfs.
        self.assertNotIn('def', test_plot.udfs)
        self.assertEqual(response_json['plot']['udf:def'], None)

        # It should not have added 'multi-jkl' to the plot udfs.
        self.assertNotIn('multi-jkl', test_plot.udfs)
        self.assertEqual(response_json['plot']['udf:multi-jkl'], None)

    def test_update_tree_with_udfs(self):
        self._makeUdfd('abc', 'choice', model_type='Tree',
                       choices=['a', 'b', 'c'])
        self._makeUdfd('def', 'choice', model_type='Tree',
                       choices=['d', 'e', 'f'])
        self._makeUdfd('multi-ghi', 'multichoice', model_type='Tree',
                       choices=['g', 'h', 'i'])
        self._makeUdfd('multi-jkl', 'multichoice', model_type='Tree',
                       choices=['j', 'k', 'l'])

        test_plot = mkPlot(self.instance, self.user)
        test_plot = mkPlot(self.instance, self.user)
        test_plot.width = 1
        test_plot.length = 2
        test_plot.geocoded_address = 'foo'
        test_plot.save_with_user(self.user)

        test_tree = mkTree(self.instance, self.user, plot=test_plot)
        test_tree.udfs['abc'] = 'a'
        test_tree.udfs['multi-ghi'] = ['g', 'h']
        test_tree.save_with_user(self.user)

        # and the endpoint must ignore it.
        # Likewise, include `udf:def` set to empty string and
        # `udf:multi-jkl` set to empty list, for the same reason.
        updated_values = {'tree':
                          {'udf:abc': 'b',
                           'udf:def': '',
                           'udf:multi-ghi': '["g"]',
                           'udf:multi-jkl': '[]'}}

        response = put_json("%s/instance/%s/plots/%d" %
                            (API_PFX, self.instance.url_name, test_plot.pk),
                            updated_values, self.client, self.user)

        self.assertEqual(200, response.status_code)

        response_json = loads(response.content)

        test_tree.refresh_from_db()

        # It should have updated the plot.
        self.assertEqual(test_tree.udfs['abc'], 'b')
        # It should have sent the new value in the response.
        self.assertEqual(response_json['tree']['udf:abc'], 'b')

        self.assertEqual(test_tree.udfs['multi-ghi'], ['g'])
        # It should have sent the new value in the response.
        self.assertEqual(response_json['tree']['udf:multi-ghi'], ['g'])

        # It should not have added 'def' to the plot udfs.
        self.assertNotIn('def', test_tree.udfs)
        self.assertEqual(response_json['tree']['udf:def'], None)

        # It should not have added 'multi-jkl' to the plot udfs.
        self.assertNotIn('multi-jkl', test_tree.udfs)
        self.assertEqual(response_json['tree']['udf:multi-jkl'], None)

    @skip("ignore pending")
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

        reputation_count = self.user.get_reputation(self.instance)

        updated_values = {'geometry':
                          {'lat': 70, 'lon': 60},
                          'plot_width': 11,
                          'plot_length': 22}

        # Send the edit request as a public user
        response = put_json("%s/instance/%s/plots/%d" %
                            (API_PFX, self.instance.url_name, test_plot.pk),
                            updated_values, self.client, self.public_user)

        self.assertEqual(200, response.status_code)

        # Assert that nothing has changed.
        # Pends should have been created instead
        response_json = loads(response.content)

        self.assertEqual(50, response_json['geom']['y'])
        self.assertEqual(50, response_json['geom']['x'])
        self.assertEqual(1, response_json['plot_width'])
        self.assertEqual(2, response_json['plot_length'])

        assert_reputation(self, reputation_count)

        self.assertEqual(3, len(Audit.pending_audits()),
                         "Expected 3 pends, one for each edited field")

        self.assertEqual(3, len(list(response_json['pending_edits'].keys())),
                         "Expected the json response to have a "
                         "pending_edits dict with 3 keys, one for each field")

    def test_invalid_field_returns_200_field_is_not_in_response(self):
        test_plot = mkPlot(self.instance, self.user)
        updated_values = {'foo': 'bar'}

        response = put_json("%s/instance/%s/plots/%d" %
                            (API_PFX, self.instance.url_name, test_plot.pk),
                            updated_values, self.client, self.user)

        self.assertEqual(200, response.status_code)
        response_json = loads(response.content)
        self.assertFalse("error" in list(response_json.keys()),
                         "Did not expect an error")

        self.assertFalse("foo" in list(response_json.keys()),
                         "Did not expect foo to be added to the plot")

    def test_update_creates_tree(self):
        test_plot = mkPlot(self.instance, self.user)
        test_plot_id = test_plot.id
        self.assertIsNone(test_plot.current_tree())
        updated_values = {'tree': {'diameter': 1.2}}

        response = put_json("%s/instance/%s/plots/%d" %
                            (API_PFX, self.instance.url_name, test_plot.pk),
                            updated_values, self.client, self.user)

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

    #     response = put_json("%s/instance/%s/plots/%d" %
    #                      (API_PFX, self.instance.url_name, test_plot.pk),
    #                      updated_values, self.client, self.public_user)

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

        # Include `updated_by` because the app does send it,
        # and the endpoint must ignore it.
        updated_values = {'tree': {'diameter': 3.9},
                          'plot': {'updated_by': self.user.pk}}
        response = put_json("%s/instance/%s/plots/%d" %
                            (API_PFX, self.instance.url_name, test_plot.id),
                            updated_values, self.client, self.user)

        self.assertEqual(200, response.status_code)

        tree = Tree.objects.get(pk=test_tree_id)
        self.assertIsNotNone(tree)
        self.assertEqual(3.9, tree.diameter)

    def test_invalid_tree_update_returns_400(self):
        test_plot = mkPlot(self.instance, self.user)
        test_tree = mkTree(self.instance, self.user, plot=test_plot)
        test_tree_id = test_tree.id
        test_tree.diameter = 2.3
        test_tree.save_with_user(self.user)

        # Include `updated_by` because the app does send it,
        # and the endpoint must ignore it.
        updated_values = {'tree': {'diameter': 0}}
        response = put_json("%s/instance/%s/plots/%d" %
                            (API_PFX, self.instance.url_name, test_plot.id),
                            updated_values, self.client, self.user)

        self.assertEqual(400, response.status_code)

        # Verify that the diameter was not changed
        tree = Tree.objects.get(pk=test_tree_id)
        self.assertIsNotNone(tree)
        self.assertEqual(2.3, tree.diameter)

    @skip("ignore pending")
    def test_update_tree_with_pending(self):
        test_plot = mkPlot(self.instance, self.user)
        test_tree = mkTree(self.instance, self.user, plot=test_plot)
        test_tree_id = test_tree.pk
        test_tree.diameter = 2.3
        test_tree.save_with_user(self.user)

        self.assertEqual(0, len(Audit.pending_audits()),
                         "Expected the test to start with no pending records")

        updated_values = {'tree': {'diameter': 3.9}}

        response = put_json("%s/instance/%s/plots/%d" %
                            (API_PFX, self.instance.url_name, test_plot.pk),
                            updated_values, self.client, self.public_user)

        self.assertEqual(200, response.status_code)
        tree = Tree.objects.get(pk=test_tree_id)

        self.assertIsNotNone(tree)
        self.assertEqual(2.3, tree.diameter,
                         "A pend should have been created instead"
                         " of editing the tree value.")
        self.assertEqual(1, len(Audit.pending_audits()),
                         "Expected 1 pend record for the edited field.")

        response_json = loads(response.content)
        self.assertEqual(1, len(list(response_json['pending_edits'].keys())),
                         "Expected the json response to have a"
                         " pending_edits dict with 1 keys")

    def test_update_tree_species(self):
        test_plot = mkPlot(self.instance, self.user)
        test_tree = mkTree(self.instance, self.user, plot=test_plot)
        test_tree_id = test_tree.id

        first_species = Species.objects.all()[0]
        updated_values = {'tree': {'species': {'id': first_species.id}}}

        response = put_json("%s/instance/%s/plots/%d" %
                            (API_PFX, self.instance.url_name, test_plot.pk),
                            updated_values, self.client, self.user)

        self.assertEqual(200, response.status_code)
        tree = Tree.objects.get(pk=test_tree_id)
        self.assertIsNotNone(tree)
        self.assertEqual(first_species, tree.species)

    def test_update_tree_returns_404_on_invalid_species_id(self):
        test_plot = mkPlot(self.instance, self.user)
        mkTree(self.instance, self.user, plot=test_plot)

        invalid_species_id = -1
        self.assertRaises(Exception,
                          Species.objects.get, pk=invalid_species_id)

        updated_values = {'tree': {'species': {'id': invalid_species_id}}}

        response = put_json("%s/instance/%s/plots/%d" %
                            (API_PFX, self.instance.url_name, test_plot.pk),
                            updated_values, self.client, self.user)

        self.assertEqual(404, response.status_code)

    def test_approve_pending_edit_returns_404_for_invalid_pend_id(self):
        invalid_pend_id = -1
        self.assertRaises(Exception, Audit.objects.get, pk=invalid_pend_id)
        url = "%s/instance/%s/pending-edits/%d/approve/" % (
            API_PFX, self.instance.url_name, invalid_pend_id)
        response = post_json(url, None, self.client, self.user)
        self.assertEqual(404, response.status_code,
                         "Expected approving and invalid "
                         "pend id to return 404")

    def test_reject_pending_edit_returns_404_for_invalid_pend_id(self):
        invalid_pend_id = -1
        self.assertRaises(Exception, Audit.objects.get, pk=invalid_pend_id)
        url = "%s/instance/%s/pending-edits/%d/reject/" % (
            API_PFX, self.instance.url_name, invalid_pend_id)
        response = post_json(url, None, self.client, self.user)

        self.assertEqual(404, response.status_code,
                         "Expected approving and invalid pend "
                         " id to return 404")

    @skip("waiting for pending integration")
    def test_approve_pending_edit(self):
        self.assert_pending_edit_operation(Audit.Type.PendingApprove)

    @skip("waiting for pending integration")
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
        response = put_json("%s/instance/%s/plots/%d" %
                            (API_PFX, self.instance.url_name, test_plot.id),
                            updated_values, self.client,
                            self.public_user)

        self.assertEqual(200, response.status_code)

        tree = Tree.objects.get(pk=test_tree_id)

        self.assertIsNotNone(tree)
        self.assertEqual(original_dbh, tree.diameter,
                         "A pend should have been created instead"
                         " of editing the tree value.")

        self.assertEqual(1, len(Audit.pending_audits()),
                         "Expected 1 pend record for the edited field.")

        pending_edit = Audit.pending_audits()[0]
        self.assertEqual(None, pending_edit.ref,
                         "Expected that the audit has not been applied")

        if action == Audit.Type.PendingApprove:
            action_str = 'approve'
        else:
            action_str = 'reject'

        response = post_json("%s/instance/%s/pending-edits/%d/%s/" %
                             (API_PFX, self.instance.url_name,
                              pending_edit.id, action_str),
                             None, self.client, self.user)

        self.assertEqual(200, response.status_code)

        pending_edit = Audit.objects.get(pk=pending_edit.id)
        self.assertIsNotNone(pending_edit.ref,
                             "Expected the audit to be marked as processed")

        pending_edit_marked = pending_edit.ref
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

    @skip("waiting for pending integration")
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

        response = put_json("%s/instance/%s/plots/%d" %
                            (API_PFX, self.instance.url_name, test_plot.id),
                            updated_values, self.client, self.public_user)
        self.assertEqual(response.status_code, 200,
                         "Non 200 response when updating plot")

        updated_values = {
            "plot_width": 175,
        }

        response = put_json("%s/instance/%s/plots/%d" %
                            (API_PFX, self.instance.url_name, test_plot.id),
                            updated_values,
                            self.client, self.public_user)

        self.assertEqual(response.status_code, 200,
                         "Non 200 response when updating plot")

        test_plot = Plot.objects.get(pk=test_plot.pk)
        pending_edit_count = len(test_plot.get_active_pending_audits())
        self.assertEqual(3, pending_edit_count,
                         "Expected three pending edits but got %d" %
                         pending_edit_count)

        pend = test_plot.get_active_pending_audits()[0]
        approved_pend_id = pend.id
        url = "%s/instance/%s/pending-edits/%d/approve/" % (
            API_PFX, self.instance.url_name, approved_pend_id)
        response = post_json(url, None, self.client, self.user)

        self.assertEqual(response.status_code, 200,
                         "Non 200 response when approving the pend")

        self.assertEqual(1, len(test_plot.get_active_pending_audits()),
                         "Expected there to be 1 pending edits after approval")

    @skip("waiting for normal plot/tree delete integration")
    def test_remove_plot(self):
        plot = mkPlot(self.instance, self.user)
        plot_id = plot.pk

        tree = mkTree(self.instance, self.user, plot=plot)
        tree_id = tree.pk
        url = "%s/instance/%s/plots/%d" % (API_PFX,
                                           self.instance.url_name,
                                           plot_id)

        response = self.client.delete(url, **self.user)
        self.assertEqual(403, response.status_code,
                         "Expected 403 when there's still a tree")

        tree.delete_with_user(self.user)
        response = self.client.delete(url, **self.user)
        self.assertEqual(200, response.status_code,
                         "Expected 200 status code after delete")

        response_dict = loads(response.content)
        self.assertTrue('ok' in response_dict,
                        'Expected a json object response with a "ok" key')

        self.assertTrue(response_dict['ok'],
                        'Expected a json object response with a "ok" key'
                        'set to True')

        plots = Plot.objects.filter(pk=plot_id)
        trees = Tree.objects.filter(pk=tree_id)

        self.assertTrue(len(plots) == 0, 'Expected plot to be gone')
        self.assertTrue(len(trees) == 0, 'Expected tree to be gone')

    @skip("waiting for normal plot/tree delete integration")
    def test_remove_tree(self):
        plot = mkPlot(self.instance, self.user)
        plot_id = plot.pk

        tree = mkTree(self.instance, self.user, plot=plot)
        tree_id = tree.pk
        url = "%s/instance/%s/plots/%d/tree" % (API_PFX,
                                                self.instance.url_name,
                                                plot_id)
        response = self.client.delete(url, **self.user)

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

    def test_update_collection_udf(self):
        test_plot = mkPlot(self.instance, self.user)

        updated_values = {'tree':
                          {'udf:Stewardship':
                           [{'Action': 'Watered', 'Date': '2014-01-01'}]},
                          'plot':
                          {'udf:Stewardship':
                           [{'Action': 'Enlarged', 'Date': '2014-02-02'}]}}

        response = put_json("%s/instance/%s/plots/%d" %
                            (API_PFX, self.instance.url_name, test_plot.pk),
                            updated_values, self.client, self.user)

        self.assertEqual(200, response.status_code)
        response_json = loads(response.content)

        updated_plot = Plot.objects.get(pk=test_plot.pk)
        new_tree = updated_plot.current_tree()

        self.assertEqual(updated_plot.pk, response_json['plot']['id'])
        self.assertEqual(new_tree.pk,
                         response_json['tree']['id'])
        self.assertEqual(updated_plot.udfs['Stewardship'][0]['id'],
                         response_json['plot']['udf:Stewardship'][0]['id'])
        self.assertEqual(new_tree.udfs['Stewardship'][0]['id'],
                         response_json['tree']['udf:Stewardship'][0]['id'])

    def _create_multichoice(self):
        udf = udf_create({'udf.name': 'multi', 'udf.model': 'Plot',
                          'udf.type': 'multichoice',
                          'udf.choices': ['a', 'b', 'c']},
                         self.instance)
        udf_perm = FieldPermission.objects.get(
            model_name='Plot',
            field_name=udf.canonical_name,
            role=self.user.get_role(self.instance),
            instance=self.instance)
        udf_perm.permission_level = FieldPermission.WRITE_DIRECTLY
        udf_perm.save()

    def test_update_multichoice_v3(self):
        self._create_multichoice()
        test_plot = mkPlot(self.instance, self.user)
        test_plot.udfs['multi'] = ['a']
        test_plot.save_with_user(self.user)

        updated_values = {'plot': {
            'geom': {'y': 0, 'x': 0, 'srid': 4326}, 'udf:multi': None}
        }

        response = put_json("/api/v3/instance/%s/plots/%d" %
                            (self.instance.url_name, test_plot.pk),
                            updated_values, self.client, self.user)

        self.assertEqual(200, response.status_code)

        response_json = loads(response.content)
        self.assertIsNone(response_json['plot']['udf:multi'])

        test_plot.udfs['multi'] = ['b', 'c']
        test_plot.save_with_user(self.user)

        updated_values = {'plot': {
            'geom': {'y': 0, 'x': 0, 'srid': 4326}, 'udf:multi': ['b', 'c']}
        }

        response = put_json("/api/v3/instance/%s/plots/%d" %
                            (self.instance.url_name, test_plot.pk),
                            updated_values, self.client, self.user)

        self.assertEqual(200, response.status_code)

        response_json = loads(response.content)
        self.assertEqual(['b', 'c'], response_json['plot']['udf:multi'])

        updated_values = {'plot': {
            'geom': {'y': 0, 'x': 0, 'srid': 4326}, 'udf:multi': []}
        }

        response = put_json("/api/v3/instance/%s/plots/%d" %
                            (self.instance.url_name, test_plot.pk),
                            updated_values, self.client, self.user)

        self.assertEqual(200, response.status_code)

        response_json = loads(response.content)

        # Make sure no change happens if we send an empty list
        # when `udf:multi` does not exist in the plot
        self.assertIsNone(response_json['plot']['udf:multi'])

        updated_values = {'plot': {
            'geom': {'y': 0, 'x': 0, 'srid': 4326}, 'udf:multi': []}
        }

        response = put_json("/api/v3/instance/%s/plots/%d" %
                            (self.instance.url_name, test_plot.pk),
                            updated_values, self.client, self.user)

        self.assertEqual(200, response.status_code)

        response_json = loads(response.content)

        self.assertIsNone(response_json['plot']['udf:multi'])


class Instance(LocalMediaTestCase):
    test_png_name = '2by2.png'
    test_png_path = os.path.join(
        os.path.dirname(__file__),
        'test_resources', test_png_name)

    def setUp(self):
        super(Instance, self).setUp()

        self.instance = make_instance(is_public=True, point=Point(0, 0))
        create_stewardship_udfs(self.instance)

        self.user = make_commander_user(instance=self.instance)
        udf = udf_create({'udf.name': 'multi', 'udf.model': 'Plot',
                          'udf.type': 'multichoice',
                          'udf.choices': ['a', 'b', 'c']},
                         self.instance)
        udf_perm = FieldPermission.objects.get(
            model_name='Plot',
            field_name=udf.canonical_name,
            role=self.user.get_role(self.instance),
            instance=self.instance)
        udf_perm.permission_level = FieldPermission.WRITE_DIRECTLY
        udf_perm.save()

        self.expected_scss_variables = {
            'primary-color': '123456',
            'secondary-color': '987654'
        }
        self.instance.config['scss_variables'] = self.expected_scss_variables
        self.instance.mobile_api_fields = [
            {'header': 'Tree Information',
             'model': 'tree',
             'field_keys': ['tree.species', 'tree.diameter',
                            'tree.height', 'tree.date_planted']},
            {'header': 'Planting Site Information',
             'model': 'plot',
             'field_keys': ['plot.width', 'plot.length', 'plot.udf:multi']},
            {'header': 'Stewardship',
             'collection_udf_keys': ['plot.udf:Stewardship',
                                     'tree.udf:Stewardship'],
             'sort_key': 'Date'}
        ]
        self.instance.save()
        with open(Instance.test_png_path, 'rb') as f:
            self.instance.logo.save(Instance.test_png_name, f)

    def test_returns_config_colors(self):
        request = sign_request_as_user(make_request(), self.user)
        info = instance_info(request, self.instance)
        self.assertEqual(self.expected_scss_variables,
                         info['config']['scss_variables'])

    def test_returns_only_scss_variables(self):
        request = sign_request_as_user(make_request(), self.user)
        info = instance_info(request, self.instance)
        self.assertTrue('scss_variables' in info['config'],
                        '"scss_variables" should exist in instance.config')
        self.assertEqual(1, len(info['config']),
                         'The config dict should only contain a single, '
                         'white listed item')

    @media_dir
    def test_returns_logo(self):
        request = sign_request_as_user(make_request(), self.user)
        info = instance_info(request, self.instance)
        # The actual file name can be changed by the django machinery
        # so I test for a fragment that remains the same
        self.assertTrue('logos/2by2' in info['logoUrl'])

    def test_date_format_conversion(self):
        self.instance.date_format = 'F j, Y'
        self.instance.short_date_format = 'm/d/Y'
        self.instance.save()

        request = sign_request_as_user(make_request(), self.user)
        info = instance_info(request, self.instance)
        self.assertEqual('MM/dd/yyyy', info.get('short_date_format'))
        self.assertEqual('MMMM d, yyyy', info.get('date_format'))

    def test_removes_unreadable_api_fields(self):
        request = sign_request_as_user(make_request(user=self.user), self.user)
        info = instance_info(request, self.instance)

        self.assertDictContainsSubset(
            {'field_keys': ['tree.species', 'tree.diameter', 'tree.height',
                            'tree.date_planted']},
            info.get('field_key_groups')[0])

        set_invisible_permissions(self.instance, self.user, 'Tree',
                                  ['species', 'diameter', 'height'])
        info = instance_info(request, self.instance)

        self.assertDictContainsSubset(
            {'field_keys': ['tree.date_planted']},
            info.get('field_key_groups')[0])

    def test_adds_always_writable_api_fields(self):
        request = sign_request_as_user(make_request(user=self.user), self.user)
        fields = instance_info(request, self.instance)['fields']
        self.assertTrue('plot.geom' in fields)

    def test_collection_udfs_v3(self):
        request = sign_request_as_user(make_request(user=self.user), self.user)

        response = instance_info_endpoint(request, 3, self.instance.url_name)
        info_dict = json.loads(response.content)

        self.assertIn({'header': 'Stewardship',
                       'collection_udf_keys': ['plot.udf:Stewardship',
                                               'tree.udf:Stewardship'],
                       'sort_key': 'Date'},
                      info_dict['field_key_groups'])

    def test_collection_udfs_removed_in_v2(self):
        request = sign_request_as_user(make_request(user=self.user), self.user)

        response = instance_info_endpoint(request, 2, self.instance.url_name)
        info_dict = json.loads(response.content)

        for field_group in info_dict['field_key_groups']:
            self.assertNotIn('collection_udf_keys', field_group)

    def test_multichoice_fields_v4(self):
        request = sign_request_as_user(make_request(user=self.user), self.user)

        response = instance_info_endpoint(request, 4, self.instance.url_name)
        info_dict = json.loads(response.content)
        self.assertIn('plot.udf:multi', list(info_dict['fields'].keys()))
        self.assertTrue(any('plot.udf:multi' in group.get('field_keys', [])
                            for group in info_dict['field_key_groups']))

    def test_multichoice_removed_in_v3(self):
        request = sign_request_as_user(make_request(user=self.user), self.user)

        response = instance_info_endpoint(request, 3, self.instance.url_name)
        info_dict = json.loads(response.content)

        self.assertNotIn('plot.udf:multi', list(info_dict['fields'].keys()))
        self.assertFalse(any('plot.udf:multi' in group.get('field_keys', [])
                             for group in info_dict['field_key_groups']))

    def _get_search_ids(self, info_dict):
        return [field['identifier']
                for field in info_dict['search']['standard']]

    def test_search_fields_v4(self):
        self.instance.mobile_search_fields = {
            'standard': [{'identifier': 'plot.udf:multi'}],
            'missing': []
        }
        self.instance.save()
        request = sign_request_as_user(make_request(user=self.user), self.user)

        response = instance_info_endpoint(request, 4, self.instance.url_name)
        info_dict = json.loads(response.content)
        self.assertIn('plot.udf:multi', self._get_search_ids(info_dict))

    def test_search_removed_in_v3(self):
        self.instance.mobile_search_fields = {
            'standard': [{'identifier': 'plot.udf:multi'}],
            'missing': []
        }
        self.instance.save()
        request = sign_request_as_user(make_request(user=self.user), self.user)

        response = instance_info_endpoint(request, 3, self.instance.url_name)
        info_dict = json.loads(response.content)
        self.assertNotIn('plot.udf:multi', self._get_search_ids(info_dict))


@override_settings(NEARBY_INSTANCE_RADIUS=2)
@override_settings(FEATURE_BACKEND_FUNCTION=None)
@override_settings(VIEWABLE_INSTANCES_FUNCTION=None)
class InstancesClosestToPoint(OTMTestCase):
    def setUp(self):
        self.i1 = make_instance(is_public=True, point=Point(0, 0))
        self.i2 = make_instance(is_public=False, point=Point(0, 0))
        self.i3 = make_instance(is_public=True, point=Point(0, 9000))
        self.i4 = make_instance(is_public=False, point=Point(10000, 0))
        self.user = make_commander_user(instance=self.i2)

    def test_nearby_list_default(self):
        request = sign_request_as_user(make_request(), self.user)

        instance_infos = instances_closest_to_point(request, 0, 0)
        self.assertEqual(1, len(instance_infos['nearby']))
        self.assertEqual(self.i1.pk, instance_infos['nearby'][0]['id'])

        self.assertEqual(0, len(instance_infos['personal']))

    def test_nearby_list_distance(self):
        request = sign_request_as_user(
            make_request({'distance': 100000}), self.user)

        instance_infos = instances_closest_to_point(request, 0, 0)
        self.assertEqual(2, len(instance_infos))
        self.assertEqual(2, len(instance_infos['nearby']))
        self.assertEqual(self.i1.pk, instance_infos['nearby'][0]['id'])
        self.assertEqual(self.i3.pk, instance_infos['nearby'][1]['id'])

        self.assertEqual(0, len(instance_infos['personal']))

    def test_user_list_default(self):
        request = sign_request_as_user(
            make_request(user=self.user), self.user)

        instance_infos = instances_closest_to_point(request, 0, 0)
        self.assertEqual(1, len(instance_infos['nearby']))
        self.assertEqual(self.i1.pk, instance_infos['nearby'][0]['id'])

        self.assertEqual(1, len(instance_infos['personal']))
        self.assertEqual(self.i2.pk, instance_infos['personal'][0]['id'])

    def test_user_list_max(self):
        request = sign_request_as_user(
            make_request({'max': 3, 'distance': 100000}, user=self.user),
            self.user)

        instance_infos = instances_closest_to_point(request, 0, 0)
        self.assertEqual(2, len(instance_infos['nearby']))
        self.assertEqual(self.i1.pk, instance_infos['nearby'][0]['id'])
        self.assertEqual(self.i3.pk, instance_infos['nearby'][1]['id'])

        self.assertEqual(1, len(instance_infos['personal']))
        self.assertEqual(self.i2.pk, instance_infos['personal'][0]['id'])


@override_settings(FEATURE_BACKEND_FUNCTION=None)
@override_settings(VIEWABLE_INSTANCES_FUNCTION=None)
class PublicInstancesTest(OTMTestCase):
    def setUp(self):
        self.i1 = make_instance(is_public=True, point=Point(0, 0))
        self.i2 = make_instance(is_public=False, point=Point(0, 0))

    def test_public_list(self):
        request = sign_request(make_request())

        instance_infos = public_instances(request)
        self.assertEqual(1, len(instance_infos))
        self.assertEqual(self.i1.pk, instance_infos[0]['id'])


class TreePhotoTest(LocalMediaTestCase):
    test_jpeg_path = os.path.join(
        os.path.dirname(__file__),
        'test_resources', '2by2.jpeg')

    test_png_path = os.path.join(
        os.path.dirname(__file__),
        'test_resources', '2by2.png')

    def setUp(self):
        super(TreePhotoTest, self).setUp()

        self.instance = setupTreemapEnv()
        self.user = User.objects.get(username="commander")

        self.factory = RequestFactory()

    def assertSuccessfulResponse(self, response):
        self.assertIsNotNone(response)
        self.assertIsNotNone(response.content)
        response_dict = loads(response.content)
        self.assertTrue('id' in response_dict)
        self.assertTrue('thumbnail' in response_dict)
        self.assertTrue('image' in response_dict)

    def _test_post_photo(self, path):
        plot = mkPlot(self.instance, self.user)
        plot_id = plot.pk

        self.assertIsNone(plot.current_tree())

        url = "%s/instance/%s/plots/%d/tree/photo" % (API_PFX,
                                                      self.instance.url_name,
                                                      plot_id)

        with open(path, 'rb') as img:
            req = self.factory.post(
                url, {'name': 'afile', 'file': img})

            req = sign_request_as_user(req, self.user)

            response = add_photo_endpoint(req, LATEST_API,
                                          self.instance.url_name, plot_id)

        plot = Plot.objects.get(pk=plot.pk)

        self.assertSuccessfulResponse(response)
        self.assertIsNotNone(plot.current_tree())
        self.assertEqual(plot.current_tree().treephoto_set.count(), 1)

    @media_dir
    def test_jpeg_tree_photo_file_name(self):
        self._test_post_photo(TreePhotoTest.test_jpeg_path)

    @media_dir
    def test_png_tree_photo_file_name(self):
        self._test_post_photo(TreePhotoTest.test_png_path)


class UserTest(LocalMediaTestCase):
    def setUp(self):
        super(UserTest, self).setUp()

        self.factory = RequestFactory()
        self.defaultBaseUserDict = {'organization': 'azavea',
                                    'last_name': 'smith',
                                    'first_name': 'john',
                                    'email': 'j@smith.co',
                                    'username': 'jsmith',
                                    'password': 'password'}

        self.defaultUserDict = {'allow_email_contact': True}
        self.defaultUserDict.update(self.defaultBaseUserDict)

    def make_post_request(self, datadict):
        r = sign_request(make_request(method='POST',
                                      body=dumps(datadict)))

        return r

    @media_dir
    def testUploadPhoto(self):
        peon = make_user(username='peon', password='pw')
        peon.save()

        url = reverse('update_user_photo', kwargs={'version': 3,
                                                   'user_id': peon.pk})

        with open(TreePhotoTest.test_jpeg_path, 'rb') as img:
            req = self.factory.post(
                url, {'name': 'afile', 'file': img})

            req = sign_request_as_user(req, peon)

            response = update_profile_photo_endpoint(req, LATEST_API,
                                                     str(peon.pk))

        self.assertEqual(response.status_code, 200)

        peon = User.objects.get(pk=peon.pk)
        self.assertIsNotNone(peon.photo)
        self.assertIsNotNone(peon.thumbnail)

    @media_dir
    def testCanOnlyUploadAsSelf(self):
        # Must do this as yourself
        peon = make_user(username='peon', password='pw')
        peon.save()

        url = reverse('update_user_photo', kwargs={'version': 3,
                                                   'user_id': peon.pk})

        grunt = make_user(username='grunt', password='pw')
        grunt.save()

        with open(TreePhotoTest.test_jpeg_path, 'rb') as img:
            req = self.factory.post(
                url, {'name': 'afile', 'file': img})

            req = sign_request_as_user(req, peon)

            response = update_profile_photo_endpoint(req, LATEST_API,
                                                     str(grunt.pk))

        self.assertEqual(response.status_code, 403)

    def testCreateUser(self):
        rslt = create_user(self.make_post_request(self.defaultUserDict))
        pk = rslt['id']

        user = User.objects.get(pk=pk)

        for field, target_value in self.defaultUserDict.items():
            if field != 'password':
                self.assertEqual(getattr(user, field), target_value)

        valid_password = user.check_password(self.defaultUserDict['password'])
        self.assertEqual(valid_password, True)

    def testGetUserVersion2(self):
        peon = make_user(username='peon', password='pw')
        peon.first_name = 'Puny'
        peon.last_name = 'Mortal'
        peon.save()

        url = reverse('user_info', kwargs={'version': 2})

        ret = loads(get_signed(self.client, url, user=peon).content)

        self.assertEqual(peon.first_name, ret['firstname'])
        self.assertEqual(peon.last_name, ret['lastname'])

    def testCreateDuplicateUsername(self):
        create_user(self.make_post_request(self.defaultUserDict))

        self.defaultUserDict['email'] = 'mail@me.me'
        resp = create_user(self.make_post_request(self.defaultUserDict))
        self.assertEqual(resp.status_code, 409)

        self.defaultUserDict['username'] = 'jsmith2'
        resp = create_user(self.make_post_request(self.defaultUserDict))

        self.assertEqual(User.objects.filter(pk=resp['id']).exists(), True)

    def testCreateDuplicateEmail(self):
        create_user(self.make_post_request(self.defaultUserDict))

        self.defaultUserDict['username'] = 'jsmith2'
        resp = create_user(self.make_post_request(self.defaultUserDict))
        self.assertEqual(resp.status_code, 409)

        self.defaultUserDict['email'] = 'mail@me.me'
        resp = create_user(self.make_post_request(self.defaultUserDict))

        self.assertEqual(User.objects.filter(pk=resp['id']).exists(), True)

    def testMissingFields(self):
        del self.defaultUserDict['email']
        self.assertRaises(ValidationError,
                          create_user,
                          self.make_post_request(self.defaultUserDict))

        self.defaultUserDict['email'] = 'mail@me.me'
        resp = create_user(self.make_post_request(self.defaultUserDict))

        self.assertIsNotNone(resp['id'])

    def testInvalidField(self):
        self.defaultUserDict['hardy'] = 'heron'
        self.assertRaises(ValidationError,
                          create_user,
                          self.make_post_request(self.defaultUserDict))

        del self.defaultUserDict['hardy']
        resp = create_user(self.make_post_request(self.defaultUserDict))

        self.assertIsNotNone(resp['id'])

    def test_boolean_defaults_empty(self):
        user_id = create_user(
            self.make_post_request(self.defaultBaseUserDict))['id']
        user = User.objects.get(pk=user_id)
        self.assertEqual(user.allow_email_contact, False)
        self.assertEqual(user.make_info_public, False)

    def test_boolean_defaults_partial(self):
        user_id = create_user(
            self.make_post_request(self.defaultUserDict))['id']
        user = User.objects.get(pk=user_id)
        self.assertEqual(user.allow_email_contact, True)
        self.assertEqual(user.make_info_public, False)

    def testUpdateUserRequiredField(self):
        peon = make_user(username='peon', password='pw')
        peon.save()

        url = reverse('update_user', kwargs={'version': 3,
                                             'user_id': peon.pk})

        def updatePeonRequest(d):
            return put_json(url, d, self.client, user=peon)

        updatePeonRequest({'last_name': 'l1'})

        peon = User.objects.get(pk=peon.pk)
        self.assertEqual(peon.last_name, 'l1')

        updatePeonRequest({'last_name': 'l2'})

        peon = User.objects.get(pk=peon.pk)
        self.assertEqual(peon.last_name, 'l2')

        updatePeonRequest({'password': 'whateva'})

        peon = User.objects.get(pk=peon.pk)
        valid_password = peon.check_password('whateva')

        self.assertTrue(valid_password)

    def testUpdateUserNameVersion2(self):
        peon = make_user(username='peon', password='pw')
        peon.save()

        url = reverse('update_user', kwargs={'version': 2,
                                             'user_id': peon.pk})

        def updatePeonRequest(d):
            return put_json(url, d, self.client, user=peon)

        updatePeonRequest({'lastname': 'l1'})

        peon = User.objects.get(pk=peon.pk)
        self.assertEqual(peon.last_name, 'l1')

        updatePeonRequest({'lastname': 'l2'})

        peon = User.objects.get(pk=peon.pk)
        self.assertEqual(peon.last_name, 'l2')

    def testCantRemoveRequiredFields(self):
        peon = make_user(username='peon', password='pw')
        peon.save()

        url = reverse('update_user', kwargs={'version': 3,
                                             'user_id': peon.pk})

        resp = put_json(url, {'username': ''},
                        self.client, user=peon)

        self.assertEqual(resp.status_code, 400)

    def testCanOnlyUpdateLoggedInUser(self):
        peon = make_user(username='peon', password='pw')
        peon.save()

        grunt = make_user(username='grunt', password='pw')
        grunt.save()

        url = reverse('update_user', kwargs={'version': 3,
                                             'user_id': peon.pk})

        resp = put_json(url, {'password': 'whateva'},
                        self.client, user=grunt)

        self.assertEqual(resp.status_code, 403)


class SigningTest(OTMTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def process_request_through_url(self, req):
        return check_signature(
            lambda req, *args, **kwargs: req)(req)

    def sign_and_send(self, path, secret):
        """
        Sign and "send" a request for a given path

        If there is an issue this method returns an
        HttpResponse object that was generated

        If signing is a success this method returns
        the authenticated request

        `self.assertRequestWasSuccess` will check
        the result of this function to make sure that
        signing worked
        """
        req = self.factory.get(path)

        req.META['HTTP_HOST'] = 'testserver.com'

        sig = get_signature_for_request(req, secret)

        req = self.factory.get('%s&signature=%s' % (path, sig))

        req.META['HTTP_HOST'] = 'testserver.com'

        resp = self.process_request_through_url(req)

        return resp

    def assertRequestWasSuccess(self, thing):
        # If we got an http request, we're golden
        self.assertIsInstance(thing, HttpRequest)

    def testAwsExample(self):
        # http://docs.aws.amazon.com/general/latest/gr/signature-version-2.html
        req = self.factory.get('https://elasticmapreduce.amazonaws.com?'
                               'AWSAccessKeyId=AKIAIOSFODNN7EXAMPLE&Action='
                               'DescribeJobFlows&SignatureMethod=HmacSHA256&'
                               'SignatureVersion=2&Timestamp='
                               '2011-10-03T15%3A19%3A30&Version=2009-03-31&'
                               'Signature='
                               'i91nKc4PWAt0JJIdXwz9HxZCJDdiy6cf%2FMj6vPxy'
                               'YIs%3')

        req.META['HTTP_HOST'] = 'elasticmapreduce.amazonaws.com'

        sig = get_signature_for_request(
            req, b'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY')

        self.assertEqual(
            sig, 'i91nKc4PWAt0JJIdXwz9HxZCJDdiy6cf/Mj6vPxyYIs=')

    def testTimestampVoidsSignature(self):
        acred = APIAccessCredential.create()
        url = ('http://testserver.com/test/blah?'
               'timestamp=%%s&'
               'k1=4&k2=a&access_key=%s' % acred.access_key)
               #'k1=4&k2=a&access_key=%s' % acred.access_key.decode())

        curtime = datetime.datetime.now()
        invalid = curtime - datetime.timedelta(minutes=100)

        req = self.sign_and_send(url % invalid.strftime(SIG_TIMESTAMP_FORMAT),
                                 acred.secret_key)

        self.assertEqual(req.status_code, 400)

        timestamp = curtime.strftime(SIG_TIMESTAMP_FORMAT)
        req = self.sign_and_send(url % timestamp, acred.secret_key)

        self.assertRequestWasSuccess(req)

    def testPOSTBodyChangesSig(self):
        url = "%s/i/plots/1/tree/photo" % API_PFX

        def get_sig(path):
            with open(path, 'rb') as img:
                req = self.factory.post(
                    url, {'name': 'afile', 'file': img})

                req = sign_request(req)

                return req.GET['signature']

        sig1 = get_sig(TreePhotoTest.test_png_path)
        sig2 = get_sig(TreePhotoTest.test_jpeg_path)

        self.assertNotEqual(sig1, sig2)

    def testChangingUrlChangesSig(self):
        path = 'http://testserver.com/test/blah?access_key=abc'

        req = self.factory.get(path)
        req.META['HTTP_HOST'] = 'testserver.com'

        sig1 = get_signature_for_request(req, b'secret')

        path = 'http://testserver.com/test/blah?access_key=abd'

        req = self.factory.get(path)
        req.META['HTTP_HOST'] = 'testserver.com'

        sig2 = get_signature_for_request(req, b'secret')

        self.assertNotEqual(sig1, sig2)

    def testChangingSecretChangesKey(self):
        path = 'http://testserver.com/test/blah?access_key=abc'
        req = self.factory.get(path)

        req.META['HTTP_HOST'] = 'testserver.com'

        sig1 = get_signature_for_request(req, b'secret1')
        sig2 = get_signature_for_request(req, b'secret2')

        self.assertNotEqual(sig1, sig2)

    def testMalformedTimestamp(self):
        acred = APIAccessCredential.create()
        timestamp = datetime.datetime.now().strftime(SIG_TIMESTAMP_FORMAT)

        url = ('http://testserver.com/test/blah?'
               'timestamp=%%s&'
               'k1=4&k2=a&access_key=%s' % acred.access_key)
               #'k1=4&k2=a&access_key=%s' % acred.access_key.decode())

        req = self.sign_and_send(url % ('%sFAIL' % timestamp),
                                 acred.secret_key)

        self.assertEqual(req.status_code, 400)

        req = self.sign_and_send(url % timestamp, acred.secret_key)
        #req = self.sign_and_send(url % timestamp, acred.secret_key.decode())

        self.assertRequestWasSuccess(req)

    def testMissingAccessKey(self):
        acred = APIAccessCredential.create()
        timestamp = datetime.datetime.now().strftime(SIG_TIMESTAMP_FORMAT)

        url = ('http://testserver.com/test/blah?'
               'timestamp=%s&'
               'k1=4&k2=a' % timestamp)

        req = self.sign_and_send(url, acred.secret_key)

        self.assertEqual(req.status_code, 400)

        #req = self.sign_and_send('%s&access_key=%s' % (url, acred.access_key.decode()),
        req = self.sign_and_send('%s&access_key=%s' % (url, acred.access_key),
                                 acred.secret_key)

        self.assertRequestWasSuccess(req)

    def testAuthenticatesAsUser(self):
        peon = make_user(username='peon', password='pw')
        peon.save()

        acred = APIAccessCredential.create(user=peon)

        timestamp = datetime.datetime.now().strftime(SIG_TIMESTAMP_FORMAT)
        req = self.sign_and_send('http://testserver.com/test/blah?'
                                 'timestamp=%s&'
                                 'k1=4&k2=a&access_key=%s' %
                                 (timestamp, acred.access_key),
                                 #(timestamp, acred.access_key.decode()),
                                 acred.secret_key)
                                 #acred.secret_key.decode())
        self.assertEqual(req.user.pk, peon.pk)


class Authentication(OTMTestCase):
    def setUp(self):
        self.instance = setupTreemapEnv()
        self.jim = User.objects.get(username="jim")

    def test_401(self):
        ret = get_signed(self.client, "%s/user" % API_PFX)
        self.assertEqual(ret.status_code, 401)

    def test_ok(self):
        auth = base64.b64encode(b"jim:password")
        withauth = {"HTTP_AUTHORIZATION": "Basic %s" % auth}

        ret = get_signed(self.client, "%s/user" % API_PFX, **withauth)
        self.assertEqual(ret.status_code, 200)

    def test_malformed_auth(self):
        withauth = {"HTTP_AUTHORIZATION": "FUUBAR"}

        ret = get_signed(self.client, "%s/user" % API_PFX, **withauth)
        self.assertEqual(ret.status_code, 401)

        auth = base64.b64encode(b"foobar")
        withauth = {"HTTP_AUTHORIZATION": "Basic %s" % auth}

        ret = get_signed(self.client, "%s/user" % API_PFX, **withauth)
        self.assertEqual(ret.status_code, 401)

    def test_bad_cred(self):
        auth = base64.b64encode(b"jim:passwordz")
        withauth = {"HTTP_AUTHORIZATION": "Basic %s" % auth}

        ret = get_signed(self.client, "%s/user" % API_PFX, **withauth)
        self.assertEqual(ret.status_code, 401)

    @skip("We can't return reputation until login takes an instance")
    def test_user_has_rep(self):
        ijim = self.jim.get_instance_user(self.instance)
        ijim.reputation = 1001
        ijim.save()

        auth = base64.b64encode(b"jim:password")
        withauth = dict(list(self.sign.items()) +
                        [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        ret = self.client.get("%s/user" % API_PFX, **withauth)

        self.assertEqual(ret.status_code, 200)

        content = loads(ret.content)

        self.assertEqual(content['username'], self.jim.username)
        self.assertEqual(content['status'], 'success')
        self.assertEqual(content['reputation'], 1001)


class UserApiExportsTest(UserExportsTestCase):
    def _test_requires_admin_access(self, endpoint_name):
        url = reverse('user_csv',
                      kwargs={'version': 3,
                              'instance_url_name': self.instance.url_name})

        iuser = self.user1.get_instance_user(self.instance)
        iuser.admin = False
        iuser.save_with_user(iuser)

        resp = get_signed(self.client, url, user=self.user1)
        self.assertEqual(resp.status_code, 403)

        iuser.admin = True
        iuser.save_with_user(self.user1)

        resp = get_signed(self.client, url, user=self.user1)
        self.assertEqual(resp.status_code, 200)

        iuser.delete_with_user(self.user1)

        resp = get_signed(self.client, url, user=self.user1)
        self.assertEqual(resp.status_code, 401)

    def test_csv_requires_admin(self):
        self._test_requires_admin_access('users_csv')

    def test_json_requires_admin(self):
        self._test_requires_admin_access('users_json')


class PasswordResetTest(OTMTestCase):
    def setUp(self):
        self.instance = setupTreemapEnv()
        self.jim = User.objects.get(username="jim")

    def test_send_password_reset_email_url(self):
        url = "%s/send-password-reset-email?email=%s"
        response = post_json(url % (API_PFX, self.jim.email),
                             {}, self.client, None)
        self.assertEqual(response.status_code, 200)


class SpeciesListTest(OTMTestCase):
    def setUp(self):
        self.instance = setupTreemapEnv()
        self.user = User.objects.get(username="jim")

    def test_species_list_endpoint(self):
        response = get_signed(
            self.client,
            "%s/instance/%s/species" % (API_PFX,
                                        self.instance.url_name),
            user=self.user)
        self.assertEqual(response.status_code, 200)
