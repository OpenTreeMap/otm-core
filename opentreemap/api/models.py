from django.contrib.gis.db import models
from treemap.models import User

API_KEY_IOS = 1
API_KEY_ANDROID = 2

class APIKey(models.Model):
    user = models.ForeignKey(User, null=True)
    special = models.IntegerField(null=True)
    key = models.CharField(max_length=50)
    enabled = models.BooleanField(default=True)
    comment = models.TextField()

class APILog(models.Model):
    url = models.TextField()
    method = models.CharField(max_length=20)
    requestvars = models.TextField()
    apikey = models.ForeignKey(APIKey)
    remoteip = models.CharField(max_length=20)
    useragent = models.CharField(max_length=255)
    appver = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now=True)
