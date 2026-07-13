from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.views.generic import RedirectView
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
import sys

from properties.sitemaps import PropertySitemap, StaticViewSitemap

# Force rebuild - 2026-07-13-07-11 - Fix healthcheck 404
print("URLS.PY LOADED - Force rebuild 2026-07-13-07-11", file=sys.stderr)

def health_check(request):
    try:
        return JsonResponse({'status': 'healthy', 'service': 'dalal-backend', 'time': str(timezone.now())})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)

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

def simple_home(request):
    """Simple home view for testing"""
    return JsonResponse({'status': 'ok', 'message': 'Home works', 'time': str(timezone.now())})

urlpatterns = [
    # Health check endpoint (move to top for Railway healthcheck)
    path('health/', health_check, name='health-check'),
    # Include properties URLs as main path (includes dashboard/)
    path('', include('properties.urls')),
    # Admin panel
    path('admin/', admin.site.urls),
    # API endpoints
    path('api/', include('properties.api_urls')),
    # Social Authentication
    path('social/', include('social_django.urls', namespace='social')),
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
else:
    # Serve static files in production using Django's static serve (fallback)
    from django.views.static import serve
    from django.conf.urls.static import static as static_files
    urlpatterns += static_files(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static_files(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
