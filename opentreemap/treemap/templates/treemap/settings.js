// Data structures pull from django
var otm = otm || {};
otm.settings = otm.settings || {};

otm.settings.utfGrid = {
    plotIdKey: 'the_plot_id'
}

otm.settings.urls = {
    'filterQueryArgumentName': 'q'
}

{% if request.instance %}
    otm.settings.instance = {
        'id': '{{ request.instance.id }}',
        'name': '{{ request.instance.name }}',
        'rev': '{{ request.instance.geo_rev_hash }}',
        'center': [{{ request.instance.center.x }}, {{ request.instance.center.y }}],
        'basemap': {
            'type': '{{ request.instance.basemap_type }}',
            'data': '{{ request.instance.basemap_data }}',
            'bing_api_key': '{{ BING_API_KEY }}'
        }
    }
{% endif %}