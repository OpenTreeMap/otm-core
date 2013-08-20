from django.views.decorators.csrf import csrf_exempt
import json


def route(**kwargs):
    @csrf_exempt
    def routed(request, **kwargs2):
        method = request.method
        req_method = kwargs[method]
        return req_method(request, **kwargs2)
    return routed


def json_from_request(request):
    """
    Accessing body throws an exception when using the Django test
    client in to make requests in unit tests.
    """
    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST
    return data
