from django.conf.urls import patterns
from django.conf.urls import include
from django.conf.urls import url
from django.views.generic.base import TemplateView


from views import RegistrationView, ActivationView, LoginForm


urlpatterns = patterns('',
    url(r'^login/?$',
        'django.contrib.auth.views.login',
        {'authentication_form': LoginForm}),
    url(r'^activation-complete/$',
       TemplateView.as_view(template_name='registration/activation_complete.html'),  # NOQA
       name='registration_activation_complete'),
    # Activation keys get matched by \w+ instead of the more specific
    # [a-fA-F0-9]{40} because a bad activation key should still get
    # to the view; that way it can return a sensible "invalid key"
    # message instead of a confusing 404.
    url(r'^activate/(?P<activation_key>\w+)/$',
       ActivationView.as_view(),
       name='registration_activate'),
    url(r'^register/$',
        RegistrationView.as_view(),
       name='registration_register'),
    url(r'^register/complete/$',
       TemplateView.as_view(template_name='registration/registration_complete.html'),  # NOQA
       name='registration_complete'),
    url(r'^register/closed/$',
       TemplateView.as_view(template_name='registration/registration_closed.html'),  # NOQA
       name='registration_disallowed'),
    (r'', include('registration.auth_urls')),
    )  # NOQA
