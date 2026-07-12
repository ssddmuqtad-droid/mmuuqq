from django.shortcuts import render
from django.http import JsonResponse
from .models import Property

def home(request):
    properties = Property.objects.all()
    return render(request, 'properties/home.html', {'properties': properties})

def properties_list(request):
    properties = Property.objects.all().values('id', 'title', 'price', 'location')
    return JsonResponse(list(properties), safe=False)
