# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django import forms
from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse
from django.contrib.sites.requests import RequestSite
from django.contrib.auth.views import\
    PasswordResetView as DefaultPasswordResetView
from django.urls import reverse_lazy

from registration import signals
from registration.forms import RegistrationFormUniqueEmail\
    as DefaultRegistrationForm
from registration.models import RegistrationProfile
from registration.backends.default.views\
    import RegistrationView as DefaultRegistrationView
from registration.backends.default.views\
    import ActivationView as DefaultActivationView

from manage_treemap.views.user_roles import should_send_user_activation
from treemap.models import InstanceUser, User
from treemap.util import get_instance_or_404


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super(LoginForm, self).__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'input-xlarge form-control'


class RegistrationForm(DefaultRegistrationForm):
    email2 = forms.EmailField(label=_("Confirm Email"))

    first_name = forms.CharField(
        max_length=100,
        required=False,
        label=_('First name'))

    last_name = forms.CharField(
        max_length=100,
        required=False,
        label=_('Last name'))

    organization = forms.CharField(
        max_length=100,
        required=False,
        label=_('Organization'))

    make_info_public = forms.BooleanField(
        required=False,
        label=_("Display my first name, last name, and organization "
                "on my publicly visible user profile page."))

    allow_email_contact = forms.BooleanField(
        required=False,
        label=_('I wish to receive occasional email '
                'updates from the tree maps to which I contribute.'))

    if settings.USE_RECAPTCHA:
        from captcha.fields import ReCaptchaField
        captcha = ReCaptchaField(label='Verification')

    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)

        self.fields['email'].label = _('Email')
        self.fields['password2'].label = _('Confirm Password')

        for field_name, field in self.fields.items():
            if not isinstance(field, forms.BooleanField):
                field.widget.attrs['class'] = 'form-control'

        self.fields['password1'].widget.attrs['outer_class'] = 'field-left'
        self.fields['password2'].widget.attrs['outer_class'] = 'field-right'
        self.fields['first_name'].widget.attrs['outer_class'] = 'field-left'
        self.fields['last_name'].widget.attrs['outer_class'] = 'field-right'

    def clean_email2(self):
        email1 = self.cleaned_data.get("email")
        email2 = self.cleaned_data.get("email2")
        if email1 and email2 and email1 != email2:
            raise forms.ValidationError(
                _("The two email fields didn't match."))
        return email2

    class Meta:
        model = User
        fields = ("username", "email", "email2")


class RegistrationView(DefaultRegistrationView):
    def get_form_class(self, *args, **kwargs):
        return RegistrationForm

    def dispatch(self, request, instance_url_name=None, *args, **kwargs):
        if instance_url_name:
            self.request.instance = get_instance_or_404(
                url_name=instance_url_name)
        return super(RegistrationView, self).dispatch(
            self.request, *args, **kwargs)

    def get_success_url(self, new_user):
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
        return super(RegistrationView, self).get_success_url(new_user)

    def register(self, form):
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
        cleaned_data = form.cleaned_data

        username = cleaned_data['username']
        email = cleaned_data['email']
        password = cleaned_data['password1']

        # TODO: Either add some Site fixtures or remove the Sites framework
        # if Site._meta.installed:
        #     site = Site.objects.get_current()
        # else:
        request = self.request
        site = RequestSite(request)

        should_email = should_send_user_activation(
            request, username, email, password)

        user = RegistrationProfile.objects.create_inactive_user(
            site, send_email=should_email, username=username,
            email=email, password=password, request=request)

        user.first_name = cleaned_data.get('first_name', '')
        user.last_name = cleaned_data.get('last_name', '')
        user.organization = cleaned_data.get('organization', '')
        user.allow_email_contact = cleaned_data.get(
            'allow_email_contact', False)
        user.make_info_public = cleaned_data.get(
            'make_info_public', False)
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
    def get_success_url(self, user):
        instanceusers = InstanceUser.objects.filter(user=user)

        if instanceusers.exists():
            instance = instanceusers[0].instance
            url = reverse('map', kwargs={'instance_url_name':
                                         instance.url_name})
            return (url, [], {})
        return super(ActivationView, self).get_success_url(user)


class PasswordResetView(DefaultPasswordResetView):
    # Override the value of `password_reset_done` set in the default
    # PasswordResetView
    success_url = reverse_lazy('auth_password_reset_done')

    def post(self, request, *args, **kwargs):
        form = self.get_form()

        if not form.is_valid():
            return self.form_invalid(form)

        # The built-in form doesn't consider inactive users as matching the
        # email provided by the user (so that admins can deactivate user
        # accounts without users being able to reactivate)
        #
        # If the user has an unactivated RegistrationProfile, we know they
        # weren't deactivated by an Admin
        user = User.objects.filter(email__iexact=form.cleaned_data['email'],
                                   registrationprofile__activated=False)
        if user.exists():
            form.add_error(None, ValidationError(_('This account is inactive'),
                                                 code='inactive'))
            return self.form_invalid(form)

        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)
