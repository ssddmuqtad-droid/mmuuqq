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

from .models import Property, PropertyImage, PropertyVideo, PropertyDocument, SiteSettings
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
            'category': prop.category,
            'type': prop.type,
            'type_display': prop.get_type_display(),
            'status': prop.status,
            'status_display': prop.get_status_display(),
            'district': prop.district,
            'street': prop.street,
            'location': prop.location,
            'full_location': prop.full_location,
            'area': prop.area,
            'total_area': prop.total_area,
            'building_area': prop.building_area,
            'price': prop.price,
            'price_formatted': prop.price_formatted,
            'currency': prop.currency,
            'original_price': prop.original_price,
            'negotiable': prop.negotiable,
            'description': prop.description,
            'phone': prop.phone,
            'bedrooms': prop.bedrooms,
            'bathrooms': prop.bathrooms,
            'living_rooms': prop.living_rooms,
            'dining_rooms': prop.dining_rooms,
            'kitchens': prop.kitchens,
            'balconies': prop.balconies,
            'parking_spaces': prop.parking_spaces,
            'floors': prop.floors,
            'total_floors': prop.total_floors,
            'floor_number': prop.floor_number,
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
            # Hotel/Resort fields
            'hotel_stars': prop.hotel_stars,
            'hotel_rating': float(prop.hotel_rating) if prop.hotel_rating else None,
            'hotel_rooms': prop.hotel_rooms,
            'resort_capacity': prop.resort_capacity,
            # Outside Iraq location
            'country': prop.country.name_ar if prop.country else None,
            'city_outside': prop.city_outside.name_ar if prop.city_outside else None,
            # Virtual tour
            'virtual_tour_url': prop.virtual_tour_url,
            'vr_tour_url': prop.vr_tour_url,
            'ar_available': prop.ar_available,
            # Live stream
            'live_stream_enabled': prop.live_stream_enabled,
            'live_stream_url': prop.live_stream_url,
            'live_stream_status': prop.live_stream_status,
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
            'category': property_obj.category,
            'type': property_obj.type,
            'type_display': property_obj.get_type_display(),
            'status': property_obj.status,
            'status_display': property_obj.get_status_display(),
            'district': property_obj.district,
            'street': property_obj.street,
            'location': property_obj.location,
            'full_location': property_obj.full_location,
            'area': property_obj.area,
            'total_area': property_obj.total_area,
            'building_area': property_obj.building_area,
            'price': property_obj.price,
            'price_formatted': property_obj.price_formatted,
            'currency': property_obj.currency,
            'original_price': property_obj.original_price,
            'negotiable': property_obj.negotiable,
            'description': property_obj.description,
            'phone': property_obj.phone,
            'bedrooms': property_obj.bedrooms,
            'bathrooms': property_obj.bathrooms,
            'living_rooms': property_obj.living_rooms,
            'dining_rooms': property_obj.dining_rooms,
            'kitchens': property_obj.kitchens,
            'balconies': property_obj.balconies,
            'parking_spaces': property_obj.parking_spaces,
            'floors': property_obj.floors,
            'total_floors': property_obj.total_floors,
            'floor_number': property_obj.floor_number,
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
            # Hotel/Resort fields
            'hotel_stars': property_obj.hotel_stars,
            'hotel_rating': float(property_obj.hotel_rating) if property_obj.hotel_rating else None,
            'hotel_rooms': property_obj.hotel_rooms,
            'hotel_suites': property_obj.hotel_suites,
            'hotel_family_rooms': property_obj.hotel_family_rooms,
            'has_restaurant': property_obj.has_restaurant,
            'has_cafe': property_obj.has_cafe,
            'has_swimming_pool': property_obj.has_swimming_pool,
            'has_gym': property_obj.has_gym,
            'has_spa': property_obj.has_spa,
            'has_conference_hall': property_obj.has_conference_hall,
            'has_wifi': property_obj.has_wifi,
            'has_parking': property_obj.has_parking,
            'has_room_service': property_obj.has_room_service,
            'has_laundry': property_obj.has_laundry,
            'has_airport_shuttle': property_obj.has_airport_shuttle,
            'resort_capacity': property_obj.resort_capacity,
            'resort_activities': property_obj.resort_activities,
            'booking_available': property_obj.booking_available,
            'booking_url': property_obj.booking_url,
            'min_booking_duration': property_obj.min_booking_duration,
            'max_booking_duration': property_obj.max_booking_duration,
            # Outside Iraq location
            'country': property_obj.country.name_ar if property_obj.country else None,
            'city_outside': property_obj.city_outside.name_ar if property_obj.city_outside else None,
            'area_outside': property_obj.area_outside.name_ar if property_obj.area_outside else None,
            'postal_code': property_obj.postal_code,
            'taxes': float(property_obj.taxes) if property_obj.taxes else None,
            'registration_fees': float(property_obj.registration_fees) if property_obj.registration_fees else None,
            'foreign_ownership_laws': property_obj.foreign_ownership_laws,
            # Virtual tour
            'virtual_tour_url': property_obj.virtual_tour_url,
            'vr_tour_url': property_obj.vr_tour_url,
            'ar_available': property_obj.ar_available,
            'qr_code': property_obj.qr_code.url if property_obj.qr_code else None,
            'short_share_code': property_obj.short_share_code,
            # Live stream
            'live_stream_enabled': property_obj.live_stream_enabled,
            'live_stream_url': property_obj.live_stream_url,
            'live_stream_scheduled': property_obj.live_stream_scheduled.isoformat() if property_obj.live_stream_scheduled else None,
            'live_stream_status': property_obj.live_stream_status,
            # AI features
            'ai_generated_description': property_obj.ai_generated_description,
            'ai_suggested_price': property_obj.ai_suggested_price,
            'ai_keywords': property_obj.ai_keywords,
            'ai_image_enhanced': property_obj.ai_image_enhanced,
            # Additional location details
            'nearest_landmark': property_obj.nearest_landmark,
            'distance_to_city_center': property_obj.distance_to_city_center,
            'distance_to_airport': property_obj.distance_to_airport,
            # Additional property details
            'property_age': property_obj.property_age,
            'last_renovation': property_obj.last_renovation,
            'maintenance_fee': float(property_obj.maintenance_fee) if property_obj.maintenance_fee else None,
            'hoa_fee': float(property_obj.hoa_fee) if property_obj.hoa_fee else None,
            # Accessibility
            'wheelchair_accessible': property_obj.wheelchair_accessible,
            'has_ramp': property_obj.has_ramp,
            'has_elevator_accessibility': property_obj.has_elevator_accessibility,
            # Green features
            'energy_efficient': property_obj.energy_efficient,
            'has_green_building_cert': property_obj.has_green_building_cert,
            'has_smart_home': property_obj.has_smart_home,
            'has_double_glazing': property_obj.has_double_glazing,
            'has_insulation': property_obj.has_insulation,
            # Parking and view
            'parking_type': property_obj.parking_type,
            'view_type': property_obj.view_type,
            # Amenities
            'has_pool': property_obj.has_pool,
            'has_garden': property_obj.has_garden,
            'has_elevator': property_obj.has_elevator,
            'has_generator': property_obj.has_generator,
            'has_national_electricity': property_obj.has_national_electricity,
            'has_water': property_obj.has_water,
            'has_internet': property_obj.has_internet,
            'has_sewerage': property_obj.has_sewerage,
            'has_heating': property_obj.has_heating,
            'has_cooling': property_obj.has_cooling,
            'has_solar_power': property_obj.has_solar_power,
            'has_security_system': property_obj.has_security_system,
            'has_cctv': property_obj.has_cctv,
            'has_alarm': property_obj.has_alarm,
            # Videos and documents
            'videos': [{'url': v.video.url, 'caption': v.caption, 'type': v.video_type} for v in property_obj.gallery_videos.all()],
            'documents': [{'title': d.title, 'type': d.document_type, 'url': d.file.url} for d in property_obj.documents.all()],
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