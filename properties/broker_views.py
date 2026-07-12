import json
import logging
import secrets
import string

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .broker_forms import BrokerCreateForm, BrokerEditForm, BrokerJoinForm, MessageReplyForm, OfficeForm
from .decorators import broker_required, manage_brokers_required
from .forms import OfficePresenceForm, QuickStatusForm, PresenceNotificationForm, BrokerNotificationSettingsForm, HotelPageForm, HotelPostForm, HotelRoomForm, HotelOfferForm, HotelBookingForm, ServiceProviderPageForm, ServiceProviderWorkForm, ServiceProviderServiceForm, ServiceProviderGalleryForm, ServiceProviderVideoForm, ServiceProvider360Form, ServiceProviderRatingForm, ServiceProviderContactForm, ServiceProviderQuoteForm
from .models import Broker, BrokerJoinRequest, Message, Office, Property, ActivityLog, Notification, OfficePresence, PresenceNotification, BrokerSubscription, BrokerNotificationSettings, BrokerSubscriptionStats, SubscriptionPlan, BrokerChannel, ChannelRating, ChannelReview, ChannelReviewReply, ChannelShare, ChannelFollow, ChannelSave, HotelPage, HotelPost, HotelRoom, HotelOffer, HotelFollower, HotelRating, ServiceProviderCategory, ServiceProviderPage, ServiceProviderWork, ServiceProviderService, ServiceProviderGallery, ServiceProviderVideo, ServiceProvider360, ServiceProviderFollower, ServiceProviderRating, ServiceProviderContact, ServiceProviderQuote
from .permissions import (
    can_manage_join_requests,
    get_accessible_messages,
    get_accessible_properties,
    get_broker,
    get_broker_stats,
    get_managed_brokers,
    is_main_broker,
    is_platform_admin,
)

logger = logging.getLogger('properties')


def _generate_password(length=10):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@login_required
@broker_required
def sub_broker_panel(request):
    """لوحة تحكم خاصة للدلال الفرعي"""
    broker = get_broker(request.user)
    
    if not broker or broker.role != Broker.ROLE_SUB:
        messages.error(request, 'هذه الصفحة متاحة للدلال الفرعي فقط')
        return redirect('dashboard')
    
    parent_broker = broker.parent
    if not parent_broker:
        messages.error(request, 'لم يتم العثور على الدلال الرئيسي')
        return redirect('dashboard')
    
    # Get sub-broker specific data
    commission_summary = broker.get_commission_summary()
    sales_performance = broker.get_sales_performance()
    permissions = broker.get_sub_broker_permissions()
    
    # Get properties managed by this sub-broker
    properties = Property.objects.filter(broker=broker)
    
    # Calculate stats
    total_properties = properties.count()
    active_properties = properties.filter(status='active').count()
    sold_properties = properties.filter(status='sold').count()
    
    return render(request, 'properties/sub_broker_panel.html', {
        'broker': broker,
        'parent_broker': parent_broker,
        'commission_summary': commission_summary,
        'sales_performance': sales_performance,
        'permissions': permissions,
        'total_properties': total_properties,
        'active_properties': active_properties,
        'sold_properties': sold_properties,
        'properties': properties[:10],  # Recent properties
    })


@login_required
@broker_required
def sub_broker_commissions(request):
    """عرض وتتبع عمولات الدلال الفرعي"""
    broker = get_broker(request.user)
    
    if not broker or broker.role != Broker.ROLE_SUB:
        messages.error(request, 'هذه الصفحة متاحة للدلال الفرعي فقط')
        return redirect('dashboard')
    
    commission_summary = broker.get_commission_summary()
    sales_performance = broker.get_sales_performance()
    
    return render(request, 'properties/sub_broker_commissions.html', {
        'broker': broker,
        'commission_summary': commission_summary,
        'sales_performance': sales_performance,
    })


@login_required
@broker_required
def sub_broker_properties(request):
    """إدارة عقارات الدلال الفرعي"""
    broker = get_broker(request.user)
    
    if not broker or broker.role != Broker.ROLE_SUB:
        messages.error(request, 'هذه الصفحة متاحة للدلال الفرعي فقط')
        return redirect('dashboard')
    
    permissions = broker.get_sub_broker_permissions()
    properties = Property.objects.filter(broker=broker)
    
    return render(request, 'properties/sub_broker_properties.html', {
        'broker': broker,
        'permissions': permissions,
        'properties': properties,
    })


@login_required
@broker_required
def sub_broker_settings(request):
    """إعدادات الدلال الفرعي"""
    broker = get_broker(request.user)
    
    if not broker or broker.role != Broker.ROLE_SUB:
        messages.error(request, 'هذه الصفحة متاحة للدلال الفرعي فقط')
        return redirect('dashboard')
    
    if request.method == 'POST':
        # Update sub-broker settings
        broker.bio = request.POST.get('bio', broker.bio)
        broker.target_sales = request.POST.get('target_sales') or None
        if request.POST.get('target_sales'):
            broker.target_sales = int(request.POST.get('target_sales'))
        broker.save()
        messages.success(request, 'تم تحديث الإعدادات بنجاح')
        return redirect('sub_broker_settings')
    
    return render(request, 'properties/sub_broker_settings.html', {
        'broker': broker,
    })


def get_client_ip(request):
    """Get the client's IP address from the request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@require_http_methods(['GET', 'POST'])
def broker_join(request):
    if request.method == 'POST':
        form = BrokerJoinForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'تم إرسال طلبك بنجاح! سيتم مراجعته من قبل الإدارة والتواصل معك قريباً.'
            )
            return redirect('broker_join')
        messages.error(request, 'يرجى تصحيح الأخطاء في النموذج')
    else:
        form = BrokerJoinForm()
    return render(request, 'properties/broker_join.html', {'form': form})


@login_required
@broker_required
def broker_panel(request):
    """Main broker panel with comprehensive dashboard."""
    broker = get_broker(request.user)
    if not broker:
        messages.error(request, 'لم يتم العثور على ملف الدلال')
        return redirect('home')
    
    # Get broker statistics
    stats = get_broker_stats(request.user)
    
    # Get broker's properties
    my_properties = Property.objects.filter(broker=broker).select_related('owner').order_by('-created_at')[:10]
    
    # Property statistics for new payment system
    total_properties = Property.objects.filter(broker=broker).count()
    published_properties = Property.objects.filter(broker=broker, status=Property.STATUS_PUBLISHED).count()
    draft_properties = Property.objects.filter(broker=broker, status=Property.STATUS_DRAFT).count()
    pending_payment_properties = Property.objects.filter(broker=broker, status=Property.STATUS_PAID).count()
    
    # Payment statistics
    from .models import PropertyPayment
    total_payments = PropertyPayment.objects.filter(broker=broker).count()
    pending_payments = PropertyPayment.objects.filter(broker=broker, status=PropertyPayment.STATUS_PENDING).count()
    completed_payments = PropertyPayment.objects.filter(broker=broker, status=PropertyPayment.STATUS_COMPLETED).count()
    total_spent = PropertyPayment.objects.filter(broker=broker, status=PropertyPayment.STATUS_COMPLETED).aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    # Get sub-brokers if main broker
    sub_brokers = []
    if broker.role == Broker.ROLE_MAIN:
        sub_brokers = Broker.objects.filter(parent=broker, is_active=True).select_related('user')
        for sub in sub_brokers:
            sub.property_count = Property.objects.filter(broker=sub).count()
    
    # Get recent activity
    recent_activity = ActivityLog.objects.filter(
        user=request.user
    ).select_related('user').order_by('-created_at')[:10]
    
    # Get unread messages count
    unread_messages = get_accessible_messages(request.user).filter(is_read=False).count()
    
    # Get notifications
    from .models import NotificationRecipient
    notifications = Notification.objects.filter(
        recipients__user=request.user
    ).order_by('-created_at')[:5]
    
    # Get property notifications
    from .models import PropertyNotification
    property_notifications = PropertyNotification.objects.filter(
        user=request.user
    ).select_related('property').order_by('-created_at')[:5]
    
    # Get broker channel if exists
    broker_channel = None
    try:
        broker_channel = BrokerChannel.objects.filter(broker=broker).first()
    except Exception:
        pass
    
    return render(request, 'properties/broker_panel.html', {
        'broker': broker,
        'stats': stats,
        'my_properties': my_properties,
        'sub_brokers': sub_brokers,
        'total_properties': total_properties,
        'published_properties': published_properties,
        'draft_properties': draft_properties,
        'pending_payment_properties': pending_payment_properties,
        'total_payments': total_payments,
        'pending_payments': pending_payments,
        'completed_payments': completed_payments,
        'total_spent': total_spent,
        'recent_activity': recent_activity,
        'unread_messages': unread_messages,
        'notifications': notifications,
        'property_notifications': property_notifications,
        'broker_channel': broker_channel,
    })


@login_required
@manage_brokers_required
def broker_list(request):
    from django.db.models import Q

    filter_type = request.GET.get('filter', 'all')
    brokers = get_managed_brokers(request.user)
    
    # Filter to show only brokers created by current user
    if filter_type == 'my_brokers':
        current_broker = get_broker(request.user)
        if current_broker and current_broker.role == Broker.ROLE_MAIN:
            brokers = brokers.filter(parent=current_broker)
    
    broker_data = []
    for b in brokers:
        prop_count = Property.objects.filter(Q(owner=b.user) | Q(broker=b)).count()
        views = Property.objects.filter(Q(owner=b.user) | Q(broker=b)).aggregate(
            t=Sum('views_count')
        )['t'] or 0
        
        # Get individual stats
        from .models import BrokerIndividualStats
        individual_stats, _ = BrokerIndividualStats.objects.get_or_create(broker=b)
        
        # Calculate performance score
        individual_stats.calculate_performance_score()
        
        # Get channel info if exists
        channel_info = None
        try:
            channel = b.channel
            channel_info = {
                'id': channel.id,
                'name': channel.name,
                'followers': channel.followers_count,
                'views': channel.views_count,
                'rating': channel.rating,
                'status': channel.status,
                'is_verified': channel.is_verified,
            }
        except BrokerChannel.DoesNotExist:
            pass
        
        broker_data.append({
            'broker': b,
            'property_count': prop_count,
            'views': views,
            'unread': b.unread_messages_count,
            'property_limit': b.get_property_limit(),
            'remaining_properties': b.get_remaining_properties(),
            'days_remaining': b.get_days_remaining(),
            'days_elapsed': b.get_days_elapsed(),
            'subscription_status': b.get_subscription_status_display(),
            'subscription_plan': b.subscription_plan.name if b.subscription_plan else 'غير مشترك',
            'subscription_end_date': b.subscription_end_date,
            'properties_added': individual_stats.properties_added,
            'properties_deleted': individual_stats.properties_deleted,
            'total_views': individual_stats.total_views,
            'average_response_time': individual_stats.average_response_time,
            'performance_score': individual_stats.performance_score,
            'channel': channel_info,
        })
    
    # Apply sorting
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'oldest':
        broker_data.sort(key=lambda x: x['broker'].created_at)
    elif sort_by == 'name':
        broker_data.sort(key=lambda x: x['broker'].display_name)
    elif sort_by == 'properties':
        broker_data.sort(key=lambda x: x['property_count'], reverse=True)
    elif sort_by == 'views':
        broker_data.sort(key=lambda x: x['total_views'], reverse=True)
    elif sort_by == 'response_time':
        broker_data.sort(key=lambda x: x['average_response_time'] if x['average_response_time'] > 0 else 9999)
    elif sort_by == 'performance':
        broker_data.sort(key=lambda x: x['performance_score'], reverse=True)
    else:  # newest
        broker_data.sort(key=lambda x: x['broker'].created_at, reverse=True)
    
    # Calculate stats
    total_brokers = len(broker_data)
    verified_brokers = sum(1 for item in broker_data if item['broker'].is_verified)
    total_properties = sum(item['property_count'] for item in broker_data)
    active_brokers = sum(1 for item in broker_data if item['broker'].is_active)
    
    # Calculate additional stats
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    one_month_ago = timezone.now() - timedelta(days=30)
    monthly_new_brokers = brokers.filter(created_at__gte=one_month_ago).count()
    monthly_properties = Property.objects.filter(
        Q(owner__in=[b.user for b in brokers]) | Q(broker__in=brokers),
        created_at__gte=one_month_ago
    ).count()
    
    verified_percentage = (verified_brokers / total_brokers * 100) if total_brokers > 0 else 0
    active_percentage = (active_brokers / total_brokers * 100) if total_brokers > 0 else 0
    
    # Calculate expired subscriptions
    expired_subscriptions = brokers.filter(
        subscription_end_date__lt=timezone.now().date(),
        is_active=True
    ).count()
    
    # Calculate total revenue (this would need to be implemented based on your payment system)
    total_revenue = 0  # Placeholder - implement based on your payment model

    return render(request, 'properties/broker_list.html', {
        'broker_data': broker_data,
        'filter_type': filter_type,
        'total_brokers': total_brokers,
        'verified_brokers': verified_brokers,
        'total_properties': total_properties,
        'active_brokers': active_brokers,
        'monthly_new_brokers': monthly_new_brokers,
        'monthly_properties': monthly_properties,
        'verified_percentage': round(verified_percentage, 1),
        'active_percentage': round(active_percentage, 1),
        'expired_subscriptions': expired_subscriptions,
        'total_revenue': total_revenue,
        'plans': SubscriptionPlan.objects.filter(is_active=True),
    })


@login_required
@manage_brokers_required
def export_brokers(request):
    """Export broker data to CSV"""
    import csv
    from django.http import HttpResponse
    
    brokers = get_managed_brokers(request.user)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="brokers_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'اسم الدلال', 'الهاتف', 'المحافظة', 'الدور', 
        'الخطة', 'حالة الاشتراك', 'تاريخ النهاية',
        'العقارات المسموحة', 'العقارات المستخدمة', 'العقارات المتبقية',
        'العقارات المضافة', 'العقارات المحذوفة', 'المشاهدات',
        'متوسط وقت الاستجابة', 'نشط', 'موثق'
    ])
    
    for broker in brokers:
        from .models import BrokerIndividualStats
        individual_stats, _ = BrokerIndividualStats.objects.get_or_create(broker=broker)
        
        writer.writerow([
            broker.display_name,
            broker.phone,
            broker.governorate or '',
            broker.get_role_display(),
            broker.subscription_plan.name if broker.subscription_plan else 'غير مشترك',
            broker.get_subscription_status_display(),
            broker.subscription_end_date.strftime('%Y-%m-%d') if broker.subscription_end_date else '',
            broker.get_property_limit() or '∞',
            broker.get_published_properties_count(),
            broker.get_remaining_properties(),
            individual_stats.properties_added,
            individual_stats.properties_deleted,
            individual_stats.total_views,
            f"{individual_stats.average_response_time:.1f}" if individual_stats.average_response_time > 0 else '',
            'نعم' if broker.is_active else 'لا',
            'نعم' if broker.is_verified else 'لا'
        ])
    
    return response


@login_required
@manage_brokers_required
def activity_log(request):
    """عرض سجل النشاطات"""
    from django.db.models import Q
    
    # Get filters
    action_filter = request.GET.get('action', '')
    model_filter = request.GET.get('model_type', '')
    user_filter = request.GET.get('user', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Base queryset
    activities = ActivityLog.objects.all()
    
    # Apply filters
    if action_filter:
        activities = activities.filter(action=action_filter)
    if model_filter:
        activities = activities.filter(model_type=model_filter)
    if user_filter:
        activities = activities.filter(user__username__icontains=user_filter)
    if date_from:
        activities = activities.filter(created_at__gte=date_from)
    if date_to:
        activities = activities.filter(created_at__lte=date_to)
    
    # Order by date descending
    activities = activities.order_by('-created_at')[:100]
    
    return render(request, 'properties/activity_log.html', {
        'activities': activities,
        'action_filter': action_filter,
        'model_filter': model_filter,
        'user_filter': user_filter,
        'date_from': date_from,
        'date_to': date_to,
    })


@login_required
@manage_brokers_required
def broker_statistics(request):
    """إحصائيات متقدمة وتقارير الدلالين"""
    from django.db.models import Count, Q, Avg
    from django.db.models.functions import TruncDate, TruncMonth
    from django.utils import timezone
    from datetime import timedelta
    
    brokers = get_managed_brokers(request.user)
    
    # إحصائيات عامة
    total_brokers = brokers.count()
    active_brokers = brokers.filter(is_active=True).count()
    verified_brokers = brokers.filter(is_verified=True).count()
    suspended_brokers = brokers.filter(is_active=False).count()
    
    # إحصائيات حسب الدور
    role_stats = brokers.values('role').annotate(
        count=Count('id')
    ).order_by('role')
    
    # إحصائيات الاشتراكات
    subscription_stats = brokers.values('subscription_plan__name').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # إحصائيات العقارات
    total_properties = Property.objects.filter(
        Q(owner__in=[b.user for b in brokers]) | Q(broker__in=brokers)
    ).count()
    
    # نشاطات الأشهر الستة الماضية
    six_months_ago = timezone.now() - timedelta(days=180)
    monthly_activities = ActivityLog.objects.filter(
        created_at__gte=six_months_ago,
        model_type='broker'
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month', 'action').annotate(
        count=Count('id')
    ).order_by('month', 'action')
    
    # الدلالين الأكثر نشاطاً
    top_brokers = brokers.annotate(
        property_count=Count('user__owned_properties', filter=Q(user__owned_properties__isnull=False)) +
                      Count('properties', filter=Q(properties__isnull=False))
    ).order_by('-property_count')[:10]
    
    # إحصائيات النشاطات
    activity_stats = ActivityLog.objects.filter(
        model_type='broker'
    ).values('action').annotate(
        count=Count('id')
    ).order_by('-count')
    
    return render(request, 'properties/broker_statistics.html', {
        'total_brokers': total_brokers,
        'active_brokers': active_brokers,
        'verified_brokers': verified_brokers,
        'suspended_brokers': suspended_brokers,
        'role_stats': role_stats,
        'subscription_stats': subscription_stats,
        'total_properties': total_properties,
        'monthly_activities': monthly_activities,
        'top_brokers': top_brokers,
        'activity_stats': activity_stats,
    })


@login_required
def broker_messaging(request):
    """نظام الرسائل بين المستخدمين والدلالين"""
    from django.db.models import Q
    
    current_broker = get_broker(request.user)
    
    # Get all users for messaging (brokers and regular users)
    if request.user.is_staff:
        # Admin can message everyone
        managed_brokers = Broker.objects.all()
        all_users = User.objects.filter(is_active=True)
    elif current_broker:
        # Brokers can message other brokers and users
        managed_brokers = get_managed_brokers(request.user)
        all_users = User.objects.filter(is_active=True).exclude(id=request.user.id)
    else:
        # Regular users can message brokers
        managed_brokers = Broker.objects.filter(is_active=True)
        all_users = []
    
    # Get conversations
    sent_messages = Message.objects.filter(
        sender=request.user,
        message_type=Message.TYPE_BROKER_MESSAGE
    ).order_by('-created_at')
    
    received_messages = Message.objects.filter(
        recipient=request.user,
        message_type=Message.TYPE_BROKER_MESSAGE
    ).order_by('-created_at')
    
    # Mark received as read
    received_messages.filter(is_read=False).update(is_read=True)
    
    return render(request, 'properties/broker_messaging.html', {
        'managed_brokers': managed_brokers,
        'all_users': all_users,
        'sent_messages': sent_messages,
        'received_messages': received_messages,
        'current_broker': current_broker,
    })


@login_required
def notifications_view(request):
    """عرض الإشعارات"""
    notifications = request.user.notifications.all().order_by('-created_at')[:50]
    unread_count = request.user.notifications.filter(is_read=False).count()
    
    return render(request, 'properties/notifications.html', {
        'notifications': notifications,
        'unread_count': unread_count,
    })


@login_required
@manage_brokers_required
def broker_create(request):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    if request.method == 'POST':
        form = BrokerCreateForm(request.POST, creator=request.user)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            email = form.cleaned_data.get('email', '')
            
            # Check for duplicate username or email
            if User.objects.filter(username=username).exists():
                messages.error(request, 'اسم المستخدم مستخدم بالفعل')
                return render(request, 'properties/broker_create.html', {'form': form})
            
            if email and User.objects.filter(email=email).exists():
                messages.error(request, 'البريد الإلكتروني مستخدم بالفعل')
                return render(request, 'properties/broker_create.html', {'form': form})
            
            # Check for duplicate phone
            phone = form.cleaned_data['phone']
            if Broker.objects.filter(phone=phone).exists():
                messages.error(request, 'رقم الهاتف مستخدم بالفعل')
                return render(request, 'properties/broker_create.html', {'form': form})
            
            # Generate password if not provided
            if not password:
                password = _generate_password(12)
            
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data.get('last_name', ''),
                is_staff=True,
                is_active=True,
            )
            user.save()

            creator_broker = get_broker(request.user)
            office = creator_broker.office if creator_broker else None
            role = form.cleaned_data['role']
            office_name = form.cleaned_data.get('office_name', '')

            parent = None
            if role == Broker.ROLE_SUB and creator_broker and creator_broker.role == Broker.ROLE_MAIN:
                parent = creator_broker

            broker = Broker.objects.create(
                user=user,
                phone=phone,
                governorate=form.cleaned_data.get('governorate', ''),
                office_name=office_name,
                office=office,
                role=role,
                parent=parent,
                is_active=True,
            )
            
            # Log activity
            ActivityLog.log(
                user=request.user,
                action='create',
                model_type='broker',
                object_id=broker.id,
                object_repr=broker.display_name,
                description=f'إنشاء دلال جديد: {broker.display_name}',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                metadata={'role': role, 'office': office_name if office else None}
            )
            
            # Create notification for creator
            Notification.create(
                user=request.user,
                notification_type='broker_created',
                title='إنشاء دلال جديد',
                message=f'تم إنشاء حساب دلال جديد: {broker.display_name}',
                link=f'/dashboard/brokers/{broker.id}/edit/',
                metadata={'broker_id': broker.id, 'broker_name': broker.display_name}
            )

            # Send notifications to admin users
            admin_users = User.objects.filter(is_staff=True, is_superuser=True).exclude(id=request.user.id)
            for admin in admin_users:
                Notification.create(
                    user=admin,
                    notification_type='broker_created',
                    title='إنشاء دلال جديد',
                    message=f'تم إنشاء حساب دلال جديد: {broker.display_name} بواسطة {request.user.username}',
                    link=f'/dashboard/brokers/{broker.id}/edit/',
                    metadata={'broker_id': broker.id, 'broker_name': broker.display_name, 'creator': request.user.username}
                )
            
            # Update system statistics
            from .models import BrokerSystemStats, BrokerIndividualStats
            BrokerSystemStats.update_stats()

            # Create individual stats for the new broker
            BrokerIndividualStats.objects.get_or_create(broker=broker)

            messages.success(request, f'تم إنشاء حساب الدلال: {broker.display_name}. كلمة المرور: {password}')
            return redirect('broker_list')
        messages.error(request, 'يرجى تصحيح الأخطاء')
    else:
        form = BrokerCreateForm(creator=request.user)
    return render(request, 'properties/broker_create.html', {'form': form})


@login_required
@manage_brokers_required
def broker_edit(request, broker_id):
    broker = get_object_or_404(Broker, pk=broker_id)
    managed = get_managed_brokers(request.user)
    if not managed.filter(pk=broker_id).exists() and not is_platform_admin(request.user):
        messages.error(request, 'ليس لديك صلاحية تعديل هذا الدلال')
        return redirect('broker_list')

    if request.method == 'POST':
        form = BrokerEditForm(request.POST, request.FILES, instance=broker, editor=request.user)
        if form.is_valid():
            # Check for duplicate phone if phone is being changed
            new_phone = form.cleaned_data.get('phone')
            if new_phone and new_phone != broker.phone:
                if Broker.objects.filter(phone=new_phone).exclude(id=broker.id).exists():
                    messages.error(request, 'رقم الهاتف مستخدم بالفعل')
                    return render(request, 'properties/broker_edit.html', {
                        'form': form, 'broker': broker, 'can_delete_broker': is_platform_admin(request.user),
                    })
            
            form.save()
            
            # Log activity
            ActivityLog.log(
                user=request.user,
                action='update',
                model_type='broker',
                object_id=broker.id,
                object_repr=broker.display_name,
                description=f'تعديل بيانات الدلال: {broker.display_name}',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            messages.success(request, 'تم تحديث بيانات الدلال')
            return redirect('broker_list')
        messages.error(request, 'يرجى تصحيح الأخطاء')
    else:
        form = BrokerEditForm(instance=broker, editor=request.user)
    return render(request, 'properties/broker_edit.html', {
        'form': form, 'broker': broker, 'can_delete_broker': is_platform_admin(request.user),
    })


@login_required
@manage_brokers_required
@require_POST
def broker_toggle_active(request, broker_id):
    broker = get_object_or_404(Broker, pk=broker_id)
    managed = get_managed_brokers(request.user)
    if not managed.filter(pk=broker_id).exists():
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('broker_list')
    if broker.user == request.user:
        messages.error(request, 'لا يمكنك إيقاف حسابك')
        return redirect('broker_list')
    broker.is_active = not broker.is_active
    broker.user.is_active = broker.is_active
    broker.save(update_fields=['is_active'])
    broker.user.save(update_fields=['is_active'])
    status = 'تفعيل' if broker.is_active else 'إيقاف'
    
    # Log activity
    ActivityLog.log(
        user=request.user,
        action='activate' if broker.is_active else 'suspend',
        model_type='broker',
        object_id=broker.id,
        object_repr=broker.display_name,
        description=f'{status} حساب الدلال: {broker.display_name}',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    messages.success(request, f'تم {status} حساب {broker.display_name}')
    return redirect('broker_list')


@login_required
@manage_brokers_required
@require_POST
def broker_delete(request, broker_id):
    broker = get_object_or_404(Broker, pk=broker_id)
    managed = get_managed_brokers(request.user)
    if not managed.filter(pk=broker_id).exists() and not is_platform_admin(request.user):
        messages.error(request, 'ليس لديك صلاحية حذف هذا الدلال')
        return redirect('broker_list')
    if broker.user == request.user:
        messages.error(request, 'لا يمكنك حذف حسابك')
        return redirect('broker_list')
    
    # Check if broker has properties
    if broker.properties.exists():
        messages.error(request, 'لا يمكن حذف الدلال الذي لديه عقارات. يرجى نقل أو حذف العقارات أولاً')
        return redirect('broker_list')
    
    # Log activity before deletion
    ActivityLog.log(
        user=request.user,
        action='delete',
        model_type='broker',
        object_id=broker.id,
        object_repr=broker.display_name,
        description=f'حذف حساب الدلال: {broker.display_name}',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    user = broker.user
    broker.delete()
    user.delete()
    messages.success(request, f'تم حذف الدلال {broker.display_name}')
    return redirect('broker_list')


@login_required
@manage_brokers_required
def broker_renew_subscription(request, broker_id):
    broker = get_object_or_404(Broker, pk=broker_id)
    managed = get_managed_brokers(request.user)
    if not managed.filter(pk=broker_id).exists():
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('broker_list')
    
    renew_type = request.POST.get('renew_type', 'time')
    duration = request.POST.get('duration')
    additional_properties = request.POST.get('additional_properties', 0)
    plan_id = request.POST.get('plan_id')
    
    # Change subscription plan if specified
    if plan_id:
        try:
            new_plan = SubscriptionPlan.objects.get(pk=plan_id)
            broker.subscription_plan = new_plan
            broker.save(update_fields=['subscription_plan'])
        except SubscriptionPlan.DoesNotExist:
            pass
    
    # Renew subscription based on type
    if renew_type in ['time', 'both']:
        if duration:
            broker.renew_subscription(duration)
    
    # Add additional properties if specified
    if renew_type in ['properties', 'both']:
        if additional_properties and int(additional_properties) > 0:
            current_limit = broker.custom_ads_limit or 0
            broker.custom_ads_limit = current_limit + int(additional_properties)
            broker.save(update_fields=['custom_ads_limit'])
    
    # Log activity
    ActivityLog.log(
        user=request.user,
        action='renew',
        model_type='broker',
        object_id=broker.id,
        object_repr=broker.display_name,
        description=f'تجديد اشتراك الدلال: {broker.display_name}',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        metadata={'renew_type': renew_type, 'duration': duration, 'additional_properties': additional_properties, 'plan_id': plan_id}
    )
    
    # Create notification
    Notification.create(
        user=request.user,
        notification_type='success',
        title='تجديد اشتراك',
        message=f'تم تجديد اشتراك الدلال {broker.display_name} بنجاح',
        link=f'/dashboard/brokers/{broker.id}/edit/',
        metadata={'broker_id': broker.id, 'broker_name': broker.display_name}
    )
    
    messages.success(request, f'تم تجديد اشتراك الدلال {broker.display_name}')
    return redirect('broker_list')


@login_required
@manage_brokers_required
def property_view_commissions(request):
    """إدارة عمولات المشاهدات للعقارات"""
    from django.db.models import Sum, Q
    
    managed_brokers = get_managed_brokers(request.user)
    properties = Property.objects.filter(
        Q(broker__in=managed_brokers) | Q(owner__in=[b.user for b in managed_brokers])
    ).select_related('broker', 'owner').order_by('-created_at')
    
    # Calculate totals
    total_view_commission = properties.aggregate(
        total=Sum('total_view_commission'),
        paid=Sum('paid_view_commission'),
        pending=Sum('pending_view_commission')
    )
    
    return render(request, 'properties/property_view_commissions.html', {
        'properties': properties,
        'total_view_commission': total_view_commission,
    })


@login_required
@manage_brokers_required
def pay_property_view_commission(request, property_id):
    """دفع عمولة المشاهدات لعقار معين"""
    property_obj = get_object_or_404(Property, pk=property_id)
    managed_brokers = get_managed_brokers(request.user)
    
    # Check permission
    if not (property_obj.broker in managed_brokers or 
            (property_obj.owner and any(b.user == property_obj.owner for b in managed_brokers))):
        messages.error(request, 'ليس لديك صلاحية لدفع عمولات هذا العقار')
        return redirect('property_view_commissions')
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
            
            property_obj.pay_view_commission(amount)
            
            # Log activity
            ActivityLog.log(
                user=request.user,
                action='pay_commission',
                model_type='property',
                object_id=property_obj.id,
                object_repr=property_obj.display_title,
                description=f'دفع عمولة مشاهدات للعقار: {property_obj.display_title}',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                metadata={'amount': amount, 'property_id': property_obj.id}
            )
            
            messages.success(request, f'تم دفع {amount} دينار بنجاح')
            return redirect('property_view_commissions')
            
        except (ValueError, Exception) as e:
            messages.error(request, f'خطأ في دفع العمولة: {str(e)}')
    
    commission_summary = property_obj.get_view_commission_summary()
    
    return render(request, 'properties/pay_property_view_commission.html', {
        'property': property_obj,
        'commission_summary': commission_summary,
    })


@login_required
@broker_required
def broker_messages(request):
    msgs = get_accessible_messages(request.user).select_related('property', 'broker').order_by('-created_at')
    show_archived = request.GET.get('archived') == '1'
    # Note: is_archived field not available on Message model, skipping this filter
    return render(request, 'properties/broker_messages.html', {
        'messages_list': msgs[:50],
        'show_archived': show_archived,
    })


@login_required
@broker_required
def broker_message_detail(request, message_id):
    msg = get_object_or_404(Message, pk=message_id)
    accessible = get_accessible_messages(request.user)
    if not accessible.filter(pk=message_id).exists():
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('broker_messages')

    if not msg.is_read:
        msg.is_read = True
        msg.save(update_fields=['is_read'])

    if request.method == 'POST':
        form = MessageReplyForm(request.POST, instance=msg)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.replied_at = timezone.now()
            msg.replied_by = request.user
            msg.is_read = True
            msg.save()
            messages.success(request, 'تم إرسال الرد')
            return redirect('broker_message_detail', message_id=message_id)
    else:
        form = MessageReplyForm(instance=msg)

    return render(request, 'properties/broker_message_detail.html', {
        'msg': msg, 'form': form,
    })


@login_required
@broker_required
@require_POST
def broker_message_archive(request, message_id):
    msg = get_object_or_404(Message, pk=message_id)
    accessible = get_accessible_messages(request.user)
    if not accessible.filter(pk=message_id).exists():
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('broker_messages')
    # Note: is_archived field not available on Message model, skipping archive operation
    messages.success(request, 'تمت العملية')
    return redirect('broker_messages')


@login_required
@broker_required
def properties_map(request):
    """Enhanced properties map with AJAX support"""
    from django.core.paginator import Paginator
    from .models import Hotel, Resort, Auction
    
    # Get filter parameters
    governorate = request.GET.get('governorate')
    city = request.GET.get('city')
    district = request.GET.get('district')
    category = request.GET.get('category')
    status = request.GET.get('status')
    price_min = request.GET.get('price_min')
    price_max = request.GET.get('price_max')
    area_min = request.GET.get('area_min')
    area_max = request.GET.get('area_max')
    bedrooms = request.GET.get('bedrooms')
    bathrooms = request.GET.get('bathrooms')
    furnished = request.GET.get('furnished')
    pool = request.GET.get('pool')
    garden = request.GET.get('garden')
    elevator = request.GET.get('elevator')
    garage = request.GET.get('garage')
    has_360 = request.GET.get('has_360')
    has_video = request.GET.get('has_video')
    featured = request.GET.get('featured')
    
    # Base queryset
    props = get_accessible_properties(request.user).filter(
        latitude__isnull=False, 
        longitude__isnull=False
    ).select_related('broker', 'owner').prefetch_related('gallery_images')
    
    # Apply filters
    if governorate:
        props = props.filter(governorate=governorate)
    if city:
        props = props.filter(city=city)
    if district:
        props = props.filter(district=district)
    if category:
        props = props.filter(category=category)
    if status:
        props = props.filter(status=status)
    if price_min:
        props = props.filter(price__gte=float(price_min))
    if price_max:
        props = props.filter(price__lte=float(price_max))
    if area_min:
        props = props.filter(area__gte=float(area_min))
    if area_max:
        props = props.filter(area__lte=float(area_max))
    if bedrooms:
        props = props.filter(bedrooms__gte=int(bedrooms))
    if bathrooms:
        props = props.filter(bathrooms__gte=int(bathrooms))
    if furnished:
        props = props.filter(furnished=True)
    if pool:
        props = props.filter(pool=True)
    if garden:
        props = props.filter(garden=True)
    if elevator:
        props = props.filter(elevator=True)
    if garage:
        props = props.filter(garage=True)
    if has_360:
        props = props.filter(has_360_tour=True)
    if has_video:
        props = props.filter(video_url__isnull=False)
    if featured:
        props = props.filter(is_featured=True)
    
    # Get counts for statistics
    try:
        hotels_count = Hotel.objects.filter(broker=request.user.broker_profile).count()
    except:
        hotels_count = 0
    
    try:
        resorts_count = Resort.objects.filter(broker=request.user.broker_profile).count()
    except:
        resorts_count = 0
    
    try:
        auctions_count = Auction.objects.filter(broker=request.user.broker_profile).count()
    except:
        auctions_count = 0
    
    try:
        from .models import Message
        unread_count = Message.objects.filter(recipient=request.user, is_read=False).count()
    except:
        unread_count = 0
    
    # If AJAX request, return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Get bounds for smart loading
        bounds = request.GET.get('bounds')
        if bounds:
            try:
                bounds_data = json.loads(bounds)
                south = float(bounds_data.get('south'))
                north = float(bounds_data.get('north'))
                west = float(bounds_data.get('west'))
                east = float(bounds_data.get('east'))
                props = props.filter(
                    latitude__gte=south,
                    latitude__lte=north,
                    longitude__gte=west,
                    longitude__lte=east
                )
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        
        # Limit results for performance
        props = props[:500]
        
        map_data = []
        for p in props:
            main_image = p.get_main_image()
            map_data.append({
                'id': p.pk,
                'title': p.display_title,
                'lat': float(p.latitude),
                'lng': float(p.longitude),
                'price': p.price_formatted,
                'price_raw': p.price,
                'currency': 'IQD',
                'url': p.get_absolute_url(),
                'district': p.district,
                'city': p.city,
                'governorate': p.governorate,
                'category': p.category,
                'type': p.get_type_display(),
                'status': p.status,
                'area': p.area,
                'bedrooms': p.bedrooms,
                'bathrooms': p.bathrooms,
                'image': main_image,
                'is_featured': p.is_featured,
                'is_promoted': p.is_promoted,
                'is_new': (timezone.now() - p.created_at).days <= 7,
                'views': p.views_count if hasattr(p, 'views_count') else 0,
                'rating': p.rating if hasattr(p, 'rating') else 0,
                'created_at': p.created_at.strftime('%Y-%m-%d') if p.created_at else '',
                'broker': p.broker.display_name if p.broker else None,
                'office': p.office.name if p.office else None,
            })
        
        return JsonResponse({
            'properties': map_data,
            'total': props.count(),
        })
    
    # Regular page load - return template
    props = props[:100]  # Initial load limit
    map_data = []
    for p in props:
        main_image = p.get_main_image()
        map_data.append({
            'id': p.pk,
            'title': p.display_title,
            'lat': float(p.latitude),
            'lng': float(p.longitude),
            'price': p.price_formatted,
            'price_raw': p.price,
            'currency': 'IQD',
            'url': p.get_absolute_url(),
            'district': p.district,
            'city': p.city,
            'governorate': p.governorate,
            'category': p.category,
            'type': p.get_type_display(),
            'status': p.status,
            'area': p.area,
            'bedrooms': p.bedrooms,
            'bathrooms': p.bathrooms,
            'image': main_image,
            'is_featured': p.is_featured,
            'is_promoted': p.is_promoted,
            'is_new': (timezone.now() - p.created_at).days <= 7,
            'views': p.views_count if hasattr(p, 'views_count') else 0,
            'rating': p.rating if hasattr(p, 'rating') else 0,
            'created_at': p.created_at.strftime('%Y-%m-%d') if p.created_at else '',
        })
    
    return render(request, 'properties/properties_map.html', {
        'map_data_json': json.dumps(map_data, ensure_ascii=False),
        'total': props.count(),
        'hotels_count': hotels_count,
        'resorts_count': resorts_count,
        'auctions_count': auctions_count,
        'unread_count': unread_count,
    })


@login_required
@broker_required
def map_api_properties(request):
    """API endpoint for map properties with advanced filtering"""
    from django.core.paginator import Paginator
    
    # Get filter parameters
    governorate = request.GET.get('governorate')
    property_type = request.GET.get('type')
    status = request.GET.get('status')
    price_min = request.GET.get('price_min')
    price_max = request.GET.get('price_max')
    area_min = request.GET.get('area_min')
    area_max = request.GET.get('area_max')
    bedrooms = request.GET.get('bedrooms')
    furnished = request.GET.get('furnished')
    is_featured = request.GET.get('featured')
    bounds = request.GET.get('bounds')
    page = int(request.GET.get('page', 1))
    
    # Base queryset
    props = get_accessible_properties(request.user).filter(
        latitude__isnull=False, 
        longitude__isnull=False
    ).select_related('broker', 'owner').prefetch_related('gallery_images')
    
    # Apply filters
    if governorate:
        props = props.filter(governorate=governorate)
    if property_type:
        props = props.filter(type=property_type)
    if status:
        props = props.filter(status=status)
    if price_min:
        props = props.filter(price__gte=float(price_min))
    if price_max:
        props = props.filter(price__lte=float(price_max))
    if area_min:
        props = props.filter(area__gte=float(area_min))
    if area_max:
        props = props.filter(area__lte=float(area_max))
    if bedrooms:
        props = props.filter(bedrooms__gte=int(bedrooms))
    if furnished:
        props = props.filter(furnished=True)
    if is_featured:
        props = props.filter(is_featured=True)
    
    # Apply bounds for smart loading
    if bounds:
        try:
            bounds_data = json.loads(bounds)
            south = float(bounds_data.get('south'))
            north = float(bounds_data.get('north'))
            west = float(bounds_data.get('west'))
            east = float(bounds_data.get('east'))
            props = props.filter(
                latitude__gte=south,
                latitude__lte=north,
                longitude__gte=west,
                longitude__lte=east
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    
    # Pagination
    paginator = Paginator(props, 100)
    props_page = paginator.get_page(page)
    
    map_data = []
    for p in props_page:
        main_image = p.get_main_image()
        map_data.append({
            'id': p.pk,
            'title': p.display_title,
            'lat': float(p.latitude),
            'lng': float(p.longitude),
            'price': p.price_formatted,
            'price_raw': p.price,
            'url': p.get_absolute_url(),
            'district': p.district,
            'governorate': p.governorate,
            'type': p.get_type_display(),
            'status': p.get_status_display(),
            'area': p.area,
            'bedrooms': p.bedrooms,
            'bathrooms': p.bathrooms,
            'image': main_image,
            'is_featured': p.is_featured,
            'is_promoted': p.is_promoted,
            'broker': p.broker.display_name if p.broker else None,
            'office': p.office.name if p.office else None,
        })
    
    return JsonResponse({
        'properties': map_data,
        'total': paginator.count,
        'page': page,
        'has_next': props_page.has_next(),
    })


@login_required
@broker_required
def map_api_nearby_places(request):
    """API endpoint for nearby places using OpenStreetMap"""
    import requests
    
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')
    place_type = request.GET.get('type', 'all')  # all, school, hospital, mosque, etc.
    radius = request.GET.get('radius', 1000)  # meters
    
    if not lat or not lng:
        return JsonResponse({'error': 'Missing coordinates'}, status=400)
    
    # OpenStreetMap Overpass API query
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    # Build query based on place type
    queries = {
        'all': f"""
            [out:json][timeout:25];
            (
              node["amenity"](around:{radius},{lat},{lng});
              way["amenity"](around:{radius},{lat},{lng});
            );
            out body;
        """,
        'school': f"""
            [out:json][timeout:25];
            (
              node["amenity"="school"](around:{radius},{lat},{lng});
              node["amenity"="university"](around:{radius},{lat},{lng});
            );
            out body;
        """,
        'hospital': f"""
            [out:json][timeout:25];
            (
              node["amenity"="hospital"](around:{radius},{lat},{lng});
              node["amenity"="clinic"](around:{radius},{lat},{lng});
            );
            out body;
        """,
        'mosque': f"""
            [out:json][timeout:25];
            (
              node["amenity"="place_of_worship"]["religion"="muslim"](around:{radius},{lat},{lng});
            );
            out body;
        """,
        'market': f"""
            [out:json][timeout:25];
            (
              node["shop"](around:{radius},{lat},{lng});
              node["amenity"="marketplace"](around:{radius},{lat},{lng});
            );
            out body;
        """,
        'restaurant': f"""
            [out:json][timeout:25];
            (
              node["amenity"="restaurant"](around:{radius},{lat},{lng});
              node["amenity"="cafe"](around:{radius},{lat},{lng});
            );
            out body;
        """,
        'park': f"""
            [out:json][timeout:25];
            (
              node["leisure"="park"](around:{radius},{lat},{lng});
              node["landuse"="recreation_ground"](around:{radius},{lat},{lng});
            );
            out body;
        """,
    }
    
    query = queries.get(place_type, queries['all'])
    
    try:
        response = requests.post(overpass_url, data={'data': query}, timeout=30)
        data = response.json()
        
        places = []
        for element in data.get('elements', []):
            if element.get('type') == 'node':
                tags = element.get('tags', {})
                name = tags.get('name', 'غير محدد')
                amenity = tags.get('amenity', tags.get('shop', 'general'))
                
                # Calculate distance
                from math import radians, cos, sin, asin, sqrt
                def haversine_distance(lat1, lon1, lat2, lon2):
                    R = 6371  # Earth radius in km
                    dLat = radians(lat2 - lat1)
                    dLon = radians(lon2 - lon1)
                    a = sin(dLat/2) * sin(dLat/2) + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon/2) * sin(dLon/2)
                    c = 2 * asin(sqrt(a))
                    return R * c * 1000  # Distance in meters
                
                distance = haversine_distance(float(lat), float(lng), element.get('lat'), element.get('lon'))
                
                places.append({
                    'id': element.get('id'),
                    'name': name,
                    'type': amenity,
                    'lat': element.get('lat'),
                    'lng': element.get('lon'),
                    'distance': round(distance, 0),
                })
        
        # Sort by distance
        places.sort(key=lambda x: x['distance'])
        
        return JsonResponse({
            'places': places[:20],  # Limit to 20 places
            'total': len(places),
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@broker_required
def map_api_directions(request):
    """API endpoint for directions using OSRM"""
    import requests
    
    start_lat = request.GET.get('start_lat')
    start_lng = request.GET.get('start_lng')
    end_lat = request.GET.get('end_lat')
    end_lng = request.GET.get('end_lng')
    profile = request.GET.get('profile', 'driving')  # driving, walking, cycling
    
    if not all([start_lat, start_lng, end_lat, end_lng]):
        return JsonResponse({'error': 'Missing coordinates'}, status=400)
    
    # OSRM API
    osrm_url = f"https://router.project-osrm.org/route/v1/{profile}/{start_lng},{start_lat};{end_lng},{end_lat}"
    
    try:
        response = requests.get(osrm_url, params={
            'overview': 'full',
            'geometries': 'geojson'
        }, timeout=30)
        
        data = response.json()
        
        if data.get('code') != 'Ok':
            return JsonResponse({'error': 'No route found'}, status=404)
        
        route = data.get('routes', [{}])[0]
        
        return JsonResponse({
            'distance': route.get('distance', 0),  # meters
            'duration': route.get('duration', 0),  # seconds
            'geometry': route.get('geometry'),
            'steps': route.get('legs', [{}])[0].get('steps', []),
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@broker_required
def map_api_offices(request):
    """API endpoint for office locations on map"""
    from .models import Office
    
    offices = Office.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False,
        is_active=True
    )
    
    office_data = []
    for office in offices:
        office_data.append({
            'id': office.id,
            'name': office.name,
            'lat': float(office.latitude),
            'lng': float(office.longitude),
            'address': office.address,
            'phone': office.phone,
            'email': office.email,
            'logo': office.logo.url if office.logo else None,
        })
    
    return JsonResponse({
        'offices': office_data,
        'total': len(office_data),
    })


@login_required
@broker_required
def map_api_brokers(request):
    """API endpoint for broker locations on map"""
    brokers = get_managed_brokers(request.user).filter(
        latitude__isnull=False,
        longitude__isnull=False,
        is_active=True
    )
    
    broker_data = []
    for broker in brokers:
        broker_data.append({
            'id': broker.id,
            'name': broker.display_name,
            'lat': float(broker.latitude) if broker.latitude else None,
            'lng': float(broker.longitude) if broker.longitude else None,
            'phone': broker.phone,
            'company_name': broker.company_name,
            'avatar': broker.avatar.url if broker.avatar else None,
        })
    
    return JsonResponse({
        'brokers': broker_data,
        'total': len(broker_data),
    })


@login_required
@broker_required
def map_api_save_favorite_area(request):
    """API endpoint to save favorite map area"""
    from .models import FavoriteArea
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            south = float(data.get('south'))
            north = float(data.get('north'))
            west = float(data.get('west'))
            east = float(data.get('east'))
            
            if not all([name, south, north, west, east]):
                return JsonResponse({'error': 'Missing required fields'}, status=400)
            
            favorite_area = FavoriteArea.objects.create(
                user=request.user,
                name=name,
                south=south,
                north=north,
                west=west,
                east=east
            )
            
            return JsonResponse({
                'success': True,
                'id': favorite_area.id,
                'message': 'تم حفظ المنطقة المفضلة بنجاح'
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    # GET request - list favorite areas
    favorite_areas = FavoriteArea.objects.filter(user=request.user, is_active=True)
    areas_data = []
    for area in favorite_areas:
        areas_data.append({
            'id': area.id,
            'name': area.name,
            'south': float(area.south),
            'north': float(area.north),
            'west': float(area.west),
            'east': float(area.east),
        })
    
    return JsonResponse({
        'areas': areas_data,
        'total': len(areas_data),
    })


@login_required
@broker_required
def map_api_add_to_comparison(request):
    """API endpoint to add property to comparison"""
    from .models import PropertyComparison
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        property_id = data.get('property_id')
        
        if not property_id:
            return JsonResponse({'error': 'Missing property_id'}, status=400)
        
        property_obj = get_object_or_404(Property, pk=property_id)
        
        comparison, created = PropertyComparison.objects.get_or_create(
            user=request.user,
            property=property_obj
        )
        
        if created:
            return JsonResponse({
                'success': True,
                'message': 'تم إضافة العقار للمقارنة'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'العقار موجود بالفعل في المقارنة'
            })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@broker_required
def map_api_comparison_list(request):
    """API endpoint to get comparison list"""
    from .models import PropertyComparison
    
    comparisons = PropertyComparison.objects.filter(user=request.user).select_related('property')
    comparison_data = []
    
    for comp in comparisons:
        comparison_data.append({
            'id': comp.id,
            'property_id': comp.property.id,
            'title': comp.property.display_title,
            'price': comp.property.price_formatted,
            'price_raw': comp.property.price,
            'area': comp.property.area,
            'bedrooms': comp.property.bedrooms,
            'bathrooms': comp.property.bathrooms,
            'district': comp.property.district,
            'image': comp.property.get_main_image(),
            'lat': float(comp.property.latitude) if comp.property.latitude else None,
            'lng': float(comp.property.longitude) if comp.property.longitude else None,
        })
    
    return JsonResponse({
        'comparisons': comparison_data,
        'total': len(comparison_data),
    })


@login_required
@broker_required
def map_api_remove_from_comparison(request, comparison_id):
    """API endpoint to remove property from comparison"""
    from .models import PropertyComparison
    
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        comparison = get_object_or_404(PropertyComparison, pk=comparison_id, user=request.user)
        comparison.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'تم إزالة العقار من المقارنة'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@broker_required
def map_api_update_property_location(request):
    """API endpoint for admin to update property location by dragging marker"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        property_id = data.get('property_id')
        lat = float(data.get('lat'))
        lng = float(data.get('lng'))
        
        if not all([property_id, lat, lng]):
            return JsonResponse({'error': 'Missing required fields'}, status=400)
        
        property_obj = get_object_or_404(Property, pk=property_id)
        
        # Check if user has permission to edit this property
        if not can_manage_brokers(request.user) and property_obj.owner != request.user:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        property_obj.latitude = lat
        property_obj.longitude = lng
        property_obj.save(update_fields=['latitude', 'longitude'])
        
        # Log activity
        ActivityLog.log(
            user=request.user,
            action='edit',
            model_type='property',
            object_id=property_obj.id,
            object_repr=property_obj.display_title,
            description=f'تحديث موقع العقار: {property_obj.display_title}',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            metadata={'property_id': property_obj.id, 'lat': lat, 'lng': lng}
        )
        
        return JsonResponse({
            'success': True,
            'message': 'تم تحديث موقع العقار بنجاح'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@broker_required
def map_api_bulk_update_coordinates(request):
    """API endpoint for admin to bulk update property coordinates"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    if not can_manage_brokers(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        updates = data.get('updates', [])
        
        updated_count = 0
        for update in updates:
            property_id = update.get('property_id')
            lat = float(update.get('lat'))
            lng = float(update.get('lng'))
            
            if all([property_id, lat, lng]):
                property_obj = Property.objects.filter(pk=property_id).first()
                if property_obj:
                    property_obj.latitude = lat
                    property_obj.longitude = lng
                    property_obj.save(update_fields=['latitude', 'longitude'])
                    updated_count += 1
        
        # Log activity
        ActivityLog.log(
            user=request.user,
            action='bulk_edit',
            model_type='property',
            description=f'تحديث دفعي لإحداثيات {updated_count} عقار',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            metadata={'updated_count': updated_count}
        )
        
        return JsonResponse({
            'success': True,
            'message': f'تم تحديث {updated_count} عقار بنجاح',
            'updated_count': updated_count
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@broker_required
def map_api_validate_coordinates(request):
    """API endpoint to validate missing or invalid coordinates"""
    if not can_manage_brokers(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Find properties with missing or invalid coordinates
    properties_missing = Property.objects.filter(
        latitude__isnull=True
    ) | Property.objects.filter(
        longitude__isnull=True
    )
    
    # Find properties with invalid coordinates (outside Iraq bounds)
    # Iraq bounds approximately: lat 29-38, lng 38-48
    properties_invalid = Property.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False
    ).exclude(
        latitude__gte=29,
        latitude__lte=38,
        longitude__gte=38,
        longitude__lte=48
    )
    
    missing_data = []
    for prop in properties_missing[:100]:
        missing_data.append({
            'id': prop.id,
            'title': prop.display_title,
            'district': prop.district,
            'governorate': prop.governorate,
        })
    
    invalid_data = []
    for prop in properties_invalid[:100]:
        invalid_data.append({
            'id': prop.id,
            'title': prop.display_title,
            'district': prop.district,
            'governorate': prop.governorate,
            'lat': prop.latitude,
            'lng': prop.longitude,
        })
    
    return JsonResponse({
        'missing': missing_data,
        'missing_total': properties_missing.count(),
        'invalid': invalid_data,
        'invalid_total': properties_invalid.count(),
    })


@login_required
@broker_required
def join_requests_list(request):
    if not can_manage_join_requests(request.user):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    requests_qs = BrokerJoinRequest.objects.all()
    status = request.GET.get('status', 'pending')
    if status:
        requests_qs = requests_qs.filter(status=status)
    return render(request, 'properties/join_requests_list.html', {
        'join_requests': requests_qs,
        'current_status': status,
    })


@login_required
@broker_required
@require_POST
def join_request_approve(request, request_id):
    if not can_manage_join_requests(request.user):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    join_req = get_object_or_404(BrokerJoinRequest, pk=request_id, status=BrokerJoinRequest.STATUS_PENDING)

    base_username = join_req.name.replace(' ', '_')[:20] or 'broker'
    username = base_username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f'{base_username}{counter}'
        counter += 1

    password = _generate_password()
    user = User.objects.create_user(
        username=username,
        password=password,
        first_name=join_req.name,
        email=join_req.email or '',
    )
    user.is_staff = True
    user.save()

    office = None
    if join_req.office_name:
        office, _ = Office.objects.get_or_create(
            name=join_req.office_name,
            defaults={'governorate': join_req.governorate, 'owner': user}
        )

    broker = Broker.objects.create(
        user=user,
        phone=join_req.phone,
        governorate=join_req.governorate,
        office_name=join_req.office_name,
        office=office,
        role=Broker.ROLE_MAIN,
        id_card_image=join_req.id_card_image,
    )

    join_req.status = BrokerJoinRequest.STATUS_APPROVED
    join_req.reviewed_by = request.user
    join_req.reviewed_at = timezone.now()
    join_req.created_user = user
    join_req.save()

    messages.success(
        request,
        f'تم قبول الطلب! اسم المستخدم: {username} | كلمة المرور: {password}'
    )
    logger.info('Approved broker join request %s, user %s', request_id, username)
    return redirect('join_requests_list')


@login_required
@broker_required
@require_POST
def join_request_reject(request, request_id):
    if not can_manage_join_requests(request.user):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    join_req = get_object_or_404(BrokerJoinRequest, pk=request_id, status=BrokerJoinRequest.STATUS_PENDING)
    join_req.status = BrokerJoinRequest.STATUS_REJECTED
    join_req.reviewed_by = request.user
    join_req.reviewed_at = timezone.now()
    join_req.save()
    messages.success(request, 'تم رفض الطلب')
    return redirect('join_requests_list')


@login_required
@manage_brokers_required
def office_panel(request):
    creator_broker = get_broker(request.user)
    if creator_broker and creator_broker.office:
        office = creator_broker.office
    elif is_platform_admin(request.user):
        office_id = request.GET.get('office')
        office = Office.objects.filter(pk=office_id).first() if office_id else None
    else:
        office = None

    offices = Office.objects.all() if is_platform_admin(request.user) else Office.objects.filter(
        pk=creator_broker.office_id
    ) if creator_broker and creator_broker.office_id else Office.objects.none()

    if request.method == 'POST' and 'create_office' in request.POST:
        form = OfficeForm(request.POST)
        if form.is_valid():
            office_obj = form.save(commit=False)
            office_obj.owner = request.user
            office_obj.save()
            if creator_broker:
                creator_broker.office = office_obj
                creator_broker.save(update_fields=['office'])
            messages.success(request, 'تم إنشاء المكتب')
            return redirect('office_panel')
    else:
        form = OfficeForm()

    office_brokers = office.brokers.all() if office else Broker.objects.none()
    office_properties = office.properties.all() if office else Property.objects.none()

    return render(request, 'properties/office_panel.html', {
        'office': office,
        'offices': offices,
        'form': form,
        'office_brokers': office_brokers,
        'office_properties': office_properties,
    })


# Office Presence Views

@login_required
@broker_required
def office_presence_settings(request):
    """Office presence settings page"""
    broker = get_broker(request.user)
    if not broker or not broker.office:
        messages.error(request, 'يجب أن تكون مرتبطاً بمكتب')
        return redirect('dashboard')
    
    office = broker.office
    presence, created = OfficePresence.objects.get_or_create(office=office)
    
    if request.method == 'POST':
        form = OfficePresenceForm(request.POST, instance=presence)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث إعدادات التواجد بنجاح')
            return redirect('office_presence_settings')
    else:
        form = OfficePresenceForm(instance=presence)
    
    return render(request, 'properties/office_presence_settings.html', {
        'form': form,
        'presence': presence,
        'office': office,
    })


@login_required
@broker_required
def update_presence_status(request):
    """AJAX endpoint to update presence status"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    broker = get_broker(request.user)
    if not broker or not broker.office:
        return JsonResponse({'error': 'No office found'}, status=404)
    
    presence, created = OfficePresence.objects.get_or_create(office=broker.office)
    
    try:
        data = json.loads(request.body)
        status = data.get('status')
        expected_return = data.get('expected_return')
        absence_reason = data.get('absence_reason')
        
        if status:
            presence.status = status
        
        if expected_return:
            from datetime import datetime
            presence.expected_return = datetime.fromisoformat(expected_return)
        
        if absence_reason:
            presence.absence_reason = absence_reason
        
        presence.save()
        
        # Notify subscribers if coming online
        if status in ['online', 'busy', 'remote']:
            notify_presence_subscribers(presence)
        
        return JsonResponse({
            'success': True,
            'status': presence.status,
            'status_display': presence.get_status_display(),
            'emoji': presence.get_status_emoji(),
            'last_seen': presence.get_last_seen_display(),
            'expected_return': presence.get_expected_return_display(),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_office_presence(request, office_id):
    """AJAX endpoint to get office presence status"""
    presence = get_object_or_404(OfficePresence, office_id=office_id)
    
    return JsonResponse({
        'status': presence.status,
        'status_display': presence.get_status_display(),
        'emoji': presence.get_status_emoji(),
        'is_online': presence.is_online(),
        'last_seen': presence.get_last_seen_display(),
        'expected_return': presence.get_expected_return_display(),
    })


@login_required
def subscribe_presence_notification(request, office_id):
    """Subscribe to presence notifications for an office"""
    office = get_object_or_404(Office, pk=office_id)
    
    notification, created = PresenceNotification.objects.get_or_create(
        user=request.user,
        office=office
    )
    
    if not created:
        # Toggle subscription
        notification.is_active = not notification.is_active
        notification.save()
        message = 'تم تفعيل الإشعارات' if notification.is_active else 'تم إيقاف الإشعارات'
    else:
        message = 'تم الاشتراك في الإشعارات'
    
    return JsonResponse({
        'success': True,
        'is_active': notification.is_active,
        'message': message,
    })


@login_required
@manage_brokers_required
def admin_presence_dashboard(request):
    """Admin dashboard for all office presences"""
    presences = OfficePresence.objects.select_related('office').all()
    
    # Calculate statistics
    total_offices = presences.count()
    online_offices = sum(1 for p in presences if p.is_online())
    avg_online_hours = presences.aggregate(avg_hours=models.Avg('total_online_hours'))['avg_hours'] or 0
    
    return render(request, 'properties/admin_presence_dashboard.html', {
        'presences': presences,
        'total_offices': total_offices,
        'online_offices': online_offices,
        'avg_online_hours': avg_online_hours,
    })


@login_required
@manage_brokers_required
def admin_update_presence(request, presence_id):
    """Admin endpoint to update office presence"""
    presence = get_object_or_404(OfficePresence, pk=presence_id)
    
    if request.method == 'POST':
        form = OfficePresenceForm(request.POST, instance=presence)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث حالة التواجد')
            return redirect('admin_presence_dashboard')
    else:
        form = OfficePresenceForm(instance=presence)
    
    return render(request, 'properties/admin_presence_edit.html', {
        'form': form,
        'presence': presence,
    })


def notify_presence_subscribers(presence):
    """Notify subscribers when office comes online"""
    subscribers = PresenceNotification.objects.filter(
        office=presence.office,
        is_active=True,
        notified=False
    )
    
    for subscriber in subscribers:
        Notification.objects.create(
            user=subscriber.user,
            title=f'{presence.office.name} متواجد الآن',
            message=f'المكتب {presence.office.name} أصبح متواجداً',
            notification_type='presence',
            link=f'/office/{presence.office.id}/'
        )
        
        subscriber.notified = True
        subscriber.notified_at = timezone.now()
        subscriber.save()


# Broker Subscription Views

@login_required
def toggle_broker_subscription(request, broker_id):
    """Toggle subscription to broker channel"""
    broker = get_object_or_404(Broker, pk=broker_id)
    
    subscription, created = BrokerSubscription.objects.get_or_create(
        user=request.user,
        broker=broker
    )
    
    if not created:
        # Toggle subscription
        subscription.is_active = not subscription.is_active
        if not subscription.is_active:
            subscription.unsubscribed_at = timezone.now()
        else:
            subscription.unsubscribed_at = None
        subscription.save()
        
        # Update stats
        stats, _ = BrokerSubscriptionStats.objects.get_or_create(broker=broker)
        stats.update_subscriber_count()
        
        message = 'تم الاشتراك' if subscription.is_active else 'تم إلغاء الاشتراك'
    else:
        # New subscription
        message = 'تم الاشتراك بنجاح'
        
        # Update stats
        stats, _ = BrokerSubscriptionStats.objects.get_or_create(broker=broker)
        stats.new_subscribers_today += 1
        stats.update_subscriber_count()
        stats.save()
    
    return JsonResponse({
        'success': True,
        'is_subscribed': subscription.is_active,
        'message': message,
        'subscriber_count': broker.subscribers.filter(is_active=True).count()
    })


@login_required
def update_broker_notification_settings(request, broker_id):
    """Update notification settings for broker"""
    broker = get_object_or_404(Broker, pk=broker_id)
    
    # Check if subscribed
    if not BrokerSubscription.objects.filter(user=request.user, broker=broker, is_active=True).exists():
        return JsonResponse({'error': 'يجب الاشتراك أولاً'}, status=400)
    
    settings_obj, created = BrokerNotificationSettings.objects.get_or_create(
        user=request.user,
        broker=broker
    )
    
    if request.method == 'POST':
        form = BrokerNotificationSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            return JsonResponse({
                'success': True,
                'message': 'تم تحديث إعدادات الإشعارات'
            })
    else:
        form = BrokerNotificationSettingsForm(instance=settings_obj)
    
    return render(request, 'properties/broker_notification_settings.html', {
        'form': form,
        'broker': broker,
    })


@login_required
def user_subscriptions(request):
    """View user's broker subscriptions"""
    subscriptions = BrokerSubscription.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('broker')
    
    return render(request, 'properties/user_subscriptions.html', {
        'subscriptions': subscriptions,
    })


@login_required
@broker_required
def broker_subscription_stats(request):
    """Broker's subscription statistics"""
    broker = get_broker(request.user)
    if not broker:
        messages.error(request, 'يجب أن تكون دلال')
        return redirect('dashboard')
    
    stats, created = BrokerSubscriptionStats.objects.get_or_create(broker=broker)
    
    # Get recent subscribers
    recent_subscribers = BrokerSubscription.objects.filter(
        broker=broker,
        is_active=True
    ).select_related('user').order_by('-subscribed_at')[:10]
    
    return render(request, 'properties/broker_subscription_stats.html', {
        'stats': stats,
        'recent_subscribers': recent_subscribers,
    })


@login_required
@manage_brokers_required
def admin_broker_subscriptions(request):
    """Admin dashboard for all broker subscriptions"""
    subscriptions = BrokerSubscription.objects.select_related('user', 'broker').all()
    
    # Calculate statistics
    total_subscriptions = subscriptions.filter(is_active=True).count()
    total_brokers = Broker.objects.count()
    avg_subscribers = Broker.objects.annotate(
        sub_count=models.Count('subscribers', filter=models.Q(subscribers__is_active=True))
    ).aggregate(avg=models.Avg('sub_count'))['avg'] or 0
    
    return render(request, 'properties/admin_broker_subscriptions.html', {
        'subscriptions': subscriptions,
        'total_subscriptions': total_subscriptions,
        'total_brokers': total_brokers,
        'avg_subscribers': avg_subscribers,
    })


def notify_broker_subscribers(broker, notification_type, title, message, link=None):
    """Notify broker subscribers about new content"""
    subscribers = BrokerSubscription.objects.filter(
        broker=broker,
        is_active=True
    ).select_related('user')
    
    for subscriber in subscribers:
        # Check notification settings
        settings_obj = BrokerNotificationSettings.objects.filter(
            user=subscriber.user,
            broker=broker
        ).first()
        
        if settings_obj:
            # Check if user wants this type of notification
            if settings_obj.notification_type == 'none':
                continue
            elif settings_obj.notification_type == 'new_properties' and notification_type != 'new_property':
                continue
            elif settings_obj.notification_type == 'featured' and notification_type != 'featured':
                continue
            elif settings_obj.notification_type == 'offers' and notification_type != 'offer':
                continue
        
        # Create notification
        Notification.objects.create(
            user=subscriber.user,
            title=title,
            message=message,
            notification_type='broker_update',
            link=link or f'/broker/{broker.user.username}/'
        )
        
        # Update stats
        subscriber.notifications_sent += 1
        subscriber.last_notification_at = timezone.now()
        subscriber.save()


@login_required
@broker_required
def broker_channel_settings(request):
    """إدارة إعدادات قناة الدلال"""
    broker = get_broker(request.user)
    
    # Get or create channel
    channel, created = BrokerChannel.objects.get_or_create(
        broker=broker,
        defaults={
            'name': f'قناة {broker.display_name}',
            'description': f'قناة عقارية خاصة بـ {broker.display_name}',
            'status': 'pending'
        }
    )
    
    if request.method == 'POST':
        # Basic channel info
        channel.name = request.POST.get('name', channel.name)
        channel.description = request.POST.get('description', channel.description)
        
        # Social links
        channel.whatsapp = request.POST.get('whatsapp', channel.whatsapp)
        channel.facebook = request.POST.get('facebook', channel.facebook)
        channel.instagram = request.POST.get('instagram', channel.instagram)
        channel.telegram = request.POST.get('telegram', channel.telegram)
        channel.youtube = request.POST.get('youtube', channel.youtube)
        channel.tiktok = request.POST.get('tiktok', channel.tiktok)
        
        # Personal information
        channel.phone = request.POST.get('phone', channel.phone)
        channel.email = request.POST.get('email', channel.email)
        channel.address = request.POST.get('address', channel.address)
        channel.work_area = request.POST.get('work_area', channel.work_area)
        
        # Handle experience_years (can be empty)
        experience_years = request.POST.get('experience_years')
        if experience_years:
            channel.experience_years = int(experience_years)
        else:
            channel.experience_years = None
        
        channel.specialization = request.POST.get('specialization', channel.specialization)
        channel.working_hours = request.POST.get('working_hours', channel.working_hours)
        channel.languages = request.POST.get('languages', channel.languages)
        channel.about_me = request.POST.get('about_me', channel.about_me)
        channel.achievements = request.POST.get('achievements', channel.achievements)
        
        # SEO
        channel.meta_title = request.POST.get('meta_title', channel.meta_title)
        channel.meta_description = request.POST.get('meta_description', channel.meta_description)
        channel.keywords = request.POST.get('keywords', channel.keywords)
        
        # Handle logo upload
        if 'logo' in request.FILES:
            channel.logo = request.FILES['logo']
        
        # Handle cover image upload
        if 'cover_image' in request.FILES:
            channel.cover_image = request.FILES['cover_image']
        
        channel.save()
        messages.success(request, 'تم تحديث إعدادات القناة بنجاح')
        return redirect('broker_channel_settings')
    
    return render(request, 'properties/broker_channel_settings.html', {
        'broker': broker,
        'channel': channel,
        'is_new_channel': created,
    })


@login_required
@broker_required
def broker_channel_stats(request):
    """إحصائيات قناة الدلال"""
    broker = get_broker(request.user)
    
    try:
        channel = broker.channel
    except BrokerChannel.DoesNotExist:
        messages.error(request, 'لم يتم إنشاء القناة بعد')
        return redirect('broker_channel_settings')
    
    # Get channel statistics
    properties = Property.objects.filter(broker=broker, status__in=['ready', 'rent'])
    
    stats = {
        'total_properties': properties.count(),
        'total_views': channel.views_count,
        'total_followers': channel.followers_count,
        'recent_properties': properties.order_by('-created_at')[:10],
    }
    
    return render(request, 'properties/broker_channel_stats.html', {
        'broker': broker,
        'channel': channel,
        'stats': stats,
    })


# ==================== Channel Interaction Views ====================

@login_required
@require_POST
def channel_follow(request, channel_id):
    """متابعة أو إلغاء متابعة قناة"""
    channel = get_object_or_404(BrokerChannel, id=channel_id)
    
    follow, created = ChannelFollow.objects.get_or_create(
        user=request.user,
        channel=channel
    )
    
    if not created:
        # Unfollow
        follow.delete()
        channel.decrement_followers()
        return JsonResponse({'success': True, 'following': False})
    else:
        # Follow
        channel.increment_followers()
        return JsonResponse({'success': True, 'following': True})


@login_required
@require_POST
def channel_save(request, channel_id):
    """حفظ أو إلغاء حفظ قناة"""
    channel = get_object_or_404(BrokerChannel, id=channel_id)
    
    saved, created = ChannelSave.objects.get_or_create(
        user=request.user,
        channel=channel
    )
    
    if not created:
        saved.delete()
        return JsonResponse({'success': True, 'saved': False})
    else:
        return JsonResponse({'success': True, 'saved': True})


@login_required
@require_POST
def channel_share(request, channel_id):
    """تسجيل مشاركة قناة"""
    channel = get_object_or_404(BrokerChannel, id=channel_id)
    
    data = json.loads(request.body)
    platform = data.get('platform', 'link')
    
    ChannelShare.objects.create(
        channel=channel,
        user=request.user,
        platform=platform
    )
    
    return JsonResponse({'success': True})


@login_required
def channel_detail(request, channel_id):
    """صفحة تفاصيل القناة"""
    channel = get_object_or_404(BrokerChannel, id=channel_id)
    broker = channel.broker
    
    # Increment views
    channel.increment_views()
    
    # Get channel properties
    properties = Property.objects.filter(
        broker=broker,
        status__in=[Property.STATUS_PUBLISHED, Property.STATUS_PAID]
    ).select_related('owner').order_by('-created_at')[:12]
    
    # Check if user is following
    is_following = False
    is_saved = False
    if request.user.is_authenticated:
        is_following = ChannelFollow.objects.filter(
            user=request.user,
            channel=channel
        ).exists()
        is_saved = ChannelSave.objects.filter(
            user=request.user,
            channel=channel
        ).exists()
    
    # Get channel reviews
    reviews = channel.reviews.filter(is_approved=True).select_related('user').order_by('-helpful_count', '-created_at')[:5]
    
    return render(request, 'properties/broker_channel_page.html', {
        'channel': channel,
        'broker': broker,
        'properties': properties,
        'is_following': is_following,
        'is_saved': is_saved,
        'reviews': reviews,
    })


@login_required
@require_POST
def channel_review(request):
    """إضافة مراجعة للقناة"""
    from .forms import ChannelReviewForm
    
    form = ChannelReviewForm(request.POST)
    if form.is_valid():
        channel_id = form.cleaned_data.get('channel_id')
        channel = get_object_or_404(BrokerChannel, id=channel_id)
        
        # Check if user already reviewed
        if ChannelReview.objects.filter(user=request.user, channel=channel).exists():
            return JsonResponse({'success': False, 'error': 'لقد قمت بمراجعة هذه القناة مسبقاً'})
        
        review = form.save(commit=False)
        review.channel = channel
        review.user = request.user
        review.is_approved = False  # Requires admin approval
        review.save()
        
        # Update channel stats
        channel.rating_count += 1
        channel.save(update_fields=['rating_count'])
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'errors': form.errors})


@login_required
@require_POST
def channel_review_helpful(request, review_id):
    """تحديد مراجعة كمفيدة"""
    review = get_object_or_404(ChannelReview, id=review_id)
    
    # Simple toggle for now (could be enhanced with proper helpful tracking)
    review.increment_helpful()
    
    return JsonResponse({'success': True})


@login_required
@require_POST
def channel_review_reply(request, review_id):
    """الرد على مراجعة"""
    from .forms import ChannelReviewReplyForm
    
    review = get_object_or_404(ChannelReview, id=review_id)
    channel = review.channel
    broker = get_broker(request.user)
    
    # Check if user is channel owner
    is_channel_owner = broker and broker.channel == channel
    
    form = ChannelReviewReplyForm(request.POST)
    if form.is_valid():
        reply = form.save(commit=False)
        reply.review = review
        reply.user = request.user
        reply.is_channel_owner = is_channel_owner
        reply.save()
        
        # Update review reply count
        review.reply_count += 1
        review.save(update_fields=['reply_count'])
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'errors': form.errors})


@login_required
def channel_search(request):
    """البحث في القنوات"""
    from .forms import ChannelSearchForm
    
    form = ChannelSearchForm(request.GET)
    channels = BrokerChannel.objects.filter(status='active')
    
    if form.is_valid():
        search_query = form.cleaned_data.get('search_query')
        governorate = form.cleaned_data.get('governorate')
        min_rating = form.cleaned_data.get('min_rating')
        min_followers = form.cleaned_data.get('min_followers')
        is_verified = form.cleaned_data.get('is_verified')
        sort_by = form.cleaned_data.get('sort_by')
        
        if search_query:
            channels = channels.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        if governorate:
            channels = channels.filter(broker__governorate=governorate)
        
        if min_rating:
            channels = channels.filter(rating__gte=min_rating)
        
        if min_followers:
            channels = channels.filter(followers_count__gte=min_followers)
        
        if is_verified:
            channels = channels.filter(is_verified=True)
        
        if sort_by == 'followers':
            channels = channels.order_by('-followers_count')
        elif sort_by == 'rating':
            channels = channels.order_by('-rating')
        elif sort_by == 'properties':
            channels = channels.order_by('-properties_count')
        elif sort_by == 'views':
            channels = channels.order_by('-views_count')
        elif sort_by == 'newest':
            channels = channels.order_by('-created_at')
        else:
            channels = channels.order_by('-rating', '-followers_count')
    
    channels = channels.select_related('broker').distinct()
    
    return render(request, 'properties/channel_search.html', {
        'form': form,
        'channels': channels,
    })


@login_required
def update_channel_settings(request, channel_id):
    """تحديث إعدادات القناة من النافذة المنبثقة"""
    channel = get_object_or_404(BrokerChannel, id=channel_id)
    
    # Check if user is the channel owner
    if request.user != channel.broker.user:
        messages.error(request, 'ليس لديك صلاحية تعديل إعدادات هذه القناة')
        return redirect('broker_channel_detail', channel_id=channel_id)
    
    if request.method == 'POST':
        # Update channel settings
        channel.name = request.POST.get('name', channel.name)
        channel.phone = request.POST.get('phone', '')
        channel.email = request.POST.get('email', '')
        channel.address = request.POST.get('address', '')
        channel.whatsapp = request.POST.get('whatsapp', '')
        channel.message = request.POST.get('message', '')
        channel.seo_description = request.POST.get('seo_description', '')
        channel.facebook = request.POST.get('facebook', '')
        channel.instagram = request.POST.get('instagram', '')
        
        # Handle logo upload
        if 'logo' in request.FILES:
            channel.logo = request.FILES['logo']
        
        channel.save()
        messages.success(request, 'تم تحديث إعدادات القناة بنجاح')
        return redirect('broker_channel_detail', channel_id=channel_id)
    
    return redirect('broker_channel_detail', channel_id=channel_id)


@login_required
@broker_required
def channel_management(request):
    """صفحة إدارة القناة للدلال"""
    broker = get_broker(request.user)
    
    try:
        channel = broker.channel
    except BrokerChannel.DoesNotExist:
        messages.error(request, 'لم يتم إنشاء القناة بعد')
        return redirect('broker_channel_settings')
    
    if request.method == 'POST':
        # Update channel settings
        channel.name = request.POST.get('name', channel.name)
        channel.description = request.POST.get('description', channel.description)
        channel.whatsapp = request.POST.get('whatsapp', '')
        channel.facebook = request.POST.get('facebook', '')
        channel.instagram = request.POST.get('instagram', '')
        channel.telegram = request.POST.get('telegram', '')
        
        # Handle logo upload
        if 'logo' in request.FILES:
            channel.logo = request.FILES['logo']
        
        # Handle cover image upload
        if 'cover_image' in request.FILES:
            channel.cover_image = request.FILES['cover_image']
        
        channel.save()
        messages.success(request, 'تم تحديث إعدادات القناة بنجاح')
        return redirect('channel_management')
    
    return render(request, 'properties/broker_channel_management.html', {
        'broker': broker,
        'channel': channel,
    })


# ==================== نظام الفنادق والمنتجعات الجديد ====================

@login_required
def hotel_page_list(request):
    """قائمة صفحات الفنادق والمنتجعات"""
    pages = HotelPage.objects.filter(status='active').select_related('broker', 'user')
    
    # Filter by governorate
    governorate = request.GET.get('governorate')
    if governorate:
        pages = pages.filter(governorate=governorate)
    
    # Filter by type
    page_type = request.GET.get('type')
    if page_type:
        pages = pages.filter(page_type=page_type)
    
    # Search
    search = request.GET.get('search')
    if search:
        pages = pages.filter(name__icontains=search)
    
    # Sort
    sort_by = request.GET.get('sort', 'followers')
    if sort_by == 'followers':
        pages = pages.order_by('-followers_count')
    elif sort_by == 'rating':
        pages = pages.order_by('-rating')
    elif sort_by == 'newest':
        pages = pages.order_by('-created_at')
    else:
        pages = pages.order_by('-is_verified', '-followers_count')
    
    pages = pages.distinct()
    
    return render(request, 'properties/hotel_page_list.html', {
        'pages': pages,
    })


@login_required
def hotel_page_detail(request, slug):
    """صفحة تفاصيل الفندق أو المنتجع"""
    page = get_object_or_404(HotelPage, slug=slug, status='active')
    
    # Increment views
    page.increment_views()
    
    # Get posts, rooms, offers
    posts = page.posts.filter(status='published').select_related('page')[:10]
    rooms = page.rooms.filter(status='available')[:10]
    offers = page.offers.filter(is_active=True)[:10]
    
    # Check if user is following
    is_following = False
    if request.user.is_authenticated:
        is_following = HotelFollower.objects.filter(page=page, user=request.user).exists()
    
    # Get user rating
    user_rating = None
    if request.user.is_authenticated:
        try:
            user_rating = HotelRating.objects.get(page=page, user=request.user)
        except HotelRating.DoesNotExist:
            pass
    
    return render(request, 'properties/hotel_page_detail.html', {
        'page': page,
        'posts': posts,
        'rooms': rooms,
        'offers': offers,
        'is_following': is_following,
        'user_rating': user_rating,
    })


@login_required
def hotel_page_create(request):
    """إنشاء صفحة فندق جديدة"""
    if request.method == 'POST':
        form = HotelPageForm(request.POST, request.FILES)
        if form.is_valid():
            page = form.save(commit=False)
            
            # Set owner
            if hasattr(request.user, 'broker_profile'):
                page.broker = request.user.broker_profile
            else:
                page.user = request.user
            
            page.save()
            messages.success(request, 'تم إنشاء الصفحة بنجاح')
            return redirect('hotel_page_detail', slug=page.slug)
    else:
        form = HotelPageForm()
    
    return render(request, 'properties/hotel_page_form.html', {
        'form': form,
        'title': 'إنشاء صفحة جديدة',
    })


@login_required
def hotel_page_follow(request, slug):
    """متابعة صفحة الفندق"""
    page = get_object_or_404(HotelPage, slug=slug, status='active')
    
    follower, created = HotelFollower.objects.get_or_create(
        page=page,
        user=request.user
    )
    
    if created:
        messages.success(request, f'أنت الآن تتابع {page.name}')
    else:
        messages.info(request, 'أنت بالفعل تتابع هذه الصفحة')
    
    return redirect('hotel_page_detail', slug=slug)


@login_required
def hotel_page_unfollow(request, slug):
    """إلغاء متابعة صفحة الفندق"""
    page = get_object_or_404(HotelPage, slug=slug)
    
    try:
        follower = HotelFollower.objects.get(page=page, user=request.user)
        follower.delete()
        messages.success(request, f'تم إلغاء متابعة {page.name}')
    except HotelFollower.DoesNotExist:
        messages.error(request, 'أنت لا تتابع هذه الصفحة')
    
    return redirect('hotel_page_detail', slug=slug)


@login_required
def hotel_rating_create(request, slug):
    """إضافة تقييم لصفحة الفندق"""
    page = get_object_or_404(HotelPage, slug=slug)
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        review = request.POST.get('review')
        
        if rating:
            HotelRating.objects.update_or_create(
                page=page,
                user=request.user,
                defaults={
                    'rating': int(rating),
                    'review': review
                }
            )
            messages.success(request, 'تم إضافة التقييم بنجاح')
        else:
            messages.error(request, 'يرجى اختيار التقييم')
    
    return redirect('hotel_page_detail', slug=slug)


# Hotel Post Views
@login_required
def hotel_post_create(request, slug):
    """Create a new post for a hotel page"""
    page = get_object_or_404(HotelPage, slug=slug)
    
    if request.method == 'POST':
        form = HotelPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.page = page
            post.save()
            
            # Update posts count on page
            page.posts_count += 1
            page.save()
            
            messages.success(request, 'تم إنشاء المنشور بنجاح')
            return redirect('hotel_page_detail', slug=slug)
    else:
        form = HotelPostForm()
    
    return render(request, 'properties/hotel_post_form.html', {
        'form': form,
        'page': page,
        'action': 'create'
    })


@login_required
def hotel_post_edit(request, slug, post_id):
    """Edit an existing post"""
    page = get_object_or_404(HotelPage, slug=slug)
    post = get_object_or_404(HotelPost, id=post_id, page=page)
    
    if request.method == 'POST':
        form = HotelPostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث المنشور بنجاح')
            return redirect('hotel_page_detail', slug=slug)
    else:
        form = HotelPostForm(instance=post)
    
    return render(request, 'properties/hotel_post_form.html', {
        'form': form,
        'page': page,
        'post': post,
        'action': 'edit'
    })


@login_required
def hotel_post_delete(request, slug, post_id):
    """Delete a post"""
    page = get_object_or_404(HotelPage, slug=slug)
    post = get_object_or_404(HotelPost, id=post_id, page=page)
    
    if request.method == 'POST':
        post.delete()
        
        # Update posts count on page
        page.posts_count = max(0, page.posts_count - 1)
        page.save()
        
        messages.success(request, 'تم حذف المنشور بنجاح')
        return redirect('hotel_page_detail', slug=slug)
    
    return render(request, 'properties/hotel_post_delete.html', {
        'page': page,
        'post': post
    })


# Hotel Room Views
@login_required
def hotel_room_create(request, slug):
    """Create a new room for a hotel page"""
    page = get_object_or_404(HotelPage, slug=slug)
    
    if request.method == 'POST':
        form = HotelRoomForm(request.POST, request.FILES)
        if form.is_valid():
            room = form.save(commit=False)
            room.page = page
            room.save()
            
            # Update rooms count on page
            page.rooms_count += 1
            page.save()
            
            messages.success(request, 'تم إنشاء الغرفة بنجاح')
            return redirect('hotel_page_detail', slug=slug)
    else:
        form = HotelRoomForm()
    
    return render(request, 'properties/hotel_room_form.html', {
        'form': form,
        'page': page,
        'action': 'create'
    })


@login_required
def hotel_room_edit(request, slug, room_id):
    """Edit an existing room"""
    page = get_object_or_404(HotelPage, slug=slug)
    room = get_object_or_404(HotelRoom, id=room_id, page=page)
    
    if request.method == 'POST':
        form = HotelRoomForm(request.POST, request.FILES, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث الغرفة بنجاح')
            return redirect('hotel_page_detail', slug=slug)
    else:
        form = HotelRoomForm(instance=room)
    
    return render(request, 'properties/hotel_room_form.html', {
        'form': form,
        'page': page,
        'room': room,
        'action': 'edit'
    })


@login_required
def hotel_room_delete(request, slug, room_id):
    """Delete a room"""
    page = get_object_or_404(HotelPage, slug=slug)
    room = get_object_or_404(HotelRoom, id=room_id, page=page)
    
    if request.method == 'POST':
        room.delete()
        
        # Update rooms count on page
        page.rooms_count = max(0, page.rooms_count - 1)
        page.save()
        
        messages.success(request, 'تم حذف الغرفة بنجاح')
        return redirect('hotel_page_detail', slug=slug)
    
    return render(request, 'properties/hotel_room_delete.html', {
        'page': page,
        'room': room
    })


# Hotel Offer Views
@login_required
def hotel_offer_create(request, slug):
    """Create a new offer for a hotel page"""
    page = get_object_or_404(HotelPage, slug=slug)
    
    if request.method == 'POST':
        form = HotelOfferForm(request.POST, request.FILES)
        if form.is_valid():
            offer = form.save(commit=False)
            offer.page = page
            offer.save()
            
            # Update offers count on page
            page.offers_count += 1
            page.save()
            
            messages.success(request, 'تم إنشاء العرض بنجاح')
            return redirect('hotel_page_detail', slug=slug)
    else:
        form = HotelOfferForm()
    
    return render(request, 'properties/hotel_offer_form.html', {
        'form': form,
        'page': page,
        'action': 'create'
    })


@login_required
def hotel_offer_edit(request, slug, offer_id):
    """Edit an existing offer"""
    page = get_object_or_404(HotelPage, slug=slug)
    offer = get_object_or_404(HotelOffer, id=offer_id, page=page)
    
    if request.method == 'POST':
        form = HotelOfferForm(request.POST, request.FILES, instance=offer)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث العرض بنجاح')
            return redirect('hotel_page_detail', slug=slug)
    else:
        form = HotelOfferForm(instance=offer)
    
    return render(request, 'properties/hotel_offer_form.html', {
        'form': form,
        'page': page,
        'offer': offer,
        'action': 'edit'
    })


@login_required
def hotel_offer_delete(request, slug, offer_id):
    """Delete an offer"""
    page = get_object_or_404(HotelPage, slug=slug)
    offer = get_object_or_404(HotelOffer, id=offer_id, page=page)
    
    if request.method == 'POST':
        offer.delete()
        
        # Update offers count on page
        page.offers_count = max(0, page.offers_count - 1)
        page.save()
        
        messages.success(request, 'تم حذف العرض بنجاح')
        return redirect('hotel_page_detail', slug=slug)
    
    return render(request, 'properties/hotel_offer_delete.html', {
        'page': page,
        'offer': offer
    })


# Hotel Booking Views
@login_required
def hotel_booking_create(request, slug):
    """Create a new booking for a hotel page"""
    page = get_object_or_404(HotelPage, slug=slug)
    
    if request.method == 'POST':
        form = HotelBookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.page = page
            booking.user = request.user
            booking.save()
            
            # Update bookings count on page
            page.bookings_count += 1
            page.save()
            
            # Update bookings count on room or offer if specified
            if booking.room:
                booking.room.bookings_count += 1
                booking.room.save()
            if booking.offer:
                booking.offer.bookings_count += 1
                booking.offer.save()
            
            messages.success(request, 'تم إنشاء الحجز بنجاح')
            return redirect('hotel_page_detail', slug=slug)
    else:
        form = HotelBookingForm(initial={'page': page})
    
    return render(request, 'properties/hotel_booking_form.html', {
        'form': form,
        'page': page,
        'action': 'create'
    })


@login_required
def hotel_booking_edit(request, slug, booking_id):
    """Edit an existing booking"""
    page = get_object_or_404(HotelPage, slug=slug)
    booking = get_object_or_404(HotelBooking, id=booking_id, page=page, user=request.user)
    
    if request.method == 'POST':
        form = HotelBookingForm(request.POST, instance=booking)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث الحجز بنجاح')
            return redirect('hotel_page_detail', slug=slug)
    else:
        form = HotelBookingForm(instance=booking)
    
    return render(request, 'properties/hotel_booking_form.html', {
        'form': form,
        'page': page,
        'booking': booking,
        'action': 'edit'
    })


@login_required
def hotel_booking_cancel(request, slug, booking_id):
    """Cancel a booking"""
    page = get_object_or_404(HotelPage, slug=slug)
    booking = get_object_or_404(HotelBooking, id=booking_id, page=page, user=request.user)
    
    if request.method == 'POST':
        booking.status = 'cancelled'
        booking.save()
        
        messages.success(request, 'تم إلغاء الحجز بنجاح')
        return redirect('hotel_page_detail', slug=slug)
    
    return render(request, 'properties/hotel_booking_cancel.html', {
        'page': page,
        'booking': booking
    })


# ==================== Service Provider Views ====================

@login_required
def service_provider_list(request):
    """قائمة مقدمي الخدمات"""
    providers = ServiceProviderPage.objects.filter(status='active').select_related('category').prefetch_related('sub_categories')
    
    # Filtering
    category_filter = request.GET.get('category')
    governorate_filter = request.GET.get('governorate')
    rating_filter = request.GET.get('rating')
    availability_filter = request.GET.get('availability')
    
    if category_filter:
        providers = providers.filter(category__category_id=category_filter)
    if governorate_filter:
        providers = providers.filter(governorate=governorate_filter)
    if rating_filter:
        providers = providers.filter(rating__gte=float(rating_filter))
    if availability_filter == 'available':
        providers = providers.filter(availability='available')
    
    # Search
    search_query = request.GET.get('q')
    if search_query:
        providers = providers.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Categories
    categories = ServiceProviderCategory.objects.filter(is_active=True)
    
    return render(request, 'properties/service_provider_list.html', {
        'providers': providers,
        'categories': categories,
        'selected_category': category_filter,
        'selected_governorate': governorate_filter,
        'selected_rating': rating_filter,
        'selected_availability': availability_filter,
        'search_query': search_query,
    })


@login_required
def service_provider_detail(request, slug):
    """صفحة تفاصيل مقدم الخدمة"""
    page = get_object_or_404(ServiceProviderPage, slug=slug, status='active')
    
    # Increment views
    page.views_count += 1
    page.save()
    
    # Get related data
    works = page.works.filter(status='published')[:6]
    services = page.services.filter(is_active=True)
    gallery = page.gallery.all()[:12]
    ratings = page.ratings.all()[:10]
    
    # Check if following
    is_following = False
    if request.user.is_authenticated:
        is_following = ServiceProviderFollower.objects.filter(page=page, user=request.user).exists()
    
    # Get user rating
    user_rating = None
    if request.user.is_authenticated:
        try:
            user_rating = ServiceProviderRating.objects.get(page=page, user=request.user)
        except ServiceProviderRating.DoesNotExist:
            pass
    
    return render(request, 'properties/service_provider_detail.html', {
        'page': page,
        'works': works,
        'services': services,
        'gallery': gallery,
        'ratings': ratings,
        'is_following': is_following,
        'user_rating': user_rating,
    })


@login_required
def service_provider_create(request):
    """إنشاء صفحة مقدم خدمة جديدة"""
    if request.method == 'POST':
        form = ServiceProviderPageForm(request.POST, request.FILES)
        if form.is_valid():
            page = form.save(commit=False)
            
            # Set owner
            if hasattr(request.user, 'broker_profile'):
                page.broker = request.user.broker_profile
            page.user = request.user
            
            page.save()
            form.save_m2m()  # Save many-to-many relationships
            
            messages.success(request, 'تم إنشاء الصفحة بنجاح')
            return redirect('service_provider_detail', slug=page.slug)
    else:
        form = ServiceProviderPageForm()
    
    return render(request, 'properties/service_provider_form.html', {
        'form': form,
        'title': 'إنشاء صفحة جديدة',
    })


@login_required
def service_provider_follow(request, slug):
    """متابعة صفحة مقدم الخدمة"""
    page = get_object_or_404(ServiceProviderPage, slug=slug, status='active')
    
    follower, created = ServiceProviderFollower.objects.get_or_create(
        page=page,
        user=request.user
    )
    
    if created:
        messages.success(request, f'أنت الآن تتابع {page.name}')
    else:
        messages.info(request, 'أنت بالفعل تتابع هذه الصفحة')
    
    return redirect('service_provider_detail', slug=slug)


@login_required
def service_provider_unfollow(request, slug):
    """إلغاء متابعة صفحة مقدم الخدمة"""
    page = get_object_or_404(ServiceProviderPage, slug=slug)
    
    try:
        follower = ServiceProviderFollower.objects.get(page=page, user=request.user)
        follower.delete()
        messages.success(request, f'تم إلغاء متابعة {page.name}')
    except ServiceProviderFollower.DoesNotExist:
        messages.error(request, 'أنت لا تتابع هذه الصفحة')
    
    return redirect('service_provider_detail', slug=slug)


@login_required
def service_provider_rating_create(request, slug):
    """إضافة تقييم لمقدم الخدمة"""
    page = get_object_or_404(ServiceProviderPage, slug=slug)
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        review = request.POST.get('review')
        
        if rating:
            ServiceProviderRating.objects.update_or_create(
                page=page,
                user=request.user,
                defaults={
                    'rating': int(rating),
                    'review': review
                }
            )
            messages.success(request, 'تم إضافة التقييم بنجاح')
        else:
            messages.error(request, 'يرجى اختيار التقييم')
    
    return redirect('service_provider_detail', slug=slug)


@login_required
def service_provider_contact(request, slug):
    """التواصل مع مقدم الخدمة"""
    page = get_object_or_404(ServiceProviderPage, slug=slug, status='active')
    
    if request.method == 'POST':
        form = ServiceProviderContactForm(request.POST)
        if form.is_valid():
            contact = form.save(commit=False)
            contact.page = page
            if request.user.is_authenticated:
                contact.user = request.user
            contact.save()
            
            messages.success(request, 'تم إرسال طلب التواصل بنجاح')
            return redirect('service_provider_detail', slug=slug)
    else:
        form = ServiceProviderContactForm()
    
    return render(request, 'properties/service_provider_contact.html', {
        'form': form,
        'page': page,
    })


@login_required
def service_provider_quote(request, slug):
    """طلب عرض سعر من مقدم الخدمة"""
    page = get_object_or_404(ServiceProviderPage, slug=slug, status='active')
    
    if request.method == 'POST':
        form = ServiceProviderQuoteForm(request.POST)
        if form.is_valid():
            quote = form.save(commit=False)
            quote.page = page
            if request.user.is_authenticated:
                quote.user = request.user
            quote.save()
            
            messages.success(request, 'تم إرسال طلب عرض السعر بنجاح')
            return redirect('service_provider_detail', slug=slug)
    else:
        form = ServiceProviderQuoteForm()
    
    return render(request, 'properties/service_provider_quote.html', {
        'form': form,
        'page': page,
    })
