# -*- coding: utf-8 -*-


from django.core.exceptions import MultipleObjectsReturned

from django.contrib.gis.db import models
from django.contrib.contenttypes.models import ContentType

from treemap.models import Instance, User

UNBOUND_MODEL_ID = -1


class MigrationEvent(models.Model):
    INCOMPLETE = -1
    SUCCESS = 0
    FAILURE = 1
    created = models.DateTimeField(auto_now_add=True,
                                   editable=False)
    completed = models.DateTimeField(auto_now=True,
                                     editable=False)
    status = models.IntegerField(default=INCOMPLETE,
                                 choices=((SUCCESS, 'SUCCESS'),
                                          (FAILURE, 'FAILURE')))


class AbstractRelic(models.Model):
    migration_event = models.ForeignKey(MigrationEvent, on_delete=models.CASCADE,
                                        null=True, blank=True)
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE)
    otm1_model_id = models.IntegerField()
    otm2_model_id = models.IntegerField()

    def summon(self, **kwargs):
        """
        Get the OTM2 model instance that is bound to this relic
        """
        app_label = kwargs.get('app_label', 'treemap')

        try:
            model_type = ContentType.objects.get(model=self.otm2_model_name)
        except MultipleObjectsReturned:
            model_type = ContentType.objects.get(
                model=self.otm2_model_name, app_label=app_label)

        return model_type.get_object_for_this_type(pk=self.otm2_model_id)

    class Meta:
        abstract = True
        unique_together = ('otm2_model_name', 'otm1_model_id', 'instance')


class OTM1ModelRelic(AbstractRelic):
    otm2_model_name = models.CharField(max_length=255)


class OTM1UserRelicManager(models.Manager):
    def get_chosen_one(self, user_id):
        """ For a given user_id, find the relic who got the same
        username on otm2.

        Sometimes this is impossible, if the username was subsequently
        uniquified because it was already in use.  This is because
        there is a two-step user uniquification in the migration:
        1) choose a best username for a given set of duplicate email addresses
        2) "Try" to choose that username on otm2, uniquifying if taken.
        """
        user = User.objects.get(pk=user_id)
        try:
            return self.get_queryset().get(otm1_username=user.username)
        except OTM1UserRelic.DoesNotExist:
            return None


class OTM1UserRelic(AbstractRelic):
    otm2_model_name = models.CharField(max_length=255,
                                       default='user',
                                       editable=False)
    otm1_username = models.CharField(max_length=255)
    email = models.EmailField()
    objects = OTM1UserRelicManager()

    def get_chosen_one(self):
        return self.objects.get_chosen_one(self.otm2_model_id)

    def save(self, *args, **kwargs):
        if not User.objects.filter(pk=self.otm2_model_id).exists():
            raise Exception('User not found')
        super(OTM1UserRelic, self).save(*args, **kwargs)


class OTM1CommentRelic(AbstractRelic):
    otm2_model_name = models.CharField(max_length=255,
                                       # TODO: change to
                                       # enhancedthreadedcomment
                                       default='threadedcomment',
                                       editable=False)
    otm1_last_child_id = models.IntegerField(null=True, blank=True)
