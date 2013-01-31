from django.shortcuts import render_to_response
from django.template import RequestContext

from treemap.models import Instance

def index(request):
    instance = Instance.objects.get(pk=request.GET['instance'])
    return render_to_response('treemap/index.html',RequestContext(request,{
        'instance': instance
    }))

def settings(request):
    instance = Instance.objects.get(pk=request.GET['instance'])
    return render_to_response('treemap/settings.js',RequestContext(request,{
        'instance': instance
    }))
