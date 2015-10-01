{% load instance_config %}
{% load i18n %}
{% load l10n %}

{% localize off %}

// Data structures pulled from django
var otm = otm || {};
otm.settings = otm.settings || {};

otm.settings.utfGrid = {
    mapfeatureIdKey: 'id'
}

otm.settings.urls = {
    'filterQueryArgumentName': 'q',
    'displayQueryArgumentName': 'show'
}

{% if not settings.TILE_HOST = None %}
    otm.settings.tileHost = "{{ settings.TILE_HOST }}";
{% endif %}

{% if request.user.is_authenticated %}
    otm.settings.loggedIn = true;
{% else %}
    otm.settings.loggedIn = false;
{% endif %}

otm.settings.loginUrl = "{% url 'django.contrib.auth.views.login' %}?next=";

otm.settings.staticUrl = '{{ STATIC_URL }}';

otm.settings.exportCheckUrl = '{{ SITE_ROOT }}{{ request.instance.url_name }}/export/check';

otm.settings.geocoder = {
    maxLocations: 20,
    errorString: '{% trans "That address was not found near this map. You may need to include a city and state." %}',
    reverseGeocoderErrorString: '{% trans "Unable to find an address for the location" %}',
    reverseGeocodeDistance: 200, // Meters
    threshold: 80
};

otm.settings.trans = {
    noStreetViewText: '{% trans "Could not load street view for this location" %}',
    treeDetails: '{% trans "Tree Details" %}',
    resourceDetails: '{{ term.Resource.singular }}{% trans " Details" %}',
    {# this has to be broken into two sections because window.onbeforeunload has a default but confirm() does not #}
    exitWarning: '{% trans "You have begun entering data. Any unsaved changes will be lost." %}',
    exitQuestion: '{% trans "Are you sure you want to continue?" %}'
}

otm.settings.errorMessages = {
    '500': {
        title: "{% trans "Oops, that's not right." %}",
        message: "{% trans "We're having some trouble saving that right now.  We'll fix it very soon!" %}"
    }
}
otm.settings.errorMessages.default = otm.settings.errorMessages['500'];

otm.settings.doubleClickInterval = '{{ settings.DOUBLE_CLICK_INTERVAL }}';

{% if request.instance %}
    otm.settings.instance = {
        'id': '{{ request.instance.id }}',
        'url': '{{ SITE_ROOT }}{{ request.instance.url_name }}/',
        'mapUrl': "{% url 'map' instance_url_name=last_instance.url_name %}",
        'polygonForPointUrl': "{% url 'polygon_for_point' instance_url_name=last_instance.url_name %}",
        'addTreeUrl': "{% url 'map' instance_url_name=last_instance.url_name %}{{ settings.ADD_TREE_URL_HASH }}",
        'name': '{{ request.instance.name }}',
        'rev': '{{ request.instance.geo_rev_hash }}',
        'center': {
            'x': '{{ request.instance.center.x }}',
            'y': '{{ request.instance.center.y }}'
        },
        'extent': {{ request.instance.extent_as_json|safe }},
        'bounds': {{ request.instance.bounds_as_geojson|safe }},
        'basemap': {
            'type': '{{ request.instance.basemap_type }}',
            'data': '{{ request.instance.basemap_data }}',
            'bing_api_key': '{{ BING_API_KEY }}'
        },
        'primaryColor': '{{ request.instance.config|primary_color }}',
        'secondaryColor': '{{ request.instance.config|secondary_color }}',
        'supportsEcobenefits': {{ request.instance_supports_ecobenefits|yesno:"true,false" }}
    }
{% endif %}

{% endlocalize %}
