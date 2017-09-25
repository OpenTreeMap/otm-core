# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


import hashlib
import re
from copy import copy

from django.conf import settings
from django.contrib.gis.geos import Point, MultiPolygon
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
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import (UserManager, AbstractBaseUser,
                                        PermissionsMixin)
from django.template.loader import get_template

from treemap.species.codes import ITREE_REGIONS, get_itree_code
from treemap.audit import Auditable, Role, Dictable, Audit, PendingAuditable
# Import this even though it's not referenced, so Django can find it
from treemap.audit import UserTrackable, FieldPermission  # NOQA
from treemap.util import leaf_models_of_class, to_object_name
from treemap.decorators import classproperty
from treemap.images import save_uploaded_image
from treemap.units import Convertible
from treemap.udf import UDFModel
from treemap.instance import Instance
from treemap.lib.object_caches import invalidate_adjuncts


def _action_format_string_for_location(action):
    """A helper that allows multiple auditable models to return the
    same action format string for a field value that should be displayed
    as a location"""
    lang = {
        Audit.Type.Insert: _('set the location'),
        Audit.Type.Update: _('updated the location'),
        Audit.Type.Delete: _('deleted the location'),
        Audit.Type.PendingApprove: _('approved an edit of the location'),
        Audit.Type.PendingReject: _('rejected an edit of the location')
    }
    return lang[action]


def _action_format_string_for_readonly(action, readonly):
    """A helper that allows multiple auditable models to return the
    the state of a readonly boolean"""
    if readonly:
        value = _("read only")
    else:
        value = _("editable")
    lang = {
        Audit.Type.Insert: _('made the tree %(value)s'),
        Audit.Type.Update: _('made the tree %(value)s'),
        Audit.Type.Delete: _('made the tree %(value)s'),
        Audit.Type.PendingApprove: _('approved making the tree %(value)s'),
        Audit.Type.PendingReject: _('approved making the tree %(value)s')
    }
    return lang[action] % {'value': value}


class StaticPage(models.Model):
    instance = models.ForeignKey(Instance)
    name = models.CharField(max_length=100)
    content = models.TextField()

    DEFAULT_CONTENT = {
        'resources': 'treemap/partials/Resources.html',
        'about': 'treemap/partials/About.html',
        'faq': 'treemap/partials/FAQ.html'
    }

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

            if page_name.lower() in StaticPage.DEFAULT_CONTENT:
                template = get_template(
                    StaticPage.DEFAULT_CONTENT[page_name.lower()])
                content = template.render()
            else:
                content = 'There is no content for this page yet.'

            static_page = StaticPage(instance=instance, name=page_name,
                                     content=content)
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
            errors['currency_symbol'] = _(
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
                    errors[field] = [_('Values must be not be negative')]
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
    def get_default_for_instance(cls, instance):
        """
        Returns a new BenefitCurrencyConversion for the instance's (first)
        i-Tree region. The instance must have bounds for this to work.
        """
        regions_covered = instance.itree_regions()

        if len(regions_covered) == 0:
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
# email_field, __, __, __ = User._meta.get_field_by_name('email')
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
        _('username'), max_length=30, unique=True,
        help_text=_(
            'Required. 30 characters or fewer. Letters, numbers and '
            '@/./+/-/_ characters'),
        validators=[
            validators.RegexValidator(
                re.compile('^[\w.@+-]+$'),
                _('Enter a valid username.'), 'invalid')
        ])
    email = models.EmailField(_('email address'), blank=True, unique=True)
    is_staff = models.BooleanField(
        _('staff status'), default=False,
        help_text=_('Designates whether the user can log into this admin '
                    'site.'))
    is_active = models.BooleanField(
        _('active'), default=True,
        help_text=_('Designates whether this user should be treated as '
                    'active. Unselect this instead of deleting accounts.'))
    date_joined = models.DateTimeField(_('date joined'),
                                       default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
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
        _('first name'), max_length=30, default='', blank=True)
    last_name = models.CharField(
        _('last name'), max_length=30, default='', blank=True)
    organization = models.CharField(max_length=255, default='', blank=True)

    make_info_public = models.BooleanField(default=False)
    allow_email_contact = models.BooleanField(default=False)

    def __init__(self, *args, **kwargs):
        super(User, self).__init__(*args, **kwargs)

        self.populate_previous_state()

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
        if (instance_user is None and
           instance.feature_enabled('auto_add_instance_user')):
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
        super(User, self).clean()

        if re.search('\\s', self.username):
            raise ValidationError(_('Cannot have spaces in a username'))

    def save_with_user(self, user, *args, **kwargs):
        self.full_clean()
        self.email = self.email.lower()
        super(User, self).save_with_user(user, *args, **kwargs)

    def save(self, *args, **kwargs):
        system_user = User.system_user()
        self.save_with_user(system_user, *args, **kwargs)


class Species(PendingAuditable, models.Model):
    """
    http://plants.usda.gov/adv_search.html
    """

    DEFAULT_MAX_DIAMETER = 200
    DEFAULT_MAX_HEIGHT = 800

    # Base required info
    instance = models.ForeignKey(Instance)
    # ``otm_code`` is the key used to link this instance
    # species row to a cannonical species. An otm_code
    # is usually the USDA code, but this is not guaranteed.
    otm_code = models.CharField(max_length=255)
    common_name = models.CharField(max_length=255, verbose_name='Common Name')
    genus = models.CharField(max_length=255, verbose_name='Genus')
    species = models.CharField(max_length=255, blank=True,
                               verbose_name='Species')
    cultivar = models.CharField(max_length=255, blank=True,
                                verbose_name='Cultivar')
    other_part_of_name = models.CharField(max_length=255, blank=True,
                                          verbose_name='Other Part of Name')

    # From original OTM (some renamed) ###
    is_native = models.NullBooleanField(verbose_name='Native to Region')
    flowering_period = models.CharField(max_length=255, blank=True,
                                        verbose_name='Flowering Period')
    fruit_or_nut_period = models.CharField(max_length=255, blank=True,
                                           verbose_name='Fruit or Nut Period')
    fall_conspicuous = models.NullBooleanField(verbose_name='Fall Conspicuous')
    flower_conspicuous = models.NullBooleanField(
        verbose_name='Flower Conspicuous')
    palatable_human = models.NullBooleanField(verbose_name='Edible')
    has_wildlife_value = models.NullBooleanField(
        verbose_name='Has Wildlife Value')
    fact_sheet_url = models.URLField(max_length=255, blank=True,
                                     verbose_name='Fact Sheet URL')
    plant_guide_url = models.URLField(max_length=255, blank=True,
                                      verbose_name='Plant Guide URL')

    # Used for validation
    max_diameter = models.IntegerField(default=DEFAULT_MAX_DIAMETER,
                                       verbose_name='Max Diameter')
    max_height = models.IntegerField(default=DEFAULT_MAX_HEIGHT,
                                     verbose_name='Max Height')

    # Included for the sake of cache busting
    updated_at = models.DateTimeField(  # TODO: remove null=True
        null=True, auto_now=True, editable=False, db_index=True)

    objects = models.GeoManager()

    def __init__(self, *args, **kwargs):
        super(Species, self).__init__(*args, **kwargs)
        self.populate_previous_state()

    @property
    def display_name(self):
        return "%s [%s]" % (self.common_name, self.scientific_name)

    @classmethod
    def get_scientific_name(clz, genus, species, cultivar, other_part_of_name):
        name = genus
        if species:
            name += " " + species
        if other_part_of_name:
            name += " " + other_part_of_name
        if cultivar:
            name += " '%s'" % cultivar
        return name

    @property
    def scientific_name(self):
        return Species.get_scientific_name(
            self.genus, self.species, self.cultivar, self.other_part_of_name)

    def dict(self):
        props = self.as_dict()
        props['scientific_name'] = self.scientific_name

        return props

    @classmethod
    def get_by_code(cls, instance, otm_code, region_code):
        """
        Get a Species with the specified otm_code in the specified instance. If
        a matching Species does not exists, attempt to find and
        ITreeCodeOverride that has a itree_code matching the specified otm_code
        in the specified region.
        """
        species = Species.objects.filter(instance=instance, otm_code=otm_code)
        if species.exists():
            return species[0]
        else:
            species_ids = \
                Species.objects.filter(instance=instance).values('pk')
            region = ITreeRegion.objects.get(code=region_code)
            itree_code = get_itree_code(region_code, otm_code)
            overrides = ITreeCodeOverride.objects.filter(
                itree_code=itree_code,
                region=region,
                instance_species_id__in=species_ids)
            if overrides.exists():
                return overrides[0].instance_species
            else:
                return None

    def get_itree_code(self, region_code=None):
        if not region_code:
            regions = self.instance.itree_regions()
            if len(regions) == 1:
                region_code = regions[0].code
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
        verbose_name = "Species"
        verbose_name_plural = "Species"
        unique_together = ('instance', 'common_name', 'genus', 'species',
                           'cultivar', 'other_part_of_name',)


class InstanceUser(Auditable, models.Model):
    instance = models.ForeignKey(Instance)
    user = models.ForeignKey(User)
    role = models.ForeignKey(Role)
    reputation = models.IntegerField(default=0)
    admin = models.BooleanField(default=False)
    last_seen = models.DateField(null=True, blank=True)

    def __init__(self, *args, **kwargs):
        super(InstanceUser, self).__init__(*args, **kwargs)
        self._do_not_track |= self.do_not_track

        self.populate_previous_state()

    class Meta:
        unique_together = ('instance', 'user',)

    def save_with_user(self, user, *args, **kwargs):
        self.full_clean()
        super(InstanceUser, self).save_with_user(user, *args, **kwargs)

    def save(self, *args, **kwargs):
        system_user = User.system_user()
        self.save_with_user(system_user, *args, **kwargs)

    @classproperty
    def do_not_track(cls):
        return Auditable.do_not_track | {'last_seen'}

    def __unicode__(self):
        # protect against not being logged in
        username = ''
        if getattr(self, 'user', None) is not None:
            username = self.user.get_username() + '/'
        if not username and not self.instance.name:
            return ''
        return '%s %s' % (username, self.instance.name)

post_save.connect(invalidate_adjuncts, sender=InstanceUser)
post_delete.connect(invalidate_adjuncts, sender=InstanceUser)


# UDFModel overrides implementations of methods in
# authorizable and auditable, thus needs to be inherited
# before PendingAuditable.
class MapFeature(Convertible, UDFModel, PendingAuditable):
    "Superclass for map feature subclasses like Plot, RainBarrel, etc."
    instance = models.ForeignKey(Instance)
    geom = models.PointField(srid=3857, db_column='the_geom_webmercator')

    address_street = models.CharField(max_length=255, blank=True, null=True,
                                      verbose_name=_("Address"))
    address_city = models.CharField(max_length=255, blank=True, null=True,
                                    verbose_name=_("City"))
    address_zip = models.CharField(max_length=30, blank=True, null=True,
                                   verbose_name=_("Postal Code"))

    readonly = models.BooleanField(default=False)

    # Although this can be retrieved with a MAX() query on the audit
    # table, we store a "cached" value here to keep filtering easy and
    # efficient.
    updated_at = models.DateTimeField(default=timezone.now,
                                      verbose_name=_("Last Updated"))
    updated_by = models.ForeignKey(User, null=True, blank=True,
                                   verbose_name=_("Last Updated By"))

    objects = models.GeoManager()

    # subclass responsibilities
    area_field_name = None
    is_editable = None

    # When querying MapFeatures (as opposed to querying a subclass like Plot),
    # we get a heterogenous collection (some Plots, some RainBarrels, etc.).
    # The feature_type attribute tells us the type of each object.

    feature_type = models.CharField(max_length=255)

    hide_at_zoom = models.IntegerField(
        null=True, blank=True, default=None, db_index=True)

    users_can_delete_own_creations = True

    @classproperty
    def always_writable(cls):
        # `hide_at_zoom` and `geom` never need to be checked.
        # If we ever implement the ability to lock down a model instance,
        # `readonly` should be removed from this list.
        return PendingAuditable.always_writable | {
            'hide_at_zoom', 'geom', 'readonly'}

    def __init__(self, *args, **kwargs):
        super(MapFeature, self).__init__(*args, **kwargs)
        if self.feature_type == '':
            self.feature_type = self.map_feature_type
        self._do_not_track |= self.do_not_track

        self.populate_previous_state()

    @classproperty
    def do_not_track(cls):
        return PendingAuditable.do_not_track | UDFModel.do_not_track | {
            'feature_type', 'mapfeature_ptr', 'hide_at_zoom'}

    @property
    def _is_generic(self):
        return self.__class__.__name__ == 'MapFeature'

    @classproperty
    def geom_field_name(cls):
        return "%s.geom" % to_object_name(cls.map_feature_type)

    @property
    def latlon(self):
        latlon = Point(self.geom.x, self.geom.y, srid=3857)
        latlon.transform(4326)
        return latlon

    @property
    def is_plot(self):
        return getattr(self, 'feature_type', None) == 'Plot'

    def update_updated_fields(self, user):
        """Changing a child object of a map feature (tree, photo,
        etc.) demands that we update the updated_at field on the
        parent map_feature, however there is likely code throughout
        the application that saves updates to a child object without
        calling save on the parent MapFeature. This method intended to
        by called in the save method of those child objects."""
        self.updated_at = timezone.now()
        self.updated_by = user
        MapFeature.objects.filter(pk=self.pk).update(
            updated_at=self.updated_at, updated_by=user)

    def save_with_user(self, user, *args, **kwargs):
        self.full_clean_with_user(user)

        if self._is_generic:
            raise Exception(
                'Never save a MapFeature -- only save a MapFeature subclass')

        self.updated_at = timezone.now()
        self.updated_by = user
        super(MapFeature, self).save_with_user(user, *args, **kwargs)

    def clean(self):
        super(MapFeature, self).clean()

        if self.geom is None:
            raise ValidationError({
                "geom": [_("Feature location is not specified")]})
        if not self.instance.bounds.geom.contains(self.geom):
            raise ValidationError({
                "geom": [
                    _(
                        "%(model)s must be created inside the map boundaries")
                    % {'model': self.terminology(self.instance)['plural']}]
            })

    def delete_with_user(self, user, *args, **kwargs):
        self.instance.update_revs('geo_rev', 'eco_rev', 'universal_rev')
        super(MapFeature, self).delete_with_user(user, *args, **kwargs)

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

    @classmethod
    def subclass_dict(cls):
        return {C.map_feature_type: C
                for C in leaf_models_of_class(MapFeature)}

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
    def get_config(cls, instance):
        """
        Get configuration properties for this map feature type on the
        specified instance.

        Note that the map feature config is assumed to be flat.
        """
        config = copy(getattr(cls, 'default_config', {}))
        overrides = instance.map_feature_config.get(cls.__name__, {})
        config.update(overrides)
        return config

    @classmethod
    def set_config_property(cls, instance, key, value, save=True):
        """
        Set a configuration property for this map feature type on the
        specified instance.
        """
        config = instance.map_feature_config
        class_name = cls.__name__
        if class_name not in config:
            config[class_name] = {}
        config[class_name][key] = value
        instance.map_feature_config = config
        if save:
            instance.save()

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

        # Need to include nearby features in the hash, as they are in the
        # detail sidebar & popup.
        for feature in self.nearby_map_features():
            string_to_hash += "," + str(feature.pk)

        return hashlib.md5(string_to_hash).hexdigest()

    def title(self):
        # Cast allows the map feature subclass to handle generating
        # the display name
        feature = self.cast_to_subtype()

        if feature.is_plot:
            tree = feature.current_tree()
            if tree:
                if tree.species:
                    title = tree.species.common_name
                else:
                    title = _("Missing Species")
            else:
                title = _("Empty Planting Site")
        else:
            title = feature.display_name(self.instance)

        return title

    def contained_plots(self):
        if self.area_field_name is not None:
            plots = Plot.objects \
                .filter(instance=self.instance) \
                .filter(geom__within=getattr(self, self.area_field_name)) \
                .prefetch_related('tree_set', 'tree_set__species')

            def key_sort(plot):
                tree = plot.current_tree()
                if tree is None:
                    return (0, None)
                if tree.species is None:
                    return (1, None)
                return (2, tree.species.common_name)

            return sorted(plots, key=key_sort)

        return None

    def cast_to_subtype(self):
        """
        Return the concrete subclass instance. For example, if self is
        a MapFeature with subtype Plot, return self.plot
        """
        if type(self) is not MapFeature:
            # This shouldn't really ever happen, but there's no point trying to
            # cast a subclass to itself
            return self

        ft = self.feature_type
        if hasattr(self, ft.lower()):
            return getattr(self, ft.lower())
        else:
            return getattr(self.polygonalmapfeature, ft.lower())

    def safe_get_current_tree(self):
        if hasattr(self, 'current_tree'):
            return self.current_tree()
        else:
            return None

    def nearby_map_features(self, distance_in_meters=None):
        if distance_in_meters is None:
            distance_in_meters = settings.NEARBY_TREE_DISTANCE

        distance_filter = MapFeature.objects.filter(
            geom__distance_lte=(self.geom, D(m=distance_in_meters)))

        return distance_filter\
            .filter(instance=self.instance)\
            .exclude(pk=self.pk)

    def __unicode__(self):
        geom = getattr(self, 'geom', None)
        x = geom and geom.x or '?'
        y = geom and geom.y or '?'

        address = getattr(self, 'address_street', "Address Unknown")
        feature_type = getattr(self, 'feature_type', "Type Unknown")
        if not feature_type and not address and not x and not y:
            return ''
        text = "%s (%s, %s) %s" % (feature_type, x, y, address)
        return text

    @classproperty
    def _terminology(cls):
        return {'singular': cls.__name__}

    @classproperty
    def benefits(cls):
        from treemap.ecobenefits import CountOnlyBenefitCalculator
        return CountOnlyBenefitCalculator(cls)

    @property
    def itree_region(self):
        regions = self.instance.itree_regions(geometry__contains=self.geom)
        if regions:
            return regions[0]
        else:
            return ITreeRegionInMemory(None)


class ValidationMixin(object):
    def validate_positive_nullable_float_field(
            self, field_name, max_value=None, zero_ok=False):

        if getattr(self, field_name) is not None:
            pretty_field_name = field_name.replace('_', ' ')

            def error(message):
                return ValidationError({field_name: [
                    message % {'field_name': pretty_field_name}]})

            try:
                # The value could be a string at this point so we
                # cast to make sure we are comparing two numeric values
                new_value = float(getattr(self, field_name))
            except ValueError:
                raise error(_('The %(field_name)s must be a decimal number'))

            if zero_ok:
                if new_value < 0:
                    raise error(_(
                        'The %(field_name)s must be zero or greater'))
            else:
                if new_value <= 0:
                    raise error(_(
                        'The %(field_name)s must be greater than zero'))

            if max_value is not None:
                if new_value > max_value:
                    raise error(_('The %(field_name)s is too large'))


# TODO:
# Exclusion Zones
# Proximity validation
# authorizable and auditable, thus needs to be inherited first
class Plot(MapFeature, ValidationMixin):
    width = models.FloatField(null=True, blank=True,
                              verbose_name=_("Planting Site Width"))
    length = models.FloatField(null=True, blank=True,
                               verbose_name=_("Planting Site Length"))

    owner_orig_id = models.CharField(max_length=255, null=True, blank=True,
                                     verbose_name=_("Custom ID"))

    objects = models.GeoManager()
    is_editable = True

    _terminology = {'singular': _('Planting Site'),
                    'plural': _('Planting Sites')}

    search_settings = {
        'owner_orig_id': {'search_type': 'IS'}
    }

    udf_settings = {
        'Stewardship': {
            'iscollection': True,
            'range_field_key': 'Date',
            'action_field_key': 'Action',
            'action_verb': _('that have been'),
            'defaults': [
                {'name': 'Action',
                 'choices': ['Enlarged',
                             'Changed to Include a Guard',
                             'Changed to Remove a Guard',
                             'Filled with Herbaceous Plantings'],
                 'type': 'choice'},
                {'type': 'date',
                 'name': 'Date'}],
        },
        'Alerts': {
            'iscollection': True,
            'warning_message': _(
                "Marking a planting site with an alert does not serve as a "
                "way to report problems with that site. If you have any "
                "emergency concerns, please contact your city directly."),
            'range_field_key': 'Date Noticed',
            'action_field_key': 'Action Needed',
            'action_verb': _('with open alerts for'),
        }
    }

    @classproperty
    def benefits(cls):
        from treemap.ecobenefits import TreeBenefitsCalculator
        return TreeBenefitsCalculator()

    def nearby_plots(self, distance_in_meters=None):
        return self.nearby_map_features(distance_in_meters)\
            .filter(feature_type='Plot')

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

    def save_with_user(self, user, *args, **kwargs):
        self.full_clean_with_user(user)

        # These validations must be done after the field values have
        # been converted to database units but `convert_to_database_units`
        # calls `clean`, so these validations cannot be part of `clean`.
        self.validate_positive_nullable_float_field('width')
        self.validate_positive_nullable_float_field('length')

        super(Plot, self).save_with_user(user, *args, **kwargs)

    def delete_with_user(self, user, cascade=False, *args, **kwargs):
        if self.current_tree() and cascade is False:
            raise ValidationError(_(
                "Cannot delete plot with existing trees."))
        super(Plot, self).delete_with_user(user, *args, **kwargs)


# UDFModel overrides implementations of methods in
# authorizable and auditable, thus needs to be inherited
# before PendingAuditable.
class Tree(Convertible, UDFModel, PendingAuditable, ValidationMixin):
    """
    Represents a single tree, belonging to an instance
    """
    instance = models.ForeignKey(Instance)

    plot = models.ForeignKey(Plot)
    species = models.ForeignKey(Species, null=True, blank=True,
                                verbose_name=_("Species"))

    readonly = models.BooleanField(default=False)
    diameter = models.FloatField(null=True, blank=True,
                                 verbose_name=_("Tree Diameter"))
    height = models.FloatField(null=True, blank=True,
                               verbose_name=_("Tree Height"))
    canopy_height = models.FloatField(null=True, blank=True,
                                      verbose_name=_("Canopy Height"))
    date_planted = models.DateField(null=True, blank=True,
                                    verbose_name=_("Date Planted"))
    date_removed = models.DateField(null=True, blank=True,
                                    verbose_name=_("Date Removed"))

    users_can_delete_own_creations = True

    objects = models.GeoManager()

    _stewardship_choices = ['Watered',
                            'Pruned',
                            'Mulched, Had Compost Added, or Soil Amended',
                            'Cleared of Trash or Debris']

    udf_settings = {
        'Stewardship': {
            'iscollection': True,
            'range_field_key': 'Date',
            'action_field_key': 'Action',
            'action_verb': 'that have been',
            'defaults': [
                {'name': 'Action',
                 'choices': _stewardship_choices,
                 'type': 'choice'},
                {'type': 'date',
                 'name': 'Date'}],
        },
        'Alerts': {
            'iscollection': True,
            'warning_message': _(
                "Marking a tree with an alert does not serve as a way to "
                "report problems with a tree. If you have any emergency "
                "tree concerns, please contact your city directly."),
            'range_field_key': 'Date Noticed',
            'action_field_key': 'Action Needed',
            'action_verb': _('with open alerts for'),
        }
    }

    @classproperty
    def always_writable(cls):
        # `plot` never needs to be checked.
        # If we ever implement the ability to lock down a model instance,
        # `readonly` should be removed from this list.
        return PendingAuditable.always_writable | {
            'plot', 'readonly'}

    _terminology = {'singular': _('Tree'), 'plural': _('Trees')}

    def __unicode__(self):
        diameter_str = getattr(self, 'diameter', '')
        species_str = getattr(self, 'species', '')
        if not diameter_str and not species_str:
            return ''
        diameter_chunk = "Diameter: %s" % diameter_str
        species_chunk = "Species: %s" % species_str
        return "%s, %s - " % (diameter_chunk, species_chunk)

    def __init__(self, *args, **kwargs):
        super(Tree, self).__init__(*args, **kwargs)
        self.populate_previous_state()

    def dict(self):
        props = self.as_dict()
        props['species'] = self.species

        return props

    def photos(self):
        return self.treephoto_set.order_by('-created_at')

    @property
    def itree_code(self):
        return self.species.get_itree_code(self.plot.itree_region.code)

    ##########################
    # tree validation
    ##########################

    def validate_diameter(self):
        if self.species:
            max_value = self.species.max_diameter
        else:
            max_value = Species.DEFAULT_MAX_DIAMETER
        self.validate_positive_nullable_float_field('diameter', max_value)

    def validate_height(self):
        if self.species:
            max_value = self.species.max_height
        else:
            max_value = Species.DEFAULT_MAX_HEIGHT
        self.validate_positive_nullable_float_field('height', max_value)

    def validate_canopy_height(self):
        self.validate_positive_nullable_float_field('canopy_height')

    def clean(self):
        super(Tree, self).clean()
        if self.plot and self.plot.instance != self.instance:
            raise ValidationError('Cannot save to a plot in another instance')

    def save_with_user(self, user, *args, **kwargs):
        self.full_clean_with_user(user)

        # These validations must be done after the field values have
        # been converted to database units but `convert_to_database_units`
        # calls `clean`, so these validations cannot be part of `clean`.
        self.validate_diameter()
        self.validate_height()
        self.validate_canopy_height()

        self.plot.update_updated_fields(user)
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
        self.plot.update_updated_fields(user)
        self.instance.update_universal_rev()
        super(Tree, self).delete_with_user(user, *args, **kwargs)


class Favorite(models.Model):
    user = models.ForeignKey(User)
    map_feature = models.ForeignKey(MapFeature)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'map_feature',)


class MapFeaturePhoto(models.Model, PendingAuditable, Convertible):
    map_feature = models.ForeignKey(MapFeature)

    image = models.ImageField(
        upload_to='trees/%Y/%m/%d', editable=False)
    thumbnail = models.ImageField(
        upload_to='trees_thumbs/%Y/%m/%d', editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    instance = models.ForeignKey(Instance)

    users_can_delete_own_creations = True
    _terminology = {'singular': _('Photo'), 'plural': _('Photos')}

    def __init__(self, *args, **kwargs):
        super(MapFeaturePhoto, self).__init__(*args, **kwargs)
        self._do_not_track |= self.do_not_track
        self.populate_previous_state()

    @classproperty
    def do_not_track(cls):
        return PendingAuditable.do_not_track | {
            'created_at', 'mapfeaturephoto_ptr'}

    @classproperty
    def always_writable(cls):
        return PendingAuditable.always_writable | {
            f.name for f in MapFeaturePhoto._meta.fields
            if f.name not in MapFeaturePhoto.do_not_track}

    def _get_db_prep_for_image(self, field):
        """
        Images are stored in various ways based on the storage backend
        but they all get serialized to a text field. For auditing, we
        store this value
        """
        thing = getattr(self, field)

        if thing is None:
            return None

        field = MapFeaturePhoto._meta.get_field(field)

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

    def save_with_user(self, user, *args, **kwargs):
        if not self.thumbnail.name:
            raise Exception('You need to call set_image instead')
        if (hasattr(self, 'map_feature') and
           self.map_feature.instance != self.instance):
            raise ValidationError(
                'Cannot save to a map feature in another instance')

        # The auto_now_add is acting up... set it here if we're new
        if self.pk is None:
            self.created_at = timezone.now()

        self.map_feature.update_updated_fields(user)
        super(MapFeaturePhoto, self).save_with_user(user, *args, **kwargs)

    def delete_with_user(self, user, *args, **kwargs):
        thumb = self.thumbnail
        image = self.image

        self.map_feature.update_updated_fields(user)
        super(MapFeaturePhoto, self).delete_with_user(user, *args, **kwargs)

        thumb.delete(False)
        image.delete(False)

    def user_can_create(self, user):
        return self._user_can_do(user, 'add')

    def user_can_delete(self, user):
        """
        A user can delete a photo if their role has the right permission
        or if they created the photo.
        """
        return self._user_can_do(user, 'delete') or self.was_created_by(user)

    def _user_can_do(self, user, action):
        role = user.get_role(self.get_instance())
        Clz = self.map_feature.__class__
        if callable(getattr(self.map_feature, 'cast_to_subtype', None)):
            Clz = self.map_feature.cast_to_subtype().__class__
        codename = Role.permission_codename(Clz, action, photo=True)
        return role.has_permission(codename, Model=MapFeaturePhoto)


class TreePhoto(MapFeaturePhoto):
    tree = models.ForeignKey(Tree)

    @classproperty
    def always_writable(cls):
        return MapFeaturePhoto.always_writable | {'tree'}

    # TreePhoto needs the version user_can_create and user_can_delete
    # defined in Authorizable, which is a base class for PendingAuditable,
    # which is one of the base classes for MapFeaturePhoto.
    #
    # MapFeaturePhoto, used as a leaf class, overrides these methods
    # in an incompatible way.
    #
    # So skip over the MapFeaturePhoto version by calling
    # MapFeaturePhoto's superclass.

    def user_can_create(self, user):
        return super(MapFeaturePhoto, self).user_can_create(user)

    def user_can_delete(self, user):
        return super(MapFeaturePhoto, self).user_can_delete(user)

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


class BoundaryManager(models.GeoManager):
    """
    By default, exclude anonymous boundaries from queries.
    """
    def get_queryset(self):
        return super(BoundaryManager, self).get_queryset().exclude(
            name='', category='', searchable=False)


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

    # Included for the sake of cache busting
    updated_at = models.DateTimeField(auto_now=True, editable=False,
                                      db_index=True)

    canopy_percent = models.FloatField(null=True)
    searchable = models.BooleanField(default=True)

    objects = BoundaryManager()
    # Allows access to anonymous boundaries
    all_objects = models.GeoManager()

    def __unicode__(self):
        return self.name

    @classmethod
    def anonymous(cls, polygon=None):
        """
        Given a polygon, create an anonymous boundary and return it.
        """
        if polygon is None:
            raise ValidationError(_('Cannot create an anonymous boundary '
                                    'without geometry'))
        b = Boundary()
        b.name = ''
        b.category = ''
        b.sort_order = 1
        b.searchable = False
        b.geom = MultiPolygon(polygon)
        return b


class ITreeRegionAbstract(object):
    def __unicode__(self):
        "printed representation, used in templates"
        return "%s (%s)" % (self.code,
                            ITREE_REGIONS.get(self.code, {}).get('name'))


class ITreeRegionInMemory(ITreeRegionAbstract):
    """
    class for in-memory itree region objects

    since we store an itree default code as a charfield and not a
    foreign key on instance, it is helpful to be able to inflate it
    into an ITreeRegion-like object and use it with the same interface
    as objects that come out of the database.
    """
    def __init__(self, code):
        self.code = code


class ITreeRegion(ITreeRegionAbstract, models.Model):
    code = models.CharField(max_length=40, unique=True)
    geometry = models.MultiPolygonField(srid=3857)

    objects = models.GeoManager()


class ITreeCodeOverride(models.Model, Auditable):
    instance_species = models.ForeignKey(Species)
    region = models.ForeignKey(ITreeRegion)
    itree_code = models.CharField(max_length=100)

    class Meta:
        unique_together = ('instance_species', 'region',)

    def __init__(self, *args, **kwargs):
        super(ITreeCodeOverride, self).__init__(*args, **kwargs)
        self.populate_previous_state()
