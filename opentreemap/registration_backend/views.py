# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django import forms
from django.utils.translation import ugettext_lazy as trans
from django.core.urlresolvers import reverse
from django.contrib.sites.models import RequestSite
from django.contrib.sites.models import Site

from registration import signals
from registration.forms import RegistrationFormUniqueEmail\
    as DefaultRegistrationForm
from registration.models import RegistrationProfile
from registration.backends.default.views\
    import RegistrationView as DefaultRegistrationView
from registration.backends.default.views\
    import ActivationView as DefaultActivationView

from treemap.models import InstanceUser
from treemap.plugin import should_send_user_activation
from treemap.util import get_instance_or_404


class RegistrationForm(DefaultRegistrationForm):
    organization = forms.CharField(
        max_length=100,
        required=False,
        label=trans('Organization'))

    firstname = forms.CharField(
        max_length=100,
        required=False,
        label=trans('First name'))

    lastname = forms.CharField(
        max_length=100,
        required=False,
        label=trans('Last name'))

    allow_email_contact = forms.BooleanField(
        required=False,
        label=trans('I wish to receive occasional email '
                    'updates from the tree maps to which '
                    'I contribute.'))


class RegistrationView(DefaultRegistrationView):
    def get_form_class(self, *args, **kwargs):
        return RegistrationForm

    def dispatch(self, request, instance_url_name=None, *args, **kwargs):
        if instance_url_name:
            request.instance = get_instance_or_404(url_name=instance_url_name)
        return super(RegistrationView, self).dispatch(
            request, *args, **kwargs)

    def get_success_url(self, request, new_user):
        """
        If a user already belongs to an instance (i.e. was invited)
        and they have been activated, redirect to that map page
        """
        instanceusers = InstanceUser.objects.filter(user=new_user)

        if instanceusers.exists() and new_user.is_active:
            instance = instanceusers[0].instance
            url = reverse('map', kwargs={'instance_url_name':
                                         instance.url_name})
            return (url, [], {})
        return super(RegistrationView, self).get_success_url(request, new_user)

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

        if hasattr(request, 'instance'):
            InstanceUser.objects.get_or_create(
                user=user,
                instance=request.instance,
                role=request.instance.default_role)

        signals.user_registered.send(sender=self.__class__,
                                     user=user,
                                     request=request,
                                     password=password)
        return user


class ActivationView(DefaultActivationView):
    def get_success_url(self, request, user):
        instanceusers = InstanceUser.objects.filter(user=user)

        if instanceusers.exists():
            instance = instanceusers[0].instance
            url = reverse('map', kwargs={'instance_url_name':
                                         instance.url_name})
            return (url, [], {})
        return super(ActivationView, self).get_success_url(request, user)
