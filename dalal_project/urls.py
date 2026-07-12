from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from properties.sitemaps import PropertySitemap, StaticViewSitemap

def health_check(request):
    return JsonResponse({'status': 'healthy', 'service': 'dalal-backend'})

sitemaps = {
    'properties': PropertySitemap,
    'static': StaticViewSitemap,
}

# Swagger/OpenAPI Schema View
schema_view = get_schema_view(
    openapi.Info(
        title="دلال API",
        default_version='v1',
        description="واجهة برمجة التطبيقات لمنصة دلال العقارية",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="support@dalal.iq"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Simple test endpoint
    path('simple-test/', lambda request: JsonResponse({'status': 'ok', 'message': 'Simple test works'}), name='simple-test'),
    # Direct path to home view with error handling
    path('', lambda request: __import__('properties.views').home(request) if True else JsonResponse({'error': 'Home view failed'}), name='home'),
    # Direct test of properties.home view
    path('direct-home/', lambda request: __import__('properties.views').home(request), name='direct-home'),
    # Test if properties app is loaded
    path('check-apps/', lambda request: JsonResponse({'apps': [app.name for app in __import__('django.conf').settings.INSTALLED_APPS], 'properties': 'properties' in [app.name for app in __import__('django.conf').settings.INSTALLED_APPS]}), name='check-apps'),
    # Check database connection
    path('check-db/', lambda request: JsonResponse({'db': str(__import__('django.conf').settings.DATABASES['default']['ENGINE'])}), name='check-db'),
    # Direct home test
    path('home-test/', lambda request: __import__('properties.views').home(request), name='home-test'),
    # Direct path to home view
    path('home-direct/', lambda request: __import__('properties.views').home(request), name='home-direct'),
    # Check if properties models can be imported
    path('check-models/', lambda request: JsonResponse({'models': 'Property' in dir(__import__('properties.models'))}), name='check-models'),
    # Include properties URLs
    path('properties/', include('properties.urls')),
    path('admin/', admin.site.urls),
    path('api/', include('properties.api_urls')),
    # Social Authentication
    path('social/', include('social_django.urls', namespace='social')),
    # Health check endpoint
    path('health/', health_check, name='health-check'),
    # Test endpoint
    path('test/', lambda request: JsonResponse({'status': 'ok', 'app': 'dalal', 'time': str(timezone.now())}), name='test'),
    # Simple test page
    path('simple/', TemplateView.as_view(template_name='properties/home.html'), name='simple'),
    # API Documentation
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('swagger.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger.yaml', schema_view.without_ui(cache_timeout=0), name='schema-yaml'),
    # Sitemap and Robots
    path(
        'sitemap.xml',
        sitemap,
        {'sitemaps': sitemaps},
        name='django.contrib.sitemaps.views.sitemap',
    ),
    path(
        'robots.txt',
        TemplateView.as_view(template_name='robots.txt', content_type='text/plain'),
        name='robots',
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
