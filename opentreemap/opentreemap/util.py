from django.views.decorators.csrf import csrf_exempt
import json


def route(**kwargs):
    @csrf_exempt
    def routed(request, *args2, **kwargs2):
        method = request.method
        req_method = kwargs[method]
        return req_method(request, *args2, **kwargs2)
    return routed


def json_from_request(request):
    body = request.body

    if body:
        return json.loads(body)
    else:
        return None

def merge_view_contexts(viewfns):
    def wrapped(*args, **kwargs):
        context = {}
        for viewfn in viewfns:
            context.update(viewfn(*args, **kwargs))

        return context
    return wrapped
