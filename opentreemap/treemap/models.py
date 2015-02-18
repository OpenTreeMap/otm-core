# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


import hashlib
import re

from django.conf import settings
from django.core.mail import send_mail
from django.core.exceptions import (ValidationError, MultipleObjectsReturned,
                                    ObjectDoesNotExist)
from django.core import validators
from django.http import Http404
from django.contrib.gis.db import models
from django.contrib.gis.measure import D
from django.db import IntegrityError, transaction
from django.db.models.signals import post_save, post_delete
from django.utils import timezone
from django.utils.translation import ugettext_lazy as trans
from django.contrib.auth.models import (UserManager, AbstractBaseUser,
                                        PermissionsMixin)

from treemap.species.codes import ITREE_REGIONS, get_itree_code
from treemap.audit import Auditable, Role, Dictable, Audit, PendingAuditable
# Import this even though it's not referenced, so Django can find it
from treemap.audit import FieldPermission  # NOQA
from treemap.util import leaf_subclasses, to_object_name
from treemap.decorators import classproperty
from treemap.images import save_uploaded_image
from treemap.units import Convertible
from treemap.udf import UDFModel, GeoHStoreUDFManager
from treemap.instance import Instance
from treemap.lib.object_caches import invalidate_adjuncts


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


class StaticPage(models.Model):
    instance = models.ForeignKey(Instance)
    name = models.CharField(max_length=100)
    content = models.TextField()

    @staticmethod
    def built_in_names():
        return ['Resources', 'FAQ', 'About', 'Partners']

    @staticmethod
    def get_or_new(instance, page_name, only_create_built_ins=True):
        '''
        If static page exists, return it;
        otherwise construct one (without saving).
        Make sure the returned object's name is cased correctly
        if it matches an existing object name or built-in name.
        '''
        try:
            static_page = StaticPage.objects.get(name__iexact=page_name,
                                                 instance=instance)
        except StaticPage.DoesNotExist:
            built_in_name = StaticPage._get_built_in_name(page_name)
            if built_in_name:
                page_name = built_in_name
            elif only_create_built_ins:
                raise Http404('Static page does not exist')

            static_page = StaticPage(
                instance=instance, name=page_name,
                content=trans('There is no content for this page yet.'))
        return static_page

    @staticmethod
    def _get_built_in_name(page_name):
        page_name_lower = page_name.lower()
        for name in StaticPage.built_in_names():
            if page_name_lower == name.lower():
                return name
        return None

    def __unicode__(self):
        return self.name


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

    # Energy conversions
    electricity_kwh_to_currency = models.FloatField()
    natural_gas_kbtu_to_currency = models.FloatField()
    # Stormwater conversions
    h20_gal_to_currency = models.FloatField()
    # CO₂ conversions
    co2_lb_to_currency = models.FloatField()
    # Air quality conversions
    o3_lb_to_currency = models.FloatField()
    nox_lb_to_currency = models.FloatField()
    pm10_lb_to_currency = models.FloatField()
    sox_lb_to_currency = models.FloatField()
    voc_lb_to_currency = models.FloatField()

    def clean(self):
        errors = {}

        if len(self.currency_symbol) > 4:
            errors['currency_symbol'] = trans(
                'Symbol is too long')

        positive_fields = ['electricity_kwh_to_currency',
                           'natural_gas_kbtu_to_currency',
                           'h20_gal_to_currency',
                           'co2_lb_to_currency',
                           'o3_lb_to_currency',
                           'nox_lb_to_currency',
                           'pm10_lb_to_currency',
                           'sox_lb_to_currency',
                           'voc_lb_to_currency']

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

    def get_factor_conversions_config(self):
        return {
            'electricity': self.electricity_kwh_to_currency,
            'natural_gas': self.natural_gas_kbtu_to_currency,
            'hydro_interception': self.h20_gal_to_currency,
            'co2_sequestered': self.co2_lb_to_currency,
            'co2_avoided': self.co2_lb_to_currency,
            'co2_storage': self.co2_lb_to_currency,
            'aq_ozone_dep': self.o3_lb_to_currency,
            'aq_nox_dep': self.nox_lb_to_currency,
            'aq_nox_avoided': self.nox_lb_to_currency,
            'aq_pm10_dep': self.pm10_lb_to_currency,
            'aq_sox_dep': self.sox_lb_to_currency,
            'aq_sox_avoided': self.sox_lb_to_currency,
            'aq_voc_avoided': self.voc_lb_to_currency
            # TODO It is unclear if the 'bvoc' factor uses the 'VOC' costs
            # Leaving it alone for now, as it seems better to incorrectly have
            # lower eco-benefit money saved than higher.
        }

    @classmethod
    def get_default_for_point(cls, point):
        """
        Returns a new BenefitCurrencyConversion for the i-Tree region that
        contains the given point.
        """
        regions_covered = ITreeRegion.objects.filter(geometry__contains=point)

        if len(regions_covered) > 1:
            raise MultipleObjectsReturned(
                "There should not be overlapping i-Tree regions")
        elif len(regions_covered) == 0:
            return None

        region_code = regions_covered[0].code

        return cls.get_default_for_region(region_code)

    @classmethod
    def get_default_for_region(cls, region_code):
        """
        Returns a new BenefitCurrencyConversion for the given i-Tree region
        """
        config = ITREE_REGIONS.get(region_code, {})\
                              .get('currency_conversion')
        if config:
            benefits_conversion = cls()
            benefits_conversion.currency_symbol = '$'
            for field, conversion in config.iteritems():
                setattr(benefits_conversion, field, conversion)
            return benefits_conversion
        else:
            return None


# This is copy and pasted with syntax mods from the source for `AbstractUser`
# from the django source code, which is suboptimal. This was done because you
# can't have your cake and eat it too: inheriting AbstractUser but modifying
# one of the core fields.
#
# This code caused failures in gunicorn but not django runserver or tests:
#
# # dynamically modify User.email to be unique, instead of
# # inheriting and overriding AbstractBaseUser and PermissionMixin
# email_field, _, _, _ = User._meta.get_field_by_name('email')
# email_field._unique = True
#
# TODO: Fix this abstraction, and/or prune out parts of this class that
# are not needed, and merge with the User class.
#
# see the following code sample for the original `AbstractUser` source
# https://raw.github.com/django/django/53c7d66869636a6cf2b8c03c4de01ddff16f9892/django/contrib/auth/models.py  # NOQA
class AbstractUniqueEmailUser(AbstractBaseUser, PermissionsMixin):
    """
    An abstract base class implementing a fully featured User model with
    admin-compliant permissions.

    Username, password and email are required. Other fields are optional.
    """
    username = models.CharField(
        trans('username'), max_length=30, unique=True,
        help_text=trans(
            'Required. 30 characters or fewer. Letters, numbers and '
            '@/./+/-/_ characters'),
        validators=[
            validators.RegexValidator(
                re.compile('^[\w.@+-]+$'),
                trans('Enter a valid username.'), 'invalid')
        ])
    email = models.EmailField(trans('email address'), blank=True, unique=True)
    is_staff = models.BooleanField(
        trans('staff status'), default=False,
        help_text=trans('Designates whether the user can log into this admin '
                        'site.'))
    is_active = models.BooleanField(
        trans('active'), default=True,
        help_text=trans('Designates whether this user should be treated as '
                        'active. Unselect this instead of deleting accounts.'))
    date_joined = models.DateTimeField(trans('date joined'),
                                       default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        verbose_name = trans('user')
        verbose_name_plural = trans('users')
        abstract = True

    def get_full_name(self):
        """
        Returns the first_name plus the last_name, with a space in between.
        """
        full_name = '%s %s' % (self.get_first_name(), self.get_last_name())
        return full_name.strip()

    def get_short_name(self):
        "Returns the short name for the user."
        return self.get_first_name()

    def email_user(self, subject, message, from_email=None, **kwargs):
        """
        Sends an email to this User.
        """
        send_mail(subject, message, from_email, [self.email], **kwargs)


class User(AbstractUniqueEmailUser, Auditable):
    _system_user = None

    photo = models.ImageField(upload_to='users', null=True, blank=True)
    thumbnail = models.ImageField(upload_to='users', null=True, blank=True)
    first_name = models.CharField(
        trans('first name'), max_length=30, default='', blank=True)
    last_name = models.CharField(
        trans('last name'), max_length=30, default='', blank=True)
    organization = models.CharField(max_length=255, default='', blank=True)

    make_info_public = models.BooleanField(default=False)
    allow_email_contact = models.BooleanField(default=False)

    @classmethod
    def system_user(clazz):
        if not User._system_user:
            try:
                User._system_user = User.objects.get(
                    pk=settings.SYSTEM_USER_ID)

            except User.DoesNotExist:
                raise User.DoesNotExist('System user does not exist. You may '
                                        'want to run '
                                        '`manage.py create_system_user`')

        return User._system_user

    @property
    def created(self):
        try:
            return Audit.objects.filter(instance=None,
                                        model='User',
                                        model_id=self.pk)\
                                .order_by('created')[0]\
                                .created
        except IndexError:
            # A user has no audit records?
            return None

    @property
    def email_hash(self):
        return hashlib.sha512(self.email).hexdigest()

    def dict(self):
        return {'id': self.pk,
                'username': self.username}

    def get_first_name(self):
        return self.first_name if self.make_info_public else ''

    def get_last_name(self):
        return self.last_name if self.make_info_public else ''

    def get_organization(self):
        return self.organization if self.make_info_public else ''

    def get_instance_user(self, instance):
        try:
            return InstanceUser.objects.get(user=self, instance=instance)
        except InstanceUser.DoesNotExist:
            return None
        except MultipleObjectsReturned:
            msg = ("User '%s' found more than once in instance '%s'"
                   % (self, instance))
            raise IntegrityError(msg)

    def get_effective_instance_user(self, instance):
        if instance is None:
            return None

        instance_user = self.get_instance_user(instance)
        # If the user has no instance user yet, we need to provide a default so
        # that template filters can determine whether that user can perform an
        # action that will make them into an instance user
        if (instance_user is None
           and instance.feature_enabled('auto_add_instance_user')):
            return InstanceUser(user=self,
                                instance=instance,
                                role=instance.default_role)
        else:
            return instance_user

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
            raise ValidationError(trans('Cannot have spaces in a username'))

    def save_with_user(self, user, *args, **kwargs):
        self.full_clean()
        self.email = self.email.lower()
        super(User, self).save_with_user(user, *args, **kwargs)

    def save(self, *args, **kwargs):
        system_user = User.system_user()
        self.save_with_user(system_user, *args, **kwargs)


class Species(UDFModel, PendingAuditable):
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
    species = models.CharField(max_length=255, blank=True)
    cultivar = models.CharField(max_length=255, blank=True)
    other_part_of_name = models.CharField(max_length=255, blank=True)

    ### From original OTM (some renamed) ###
    is_native = models.NullBooleanField()
    flowering_period = models.CharField(max_length=255, blank=True)
    fruit_or_nut_period = models.CharField(max_length=255, blank=True)
    fall_conspicuous = models.NullBooleanField()
    flower_conspicuous = models.NullBooleanField()
    palatable_human = models.NullBooleanField()
    has_wildlife_value = models.NullBooleanField()
    fact_sheet_url = models.URLField(max_length=255, blank=True)
    plant_guide_url = models.URLField(max_length=255, blank=True)

    ### Used for validation
    max_diameter = models.IntegerField(default=200)
    max_height = models.IntegerField(default=800)

    objects = GeoHStoreUDFManager()

    @property
    def display_name(self):
        return "%s [%s]" % (self.common_name, self.scientific_name)

    @classmethod
    def get_scientific_name(clazz, genus, species, cultivar):
        name = genus
        if species:
            name += " " + species
        if cultivar:
            name += " '%s'" % cultivar
        return name

    @property
    def scientific_name(self):
        return Species.get_scientific_name(self.genus,
                                           self.species,
                                           self.cultivar)

    def dict(self):
        props = self.as_dict()
        props['scientific_name'] = self.scientific_name

        return props

    def get_itree_code(self, region_code=None):
        if not region_code:
            region_codes = self.instance.itree_region_codes()
            if len(region_codes) == 1:
                region_code = region_codes[0]
            else:
                return None
        override = ITreeCodeOverride.objects.filter(
            instance_species=self,
            region=ITreeRegion.objects.get(code=region_code),
            )
        if override.exists():
            return override[0].itree_code
        else:
            return get_itree_code(region_code, self.otm_code)

    def __unicode__(self):
        return self.display_name

    class Meta:
        verbose_name_plural = "Species"
        unique_together = ('instance', 'common_name', 'genus', 'species',
                           'cultivar', 'other_part_of_name',)


class InstanceUser(Auditable, models.Model):
    instance = models.ForeignKey(Instance)
    user = models.ForeignKey(User)
    role = models.ForeignKey(Role)
    reputation = models.IntegerField(default=0)
    admin = models.BooleanField(default=False)

    class Meta:
        unique_together = ('instance', 'user',)

    def save_with_user(self, user, *args, **kwargs):
        self.full_clean()
        super(InstanceUser, self).save_with_user(user, *args, **kwargs)

    def save(self, *args, **kwargs):
        system_user = User.system_user()
        self.save_with_user(system_user, *args, **kwargs)

    def __unicode__(self):
        return '%s/%s' % (self.user.get_username(), self.instance.name)

post_save.connect(invalidate_adjuncts, sender=InstanceUser)
post_delete.connect(invalidate_adjuncts, sender=InstanceUser)


class MapFeature(Convertible, UDFModel, PendingAuditable):
    "Superclass for map feature subclasses like Plot, RainBarrel, etc."
    instance = models.ForeignKey(Instance)
    geom = models.PointField(srid=3857, db_column='the_geom_webmercator')

    address_street = models.CharField(max_length=255, blank=True, null=True)
    address_city = models.CharField(max_length=255, blank=True, null=True)
    address_zip = models.CharField(max_length=30, blank=True, null=True)

    readonly = models.BooleanField(default=False)

    objects = GeoHStoreUDFManager()

    area_field_name = None  # subclass responsibility

    # When querying MapFeatures (as opposed to querying a subclass like Plot),
    # we get a heterogenous collection (some Plots, some RainBarrels, etc.).
    # The feature_type attribute tells us the type of each object.

    feature_type = models.CharField(max_length=255)

    def __init__(self, *args, **kwargs):
        super(MapFeature, self).__init__(*args, **kwargs)
        if self.feature_type == '':
            self.feature_type = self.map_feature_type
        self._do_not_track.add('feature_type')
        self._do_not_track.add('mapfeature_ptr')
        self.populate_previous_state()

    @property
    def _is_generic(self):
        return self.__class__.__name__ == 'MapFeature'

    @classproperty
    def geom_field_name(cls):
        return "%s.geom" % to_object_name(cls.map_feature_type)

    @property
    def is_plot(self):
        return getattr(self, 'feature_type', None) == 'Plot'

    def save_with_user(self, user, *args, **kwargs):
        self.full_clean_with_user(user)

        if self._is_generic:
            raise Exception(
                'Never save a MapFeature -- only save a MapFeature subclass')
        super(MapFeature, self).save_with_user(user, *args, **kwargs)

    def clean(self):
        super(MapFeature, self).clean()

        if not self.instance.bounds.contains(self.geom):
            raise ValidationError({
                "geom": [
                    trans(
                        "%(model)ss must be created inside the map boundaries")
                    % {'model': self.display_name}]
            })

    def photos(self):
        return self.mapfeaturephoto_set.order_by('-created_at')

    def add_photo(self, image, user):
        photo = MapFeaturePhoto(map_feature=self, instance=self.instance)
        photo.set_image(image)
        photo.save_with_user(user)
        return photo

    @classproperty
    def map_feature_type(cls):
        # Map feature type defaults to subclass name (e.g. 'Plot').
        # Subclasses can override it if they want something different.
        # (But note that the value gets stored in the database, so should not
        # be changed for a subclass once objects have been saved.)
        return cls.__name__

    @classproperty
    def display_name(cls):
        # Subclasses should override with something useful
        return cls.map_feature_type

    @classmethod
    def subclass_dict(cls):
        return {C.map_feature_type: C for C in leaf_subclasses(MapFeature)}

    @classmethod
    def has_subclass(cls, type):
        return type in cls.subclass_dict()

    @classmethod
    def get_subclass(cls, type):
        try:
            return cls.subclass_dict()[type]
        except KeyError as e:
            raise ValidationError('Map feature type %s not found' % e)

    @classmethod
    def create(cls, type, instance):
        """
        Create a map feature with the given type string (e.g. 'Plot')
        """
        return cls.get_subclass(type)(instance=instance)

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
            return super(MapFeature, clz).action_format_string_for_audit(audit)

    @property
    def hash(self):
        string_to_hash = super(MapFeature, self).hash

        if self.is_plot:
            # The hash for a plot includes the hash for its trees
            tree_hashes = [t.hash for t in self.plot.tree_set.all()]
            string_to_hash += "," + ",".join(tree_hashes)

        return hashlib.md5(string_to_hash).hexdigest()

    def cast_to_subtype(self):
        """
        Return the concrete subclass instance. For example, if self is
        a MapFeature with subtype Plot, return self.plot
        """
        return getattr(self, self.feature_type.lower())

    def __unicode__(self):
        x = self.geom.x if self.geom else "?"
        y = self.geom.y if self.geom else "?"
        address = self.address_street or "Address Unknown"
        text = "%s (%s, %s) %s" % (self.feature_type, x, y, address)
        return text


#TODO:
# Exclusion Zones
# Proximity validation
# UDFModel overrides implementations of methods in
# authorizable and auditable, thus needs to be inherited first
class Plot(MapFeature):
    width = models.FloatField(null=True, blank=True,
                              help_text=trans("Plot Width"))
    length = models.FloatField(null=True, blank=True,
                               help_text=trans("Plot Length"))

    owner_orig_id = models.CharField(max_length=255, null=True, blank=True)

    objects = GeoHStoreUDFManager()

    @classproperty
    def benefits(cls):
        from treemap.ecobenefits import TreeBenefitsCalculator
        return TreeBenefitsCalculator()

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

    def delete_with_user(self, user, cascade=False, *args, **kwargs):
        if self.current_tree() and cascade is False:
            raise ValidationError(trans(
                "Cannot delete plot with existing trees."))
        super(Plot, self).delete_with_user(user, *args, **kwargs)

    @classproperty
    def display_name(cls):
        return trans('Planting Site')


# UDFModel overrides implementations of methods in
# authorizable and auditable, thus needs to be inherited first
class Tree(Convertible, UDFModel, PendingAuditable):
    """
    Represents a single tree, belonging to an instance
    """
    instance = models.ForeignKey(Instance)

    plot = models.ForeignKey(Plot)
    species = models.ForeignKey(Species, null=True, blank=True)

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

    objects = GeoHStoreUDFManager()

    def __unicode__(self):
        diameter_chunk = ("Diameter: %s, " % self.diameter
                          if self.diameter else "")
        species_chunk = ("Species: %s - " % self.species
                         if self.species else "")
        return "%s%s" % (diameter_chunk, species_chunk)

    def dict(self):
        props = self.as_dict()
        props['species'] = self.species

        return props

    def photos(self):
        return self.treephoto_set.order_by('-created_at')

    @property
    def itree_region(self):
        if self.instance.itree_region_default:
            region = self.instance.itree_region_default
        else:
            regions = ITreeRegion.objects\
                                 .filter(geometry__contains=self.plot.geom)

            if len(regions) > 0:
                region = regions[0].code
            else:
                region = None

        return region

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

    @transaction.atomic
    def delete_with_user(self, user, *args, **kwargs):
        photos = self.photos()
        for photo in photos:
            photo.delete_with_user(user)
        super(Tree, self).delete_with_user(user, *args, **kwargs)


class Favorite(models.Model):
    user = models.ForeignKey(User)
    map_feature = models.ForeignKey(MapFeature)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'map_feature',)


class MapFeaturePhoto(models.Model, PendingAuditable):
    map_feature = models.ForeignKey(MapFeature)

    image = models.ImageField(
        upload_to='trees/%Y/%m/%d', editable=False)
    thumbnail = models.ImageField(
        upload_to='trees_thumbs/%Y/%m/%d', editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    instance = models.ForeignKey(Instance)

    def __init__(self, *args, **kwargs):
        super(MapFeaturePhoto, self).__init__(*args, **kwargs)
        self._do_not_track.add('created_at')
        self._do_not_track.add('mapfeaturephoto_ptr')
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

        field, _, _, _ = MapFeaturePhoto._meta.get_field_by_name(field)

        saved_rep = field.pre_save(self, thing)
        return str(saved_rep)

    def as_dict(self):
        data = super(MapFeaturePhoto, self).as_dict()

        data['image'] = self._get_db_prep_for_image('image')
        data['thumbnail'] = self._get_db_prep_for_image('thumbnail')

        return data

    @property
    def image_prefix(self):
        return str(self.map_feature.pk)

    def set_image(self, image_data, degrees_to_rotate=None):
        self.image, self.thumbnail = save_uploaded_image(
            image_data, self.image_prefix, thumb_size=(256, 256),
            degrees_to_rotate=degrees_to_rotate)

    def save_with_user(self, *args, **kwargs):
        if not self.thumbnail.name:
            raise Exception('You need to call set_image instead')
        if (hasattr(self, 'map_feature') and
           self.map_feature.instance != self.instance):
            raise ValidationError(
                'Cannot save to a map feature in another instance')

        # The auto_now_add is acting up... set it here if we're new
        if self.pk is None:
            self.created_at = timezone.now()

        super(MapFeaturePhoto, self).save_with_user(*args, **kwargs)

    def delete_with_user(self, *args, **kwargs):
        thumb = self.thumbnail
        image = self.image

        super(MapFeaturePhoto, self).delete_with_user(*args, **kwargs)

        thumb.delete(False)
        image.delete(False)


class TreePhoto(MapFeaturePhoto):
    tree = models.ForeignKey(Tree)

    def save_with_user(self, *args, **kwargs):
        def is_attr_set(attr):
            try:
                return bool(getattr(self, attr))
            except ObjectDoesNotExist:
                return False

        if is_attr_set('tree') and self.tree.instance != self.instance:
            raise ValidationError('Cannot save to a tree in another instance')

        if is_attr_set('map_feature'):
            if not self.map_feature.is_plot:
                raise ValidationError('Cannot save to a tree without a plot')

            elif self.map_feature.current_tree() != self.tree:
                raise ValidationError(
                    'Cannot save to a tree with the wrong plot')
        elif is_attr_set('tree'):
            self.map_feature = self.tree.plot

        super(TreePhoto, self).save_with_user(*args, **kwargs)

    @property
    def image_prefix(self):
        return "%s-%s" % (self.tree.plot.pk, self.tree.pk)

    def as_dict(self):
        data = super(TreePhoto, self).as_dict()

        if hasattr(self, 'tree'):
            data['tree'] = self.tree.pk

        return data


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
        +- Callowhill (Neighborhood, 4)
         +- 19107 (Zip Code, 5)
    """
    geom = models.MultiPolygonField(srid=3857,
                                    db_column='the_geom_webmercator')

    name = models.CharField(max_length=255)
    category = models.CharField(max_length=255)
    sort_order = models.IntegerField()

    objects = models.GeoManager()

    def __unicode__(self):
        return self.name


class ITreeRegion(models.Model):
    code = models.CharField(max_length=40, unique=True)
    geometry = models.MultiPolygonField(srid=3857)

    objects = models.GeoManager()


class ITreeCodeOverride(models.Model, Auditable):
    instance_species = models.ForeignKey(Species)
    region = models.ForeignKey(ITreeRegion)
    itree_code = models.CharField(max_length=100)

    class Meta:
        unique_together = ('instance_species', 'region',)
