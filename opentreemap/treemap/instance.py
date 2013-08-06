from django.contrib.gis.db import models

class Instance(models.Model):
    """
    Each "Tree Map" is a single instance
    """
    name = models.CharField(max_length=255)

    """
    Basemap type     Basemap data
    ------------     -----------------
    Google           Google_API_Key
    Bing             Bing_API_Key
    TMS              TMS URL with {x},{y},{z}
    """
    basemap_type = models.CharField(max_length=255,
                                    choices=(("google", "Google"),
                                             ("bing", "Bing"),
                                             ("tms", "Tile Map Service")),
                                    default="google")
    basemap_data = models.CharField(max_length=255, null=True, blank=True)

    """
    The current database revision for the instance

    This revision is used to determine if tiles should be cached.
    In particular, the revision has *no* effect on the actual
    data.

    Generally we make tile requests like:
    http://tileserver/tile/{layer}/{rev}/{Z}/{Y}/{X}

    There is a database trigger that updates the
    revision whenever an edit to a geometry field is made
    so you don't have to worry about it.

    You should *not* edit this field.
    """
    geo_rev = models.IntegerField(default=1)

    """ Center of the map when loading the instance """
    center = models.PointField(srid=3857)

    default_role = models.ForeignKey('Role', related_name='default_role')

    boundaries = models.ManyToManyField('Boundary', null=True, blank=True)

    objects = models.GeoManager()

    def __unicode__(self):
        return self.name

    @property
    def geo_rev_hash(self):
        return hashlib.md5(str(self.geo_rev)).hexdigest()

    @property
    def center_lat_lng(self):
        return self.center.transform(4326, clone=True)

    def scope_model(self, model):
        qs = model.objects.filter(instance=self)
        return qs
