from django.contrib.sites.models import RequestSite
from django.contrib.sites.models import Site
from django.contrib.auth import get_user_model
from django.db import transaction

from registration import signals
from registration.models import RegistrationProfile, SHA1_RE
from registration.backends.default.views\
    import RegistrationView as DefaultRegistrationView
from registration.backends.default.views\
    import ActivationView as DefaultActivationView


class RegistrationView(DefaultRegistrationView):

    def create_inactive_user(self, request, username,
                             email, password):
        """
        Register a inactive user account with the specified
        username, email, and password.

        Creates a new user model object, and a new
        ``registration.models.RegistrationProfile`` tied to the new user
        and containing the activation key used for this account.
        """
        new_user = get_user_model()()
        new_user.username = username
        new_user.set_password(password)
        new_user.email = email
        new_user.is_active = False
        new_user.save_base()

        registration_profile =\
            RegistrationProfile.objects.create_profile(new_user)

        return registration_profile

    create_inactive_user =\
        transaction.commit_on_success(create_inactive_user)

    def send_activation_email(self, profile, request):
        if Site._meta.installed:
            site = Site.objects.get_current()
        else:
            site = RequestSite(request)

        profile.send_activation_email(site)

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
        profile = self.create_inactive_user(request,  # NOQA
            cleaned_data['username'],
            cleaned_data['email'],
            cleaned_data['password1'])

        self.send_activation_email(profile, request)

        signals.user_registered.send(sender=self.__class__,
                                     user=profile.user,
                                     request=request)
        return profile.user


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
