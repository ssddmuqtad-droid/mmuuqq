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
