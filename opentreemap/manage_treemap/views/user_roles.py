# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator, EmptyPage
from django.contrib.auth import login, authenticate
from django.db import transaction
from django.dispatch import receiver
from django.http import HttpResponse
from django.utils.translation import ugettext as _
from django.shortcuts import get_object_or_404

from registration.signals import user_registered, user_activated

from opentreemap.util import json_from_request

from treemap.lib.page_of_items import UrlParams
from treemap.models import InstanceUser, Role, User
from treemap.plugin import (can_add_user, does_user_own_instance,
                            invitation_accepted_notification_emails)

from manage_treemap.models import InstanceInvitation
from manage_treemap.lib.email import send_email


def _extract_role_updates(post):
    """
    takes a POST dict where some keys will be of
    the format "iuser_#_role" when representing
    an update to the iuser's role. Scrubs these
    keys down to iuser ids and makes a dictionary
    mapping them to the values
    """
    updates = {}
    for key, value in post.iteritems():
        if key.startswith("iuser_") and key.endswith("_role"):
            iuser_id = key[6:-5]
            updates[iuser_id] = value
    return updates


def create_user_role(request, instance):
    data = json_from_request(request)

    email = data.get('email')

    if not email:
        raise ValidationError(_("User's email is required"))

    error = can_add_user(instance)
    if isinstance(error, ValidationError):
        raise error

    try:
        user = User.objects.get(email=email)
        add_user_to_instance(request, user, instance, request.user)
    except ObjectDoesNotExist:
        invite_user_with_email_to_instance(request, email, instance)

    return user_roles_list(request, instance)


def user_roles_list(request, instance):
    page = int(request.GET.get('page', '1'))
    user_sort = request.GET.get('user_sort', 'user__username')
    invite_sort = request.GET.get('invite_sort', 'email')
    query = request.GET.get('query', '')

    def invite_context(invites):
        for invite in invites:
            yield {
                'id': str(invite.pk),
                'username': invite.email,
                'role_id': invite.role.pk,
                'role_name': invite.role.name,
                'admin': invite.admin,
            }

    def instance_user_context(instance_users):
        for instance_user in paged_instance_users:
            user = instance_user.user
            yield {
                'id': str(instance_user.pk),
                'username': user.username,
                'role_id': instance_user.role.pk,
                'role_name': instance_user.role.name,
                'admin': instance_user.admin,
                'is_owner': does_user_own_instance(instance, user)
            }

    # The secondary sort on username/email is needed to ensure consistent
    # ordering within groupings. Testing shows that things work correctly when
    # the supplied sort order is also username/email
    invited = instance.instanceinvitation_set \
        .select_related('role') \
        .filter(accepted=False) \
        .order_by(invite_sort, 'email')
    instance_users = instance.instanceuser_set \
        .select_related('role', 'user') \
        .exclude(user=User.system_user()) \
        .order_by(user_sort, 'user__username')

    if query:
        instance_users = instance_users.filter(user__username__icontains=query)

    paginator = Paginator(instance_users, 15)

    urlizer = UrlParams('user_roles_partial', instance.url_name, page=page,
                        invite_sort=invite_sort, user_sort=user_sort,
                        query=query)

    try:
        paged_instance_users = paginator.page(page)
    except EmptyPage:
        # If the page number is out of bounds, return the last page
        paged_instance_users = paginator.page(paginator.num_pages)

    return {
        'instance': instance,
        'instance_users': instance_user_context(paged_instance_users),
        'paged_instance_users': paged_instance_users,
        'invited_users': invite_context(invited),
        'instance_roles': Role.objects.filter(instance_id=instance.pk),
        'page_url': urlizer.url('invite_sort', 'user_sort', 'query'),
        'invite_sort_url': urlizer.url('page', 'user_sort', 'query'),
        'user_sort_url': urlizer.url('invite_sort', 'query'),
        'search_url': urlizer.url('invite_sort', 'user_sort'),
        'invite_sort': invite_sort,
        'user_sort': user_sort,
    }


def invite_user_with_email_to_instance(request, email, instance):
    existing_invites = InstanceInvitation.objects.filter(
        email__iexact=email, instance=instance)

    if existing_invites.exists():
        raise ValidationError(
            _("A user with email address '%s' has already been invited.") %
            email)

    invite = InstanceInvitation.objects.create(instance=instance,
                                               email=email,
                                               created_by=request.user,
                                               role=instance.default_role)

    ctxt = {'request': request,
            'instance': instance,
            'invite': invite}

    send_email('invite_to_new_user', ctxt, (email,))


def remove_invited_user_from_instance(request, instance, invite_id):
    invite = get_object_or_404(InstanceInvitation, pk=invite_id,
                               accepted=False)
    invite.delete()

    return HttpResponse(_('Removed invite'))


def add_user_to_instance(request, user, instance, admin_user):
    iuser_already_exists = (InstanceUser.objects
                            .filter(user_id=user.pk,
                                    instance=instance).exists())

    if iuser_already_exists:
        raise ValidationError(_("A user with email address '%s' has already "
                              "joined this map.") % user.email)

    iuser = InstanceUser(user_id=user.pk,
                         instance=instance,
                         role=instance.default_role)
    iuser.save_with_user(admin_user)

    ctxt = {'request': request,
            'instance': instance}

    send_email('invite_to_existing_user', ctxt, (user.email,))


def update_user_roles(request, instance):
    role_updates = json_from_request(request)

    admin_user = request.user

    for Model, key in ((InstanceUser, 'users'),
                       (InstanceInvitation, 'invites')):
        updates = role_updates.get(key, {})

        for pk, updated_info in updates.iteritems():
            model = Model.objects.get(pk=pk)

            updated_role = int(updated_info.get('role', model.role_id))
            is_admin = updated_info.get('admin', model.admin)

            if model.role_id != updated_role or is_admin != model.admin:
                model.role_id = updated_role
                model.admin = is_admin

                if Model == InstanceInvitation:
                    model.save()
                elif (does_user_own_instance(instance, model.user)
                      and not is_admin):
                    raise ValidationError('Instance owner must be admin')
                else:
                    model.save_with_user(admin_user)

    return HttpResponse(_('Updated role assignments'))


def should_send_user_activation(request, username, email, password):
    activation_key = request.GET.get('key', None)

    # Users shouldn't get an activation email if they signed up from an
    # invitation, because we already know their email is valid, provided their
    # activation_key is in the URL
    # We can only do this, however, if *both* the email and key match
    return not InstanceInvitation.objects.filter(
        email__iexact=email, activation_key=activation_key).exists()


@receiver(user_registered)
@transaction.atomic
def activate_user(sender, user, request, password=None, **kwargs):
    """
    Listens to the user registered signal from Django-registration in order to
    handle users who were invited to an instance
    """
    # Normally you would just add sender=RegistrationView to the receives
    # decorator, but that causes circular imports
    from registration_backend.views import RegistrationView
    if not issubclass(sender, RegistrationView):
        return

    invites_matching_email = InstanceInvitation.objects.filter(
        email__iexact=user.email)
    key = request.GET.get('key', None)

    # The email the user signed up with is not necessarily the same as
    # the one in their invite.  If they used a different email, we should
    # change their invite to their new email, so that they get added to their
    # invited maps after activating via email activation
    invites_matching_key = \
        InstanceInvitation.objects.filter(activation_key=key)

    if invites_matching_key:
        this_invite = invites_matching_key[0]

        # If the activation key from the user invite was present in the URL,
        # *and* the email they signed up with matches the invite email,
        # we skip email activation, log the user in, and then in
        # registration_backend.ActivationView we redirect to the map they were
        # invited to.
        if this_invite.email.lower() == user.email.lower():
            invites = set(invites_matching_email) | set(invites_matching_key)
            create_instance_users_from_invites(request, user, invites)

            user.is_active = True
            user.save_with_user(user)
            # The registration system uses both the `activated` field in
            # addition to the `User.is_active` fields. Setting `User.is_active`
            # to false after activation lets us disable an account and prevent
            # the user from reactivating it. Because of this we must also
            # update the `activated` field.
            user.registrationprofile.activated = True
            user.registrationprofile.save()

            auser = authenticate(username=user.username,
                                 password=password)
            login(request, auser)
        else:
            # We got a matching activation key, but not a matching email.
            # If we change the invite to the user's email address, then after
            # they complete activation we can add them to their invited maps
            this_invite.email = user.email
            this_invite.save()


@receiver(user_activated)
def create_instance_users(sender, user, request, *args, **kwargs):
    # Normally you would just add sender=AcitvationView to the receives
    # decorator, but that causes circular imports
    from registration_backend.views import ActivationView
    if not issubclass(sender, ActivationView):
        return
    # We sometimes receive the "user_activated" signal twice
    # Filtering for only accepted invitation prevents us from trying to create
    # duplicate instance users
    invites = InstanceInvitation.objects.filter(email__iexact=user.email,
                                                accepted=False)

    if invites:
        create_instance_users_from_invites(request, user, invites)


@transaction.atomic
def create_instance_users_from_invites(request, user, invites):
    ctxt = {'user': user,
            'request': request}
    for invite in invites:
        instance = invite.instance
        iuser = InstanceUser(user=user,
                             instance=instance,
                             role=invite.role,
                             admin=invite.admin)
        iuser.save_with_user(user)
        invite.accepted = True
        invite.save()

        # The user who created the invitation is always notified when the
        # invitation is accepted. A plugin function provides additional email
        # addresses. The concatenation of the two lists is wrapped with `set()`
        # to remove duplicates.
        emails_to_notify = set(
            [invite.created_by.email]
            + invitation_accepted_notification_emails(invite)
        )

        send_email('user_joined_instance', ctxt, emails_to_notify)
