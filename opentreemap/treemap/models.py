from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.gis.db import models
from treemap.audit import Auditable, Audit
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    pass

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

class Species(models.Model):
    """
    http://plants.usda.gov/adv_search.html
    """
    ### Base required info
    symbol = models.CharField(max_length=255)
    genus = models.CharField(max_length=255)
    species = models.CharField(max_length=255, null=True, blank=True)
    cultivar_name = models.CharField(max_length=255, null=True, blank=True)
    gender = models.CharField(max_length=50, null=True, blank=True)
    common_name = models.CharField(max_length=255, null=True, blank=True)

    ### Copied from original OTM ###
    native_status = models.CharField(max_length=255, null=True, blank=True)
    bloom_period = models.CharField(max_length=255, null=True, blank=True)
    fruit_period = models.CharField(max_length=255, null=True, blank=True)
    fall_conspicuous = models.NullBooleanField()
    flower_conspicuous = models.NullBooleanField()
    palatable_human = models.NullBooleanField()
    wildlife_value = models.NullBooleanField()

    fact_sheet = models.URLField(max_length=255, null=True, blank=True)
    plant_guide = models.URLField(max_length=255, null=True, blank=True)

    ### Used for validation
    max_dbh = models.IntegerField(default=200)
    max_height = models.IntegerField(default=800)

    objects = models.GeoManager()

    @property
    def scientific_name(self):
        name = self.genus
        if self.species:
            name += " " + species
        if self.cultivar:
            name += " '%s'" % self.cultivar

class InstanceSpecies(Auditable, models.Model):
    instance = models.ForeignKey(Instance)
    species = models.ForeignKey(Species)
    common_name = models.CharField(max_length=255, null=True, blank=True)

class ImportEvent(models.Model):
    imported_by = models.ForeignKey(User)
    imported_on = models.DateField(auto_now_add=True)

#TODO:
# Exclusion Zones
# Proximity validation
class Plot(Auditable, models.Model):
    instance = models.ForeignKey(Instance)
    geom = models.PointField(srid=3857, db_column='the_geom_webmercator')

    width = models.FloatField(null=True, blank=True)
    length = models.FloatField(null=True, blank=True)

    address_street = models.CharField(max_length=255, blank=True, null=True)
    address_city = models.CharField(max_length=255, blank=True, null=True)
    address_zip = models.CharField(max_length=30,blank=True, null=True)

    import_event = models.ForeignKey(ImportEvent, null=True, blank=True)
    created_by = models.ForeignKey(User)
    owner_orig_id = models.CharField(max_length=255, null=True, blank=True)
    readonly = models.BooleanField(default=False)

    objects = models.GeoManager()

    @property
    def zones(self):
        if self.geom:
            return BoundaryZones.objects\
                                .filter(geom__contains=self.goem)\
                                .order('sort_order')
        else:
            return []

class Tree(Auditable, models.Model):
    """
    Represents a single tree, belonging to an instance
    """
    instance = models.ForeignKey(Instance)

    plot = models.ForeignKey(Plot)
    species = models.ForeignKey(Species,null=True,blank=True)
    created_by = models.ForeignKey(User)
    import_event = models.ForeignKey(ImportEvent,null=True,blank=True)

    readonly = models.BooleanField(default=False)
    diameter = models.FloatField(null=True, blank=True)
    height = models.FloatField(null=True, blank=True)
    canopy_height = models.FloatField(null=True, blank=True)
    date_planted = models.DateField(null=True, blank=True)
    date_removed = models.DateField(null=True, blank=True)

    objects = models.GeoManager()

class BoundaryZones(models.Model):
    """
    A plot can belong to many different boundary zones. Boundary zones are
    always sorted by 'sort_order' before displaying. An example output
    for a given tree could be:
    { name } ({category}, {sort order})
    +- United States (Country, 0)
     +- Pennsylvania (State, 1)
      +- Philadelphia (County, 2)
       +- Philadelphia (City, 3)
        +- 19107 (Zip Code, 4)
        +- Callowhill (Neighborhood, 4)
    """
    geom = models.MultiPolygonField(srid=3857)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=255)
    sort_order = models.IntegerField()

    objects = models.GeoManager()
