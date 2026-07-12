from django.urls import path
from . import views

app_name = 'properties'

urlpatterns = [
    path('', views.home, name='home'),
    path('api/properties/', views.properties_list, name='properties_list'),
]
