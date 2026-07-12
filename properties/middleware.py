class HealthCheckMiddleware:
    """Bypass all middleware for health check endpoints."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in ['/health/', '/health']:
            from django.http import JsonResponse
            from django.utils import timezone
            import os
            
            # Simple health check without database verification
            return JsonResponse({
                'status': 'healthy',
                'service': 'dalal-backend',
                'version': os.getenv('RAILWAY_GIT_COMMIT_SHA', 'unknown'),
                'timestamp': timezone.now().isoformat(),
            }, status=200)
        
        # Log all requests for debugging
        import logging
        logger = logging.getLogger('django.request')
        logger.info(f"HealthCheckMiddleware: Processing {request.path} - Host: {request.get_host()}")
        
        return self.get_response(request)


class SecurityHeadersMiddleware:
    """Add security headers for production."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Content Security Policy - improved security
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' https://unpkg.com https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com https://fonts.googleapis.com",
            "img-src 'self' data: https: blob:",
            "font-src 'self' data: https://cdn.jsdelivr.net https://fonts.gstatic.com",
            "connect-src 'self' https://unpkg.com https://cdn.jsdelivr.net https://*.tile.openstreetmap.org",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "base-uri 'self'",
            "object-src 'none'",
        ]
        response['Content-Security-Policy'] = '; '.join(csp_directives)
        
        if request.is_secure():
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        return response


class MaintenanceModeMiddleware:
    """Middleware to handle maintenance mode."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Paths that should always be accessible during maintenance
        allowed_paths = [
            '/admin/',
            '/login/',
            '/maintenance/',
            '/health/',
            '/health',
            '/static/',
            '/media/',
        ]

        # Check if path is allowed
        for path in allowed_paths:
            if request.path.startswith(path):
                return self.get_response(request)

        # Check if user is authenticated and is superuser (after AuthenticationMiddleware)
        if hasattr(request, 'user') and request.user.is_authenticated and request.user.is_superuser:
            return self.get_response(request)

        # Check maintenance mode status
        try:
            from .models import SiteSettings
            settings = SiteSettings.get_solo()
        except Exception:
            # If SiteSettings doesn't exist or database error, skip maintenance check
            return self.get_response(request)

        if settings.maintenance_mode:
            # Check if admins are allowed during maintenance
            if settings.allow_admins_during_maintenance:
                if hasattr(request, 'user') and request.user.is_authenticated and request.user.is_superuser:
                    return self.get_response(request)

            # Show maintenance page
            from django.shortcuts import render
            return render(request, 'properties/maintenance.html', {
                'maintenance_message': settings.maintenance_message,
                'maintenance_end_time': settings.maintenance_end_time,
                'site_settings': settings,
            }, status=503)

        return self.get_response(request)


class SubscriptionCheckMiddleware:
    """Middleware to check subscription status for broker operations."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Paths that require subscription check
        protected_paths = [
            '/dashboard/add-property/',
            '/dashboard/edit-property/',
            '/dashboard/delete-property/',
            '/dashboard/feature-property/',
            '/dashboard/promote-property/',
        ]

        # Skip subscription check for non-protected paths
        if not any(request.path.startswith(path) for path in protected_paths):
            return self.get_response(request)

        # Skip if user is not authenticated
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return self.get_response(request)

        # Skip for superuser/admin
        if request.user.is_superuser:
            return self.get_response(request)

        # Check subscription for brokers
        from .permissions import get_broker
        broker = get_broker(request.user)
        
        if broker:
            # Auto-check subscription status
            broker.check_subscription_status()
            
            # If subscription is expired or suspended, block access
            if not broker.is_subscription_active():
                from django.shortcuts import redirect
                from django.contrib import messages
                
                if broker.is_suspended:
                    messages.error(request, 'تم تعطيل حسابك مؤقتاً بسبب انتهاء الاشتراك. يرجى تجديد الاشتراك للاستمرار.')
                else:
                    messages.error(request, 'انتهى اشتراكك. يرجى تجديد الاشتراك للاستمرار.')
                
                return redirect('dashboard')

        return self.get_response(request)

