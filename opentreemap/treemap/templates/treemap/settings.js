{% load instance_config %}
{% load i18n %}
{% load l10n %}

{% localize off %}

// Data structures pulled from django
var otm = otm || {};
otm.settings = otm.settings || {};

otm.settings.utfGrid = Object.freeze({
    mapfeatureIdKey: 'id'
});

otm.settings.urls = Object.freeze({
    'filterQueryArgumentName': 'q',
    'displayQueryArgumentName': 'show'
});

{% if not settings.TILE_HOST == None %}
    otm.settings.tileHost = "{{ settings.TILE_HOST }}";
{% endif %}

{% if request.user.is_authenticated %}
    otm.settings.loggedIn = true;
{% else %}
    otm.settings.loggedIn = false;
{% endif %}

otm.settings.loginUrl = "{% url 'login' %}?next=";

otm.settings.staticUrl = '{{ STATIC_URL }}';

otm.settings.bing_api_key = '{{ BING_API_KEY }}';

otm.settings.geocoder = Object.freeze({
    maxLocations: 20,
    errorString: '{% trans "Location not found." %}',
    reverseGeocoderErrorString: '{% trans "Unable to find an address for the location" %}',
    reverseGeocodeDistance: 200, // Meters
    threshold: 80
});

otm.settings.trans = Object.freeze({
    noStreetViewText: '{% trans "Could not load street view for this location" %}',
    treeDetails: '{% trans "Tree Details" %}',
    resourceDetails: '{{ term.Resource.singular }}{% trans " Details" %}',
    //{# this has to be broken into two sections because window.onbeforeunload has a default but confirm() does not #}
    exitWarning: '{% trans "You have begun entering data. Any unsaved changes will be lost." %}',
    exitQuestion: '{% trans "Are you sure you want to continue?" %}',
    fileExceedsMaximumFileSize: '{% trans "{0} exceeds the maximum file size of {1}" %}',
    tooltipsForDrawArea: {
        start: {
            message: '{% trans "Click the first corner of your search area" %}',
            kicker: '{% trans "ESC to cancel" %}'
        },
        cont: {
            message: '{% trans "Click to add a corner" %}'
        },
        end: {
            message: '{% trans "Click to add a corner" %}',
            kicker: '{% trans "Click first corner to finish" %}'
        }
    },
    tooltipForEditArea: [
        '{% trans "Drag a corner to move it." %}',
        '{% trans "Click a corner to delete it." %}',
        '{% trans "Enter when done. ESC to cancel." %}'
    ]
});

otm.settings.errorMessages = Object.freeze({
    '500': {
        title: "{% trans "Oops, that's not right." %}",
        message: "{% trans "We're having some trouble saving that right now.  We'll fix it very soon!" %}"
    }
});
otm.settings.errorMessages.default = otm.settings.errorMessages['500'];

otm.settings.doubleClickInterval = '{{ settings.DOUBLE_CLICK_INTERVAL }}';

{% if request.instance %}
    otm.settings.instance = Object.freeze({
        'id': '{{ request.instance.id }}',
        'url': '{{ SITE_ROOT }}{{ request.instance.url_name }}/',
        'url_name': '{{ request.instance.url_name }}',
        'name': '{{ request.instance.name }}',
        'mapFeatureTypes': {{ request.instance.map_feature_types|as_json|safe }},
        'geoRevHash': '{{ request.instance.geo_rev_hash }}',
        'universalRevHash': '{{ request.instance.universal_rev_hash }}',
        'center': {
            'x': '{{ request.instance.center.x }}',
            'y': '{{ request.instance.center.y }}'
        },
        'extent': {{ request.instance.bounds_extent_as_json|safe }},
        'bounds': {{ request.instance.bounds_as_geojson|safe }},
        'basemap': {
            'type': '{{ request.instance.basemap_type }}',
            'data': '{{ request.instance.basemap_data }}'
        },
        'customLayers': {{ request.instance.custom_layers|as_json|safe }},
        'scssQuery': "{{ request.instance.scss_query_string|safe }}",
        'primaryColor': '{{ request.instance.config|primary_color }}',
        'secondaryColor': '{{ request.instance.config|secondary_color }}',
        'supportsEcobenefits': {{ request.instance_supports_ecobenefits|yesno:"true,false" }},
        'canopyEnabled': {{ request.instance.canopy_enabled|yesno:"true,false" }},
        'canopyBoundaryCategory': '{{ request.instance.canopy_boundary_category }}'
    });
{% endif %}

{% endlocalize %}
