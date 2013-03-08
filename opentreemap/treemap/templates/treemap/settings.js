// Data structures pull from django
var otm = otm || {};
otm.settings = otm.settings || {};

otm.settings.instance = {
    'id': '{{ instance.id }}',
    'name': '{{ instance.name }}',
    'rev': '{{ instance.geo_rev_hash }}',
    'center': [{{ instance.center.x }}, {{ instance.center.y }}]
}
