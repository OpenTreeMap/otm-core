from django import template

register = template.Library()

last_request_and_thumbprint = (None, None)

# Some pages contain many species autocompletes. To avoid re-querying
# we hang on to the last request and thumbprint. This isn't thread-safe,
# but the the worst that could happen with a data race is an extra query.

@register.filter
def species_thumbprint(request):
    global last_request_and_thumbprint

    last_request, last_thumbprint = last_request_and_thumbprint

    if request == last_request:
        thumbprint = last_thumbprint
    else:
        thumbprint = request.instance.species_thumbprint
        last_request_and_thumbprint = (request, thumbprint)

    return thumbprint
