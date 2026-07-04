"""
JSON API endpoints for Next.js frontend.
Provides headless API access while maintaining existing Django templates.
"""

import json
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q
from django.core.cache import cache
from django.utils.decorators import method_decorator
from functools import wraps

from .models import Property, PropertyImage, SiteSettings
from .utils import get_public_properties, filter_properties, sort_properties


def rate_limit(limit=100, period=60):
    """
    Rate limiting decorator to prevent API abuse.
    limit: maximum number of requests
    period: time period in seconds
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Get client IP
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR', 'unknown')
            
            # Create cache key
            cache_key = f'rate_limit_{ip}_{view_func.__name__}'
            
            # Get current count
            count = cache.get(cache_key, 0)
            
            if count >= limit:
                return JsonResponse({
                    'error': 'Too many requests',
                    'message': f'Rate limit exceeded. Maximum {limit} requests per {period} seconds.'
                }, status=429)
            
            # Increment count
            cache.set(cache_key, count + 1, period)
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


@require_http_methods(["GET"])
@rate_limit(limit=200, period=60)
def api_health(request):
    """Health check endpoint for API."""
    return JsonResponse({
        'status': 'healthy',
        'version': '1.0.0',
        'timestamp': '2025-01-01'
    })


@require_http_methods(["GET"])
@rate_limit(limit=100, period=60)
def api_properties(request):
    """
    Get properties with filtering, pagination, and sorting.
    Query params:
    - page: page number (default: 1)
    - page_size: items per page (default: 12)
    - district, street, type, status: filters
    - price_min, price_max: price range
    - area_min, area_max: area range
    - bedrooms: number of bedrooms
    - sort: sort order (newest, price_asc, price_desc, popular)
    - q: search query
    - featured: filter featured properties (1/0)
    """
    properties = get_public_properties()
    properties = filter_properties(properties, request.GET)
    properties = sort_properties(request.GET.get('sort'))
    
    page_size = int(request.GET.get('page_size', 12))
    page_number = int(request.GET.get('page', 1))
    
    paginator = Paginator(properties, page_size)
    page_obj = paginator.get_page(page_number)
    
    # Serialize properties
    properties_data = []
    for prop in page_obj:
        properties_data.append({
            'id': prop.id,
            'title': prop.display_title,
            'slug': prop.slug,
            'type': prop.type,
            'type_display': prop.get_type_display(),
            'status': prop.status,
            'status_display': prop.get_status_display(),
            'district': prop.district,
            'street': prop.street,
            'location': prop.location,
            'full_location': prop.full_location,
            'area': prop.area,
            'price': prop.price,
            'price_formatted': prop.price_formatted,
            'description': prop.description,
            'phone': prop.phone,
            'bedrooms': prop.bedrooms,
            'bathrooms': prop.bathrooms,
            'floors': prop.floors,
            'year_built': prop.year_built,
            'parking': prop.parking,
            'furnished': prop.furnished,
            'latitude': float(prop.latitude) if prop.latitude else None,
            'longitude': float(prop.longitude) if prop.longitude else None,
            'main_image': prop.get_main_image(),
            'images': prop.get_all_images(),
            'is_featured': prop.is_featured,
            'is_promoted': prop.is_promoted,
            'views_count': prop.views_count,
            'created_at': prop.created_at.isoformat(),
            'updated_at': prop.updated_at.isoformat(),
            'url': prop.get_absolute_url(),
        })
    
    return JsonResponse({
        'properties': properties_data,
        'pagination': {
            'page': page_number,
            'page_size': page_size,
            'total_items': paginator.count,
            'total_pages': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }
    })


@require_http_methods(["GET"])
@rate_limit(limit=100, period=60)
def api_property_detail(request, slug):
    """Get detailed information for a single property."""
    property_obj = get_object_or_404(Property, slug=slug)
    
    # Increment views
    property_obj.increment_views()
    
    # Get related properties
    related = get_public_properties().filter(
        Q(district=property_obj.district) | Q(type=property_obj.type)
    ).exclude(pk=property_obj.pk)[:4]
    
    # Serialize related properties
    related_data = []
    for prop in related:
        related_data.append({
            'id': prop.id,
            'title': prop.display_title,
            'slug': prop.slug,
            'type': prop.type,
            'type_display': prop.get_type_display(),
            'district': prop.district,
            'area': prop.area,
            'price': prop.price,
            'price_formatted': prop.price_formatted,
            'main_image': prop.get_main_image(),
            'is_featured': prop.is_featured,
        })
    
    return JsonResponse({
        'property': {
            'id': property_obj.id,
            'title': property_obj.display_title,
            'slug': property_obj.slug,
            'type': property_obj.type,
            'type_display': property_obj.get_type_display(),
            'status': property_obj.status,
            'status_display': property_obj.get_status_display(),
            'district': property_obj.district,
            'street': property_obj.street,
            'location': property_obj.location,
            'full_location': property_obj.full_location,
            'area': property_obj.area,
            'price': property_obj.price,
            'price_formatted': property_obj.price_formatted,
            'description': property_obj.description,
            'phone': property_obj.phone,
            'bedrooms': property_obj.bedrooms,
            'bathrooms': property_obj.bathrooms,
            'floors': property_obj.floors,
            'year_built': property_obj.year_built,
            'parking': property_obj.parking,
            'furnished': property_obj.furnished,
            'latitude': float(property_obj.latitude) if property_obj.latitude else None,
            'longitude': float(property_obj.longitude) if property_obj.longitude else None,
            'main_image': property_obj.get_main_image(),
            'images': property_obj.get_all_images(),
            'is_featured': property_obj.is_featured,
            'is_promoted': property_obj.is_promoted,
            'promotion_until': property_obj.promotion_until.isoformat() if property_obj.promotion_until else None,
            'views_count': property_obj.views_count,
            'created_at': property_obj.created_at.isoformat(),
            'updated_at': property_obj.updated_at.isoformat(),
            'url': property_obj.get_absolute_url(),
            'has_map': property_obj.has_map(),
        },
        'related_properties': related_data,
    })


@require_http_methods(["GET"])
@rate_limit(limit=100, period=60)
def api_featured_properties(request):
    """Get featured properties."""
    featured = get_public_properties().filter(is_featured=True)[:6]
    
    properties_data = []
    for prop in featured:
        properties_data.append({
            'id': prop.id,
            'title': prop.display_title,
            'slug': prop.slug,
            'type': prop.type,
            'type_display': prop.get_type_display(),
            'city': prop.city,
            'area': prop.area,
            'price': prop.price,
            'price_formatted': prop.price_formatted,
            'main_image': prop.get_main_image(),
            'is_featured': prop.is_featured,
        })
    
    return JsonResponse({'properties': properties_data})


@require_http_methods(["GET"])
@rate_limit(limit=100, period=60)
def api_site_settings(request):
    """Get site settings and configuration."""
    settings = SiteSettings.get_solo()
    
    return JsonResponse({
        'site_name': settings.site_name,
        'tagline': settings.tagline,
        'broker_phone': settings.broker_phone,
        'broker_email': settings.broker_email,
        'broker_address': settings.broker_address,
        'whatsapp': settings.whatsapp,
        'about_title': settings.about_title,
        'about_content': settings.about_content,
        'mission': settings.mission,
        'facebook_url': settings.facebook_url,
        'instagram_url': settings.instagram_url,
        'meta_description': settings.meta_description,
    })


@require_http_methods(["GET"])
@rate_limit(limit=50, period=60)
def api_search_suggestions(request):
    """Get search suggestions for autocomplete."""
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'suggestions': []})
    
    properties = get_public_properties().filter(
        Q(title__icontains=query) |
        Q(district__icontains=query) |
        Q(street__icontains=query) |
        Q(location__icontains=query)
    )[:10]
    
    suggestions = []
    for prop in properties:
        suggestions.append({
            'id': prop.id,
            'title': prop.display_title,
            'district': prop.district,
            'type': prop.get_type_display(),
            'slug': prop.slug,
        })
    
    return JsonResponse({'suggestions': suggestions})


@require_http_methods(["GET"])
@rate_limit(limit=50, period=60)
def api_statistics(request):
    """Get site statistics for dashboard."""
    from django.db.models import Count, Sum
    
    properties = get_public_properties()
    
    stats = {
        'total_properties': properties.count(),
        'featured_properties': properties.filter(is_featured=True).count(),
        'promoted_properties': properties.filter(is_promoted=True).count(),
        'total_views': properties.aggregate(total=Sum('views_count'))['total'] or 0,
        'properties_by_type': dict(
            properties.values('type').annotate(count=Count('id')).values_list('type', 'count')
        ),
        'properties_by_district': dict(
            properties.values('district').annotate(count=Count('id')).values_list('district', 'count')
        ),
    }
    
    return JsonResponse(stats)