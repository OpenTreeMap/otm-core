from django.shortcuts import render

def index(request):
    context = {}
    return render(request, 'example/index.html', context)
