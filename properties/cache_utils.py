"""
Cache utilities for performance optimization
"""
from django.core.cache import cache
from django.conf import settings
from functools import wraps
import hashlib
import json


def cache_result(timeout=300, key_prefix=None):
    """
    Decorator to cache function results
    Usage:
        @cache_result(timeout=300, key_prefix='property_list')
        def get_featured_properties():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = key_prefix or func.__name__
            
            # Add args and kwargs to key for uniqueness
            if args or kwargs:
                args_str = json.dumps([str(arg) for arg in args], sort_keys=True)
                kwargs_str = json.dumps(kwargs, sort_keys=True)
                key_hash = hashlib.md5(f"{args_str}{kwargs_str}".encode()).hexdigest()[:8]
                cache_key = f"{cache_key}_{key_hash}"
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result
        return wrapper
    return decorator


def cache_property_list(timeout=300):
    """Cache property list results"""
    return cache_result(timeout=timeout, key_prefix='property_list')


def cache_property_detail(timeout=600):
    """Cache individual property details"""
    return cache_result(timeout=timeout, key_prefix='property_detail')


def cache_featured_properties(timeout=300):
    """Cache featured properties"""
    return cache_result(timeout=timeout, key_prefix='featured_properties')


def cache_latest_properties(timeout=300):
    """Cache latest properties"""
    return cache_result(timeout=timeout, key_prefix='latest_properties')


def cache_site_settings(timeout=3600):
    """Cache site settings for 1 hour"""
    return cache_result(timeout=timeout, key_prefix='site_settings')


def invalidate_property_cache(property_id=None):
    """
    Invalidate property-related cache
    If property_id is provided, only invalidate that property's cache
    Otherwise, invalidate all property cache
    """
    if property_id:
        # Invalidate specific property cache
        cache_keys = [
            f'property_detail_{property_id}',
            f'property_list_{property_id}',
        ]
        for key in cache_keys:
            cache.delete(key)
    else:
        # Invalidate all property cache (delete_pattern not available in default cache)
        # For Redis cache backend, you can use cache.delete_pattern
        # For now, we'll delete known keys
        cache.delete('featured_properties')
        cache.delete('latest_properties')
        cache.delete('property_list')
        # Note: For full invalidation with Redis, use: cache.delete_pattern('property_*')


def invalidate_site_settings_cache():
    """Invalidate site settings cache"""
    cache.delete('site_settings')


def cache_query_result(queryset, timeout=300, key_prefix='query'):
    """
    Cache queryset results
    Useful for complex queries that don't change frequently
    """
    # Generate cache key based on query
    query_str = str(queryset.query)
    key_hash = hashlib.md5(query_str.encode()).hexdigest()[:8]
    cache_key = f"{key_prefix}_{key_hash}"
    
    # Try to get from cache
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    # Execute query and cache result
    result = list(queryset)
    cache.set(cache_key, result, timeout)
    return result


def get_cached_count(queryset, timeout=300):
    """
    Cache count results for large querysets
    """
    query_str = str(queryset.query)
    key_hash = hashlib.md5(query_str.encode()).hexdigest()[:8]
    cache_key = f"count_{key_hash}"
    
    cached_count = cache.get(cache_key)
    if cached_count is not None:
        return cached_count
    
    count = queryset.count()
    cache.set(cache_key, count, timeout)
    return count


class CacheViewMixin:
    """
    Mixin for views to add caching capabilities
    """
    cache_timeout = 300
    cache_key_prefix = None
    
    def get_cache_key(self):
        """Generate cache key for this view"""
        if self.cache_key_prefix:
            return self.cache_key_prefix
        return f"{self.__class__.__name__}_{self.request.path}"
    
    def get_from_cache(self):
        """Try to get response from cache"""
        cache_key = self.get_cache_key()
        return cache.get(cache_key)
    
    def set_to_cache(self, response):
        """Cache the response"""
        cache_key = self.get_cache_key()
        cache.set(cache_key, response, self.cache_timeout)
        return response
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to add caching"""
        # Only cache GET requests
        if request.method == 'GET':
            cached_response = self.get_from_cache()
            if cached_response:
                return cached_response
        
        response = super().dispatch(request, *args, **kwargs)
        
        if request.method == 'GET':
            self.set_to_cache(response)
        
        return response


def cache_broker_list(timeout=300):
    """Cache broker list results"""
    return cache_result(timeout=timeout, key_prefix='broker_list')


def cache_auction_list(timeout=60):
    """Cache auction list results (shorter timeout for real-time updates)"""
    return cache_result(timeout=timeout, key_prefix='auction_list')


def cache_statistics(timeout=600):
    """Cache statistics results"""
    return cache_result(timeout=timeout, key_prefix='statistics')
