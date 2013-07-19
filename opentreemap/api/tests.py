"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from StringIO import StringIO

from django.contrib.auth.models import User, UserManager, Permission as P, AnonymousUser
from django.contrib.gis.geos import Point
from django.contrib.contenttypes.models import ContentType
from profiles.models import UserProfile
from django_reputation.models import Reputation
from django.test import TestCase
from django.test.client import Client
import unittest
from django_reputation.models import UserReputationAction, ReputationAction
from simplejson import loads, dumps

from django.conf import settings
from urlparse import urlparse
import urllib
from api.test_utils import setupTreemapEnv, teardownTreemapEnv, mkPlot, mkTree
from treemap.models import Species, Plot, Tree, Pending, TreePending, PlotPending, TreeResource
from treemap.forms import TreeAddForm

from api.models import APIKey, APILog
from api.views import InvalidAPIKeyException, plot_or_tree_permissions, plot_permissions, tree_resource_to_dict, _parse_application_version_header_as_dict, _attribute_requires_conversion, get_cql_query

import os
import struct
import base64

API_PFX = "/api/v2"

def create_signer_dict(user):
    key = APIKey(user=user,key="TESTING",enabled=True,comment="")
    key.save()

    return { "HTTP_X_API_KEY": key.key }

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

def send_binary_body(url, body_stream, size, content_type, client, method, sign_dict=None):
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
        response = send_binary_body(url, f, stat.st_size, content_type, client, 'POST', sign_dict)
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
        self.assertRaises(InvalidAPIKeyException, self.client.get,"%s/version" % API_PFX)

    def test_signed_header(self):
        key = APIKey(user=self.u,key="TESTING",enabled=True,comment="")
        key.save()
        
        ret = self.client.get("%s/version" % API_PFX, **{ "HTTP_X_API_KEY": key.key })
        self.assertEqual(ret.status_code, 200)

    def test_url_param(self):
        key = APIKey(user=self.u,key="TESTING",enabled=True,comment="")
        key.save()
        
        ret = self.client.get("%s/version?apikey=%s" % (API_PFX,key.key))
        self.assertEqual(ret.status_code, 200)

    def test_disabled_keys_dont_work(self):
        key = APIKey(user=self.u,key="TESTING",enabled=False,comment="")
        key.save()

        self.assertRaises(InvalidAPIKeyException, self.client.get, "%s/version" % API_PFX, **{ "X-API-Key": key.key })


    def tearDown(self):
        teardownTreemapEnv()


class Authentication(TestCase):
    def setUp(self):
        setupTreemapEnv()

        self.u = User.objects.get(username="jim")
        self.u.set_password("password")
        self.u.save()

        amy = User.objects.get(username="amy")
        amy.reputation = Reputation(user=amy)
        amy.reputation.save()
        amy_profile = UserProfile(user=amy)
        amy_profile.save()
        amy.set_password("password")
        amy.save()

        self.sign = create_signer_dict(self.u)

    def test_401(self):
        ret = self.client.get("%s/login" % API_PFX, **self.sign)
        self.assertEqual(ret.status_code, 401)
        

    def test_ok(self):
        auth = base64.b64encode("jim:password")
        withauth = dict(self.sign.items() + [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        ret = self.client.get("%s/login" % API_PFX, **withauth)
        self.assertEqual(ret.status_code, 200)

    def test_malformed_auth(self):
        withauth = dict(self.sign.items() + [("HTTP_AUTHORIZATION", "FUUBAR")])

        ret = self.client.get("%s/login" % API_PFX, **withauth)
        self.assertEqual(ret.status_code, 401)

        auth = base64.b64encode("foobar")
        withauth = dict(self.sign.items() + [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        ret = self.client.get("%s/login" % API_PFX, **withauth)
        self.assertEqual(ret.status_code, 401)


    def test_bad_cred(self):
        auth = base64.b64encode("jim:passwordz")
        withauth = dict(self.sign.items() + [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        ret = self.client.get("%s/login" % API_PFX, **withauth)
        self.assertEqual(ret.status_code, 401)

    def test_includes_permissions(self):
        amy = User.objects.get(username="amy")
        self.assertEqual(len(amy.user_permissions.all()), 0, 'Expected the test setUp to create user "amy" with no permissions')

        amy.user_permissions.add(P.objects.get(codename="delete_tree"))
        amy.save()
        amys_perm_count = len(amy.user_permissions.all())

        auth = base64.b64encode("amy:password")
        withauth = dict(self.sign.items() + [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        ret = self.client.get("%s/login" % API_PFX, **withauth)
        self.assertEqual(ret.status_code, 200, "Authentication failed so testing for permissions is blocked")
        self.assertIsNotNone(ret.content, "Response had no content so testing for permissions is blocked")
        content_dict = loads(ret.content)
        self.assertTrue('permissions' in content_dict, "The response did not contain a permissions attribute")
        self.assertEqual(amys_perm_count, len(content_dict['permissions']))
        self.assertTrue('treemap.delete_tree' in content_dict['permissions'], 'The "delete_tree" permission was not in the permissions list for the test user.')

    def user_has_type(self, user, typ):
        auth = base64.b64encode("%s:%s" % (user.username,user.username))
        withauth = dict(create_signer_dict(user).items() + [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        ret = self.client.get("%s/login" % API_PFX, **withauth)
        
        self.assertEqual(ret.status_code, 200)
        json = loads(ret.content)

        self.assertEqual(json['username'], user.username)        
        self.assertEqual(json['user_type'], typ)        

    def create_user(self, username):
        ben = User.objects.create_user(username, "%s@test.org" % username, username)
        ben.set_password(username)
        ben.save()
        ben_profile = UserProfile(user=ben)
        ben_profile.save()
        ben.reputation = Reputation(user=ben)
        ben.reputation.save()        
        return ben

    def test_user_is_admin(self):
        ben = self.create_user("ben")
        ben.is_superuser = True
        ben.save()

        self.user_has_type(ben, {'name': 'administrator', 'level': 1000 })
    
        ben.delete()
    
    def test_user_is_editor(self):
        carol = self.create_user("carol")
        carol.reputation.reputation = 1001
        carol.reputation.save()
    
        self.user_has_type(carol, {'name': 'editor', 'level': 500 })
    
        carol.delete()
    
    def test_user_is_public(self):
        dave = self.create_user("dave")
        dave.reputation.reputation = 0
        dave.reputation.save()
    
        self.user_has_type(dave, {"name": "public", 'level': 0})
    
        dave.delete()


    def tearDown(self):
        teardownTreemapEnv()

class Logging(TestCase):
    def setUp(self):
        setupTreemapEnv()

        self.u = User.objects.get(username="jim")
        self.sign = create_signer_dict(self.u)

    def test_log_request(self):
        settings.SITE_ROOT = ''

        ret = self.client.get("%s/version?rvar=4,rvar2=5" % API_PFX, **self.sign)
        self.assertEqual(ret.status_code, 200)
        
        logs = APILog.objects.all()

        self.assertTrue(logs is not None and len(logs) == 1)

        key = APIKey.objects.get(user=self.u)
        log = logs[0]

        self.assertEqual(log.apikey,key)
        self.assertTrue(log.url.endswith("%s/version?rvar=4,rvar2=5" % API_PFX))
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


class TileRequest(TestCase):
    def setUp(self):
        setupTreemapEnv()

        self.u = User.objects.get(username="jim")

        self.sign = create_signer_dict(self.u)

    def tearDown(self):
        teardownTreemapEnv()
        
    def test_returns(self):
        p1 = mkPlot(self.u)
        p1.geometry = Point(-77,36)
        p1.save()

        p2 = mkPlot(self.u)
        p2.geometry = Point(-77.1,36.1)
        p2.save()

        #
        # Test #1 - Simple request
        # bbox(-78,35,-76,37) <--> bbox(-8682920,4163881,-8460281,4439106)
        #
        # Origin is bottom left
        #
        # Expected values:
        p1x = -77.0
        p1y = 36.0
        p1xM = -8571600.0
        p1yM = 4300621.0
        p2x = -77.1
        p2y = 36.1
        p2xM = -8582732.0
        p2yM = 4314389.0
        
        # Offset X values
        p1offsetx = p1xM - -8682920 #xmin
        p2offsetx = p2xM - -8682920 #xmin

        p1offsety = p1yM - 4163881.0 #ymin
        p2offsety = p2yM - 4163881.0 #ymin

        # Compute scale
        pixelsPerMeterX = 255.0 / (-8460281.0 - -8682920.0)
        pixelsPerMeterY = 255.0 / (4439106.0 - 4163881.0)

        # Computer origin offsets
        pixels1x = int(p1offsetx * pixelsPerMeterX + 0.5)
        pixels2x = int(p2offsetx * pixelsPerMeterX + 0.5)

        pixels1y = int(p1offsety * pixelsPerMeterY + 0.5)
        pixels2y = int(p2offsety * pixelsPerMeterY + 0.5)

        style = 0
        npts = 2

        # Format:
        # | File Header           | Section Header             | Pts                                        |
        # |0xA3A5EA00 | int: size | byte: style | short: # pts | 00 | byte:x1 | byte:y1 | byte:x2 | byte:y2 |
        testoutp = struct.pack("<IIBHxBBBB", 0xA3A5EA00, npts, style, npts, pixels2x, pixels2y, pixels1x, pixels1y)

        outp = self.client.get("%s/tiles?bbox=-78,35,-76,37" % API_PFX, **self.sign)

        self.assertEqual(testoutp, outp.content)
        

    def test_eats_same_point(self):
        x = 128 # these values come from the test_returns
        y = 127 # test case

        p1 = mkPlot(self.u)
        p1.geometry = Point(-77.0,36.0)
        p1.save()

        p2 = mkPlot(self.u)
        p2.geometry = Point(-77.0,36.0000001)
        p2.save()

        p3 = mkPlot(self.u)
        p3.geometry = Point(-76.99999,36)
        p3.save()

        p4 = mkPlot(self.u)
        p4.geometry = Point(-77.0,35.999999)
        p4.save()

        # These should all map to (x,y)->(128,127)
        npts = 1
        style = 0

        # Format:
        # | File Header           | Section Header             | Pts                                        |
        # |0xA3A5EA00 | int: size | byte: style | short: # pts | 00 | byte:x1 | byte:y1 | byte:x2 | byte:y2 |
        testoutp = struct.pack("<IIBHxBB", 0xA3A5EA00, npts, style, npts, x,y)
        
        outp = self.client.get("%s/tiles?bbox=-78,35,-76,37" % API_PFX, **self.sign)

        self.assertEqual(testoutp, outp.content)
        

class PlotListing(TestCase):
    def setUp(self):
        setupTreemapEnv()

        self.u = User.objects.get(username="jim")
        self.sign = create_signer_dict(self.u)
        self.client = Client()

    def tearDown(self):
        teardownTreemapEnv()

    def test_recent_edits(self):
        user = self.u
        p = mkPlot(user)
        p2 = mkPlot(user)
        t3 = mkTree(user)
        acts = ReputationAction.objects.all()

        content_type_p = ContentType(app_label='auth', model='Plot')
        content_type_p.save()

        reputation1 = UserReputationAction(action=acts[0],
                                           user=user,
                                           originating_user=user,
                                           content_type=content_type_p,
                                           object_id=p.pk,
                                           content_object=p,
                                           value=20)
        reputation1.save()

        auth = base64.b64encode("%s:%s" % (user.username,user.username))
        withauth = dict(create_signer_dict(user).items() + [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        ret = self.client.get("%s/user/%s/edits" % (API_PFX, user.pk), **withauth)
        json = loads(ret.content)
        
        self.assertEqual(len(json), 1) # Just on reputation item
        self.assertEqual(json[0]['plot_id'], p.pk)
        self.assertEqual(json[0]['id'], reputation1.pk)

        reputation2 = UserReputationAction(action=acts[1 % len(acts)],
                                           user=user,
                                           originating_user=user,
                                           content_type=content_type_p,
                                           object_id=p2.pk,
                                           content_object=p2,
                                           value=20)
        reputation2.save()

        ret = self.client.get("%s/user/%s/edits" % (API_PFX, user.pk), **withauth)
        json = loads(ret.content)
        
        self.assertEqual(len(json), 2) # Just on reputation item
        self.assertEqual(json[0]['plot_id'], p2.pk)
        self.assertEqual(json[0]['id'], reputation2.pk)

        self.assertEqual(json[1]['plot_id'], p.pk)
        self.assertEqual(json[1]['id'], reputation1.pk)

        reputation3 = UserReputationAction(action=acts[2 % len(acts)],
                                           user=user,
                                           originating_user=user,
                                           content_type=content_type_p,
                                           object_id=t3.pk,
                                           content_object=t3,
                                           value=20)
        reputation3.save()


        ret = self.client.get("%s/user/%s/edits" % (API_PFX, user.pk), **withauth)
        json = loads(ret.content)
        
        self.assertEqual(len(json), 3) # Just on reputation item
        self.assertEqual(json[0]['plot_id'], t3.plot.pk)
        self.assertEqual(json[0]['id'], reputation3.pk)

        self.assertEqual(json[1]['plot_id'], p2.pk)
        self.assertEqual(json[1]['id'], reputation2.pk)

        self.assertEqual(json[2]['plot_id'], p.pk)
        self.assertEqual(json[2]['id'], reputation1.pk)

        ret = self.client.get("%s/user/%s/edits?offset=1" % (API_PFX, user.pk), **withauth)
        json = loads(ret.content)
        
        self.assertEqual(len(json), 2) # Just on reputation item
        self.assertEqual(json[0]['plot_id'], p2.pk)
        self.assertEqual(json[0]['id'], reputation2.pk)

        self.assertEqual(json[1]['plot_id'], p.pk)
        self.assertEqual(json[1]['id'], reputation1.pk)

        ret = self.client.get("%s/user/%s/edits?offset=2&length=1" % (API_PFX, user.pk), **withauth)
        json = loads(ret.content)
        
        self.assertEqual(len(json), 1) # Just on reputation item
        self.assertEqual(json[0]['plot_id'], p.pk)
        self.assertEqual(json[0]['id'], reputation1.pk)

        ret = self.client.get("%s/user/%s/edits?length=1" % (API_PFX, user.pk), **withauth)
        json = loads(ret.content)
        
        self.assertEqual(len(json), 1) # Just on reputation item
        self.assertEqual(json[0]['plot_id'], t3.plot.pk)
        self.assertEqual(json[0]['id'], reputation3.pk)
        
        reputation1.delete()
        reputation2.delete()
        reputation3.delete()
        content_type_p.delete()                
        p.delete()
        p2.delete()
        t3.delete()

    def test_edit_flags(self):
        content_type_p = ContentType(app_label='auth', model='Plot')
        content_type_p.save()

        content_type_t = ContentType(app_label='auth', model='Tree')
        content_type_t.save()

        p = P(codename="change_user",name="change_user",content_type=content_type_p)
        p.save()

        t = P(codename="change_user",name="change_user",content_type=content_type_t)
        t.save()

        ghost = AnonymousUser()

        peon = User(username="peon")
        peon.save()
        peon.reputation = Reputation(user=peon)
        peon.reputation.save()

        duke = User(username="duke")
        duke.save()
        duke.reputation = Reputation(user=duke)
        duke.reputation.save()

        leroi = User(username="leroi")
        leroi.active = True
        leroi.save() # double save required for m2m... 
        leroi.reputation = Reputation(user=leroi)
        leroi.user_permissions.add(p)
        leroi.user_permissions.add(t)
        leroi.save()
        leroi.reputation.save()

        p_peon_0 = mkPlot(peon)
        p_peon_1 = mkPlot(peon)
        p_duke_2 = mkPlot(duke)
        
        t_duke_0 = mkTree(duke, plot=p_peon_0)
        t_peon_1 = mkTree(peon, plot=p_peon_1)
        t_duke_2 = mkTree(duke, plot=p_duke_2)

        p_roi_3 = mkPlot(leroi)
        t_roi_3 = mkTree(leroi, plot=p_roi_3)

        plots = [p_peon_0, p_peon_1, p_duke_2, p_roi_3]
        trees = [t_duke_0, t_peon_1, t_duke_2, t_roi_3]
        users = [ghost, peon, duke, leroi]

        def mkd(e, d):
            return { "can_delete": d, "can_edit": e }

        def mkdp(pe, pd, te=None, td=None):
            d = { "plot": mkd(pe,pd) }
            if td != None and te != None:
                d["tree"] = mkd(te, td)

            return d

        #################################
        # A None or Anonymous user can't
        # do anything
        for p in plots:
            self.assertEqual(mkd(False,False), plot_or_tree_permissions(p, ghost))
            self.assertEqual(mkdp(False,False,False,False), plot_permissions(p, ghost))

            self.assertEqual(mkd(False,False), plot_or_tree_permissions(p, None))
            self.assertEqual(mkdp(False,False,False,False), plot_permissions(p, None))

        for t in trees:
            self.assertEqual(mkd(False,False), plot_or_tree_permissions(t, ghost))
            self.assertEqual(mkd(False,False), plot_or_tree_permissions(t, None))

        #################################
        # A user can always delete or edit their own trees and plots
        #
        self.assertEqual(mkd(True,True), plot_or_tree_permissions(p_peon_0, peon))
        self.assertEqual(mkd(True,True), plot_or_tree_permissions(p_peon_1, peon))
        self.assertEqual(mkd(True,True), plot_or_tree_permissions(p_duke_2, duke))

        self.assertEqual(mkd(True,True), plot_or_tree_permissions(t_duke_0, duke))        
        self.assertEqual(mkd(True,True), plot_or_tree_permissions(t_peon_1, peon))        
        self.assertEqual(mkd(True,True), plot_or_tree_permissions(t_duke_2, duke))        

        self.assertEqual(mkd(True,True), plot_or_tree_permissions(p_roi_3, leroi)) 
        self.assertEqual(mkd(True,True), plot_or_tree_permissions(t_roi_3, leroi)) 

        #################################
        # An admin user can always do anything
        #
        for p in plots:
            self.assertEqual(mkd(True,True), plot_or_tree_permissions(p, leroi))
            self.assertEqual(mkdp(True,True,True,True), plot_permissions(p, leroi))

        for t in trees:
            self.assertEqual(mkd(True,True), plot_or_tree_permissions(t, leroi))

        #################################
        # A user can edit other trees but can't delete
        #
        self.assertEqual(mkdp(True,False,True,False), plot_permissions(p_roi_3, duke))

        #################################
        # No one can edit readonly trees
        #
        for p in plots:
            p.readonly = True
            p.save()
        for t in trees:
            t.readonly = True
            t.save()

        for p in plots:
            for u in users:
                self.assertEqual(mkd(False,False), plot_or_tree_permissions(p, u))
                self.assertEqual(mkdp(False,False,False,False), plot_permissions(p, u))

        for t in trees:
            for u in users:
                self.assertEqual(mkd(False,False), plot_or_tree_permissions(t, u))
        
        
        

        
    def test_basic_data(self):
        p = mkPlot(self.u)
        p.width = 22
        p.length = 44
        p.present = True
        p.geometry = Point(55,56)
        p.geometry.srid = 4326
        p.readonly = False
        p.save()

        info = self.client.get("%s/plots" % API_PFX, **self.sign)

        self.assertEqual(info.status_code, 200)
        
        json = loads(info.content)

        self.assertEqual(len(json), 1)
        record = json[0]

        self.assertEqual(record["id"], p.pk)
        self.assertEqual(record["plot_width"], 22)
        self.assertEqual(record["plot_length"], 44)
        self.assertEqual(record["readonly"], False)
        self.assertEqual(record["geometry"]["srid"], 4326)
        self.assertEqual(record["geometry"]["lat"], 56)
        self.assertEqual(record["geometry"]["lng"], 55)
        self.assertEqual(record.get("tree"), None)

    def test_tree_data(self):
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
        setupTreemapEnv()

        self.user = User.objects.get(username="jim")
        self.sign = create_signer_dict(self.user)

    def test_locations_plots_endpoint_with_auth(self):
        auth = base64.b64encode("%s:%s" % (self.user.username,self.user.username))
        withauth = dict(create_signer_dict(self.user).items() + [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        response = self.client.get("%s/locations/0,0/plots" % API_PFX, **withauth)
        self.assertEqual(response.status_code, 200)

    def test_locations_plots_endpoint(self):
        response = self.client.get("%s/locations/0,0/plots" % API_PFX, **self.sign)
        self.assertEqual(response.status_code, 200)

    def test_locations_plots_endpoint_max_plots_param_must_be_a_number(self):
        response = self.client.get("%s/locations/0,0/plots?max_plots=foo" % API_PFX, **self.sign)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, 'The max_plots parameter must be a number between 1 and 500')

    def test_locations_plots_endpoint_max_plots_param_cannot_be_greater_than_500(self):
        response = self.client.get("%s/locations/0,0/plots?max_plots=501" % API_PFX, **self.sign)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, 'The max_plots parameter must be a number between 1 and 500')
        response = self.client.get("%s/locations/0,0/plots?max_plots=500" % API_PFX, **self.sign)
        self.assertEqual(response.status_code, 200)

    def test_locations_plots_endpoint_max_plots_param_cannot_be_less_than_1(self):
        response = self.client.get("%s/locations/0,0/plots?max_plots=0" % API_PFX, **self.sign)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, 'The max_plots parameter must be a number between 1 and 500')
        response = self.client.get("%s/locations/0,0/plots?max_plots=1" % API_PFX, **self.sign)
        self.assertEqual(response.status_code, 200)

    def test_locations_plots_endpoint_distance_param_must_be_a_number(self):
        response = self.client.get("%s/locations/0,0/plots?distance=foo" % API_PFX, **self.sign)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, 'The distance parameter must be a number')
        response = self.client.get("%s/locations/0,0/plots?distance=42" % API_PFX, **self.sign)
        self.assertEqual(response.status_code, 200)

    def test_plots(self):
        plot = mkPlot(self.user)
        plot.present = True
        plot.save()

        response = self.client.get("%s/locations/%s,%s/plots" % (API_PFX, plot.geometry.x, plot.geometry.y), **self.sign)

        self.assertEqual(response.status_code, 200)
        json = loads(response.content)

class CreatePlotAndTree(TestCase):

    def setUp(self):
        setupTreemapEnv()

        self.user = User.objects.get(username="jim")
        self.user.set_password("password")
        self.user.save()
        self.sign = create_signer_dict(self.user)
        auth = base64.b64encode("jim:password")
        self.sign = dict(self.sign.items() + [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

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

        plot_count = Plot.objects.count()
        reputation_count = UserReputationAction.objects.count()

        response = post_json( "%s/plots"  % API_PFX, data, self.client, self.sign)

        self.assertEqual(201, response.status_code, "Create failed:" + response.content)

        # Assert that a plot was added
        self.assertEqual(plot_count + 1, Plot.objects.count())
        # Assert that reputation was added
        self.assertEqual(reputation_count + 1, UserReputationAction.objects.count())

        response_json = loads(response.content)
        self.assertTrue("id" in response_json)
        id = response_json["id"]
        plot = Plot.objects.get(pk=id)
        self.assertEqual(35.0, plot.geometry.x)
        self.assertEqual(25.0, plot.geometry.y)
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
        reputation_count = UserReputationAction.objects.count()

        response = post_json( "%s/plots"  % API_PFX, data, self.client, self.sign)

        self.assertEqual(400, response.status_code, "Expected creating a million foot tall tree to return 400:" + response.content)

        body_dict = loads(response.content)
        self.assertTrue('error' in body_dict, "Expected the body JSON to contain an 'error' key")
        errors = body_dict['error']
        self.assertTrue(len(errors) == 1, "Expected a single error message to be returned")
        self.assertEqual('Height is too large.', errors[0])

        # Assert that a tree was _not_ added
        self.assertEqual(tree_count, Tree.objects.count())
        # Assert that reputation was _not_ added
        self.assertEqual(reputation_count, UserReputationAction.objects.count())

    def test_create_plot_with_geometry(self):
        data = {
            "geometry": {
                "lon": 35,
                "lat": 25,
            },
            "geocode_address": "1234 ANY ST",
            "edit_address_street": "1234 ANY ST",
            "tree": {
                "height": 10
            }
        }

        plot_count = Plot.objects.count()
        reputation_count = UserReputationAction.objects.count()

        response = post_json( "%s/plots"  % API_PFX, data, self.client, self.sign)

        self.assertEqual(201, response.status_code, "Create failed:" + response.content)

        # Assert that a plot was added
        self.assertEqual(plot_count + 1, Plot.objects.count())
        # Assert that reputation was added
        self.assertEqual(reputation_count + 1, UserReputationAction.objects.count())

        response_json = loads(response.content)
        self.assertTrue("id" in response_json)
        id = response_json["id"]
        plot = Plot.objects.get(pk=id)
        self.assertEqual(35.0, plot.geometry.x)
        self.assertEqual(25.0, plot.geometry.y)
        tree = plot.current_tree()
        self.assertIsNotNone(tree)
        self.assertEqual(10.0, tree.height)

class PendingTrigger(TestCase):
   def setUp(self):
        setupTreemapEnv()
        settings.PENDING_ON = True

        self.user = User.objects.get(username="jim")
        self.user.set_password("password")
        self.user.save()
        self.sign = create_signer_dict(self.user)
        auth = base64.b64encode("jim:password")
        self.sign = dict(self.sign.items() + [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        self.public_user1 = User.objects.get(username="amy")
        self.public_user1.set_password("password")
        self.public_user1.save()
        self.public_user1.reputation = Reputation(user=self.public_user1)
        self.public_user1.reputation.save()
        self.public_user1_sign = create_signer_dict(self.public_user1)
        public_user1_auth = base64.b64encode("amy:password")
        self.public_user1_sign = dict(self.public_user1_sign.items() + [("HTTP_AUTHORIZATION", "Basic %s" % public_user1_auth)])

        self.public_user2 = User.objects.get(username="olivia")
        self.public_user2.set_password("password")
        self.public_user2.save()
        self.public_user2.reputation = Reputation(user=self.public_user2)
        self.public_user2.reputation.save()
        self.public_user2_sign = create_signer_dict(self.public_user2)
        public_user2_auth = base64.b64encode("olivia:password")
        self.public_user2_sign = dict(self.public_user2_sign.items() + [("HTTP_AUTHORIZATION", "Basic %s" % public_user2_auth)])


   def create_standard_plot(self, user,x=50,y=50,width=1,length=2,geocoded_address='foo'):
      test_plot = mkPlot(user)
      test_plot.width = 1
      test_plot.length = 2
      test_plot.geocoded_address = 'foo'
      test_plot.save()

      self.assertEqual(50, test_plot.geometry.x)
      self.assertEqual(50, test_plot.geometry.y)
      self.assertEqual(1, test_plot.width)
      self.assertEqual(2, test_plot.length)
      self.assertEqual('foo', test_plot.geocoded_address)
      self.assertEqual(0, len(Pending.objects.all()), "Expected the test to start with no pending records")

      return test_plot

   def verify_standard_plot(self, response_json,x=50,y=50,width=1,length=2,geocoded_address='foo'):
      self.assertEqual(y, response_json['geometry']['lat'])
      self.assertEqual(x, response_json['geometry']['lng'])
      self.assertEqual(width, response_json['plot_width'])
      self.assertEqual(length, response_json['plot_length'])
      self.assertEqual(geocoded_address, response_json['address'])

   def make_and_edit(self, make_user, edit_user_sign, expectpends):
      for p in Pending.objects.all():
         p.delete()

      updated_values = {'geometry': {'lat': 70, 'lon': 60},
                        'plot_width': 11, 
                        'plot_length': 22, 
                        'geocoded_address': 'bar'}


      plot = self.create_standard_plot(make_user)

      reputation_count = UserReputationAction.objects.count()

      # Send the edit request as a public user
      response = put_json( "%s/plots/%d"  % (API_PFX, plot.id),
                           updated_values, self.client, edit_user_sign)

      response_json = loads(response.content)

      self.assertEqual(200, response.status_code)

      if expectpends:
         # Assert that nothing has changed. Pends should have been created instead
         response_json = loads(response.content)

         self.verify_standard_plot(response_json)
         self.assertEqual(reputation_count, UserReputationAction.objects.count())
         self.assertEqual(4, len(PlotPending.objects.all()),
                          "Expected 4 pends, one for each edited field")

         self.assertEqual(4, len(response_json['pending_edits'].keys()), 
                          "Expected the json response to have a "\
                          "pending_edits dict with 4 keys, one for each field")

      else:
         # Assert that values have been updatd
         self.verify_standard_plot(response_json,
                                   x=60, y=70,
                                   width=11, length=22,
                                   geocoded_address='bar')

         self.assertTrue(not response_json['pending_edits'],
                         "Expected no pending edits")

   def test_public_edits_public(self):
      settings.PENDING_REQUIRED_FOR_PUBLIC_EDITING_PUBLIC_TREES = False
      self.make_and_edit(self.public_user1, self.public_user2_sign, 
                         expectpends=False)

      settings.PENDING_REQUIRED_FOR_PUBLIC_EDITING_PUBLIC_TREES = True
      self.make_and_edit(self.public_user1, self.public_user2_sign, 
                         expectpends=True)

   def test_public_edits_mgmt(self):
      settings.PENDING_REQUIRED_FOR_PUBLIC_EDITING_PUBLIC_TREES = False
      self.make_and_edit(self.user, self.public_user1_sign,
                         expectpends=True)
    
      settings.PENDING_REQUIRED_FOR_PUBLIC_EDITING_PUBLIC_TREES = True
      self.make_and_edit(self.user, self.public_user1_sign,
                         expectpends=True)

   def test_public_edits_own(self):
      settings.PENDING_REQUIRED_FOR_PUBLIC_EDITING_PUBLIC_TREES = False
      self.make_and_edit(self.public_user1, self.public_user1_sign,
                         expectpends=False)
    
      settings.PENDING_REQUIRED_FOR_PUBLIC_EDITING_PUBLIC_TREES = True
      self.make_and_edit(self.public_user1, self.public_user1_sign,
                         expectpends=False)

   def test_mgmt_edits_own(self):
      settings.PENDING_REQUIRED_FOR_PUBLIC_EDITING_PUBLIC_TREES = False
      self.make_and_edit(self.user, self.sign,
                         expectpends=False)
    
      settings.PENDING_REQUIRED_FOR_PUBLIC_EDITING_PUBLIC_TREES = True
      self.make_and_edit(self.user, self.sign,
                         expectpends=False)

   def test_mgmt_edits_public(self):
      settings.PENDING_REQUIRED_FOR_PUBLIC_EDITING_PUBLIC_TREES = False
      self.make_and_edit(self.public_user1, self.sign,
                         expectpends=False)
    
      settings.PENDING_REQUIRED_FOR_PUBLIC_EDITING_PUBLIC_TREES = True
      self.make_and_edit(self.public_user1, self.sign,
                         expectpends=False)

class UpdatePlotAndTree(TestCase):
    def setUp(self):
        setupTreemapEnv()
        settings.PENDING_ON = False

        self.user = User.objects.get(username="jim")
        self.user.set_password("password")
        self.user.save()
        self.sign = create_signer_dict(self.user)
        auth = base64.b64encode("jim:password")
        self.sign = dict(self.sign.items() + [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        self.public_user = User.objects.get(username="amy")
        self.public_user.set_password("password")
        self.public_user.save()
        self.public_user.reputation = Reputation(user=self.public_user)
        self.public_user.reputation.save()

        self.public_user_sign = create_signer_dict(self.public_user)
        public_user_auth = base64.b64encode("amy:password")
        self.public_user_sign = dict(self.public_user_sign.items() + [("HTTP_AUTHORIZATION", "Basic %s" % public_user_auth)])

    def test_invalid_plot_id_returns_400_and_a_json_error(self):
        response = put_json( "%s/plots/0"  % API_PFX, {}, self.client, self.sign)
        self.assertEqual(400, response.status_code)
        response_json = loads(response.content)
        self.assertTrue("error" in response_json)
        # Received an error message as expected in response_json['error']

    def test_update_plot(self):
        test_plot = mkPlot(self.user)
        test_plot.width = 1
        test_plot.length = 2
        test_plot.geocoded_address = 'foo'
        test_plot.save()
        self.assertEqual(50, test_plot.geometry.x)
        self.assertEqual(50, test_plot.geometry.y)
        self.assertEqual(1, test_plot.width)
        self.assertEqual(2, test_plot.length)
        self.assertEqual('foo', test_plot.geocoded_address)

        reputation_count = UserReputationAction.objects.count()

        updated_values = {'geometry': {'lat': 70, 'lon': 60}, 'plot_width': 11, 'plot_length': 22, 'geocoded_address': 'bar'}
        response = put_json( "%s/plots/%d"  % (API_PFX, test_plot.id), updated_values, self.client, self.sign)
        self.assertEqual(200, response.status_code)

        response_json = loads(response.content)
        self.assertEqual(70, response_json['geometry']['lat'])
        self.assertEqual(60, response_json['geometry']['lng'])
        self.assertEqual(11, response_json['plot_width'])
        self.assertEqual(22, response_json['plot_length'])
        self.assertEqual('bar', response_json['address'])
        self.assertEqual(reputation_count + 1, UserReputationAction.objects.count())

    def test_update_plot_with_pending(self):
        settings.PENDING_ON = True
        test_plot = mkPlot(self.user)
        test_plot.width = 1
        test_plot.length = 2
        test_plot.geocoded_address = 'foo'
        test_plot.save()
        self.assertEqual(50, test_plot.geometry.x)
        self.assertEqual(50, test_plot.geometry.y)
        self.assertEqual(1, test_plot.width)
        self.assertEqual(2, test_plot.length)
        self.assertEqual('foo', test_plot.geocoded_address)
        self.assertEqual(0, len(Pending.objects.all()), "Expected the test to start with no pending records")

        reputation_count = UserReputationAction.objects.count()

        updated_values = {'geometry': {'lat': 70, 'lon': 60}, 'plot_width': 11, 'plot_length': 22, 'geocoded_address': 'bar'}
        # Send the edit request as a public user
        response = put_json( "%s/plots/%d"  % (API_PFX, test_plot.id), updated_values, self.client, self.public_user_sign)
        self.assertEqual(200, response.status_code)

        # Assert that nothing has changed. Pends should have been created instead
        response_json = loads(response.content)
        self.assertEqual(50, response_json['geometry']['lat'])
        self.assertEqual(50, response_json['geometry']['lng'])
        self.assertEqual(1, response_json['plot_width'])
        self.assertEqual(2, response_json['plot_length'])
        self.assertEqual('foo', response_json['address'])
        self.assertEqual(reputation_count, UserReputationAction.objects.count())
        self.assertEqual(4, len(PlotPending.objects.all()), "Expected 4 pends, one for each edited field")

        self.assertEqual(4, len(response_json['pending_edits'].keys()), "Expected the json response to have a pending_edits dict with 4 keys, one for each field")

    def test_invalid_field_returns_200_field_is_not_in_response(self):
        test_plot = mkPlot(self.user)
        updated_values = {'foo': 'bar'}
        response = put_json( "%s/plots/%d"  % (API_PFX, test_plot.id), updated_values, self.client, self.sign)
        self.assertEqual(200, response.status_code)
        response_json = loads(response.content)
        self.assertFalse("error" in response_json.keys(), "Did not expect an error")
        self.assertFalse("foo" in response_json.keys(), "Did not expect foo to be added to the plot")

    def test_update_creates_tree(self):
        test_plot = mkPlot(self.user)
        test_plot_id = test_plot.id
        self.assertIsNone(test_plot.current_tree())
        updated_values = {'tree': {'dbh': 1.2}}
        response = put_json( "%s/plots/%d"  % (API_PFX, test_plot.id), updated_values, self.client, self.sign)
        self.assertEqual(200, response.status_code)
        tree = Plot.objects.get(pk=test_plot_id).current_tree()
        self.assertIsNotNone(tree)
        self.assertEqual(1.2, tree.dbh)

    def test_update_creates_tree_with_pending(self):
        settings.PENDING_ON = True
        test_plot = mkPlot(self.user)
        test_plot_id = test_plot.id
        self.assertIsNone(test_plot.current_tree())
        self.assertEqual(0, len(Pending.objects.all()), "Expected the test to start with no pending records")

        updated_values = {'tree': {'dbh': 1.2}}
        response = put_json( "%s/plots/%d"  % (API_PFX, test_plot.id), updated_values, self.client, self.public_user_sign)
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(Pending.objects.all()), "Expected a new tree to be created, rather than creating pends")
        tree = Plot.objects.get(pk=test_plot_id).current_tree()
        self.assertIsNotNone(tree)
        self.assertEqual(1.2, tree.dbh)

    def test_update_tree(self):
        test_plot = mkPlot(self.user)
        test_tree = mkTree(self.user, plot=test_plot)
        test_tree_id = test_tree.id
        test_tree.dbh = 2.3
        test_tree.save()

        updated_values = {'tree': {'dbh': 3.9}}
        response = put_json( "%s/plots/%d"  % (API_PFX, test_plot.id), updated_values, self.client, self.sign)
        self.assertEqual(200, response.status_code)
        tree = Tree.objects.get(pk=test_tree_id)
        self.assertIsNotNone(tree)
        self.assertEqual(3.9, tree.dbh)

    def test_update_tree_with_pending(self):
        settings.PENDING_ON = True

        test_plot = mkPlot(self.user)
        test_tree = mkTree(self.user, plot=test_plot)
        test_tree_id = test_tree.id
        test_tree.dbh = 2.3
        test_tree.save()

        self.assertEqual(0, len(Pending.objects.all()), "Expected the test to start with no pending records")

        updated_values = {'tree': {'dbh': 3.9}}
        response = put_json( "%s/plots/%d"  % (API_PFX, test_plot.id), updated_values, self.client, self.public_user_sign)
        self.assertEqual(200, response.status_code)
        tree = Tree.objects.get(pk=test_tree_id)
        self.assertIsNotNone(tree)
        self.assertEqual(2.3, tree.dbh, "A pend should have been created instead of editing the tree value.")
        self.assertEqual(1, len(TreePending.objects.all()), "Expected 1 pend record for the edited field.")

        response_json = loads(response.content)
        self.assertEqual(1, len(response_json['pending_edits'].keys()), "Expected the json response to have a pending_edits dict with 1 keys")

    def test_update_tree_species(self):
        test_plot = mkPlot(self.user)
        test_tree = mkTree(self.user, plot=test_plot)
        test_tree_id = test_tree.id

        first_species = Species.objects.all()[0]
        updated_values = {'tree': {'species': first_species.id}}
        response = put_json( "%s/plots/%d"  % (API_PFX, test_plot.id), updated_values, self.client, self.sign)
        self.assertEqual(200, response.status_code)
        tree = Tree.objects.get(pk=test_tree_id)
        self.assertIsNotNone(tree)
        self.assertEqual(first_species, tree.species)

    def test_update_tree_returns_400_on_invalid_species_id(self):
        test_plot = mkPlot(self.user)
        mkTree(self.user, plot=test_plot)

        invalid_species_id = -1
        self.assertRaises(Exception, Species.objects.get, pk=invalid_species_id)

        updated_values = {'tree': {'species': invalid_species_id}}
        response = put_json( "%s/plots/%d"  % (API_PFX, test_plot.id), updated_values, self.client, self.sign)
        self.assertEqual(400, response.status_code)
        response_json = loads(response.content)
        self.assertTrue("error" in response_json.keys(), "Expected an 'error' key in the JSON response")

    def test_approve_pending_edit_returns_404_for_invalid_pend_id(self):
        settings.PENDING_ON = True
        invalid_pend_id = -1
        self.assertRaises(Exception, PlotPending.objects.get, pk=invalid_pend_id)
        self.assertRaises(Exception, TreePending.objects.get, pk=invalid_pend_id)

        response = post_json("%s/pending-edits/%d/approve/"  % (API_PFX, invalid_pend_id), None, self.client, self.sign)
        self.assertEqual(404, response.status_code, "Expected approving and invalid pend id to return 404")

    def test_reject_pending_edit_returns_404_for_invalid_pend_id(self):
        settings.PENDING_ON = True
        invalid_pend_id = -1
        self.assertRaises(Exception, PlotPending.objects.get, pk=invalid_pend_id)
        self.assertRaises(Exception, TreePending.objects.get, pk=invalid_pend_id)

        response = post_json("%s/pending-edits/%d/reject/"  % (API_PFX, invalid_pend_id), None, self.client, self.sign)
        self.assertEqual(404, response.status_code, "Expected approving and invalid pend id to return 404")

    def test_approve_pending_edit(self):
        self.assert_pending_edit_operation('approve')

    def test_reject_pending_edit(self):
        self.assert_pending_edit_operation('reject')

    def assert_pending_edit_operation(self, action, original_dbh=2.3, edited_dbh=3.9):
        settings.PENDING_ON = True

        test_plot = mkPlot(self.user)
        test_tree = mkTree(self.user, plot=test_plot)
        test_tree_id = test_tree.id
        test_tree.dbh = original_dbh
        test_tree.save()

        if action == 'approve':
            status_after_action = 'approved'
        elif action == 'reject':
            status_after_action = 'rejected'
        else:
            raise Exception('Action must be "approve" or "reject"')

        self.assertEqual(0, len(Pending.objects.all()), "Expected the test to start with no pending records")

        updated_values = {'tree': {'dbh': edited_dbh}}
        response = put_json( "%s/plots/%d"  % (API_PFX, test_plot.id), updated_values, self.client, self.public_user_sign)
        self.assertEqual(200, response.status_code)
        tree = Tree.objects.get(pk=test_tree_id)
        self.assertIsNotNone(tree)
        self.assertEqual(original_dbh, tree.dbh, "A pend should have been created instead of editing the tree value.")
        self.assertEqual(1, len(TreePending.objects.all()), "Expected 1 pend record for the edited field.")

        pending_edit = TreePending.objects.all()[0]
        self.assertEqual('pending', pending_edit.status, "Expected the status of the Pending to be 'pending'")
        response = post_json("%s/pending-edits/%d/%s/"  % (API_PFX, pending_edit.id, action), None, self.client, self.sign)
        self.assertEqual(200, response.status_code)

        pending_edit = TreePending.objects.get(pk=pending_edit.id)
        self.assertEqual(status_after_action, pending_edit.status, "Expected the status of the Pending to be '%s'" % status_after_action)
        test_tree = Tree.objects.get(pk=test_tree_id)

        if action == 'approve':
            self.assertEqual(edited_dbh, test_tree.dbh, "Expected dbh to have been updated on the Tree")
        elif action == 'reject':
            self.assertEqual(original_dbh, test_tree.dbh, "Expected dbh to NOT have been updated on the Tree")

        response_json = loads(response.content)
        self.assertTrue('tree' in response_json)
        self.assertTrue('dbh' in response_json['tree'])
        if action == 'approve':
            self.assertEqual(edited_dbh, response_json['tree']['dbh'], "Expected dbh to have been updated in the JSON response")
        elif action == 'reject':
            self.assertEqual(original_dbh, response_json['tree']['dbh'], "Expected dbh to NOT have been updated in the JSON response")

    def test_approve_plot_pending_with_mutiple_pending_edits(self):
        settings.PENDING_ON = True

        test_plot = mkPlot(self.user)
        test_plot.width = 100
        test_plot.length = 50
        test_plot.save()
        test_tree = mkTree(self.user, plot=test_plot)
        test_tree.dbh = 2.3
        test_tree.save()

        updated_values = {
            "plot_width": 125,
            "plot_length": 25,
            "tree": {
                "dbh": 3.9
            }
        }

        response = put_json( "%s/plots/%d"  % (API_PFX, test_plot.id), updated_values, self.client, self.public_user_sign)
        self.assertEqual(response.status_code, 200, "Non 200 response when updating plot")

        updated_values = {
            "plot_width": 175,
        }

        response = put_json( "%s/plots/%d"  % (API_PFX, test_plot.id), updated_values, self.client, self.public_user_sign)
        self.assertEqual(response.status_code, 200, "Non 200 response when updating plot")

        test_plot = Plot.objects.get(pk=test_plot.pk)
        pending_edit_count = len(list(test_plot.get_active_pends_with_tree_pends()))
        self.assertEqual(4, pending_edit_count, "Expected three pending edits but got %d" % pending_edit_count)

        pend = test_plot.get_active_pends()[0]
        approved_pend_id = pend.id

        response = post_json("%s/pending-edits/%d/approve/"  % (API_PFX, approved_pend_id), None, self.client, self.sign)
        self.assertEqual(response.status_code, 200, "Non 200 response when approving the pend")
        self.assertEqual(2, len(list(test_plot.get_active_pends_with_tree_pends())), "Expected there to be 2 pending edits after approval")

        for plot_pending in PlotPending.objects.all():
            if plot_pending.id == approved_pend_id:
                self.assertEqual('approved', plot_pending.status, 'The status of the approved pend should be "approved"')
            elif plot_pending.field == 'width':
                self.assertEqual('rejected', plot_pending.status, 'The status of the non-approved width pends should be "rejected"')
            else: # plot_pending.id != approved_pend_id and plot_pending.field != 'width'
                self.assertEqual('pending', plot_pending.status, 'The status of plot pends not on the width field should still be "pending"')

        for tree_pending in TreePending.objects.all():
            self.assertEqual('pending', tree_pending.status, 'The status of tree pends should still be "pending"')

    def test_remove_plot(self):
        plot = mkPlot(self.user)
        plot_id = plot.pk

        tree = mkTree(self.user, plot=plot)
        tree_id = tree.pk

        response = self.client.delete("%s/plots/%d" % (API_PFX, plot_id), **self.sign)
        self.assertEqual(200, response.status_code, "Expected 200 status code after delete")
        response_dict = loads(response.content)
        self.assertTrue('ok' in response_dict, 'Expected a json object response with a "ok" key')
        self.assertTrue(response_dict['ok'], 'Expected a json object response with a "ok" key set to True')

        plot = Plot.objects.get(pk=plot_id)
        tree = Tree.objects.get(pk=tree_id)

        self.assertFalse(plot.present, 'Expected "present" to be False on a deleted plot')
        for audit_trail_record in plot.history.all():
            self.assertFalse(audit_trail_record.present, 'Expected "present" to be False for all audit trail records for a deleted plot')

        self.assertFalse(tree.present, 'Expected "present" to be False on tree associated with a deleted plot')
        for audit_trail_record in tree.history.all():
            self.assertFalse(audit_trail_record.present, 'Expected "present" to be False for all audit trail records for tree associated with a deleted plot')

    def test_remove_tree(self):
        plot = mkPlot(self.user)
        plot_id = plot.pk

        tree = mkTree(self.user, plot=plot)
        tree_id = tree.pk

        response = self.client.delete("%s/plots/%d/tree" % (API_PFX, plot_id), **self.sign)
        self.assertEqual(200, response.status_code, "Expected 200 status code after delete")
        response_dict = loads(response.content)
        self.assertIsNone(response_dict['tree'], 'Expected a json object response to a None value for "tree" key after the tree is deleted')

        plot = Plot.objects.get(pk=plot_id)
        tree = Tree.objects.get(pk=tree_id)

        self.assertTrue(plot.present, 'Expected "present" to be True after tree is deleted from plot')
        for audit_trail_record in plot.history.all():
            self.assertTrue(audit_trail_record.present, 'Expected "present" to be True for all audit trail records for plot with a deleted tree')

        self.assertFalse(tree.present, 'Expected "present" to be False on tree associated with a deleted plot')
        for audit_trail_record in tree.history.all():
            self.assertFalse(audit_trail_record.present, 'Expected "present" to be False for all audit trail records for tree associated with a deleted plot')

    def test_get_current_tree(self):
        plot = mkPlot(self.user)
        plot_id = plot.pk

        tree = mkTree(self.user, plot=plot)

        response = self.client.get("%s/plots/%d/tree" % (API_PFX, plot_id), **self.sign)
        self.assertEqual(200, response.status_code, "Expected 200 status code after delete")
        response_dict = loads(response.content)
        self.assertTrue('species' in response_dict, 'Expected "species" to be a top level key in the response object')
        self.assertEqual(tree.species.pk, response_dict['species'])

    def test_registration(self):
        self.assertTrue(User.objects.filter(username='foobar').count() == 0, "The test expects the foobar user to not exists.")
        data = {
            'username': 'foobar',
            'firstname': 'foo',
            'lastname': 'bar',
            'email': 'foo@bar.com',
            'password': 'drowssap',
            'zipcode': 19107
        }
        response = post_json("%s/user/" % API_PFX, data, self.client, self.sign)
        self.assertEqual(200, response.status_code, "Expected 200 status code after creating user")
        response_dict = loads(response.content)
        self.assertTrue('status' in response_dict, 'Expected "status" to be a top level key in the response object')
        self.assertEqual('success', response_dict['status'], 'Expected "status" to be "success"')
        self.assertTrue(User.objects.filter(username='foobar').count() == 1, 'Expected the "foobar" user to be created.')

    def test_duplicate_registration(self):
        self.assertTrue(User.objects.filter(username='jim').count() == 1, "The test expects the jim user to exist.")
        data = {
            'username': 'jim',
            'firstname': 'Jim',
            'lastname': 'User',
            'email': 'jim@user.com',
            'password': 'drowssap',
            'zipcode': 19107
        }
        response = post_json("%s/user/" % API_PFX, data, self.client, self.sign)
        self.assertEqual(409, response.status_code, "Expected 409 status code after attempting to create duplicate username")
        response_dict = loads(response.content)
        self.assertTrue('status' in response_dict, 'Expected "status" to be a top level key in the response object')
        self.assertEqual('failure', response_dict['status'], 'Expected "status" to be "failure"')
        self.assertTrue('detail' in response_dict, 'Expected "detail" to be a top level key in the response object')
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
        request = _create_mock_request_with_version_string('ios-1.2-b32-some-other junk')
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


class ChoiceConversion(TestCase):

    def setUp(self):
        setupTreemapEnv()
        self._setup_test_choice_conversions()

        self.user = User.objects.get(username="jim")
        self.user.set_password("password")
        self.user.save()
        self.sign = create_signer_dict(self.user)
        auth = base64.b64encode("jim:password")
        self.sign = dict(self.sign.items() + [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        self.public_user = User.objects.get(username="amy")
        self.public_user.set_password("password")
        self.public_user.save()
        self.public_user.reputation = Reputation(user=self.public_user)
        self.public_user.reputation.save()

        self.public_user_sign = create_signer_dict(self.public_user)
        public_user_auth = base64.b64encode("amy:password")
        self.public_user_sign = dict(self.public_user_sign.items() + [("HTTP_AUTHORIZATION", "Basic %s" % public_user_auth)])

    def tearDown(self):
        self._restore_choice_conversions()
        teardownTreemapEnv()

    def _setup_test_choice_conversions(self):
        self.original_choices = settings.CHOICES
        if hasattr(settings, 'CHOICE_CONVERSIONS'):
            self.original_choice_conversions = settings.CHOICE_CONVERSIONS
        else:
            self.original_choice_conversions = None

        settings.CHOICES['conditions'] = [
                ("10", "Good"),
                ("11", "Bad")
            ]
        settings.CHOICE_CONVERSIONS = {
            "condition": {
                'version-threshold': {
                    'ios': '1.2.2'
                },
                "forward": [
                    ("1", "10"),
                    ("2", "11"),
                    ("3", "11")
                ],
                "reverse": [
                    ("10", "1"),
                    ("11", "3")
                ]
            }
        }
        # Form field definitions are cached so a change to settings.CHOICES after the
        # form class has been imported will not be reflected automatically
        TreeAddForm.base_fields['condition'].choices = settings.CHOICES['conditions']

    def _restore_choice_conversions(self):
        settings.CHOICES = self.original_choices
        # Form field definitions are cached so a change to settings.CHOICES after the
        # form class has been imported will not be reflected automatically
        TreeAddForm.base_fields['condition'].choices = settings.CHOICES['conditions']

        if self.original_choice_conversions is not None:
            settings.CHOICE_CONVERSIONS = self.original_choice_conversions

    def test_attribute_requires_conversion_when_no_version_is_specified(self):
        request = _create_mock_request_without_version()
        self.assertTrue(_attribute_requires_conversion(request, 'condition'))

    def test_attribute_requires_conversion_when_version_is_under_threshold(self):
        request = _create_mock_request_with_version_string('ios-1.1-b12')
        self.assertTrue(_attribute_requires_conversion(request, 'condition'))

    def test_attribute_requires_conversion_when_version_is_non_numeric(self):
        request = _create_mock_request_with_version_string('ios-null-bnull')
        self.assertTrue(_attribute_requires_conversion(request, 'condition'))

    def test_attribute_requires_conversion_when_version_is_3_segments(self):
        request = _create_mock_request_with_version_string('ios-1.2.1-b12')
        self.assertTrue(_attribute_requires_conversion(request, 'condition'))

    def test_attribute_does_not_require_conversion_when_version_is_3_segments(self):
        request = _create_mock_request_with_version_string('ios-1.3.1-b12')
        self.assertFalse(_attribute_requires_conversion(request, 'condition'))

    def test_attribute_does_not_require_conversion_when_version_is_equal_to_threshold(self):
        request = _create_mock_request_with_version_string('ios-1.2.2-b12')
        self.assertFalse(_attribute_requires_conversion(request, 'condition'))

    def test_set_tree_attribute_with_choice_conversion(self):
        test_plot = mkPlot(self.user)
        test_tree = mkTree(self.user, plot=test_plot)
        test_tree_id = test_tree.id
        test_tree.condition = "10"
        test_tree.save()

        # We expect the 2 to be converted to an 11
        updated_values = {'tree': {'condition': '2'}}
        response = put_json("%s/plots/%d" %
            (API_PFX, test_plot.id), updated_values, self.client, self.sign)
        self.assertEqual(200, response.status_code)
        tree = Tree.objects.get(pk=test_tree_id)
        self.assertIsNotNone(tree)
        self.assertEqual("11", tree.condition)

    def test_get_tree_with_choice_conversion(self):
        plot = mkPlot(self.user)
        plot_id = plot.pk

        tree = mkTree(self.user, plot=plot)
        tree.condition = "10"
        tree.save()

        response = self.client.get("%s/plots/%d" % (API_PFX, plot_id), **self.sign)
        self.assertEqual(200, response.status_code, "Expected 200 status code after delete")
        response_dict = loads(response.content)
        self.assertTrue('tree' in response_dict, 'Expected "tree" to be a top level key in the response object')
        tree_dict = response_dict['tree']
        self.assertTrue('condition' in tree_dict, 'Expected "condition" to be a key in the tree object')
        self.assertEqual(tree_dict['condition'], '1')

    def test_create_plot_with_tree(self):
        data = {
            "lon": 35,  # Location properties are required
            "lat": 25,  # Location properties are required
            "geocode_address": "1234 ANY ST",  # Location properties are required
            "edit_address_street": "1234 ANY ST",  # Location properties are required
            'tree': {
                'condition': 1
            }
        }

        response = post_json('%s/plots' % API_PFX, data, self.client, self.sign)

        self.assertEqual(201, response.status_code, 'Create failed:' + response.content)

        response_json = loads(response.content)
        self.assertTrue('tree' in response_json)
        self.assertTrue('condition' in response_json['tree'])
        # Check that the server responds with the 'old' choice value
        self.assertEqual('1', response_json['tree']['condition'])

        self.assertTrue('id' in response_json)
        id = response_json['id']
        plot = Plot.objects.get(pk=id)
        tree = plot.current_tree()
        self.assertIsNotNone(tree)
        # Check that the 'new' choice value was set in the database
        self.assertEqual('10', tree.condition)

    def test_update_tree_with_pending(self):
        settings.PENDING_ON = True
        try:
            test_plot = mkPlot(self.user)
            test_tree = mkTree(self.user, plot=test_plot)
            test_tree_id = test_tree.id
            test_tree.condition = 11
            test_tree.save()

            updated_values = {'tree': {'condition': 1}}
            response = put_json("%s/plots/%d" % (API_PFX, test_plot.id), updated_values, self.client, self.public_user_sign)
            self.assertEqual(200, response.status_code)
            tree = Tree.objects.get(pk=test_tree_id)
            self.assertIsNotNone(tree)
            self.assertEqual('11', tree.condition, "A pend should have been created instead of editing the tree value.")

            self.assertEqual(1, len(TreePending.objects.all()))
            pend = TreePending.objects.all()[0]
            self.assertEqual('10', pend.value, "Expected the updated value of 1 to be converted to a 10")

            response_json = loads(response.content)
            self.assertEqual(1, len(response_json['pending_edits'].keys()), "Expected the json response to have a pending_edits dict with 1 keys")
            self.assertEqual('tree.condition', response_json['pending_edits'].keys()[0], "Expected 'tree.condition' to have a pending edit")
            pending_edit = response_json['pending_edits']['tree.condition']
            self.assertEqual('1', pending_edit['latest_value'], "Expected the latest_value to be 1 in the JSON response")
            pending_edit_item = pending_edit['pending_edits'][0]
            self.assertEqual('1', pending_edit_item['value'], "Expected the pending edit value to be 1 in the JSON response")

        finally:
            settings.PENDING_ON = False

    def test_approve_pending_edit(self):
        self.assert_pending_edit_operation('approve')

    def test_reject_pending_edit(self):
        self.assert_pending_edit_operation('reject')

    def assert_pending_edit_operation(self, action):
        settings.PENDING_ON = True

        old_original_conditions = ['2', '3']
        old_edited_condition = '1'

        new_original_condition = '11'
        new_edited_condition = '10'

        test_plot = mkPlot(self.user)
        test_tree = mkTree(self.user, plot=test_plot)
        test_tree_id = test_tree.id
        test_tree.condition = new_original_condition
        test_tree.save()

        if action == 'approve':
            status_after_action = 'approved'
        elif action == 'reject':
            status_after_action = 'rejected'
        else:
            raise Exception('Action must be "approve" or "reject"')

        self.assertEqual(0, len(Pending.objects.all()), "Expected the test to start with no pending records")

        updated_values = {'tree': {'condition': old_edited_condition}}
        response = put_json("%s/plots/%d" % (API_PFX, test_plot.id), updated_values, self.client, self.public_user_sign)
        self.assertEqual(200, response.status_code)
        tree = Tree.objects.get(pk=test_tree_id)
        self.assertIsNotNone(tree)
        self.assertEqual(new_original_condition, tree.condition, "A pend should have been created instead of editing the tree value.")
        self.assertEqual(1, len(TreePending.objects.all()), "Expected 1 pend record for the edited field.")

        pending_edit = TreePending.objects.all()[0]
        self.assertEqual('pending', pending_edit.status, "Expected the status of the Pending to be 'pending'")

        response = post_json("%s/pending-edits/%d/%s/" % (API_PFX, pending_edit.id, action), None, self.client, self.sign)
        self.assertEqual(200, response.status_code)

        pending_edit = TreePending.objects.get(pk=pending_edit.id)
        self.assertEqual(status_after_action, pending_edit.status, "Expected the status of the Pending to be '%s'" % status_after_action)
        test_tree = Tree.objects.get(pk=test_tree_id)

        if action == 'approve':
            self.assertEqual(new_edited_condition, test_tree.condition, "Expected condition to have been updated on the Tree")
        elif action == 'reject':
            self.assertEqual(new_original_condition, test_tree.condition, "Expected condition to NOT have been updated on the Tree")

        response_json = loads(response.content)
        self.assertTrue('tree' in response_json)
        self.assertTrue('condition' in response_json['tree'])
        if action == 'approve':
            self.assertEqual(old_edited_condition, response_json['tree']['condition'], "Expected condition to have been updated in the JSON response")
        elif action == 'reject':
            # Because both 2 and 3 convert to the same value the values that gets restored on
            # rejection is not deterministic
            self.assertTrue(response_json['tree']['condition'] in old_original_conditions, "Expected condition to NOT have been updated in the JSON response")


class Resource(TestCase):
    def setUp(self):
        setupTreemapEnv()

    def tearDown(self):
        teardownTreemapEnv()

    def test_tree_resource_to_dict_on_empty_resource(self):
        # If resources are all calculated as zero, this method should still return a valid object

        tr = TreeResource()
        tr.annual_stormwater_management = 0
        tr.annual_electricity_conserved = 0
        tr.annual_energy_conserved = 0
        tr.annual_natural_gas_conserved = 0
        tr.annual_air_quality_improvement = 0
        tr.annual_co2_sequestered = 0
        tr.annual_co2_avoided = 0
        tr.annual_co2_reduced = 0
        tr.total_co2_stored = 0
        tr.annual_ozone = 0
        tr.annual_nox = 0
        tr.annual_pm10 = 0
        tr.annual_sox = 0
        tr.annual_voc = 0
        tr.annual_bvoc = 0

        resource_dict = tree_resource_to_dict(tr)
        self.assertIsNotNone(resource_dict)

class TreePhoto(TestCase):

    def setUp(self):
        setupTreemapEnv()
        self.user = User.objects.get(username="jim")
        self.user.set_password("password")
        self.user.save()
        self.sign = create_signer_dict(self.user)
        auth = base64.b64encode("jim:password")
        self.sign = dict(self.sign.items() + [("HTTP_AUTHORIZATION", "Basic %s" % auth)])

        self.test_jpeg_path = os.path.join(os.path.dirname(__file__), 'test_resources', '2by2.jpeg')
        self.test_png_path = os.path.join(os.path.dirname(__file__), 'test_resources', '2by2.png')

        def assertSuccessfulResponse(response):
            self.assertIsNotNone(response)
            self.assertIsNotNone(response.content)
            response_dict = loads(response.content)
            self.assertTrue('status' in response_dict)
            self.assertEqual('success', response_dict['status'])
        self.assertSuccessfulResponse = assertSuccessfulResponse

    def tearDown(self):
        teardownTreemapEnv()

    def test_jpeg_tree_photo_file_name(self):
        plot = mkPlot(self.user)
        plot_id = plot.pk
        response = post_jpeg_file( "%s/plots/%d/tree/photo"  % (API_PFX, plot_id), self.test_jpeg_path,
            self.client, self.sign)

        self.assertSuccessfulResponse(response)

        plot = Plot.objects.get(pk=plot_id)
        tree = plot.current_tree()
        self.assertIsNotNone(tree)
        photo = tree.treephoto_set.all()[0]
        self.assertEqual('plot_%d.jpeg' % plot_id, photo.title)

    def test_png_tree_photo_file_name(self):
        plot = mkPlot(self.user)
        plot_id = plot.pk
        response = post_png_file( "%s/plots/%d/tree/photo"  % (API_PFX, plot_id), self.test_png_path,
            self.client, self.sign)

        self.assertSuccessfulResponse(response)

        plot = Plot.objects.get(pk=plot_id)
        tree = plot.current_tree()
        self.assertIsNotNone(tree)
        photo = tree.treephoto_set.all()[0]
        self.assertEqual('plot_%d.png' % plot_id, photo.title)

class CQLFiltering(TestCase):
    """Class for testing the APIs feature to generate CQL strings.

    The testing strategy used here is to:
    1) Test that an API call with no parameters will return an empty CQL string
    2) Test two different boolean parameters
    3) Test that two boolean parameters can be correctly combined
    4) Test a non boolean (string matching) parameter
    """
    def setUp(self):
        setupTreemapEnv()
        self.user = User.objects.get(username="jim")
        self.user.set_password("password")
        self.user.save()
        self.sign = create_signer_dict(self.user)

    def tearDown(self):
        teardownTreemapEnv()

    def assertParamsProduceResponse(self, params, expected_cql):
        expected_json = """{"cql_string": "%s"}""" % expected_cql
        response = self.client.get("%s/cql-filter" % API_PFX, params, **self.sign)
        self.assertEqual(expected_json, response.content)

    def test_without_params(self):
        params = {}
        expected_cql = ""
        self.assertParamsProduceResponse(params, expected_cql)

    def test_boolean_missing_species(self):
        params = {'missing_species' : 'True',}
        expected_cql = "species_id IS NULL"
        self.assertParamsProduceResponse(params, expected_cql)

    def test_boolean_missing_height(self):
        params = {'missing_height' : 'True'}
        expected_cql = "(height IS NULL OR height = 0)"
        self.assertParamsProduceResponse(params, expected_cql)

    def test_boolean_missing_species_and_height(self):
        params = {'missing_species' : 'True', 'missing_height' : 'True'}
        expected_cql =  "species_id IS NULL AND (height IS NULL OR height = 0)"
        self.assertParamsProduceResponse(params, expected_cql)

    def test_matching_tree_owner(self):
        params = {'tree_owner' : 'John Doe'}
        expected_cql =  "tree_owner LIKE '%John Doe%'"
        self.assertParamsProduceResponse(params, expected_cql)


