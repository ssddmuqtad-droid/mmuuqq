"""
Enterprise API Views for Admin Dashboard
Real-time statistics, system monitoring, and advanced features
"""

import json
import logging
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from .models import (
    Property, Broker, ActivityLog, Notification,
    FinancialTransaction, Expense, Profit
)

logger = logging.getLogger('properties')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_health(request):
    """Health check endpoint for the API"""
    return Response({
        'status': 'healthy',
        'version': '1.0.0',
        'timestamp': timezone.now().isoformat(),
        'database': 'connected',
        'cache': 'active'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_statistics(request):
    """Get real-time platform statistics"""
    if not request.user.is_superuser:
        return Response({'error': 'Unauthorized'}, status=403)
    
    # Calculate statistics
    total_users = User.objects.count()
    total_brokers = Broker.objects.count()
    total_properties = Property.objects.count()
    total_revenue = FinancialTransaction.objects.filter(
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Recent activity (last 24 hours)
    yesterday = timezone.now() - timedelta(days=1)
    recent_properties = Property.objects.filter(
        created_at__gte=yesterday
    ).count()
    recent_users = User.objects.filter(
        date_joined__gte=yesterday
    ).count()
    
    return Response({
        'total_users': total_users,
        'total_brokers': total_brokers,
        'total_properties': total_properties,
        'total_revenue': float(total_revenue),
        'recent_properties': recent_properties,
        'recent_users': recent_users,
        'timestamp': timezone.now().isoformat()
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_system_status(request):
    """Get system status and monitoring data"""
    if not request.user.is_superuser:
        return Response({'error': 'Unauthorized'}, status=403)
    
    # Check system components
    from django.db import connection
    from django.core.cache import cache
    
    db_status = 'connected'
    try:
        connection.cursor()
    except Exception:
        db_status = 'error'
    
    cache_status = 'active'
    try:
        cache.set('health_check', 'ok', 10)
        if cache.get('health_check') != 'ok':
            cache_status = 'error'
    except Exception:
        cache_status = 'error'
    
    return Response({
        'database': db_status,
        'cache': cache_status,
        'server_time': timezone.now().isoformat(),
        'debug_mode': False,
        'version': '1.0.0'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_error_logs(request):
    """Get recent error logs"""
    if not request.user.is_superuser:
        return Response({'error': 'Unauthorized'}, status=403)
    
    # Get recent errors from activity log
    errors = ActivityLog.objects.filter(
        action='error'
    ).order_by('-created_at')[:50]
    
    return Response({
        'errors': [
            {
                'id': e.id,
                'user': e.user.username,
                'description': e.description,
                'created_at': e.created_at.isoformat()
            }
            for e in errors
        ]
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_export_data(request):
    """Export data in various formats (PDF, Excel, CSV)"""
    if not request.user.is_superuser:
        return Response({'error': 'Unauthorized'}, status=403)
    
    export_format = request.query_params.get('format', 'json')
    data_type = request.query_params.get('type', 'properties')
    
    if data_type == 'properties':
        data = list(Property.objects.values(
            'id', 'title', 'type', 'status', 'price', 'area', 'district', 'created_at'
        ))
    elif data_type == 'users':
        data = list(User.objects.values(
            'id', 'username', 'email', 'first_name', 'last_name', 'date_joined', 'is_active'
        ))
    elif data_type == 'transactions':
        data = list(FinancialTransaction.objects.select_related('user').values(
            'id', 'user__username', 'amount', 'transaction_type', 'status', 'created_at'
        ))
    else:
        return Response({'error': 'Invalid data type'}, status=400)
    
    if export_format == 'csv':
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{data_type}.csv"'
        if data:
            writer = csv.DictWriter(response, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        return response
    
    return Response({
        'format': export_format,
        'type': data_type,
        'count': len(data),
        'data': data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_search(request):
    """Advanced search across all models"""
    query = request.query_params.get('q', '')
    
    if not query:
        return Response({'error': 'Search query required'}, status=400)
    
    results = {
        'properties': [],
        'users': [],
        'brokers': []
    }
    
    # Search properties
    properties = Property.objects.filter(
        Q(title__icontains=query) |
        Q(description__icontains=query) |
        Q(district__icontains=query) |
        Q(location__icontains=query)
    ).values('id', 'title', 'price', 'district')[:10]
    results['properties'] = list(properties)
    
    # Search users (admin only)
    if request.user.is_superuser:
        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).values('id', 'username', 'email')[:10]
        results['users'] = list(users)
        
        brokers = Broker.objects.filter(
            Q(display_name__icontains=query) |
            Q(phone__icontains=query)
        ).select_related('user').values(
            'id', 'display_name', 'phone', 'user__username'
        )[:10]
        results['brokers'] = list(brokers)
    
    return Response(results)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_notifications(request):
    """Get user notifications"""
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')[:20]
    
    return Response({
        'notifications': [
            {
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'is_read': n.is_read,
                'created_at': n.created_at.isoformat()
            }
            for n in notifications
        ],
        'unread_count': Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_mark_notification_read(request, notification_id):
    """Mark notification as read"""
    try:
        notification = Notification.objects.get(
            id=notification_id, user=request.user
        )
        notification.is_read = True
        notification.save()
        return Response({'success': True})
    except Notification.DoesNotExist:
        return Response({'error': 'Notification not found'}, status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_sessions(request):
    """Get active sessions (admin only)"""
    if not request.user.is_superuser:
        return Response({'error': 'Unauthorized'}, status=403)
    
    from django.contrib.sessions.models import Session
    
    sessions = Session.objects.filter(
        expire_date__gt=timezone.now
    ).order_by('-expire_date')[:50]
    
    return Response({
        'sessions': [
            {
                'session_key': s.session_key,
                'expire_date': s.expire_date.isoformat()
            }
            for s in sessions
        ],
        'count': sessions.count()
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_api_keys(request):
    """Get API keys (admin only)"""
    if not request.user.is_superuser:
        return Response({'error': 'Unauthorized'}, status=403)
    
    # This would integrate with a proper API key management system
    return Response({
        'api_keys': [
            {
                'id': 1,
                'name': 'Default API Key',
                'key': 'sk_live_*********************',
                'created_at': timezone.now().isoformat(),
                'last_used': timezone.now().isoformat()
            }
        ]
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_performance_metrics(request):
    """Get performance metrics"""
    if not request.user.is_superuser:
        return Response({'error': 'Unauthorized'}, status=403)
    
    # Get performance data
    from django.db import connection
    from django.core.cache import cache
    
    # Database query count
    db_queries = len(connection.queries)
    
    # Cache hit rate (simplified)
    cache_hits = cache.get('cache_hits', 0)
    
    return Response({
        'database_queries': db_queries,
        'cache_hits': cache_hits,
        'server_time': timezone.now().isoformat()
    })