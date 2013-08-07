from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.gis.db import models
from django.db import IntegrityError

from django.contrib.auth.models import AbstractUser

from treemap.audit import Auditable, Authorizable, FieldPermission, Role

import hashlib
import re

from treemap.udf import UDFModel, GeoHStoreManager
from treemap.instance import Instance


class User(Auditable, AbstractUser):
    roles = models.ManyToManyField(Role, blank=True, null=True)
    reputation = models.IntegerField(default=0)

    _system_user = None

    @classmethod
    def system_user(clazz):
        if not User._system_user:
            try:
                User._system_user = User.objects.get(
                    pk=settings.SYSTEM_USER_ID)

            except User.DoesNotExist:
                raise Exception('System user does not exist. You may '
                                'want to run `manage.py create_system_user`')

        return User._system_user

    def get_instance_permissions(self, instance, model_name=None):
        roles = self.roles.filter(instance=instance)

        if len(roles) > 1:
            error_message = ("%s cannot have more than one role per"
                             " instance. Something might be very "
                             "wrong with your database configuration." %
                             self.username)
            raise IntegrityError(error_message)

        elif len(roles) == 1:
            perms = FieldPermission.objects.filter(role=roles[0])
        else:
            perms = FieldPermission.objects.filter(role=instance.default_role)

        if model_name:
            perms = perms.filter(model_name=model_name)

        return perms

    def clean(self):
        if re.search('\\s', self.username):
            raise ValidationError('Cannot have spaces in a username')

    def save(self):
        self.full_clean()

        system_user = User.system_user()
        self.save_with_user(system_user)


class Species(models.Model):
    """
    http://plants.usda.gov/adv_search.html
    """
    ### Base required info
    symbol = models.CharField(max_length=255)
    common_name = models.CharField(max_length=255)
    genus = models.CharField(max_length=255)
    species = models.CharField(max_length=255, null=True, blank=True)
    cultivar_name = models.CharField(max_length=255, null=True, blank=True)
    gender = models.CharField(max_length=50, null=True, blank=True)

    ### Copied from original OTM ###
    native_status = models.CharField(max_length=255, null=True, blank=True)
    bloom_period = models.CharField(max_length=255, null=True, blank=True)
    fruit_period = models.CharField(max_length=255, null=True, blank=True)
    fall_conspicuous = models.NullBooleanField()
    flower_conspicuous = models.NullBooleanField()
    palatable_human = models.NullBooleanField()
    wildlife_value = models.NullBooleanField()

    itree_code = models.CharField(max_length=255, null=True, blank=True)

    fact_sheet = models.URLField(max_length=255, null=True, blank=True)
    plant_guide = models.URLField(max_length=255, null=True, blank=True)

    ### Used for validation
    max_dbh = models.IntegerField(default=200)
    max_height = models.IntegerField(default=800)

    objects = models.GeoManager()

    @property
    def display_name(self):
        return "%s [%s]" % (self.common_name, self.scientific_name)

    @property
    def scientific_name(self):
        name = self.genus
        if self.species:
            name += " " + self.species
        if self.cultivar_name:
            name += " '%s'" % self.cultivar_name
        return name

    def __unicode__(self):
        return self.display_name

    class Meta:
        verbose_name_plural = "Species"


class InstanceSpecies(Auditable, models.Model):
    instance = models.ForeignKey(Instance)
    species = models.ForeignKey(Species)
    common_name = models.CharField(max_length=255, null=True, blank=True)

    def __unicode__(self):
        return self.common_name


class ImportEvent(models.Model):
    imported_by = models.ForeignKey(User)
    imported_on = models.DateField(auto_now_add=True)

    def __unicode__(self):
        return "%s - %s" % (self.imported_by, self.imported_on)


#TODO:
# Exclusion Zones
# Proximity validation
class Plot(Authorizable, Auditable, UDFModel):
    instance = models.ForeignKey(Instance)
    geom = models.PointField(srid=3857, db_column='the_geom_webmercator')

    width = models.FloatField(null=True, blank=True)
    length = models.FloatField(null=True, blank=True)

    address_street = models.CharField(max_length=255, blank=True, null=True)
    address_city = models.CharField(max_length=255, blank=True, null=True)
    address_zip = models.CharField(max_length=30, blank=True, null=True)

    import_event = models.ForeignKey(ImportEvent, null=True, blank=True)
    owner_orig_id = models.CharField(max_length=255, null=True, blank=True)
    readonly = models.BooleanField(default=False)

    objects = GeoHStoreManager()

    def current_tree(self):
        """
        This is a compatibility method that is used by the API to
        select the 'current tree'. Right now OTM only supports one
        tree per plot, so this method returns the 'first' tree
        """
        trees = list(self.tree_set.all())
        if trees:
            return trees[0]
        else:
            return None

    def __unicode__(self):
        x_chunk = "X: %s" % self.geom.x
        y_chunk = "Y: %s" % self.geom.y
        address_chunk = self.address_street or "No Address Provided"
        return "%s, %s - %s" % (x_chunk, y_chunk, address_chunk)

    @property
    def hash(self):
        string_to_hash = super(Plot, self).hash

        # The hash state for a given plot also includes the hash
        # state for all of the trees on it as well
        tree_hashes = [t.hash for t in self.tree_set.all()]
        string_to_hash += "," + ",".join(tree_hashes)

        return hashlib.md5(string_to_hash).hexdigest()

    @property
    def address_full(self):
        components = []
        if self.address_street:
            components.append(self.address_street)
        if self.address_city:
            components.append(self.address_city)
        if self.address_zip:
            components.append(self.address_zip)
        return ', '.join(components)


class Tree(Authorizable, Auditable, UDFModel):
    """
    Represents a single tree, belonging to an instance
    """
    instance = models.ForeignKey(Instance)

    plot = models.ForeignKey(Plot)
    species = models.ForeignKey(Species, null=True, blank=True)
    import_event = models.ForeignKey(ImportEvent, null=True, blank=True)

    readonly = models.BooleanField(default=False)
    diameter = models.FloatField(null=True, blank=True)
    height = models.FloatField(null=True, blank=True)
    canopy_height = models.FloatField(null=True, blank=True)
    date_planted = models.DateField(null=True, blank=True)
    date_removed = models.DateField(null=True, blank=True)

    objects = GeoHStoreManager()

    def __unicode__(self):
        diameter_chunk = ("Diameter: %s, " % self.diameter
                          if self.diameter else "")
        species_chunk = ("Species: %s - " % self.species
                         if self.species else "")
        return "%s%s" % (diameter_chunk, species_chunk)

    ##########################
    # tree validation
    ##########################

    def clean(self):
        if self.plot and self.plot.instance != self.instance:
            raise ValidationError('Cannot save to a plot in another instance')

    def save_with_user(self, user, *args, **kwargs):
        self.full_clean()
        super(Tree, self).save_with_user(user, *args, **kwargs)


class Boundary(models.Model):
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
    geom = models.MultiPolygonField(srid=3857,
                                    db_column='the_geom_webmercator')

    name = models.CharField(max_length=255)
    category = models.CharField(max_length=255)
    sort_order = models.IntegerField()

    objects = models.GeoManager()

    def __unicode__(self):
        return self.name
