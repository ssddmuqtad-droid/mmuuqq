import functools
import time

from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from .permissions import can_access_dashboard, can_manage_brokers, can_access_admin_panel


def rate_limit(key_prefix, limit=100, period=60):
    """Simple IP-based rate limiter using Django cache."""

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            if not ip:
                ip = request.META.get('REMOTE_ADDR', 'unknown')
            cache_key = f'ratelimit:{key_prefix}:{ip}'
            data = cache.get(cache_key)
            now = time.time()
            if data is None:
                cache.set(cache_key, {'count': 1, 'start': now}, period)
            else:
                if now - data['start'] > period:
                    cache.set(cache_key, {'count': 1, 'start': now}, period)
                elif data['count'] >= limit:
                    return HttpResponseForbidden('تم تجاوز عدد المحاولات. حاول لاحقاً.')
                else:
                    data['count'] += 1
                    cache.set(cache_key, data, period)
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def broker_required(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not can_access_dashboard(request.user):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def manage_brokers_required(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not can_manage_brokers(request.user):
            return HttpResponseForbidden('ليس لديك صلاحية إدارة الدلالين')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    """Decorator to require admin panel access."""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not can_access_admin_panel(request.user):
            return HttpResponseForbidden('ليس لديك صلاحية للوصول إلى لوحة الإدارة')
        return view_func(request, *args, **kwargs)
    return wrapper
