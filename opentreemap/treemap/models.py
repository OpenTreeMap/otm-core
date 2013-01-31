from django.contrib.gis.db import models

class Instance(models.Model):
    """
    Each "Tree Map" is a single instance
    """
    name = models.CharField(max_length=255)

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

    objects = models.GeoManager()

    @property
    def geo_rev_hash(self):
        import hashlib
        return hashlib.md5(str(self.geo_rev)).hexdigest()

    @property
    def center_lat_lng(self):
        return self.center.transform(4326,clone=True)

class Tree(models.Model):
    """
    Represents a single tree, belonging to an instance
    """
    geom = models.PointField(srid=3857, db_column='the_geom_webmercator')
    instance = models.ForeignKey(Instance)

    objects = models.GeoManager()
