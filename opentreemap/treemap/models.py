# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import hashlib
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.gis.db import models
from django.contrib.gis.measure import D
from django.db import IntegrityError
from django.utils import timezone
from django.utils.translation import ugettext_lazy as trans

from django.contrib.auth.models import AbstractUser

from treemap.audit import (Auditable, Authorizable, FieldPermission, Role,
                           Dictable, Audit, AuthorizableQuerySet,
                           AuthorizableManager)
from treemap.util import save_uploaded_image
from treemap.units import Convertible
from treemap.udf import UDFModel, GeoHStoreUDFManager, GeoHStoreUDFQuerySet
from treemap.instance import Instance


def _action_format_string_for_location(action):
    """A helper that allows multiple auditable models to return the
    same action format string for a field value that should be displayed
    as a location"""
    lang = {
        Audit.Type.Insert: trans('set the location'),
        Audit.Type.Update: trans('updated the location'),
        Audit.Type.Delete: trans('deleted the location'),
        Audit.Type.PendingApprove: trans('approved an '
                                         'edit of the location'),
        Audit.Type.PendingReject: trans('rejected an '
                                        'edit of the location')
    }
    return lang[action]


def _action_format_string_for_readonly(action, readonly):
    """A helper that allows multiple auditable models to return the
    the state of a readonly boolean"""
    if readonly:
        value = trans("read only")
    else:
        value = trans("editable")
    lang = {
        Audit.Type.Insert: trans('made the tree %(value)s'),
        Audit.Type.Update: trans('made the tree %(value)s'),
        Audit.Type.Delete: trans('made the tree %(value)s'),
        Audit.Type.PendingApprove: trans('approved making the tree '
                                         '%(value)s'),
        Audit.Type.PendingReject: trans('approved making the tree '
                                        '%(value)s')
    }
    return lang[action] % {'value': value}


class AuthorizableGeoHStoreUDFQuerySet(AuthorizableQuerySet,
                                       GeoHStoreUDFQuerySet):
    pass


class AuthorizableGeoHStoreUDFManager(AuthorizableManager,
                                      GeoHStoreUDFManager):
    def get_query_set(self):
        return AuthorizableGeoHStoreUDFQuerySet(self.model,
                                                using=self._db)


class BenefitCurrencyConversion(Dictable, models.Model):
    """
    These conversion factors are used to convert a unit of benefit
    into a currency unit.

    While there is currently a 1-to-1 relationship between a given
    benefit currency conversion and an instance, this provides an
    easy way to note that there is no conversion available (setting
    the FK to None). It also provides a mechanism for naming different
    conversions or working with geography in the future
    """

    """
    Symbol to display ($,£, etc)
    """
    currency_symbol = models.CharField(max_length=5)

    kwh_to_currency = models.FloatField()
    stormwater_gal_to_currency = models.FloatField()
    carbon_dioxide_lb_to_currency = models.FloatField()

    """
    Air quality is currently a mixture of:
    NOx, PM10, SOx, VOC and BVOX so this conversion
    should try to assign an aggregate (weighted) conversion
    factor.
    """
    airquality_aggregate_lb_to_currency = models.FloatField()

    def clean(self):
        errors = {}

        if len(self.currency_symbol) > 4:
            errors['currency_symbol'] = trans(
                'Symbol is too long')

        positive_fields = ['kwh_to_currency',
                           'airquality_aggregate_lb_to_currency',
                           'carbon_dioxide_lb_to_currency',
                           'stormwater_gal_to_currency']

        for field in positive_fields:
            value = getattr(self, field)
            try:
                value = float(value or '')
                if value < 0:
                    errors[field] = [trans('Values must be not be negative')]
            except ValueError:
                pass

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()

        super(BenefitCurrencyConversion, self).save(*args, **kwargs)


class User(Auditable, AbstractUser):
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

    def get_instance_user(self, instance):
        qs = InstanceUser.objects.filter(user=self, instance=instance)
        if qs.count() == 1:
            return qs[0]
        elif qs.count() == 0:
            return None
        else:
            msg = ("User '%s' found more than once in instance '%s'"
                   % (self, instance))
            raise IntegrityError(msg)

    def get_instance_permissions(self, instance, model_name=None):
        role = self.get_role(instance)
        perms = FieldPermission.objects.filter(role=role)
        if model_name:
            perms = perms.filter(model_name=model_name)
        return perms

    def get_role(self, instance):
        iuser = self.get_instance_user(instance)
        role = iuser.role if iuser else instance.default_role
        return role

    def get_reputation(self, instance):
        iuser = self.get_instance_user(instance)
        reputation = iuser.reputation if iuser else 0
        return reputation

    def clean(self):
        if re.search('\\s', self.username):
            raise ValidationError('Cannot have spaces in a username')

    def save(self, *args, **kwargs):
        self.full_clean()

        self.email = self.email.lower()

        system_user = User.system_user()
        self.save_with_user(system_user, *args, **kwargs)

# dynamically modify User.email to be unique, instead of
# inheriting and overriding AbstractBaseUser and PermissionMixin
email_field, _, _, _ = User._meta.get_field_by_name('email')
email_field._unique = True


class Species(UDFModel, Authorizable, Auditable):
    """
    http://plants.usda.gov/adv_search.html
    """
    ### Base required info
    instance = models.ForeignKey(Instance)
    # ``otm_code`` is the key used to link this instance
    # species row to a cannonical species. An otm_code
    # is usually the USDA code, but this is not guaranteed.
    otm_code = models.CharField(max_length=255)
    common_name = models.CharField(max_length=255)
    genus = models.CharField(max_length=255)
    species = models.CharField(max_length=255, null=True, blank=True)
    cultivar = models.CharField(max_length=255, null=True, blank=True)
    other = models.CharField(max_length=255, null=True, blank=True)

    ### Copied from original OTM ###
    native_status = models.NullBooleanField()
    gender = models.CharField(max_length=50, null=True, blank=True)
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

    objects = AuthorizableGeoHStoreUDFManager()

    @property
    def display_name(self):
        return "%s [%s]" % (self.common_name, self.scientific_name)

    @property
    def scientific_name(self):
        name = self.genus
        if self.species:
            name += " " + self.species
        if self.cultivar:
            name += " '%s'" % self.cultivar
        return name

    def __unicode__(self):
        return self.display_name

    class Meta:
        verbose_name_plural = "Species"


class InstanceUser(Auditable, models.Model):
    instance = models.ForeignKey(Instance)
    user = models.ForeignKey(User)
    role = models.ForeignKey(Role)
    reputation = models.IntegerField(default=0)
    admin = models.BooleanField(default=False)

    def can_add_photos_to_tree(self):
        # Users can add photos only if they have all
        # WRITE_DIRECTLY or WRITE_WITH_AUDIT permissions
        # on tree photo
        fields = {'tree', 'image', 'thumbnail', 'id'}

        perms = self.user.get_instance_permissions(
            self.instance, 'TreePhoto')

        fieldperms = {perm.field_name
                      for perm
                      in perms
                      if perm.allows_writes}

        return fieldperms == fields

    def save_with_user(self, user):
        self.full_clean()
        super(InstanceUser, self).save_with_user(user)

    def __unicode__(self):
        return '%s/%s' % (self.user.get_username(), self.instance.name)


class ImportEvent(models.Model):
    imported_by = models.ForeignKey(User)
    imported_on = models.DateField(auto_now_add=True)

    def __unicode__(self):
        return "%s - %s" % (self.imported_by, self.imported_on)


#TODO:
# Exclusion Zones
# Proximity validation
# UDFModel overrides implementations of methods in
# authorizable and auditable, thus needs to be inherited first
class Plot(Convertible, UDFModel, Authorizable, Auditable):
    instance = models.ForeignKey(Instance)
    geom = models.PointField(srid=3857, db_column='the_geom_webmercator')

    width = models.FloatField(null=True, blank=True,
                              help_text=trans("Plot Width"))
    length = models.FloatField(null=True, blank=True,
                               help_text=trans("Plot Length"))

    address_street = models.CharField(max_length=255, blank=True, null=True)
    address_city = models.CharField(max_length=255, blank=True, null=True)
    address_zip = models.CharField(max_length=30, blank=True, null=True)

    import_event = models.ForeignKey(ImportEvent, null=True, blank=True)
    owner_orig_id = models.CharField(max_length=255, null=True, blank=True)
    readonly = models.BooleanField(default=False)

    objects = AuthorizableGeoHStoreUDFManager()

    def nearby_plots(self, distance_in_meters=None):
        if distance_in_meters is None:
            distance_in_meters = settings.NEARBY_TREE_DISTANCE

        distance_filter = Plot.objects.filter(
            geom__distance_lte=(self.geom, D(m=distance_in_meters)))

        return distance_filter\
            .filter(instance=self.instance)\
            .exclude(pk=self.pk)

    def get_tree_history(self):
        """
        Get a list of all tree ids that were ever assigned
        to this plot
        """
        return Audit.objects.filter(instance=self.instance)\
                            .filter(model='Tree')\
                            .filter(field='plot')\
                            .filter(current_value=self.pk)\
                            .order_by('-model_id', '-updated')\
                            .distinct('model_id')\
                            .values_list('model_id', flat=True)

    def save_with_user(self, user, *args, **kwargs):
        self.full_clean_with_user(user)

        super(Plot, self).save_with_user(user, *args, **kwargs)

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
        x_chunk = "X: %s" % self.geom.x if self.geom else "?"
        y_chunk = "Y: %s" % self.geom.y if self.geom else "?"
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

    @classmethod
    def action_format_string_for_audit(clz, audit):
        if audit.field in set(['geom', 'readonly']):
            if audit.field == 'geom':
                return _action_format_string_for_location(audit.action)
            else:  # field == 'readonly'
                return _action_format_string_for_readonly(
                    audit.action,
                    audit.clean_current_value)
        else:
            return super(Plot, clz).action_format_string_for_audit(audit)


# UDFModel overrides implementations of methods in
# authorizable and auditable, thus needs to be inherited first
class Tree(Convertible, UDFModel, Authorizable, Auditable):
    """
    Represents a single tree, belonging to an instance
    """
    instance = models.ForeignKey(Instance)

    plot = models.ForeignKey(Plot)
    species = models.ForeignKey(Species, null=True, blank=True)
    import_event = models.ForeignKey(ImportEvent, null=True, blank=True)

    readonly = models.BooleanField(default=False)
    diameter = models.FloatField(null=True, blank=True,
                                 help_text=trans("Tree Diameter"))
    height = models.FloatField(null=True, blank=True,
                               help_text=trans("Tree Height"))
    canopy_height = models.FloatField(null=True, blank=True,
                                      help_text=trans("Canopy Height"))
    date_planted = models.DateField(null=True, blank=True,
                                    help_text=trans("Date Planted"))
    date_removed = models.DateField(null=True, blank=True,
                                    help_text=trans("Date Removed"))

    objects = AuthorizableGeoHStoreUDFManager()

    def __unicode__(self):
        diameter_chunk = ("Diameter: %s, " % self.diameter
                          if self.diameter else "")
        species_chunk = ("Species: %s - " % self.species
                         if self.species else "")
        return "%s%s" % (diameter_chunk, species_chunk)

    def most_recent_photo(self):
        try:
            return self.treephoto_set.order_by('-created_at')[0]
        except IndexError:
            return None

    ##########################
    # tree validation
    ##########################

    def clean(self):
        super(Tree, self).clean()
        if self.plot and self.plot.instance != self.instance:
            raise ValidationError('Cannot save to a plot in another instance')

    def save_with_user(self, user, *args, **kwargs):
        self.full_clean_with_user(user)
        super(Tree, self).save_with_user(user, *args, **kwargs)

    @property
    def hash(self):
        string_to_hash = super(Tree, self).hash

        # We need to include tree photos in this hash as well
        photos = [str(photo.pk) for photo in self.treephoto_set.all()]
        string_to_hash += ":" + ",".join(photos)

        return hashlib.md5(string_to_hash).hexdigest()

    def add_photo(self, image, user):
        tp = TreePhoto(tree=self, instance=self.instance)
        tp.set_image(image)
        tp.save_with_user(user)
        return tp

    @classmethod
    def action_format_string_for_audit(clz, audit):
        if audit.field in set(['plot', 'readonly']):
            if audit.field == 'plot':
                return _action_format_string_for_location(audit.action)
            else:  # audit.field == 'readonly'
                return _action_format_string_for_readonly(
                    audit.action, audit.clean_current_value)
        else:
            return super(Tree, clz).action_format_string_for_audit(audit)


class TreePhoto(models.Model, Authorizable, Auditable):
    tree = models.ForeignKey(Tree)

    image = models.ImageField(
        upload_to='trees/%Y/%m/%d', editable=False)
    thumbnail = models.ImageField(
        upload_to='trees_thumbs/%Y/%m/%d', editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    instance = models.ForeignKey(Instance)

    def __init__(self, *args, **kwargs):
        super(TreePhoto, self).__init__(*args, **kwargs)
        self._do_not_track.add('created_at')
        self.populate_previous_state()

    def _get_db_prep_for_image(self, field):
        """
        Images are stored in various ways based on the storage backend
        but they all get serialized to a text field. For auditing, we
        store this value
        """
        thing = getattr(self, field)

        if thing is None:
            return None

        field, _, _, _ = TreePhoto._meta.get_field_by_name(field)

        saved_rep = field.pre_save(self, thing)
        return str(saved_rep)

    def as_dict(self):
        data = super(TreePhoto, self).as_dict()

        data['image'] = self._get_db_prep_for_image('image')
        data['thumbnail'] = self._get_db_prep_for_image('thumbnail')

        return data

    def set_image(self, image_data):
        name_prefix = "%s-%s" % (self.tree.plot.pk, self.tree.pk)
        self.image, self.thumbnail = save_uploaded_image(
            image_data, name_prefix, thumb_size=(256, 256))

    def save_with_user(self, *args, **kwargs):
        if not self.thumbnail.name:
            raise Exception('You need to call set_image instead')
        if self.tree and self.tree.instance != self.instance:
            raise ValidationError('Cannot save to a tree in another instance')

        # The auto_now_add is acting up... set if here if we're new
        if self.pk is None:
            self.created_at = timezone.now()

        super(TreePhoto, self).save_with_user(*args, **kwargs)

    def delete_with_user(self, *args, **kwargs):
        thumb = self.thumbnail
        image = self.image

        super(TreePhoto, self).delete_with_user(*args, **kwargs)

        thumb.delete(False)
        image.delete(False)


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
