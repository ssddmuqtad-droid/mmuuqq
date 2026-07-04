from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.views.generic import TemplateView
from django.http import JsonResponse
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
    path('admin/', admin.site.urls),
    path('', include('properties.urls')),
    path('api/', include('properties.api_urls')),
    # Health check endpoint
    path('health/', health_check, name='health-check'),
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
