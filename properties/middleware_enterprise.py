"""
Enterprise Security Middleware
Advanced security features for the admin dashboard
"""

import time
import logging
from collections import defaultdict
from threading import Lock

from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from django.utils import timezone

logger = logging.getLogger('properties')

# Rate limiting storage
rate_limit_storage = defaultdict(list)
rate_limit_lock = Lock()

# Get DEBUG from settings
from django.conf import settings
DEBUG = settings.DEBUG


class RateLimitMiddleware:
    """Rate limiting middleware to prevent abuse"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limit_lock = Lock()
    
    def __call__(self, request):
        # Skip rate limiting for static files and health checks
        if request.path.startswith('/static/') or request.path in ['/health/', '/health']:
            return self.get_response(request)
        
        # Get client IP
        ip = self.get_client_ip(request)
        
        # Rate limit configuration
        rate_limit = 100  # requests per minute
        window = 60  # seconds
        
        with self.rate_limit_lock:
            now = time.time()
            requests = rate_limit_storage[ip]
            
            # Remove old requests
            requests[:] = [r for r in requests if now - r < window]
            
            if len(requests) >= rate_limit:
                logger.warning(f'Rate limit exceeded for IP: {ip}')
                return JsonResponse(
                    {'error': 'Rate limit exceeded. Please try again later.'},
                    status=429
                )
            
            requests.append(now)
        
        return self.get_response(request)
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


class SecurityHeadersMiddleware:
    """Enhanced security headers middleware"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "img-src 'self' data: https: blob:; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "base-uri 'self'; "
            "object-src 'none'"
        )
        response['Content-Security-Policy'] = csp
        
        # HSTS for HTTPS
        if request.is_secure():
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        
        return response


class XSSProtectionMiddleware:
    """XSS protection middleware"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check for XSS patterns in GET parameters
        for key, value in request.GET.items():
            if self.detect_xss(value):
                logger.warning(f'XSS attempt detected from IP: {self.get_client_ip(request)}')
                return JsonResponse(
                    {'error': 'Invalid input detected'},
                    status=400
                )
        
        response = self.get_response(request)
        return response
    
    def detect_xss(self, value):
        """Detect XSS patterns in input"""
        if not isinstance(value, str):
            return False
        
        xss_patterns = [
            '<script', '</script', 'javascript:', 'onerror=',
            'onload=', 'onclick=', 'onmouseover=', '<iframe',
            '<object', '<embed', 'eval(', 'document.cookie'
        ]
        
        value_lower = value.lower()
        return any(pattern in value_lower for pattern in xss_patterns)
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


class SQLInjectionProtectionMiddleware:
    """SQL injection protection middleware"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check for SQL injection patterns
        for key, value in request.GET.items():
            if self.detect_sql_injection(value):
                logger.warning(f'SQL injection attempt detected from IP: {self.get_client_ip(request)}')
                return JsonResponse(
                    {'error': 'Invalid input detected'},
                    status=400
                )
        
        response = self.get_response(request)
        return response
    
    def detect_sql_injection(self, value):
        """Detect SQL injection patterns in input"""
        if not isinstance(value, str):
            return False
        
        sql_patterns = [
            'union select', 'drop table', 'insert into', 'delete from',
            'update set', '--', '/*', '*/', ';--', 'or 1=1', 'and 1=1',
            'exec(', 'execute(', 'xp_', 'sp_', 'waitfor delay'
        ]
        
        value_lower = value.lower()
        return any(pattern in value_lower for pattern in sql_patterns)
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


class AdminIPRestrictionMiddleware:
    """Restrict admin access to specific IPs"""

    def __init__(self, get_response):
        self.get_response = get_response
        # Allow all IPs in production for now, restrict in production if needed
        self.allowed_ips = ['127.0.0.1', '::1']  # Add your admin IPs here

    def __call__(self, request):
        # Only restrict admin panel, not dashboard
        if request.path.startswith('/admin/'):
            ip = self.get_client_ip(request)

            # In production, check against allowed IPs
            # For now, we allow all IPs in DEBUG mode
            if not self.is_allowed_ip(ip) and not DEBUG:
                logger.warning(f'Unauthorized admin access attempt from IP: {ip}')
                return JsonResponse(
                    {'error': 'Access denied'},
                    status=403
                )

        return self.get_response(request)
    
    def is_allowed_ip(self, ip):
        """Check if IP is in allowed list"""
        return ip in self.allowed_ips
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')