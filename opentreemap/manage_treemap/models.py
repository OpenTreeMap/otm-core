# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import random
import string

from django.core.validators import validate_email
from django.contrib.gis.db import models

from treemap.models import User
from treemap.instance import Instance
from treemap.audit import Role


class InstanceInvitation(models.Model):
    """
    Instance invites represent people that have been invited to a map
    but have not yet registered.

    The expected workflow is something:
    * Instance Owner invites a@b.com to their map and an invite is created
    * a@b.com gets an email with link to registration page
    * a@b.com registers and they are added to all maps where they have
    * an invite
    """
    email = models.CharField(max_length=255,
                             validators=[validate_email])

    instance = models.ForeignKey(Instance)
    role = models.ForeignKey(Role)
    admin = models.BooleanField(default=False)

    created = models.DateField(auto_now_add=True)
    created_by = models.ForeignKey(User)

    updated = models.DateField(auto_now=True)
    accepted = models.BooleanField(default=False)

    # We use a random key as part of the URL sent in the invitation email
    # Visiting this URL will mark the the invite as activated, allowing us to
    # skip email activation during user registration
    activation_key = models.CharField(max_length=40, unique=True)

    @staticmethod
    def generate_key():
        # from http://stackoverflow.com/a/23728630/233437
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.SystemRandom().choice(chars) for __ in range(40))

    def save(self, *args, **kwargs):
        if not self.activation_key:
            while True:
                self.activation_key = InstanceInvitation.generate_key()
                # If our randomly generated key matches an existing key,
                # we need to try again
                matching_keys = InstanceInvitation.objects.filter(
                    activation_key=self.activation_key)
                if not matching_keys.exists():
                    break

        self.full_clean()
        super(InstanceInvitation, self).save(*args, **kwargs)

    class Meta:
        unique_together = ("email", "instance")
