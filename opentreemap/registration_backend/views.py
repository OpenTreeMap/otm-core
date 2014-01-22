# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django import forms
from django.core.urlresolvers import reverse
from django.contrib.sites.models import RequestSite
from django.contrib.sites.models import Site

from registration import signals
from registration.models import RegistrationProfile, SHA1_RE
from registration.forms import RegistrationFormUniqueEmail\
    as DefaultRegistrationForm
from registration.backends.default.views\
    import RegistrationView as DefaultRegistrationView
from registration.backends.default.views\
    import ActivationView as DefaultActivationView

from treemap.models import InstanceUser
from treemap.plugin import should_send_user_activation


class RegistrationForm(DefaultRegistrationForm):
    organization = forms.CharField(max_length=100, required=False)
    firstname = forms.CharField(max_length=100, required=False)
    lastname = forms.CharField(max_length=100, required=False)
    allow_email_contact = forms.BooleanField(required=False)


class RegistrationView(DefaultRegistrationView):
    def get_form_class(self, *args, **kwargs):
        return RegistrationForm

    def get_success_url(self, request, new_user):
        """
        If a user already belongs to an instance (i.e. was invited)
        redirect to that map page
        """
        instanceusers = InstanceUser.objects.filter(user=new_user)

        if instanceusers.exists():
            instance = instanceusers[0].instance
            url = reverse('map', kwargs={'instance_url_name':
                                         instance.url_name})
            return (url, [], {})
        return super(RegistrationView, self).get_success_url(
            request, new_user)

    def register(self, request, **cleaned_data):
        """
        Register a new user account, inactive user account with the specified
        username, email, and password.

        Creates a new user model object, and a new
        ``registration.models.RegistrationProfile`` tied to the new user
        and containing the activation key used for this account.

        An email will be sent to the supplied email address containing an
        activation link. The email is rendered using two templates. See the
        documentation for ``RegistrationProfile.send_activation_email()`` for
        information about these templates and the contexts provided to
        them.

        After the ``User`` and ``RegistrationProfile`` are created and
        the activation email is sent, the signal
        ``registration.signals.user_registered`` is be sent, with
        the new ``User`` as the keyword argument ``user`` and the
        class of this backend as the sender.
        """
        username = cleaned_data['username']
        email = cleaned_data['email']
        password = cleaned_data['password1']

        if Site._meta.installed:
            site = Site.objects.get_current()
        else:
            site = RequestSite(request)

        should_email = should_send_user_activation(
            request, username, email, password)

        user = RegistrationProfile.objects.create_inactive_user(
            username, email, password, site, send_email=should_email)

        user.firstname = cleaned_data.get('firstname', '')
        user.lastname = cleaned_data.get('lastname', '')
        user.organization = cleaned_data.get('organization', '')
        user.allow_email_contact = cleaned_data.get(
            'allow_email_contact', False)
        user.save_with_user(user)

        signals.user_registered.send(sender=self.__class__,
                                     user=user,
                                     request=request,
                                     password=password)
        return user


class ActivationView(DefaultActivationView):

    def _activate_user(self, activation_key):
        """
        Given an an activation key, look up and activate the user
        account corresponding to that key. If the key is not in a valid
        format or does not have a corresponding RegistrationProfile, then
        the function returns false. Otherwise, the function returns the
        activated User
        """
        # Make sure the key we're trying conforms to the pattern of a
        # SHA1 hash; if it doesn't, no point trying to look it up in
        # the database.
        if SHA1_RE.search(activation_key):
            try:
                profile = RegistrationProfile.objects.get(
                    activation_key=activation_key)
            except RegistrationProfile.objects.model.DoesNotExist:
                return False
            if not profile.activation_key_expired():
                user = profile.user
                user.is_active = True
                user.save_base()
                profile.activation_key =\
                    RegistrationProfile.objects.model.ACTIVATED
                profile.save()
                return user
        else:
            return False

    def activate(self, request, activation_key):
        """
        Given an an activation key, look up and activate the user
        account corresponding to that key.

        After successful activation, the signal
        ``registration.signals.user_activated`` will be sent, with the
        newly activated ``User`` as the keyword argument ``user`` and
        the class of this backend as the sender.

        If the key is not in a valid format or does not have a
        corresponding RegistrationProfile, then the function returns false.
        Otherwise, the function returns the activated User
        """
        activated_user = self._activate_user(activation_key)
        if activated_user:
            signals.user_activated.send(sender=self.__class__,
                                        user=activated_user,
                                        request=request)
        return activated_user

    def get_success_url(self, request, user):
        return ('registration_activation_complete', (), {})
