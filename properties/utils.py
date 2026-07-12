from django.db.models import Q

from .models import Property, PropertyImage, PropertyVideo, Notification
from .cache_utils import cache_result


PUBLIC_STATUSES = ['ready', 'under-construction', 'rent']


@cache_result(timeout=300, key_prefix='public_properties')
def get_public_properties():
    """Get public properties, excluding those from suspended/expired brokers and brokers with standalone pages."""
    from .models import Broker
    # Get active brokers with valid subscriptions and NO standalone page
    active_brokers = Broker.objects.filter(
        is_active=True,
        has_standalone_page=False
    ).select_related('user')
    
    # Filter out suspended or expired brokers
    active_broker_ids = []
    for broker in active_brokers:
        if broker.is_subscription_active():
            active_broker_ids.append(broker.id)
    
    return list(Property.objects.filter(
        status__in=PUBLIC_STATUSES,
        broker_id__in=active_broker_ids
    ).select_related().prefetch_related('gallery_images'))


def filter_properties(queryset, params):
    """Apply search filters from GET params dict."""
    
    # Handle list input (from get_public_properties)
    if isinstance(queryset, list):
        q = params.get('q', '').strip()
        city = params.get('city', '').strip()
        governorate = params.get('governorate', '').strip()
        district = params.get('district', '').strip()
        ptype = params.get('type')
        status = params.get('status')
        price_min = params.get('price_min')
        price_max = params.get('price_max')
        area_min = params.get('area_min')
        area_max = params.get('area_max')
        bedrooms = params.get('bedrooms')
        owner_name = params.get('owner_name', '').strip()
        
        filtered = queryset
        if q:
            filtered = [p for p in filtered if q.lower() in p.title.lower() or (p.location and q.lower() in p.location.lower()) or (p.city and q.lower() in p.city.lower()) or (p.district and q.lower() in p.district.lower()) or (p.description and q.lower() in p.description.lower())]
        if city:
            filtered = [p for p in filtered if p.city and city.lower() in p.city.lower()]
        if district:
            filtered = [p for p in filtered if p.district and district.lower() in p.district.lower()]
        if ptype:
            filtered = [p for p in filtered if p.type == ptype]
        if status:
            filtered = [p for p in filtered if p.status == status]
        if price_min:
            try:
                filtered = [p for p in filtered if p.price and p.price >= int(price_min)]
            except (TypeError, ValueError):
                pass
        if price_max:
            try:
                filtered = [p for p in filtered if p.price and p.price <= int(price_max)]
            except (TypeError, ValueError):
                pass
        if area_min:
            try:
                filtered = [p for p in filtered if p.area and p.area >= int(area_min)]
            except (TypeError, ValueError):
                pass
        if area_max:
            try:
                filtered = [p for p in filtered if p.area and p.area <= int(area_max)]
            except (TypeError, ValueError):
                pass
        if bedrooms:
            try:
                filtered = [p for p in filtered if p.bedrooms and p.bedrooms >= int(bedrooms)]
            except (TypeError, ValueError):
                pass
        if owner_name:
            filtered = [p for p in filtered if p.owner and (owner_name.lower() in p.owner.first_name.lower() or owner_name.lower() in p.owner.last_name.lower() or owner_name.lower() in p.owner.username.lower())]
        if params.get('has_parking'):
            filtered = [p for p in filtered if p.parking]
        if params.get('furnished'):
            filtered = [p for p in filtered if p.furnished]
        if params.get('featured') in ('1', 'true', 'on'):
            filtered = [p for p in filtered if p.is_featured]
        
        return filtered
    
    # Original QuerySet logic
    q = params.get('q', '').strip()
    if q:
        queryset = queryset.filter(
            Q(title__icontains=q)
            | Q(location__icontains=q)
            | Q(city__icontains=q)
            | Q(district__icontains=q)
            | Q(description__icontains=q)
        )

    city = params.get('city', '').strip()
    if city:
        queryset = queryset.filter(city__icontains=city)

    governorate = params.get('governorate', '').strip()
    if governorate:
        queryset = queryset.filter(
            Q(broker__governorate__icontains=governorate)
        )

    district = params.get('district', '').strip()
    if district:
        queryset = queryset.filter(district__icontains=district)

    ptype = params.get('type')
    if ptype:
        queryset = queryset.filter(type=ptype)

    status = params.get('status')
    if status:
        queryset = queryset.filter(status=status)

    price_min = params.get('price_min')
    if price_min:
        try:
            queryset = queryset.filter(price__gte=int(price_min))
        except (TypeError, ValueError):
            pass

    price_max = params.get('price_max')
    if price_max:
        try:
            queryset = queryset.filter(price__lte=int(price_max))
        except (TypeError, ValueError):
            pass

    area_min = params.get('area_min')
    if area_min:
        try:
            queryset = queryset.filter(area__gte=int(area_min))
        except (TypeError, ValueError):
            pass

    area_max = params.get('area_max')
    if area_max:
        try:
            queryset = queryset.filter(area__lte=int(area_max))
        except (TypeError, ValueError):
            pass

    bedrooms = params.get('bedrooms')
    if bedrooms:
        try:
            queryset = queryset.filter(bedrooms__gte=int(bedrooms))
        except (TypeError, ValueError):
            pass

    # Search by owner name
    owner_name = params.get('owner_name', '').strip()
    if owner_name:
        queryset = queryset.filter(
            Q(owner__first_name__icontains=owner_name)
            | Q(owner__last_name__icontains=owner_name)
            | Q(owner__username__icontains=owner_name)
        )

    if params.get('has_parking'):
        queryset = queryset.filter(parking=True)
    if params.get('furnished'):
        queryset = queryset.filter(furnished=True)
    if params.get('featured') in ('1', 'true', 'on'):
        queryset = queryset.filter(is_featured=True)

    return queryset


def sort_properties(queryset, sort_key):
    mapping = {
        'newest': ['-created_at'],
        'price_asc': ['price'],
        'price_desc': ['-price'],
        'area_asc': ['area'],
        'area_desc': ['-area'],
        'views': ['-views_count'],
    }
    
    # Handle list input (from get_public_properties)
    if isinstance(queryset, list):
        sort_fields = mapping.get(sort_key, ['-is_featured', '-is_promoted', '-created_at'])
        reverse = False
        if sort_fields[0].startswith('-'):
            reverse = True
            sort_field = sort_fields[0][1:]
        else:
            sort_field = sort_fields[0]
        
        return sorted(queryset, key=lambda x: getattr(x, sort_field, 0), reverse=reverse)
    
    return queryset.order_by(*mapping.get(sort_key, ['-is_featured', '-is_promoted', '-created_at']))


def save_gallery_images(property_obj, files, is_360_list=None):
    """Save multiple uploaded images to PropertyImage."""
    if not files:
        return
    start_order = property_obj.gallery_images.count()
    for i, f in enumerate(files):
        if not f or not getattr(f, 'name', None):
            continue
        ctype = getattr(f, 'content_type', '') or ''
        if ctype and not ctype.startswith('image/'):
            continue
        
        # Check if this is a 360° image
        is_360 = False
        if is_360_list and i < len(is_360_list):
            is_360 = is_360_list[i]
        
        PropertyImage.objects.create(
            property=property_obj,
            image=f,
            sort_order=start_order + i,
            is_primary=(start_order == 0 and i == 0 and not property_obj.image),
            is_360=is_360,
        )


def save_gallery_videos(property_obj, files):
    """Save multiple uploaded videos to PropertyVideo."""
    if not files:
        return
    start_order = property_obj.gallery_videos.count()
    for i, f in enumerate(files):
        if not f or not getattr(f, 'name', None):
            continue
        ctype = getattr(f, 'content_type', '') or ''
        if ctype and not ctype.startswith('video/'):
            continue
        PropertyVideo.objects.create(
            property=property_obj,
            video=f,
            sort_order=start_order + i,
        )


def create_notification(user, notification_type, title, message, link='', metadata=None):
    """Create a notification for a user."""
    if metadata is None:
        metadata = {}
    Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        link=link,
        metadata=metadata,
    )
