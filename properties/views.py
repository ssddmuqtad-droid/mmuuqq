import logging
import json

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


from .decorators import broker_required, rate_limit
from .forms import MessageForm, PropertyForm, PropertySearchForm, SiteSettingsForm, PropertyNoteForm, VirtualTour360Form, AuctionForm, BidForm, BuildingRequestForm, LandInfoForm, BuildingDetailsForm, BudgetForm, QuoteForm, ContractorBidForm, ContractorRatingForm, ReportForm, FinancialTransactionForm, ExpenseForm, ProfitForm, SubscriptionPlanForm, UserProfileForm, UserBasicInfoForm, UserSecurityForm, UserNotificationForm, UserPrivacyForm, UserPreferencesForm, BlockUserForm, SavedSearchForm, AutoBidForm, AuctionRatingForm, AuctionLiveStreamForm, AuctionAdvertisementForm, HotelSearchForm, ResortSearchForm
from .models import Message, Property, PropertyImage, SiteSettings, PropertyNote, Notification, VirtualTour360, Auction, Bid, BuildingRequest, LandInfo, BuildingDetails, Budget, Blueprint, Quote, ProjectTracking, DeliveryMilestone, ContractorRating, ContractorBid, FinancialTransaction, Expense, Payment, OfficeWallet, WalletTransaction, Broker, Report, ReportAction, PropertyLike, PropertySave, PropertyComment, VirtualTourPoint, VirtualTourConnection, Profit, SubscriptionPlan, ActivityLog, UserSettings, BlockedUser, SavedSearch, AutoBid, AuctionNotification, AuctionRating, AuctionStats, AuctionLiveStream, AuctionAdvertisement, Hotel, Resort, BrokerChannel, ChannelFollow, ChannelSave
from .permissions import (
    can_access_dashboard,
    can_add_property,
    can_delete_property,
    can_edit_property,
    can_manage_brokers,
    can_manage_site_settings,
    can_replace_property,
    get_accessible_messages,
    get_accessible_properties,
    get_broker,
    get_broker_stats,
    get_managed_brokers,
    is_platform_admin,
)
from .utils import filter_properties, get_public_properties, save_gallery_images, save_gallery_videos, sort_properties

logger = logging.getLogger('properties')

staff_required = user_passes_test(lambda u: u.is_authenticated and can_access_dashboard(u))


def get_client_ip(request):
    """Get the client's IP address from the request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def home(request):
    properties = get_public_properties()
    form = PropertySearchForm(request.GET)
    properties = filter_properties(properties, request.GET)
    properties = sort_properties(properties, request.GET.get('sort'))
    
    # Get featured and promoted before pagination to avoid N+1 queries
    featured_properties = [p for p in properties if p.is_featured][:6]
    promoted_properties = [p for p in properties if p.is_promoted][:4]
    
    # Get dallal properties if system is enabled
    dallal_properties = []
    try:
        from .dallal_logic import get_dallal_properties_for_display
        dallal_properties = get_dallal_properties_for_display()[:8]
    except Exception:
        dallal_properties = []
    
    paginator = Paginator(properties, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    query_string = request.GET.urlencode()
    
    return render(request, 'properties/home.html', {
        'properties': page_obj,
        'page_obj': page_obj,
        'form': form,
        'featured_properties': featured_properties,
        'promoted_properties': promoted_properties,
        'dallal_properties': dallal_properties,
        'query_string': query_string,
    })


def property_detail(request, slug):
    property_obj = get_object_or_404(Property, slug=slug)
    if property_obj.status not in ['ready', 'under-construction', 'rent'] and not can_access_dashboard(request.user):
        messages.warning(request, 'هذا العقار غير متاح حالياً.')
        return redirect('home')

    property_obj.increment_views()
    images = property_obj.get_all_images()
    videos = property_obj.gallery_videos.all()
    
    # Track views for broker statistics
    if property_obj.broker:
        from .models import BrokerIndividualStats
        stats, created = BrokerIndividualStats.objects.get_or_create(broker=property_obj.broker)
        stats.update_views_stats()
    
    # Get virtual tours
    try:
        virtual_tours = property_obj.virtual_tours.all()
    except Exception:
        virtual_tours = []

    related = get_public_properties().filter(
        Q(district=property_obj.district) | Q(type=property_obj.type)
    ).exclude(pk=property_obj.pk).prefetch_related('gallery_images')[:4]

    message_form = MessageForm()
    return render(request, 'properties/property_detail.html', {
        'property': property_obj,
        'images': images,
        'videos': videos,
        'virtual_tours': virtual_tours,
        'related_properties': related,
        'message_form': message_form,
    })


def property_detail_legacy(request, property_id):
    prop = get_object_or_404(Property, pk=property_id)
    return redirect(prop.get_absolute_url(), permanent=True)


def about_page(request):
    settings = SiteSettings.get_solo()
    return render(request, 'properties/about.html', {
        'site_settings': settings,
        'total_properties': len(get_public_properties()),
    })


def contact_page(request):
    settings = SiteSettings.get_solo()
    form = MessageForm()
    return render(request, 'properties/contact.html', {
        'settings': settings,
        'form': form,
    })


def subscription_plans(request):
    """Display subscription plans page."""
    settings = SiteSettings.get_solo()
    return render(request, 'properties/subscription_plans.html', {
        'site_settings': settings,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subscription_expire_notification(request):
    """Handle subscription expiration notification from client."""
    if not request.user.is_authenticated or not hasattr(request.user, 'broker_profile'):
        return Response({'error': 'Unauthorized'}, status=401)
    
    broker = request.user.broker_profile
    
    # Create notification for broker
    from django.core.mail import send_mail
    
    # Send email notification to broker
    if broker.user.email:
        send_mail(
            'انتهاء اشتراكك في دلال',
            'عزيزي الدلال،\n\nاشتراكك في منصة دلال قد انتهى. يرجى تجديده للمتابعة في استخدام الخدمة.\n\nيمكنك تجديد اشتراكك من خلال الرابط التالي:\nhttps://yourdomain.com/subscription-plans/\n\nشكراً لاستخدامك منصة دلال.',
            settings.DEFAULT_FROM_EMAIL,
            [broker.user.email],
            fail_silently=True,
        )
    
    # Send notification to admin
    admin_users = User.objects.filter(is_superuser=True, email__isnull=False)
    for admin in admin_users:
        if admin.email:
            send_mail(
                f'انتهاء اشتراك الدلال: {broker.display_name}',
                f'اشتراك الدلال {broker.display_name} قد انتهى.\n\nرقم الهاتف: {broker.phone}\nتاريخ الانتهاء: {broker.subscription_end_date}',
                settings.DEFAULT_FROM_EMAIL,
                [admin.email],
                fail_silently=True,
            )
    
    return Response({'success': True, 'message': 'Notification sent successfully'})


@login_required
def main_broker_panel(request):
    """Main broker panel to manage sub brokers and their properties"""
    if not hasattr(request.user, 'broker_profile'):
        messages.error(request, 'يجب أن تكون دلالاً للوصول إلى هذه الصفحة')
        return redirect('home')
    
    broker = request.user.broker_profile
    
    # Check if user is main broker
    if broker.role != Broker.ROLE_MAIN and broker.role != Broker.ROLE_ADMIN:
        messages.error(request, 'يجب أن تكون دلالاً رئيسياً للوصول إلى هذه الصفحة')
        return redirect('home')
    
    # Get sub brokers
    sub_brokers = broker.sub_brokers.filter(is_active=True)
    
    # Get all properties from sub brokers
    from django.db.models import Count, Q
    sub_broker_properties = Property.objects.filter(
        Q(broker__in=sub_brokers) | Q(owner__in=[b.user for b in sub_brokers])
    ).select_related('broker', 'owner')
    
    # Statistics
    total_sub_brokers = sub_brokers.count()
    total_properties = sub_broker_properties.count()
    active_properties = sub_broker_properties.filter(status='ready').count()
    
    # Recent activity
    recent_properties = sub_broker_properties.order_by('-created_at')[:10]
    
    context = {
        'broker': broker,
        'sub_brokers': sub_brokers,
        'sub_broker_properties': sub_broker_properties,
        'total_sub_brokers': total_sub_brokers,
        'total_properties': total_properties,
        'active_properties': active_properties,
        'recent_properties': recent_properties,
    }
    
    return render(request, 'properties/main_broker_panel.html', context)


def broker_profile(request, username):
    """Display broker's profile with their properties only."""
    broker = get_object_or_404(Broker, user__username=username)
    
    # Get only this broker's properties
    properties = Property.objects.filter(
        Q(broker=broker) | Q(owner=broker.user),
        status__in=['ready', 'under-construction', 'rent']
    ).select_related().prefetch_related('gallery_images')
    
    # Apply search filters
    properties = filter_properties(properties, request.GET)
    properties = sort_properties(properties, request.GET.get('sort'))
    
    # Pagination
    paginator = Paginator(properties, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    query_string = request.GET.urlencode()
    
    # Get broker stats
    property_count = broker.get_published_properties_count()
    property_limit = broker.get_property_limit()
    remaining_properties = broker.get_remaining_properties()
    days_elapsed = broker.get_days_elapsed()
    days_remaining = broker.get_days_remaining()
    
    return render(request, 'properties/broker_profile.html', {
        'broker': broker,
        'properties': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'property_count': property_count,
        'property_limit': property_limit,
        'remaining_properties': remaining_properties,
        'days_elapsed': days_elapsed,
        'days_remaining': days_remaining,
    })


def login_view(request):
    from .permissions import get_redirect_after_login, get_user_type, can_access_dashboard

    if request.user.is_authenticated:
        redirect_url = get_redirect_after_login(request.user)
        return redirect(redirect_url)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            user_type = get_user_type(user)

            # Simplified redirect: always go to home first to avoid redirect loops
            messages.success(request, 'تم تسجيل الدخول بنجاح')
            return redirect('home')
        messages.error(request, 'بيانات الدخول غير صحيحة')
        logger.warning('Failed login attempt for user: %s', username)
    return render(request, 'properties/login.html')


def register_view(request):
    """Register a new user account."""
    from django.contrib.auth.models import User
    
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        # Validation
        if not username or not email or not password:
            messages.error(request, 'يرجى ملء جميع الحقول المطلوبة')
        elif password != confirm_password:
            messages.error(request, 'كلمات المرور غير متطابقة')
        elif len(password) < 6:
            messages.error(request, 'كلمة المرور يجب أن تكون 6 أحرف على الأقل')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'اسم المستخدم مستخدم بالفعل')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'البريد الإلكتروني مستخدم بالفعل')
        else:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
                is_staff=True  # Brokers need is_staff=True for dashboard access
            )

            # Create Broker profile automatically
            from .models import Broker
            broker = Broker.objects.create(
                user=user,
                phone=phone,
                role=Broker.ROLE_MAIN,
                is_active=True,
            )

            # Create notification for admins
            from .utils import create_notification
            admins = User.objects.filter(is_superuser=True) | User.objects.filter(is_staff=True)
            
            for admin in admins:
                create_notification(
                    user=admin,
                    notification_type='system',
                    title='مستخدم جديد',
                    message=f'مستخدم جديد: {user.get_full_name() or user.username}',
                    link=f'/admin/auth/user/{user.id}/change/',
                    metadata={'user_id': user.id}
                )
            
            # Log activity
            from .models import ActivityLog
            ActivityLog.log(
                user=user,
                action='create',
                model_type='user',
                object_id=user.id,
                object_repr=user.username,
                description=f'إنشاء حساب مستخدم جديد: {user.username}',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                metadata={'account_type': 'user'}
            )
            
            messages.success(request, 'تم إنشاء الحساب بنجاح. يمكنك الآن تسجيل الدخول')
            return redirect('login')
    
    return render(request, 'properties/register.html')


def logout_view(request):
    logout(request)
    messages.info(request, 'تم تسجيل الخروج بنجاح')
    return redirect('home')


@login_required
# Temporarily disabled staff_required to prevent redirect loops
# @staff_required
def dashboard(request):
    properties = get_accessible_properties(request.user).prefetch_related('gallery_images', 'broker', 'owner')
    
    # Add pagination for properties
    paginator = Paginator(properties, 25)
    page_number = request.GET.get('page', 1)
    properties = paginator.get_page(page_number)
    
    # Get unread messages with optimized query
    unread = get_accessible_messages(request.user).filter(is_read=False, is_archived=False).select_related('property')[:20]
    broker = get_broker(request.user)
    
    # Try to get notes with optimized query
    notes = []
    pending_notes_count = 0
    try:
        notes = PropertyNote.objects.select_related('property')[:20]
        pending_notes_count = PropertyNote.objects.filter(is_completed=False).count()
    except Exception:
        # PropertyNote table doesn't exist yet (migration not applied)
        notes = []
        pending_notes_count = 0
    
    # Try to get notifications
    notifications = []
    unread_notifications_count = 0
    try:
        notifications = Notification.objects.filter(user=request.user).select_related('property')[:20]
        unread_notifications_count = Notification.objects.filter(user=request.user, is_read=False).count()
    except Exception:
        # Notification table doesn't exist yet (migration not applied)
        notifications = []
        unread_notifications_count = 0
    
    # Get auctions with optimized query
    auctions_list = []
    try:
        auctions_list = Auction.objects.all().select_related('property', 'broker').order_by('-created_at')[:20]
    except Exception:
        auctions_list = []
    
    # Get building requests with optimized query
    building_requests_list = []
    try:
        building_requests_list = BuildingRequest.objects.all().select_related('land_info', 'building_details', 'budget').order_by('-created_at')[:20]
    except Exception:
        building_requests_list = []
    
    # Get activity logs with optimized query
    activity_logs = []
    try:
        activity_logs = ActivityLog.objects.all().select_related('user').order_by('-created_at')[:50]
    except Exception:
        activity_logs = []
    
    settings = SiteSettings.get_solo()
    settings_form = SiteSettingsForm(instance=settings)
    property_form = PropertyForm()
    
    # Only create note form if PropertyNote table exists
    try:
        note_form = PropertyNoteForm()
    except Exception:
        note_form = None

    stats = get_broker_stats(request.user)
    stats['pending_notes'] = pending_notes_count
    stats['unread_notifications'] = unread_notifications_count
    stats['total'] = stats['total_properties']
    stats['featured'] = stats['featured_properties']
    stats['unread_messages'] = stats.get('unread_messages', 0)

    # Admin-only data
    all_conversations = []
    all_reports = []
    all_users = []
    subscription_plans = []
    platform_stats = {}
    pending_properties = []
    recent_payments = []
    staff_users = []
    backups = []
    support_tickets = []
    subscription_requests = []  # Fixed UnboundLocalError
    
    if request.user.is_superuser:
        try:
            from .models import Conversation, MessageReport, SubscriptionPlan, FinancialTransaction
            all_conversations = Conversation.objects.all().prefetch_related('participants_info', 'chat_messages')
            all_reports = MessageReport.objects.all().select_related('reporter', 'message', 'message__sender')
            all_users = User.objects.all().order_by('-date_joined')
            subscription_plans = SubscriptionPlan.objects.all()
            pending_properties = Property.objects.filter(status='pending').select_related('owner', 'broker')
            recent_payments = FinancialTransaction.objects.all().select_related('user').order_by('-created_at')[:20]
            staff_users = User.objects.filter(is_staff=True).order_by('-last_login')
            
            # Platform statistics
            platform_stats = {
                'total_users': User.objects.count(),
                'total_conversations': Conversation.objects.count(),
                'total_messages': 0,
                'total_reports': MessageReport.objects.count(),
                'total_brokers': Broker.objects.count(),
                'total_regular_users': User.objects.filter(is_superuser=False, is_staff=False).count() - Broker.objects.count(),
                'total_admins': User.objects.filter(is_superuser=True).count(),
                'active_subscriptions': Broker.objects.filter(subscription_plan__isnull=False).count(),
                'total_revenue': sum(t.amount or 0 for t in FinancialTransaction.objects.filter(status='completed')),
                'active_ads': Property.objects.filter(is_featured=True).count(),
                'pending_payments': FinancialTransaction.objects.filter(status='pending').count(),
                'completed_payments': FinancialTransaction.objects.filter(status='completed').count(),
                'total_backups': 0,
                'last_backup_size': 0,
                'last_backup_date': '--',
                'total_tickets': 0,
                'pending_tickets': 0,
                'resolved_tickets': 0,
            }
            try:
                from .models import ChatMessage
                platform_stats['total_messages'] = ChatMessage.objects.count()
            except Exception:
                pass
            
            # Try to get backup stats
            try:
                from .models import Backup
                backups = Backup.objects.all().order_by('-created_at')[:10]
                platform_stats['total_backups'] = Backup.objects.count()
                if backups.exists():
                    latest = backups.first()
                    platform_stats['last_backup_size'] = latest.size
                    platform_stats['last_backup_date'] = latest.created_at.strftime('%Y-%m-%d')
            except Exception:
                pass
            
            # Try to get support tickets
            try:
                from .models import SupportTicket
                support_tickets = SupportTicket.objects.all().select_related('user').order_by('-created_at')[:20]
                platform_stats['total_tickets'] = SupportTicket.objects.count()
                platform_stats['pending_tickets'] = SupportTicket.objects.filter(status='pending').count()
                platform_stats['resolved_tickets'] = SupportTicket.objects.filter(status='resolved').count()
            except Exception:
                pass
            
            # Try to get subscription requests
            try:
                from .models import SubscriptionRequest
                subscription_requests = SubscriptionRequest.objects.all().select_related('user', 'current_plan', 'requested_plan').order_by('-created_at')[:50]
            except Exception:
                subscription_requests = []
        except Exception as e:
            logger.error(f"Error loading admin data: {e}")

    return render(request, 'properties/dashboard.html', {
        'properties': properties,
        'messages_list': unread,
        'notes_list': notes,
        'notifications_list': notifications,
        'auctions_list': auctions_list,
        'building_requests_list': building_requests_list,
        'activity_logs': activity_logs,
        'settings_form': settings_form,
        'property_form': property_form,
        'note_form': note_form,
        'stats': stats,
        'broker': broker,
        'can_manage_brokers': can_manage_brokers(request.user),
        'can_manage_settings': can_manage_site_settings(request.user),
        'managed_brokers': get_managed_brokers(request.user).annotate(
            property_count=Count('user__owned_properties', distinct=True)
        ) if can_manage_brokers(request.user) else [],
        'all_conversations': all_conversations,
        'all_reports': all_reports,
        'all_users': all_users,
        'subscription_plans': subscription_plans,
        'platform_stats': platform_stats,
        'pending_properties': pending_properties,
        'recent_payments': recent_payments,
        'staff_users': staff_users,
        'backups': backups,
        'support_tickets': support_tickets,
        'subscription_requests': subscription_requests,
    })


@login_required
@staff_required
@require_POST
def update_site_settings(request):
    if not can_manage_site_settings(request.user):
        messages.error(request, 'ليس لديك صلاحية تعديل إعدادات الموقع')
        return redirect('dashboard')
    settings = SiteSettings.get_solo()
    form = SiteSettingsForm(request.POST, instance=settings)
    if form.is_valid():
        form.save()
        messages.success(request, 'تم حفظ إعدادات الموقع')
    else:
        messages.error(request, 'تحقق من الحقول المدخلة')
    return redirect('dashboard')


@login_required
@staff_required
def settings_general(request):
    """General settings page."""
    if not can_manage_site_settings(request.user):
        messages.error(request, 'ليس لديك صلاحية تعديل إعدادات الموقع')
        return redirect('dashboard')
    settings = SiteSettings.get_solo()
    if request.method == 'POST':
        settings.site_name = request.POST.get('site_name', 'دلال')
        settings.tagline = request.POST.get('tagline', '')
        settings.site_description = request.POST.get('site_description', '')
        settings.default_language = request.POST.get('default_language', 'ar')
        settings.timezone = request.POST.get('timezone', 'Asia/Baghdad')
        settings.date_format = request.POST.get('date_format', 'Y-m-d')
        settings.time_format = request.POST.get('time_format', 'H:i')
        if 'favicon' in request.FILES:
            settings.favicon = request.FILES['favicon']
        settings.save()
        messages.success(request, 'تم تحديث الإعدادات العامة بنجاح')
        return redirect('settings_general')
    
    return render(request, 'properties/settings_general.html', {'settings': settings, 'section': 'general'})


@login_required
@staff_required
def settings_maintenance(request):
    """Maintenance mode settings page."""
    if not can_manage_site_settings(request.user):
        messages.error(request, 'ليس لديك صلاحية تعديل إعدادات الموقع')
        return redirect('dashboard')
    
    settings = SiteSettings.get_solo()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'toggle_maintenance':
            old_status = settings.maintenance_mode
            settings.maintenance_mode = not settings.maintenance_mode
            settings.save()
            
            # Log the action
            from .models import ActivityLog
            ActivityLog.objects.create(
                user=request.user,
                action=f"تغيير وضع الصيانة من {'مفعل' if old_status else 'معطل'} إلى {'مفعل' if settings.maintenance_mode else 'معطل'}",
                details=f"تم تغيير وضع الصيانة بواسطة {request.user.username}"
            )
            
            status_text = 'تفعيل' if settings.maintenance_mode else 'إلغاء'
            messages.success(request, f'تم {status_text} وضع الصيانة بنجاح')
            
        elif action == 'update_message':
            settings.maintenance_message = request.POST.get('maintenance_message', settings.maintenance_message)
            settings.maintenance_end_time = request.POST.get('maintenance_end_time') or None
            settings.allow_admins_during_maintenance = request.POST.get('allow_admins_during_maintenance') == 'on'
            settings.save()
            messages.success(request, 'تم تحديث إعدادات الصيانة بنجاح')
        
        return redirect('settings_maintenance')
    
    return render(request, 'properties/settings_maintenance.html', {'settings': settings, 'section': 'maintenance'})


@login_required
@staff_required
def admin_channels_list(request):
    """Admin view to manage all broker channels."""
    from .models import BrokerChannel
    
    if not request.user.is_superuser:
        messages.error(request, 'ليس لديك صلاحية الوصول لهذه الصفحة')
        return redirect('dashboard')
    
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')
    
    channels = BrokerChannel.objects.all().select_related('broker', 'broker__user')
    
    if status_filter != 'all':
        channels = channels.filter(status=status_filter)
    
    if search_query:
        channels = channels.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(broker__display_name__icontains=search_query) |
            Q(broker__user__username__icontains=search_query)
        )
    
    channels = channels.order_by('-created_at')
    
    return render(request, 'properties/admin_channels_list.html', {
        'channels': channels,
        'status_filter': status_filter,
        'search_query': search_query,
    })


@login_required
@staff_required
def admin_channel_approve(request, channel_id):
    """Approve a broker channel."""
    from .models import BrokerChannel
    
    if not request.user.is_superuser:
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    
    channel = get_object_or_404(BrokerChannel, id=channel_id)
    channel.status = 'active'
    channel.save()
    
    messages.success(request, f'تم تفعيل قناة {channel.name} بنجاح')
    return redirect('admin_channels_list')


@login_required
@staff_required
def admin_channel_reject(request, channel_id):
    """Reject/suspend a broker channel."""
    from .models import BrokerChannel
    
    if not request.user.is_superuser:
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    
    channel = get_object_or_404(BrokerChannel, id=channel_id)
    channel.status = 'suspended'
    channel.save()
    
    messages.success(request, f'تم إيقاف قناة {channel.name}')
    return redirect('admin_channels_list')


@login_required
@staff_required
def admin_channel_verify(request, channel_id):
    """Verify a broker channel."""
    from .models import BrokerChannel
    
    if not request.user.is_superuser:
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    
    channel = get_object_or_404(BrokerChannel, id=channel_id)
    channel.is_verified = True
    channel.save()
    
    messages.success(request, f'تم توثيق قناة {channel.name} بنجاح')
    return redirect('admin_channels_list')


@login_required
@staff_required
def user_details_api(request, user_id):
    """API endpoint to get user details for modal."""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'}, status=403)
    
    try:
        user = User.objects.get(id=user_id)
        
        # Get user activities
        activities = []
        try:
            from .models import ActivityLog
            user_activities = ActivityLog.objects.filter(user=user).order_by('-created_at')[:10]
            for activity in user_activities:
                activities.append({
                    'action': activity.action,
                    'date': activity.created_at.strftime('%Y-%m-%d %H:%M'),
                    'ip': activity.ip_address or '--'
                })
        except Exception:
            pass
        
        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'date_joined': user.date_joined.strftime('%Y-%m-%d %H:%M'),
            'last_login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else None,
            'is_active': user.is_active,
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
            'avatar': None,  # Add avatar field if exists
            'password': '••••••••',  # Never send real password
            'conversations_count': user.conversationparticipant_set.count(),
            'messages_count': 0,  # Add if message model exists
            'reports_count': user.messagereport_reporter.count(),
            'properties_count': 0,  # Add if property relation exists
            'activities': activities
        }
        
        return JsonResponse({'success': True, 'user': user_data})
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'المستخدم غير موجود'}, status=404)
    except Exception as e:
        logger.error(f"Error getting user details: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@staff_required
def toggle_user_status_api(request, user_id):
    """API endpoint to toggle user status."""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'}, status=403)
    
    try:
        user = User.objects.get(id=user_id)
        user.is_active = not user.is_active
        user.save()
        return JsonResponse({'success': True})
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'المستخدم غير موجود'}, status=404)
    except Exception as e:
        logger.error(f"Error toggling user status: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@staff_required
def subscription_plan_details_api(request, plan_id):
    """API endpoint to get subscription plan details."""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'}, status=403)
    
    try:
        from .models import SubscriptionPlan
        plan = SubscriptionPlan.objects.get(id=plan_id)
        
        plan_data = {
            'id': plan.id,
            'name': plan.name,
            'period': plan.period,
            'ads_limit': plan.ads_limit,
            'price': str(plan.price),
            'price_per_property': str(plan.price_per_property),
            'color': plan.color,
            'is_active': plan.is_active,
            'subscribers_count': plan.broker_set.count()
        }
        
        return JsonResponse({'success': True, 'plan': plan_data})
    except SubscriptionPlan.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'الخطة غير موجودة'}, status=404)
    except Exception as e:
        logger.error(f"Error getting plan details: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@staff_required
@require_POST
def subscription_plan_create_api(request):
    """API endpoint to create subscription plan."""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'}, status=403)
    
    try:
        from .models import SubscriptionPlan
        data = json.loads(request.body)
        
        plan = SubscriptionPlan.objects.create(
            name=data.get('name'),
            period=data.get('period'),
            ads_limit=data.get('ads_limit'),
            price=data.get('price', 0),
            price_per_property=data.get('price_per_property', 50.00),
            color=data.get('color', '#0d9488'),
            is_active=data.get('is_active', True)
        )
        
        return JsonResponse({'success': True, 'plan_id': plan.id})
    except Exception as e:
        logger.error(f"Error creating plan: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@staff_required
@require_POST
def subscription_plan_update_api(request, plan_id):
    """API endpoint to update subscription plan."""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'}, status=403)
    
    try:
        from .models import SubscriptionPlan
        plan = SubscriptionPlan.objects.get(id=plan_id)
        data = json.loads(request.body)
        
        plan.name = data.get('name', plan.name)
        plan.period = data.get('period', plan.period)
        plan.ads_limit = data.get('ads_limit', plan.ads_limit)
        plan.price = data.get('price', plan.price)
        plan.price_per_property = data.get('price_per_property', plan.price_per_property)
        plan.color = data.get('color', plan.color)
        plan.is_active = data.get('is_active', plan.is_active)
        plan.save()
        
        return JsonResponse({'success': True})
    except SubscriptionPlan.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'الخطة غير موجودة'}, status=404)
    except Exception as e:
        logger.error(f"Error updating plan: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@staff_required
@require_POST
def subscription_plan_toggle_status_api(request, plan_id):
    """API endpoint to toggle subscription plan status."""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'}, status=403)
    
    try:
        from .models import SubscriptionPlan
        plan = SubscriptionPlan.objects.get(id=plan_id)
        plan.is_active = not plan.is_active
        plan.save()
        return JsonResponse({'success': True})
    except SubscriptionPlan.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'الخطة غير موجودة'}, status=404)
    except Exception as e:
        logger.error(f"Error toggling plan status: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@staff_required
@require_POST
def subscription_request_approve_api(request, request_id):
    """API endpoint to approve subscription request."""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'}, status=403)
    
    try:
        from .models import SubscriptionRequest
        sub_request = SubscriptionRequest.objects.get(id=request_id)
        sub_request.approve(request.user)
        return JsonResponse({'success': True})
    except SubscriptionRequest.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'الطلب غير موجود'}, status=404)
    except Exception as e:
        logger.error(f"Error approving request: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@staff_required
@require_POST
def subscription_request_reject_api(request, request_id):
    """API endpoint to reject subscription request."""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'}, status=403)
    
    try:
        from .models import SubscriptionRequest
        sub_request = SubscriptionRequest.objects.get(id=request_id)
        data = json.loads(request.body)
        notes = data.get('notes', '')
        sub_request.reject(request.user, notes)
        return JsonResponse({'success': True})
    except SubscriptionRequest.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'الطلب غير موجود'}, status=404)
    except Exception as e:
        logger.error(f"Error rejecting request: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def subscription_request_create_api(request):
    """API endpoint for users to create subscription requests."""
    try:
        from .models import SubscriptionRequest, Broker
        data = json.loads(request.body)
        
        # Check if user has a broker profile
        try:
            broker = request.user.broker
        except Broker.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'ليس لديك ملف دلال'}, status=400)
        
        # Create request
        sub_request = SubscriptionRequest.objects.create(
            user=request.user,
            request_type=data.get('request_type', 'upgrade'),
            current_plan=broker.subscription_plan,
            notes=data.get('notes', '')
        )
        
        return JsonResponse({'success': True, 'request_id': sub_request.id})
    except Exception as e:
        logger.error(f"Error creating subscription request: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@staff_required
def settings_theme(request):
    """Theme settings page."""
    if not can_manage_site_settings(request.user):
        messages.error(request, 'ليس لديك صلاحية تعديل إعدادات الموقع')
        return redirect('dashboard')
    settings = SiteSettings.get_solo()
    if request.method == 'POST':
        settings.theme_mode = request.POST.get('theme_mode', 'light')
        settings.primary_color = request.POST.get('primary_color', '#0d9488')
        settings.secondary_color = request.POST.get('secondary_color', '#f97316')
        settings.font_family = request.POST.get('font_family', 'Cairo')
        settings.font_size = int(request.POST.get('font_size', 16))
        settings.button_style = request.POST.get('button_style', 'rounded')
        settings.layout_style = request.POST.get('layout_style', 'boxed')
        settings.save()
        messages.success(request, 'تم تحديث إعدادات المظهر بنجاح')
        return redirect('settings_theme')
    
    return render(request, 'properties/settings_theme.html', {'settings': settings, 'section': 'theme'})


@login_required
@staff_required
def settings_homepage(request):
    """Homepage settings page."""
    if not can_manage_site_settings(request.user):
        messages.error(request, 'ليس لديك صلاحية تعديل إعدادات الموقع')
        return redirect('dashboard')
    settings = SiteSettings.get_solo()
    if request.method == 'POST':
        settings.hero_banner_title = request.POST.get('hero_banner_title', '')
        settings.hero_banner_subtitle = request.POST.get('hero_banner_subtitle', '')
        settings.show_featured_properties = request.POST.get('show_featured_properties') == 'on'
        settings.show_latest_properties = request.POST.get('show_latest_properties') == 'on'
        settings.show_brokers_section = request.POST.get('show_brokers_section') == 'on'
        settings.featured_properties_count = int(request.POST.get('featured_properties_count', 6))
        settings.latest_properties_count = int(request.POST.get('latest_properties_count', 12))
        if 'hero_banner_image' in request.FILES:
            settings.hero_banner_image = request.FILES['hero_banner_image']
        settings.save()
        messages.success(request, 'تم تحديث إعدادات الصفحة الرئيسية بنجاح')
        return redirect('settings_homepage')
    
    return render(request, 'properties/settings_homepage.html', {'settings': settings, 'section': 'homepage'})


@login_required
@staff_required
def settings_users(request):
    """User and permissions settings page."""
    if not can_manage_site_settings(request.user):
        messages.error(request, 'ليس لديك صلاحية تعديل إعدادات الموقع')
        return redirect('dashboard')
    settings = SiteSettings.get_solo()
    if request.method == 'POST':
        settings.allow_registration = request.POST.get('allow_registration') == 'on'
        settings.require_email_verification = request.POST.get('require_email_verification') == 'on'
        settings.require_phone_verification = request.POST.get('require_phone_verification') == 'on'
        settings.auto_activate_accounts = request.POST.get('auto_activate_accounts') == 'on'
        settings.default_user_role = request.POST.get('default_user_role', 'user')
        settings.save()
        messages.success(request, 'تم تحديث إعدادات المستخدمين بنجاح')
        return redirect('settings_users')
    
    return render(request, 'properties/settings_users.html', {'settings': settings, 'section': 'users'})


@login_required
@staff_required
def settings_properties(request):
    """Property settings page."""
    if not can_manage_site_settings(request.user):
        messages.error(request, 'ليس لديك صلاحية تعديل إعدادات الموقع')
        return redirect('dashboard')
    settings = SiteSettings.get_solo()
    if request.method == 'POST':
        settings.default_currency = request.POST.get('default_currency', 'IQD')
        settings.area_unit = request.POST.get('area_unit', 'm2')
        settings.max_images_per_property = int(request.POST.get('max_images_per_property', 20))
        settings.allow_video_upload = request.POST.get('allow_video_upload') == 'on'
        settings.allow_virtual_tours = request.POST.get('allow_virtual_tours') == 'on'
        settings.save()
        messages.success(request, 'تم تحديث إعدادات العقارات بنجاح')
        return redirect('settings_properties')
    
    return render(request, 'properties/settings_properties.html', {'settings': settings, 'section': 'properties'})


@login_required
@staff_required
def settings_media(request):
    """Media settings page."""
    if not can_manage_site_settings(request.user):
        messages.error(request, 'ليس لديك صلاحية تعديل إعدادات الموقع')
        return redirect('dashboard')
    settings = SiteSettings.get_solo()
    if request.method == 'POST':
        settings.max_image_size = int(request.POST.get('max_image_size', 5242880))
        settings.allowed_image_types = request.POST.get('allowed_image_types', 'jpg,jpeg,png,webp')
        settings.max_video_size = int(request.POST.get('max_video_size', 52428800))
        settings.allowed_video_types = request.POST.get('allowed_video_types', 'mp4,webm')
        settings.save()
        messages.success(request, 'تم تحديث إعدادات الوسائط بنجاح')
        return redirect('settings_media')
    
    return render(request, 'properties/settings_media.html', {'settings': settings, 'section': 'media'})


@login_required
@staff_required
def settings_notifications(request):
    """Notification settings page."""
    if not can_manage_site_settings(request.user):
        messages.error(request, 'ليس لديك صلاحية تعديل إعدادات الموقع')
        return redirect('dashboard')
    settings = SiteSettings.get_solo()
    if request.method == 'POST':
        settings.enable_site_notifications = request.POST.get('enable_site_notifications') == 'on'
        settings.enable_email_notifications = request.POST.get('enable_email_notifications') == 'on'
        settings.enable_sms_notifications = request.POST.get('enable_sms_notifications') == 'on'
        settings.enable_push_notifications = request.POST.get('enable_push_notifications') == 'on'
        settings.save()
        messages.success(request, 'تم تحديث إعدادات الإشعارات بنجاح')
        return redirect('settings_notifications')
    
    return render(request, 'properties/settings_notifications.html', {'settings': settings, 'section': 'notifications'})


@login_required
@staff_required
def settings_payments(request):
    """Payment settings page."""
    if not can_manage_site_settings(request.user):
        messages.error(request, 'ليس لديك صلاحية تعديل إعدادات الموقع')
        return redirect('dashboard')
    settings = SiteSettings.get_solo()
    if request.method == 'POST':
        settings.payment_methods = request.POST.get('payment_methods', 'cash,bank_transfer')
        settings.enable_subscriptions = request.POST.get('enable_subscriptions') == 'on'
        settings.subscription_price_monthly = Decimal(request.POST.get('subscription_price_monthly', 0))
        settings.subscription_price_yearly = Decimal(request.POST.get('subscription_price_yearly', 0))
        settings.enable_invoices = request.POST.get('enable_invoices') == 'on'
        settings.save()
        messages.success(request, 'تم تحديث إعدادات المدفوعات بنجاح')
        return redirect('settings_payments')
    
    return render(request, 'properties/settings_payments.html', {'settings': settings, 'section': 'payments'})


@login_required
@staff_required
def settings_security(request):
    """Security settings page."""
    if not can_manage_site_settings(request.user):
        messages.error(request, 'ليس لديك صلاحية تعديل إعدادات الموقع')
        return redirect('dashboard')
    settings = SiteSettings.get_solo()
    if request.method == 'POST':
        settings.enable_two_factor = request.POST.get('enable_two_factor') == 'on'
        settings.password_min_length = int(request.POST.get('password_min_length', 8))
        settings.require_special_chars = request.POST.get('require_special_chars') == 'on'
        settings.session_timeout = int(request.POST.get('session_timeout', 3600))
        settings.log_login_attempts = request.POST.get('log_login_attempts') == 'on'
        settings.save()
        messages.success(request, 'تم تحديث إعدادات الأمان بنجاح')
        return redirect('settings_security')
    
    return render(request, 'properties/settings_security.html', {'settings': settings, 'section': 'security'})


@login_required
@staff_required
def settings_reports(request):
    """Report settings page."""
    if not can_manage_site_settings(request.user):
        messages.error(request, 'ليس لديك صلاحية تعديل إعدادات الموقع')
        return redirect('dashboard')
    settings = SiteSettings.get_solo()
    if request.method == 'POST':
        settings.enable_reports = request.POST.get('enable_reports') == 'on'
        settings.auto_review_reports = request.POST.get('auto_review_reports') == 'on'
        settings.report_priority_threshold = request.POST.get('report_priority_threshold', 'high')
        settings.save()
        messages.success(request, 'تم تحديث إعدادات البلاغات بنجاح')
        return redirect('settings_reports')
    
    return render(request, 'properties/settings_reports.html', {'settings': settings, 'section': 'reports'})


@login_required
@staff_required
def settings_backup(request):
    """Backup settings page."""
    if not can_manage_site_settings(request.user):
        messages.error(request, 'ليس لديك صلاحية تعديل إعدادات الموقع')
        return redirect('dashboard')
    settings = SiteSettings.get_solo()
    if request.method == 'POST':
        settings.auto_backup_enabled = request.POST.get('auto_backup_enabled') == 'on'
        settings.backup_frequency = request.POST.get('backup_frequency', 'daily')
        settings.backup_retention_days = int(request.POST.get('backup_retention_days', 30))
        settings.save()
        messages.success(request, 'تم تحديث إعدادات النسخ الاحتياطي بنجاح')
        return redirect('settings_backup')
    
    return render(request, 'properties/settings_backup.html', {'settings': settings, 'section': 'backup'})


@login_required
@staff_required
def settings_seo(request):
    """SEO settings page."""
    if not can_manage_site_settings(request.user):
        messages.error(request, 'ليس لديك صلاحية تعديل إعدادات الموقع')
        return redirect('dashboard')
    settings = SiteSettings.get_solo()
    if request.method == 'POST':
        settings.seo_title = request.POST.get('seo_title', '')
        settings.seo_description = request.POST.get('seo_description', '')
        settings.seo_keywords = request.POST.get('seo_keywords', '')
        settings.enable_og_tags = request.POST.get('enable_og_tags') == 'on'
        settings.save()
        messages.success(request, 'تم تحديث إعدادات SEO بنجاح')
        return redirect('settings_seo')
    
    return render(request, 'properties/settings_seo.html', {'settings': settings, 'section': 'seo'})


@login_required
@staff_required
def settings_api(request):
    """API settings page."""
    if not can_manage_site_settings(request.user):
        messages.error(request, 'ليس لديك صلاحية تعديل إعدادات الموقع')
        return redirect('dashboard')
    settings = SiteSettings.get_solo()
    if request.method == 'POST':
        settings.enable_api = request.POST.get('enable_api') == 'on'
        settings.api_rate_limit = int(request.POST.get('api_rate_limit', 1000))
        settings.api_key_required = request.POST.get('api_key_required') == 'on'
        settings.save()
        messages.success(request, 'تم تحديث إعدادات API بنجاح')
        return redirect('settings_api')
    
    return render(request, 'properties/settings_api.html', {'settings': settings, 'section': 'api'})


@login_required
@staff_required
def settings_system(request):
    """System info page."""
    if not can_manage_site_settings(request.user):
        messages.error(request, 'ليس لديك صلاحية تعديل إعدادات الموقع')
        return redirect('dashboard')
    settings = SiteSettings.get_solo()
    if request.method == 'POST':
        settings.system_version = request.POST.get('system_version', '1.0.0')
        settings.license_key = request.POST.get('license_key', '')
        settings.save()
        messages.success(request, 'تم تحديث معلومات النظام بنجاح')
        return redirect('settings_system')
    
    return render(request, 'properties/settings_system.html', {'settings': settings, 'section': 'system'})


def explore_view(request):
    """TikTok-style property browsing page."""
    # Get filters from query parameters
    content_type = request.GET.get('type', 'all')  # all, video, photo
    property_type = request.GET.get('property_type', 'all')  # all, villa, apartment, land, office
    listing_type = request.GET.get('listing_type', 'all')  # all, sale, rent
    user_only = request.GET.get('user_only', 'false') == 'true'  # show user's properties only
    
    # Get properties with videos or images
    properties = get_public_properties()
    
    # Filter by user if requested
    if user_only and request.user.is_authenticated:
        properties = [p for p in properties if p.owner == request.user or (p.broker and p.broker.user == request.user)]
    
    # Apply filters (handle list input)
    if content_type == 'video':
        properties = [p for p in properties if p.videos.exists()]
    elif content_type == 'photo':
        properties = [p for p in properties if p.gallery_images.exists()]
    
    if property_type != 'all':
        properties = [p for p in properties if p.type == property_type]
    
    if listing_type == 'sale':
        properties = [p for p in properties if p.status == 'ready']
    elif listing_type == 'rent':
        properties = [p for p in properties if p.status == 'rent']
    
    # Order by views or random for variety
    properties = sorted(properties, key=lambda x: x.created_at, reverse=True)[:50]
    
    # Get user's likes and saves if authenticated
    user_likes = set()
    user_saves = set()
    if request.user.is_authenticated:
        user_likes = set(PropertyLike.objects.filter(user=request.user).values_list('property_id', flat=True))
        user_saves = set(PropertySave.objects.filter(user=request.user).values_list('property_id', flat=True))
    
    return render(request, 'properties/explore.html', {
        'properties': properties,
        'content_type': content_type,
        'property_type': property_type,
        'listing_type': listing_type,
        'user_likes': user_likes,
        'user_saves': user_saves,
        'user_only': user_only,
    })


def properties_outside_iraq_view(request):
    """View for properties, resorts, and hotels outside Iraq with advanced filters."""
    from properties.models import Resort, Hotel, Country, City, Area
    from properties.constants import OUTSIDE_IRAQ_PROPERTY_TYPES
    
    # Get filters from query parameters
    category = request.GET.get('category', 'all')  # all, properties, resorts, hotels
    content_type = request.GET.get('type', 'all')
    property_type = request.GET.get('property_type', 'all')
    listing_type = request.GET.get('listing_type', 'all')
    user_only = request.GET.get('user_only', 'false') == 'true'
    
    # Advanced filters
    country_id = request.GET.get('country', '')
    city_id = request.GET.get('city', '')
    area_id = request.GET.get('area', '')
    price_min = request.GET.get('price_min', '')
    price_max = request.GET.get('price_max', '')
    currency = request.GET.get('currency', '')
    area_min = request.GET.get('area_min', '')
    area_max = request.GET.get('area_max', '')
    bedrooms = request.GET.get('bedrooms', '')
    bathrooms = request.GET.get('bathrooms', '')
    year_built = request.GET.get('year_built', '')
    broker_name = request.GET.get('broker_name', '')
    featured_only = request.GET.get('featured_only', 'false') == 'true'
    min_rating = request.GET.get('min_rating', '')
    
    properties_list = []
    resorts_list = []
    hotels_list = []
    
    # Get all countries for the filter dropdown
    countries = Country.objects.filter(is_active=True).order_by('order', 'name_ar')
    cities = []
    areas = []
    
    if country_id:
        cities = City.objects.filter(country_id=country_id, is_active=True).order_by('name_ar')
    if city_id:
        areas = Area.objects.filter(city_id=city_id, is_active=True).order_by('name_ar')
    
    # Get properties outside Iraq
    if category in ['all', 'properties']:
        properties = get_public_properties()
        properties = [p for p in properties if p.country and p.country.code != 'IQ']
        
        # Filter by country
        if country_id:
            properties = [p for p in properties if p.country_id == int(country_id)]
        
        # Filter by city
        if city_id:
            properties = [p for p in properties if p.city_id == int(city_id)]
        
        # Filter by area
        if area_id:
            properties = [p for p in properties if p.area_outside_id == int(area_id)]
        
        # Filter by currency
        if currency:
            properties = [p for p in properties if p.currency == currency]
        
        # Filter by price range
        if price_min:
            properties = [p for p in properties if p.price >= int(price_min)]
        if price_max:
            properties = [p for p in properties if p.price <= int(price_max)]
        
        # Filter by area range
        if area_min:
            properties = [p for p in properties if p.area >= int(area_min)]
        if area_max:
            properties = [p for p in properties if p.area <= int(area_max)]
        
        # Filter by bedrooms
        if bedrooms:
            properties = [p for p in properties if p.bedrooms == int(bedrooms)]
        
        # Filter by bathrooms
        if bathrooms:
            properties = [p for p in properties if p.bathrooms == int(bathrooms)]
        
        # Filter by year built
        if year_built:
            properties = [p for p in properties if p.year_built == int(year_built)]
        
        # Filter by broker name
        if broker_name:
            properties = [p for p in properties if p.broker and broker_name.lower() in p.broker.display_name.lower()]
        
        # Filter by featured only
        if featured_only:
            properties = [p for p in properties if p.is_featured]
        
        # Filter by minimum rating
        if min_rating:
            properties = [p for p in properties if hasattr(p, 'average_rating') and p.average_rating >= float(min_rating)]
        
        # Filter by user if requested
        if user_only and request.user.is_authenticated:
            properties = [p for p in properties if p.owner == request.user or (p.broker and p.broker.user == request.user)]
        
        # Apply content type filters
        if content_type == 'video':
            properties = [p for p in properties if p.videos.exists()]
        elif content_type == 'photo':
            properties = [p for p in properties if p.gallery_images.exists()]
        
        # Apply property type filter
        if property_type != 'all':
            properties = [p for p in properties if p.type == property_type]
        
        # Apply listing type filter
        if listing_type == 'sale':
            properties = [p for p in properties if p.status == 'ready']
        elif listing_type == 'rent':
            properties = [p for p in properties if p.status == 'rent']
        
        # Order by creation date
        properties_list = sorted(properties, key=lambda x: x.created_at, reverse=True)[:50]
    
    # Get resorts outside Iraq
    if category in ['all', 'resorts']:
        resorts = Resort.objects.filter(is_active=True)
        resorts = [r for r in resorts if r.country and r.country.code != 'IQ']
        
        # Filter by country
        if country_id:
            resorts = [r for r in resorts if r.country_id == int(country_id)]
        
        # Filter by city
        if city_id:
            resorts = [r for r in resorts if r.city_id == int(city_id)]
        
        if user_only and request.user.is_authenticated:
            resorts = [r for r in resorts if r.owner == request.user]
        
        resorts_list = sorted(resorts, key=lambda x: x.created_at, reverse=True)[:50]
    
    # Get hotels outside Iraq
    if category in ['all', 'hotels']:
        hotels = Hotel.objects.filter(is_active=True)
        hotels = [h for h in hotels if h.country and h.country.code != 'IQ']
        
        # Filter by country
        if country_id:
            hotels = [h for h in hotels if h.country_id == int(country_id)]
        
        # Filter by city
        if city_id:
            hotels = [h for h in hotels if h.city_id == int(city_id)]
        
        if user_only and request.user.is_authenticated:
            hotels = [h for h in hotels if h.owner == request.user]
        
        hotels_list = sorted(hotels, key=lambda x: x.created_at, reverse=True)[:50]
    
    # Get user's likes and saves if authenticated
    user_likes = set()
    user_saves = set()
    if request.user.is_authenticated:
        user_likes = set(PropertyLike.objects.filter(user=request.user).values_list('property_id', flat=True))
        user_saves = set(PropertySave.objects.filter(user=request.user).values_list('property_id', flat=True))
    
    return render(request, 'properties/explore.html', {
        'properties': properties_list,
        'resorts': resorts_list,
        'hotels': hotels_list,
        'content_type': content_type,
        'property_type': property_type,
        'listing_type': listing_type,
        'category': category,
        'user_likes': user_likes,
        'user_saves': user_saves,
        'user_only': user_only,
        'page_title': 'تصفح',
        'countries': countries,
        'cities': cities,
        'areas': areas,
        'selected_country': country_id,
        'selected_city': city_id,
        'selected_area': area_id,
        'price_min': price_min,
        'price_max': price_max,
        'currency': currency,
        'area_min': area_min,
        'area_max': area_max,
        'bedrooms': bedrooms,
        'bathrooms': bathrooms,
        'year_built': year_built,
        'broker_name': broker_name,
        'featured_only': featured_only,
        'min_rating': min_rating,
        'OUTSIDE_IRAQ_PROPERTY_TYPES': OUTSIDE_IRAQ_PROPERTY_TYPES,
        'is_outside_iraq': True,
    })


def unified_search_view(request):
    """Unified search view for properties, hotels, and resorts."""
    form = PropertySearchForm(request.GET)
    category = request.GET.get('category', '')
    q = request.GET.get('q', '')
    
    # Initialize result containers
    properties = []
    hotels = []
    resorts = []
    
    # Search in Properties (Iraq and outside Iraq)
    if category in ['', 'property_iraq', 'property_outside']:
        property_queryset = get_public_properties()
        
        # Filter by category (Iraq vs outside Iraq)
        if category == 'property_iraq':
            property_queryset = [p for p in property_queryset if p.country == 'Iraq' or not hasattr(p, 'country')]
        elif category == 'property_outside':
            property_queryset = [p for p in property_queryset if hasattr(p, 'country') and p.country != 'Iraq']
        
        # Apply text search
        if q:
            property_queryset = [
                p for p in property_queryset
                if q.lower() in p.title.lower() or 
                   q.lower() in p.district.lower() or 
                   q.lower() in p.location.lower() or
                   (p.broker and q.lower() in p.broker.display_name.lower())
            ]
        
        # Apply filters
        governorate = request.GET.get('governorate')
        if governorate:
            property_queryset = [p for p in property_queryset if p.district and governorate in p.district]
        
        district = request.GET.get('district')
        if district:
            property_queryset = [p for p in property_queryset if district.lower() in p.district.lower()]
        
        city = request.GET.get('city')
        if city:
            property_queryset = [p for p in property_queryset if city.lower() in p.location.lower()]
        
        country = request.GET.get('country')
        if country:
            property_queryset = [p for p in property_queryset if hasattr(p, 'country') and country.lower() in p.country.lower()]
        
        property_type = request.GET.get('type')
        if property_type:
            property_queryset = [p for p in property_queryset if p.type == property_type]
        
        status = request.GET.get('status')
        if status:
            property_queryset = [p for p in property_queryset if p.status == status]
        
        price_min = request.GET.get('price_min')
        if price_min:
            property_queryset = [p for p in property_queryset if p.price >= int(price_min)]
        
        price_max = request.GET.get('price_max')
        if price_max:
            property_queryset = [p for p in property_queryset if p.price <= int(price_max)]
        
        area_min = request.GET.get('area_min')
        if area_min:
            property_queryset = [p for p in property_queryset if p.area >= int(area_min)]
        
        area_max = request.GET.get('area_max')
        if area_max:
            property_queryset = [p for p in property_queryset if p.area <= int(area_max)]
        
        bedrooms = request.GET.get('bedrooms')
        if bedrooms:
            property_queryset = [p for p in property_queryset if p.bedrooms == int(bedrooms)]
        
        bathrooms = request.GET.get('bathrooms')
        if bathrooms:
            property_queryset = [p for p in property_queryset if p.bathrooms == int(bathrooms)]
        
        floors = request.GET.get('floors')
        if floors:
            property_queryset = [p for p in property_queryset if p.floors == int(floors)]
        
        year_built = request.GET.get('year_built')
        if year_built:
            property_queryset = [p for p in property_queryset if p.year_built == int(year_built)]
        
        featured_only = request.GET.get('featured_only')
        if featured_only:
            property_queryset = [p for p in property_queryset if p.is_featured]
        
        verified_only = request.GET.get('verified_only')
        if verified_only:
            property_queryset = [p for p in property_queryset if p.broker and p.broker.is_verified]
        
        new_only = request.GET.get('new_only')
        if new_only:
            from datetime import timedelta
            from django.utils import timezone
            week_ago = timezone.now() - timedelta(days=7)
            property_queryset = [p for p in property_queryset if p.created_at >= week_ago]
        
        broker_name = request.GET.get('broker_name')
        if broker_name:
            property_queryset = [p for p in property_queryset if p.broker and broker_name.lower() in p.broker.display_name.lower()]
        
        rating_min = request.GET.get('rating_min')
        if rating_min:
            property_queryset = [p for p in property_queryset if hasattr(p, 'average_rating') and p.average_rating >= int(rating_min)]
        
        # Apply sorting
        sort = request.GET.get('sort')
        if sort == 'newest':
            property_queryset = sorted(property_queryset, key=lambda x: x.created_at, reverse=True)
        elif sort == 'oldest':
            property_queryset = sorted(property_queryset, key=lambda x: x.created_at)
        elif sort == 'price_asc':
            property_queryset = sorted(property_queryset, key=lambda x: x.price)
        elif sort == 'price_desc':
            property_queryset = sorted(property_queryset, key=lambda x: x.price, reverse=True)
        elif sort == 'views':
            property_queryset = sorted(property_queryset, key=lambda x: x.views_count, reverse=True)
        elif sort == 'rating':
            property_queryset = sorted(property_queryset, key=lambda x: getattr(x, 'average_rating', 0), reverse=True)
        
        properties = property_queryset
    
    # Search in Hotels
    if category in ['', 'hotel']:
        hotel_queryset = Hotel.objects.filter(is_active=True)
        
        if q:
            hotel_queryset = hotel_queryset.filter(
                Q(name__icontains=q) |
                Q(description__icontains=q) |
                Q(city__icontains=q)
            )
        
        city = request.GET.get('city')
        if city:
            hotel_queryset = hotel_queryset.filter(city__icontains=city)
        
        price_range = request.GET.get('price_range')
        if price_range:
            hotel_queryset = hotel_queryset.filter(price_range=price_range)
        
        star_rating = request.GET.get('star_rating')
        if star_rating:
            hotel_queryset = hotel_queryset.filter(star_rating=int(star_rating))
        
        featured_only = request.GET.get('featured_only')
        if featured_only:
            hotel_queryset = hotel_queryset.filter(is_featured=True)
        
        hotels = list(hotel_queryset)
    
    # Search in Resorts
    if category in ['', 'resort']:
        resort_queryset = Resort.objects.filter(is_active=True)
        
        if q:
            resort_queryset = resort_queryset.filter(
                Q(name__icontains=q) |
                Q(description__icontains=q) |
                Q(city__icontains=q)
            )
        
        governorate = request.GET.get('governorate')
        if governorate:
            resort_queryset = resort_queryset.filter(governorate=governate)
        
        city = request.GET.get('city')
        if city:
            resort_queryset = resort_queryset.filter(city__icontains=city)
        
        resort_type = request.GET.get('resort_type')
        if resort_type:
            resort_queryset = resort_queryset.filter(resort_type=resort_type)
        
        featured_only = request.GET.get('featured_only')
        if featured_only:
            resort_queryset = resort_queryset.filter(is_featured=True)
        
        resorts = list(resort_queryset)
    
    # Combine all results for pagination
    all_results = []
    for p in properties:
        all_results.append({
            'type': 'property',
            'object': p,
            'title': p.display_title,
            'price': p.price,
            'location': p.district,
            'image': p.get_main_image if hasattr(p, 'get_main_image') else None,
            'created_at': p.created_at,
        })
    
    for h in hotels:
        all_results.append({
            'type': 'hotel',
            'object': h,
            'title': h.name,
            'price': 0,  # Hotels use price_range instead
            'location': h.city,
            'image': h.image.url if h.image else None,
            'created_at': h.created_at if hasattr(h, 'created_at') else None,
        })
    
    for r in resorts:
        all_results.append({
            'type': 'resort',
            'object': r,
            'title': r.name,
            'price': 0,  # Resorts use price_range instead
            'location': r.city,
            'image': r.image.url if r.image else None,
            'created_at': r.created_at,
        })
    
    # Sort combined results
    sort = request.GET.get('sort')
    if sort == 'newest':
        all_results = sorted(all_results, key=lambda x: x['created_at'] or timezone.now(), reverse=True)
    elif sort == 'oldest':
        all_results = sorted(all_results, key=lambda x: x['created_at'] or timezone.now())
    
    # Pagination
    paginator = Paginator(all_results, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get user's likes and saves
    user_likes = set()
    user_saves = set()
    if request.user.is_authenticated:
        user_likes = set(PropertyLike.objects.filter(user=request.user).values_list('property_id', flat=True))
        user_saves = set(PropertySave.objects.filter(user=request.user).values_list('property_id', flat=True))
    
    return render(request, 'properties/unified_search.html', {
        'form': form,
        'results': page_obj,
        'page_obj': page_obj,
        'properties': properties,
        'hotels': hotels,
        'resorts': resorts,
        'category': category,
        'q': q,
        'user_likes': user_likes,
        'user_saves': user_saves,
    })


def channel_brokers_view(request):
    """Channel page for broker properties with district filter."""
    from .models import Broker
    
    district = request.GET.get('district', '')
    property_type = request.GET.get('property_type', 'all')
    listing_type = request.GET.get('listing_type', 'all')
    
    # Get all brokers
    brokers = Broker.objects.filter(is_active=True, is_verified=True)
    
    # Get broker properties
    properties = Property.objects.filter(
        broker__isnull=False,
        broker__is_active=True,
        status__in=['ready', 'rent']
    ).select_related('owner', 'broker', 'broker__user').prefetch_related('gallery_images')
    
    # Filter by district
    if district:
        properties = properties.filter(district__icontains=district)
    
    # Filter by property type
    if property_type != 'all':
        properties = properties.filter(type=property_type)
    
    # Filter by listing type
    if listing_type == 'sale':
        properties = properties.filter(status='ready')
    elif listing_type == 'rent':
        properties = properties.filter(status='rent')
    
    # Order by created date
    properties = properties.order_by('-created_at')[:50]
    
    # Get all districts for filter
    districts = Property.objects.values_list('district', flat=True).distinct()
    
    # Get user's likes and saves if authenticated
    user_likes = set()
    user_saves = set()
    if request.user.is_authenticated:
        user_likes = set(PropertyLike.objects.filter(user=request.user).values_list('property_id', flat=True))
        user_saves = set(PropertySave.objects.filter(user=request.user).values_list('property_id', flat=True))
    
    return render(request, 'properties/channel_brokers.html', {
        'properties': properties,
        'district': district,
        'property_type': property_type,
        'listing_type': listing_type,
        'districts': districts,
        'user_likes': user_likes,
        'user_saves': user_saves,
        'channel_name': 'الدلالين',
        'channel_icon': '🧑‍💼',
    })


def channel_users_view(request):
    """Channel page for user properties with district filter."""
    district = request.GET.get('district', '')
    property_type = request.GET.get('property_type', 'all')
    listing_type = request.GET.get('listing_type', 'all')
    
    # Get user properties (properties without broker)
    properties = Property.objects.filter(
        broker__isnull=True,
        status__in=['ready', 'rent']
    ).select_related('owner').prefetch_related('gallery_images')
    
    # Filter by district
    if district:
        properties = properties.filter(district__icontains=district)
    
    # Filter by property type
    if property_type != 'all':
        properties = properties.filter(type=property_type)
    
    # Filter by listing type
    if listing_type == 'sale':
        properties = properties.filter(status='ready')
    elif listing_type == 'rent':
        properties = properties.filter(status='rent')
    
    # Order by created date
    properties = properties.order_by('-created_at')[:50]
    
    # Get all districts for filter
    districts = Property.objects.values_list('district', flat=True).distinct()
    
    # Get user's likes and saves if authenticated
    user_likes = set()
    user_saves = set()
    if request.user.is_authenticated:
        user_likes = set(PropertyLike.objects.filter(user=request.user).values_list('property_id', flat=True))
        user_saves = set(PropertySave.objects.filter(user=request.user).values_list('property_id', flat=True))
    
    return render(request, 'properties/channel_users.html', {
        'properties': properties,
        'district': district,
        'property_type': property_type,
        'listing_type': listing_type,
        'districts': districts,
        'user_likes': user_likes,
        'user_saves': user_saves,
        'channel_name': 'المستخدمين',
        'channel_icon': '👤',
    })


def channel_admin_view(request):
    """Channel page for all properties (admin view) with district filter."""
    if not request.user.is_superuser:
        messages.error(request, 'ليس لديك صلاحية الوصول لهذه الصفحة')
        return redirect('home')
    
    district = request.GET.get('district', '')
    property_type = request.GET.get('property_type', 'all')
    listing_type = request.GET.get('listing_type', 'all')
    
    # Get all properties
    properties = Property.objects.select_related('owner', 'broker', 'broker__user').prefetch_related('gallery_images')
    
    # Filter by district
    if district:
        properties = properties.filter(district__icontains=district)
    
    # Filter by property type
    if property_type != 'all':
        properties = properties.filter(type=property_type)
    
    # Filter by listing type
    if listing_type == 'sale':
        properties = properties.filter(status='ready')
    elif listing_type == 'rent':
        properties = properties.filter(status='rent')
    
    # Order by created date
    properties = properties.order_by('-created_at')[:50]
    
    # Get all districts for filter
    districts = Property.objects.values_list('district', flat=True).distinct()
    
    # Get user's likes and saves if authenticated
    user_likes = set()
    user_saves = set()
    if request.user.is_authenticated:
        user_likes = set(PropertyLike.objects.filter(user=request.user).values_list('property_id', flat=True))
        user_saves = set(PropertySave.objects.filter(user=request.user).values_list('property_id', flat=True))
    
    return render(request, 'properties/channel_admin.html', {
        'properties': properties,
        'district': district,
        'property_type': property_type,
        'listing_type': listing_type,
        'districts': districts,
        'user_likes': user_likes,
        'user_saves': user_saves,
        'channel_name': 'مدير المنصة',
        'channel_icon': '👑',
    })


def channels_view(request):
    """Main channels page listing all available channels."""
    from .models import Broker, BrokerChannel
    
    # Get channel statistics
    broker_properties_count = Property.objects.filter(
        broker__isnull=False,
        broker__is_active=True,
        status__in=['ready', 'rent']
    ).count()
    
    user_properties_count = Property.objects.filter(
        broker__isnull=True,
        status__in=['ready', 'rent']
    ).count()
    
    all_properties_count = Property.objects.count()
    
    brokers_count = Broker.objects.filter(is_active=True, is_verified=True).count()
    
    channels = [
        {
            'name': 'الدلالين',
            'icon': '🧑‍💼',
            'description': 'تصفح جميع العقارات المعروضة من قبل الدلالين المعتمدين',
            'url': 'channel_brokers',
            'color': 'linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%)',
            'properties_count': broker_properties_count,
            'members_count': brokers_count,
        },
    ]
    
    # Add individual broker channels
    try:
        broker_channels = BrokerChannel.objects.filter(
            status='active',
            is_verified=True
        ).select_related('broker', 'broker__user').prefetch_related('broker__user__owned_properties')
        
        for channel in broker_channels:
            channels.append({
                'name': channel.name,
                'icon': '📺',
                'description': channel.description or f'قناة {channel.broker.display_name}',
                'url': 'broker_channel_detail',
                'url_args': [channel.id],
                'color': 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
                'properties_count': channel.properties_count,
                'members_count': channel.followers_count,
                'is_broker_channel': True,
                'channel_id': channel.id,
                'logo': channel.logo.url if channel.logo else None,
                'cover': channel.cover_image.url if channel.cover_image else None,
            })
    except Exception as e:
        logger.error(f"Error loading broker channels: {e}")
    
    # Add admin channel only for superusers
    if request.user.is_superuser:
        channels.append({
            'name': 'مدير المنصة',
            'icon': '👑',
            'description': 'تصفح جميع العقارات في المنصة (عرض المدير)',
            'url': 'channel_admin',
            'color': 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
            'properties_count': all_properties_count,
            'members_count': 1,
        })
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        channels = [c for c in channels if search_query.lower() in c['name'].lower()]
    
    return render(request, 'properties/channels.html', {
        'channels': channels,
        'search_query': search_query,
    })


def broker_channel_detail(request, channel_id):
    """Individual broker channel page showing all properties from that broker."""
    from .models import BrokerChannel
    
    channel = get_object_or_404(BrokerChannel, id=channel_id)
    
    # Increment views
    channel.increment_views()
    
    district = request.GET.get('district', '')
    property_type = request.GET.get('property_type', 'all')
    listing_type = request.GET.get('listing_type', 'all')
    
    # Get broker properties
    properties = Property.objects.filter(
        broker=channel.broker,
        status__in=['ready', 'rent']
    ).select_related('owner', 'broker', 'broker__user').prefetch_related('gallery_images')
    
    # Filter by district
    if district:
        properties = properties.filter(district__icontains=district)
    
    # Filter by property type
    if property_type != 'all':
        properties = properties.filter(type=property_type)
    
    # Filter by listing type
    if listing_type == 'sale':
        properties = properties.filter(status='ready')
    elif listing_type == 'rent':
        properties = properties.filter(status='rent')
    
    # Order by created date
    properties = properties.order_by('-created_at')[:50]
    
    # Get all districts for filter
    districts = Property.objects.filter(broker=channel.broker).values_list('district', flat=True).distinct()
    
    # Get user's likes and saves if authenticated
    user_likes = set()
    user_saves = set()
    is_following = False
    if request.user.is_authenticated:
        user_likes = set(PropertyLike.objects.filter(user=request.user).values_list('property_id', flat=True))
        user_saves = set(PropertySave.objects.filter(user=request.user).values_list('property_id', flat=True))
        # Check if user is following this channel (you can implement a follow model later)
    
    return render(request, 'properties/broker_channel_detail.html', {
        'channel': channel,
        'properties': properties,
        'district': district,
        'property_type': property_type,
        'listing_type': listing_type,
        'districts': districts,
        'user_likes': user_likes,
        'user_saves': user_saves,
        'is_following': is_following,
    })


@login_required
def like_property(request, property_id):
    """Like or unlike a property."""
    property = get_object_or_404(Property, id=property_id)
    like, created = PropertyLike.objects.get_or_create(
        property=property,
        user=request.user
    )
    
    if not created:
        like.delete()
        return JsonResponse({'liked': False, 'count': property.likes.count()})
    
    return JsonResponse({'liked': True, 'count': property.likes.count()})


@login_required
def save_property(request, property_id):
    """Save or unsave a property."""
    property = get_object_or_404(Property, id=property_id)
    save, created = PropertySave.objects.get_or_create(
        property=property,
        user=request.user
    )
    
    if not created:
        save.delete()
        return JsonResponse({'saved': False})
    
    return JsonResponse({'saved': True})


@login_required
def add_comment(request, property_id):
    """Add a comment to a property."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    property = get_object_or_404(Property, id=property_id)
    content = request.POST.get('content', '').strip()
    
    if not content:
        return JsonResponse({'error': 'Comment cannot be empty'}, status=400)
    
    comment = PropertyComment.objects.create(
        property=property,
        user=request.user,
        content=content
    )
    
    return JsonResponse({
        'success': True,
        'comment': {
            'id': comment.id,
            'content': comment.content,
            'user': comment.user.username,
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M')
        }
    })


@login_required
def favorites_view(request):
    """Display user's favorite/saved properties."""
    saved_properties = PropertySave.objects.filter(user=request.user).select_related('property').order_by('-created_at')
    properties = [save.property for save in saved_properties]
    
    return render(request, 'properties/favorites.html', {
        'properties': properties,
        'saved_properties': saved_properties,
    })


@login_required
def add_virtual_tour(request, property_id):
    """Add a virtual tour to a property."""
    property = get_object_or_404(Property, id=property_id)
    
    if not can_edit_property(request.user, property):
        messages.error(request, 'ليس لديك صلاحية إضافة جولة لهذا العقار')
        return redirect('property_detail', property.slug)
    
    if request.method == 'POST':
        form = VirtualTour360Form(request.POST, request.FILES)
        if form.is_valid():
            tour = form.save(commit=False)
            tour.property = property
            tour.save()
            messages.success(request, 'تم إضافة الجولة الافتراضية بنجاح')
            return redirect('property_detail', property.slug)
    else:
        form = VirtualTour360Form()
    
    return render(request, 'properties/add_virtual_tour.html', {
        'form': form,
        'property': property,
    })


@login_required
def edit_virtual_tour(request, tour_id):
    """Edit a virtual tour."""
    tour = get_object_or_404(VirtualTour360, id=tour_id)
    
    if not can_edit_property(request.user, tour.property):
        messages.error(request, 'ليس لديك صلاحية تعديل هذه الجولة')
        return redirect('property_detail', tour.property.slug)
    
    if request.method == 'POST':
        form = VirtualTour360Form(request.POST, request.FILES, instance=tour)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث الجولة الافتراضية بنجاح')
            return redirect('property_detail', tour.property.slug)
    else:
        form = VirtualTour360Form(instance=tour)
    
    return render(request, 'properties/edit_virtual_tour.html', {
        'form': form,
        'tour': tour,
        'property': tour.property,
    })


@login_required
def delete_virtual_tour(request, tour_id):
    """Delete a virtual tour."""
    tour = get_object_or_404(VirtualTour360, id=tour_id)
    property_slug = tour.property.slug
    
    if not can_edit_property(request.user, tour.property):
        messages.error(request, 'ليس لديك صلاحية حذف هذه الجولة')
        return redirect('property_detail', property_slug)
    
    tour.delete()
    messages.success(request, 'تم حذف الجولة الافتراضية بنجاح')
    return redirect('property_detail', property_slug)


@login_required
def add_tour_point(request, tour_id):
    """Add a point to a virtual tour."""
    tour = get_object_or_404(VirtualTour360, id=tour_id)
    
    if not can_edit_property(request.user, tour.property):
        messages.error(request, 'ليس لديك صلاحية إضافة نقطة لهذه الجولة')
        return redirect('property_detail', tour.property.slug)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        image = request.FILES.get('image')
        
        if name:
            point = VirtualTourPoint.objects.create(
                virtual_tour=tour,
                name=name,
                description=description,
                image=image
            )
            messages.success(request, 'تم إضافة النقطة بنجاح')
            return redirect('property_detail', tour.property.slug)
    
    return render(request, 'properties/add_tour_point.html', {
        'tour': tour,
        'property': tour.property,
    })


@login_required
def edit_tour_point(request, point_id):
    """Edit a tour point."""
    point = get_object_or_404(VirtualTourPoint, id=point_id)
    
    if not can_edit_property(request.user, point.virtual_tour.property):
        messages.error(request, 'ليس لديك صلاحية تعديل هذه النقطة')
        return redirect('property_detail', point.virtual_tour.property.slug)
    
    if request.method == 'POST':
        point.name = request.POST.get('name', point.name)
        point.description = request.POST.get('description', point.description)
        image = request.FILES.get('image')
        if image:
            point.image = image
        point.save()
        messages.success(request, 'تم تحديث النقطة بنجاح')
        return redirect('property_detail', point.virtual_tour.property.slug)
    
    return render(request, 'properties/edit_tour_point.html', {
        'point': point,
        'tour': point.virtual_tour,
        'property': point.virtual_tour.property,
    })


@login_required
def delete_tour_point(request, point_id):
    """Delete a tour point."""
    point = get_object_or_404(VirtualTourPoint, id=point_id)
    property_slug = point.virtual_tour.property.slug
    
    if not can_edit_property(request.user, point.virtual_tour.property):
        messages.error(request, 'ليس لديك صلاحية حذف هذه النقطة')
        return redirect('property_detail', property_slug)
    
    point.delete()
    messages.success(request, 'تم حذف النقطة بنجاح')
    return redirect('property_detail', property_slug)


@login_required
@staff_required
@require_POST
def add_property(request):
    # Check if adding or replacing
    replace_property_id = request.POST.get('replace_property_id')
    if replace_property_id:
        # Replacement mode - delete old property first
        try:
            old_prop = Property.objects.get(id=replace_property_id, owner=request.user)
            old_prop.delete()
            messages.info(request, 'تم استبدال العقار القديم')
        except Property.DoesNotExist:
            messages.error(request, 'العقار المطلوب استبداله غير موجود')
            return redirect('dashboard')
    
    # Check subscription status before adding property
    broker = get_broker(request.user)
    if broker:
        broker.check_subscription_status()
        if not broker.can_publish_property():
            if broker.is_suspended:
                messages.error(request, 'تم تعطيل حسابك مؤقتاً بسبب انتهاء الاشتراك. يرجى تجديد الاشتراك للاستمرار.')
            elif not broker.is_subscription_active():
                messages.error(request, 'انتهى اشتراكك. يرجى تجديد الاشتراك لنشر العقارات.')
            elif not broker.can_add_properties:
                messages.error(request, 'ليس لديك صلاحية إضافة عقارات.')
            else:
                remaining = broker.get_remaining_properties()
                published = broker.get_published_properties_count()
                limit = broker.get_property_limit()
                messages.error(
                    request, 
                    f'وصلت للحد الأقصى من العقارات ({published}/{limit}). '
                    f'يمكنك حذف بعض العقارات القديمة أو طلب تطوير خطة الاشتراك لنشر المزيد.'
                )
            return redirect('dashboard')
    elif not can_add_property(request.user):
        messages.error(
            request, 
            'وصلت للحد الأقصى من العقارات حسب باقة اشتراكك. '
            'يمكنك حذف بعض العقارات القديمة أو طلب تطوير خطة الاشتراك.'
        )
        return redirect('dashboard')
    
    form = PropertyForm(request.POST, request.FILES)
    if form.is_valid():
        prop = form.save(commit=False)
        prop.owner = request.user
        broker = get_broker(request.user)
        if broker:
            prop.broker = broker
            if broker.office_id:
                prop.office = broker.office
        prop.save()
        
        # Handle 360° image checkboxes
        is_360_list = request.POST.getlist('is_360')
        is_360_list = [val == 'on' for val in is_360_list]
        
        save_gallery_images(prop, request.FILES.getlist('gallery_images'), is_360_list)
        save_gallery_videos(prop, request.FILES.getlist('gallery_videos'))
        
        # Log activity
        ActivityLog.log(
            user=request.user,
            action='create',
            model_type='property',
            object_id=prop.id,
            object_repr=prop.title,
            description=f'إضافة عقار جديد: {prop.title}',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            metadata={'property_type': prop.property_type, 'price': str(prop.price)}
        )
        
        # Track broker statistics
        if broker:
            from .models import BrokerIndividualStats
            BrokerIndividualStats.track_property_added(broker)
        
        # Create notification
        Notification.create(
            user=request.user,
            notification_type='success',
            title='إضافة عقار',
            message=f'تم إضافة العقار: {prop.title}',
            link=f'/property/{prop.slug}/',
            metadata={'property_id': prop.id, 'property_title': prop.title}
        )
        
        # Handle virtual tour if provided
        tour_type = request.POST.get('tour_type')
        if tour_type:
            tour_title = request.POST.get('tour_title', 'جولة افتراضية')
            tour_description = request.POST.get('tour_description', '')
            
            virtual_tour = VirtualTour360.objects.create(
                property=prop,
                title=tour_title,
                tour_type=tour_type,
                description=tour_description
            )
            
            if tour_type == 'image' or tour_type == 'multi':
                tour_image = request.FILES.get('tour_image')
                if tour_image:
                    virtual_tour.image = tour_image
            elif tour_type == 'file':
                tour_file = request.FILES.get('tour_file')
                if tour_file:
                    virtual_tour.tour_file = tour_file
            elif tour_type == 'external':
                external_url = request.POST.get('external_url')
                external_service = request.POST.get('external_service')
                if external_url:
                    virtual_tour.external_url = external_url
                    virtual_tour.external_service = external_service
            
            virtual_tour.save()
        
        # Send notifications to all users about new property
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            users = User.objects.filter(is_active=True)
            for user in users:
                Notification.objects.create(
                    user=user,
                    notification_type='new_property',
                    title=f'عقار جديد: {prop.display_title}',
                    message=f'تم إضافة عقار جديد في {prop.district} بسعر {prop.price_formatted}',
                    property=prop
                )
        except Exception as e:
            logger.error(f'Error sending notifications: {str(e)}')
        
        messages.success(request, f'تم نشر العقار: {prop.display_title}')
        return redirect('dashboard')
    messages.error(request, 'يرجى تصحيح الأخطاء في النموذج')
    for field, errs in form.errors.items():
        for e in errs:
            messages.error(request, f'{field}: {e}')
    return redirect('dashboard')


@login_required
@staff_required
def edit_property(request, property_id):
    prop = get_object_or_404(Property, pk=property_id)
    if not can_edit_property(request.user, prop):
        messages.error(request, 'ليس لديك صلاحية تعديل هذا العقار')
        return redirect('dashboard')
    
    # Get virtual tours
    try:
        virtual_tours = prop.virtual_tours.all()
    except Exception:
        virtual_tours = []
    
    # Get auctions
    try:
        auctions = prop.auctions.all()
    except Exception:
        auctions = []
    
    if request.method == 'POST':
        form = PropertyForm(request.POST, request.FILES, instance=prop)
        if form.is_valid():
            form.save()
            
            # Handle 360° image checkboxes
            is_360_list = request.POST.getlist('is_360')
            is_360_list = [val == 'on' for val in is_360_list]
            
            save_gallery_images(prop, request.FILES.getlist('gallery_images'), is_360_list)
            save_gallery_videos(prop, request.FILES.getlist('gallery_videos'))
            
            # Log activity
            ActivityLog.log(
                user=request.user,
                action='update',
                model_type='property',
                object_id=prop.id,
                object_repr=prop.title,
                description=f'تعديل العقار: {prop.title}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Create notification
            Notification.create(
                user=request.user,
                notification_type='success',
                title='تعديل عقار',
                message=f'تم تعديل العقار: {prop.title}',
                link=f'/property/{prop.slug}/',
                metadata={'property_id': prop.id, 'property_title': prop.title}
            )
            
            messages.success(request, 'تم تحديث العقار')
            return redirect('dashboard')
        return render(request, 'properties/edit_property.html', {
            'property': prop, 'form': form, 'virtual_tours': virtual_tours, 'auctions': auctions,
        })
    return render(request, 'properties/edit_property.html', {
        'property': prop, 'form': PropertyForm(instance=prop), 'virtual_tours': virtual_tours, 'auctions': auctions,
    })


@login_required
@staff_required
def property_statistics(request):
    """إحصائيات متقدمة وتقارير العقارات"""
    from django.db.models import Count, Q, Avg, Sum, Min, Max
    from django.db.models.functions import TruncDate, TruncMonth
    from django.utils import timezone
    from datetime import timedelta

    properties = get_accessible_properties(request.user)
    
    # General stats
    total_properties = properties.count()
    active_properties = properties.filter(status='active').count()
    sold_properties = properties.filter(status='sold').count()
    pending_properties = properties.filter(status='pending').count()
    
    # Property type stats
    type_stats = properties.values('type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Governorate stats
    governorate_stats = properties.values('governorate').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Price statistics
    price_stats = properties.aggregate(
        avg_price=Avg('price'),
        min_price=Min('price'),
        max_price=Max('price'),
        total_value=Sum('price')
    )
    
    # Monthly property additions
    six_months_ago = timezone.now() - timedelta(days=180)
    monthly_properties = ActivityLog.objects.filter(
        created_at__gte=six_months_ago,
        model_type='property',
        action='create'
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')
    
    # Most viewed properties
    top_viewed = properties.order_by('-views_count')[:10]
    
    # Activity stats for properties
    activity_stats = ActivityLog.objects.filter(
        model_type='property'
    ).values('action').annotate(
        count=Count('id')
    ).order_by('-count')
    
    return render(request, 'properties/property_statistics.html', {
        'total_properties': total_properties,
        'active_properties': active_properties,
        'sold_properties': sold_properties,
        'pending_properties': pending_properties,
        'type_stats': type_stats,
        'governorate_stats': governorate_stats,
        'price_stats': price_stats,
        'monthly_properties': monthly_properties,
        'top_viewed': top_viewed,
        'activity_stats': activity_stats,
    })


@login_required
@staff_required
@require_POST
def delete_property(request, property_id):
    try:
        prop = get_object_or_404(Property, pk=property_id)
        if not can_delete_property(request.user, prop):
            messages.error(request, 'ليس لديك صلاحية حذف هذا العقار')
            return redirect('dashboard')
        title = prop.display_title
        
        # Log activity before deletion
        ActivityLog.log(
            user=request.user,
            action='delete',
            model_type='property',
            object_id=prop.id,
            object_repr=title,
            description=f'حذف العقار: {title}',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Create notification before deletion
        Notification.create(
            user=request.user,
            notification_type='warning',
            title='حذف عقار',
            message=f'تم حذف العقار: {title}',
            metadata={'property_id': prop.id, 'property_title': title}
        )
        
        # Track broker statistics before deletion
        if prop.broker:
            from .models import BrokerIndividualStats
            BrokerIndividualStats.track_property_deleted(prop.broker)
        
        prop.delete()
        messages.success(request, f'تم حذف العقار: {title}')
        return redirect('dashboard')
    except Exception as e:
        messages.error(request, f'حدث خطأ أثناء حذف العقار: {str(e)}')
        return redirect('dashboard')


@login_required
@staff_required
@require_POST
def delete_property_image(request, image_id):
    img = get_object_or_404(PropertyImage, pk=image_id)
    prop_id = img.property_id
    img.delete()
    messages.success(request, 'تم حذف الصورة')
    return redirect('edit_property', property_id=prop_id)


@rate_limit('message', limit=5, period=300)
@require_http_methods(['POST'])
def send_message(request):
    form = MessageForm(request.POST)
    property_id = request.POST.get('property_id')
    prop = None
    if property_id:
        prop = get_object_or_404(Property, pk=property_id)

    if form.is_valid():
        msg = form.save(commit=False)
        msg.property = prop
        if prop and prop.broker_id:
            msg.broker = prop.broker
        msg.save()
        messages.success(request, 'تم إرسال رسالتك بنجاح. سنتواصل معك قريباً.')
        logger.info('New message from %s', msg.name)
        if prop:
            return redirect(prop.get_absolute_url())
        return redirect('contact')
    messages.error(request, 'يرجى تعبئة جميع الحقول المطلوبة بشكل صحيح')
    if prop:
        return redirect(prop.get_absolute_url())
    return redirect('contact')


@login_required
@staff_required
@require_POST
def mark_legacy_message_read(request, message_id):
    msg = get_object_or_404(Message, pk=message_id)
    msg.is_read = True
    msg.save(update_fields=['is_read'])
    return redirect('dashboard')


@login_required
@staff_required
def add_note(request):
    try:
        if request.method == 'POST':
            form = PropertyNoteForm(request.POST)
            if form.is_valid():
                note = form.save()
                messages.success(request, f'تم إضافة الملاحظة: {note.title}')
                return redirect('dashboard')
            messages.error(request, 'يرجى تصحيح الأخطاء في النموذج')
            for field, errs in form.errors.items():
                for e in errs:
                    messages.error(request, f'{field}: {e}')
        return redirect('dashboard')
    except Exception as e:
        logger.error(f'Error adding note: {str(e)}')
        messages.error(request, f'حدث خطأ أثناء حفظ الملاحظة: {str(e)}')
        return redirect('dashboard')


@login_required
@staff_required
def toggle_note_complete(request, note_id):
    try:
        note = get_object_or_404(PropertyNote, pk=note_id)
        note.is_completed = not note.is_completed
        note.save(update_fields=['is_completed'])
        status = 'مكتمل' if note.is_completed else 'غير مكتمل'
        messages.success(request, f'تم تحديث حالة الملاحظة إلى {status}')
        return redirect('dashboard')
    except Exception as e:
        messages.error(request, 'ميزة الملاحظات غير متاحة حالياً. يرجى تطبيق الترحيلات (migrations).')
        return redirect('dashboard')


@login_required
@staff_required
def delete_note(request, note_id):
    try:
        note = get_object_or_404(PropertyNote, pk=note_id)
        note.delete()
        messages.success(request, f'تم حذف الملاحظة: {note.title}')
        return redirect('dashboard')
    except Exception as e:
        messages.error(request, 'ميزة الملاحظات غير متاحة حالياً. يرجى تطبيق الترحيلات (migrations).')
        return redirect('dashboard')


@login_required
def mark_notification_read(request, notification_id):
    try:
        notification = get_object_or_404(Notification, pk=notification_id, user=request.user)
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return redirect('dashboard')
    except Exception as e:
        logger.error(f'Error marking notification as read: {str(e)}')
        return redirect('dashboard')


@login_required
def delete_notification(request, notification_id):
    try:
        notification = get_object_or_404(Notification, pk=notification_id, user=request.user)
        notification.delete()
        messages.success(request, 'تم حذف الإشعار')
        return redirect('dashboard')
    except Exception as e:
        logger.error(f'Error deleting notification: {str(e)}')
        return redirect('dashboard')


@login_required
@staff_required
def add_virtual_tour(request, property_id):
    prop = get_object_or_404(Property, pk=property_id)
    if request.method == 'POST':
        form = VirtualTour360Form(request.POST, request.FILES)
        if form.is_valid():
            tour = form.save(commit=False)
            tour.property = prop
            tour.save()
            messages.success(request, f'تم إضافة الجولة الافتراضية: {tour.title}')
            return redirect('edit_property', property_id=property_id)
    else:
        form = VirtualTour360Form(initial={'property': prop})
    return render(request, 'properties/add_virtual_tour.html', {
        'form': form,
        'property': prop,
    })


@login_required
@staff_required
@require_POST
def delete_virtual_tour(request, tour_id):
    try:
        tour = get_object_or_404(VirtualTour360, pk=tour_id)
        property_id = tour.property_id
        tour.delete()
        messages.success(request, 'تم حذف الجولة الافتراضية')
        return redirect('edit_property', property_id=property_id)
    except Exception as e:
        logger.error(f'Error deleting virtual tour: {str(e)}')
        return redirect('dashboard')


@login_required
@staff_required
def add_auction(request, property_id):
    prop = get_object_or_404(Property, pk=property_id)
    if request.method == 'POST':
        form = AuctionForm(request.POST)
        if form.is_valid():
            auction = form.save(commit=False)
            auction.property = prop
            auction.save()
            messages.success(request, f'تم إنشاء المزاد: {auction.title}')
            return redirect('edit_property', property_id=property_id)
    else:
        form = AuctionForm(initial={'property': prop})
    return render(request, 'properties/add_auction.html', {
        'form': form,
        'property': prop,
    })


@login_required
@staff_required
@require_POST
def delete_auction(request, auction_id):
    try:
        auction = get_object_or_404(Auction, pk=auction_id)
        property_id = auction.property_id
        auction.delete()
        messages.success(request, 'تم حذف المزاد')
        return redirect('edit_property', property_id=property_id)
    except Exception as e:
        logger.error(f'Error deleting auction: {str(e)}')
        return redirect('dashboard')


def auctions_list(request):
    try:
        auctions = Auction.objects.all().select_related('property').prefetch_related('bids')
    except Exception:
        auctions = []
    
    paginator = Paginator(auctions, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'properties/auctions.html', {
        'auctions': page_obj,
        'page_obj': page_obj,
    })


def auction_detail(request, auction_id):
    auction = get_object_or_404(Auction, pk=auction_id)
    bids = auction.bids.select_related('user').all().order_by('-amount', '-created_at')
    
    if request.method == 'POST' and request.user.is_authenticated:
        form = BidForm(request.POST)
        if form.is_valid():
            bid = form.save(commit=False)
            bid.auction = auction
            bid.user = request.user
            
            # Validate bid amount
            current_highest = auction.get_current_highest_bid()
            if bid.amount <= current_highest:
                messages.error(request, f'يجب أن يكون المبلغ أعلى من أعلى مزايدة الحالية: {current_highest:,}')
            elif bid.amount < auction.starting_price:
                messages.error(request, f'يجب أن يكون المبلغ أعلى من سعر البداية: {auction.starting_price:,}')
            else:
                bid.save()
                messages.success(request, f'تم إضافة مزايدتك: {bid.amount:,}')
                return redirect('auction_detail', auction_id=auction_id)
    else:
        form = BidForm()
    
    return render(request, 'properties/auction_detail.html', {
        'auction': auction,
        'bids': bids,
        'form': form,
    })


def auction_terms(request):
    return render(request, 'properties/auction_terms.html')


@login_required
def building_request_create(request):
    if request.method == 'POST':
        form = BuildingRequestForm(request.POST)
        if form.is_valid():
            building_request = form.save(commit=False)
            building_request.user = request.user
            building_request.save()
            messages.success(request, 'تم إنشاء طلب البناء بنجاح')
            return redirect('building_request_detail', request_id=building_request.id)
    else:
        form = BuildingRequestForm()
    return render(request, 'properties/building_request_create.html', {'form': form})


@login_required
def building_request_detail(request, request_id):
    building_request = get_object_or_404(BuildingRequest, pk=request_id)
    return render(request, 'properties/building_request_detail.html', {'building_request': building_request})


@login_required
def building_request_list(request):
    try:
        building_requests = BuildingRequest.objects.filter(user=request.user).select_related('land_info', 'building_details', 'budget').order_by('-created_at')
    except Exception:
        building_requests = []
    return render(request, 'properties/building_request_list.html', {'building_requests': building_requests})


@login_required
def building_request_add_land_info(request, request_id):
    building_request = get_object_or_404(BuildingRequest, pk=request_id)
    if request.method == 'POST':
        form = LandInfoForm(request.POST, request.FILES)
        if form.is_valid():
            land_info = form.save(commit=False)
            land_info.building_request = building_request
            land_info.save()
            messages.success(request, 'تم إضافة معلومات الأرض بنجاح')
            return redirect('building_request_detail', request_id=request_id)
    else:
        form = LandInfoForm()
    return render(request, 'properties/building_request_add_land_info.html', {'form': form, 'building_request': building_request})


@login_required
def building_request_add_building_details(request, request_id):
    building_request = get_object_or_404(BuildingRequest, pk=request_id)
    if request.method == 'POST':
        form = BuildingDetailsForm(request.POST)
        if form.is_valid():
            building_details = form.save(commit=False)
            building_details.building_request = building_request
            building_details.save()
            messages.success(request, 'تم إضافة تفاصيل البناء بنجاح')
            return redirect('building_request_detail', request_id=request_id)
    else:
        form = BuildingDetailsForm()
    return render(request, 'properties/building_request_add_building_details.html', {'form': form, 'building_request': building_request})


@login_required
def building_request_add_budget(request, request_id):
    building_request = get_object_or_404(BuildingRequest, pk=request_id)
    if request.method == 'POST':
        form = BudgetForm(request.POST)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.building_request = building_request
            budget.save()
            messages.success(request, 'تم إضافة الميزانية بنجاح')
            return redirect('building_request_detail', request_id=request_id)
    else:
        form = BudgetForm()
    return render(request, 'properties/building_request_add_budget.html', {'form': form, 'building_request': building_request})


@login_required
def building_request_add_quote(request, request_id):
    building_request = get_object_or_404(BuildingRequest, pk=request_id)
    if request.method == 'POST':
        form = QuoteForm(request.POST)
        if form.is_valid():
            quote = form.save(commit=False)
            quote.building_request = building_request
            quote.save()
            messages.success(request, 'تم إضافة العرض بنجاح')
            return redirect('building_request_detail', request_id=request_id)
    else:
        form = QuoteForm()
    return render(request, 'properties/building_request_add_quote.html', {'form': form, 'building_request': building_request})


@login_required
def building_request_add_contractor_bid(request, request_id):
    building_request = get_object_or_404(BuildingRequest, pk=request_id)
    if request.method == 'POST':
        form = ContractorBidForm(request.POST)
        if form.is_valid():
            bid = form.save(commit=False)
            bid.building_request = building_request
            bid.save()
            messages.success(request, 'تم إضافة المزايدة بنجاح')
            return redirect('building_request_detail', request_id=request_id)
    else:
        form = ContractorBidForm()
    return render(request, 'properties/building_request_add_contractor_bid.html', {'form': form, 'building_request': building_request})


@login_required
def building_request_add_contractor_rating(request, request_id):
    building_request = get_object_or_404(BuildingRequest, pk=request_id)
    if request.method == 'POST':
        form = ContractorRatingForm(request.POST)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.building_request = building_request
            rating.save()
            messages.success(request, 'تم إضافة التقييم بنجاح')
            return redirect('building_request_detail', request_id=request_id)
    else:
        form = ContractorRatingForm()
    return render(request, 'properties/building_request_add_contractor_rating.html', {'form': form, 'building_request': building_request})


@login_required
def create_auction(request):
    """Create a new auction"""
    if request.method == 'POST':
        form = AuctionForm(request.POST)
        if form.is_valid():
            auction = form.save(commit=False)
            auction.save()
            messages.success(request, 'تم إنشاء المزاد بنجاح')
            return redirect('auction_detail', auction_id=auction.id)
    else:
        form = AuctionForm()
    return render(request, 'properties/create_auction.html', {'form': form})


def auction_detail(request, auction_id):
    """View auction details with real-time updates"""
    auction = get_object_or_404(Auction, id=auction_id)
    
    # Check if auction requires access code
    if auction.access_code:
        if 'auction_access' not in request.session or request.session['auction_access'] != auction.id:
            if request.method == 'POST':
                code = request.POST.get('access_code')
                if code == auction.access_code:
                    request.session['auction_access'] = auction.id
                    return redirect('auction_detail', auction_id=auction.id)
                else:
                    messages.error(request, 'كود الدخول غير صحيح')
            return render(request, 'properties/auction_access.html', {'auction': auction})
    
    # Get auction data
    highest_bid = auction.get_current_highest_bid()
    total_bids = auction.get_total_bids()
    participant_count = auction.get_participant_count()
    time_remaining = auction.get_time_remaining()
    
    # Check if user is participant
    is_participant = False
    if request.user.is_authenticated:
        try:
            AuctionParticipant.objects.get(auction=auction, user=request.user)
            is_participant = True
        except AuctionParticipant.DoesNotExist:
            pass
    
    context = {
        'auction': auction,
        'highest_bid': highest_bid,
        'total_bids': total_bids,
        'participant_count': participant_count,
        'time_remaining': time_remaining,
        'is_participant': is_participant,
    }
    return render(request, 'properties/auction_detail.html', context)


@login_required
def place_bid(request, auction_id):
    """Place a bid on an auction"""
    auction = get_object_or_404(Auction, id=auction_id)
    
    if not auction.is_active():
        messages.error(request, 'المزاد غير نشط حالياً')
        return redirect('auction_detail', auction_id=auction.id)
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        try:
            amount = int(amount)
            bid = Bid(auction=auction, user=request.user, amount=amount)
            bid.save()
            messages.success(request, 'تم تقديم عرضك بنجاح')
            if bid.is_auto_extended:
                messages.info(request, 'تم تمديد المزاد تلقائياً لمدة 5 دقائق')
        except ValueError as e:
            messages.error(request, str(e))
    
    return redirect('auction_detail', auction_id=auction.id)


@login_required
def join_auction(request, auction_id):
    """Join an auction as a participant"""
    auction = get_object_or_404(Auction, id=auction_id)
    
    if request.method == 'POST':
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        
        # Create or update participant
        participant, created = AuctionParticipant.objects.get_or_create(
            auction=auction,
            user=request.user,
            defaults={
                'phone': phone,
                'email': email,
            }
        )
        
        if not created:
            participant.phone = phone
            participant.email = email
            participant.save()
        
        messages.success(request, 'تم الانضمام إلى المزاد بنجاح')
    
    return redirect('auction_detail', auction_id=auction.id)


@login_required
def auction_list(request):
    """List all auctions"""
    auctions = Auction.objects.all().order_by('-created_at')
    return render(request, 'properties/auctions.html', {'auctions': auctions})


# Auction Advanced Features Views

@login_required
def setup_auto_bid(request, auction_id):
    """Setup automatic bidding for an auction"""
    auction = get_object_or_404(Auction, id=auction_id)
    
    if request.method == 'POST':
        form = AutoBidForm(request.POST)
        if form.is_valid():
            auto_bid, created = AutoBid.objects.update_or_create(
                auction=auction,
                user=request.user,
                defaults={
                    'max_amount': form.cleaned_data['max_amount'],
                    'is_active': form.cleaned_data['is_active']
                }
            )
            if created:
                messages.success(request, 'تم تفعيل المزايدة الآلية بنجاح')
            else:
                messages.success(request, 'تم تحديث المزايدة الآلية بنجاح')
            return redirect('auction_detail', auction_id=auction.id)
    else:
        try:
            auto_bid = AutoBid.objects.get(auction=auction, user=request.user)
            form = AutoBidForm(instance=auto_bid)
        except AutoBid.DoesNotExist:
            form = AutoBidForm()
    
    return render(request, 'properties/setup_auto_bid.html', {
        'form': form,
        'auction': auction
    })


@login_required
def toggle_auto_bid(request, auction_id):
    """Toggle auto-bid active status"""
    auction = get_object_or_404(Auction, id=auction_id)
    
    try:
        auto_bid = AutoBid.objects.get(auction=auction, user=request.user)
        auto_bid.is_active = not auto_bid.is_active
        auto_bid.save()
        status = 'مفعّل' if auto_bid.is_active else 'معطّل'
        messages.success(request, f'تم {status} المزايدة الآلية')
    except AutoBid.DoesNotExist:
        messages.error(request, 'لم يتم إعداد المزايدة الآلية بعد')
    
    return redirect('auction_detail', auction_id=auction.id)


@login_required
def auction_rating(request, auction_id):
    """Rate auction participants"""
    auction = get_object_or_404(Auction, id=auction_id)
    
    if auction.status != 'ended':
        messages.error(request, 'يمكن التقييم فقط بعد انتهاء المزاد')
        return redirect('auction_detail', auction_id=auction.id)
    
    if request.method == 'POST':
        form = AuctionRatingForm(request.POST)
        if form.is_valid():
            # Get the highest bidder (winner)
            highest_bid = auction.bids.order_by('-amount').first()
            if not highest_bid:
                messages.error(request, 'لا يوجد فائز للمزاد')
                return redirect('auction_detail', auction_id=auction.id)
            
            AuctionRating.objects.update_or_create(
                auction=auction,
                rater=request.user,
                rated_user=highest_bid.user,
                defaults={
                    'rating': form.cleaned_data['rating'],
                    'comment': form.cleaned_data['comment']
                }
            )
            messages.success(request, 'تم إرسال التقييم بنجاح')
            return redirect('auction_detail', auction_id=auction.id)
    else:
        form = AuctionRatingForm()
    
    return render(request, 'properties/auction_rating.html', {
        'form': form,
        'auction': auction
    })


@login_required
def auction_stats(request, auction_id):
    """View auction statistics"""
    auction = get_object_or_404(Auction, id=auction_id)
    
    # Get or create stats
    stats, created = AuctionStats.objects.get_or_create(auction=auction)
    if created:
        stats.update_stats()
    
    # Get ratings
    ratings = auction.ratings.all()
    avg_rating = 0
    if ratings:
        avg_rating = sum(r.rating for r in ratings) / len(ratings)
    
    context = {
        'auction': auction,
        'stats': stats,
        'ratings': ratings,
        'avg_rating': round(avg_rating, 1),
        'rating_count': ratings.count()
    }
    return render(request, 'properties/auction_stats.html', context)


@login_required
def setup_live_stream(request, auction_id):
    """Setup live streaming for auction"""
    auction = get_object_or_404(Auction, id=auction_id)
    
    if request.method == 'POST':
        form = AuctionLiveStreamForm(request.POST)
        if form.is_valid():
            live_stream, created = AuctionLiveStream.objects.update_or_create(
                auction=auction,
                defaults={
                    'stream_url': form.cleaned_data['stream_url'],
                    'stream_key': form.cleaned_data['stream_key'],
                    'platform': form.cleaned_data['platform'],
                    'chat_enabled': form.cleaned_data['chat_enabled'],
                    'recording_enabled': form.cleaned_data['recording_enabled']
                }
            )
            if created:
                messages.success(request, 'تم إعداد البث المباشر بنجاح')
            else:
                messages.success(request, 'تم تحديث البث المباشر بنجاح')
            return redirect('auction_detail', auction_id=auction.id)
    else:
        try:
            live_stream = AuctionLiveStream.objects.get(auction=auction)
            form = AuctionLiveStreamForm(instance=live_stream)
        except AuctionLiveStream.DoesNotExist:
            form = AuctionLiveStreamForm()
    
    return render(request, 'properties/setup_live_stream.html', {
        'form': form,
        'auction': auction
    })


@login_required
def auction_notifications(request):
    """View auction notifications for current user"""
    notifications = AuctionNotification.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    # Mark as read
    notifications.filter(is_read=False).update(is_read=True)
    
    return render(request, 'properties/auction_notifications.html', {
        'notifications': notifications
    })


@login_required
def create_auction_advertisement(request, auction_id):
    """Create advertisement for auction"""
    auction = get_object_or_404(Auction, id=auction_id)
    
    if request.method == 'POST':
        form = AuctionAdvertisementForm(request.POST)
        if form.is_valid():
            ad = form.save(commit=False)
            ad.auction = auction
            ad.save()
            messages.success(request, 'تم إنشاء الإعلان بنجاح')
            return redirect('auction_detail', auction_id=auction.id)
    else:
        form = AuctionAdvertisementForm()
    
    return render(request, 'properties/create_auction_advertisement.html', {
        'form': form,
        'auction': auction
    })


@login_required
def financial_dashboard(request):
    """Financial dashboard for office management"""
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    from datetime import timedelta
    
    # Get user's transactions
    user_transactions = FinancialTransaction.objects.filter(user=request.user)
    
    # Calculate statistics


def hotels_list(request):
    """View for listing and searching hotels"""
    form = HotelSearchForm(request.GET or None)
    hotels = Hotel.objects.filter(is_active=True)
    
    if form.is_valid():
        # Filter by star rating
        if form.cleaned_data.get('star_rating'):
            hotels = hotels.filter(star_rating__in=form.cleaned_data['star_rating'])
        
        # Filter by price range
        if form.cleaned_data.get('price_range'):
            hotels = hotels.filter(price_range__in=form.cleaned_data['price_range'])
        
        # Filter by room types (JSON field)
        if form.cleaned_data.get('room_types'):
            hotels = [h for h in hotels if any(rt in h.room_types for rt in form.cleaned_data['room_types'])]
        
        # Filter by meal plan
        if form.cleaned_data.get('meal_plan'):
            hotels = hotels.filter(meal_plan=form.cleaned_data['meal_plan'])
        
        # Filter by services (JSON field)
        if form.cleaned_data.get('services'):
            hotels = [h for h in hotels if any(s in h.services for s in form.cleaned_data['services'])]
        
        # Filter by suitable for (JSON field)
        if form.cleaned_data.get('suitable_for'):
            hotels = [h for h in hotels if any(sf in h.suitable_for for sf in form.cleaned_data['suitable_for'])]
        
        # Filter by governorate
        if form.cleaned_data.get('governorate'):
            hotels = hotels.filter(governorate=form.cleaned_data['governorate'])
    
    return render(request, 'properties/hotels_list.html', {
        'hotels': hotels,
        'form': form,
    })


def resorts_list(request):
    """View for listing and searching resorts"""
    form = ResortSearchForm(request.GET or None)
    resorts = Resort.objects.filter(is_active=True)
    
    if form.is_valid():
        # Filter by resort type
        if form.cleaned_data.get('resort_type'):
            resorts = resorts.filter(resort_type__in=form.cleaned_data['resort_type'])
        
        # Filter by price range
        if form.cleaned_data.get('price_range'):
            resorts = resorts.filter(price_range__in=form.cleaned_data['price_range'])
        
        # Filter by accommodation types (JSON field)
        if form.cleaned_data.get('accommodation_types'):
            resorts = [r for r in resorts if any(at in r.accommodation_types for at in form.cleaned_data['accommodation_types'])]
        
        # Filter by facilities (JSON field)
        if form.cleaned_data.get('facilities'):
            resorts = [r for r in resorts if any(f in r.facilities for f in form.cleaned_data['facilities'])]
        
        # Filter by suitable for (JSON field)
        if form.cleaned_data.get('suitable_for'):
            resorts = [r for r in resorts if any(sf in r.suitable_for for sf in form.cleaned_data['suitable_for'])]
        
        # Filter by governorate
        if form.cleaned_data.get('governorate'):
            resorts = resorts.filter(governorate=form.cleaned_data['governorate'])
    
    return render(request, 'properties/resorts_list.html', {
        'resorts': resorts,
        'form': form,
    })


@login_required
def financial_dashboard(request):
    """Financial dashboard for office management"""
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    from datetime import timedelta
    
    # Get user's transactions
    user_transactions = FinancialTransaction.objects.filter(user=request.user)
    
    # Calculate statistics
    total_sales = user_transactions.filter(
        transaction_type='sale', status='completed'
    ).aggregate(total=Sum('sale_price'))['total'] or 0
    
    total_commissions = user_transactions.filter(
        status='completed'
    ).aggregate(total=Sum('commission_amount'))['total'] or 0
    
    total_expenses = Expense.objects.filter(user=request.user).aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    total_profits = Profit.objects.filter(user=request.user).aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    net_profit = total_commissions + total_profits - total_expenses
    
    # Get properties sold
    properties_sold = user_transactions.filter(
        transaction_type='sale', status='completed'
    ).count()
    
    # Get completed transactions
    completed_transactions = user_transactions.filter(status='completed').count()
    
    # Get recent transactions
    recent_transactions = user_transactions.order_by('-created_at')[:10]
    
    # Get recent expenses
    recent_expenses = Expense.objects.filter(user=request.user).order_by('-date')[:10]
    
    # Get recent profits
    recent_profits = Profit.objects.filter(user=request.user).order_by('-date')[:10]
    
    # Get wallet info
    wallet, created = OfficeWallet.objects.get_or_create(user=request.user)
    
    # Time-based statistics
    today = timezone.now().date()
    this_month = today.replace(day=1)
    
    # Daily stats
    daily_sales = user_transactions.filter(
        transaction_type='sale', status='completed', created_at__date=today
    ).aggregate(total=Sum('sale_price'))['total'] or 0
    
    daily_commissions = user_transactions.filter(
        status='completed', created_at__date=today
    ).aggregate(total=Sum('commission_amount'))['total'] or 0
    
    # Monthly stats
    monthly_sales = user_transactions.filter(
        transaction_type='sale', status='completed', created_at__date__gte=this_month
    ).aggregate(total=Sum('sale_price'))['total'] or 0
    
    monthly_commissions = user_transactions.filter(
        status='completed', created_at__date__gte=this_month
    ).aggregate(total=Sum('commission_amount'))['total'] or 0
    
    monthly_expenses = Expense.objects.filter(
        user=request.user, date__gte=this_month
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    context = {
        'total_sales': total_sales,
        'total_commissions': total_commissions,
        'total_expenses': total_expenses,
        'total_profits': total_profits,
        'net_profit': net_profit,
        'properties_sold': properties_sold,
        'completed_transactions': completed_transactions,
        'recent_transactions': recent_transactions,
        'recent_expenses': recent_expenses,
        'recent_profits': recent_profits,
        'wallet': wallet,
        'daily_sales': daily_sales,
        'daily_commissions': daily_commissions,
        'monthly_sales': monthly_sales,
        'monthly_commissions': monthly_commissions,
        'monthly_expenses': monthly_expenses,
    }
    
    return render(request, 'properties/financial_dashboard.html', context)


@login_required
def add_financial_transaction(request):
    """Add a new financial transaction"""
    if request.method == 'POST':
        form = FinancialTransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user
            transaction.save()
            
            # Update wallet - handle missing models gracefully
            try:
                wallet, created = OfficeWallet.objects.get_or_create(user=request.user)
                if transaction.status == 'completed' and transaction.commission_amount:
                    wallet.pending_commissions += transaction.commission_amount
                    wallet.save()
                    
                    # Create wallet transaction
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='commission',
                        amount=transaction.commission_amount,
                        balance_before=wallet.current_balance,
                        balance_after=wallet.current_balance + transaction.commission_amount,
                        description=f'عمولة من بيع {transaction.property.display_title if transaction.property else "عقار"}',
                        related_transaction=transaction
                    )
            except Exception as e:
                # Log the error but don't fail the transaction
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error updating wallet: {e}")
            
            messages.success(request, 'تم إضافة المعاملة المالية بنجاح')
            return redirect('financial_dashboard')
    else:
        form = FinancialTransactionForm()
    
    return render(request, 'properties/add_financial_transaction.html', {'form': form})


@login_required
def add_expense(request):
    """Add a new expense"""
    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
            
            # Update wallet - handle missing models gracefully
            try:
                wallet, created = OfficeWallet.objects.get_or_create(user=request.user)
                if expense.amount:
                    wallet.current_balance -= expense.amount
                    wallet.save()
                    
                    # Create wallet transaction
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='withdrawal',
                        amount=expense.amount,
                        balance_before=wallet.current_balance + expense.amount,
                        balance_after=wallet.current_balance,
                        description=f'مصروف: {expense.title or "بدون عنوان"}',
                    )
            except Exception as e:
                # Log the error but don't fail the expense
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error updating wallet: {e}")
            
            messages.success(request, 'تم إضافة المصروف بنجاح')
            return redirect('financial_dashboard')
    else:
        form = ExpenseForm()
    
    return render(request, 'properties/add_expense.html', {'form': form})


@login_required
def add_payment(request, transaction_id):
    """Add a payment to property owner"""
    transaction = get_object_or_404(FinancialTransaction, id=transaction_id, user=request.user)
    
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.financial_transaction = transaction
            payment.user = request.user
            payment.save()
            
            messages.success(request, 'تم إضافة الدفعة بنجاح')
            return redirect('financial_dashboard')
    else:
        form = PaymentForm()
    
    context = {
        'form': form,
        'transaction': transaction,
        'remaining_amount': transaction.owner_amount - transaction.payments.filter(status='completed').aggregate(
            total=Sum('amount')
        )['total'] or 0
    }
    
    return render(request, 'properties/add_payment.html', context)


@login_required
def wallet_details(request):
    """View wallet details and transaction history"""
    wallet, created = OfficeWallet.objects.get_or_create(user=request.user)
    transactions = wallet.transactions.order_by('-created_at')[:50]
    
    context = {
        'wallet': wallet,
        'transactions': transactions,
    }
    
    return render(request, 'properties/wallet_details.html', context)


@login_required
def add_profit(request):
    """Add a profit record"""
    if request.method == 'POST':
        form = ProfitForm(request.POST, user=request.user)
        if form.is_valid():
            profit = form.save(commit=False)
            profit.user = request.user
            profit.save()
            
            messages.success(request, 'تم إضافة الربح بنجاح')
            return redirect('financial_dashboard')
    else:
        form = ProfitForm(user=request.user)
    
    return render(request, 'properties/add_profit.html', {'form': form})


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def subscription_plans_list(request):
    """List all subscription plans"""
    plans = SubscriptionPlan.objects.all().order_by('period', 'ads_limit')
    return render(request, 'properties/subscription_plans_list.html', {'plans': plans})


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def subscription_plan_create(request):
    """Create a new subscription plan"""
    if request.method == 'POST':
        form = SubscriptionPlanForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إضافة خطة الاشتراك بنجاح')
            return redirect('subscription_plans_list')
    else:
        form = SubscriptionPlanForm()
    
    return render(request, 'properties/subscription_plan_form.html', {'form': form, 'title': 'إضافة خطة اشتراك جديدة'})


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def subscription_plan_edit(request, plan_id):
    """Edit an existing subscription plan"""
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    
    if request.method == 'POST':
        form = SubscriptionPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث خطة الاشتراك بنجاح')
            return redirect('subscription_plans_list')
    else:
        form = SubscriptionPlanForm(instance=plan)
    
    return render(request, 'properties/subscription_plan_form.html', {'form': form, 'title': 'تعديل خطة الاشتراك', 'plan': plan})


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def subscription_plan_delete(request, plan_id):
    """Delete a subscription plan"""
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    
    if request.method == 'POST':
        plan.delete()
        messages.success(request, 'تم حذف خطة الاشتراك بنجاح')
        return redirect('subscription_plans_list')
    
    return render(request, 'properties/subscription_plan_confirm_delete.html', {'plan': plan})


@login_required
def financial_reports(request):
    """View financial reports"""
    from django.db.models import Sum
    from django.utils import timezone
    from datetime import timedelta
    
    report_type = request.GET.get('type', 'monthly')
    
    # Get date range
    today = timezone.now().date()
    
    if report_type == 'daily':
        start_date = today
        end_date = today
    elif report_type == 'weekly':
        start_date = today - timedelta(days=7)
        end_date = today
    elif report_type == 'yearly':
        start_date = today.replace(month=1, day=1)
        end_date = today
    else:  # monthly
        start_date = today.replace(day=1)
        end_date = today
    
    # Get transactions in range
    transactions = FinancialTransaction.objects.filter(
        user=request.user,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    )
    
    expenses = Expense.objects.filter(
        user=request.user,
        date__gte=start_date,
        date__lte=end_date
    )
    
    # Calculate totals
    total_sales = transactions.filter(transaction_type='sale', status='completed').aggregate(
        total=Sum('sale_price')
    )['total'] or 0
    
    total_commissions = transactions.filter(status='completed').aggregate(
        total=Sum('commission_amount')
    )['total'] or 0
    
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0
    
    net_profit = total_commissions - total_expenses
    
    # Get transaction count
    transaction_count = transactions.count()
    expense_count = expenses.count()
    
    context = {
        'report_type': report_type,
        'start_date': start_date,
        'end_date': end_date,
        'total_sales': total_sales,
        'total_commissions': total_commissions,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
        'transaction_count': transaction_count,
        'expense_count': expense_count,
        'transactions': transactions.order_by('-created_at')[:20],
        'expenses': expenses.order_by('-date')[:20],
    }
    
    return render(request, 'properties/financial_reports.html', context)


@login_required
def submit_report(request):
    """Submit a new report."""
    if request.method == 'POST':
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.reporter = request.user
            report.save()
            messages.success(request, 'تم إرسال البلاغ بنجاح')
            return redirect('home')
    else:
        form = ReportForm()
    
    return render(request, 'properties/submit_report.html', {'form': form})


@login_required
@staff_required
def report_list(request):
    """List all reports for admin."""
    if not is_platform_admin(request.user):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    
    reports = Report.objects.all().select_related('reporter', 'assigned_to')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        reports = reports.filter(status=status_filter)
    
    # Filter by type
    type_filter = request.GET.get('type')
    if type_filter:
        reports = reports.filter(report_type=type_filter)
    
    # Filter by priority
    priority_filter = request.GET.get('priority')
    if priority_filter:
        reports = reports.filter(priority=priority_filter)
    
    paginator = Paginator(reports, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'properties/report_list.html', {
        'reports': page_obj,
        'page_obj': page_obj,
    })


@login_required
@staff_required
def report_detail(request, report_id):
    """View report details."""
    if not is_platform_admin(request.user):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    
    report = get_object_or_404(Report, pk=report_id)
    actions = report.actions.all().select_related('performed_by')
    
    if request.method == 'POST':
        action_type = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        if action_type:
            # Create action record
            ReportAction.objects.create(
                report=report,
                action=action_type,
                notes=notes,
                performed_by=request.user
            )
            
            # Update report status based on action
            if action_type == Report.ACTION_CLOSE_REPORT:
                report.status = Report.STATUS_CLOSED
                report.resolved_at = timezone.now()
            elif action_type == Report.ACTION_REJECT_REPORT:
                report.status = Report.STATUS_REJECTED
            elif action_type in [Report.ACTION_DELETE_AD, Report.ACTION_HIDE_AD, Report.ACTION_SUSPEND_ACCOUNT]:
                report.status = Report.STATUS_REVIEWING
            
            report.save()
            messages.success(request, 'تم تنفيذ الإجراء')
            return redirect('report_detail', report_id=report_id)
    
    return render(request, 'properties/report_detail.html', {
        'report': report,
        'actions': actions,
    })


@login_required
def user_messages(request):
    """عرض رسائل المستخدم مع الدلالين."""
    # Get messages where user is either sender or recipient
    messages = Message.objects.filter(
        message_type=Message.TYPE_USER_BROKER,
        is_deleted_by_sender=False if request.user in Message.objects.filter(sender=request.user) else True,
        is_deleted_by_recipient=False if request.user in Message.objects.filter(recipient=request.user) else True
    ).filter(
        models.Q(sender=request.user) | models.Q(recipient=request.user)
    ).select_related('sender', 'recipient').order_by('-created_at')
    
    # Get unread count
    unread_count = messages.filter(recipient=request.user, is_read=False).count()
    
    return render(request, 'properties/user_messages.html', {
        'messages': messages,
        'unread_count': unread_count,
    })


@login_required
def user_message_detail(request, message_id):
    """عرض تفاصيل رسالة المستخدم."""
    message = get_object_or_404(Message, pk=message_id)
    
    # Check if user has access to this message
    if message.sender != request.user and message.recipient != request.user:
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الرسالة')
        return redirect('user_messages')
    
    # Check if message is deleted for this user
    if (message.sender == request.user and message.is_deleted_by_sender) or \
       (message.recipient == request.user and message.is_deleted_by_recipient):
        messages.error(request, 'هذه الرسالة محذوفة')
        return redirect('user_messages')
    
    # Mark as read if user is recipient
    if message.recipient == request.user and not message.is_read:
        message.mark_as_read()
    
    return render(request, 'properties/user_message_detail.html', {
        'message': message,
    })


@login_required
def send_user_message(request, broker_id=None):
    """إرسال رسالة من مستخدم إلى دلال."""
    # Check if recipient broker exists
    recipient_broker = None
    if broker_id:
        recipient_broker = get_object_or_404(Broker, pk=broker_id)
    
    if request.method == 'POST':
        recipient_id = request.POST.get('recipient_id')
        message_text = request.POST.get('message')
        property_id = request.POST.get('property_id')
        
        if recipient_id and message_text:
            recipient = get_object_or_404(User, pk=recipient_id)
            recipient_broker_profile = get_broker(recipient)
            
            if not recipient_broker_profile:
                messages.error(request, 'المستلم ليس دلال')
            else:
                # Create message
                message = Message.objects.create(
                    name=request.user.get_full_name() or request.user.username,
                    email=request.user.email,
                    message=message_text,
                    message_type=Message.TYPE_USER_BROKER,
                    sender=request.user,
                    recipient=recipient,
                    broker=recipient_broker_profile
                )
                
                # Add property if specified
                if property_id:
                    try:
                        prop = Property.objects.get(pk=property_id)
                        message.property = prop
                        message.save()
                    except Property.DoesNotExist:
                        pass
                
                # Create notification for recipient
                from .utils import create_notification
                create_notification(
                    user=recipient,
                    notification_type='message',
                    title='رسالة جديدة',
                    message=f'لديك رسالة جديدة من {request.user.get_full_name() or request.user.username}',
                    link=f'/messages/{message.id}/'
                )
                
                messages.success(request, 'تم إرسال الرسالة بنجاح')
                return redirect('user_messages')
        else:
            messages.error(request, 'يرجى ملء جميع الحقول المطلوبة')
    
    # Get list of brokers to send message to
    brokers = Broker.objects.filter(is_active=True).exclude(user=request.user).select_related('user')
    
    return render(request, 'properties/send_user_message.html', {
        'brokers': brokers,
        'recipient_broker': recipient_broker,
    })


@login_required
@require_POST
def delete_user_message(request, message_id):
    """حذف رسالة المستخدم (حذف ناعم)."""
    message = get_object_or_404(Message, pk=message_id)
    
    # Check if user has access to this message
    if message.sender != request.user and message.recipient != request.user:
        messages.error(request, 'ليس لديك صلاحية لحذف هذه الرسالة')
        return redirect('user_messages')
    
    message.delete_for_user(request.user)
    messages.success(request, 'تم حذف الرسالة')
    return redirect('user_messages')


@login_required
def broker_messages_list(request):
    """List broker messages (inbox and sent)."""
    broker = get_broker(request.user)
    if not broker:
        messages.error(request, 'يجب أن تكون دلال للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    
    # Get message type filter (inbox/sent)
    message_type = request.GET.get('type', 'inbox')
    
    if message_type == 'sent':
        messages_list = Message.objects.filter(
            sender=request.user,
            message_type=Message.TYPE_BROKER_MESSAGE
        ).select_related('recipient')
    else:
        messages_list = Message.objects.filter(
            recipient=request.user,
            message_type=Message.TYPE_BROKER_MESSAGE
        ).select_related('sender')
    
    # Filter by archived status
    show_archived = request.GET.get('archived') == '1'
    if show_archived:
        messages_list = messages_list.filter(is_archived=True)
    else:
        messages_list = messages_list.filter(is_archived=False)
    
    messages_list = messages_list.order_by('-created_at')
    
    return render(request, 'properties/broker_messages_list.html', {
        'messages': messages_list,
        'message_type': message_type,
        'show_archived': show_archived,
    })


@login_required
def broker_message_detail(request, message_id):
    """View broker message details."""
    broker = get_broker(request.user)
    if not broker:
        messages.error(request, 'يجب أن تكون دلال للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    
    message = get_object_or_404(Message, pk=message_id, message_type=Message.TYPE_BROKER_MESSAGE)
    
    # Check if user is sender or recipient
    if message.sender != request.user and message.recipient != request.user:
        messages.error(request, 'ليس لديك صلاحية عرض هذه الرسالة')
        return redirect('broker_messages')
    
    # Mark as read if recipient
    if message.recipient == request.user and not message.is_read:
        message.is_read = True
        message.save()
    
    return render(request, 'properties/broker_message_detail.html', {
        'message': message,
    })


@login_required
def send_broker_message(request, broker_id=None):
    """Send a message to another user (broker or regular user)."""
    from .models import MessageAttachment
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    
    broker = get_broker(request.user)
    
    recipient_broker = None
    if broker_id:
        recipient_broker = get_object_or_404(Broker, pk=broker_id)
    
    if request.method == 'POST':
        recipient_id = request.POST.get('recipient')
        message_text = request.POST.get('message')
        attachments = request.FILES.getlist('attachment')
        
        if recipient_id and message_text:
            recipient = get_object_or_404(User, pk=recipient_id)
            recipient_broker_profile = get_broker(recipient)
            
            # Allow messaging to both brokers and regular users
            message = Message.objects.create(
                name=request.user.get_full_name() or request.user.username,
                email=request.user.email,
                phone=broker.phone if broker else '',
                message=message_text,
                message_type=Message.TYPE_BROKER_MESSAGE,
                sender=request.user,
                recipient=recipient,
                broker=broker
            )
            
            # Handle attachments
            for attachment in attachments:
                MessageAttachment.objects.create(
                    message=message,
                    file=attachment,
                    uploaded_by=request.user
                )
            
            # Send real-time notification via WebSocket
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"notifications_{recipient.id}",
                {
                    'type': 'notification',
                    'notification': {
                        'type': 'new_message',
                        'title': 'رسالة جديدة',
                        'message': f'رسالة جديدة من {request.user.get_full_name() or request.user.username}',
                        'sender_id': request.user.id,
                        'sender_name': request.user.get_full_name() or request.user.username,
                        'message_id': message.id,
                        'message_preview': message_text[:100]
                    },
                    'timestamp': str(message.created_at)
                }
            )
            
            messages.success(request, 'تم إرسال الرسالة بنجاح')
            return redirect('broker_messaging')
        else:
            messages.error(request, 'يرجى ملء جميع الحقول')
    
    # Get list of brokers to send message to
    brokers = Broker.objects.filter(is_active=True).exclude(user=request.user).select_related('user')
    
    return render(request, 'properties/send_broker_message.html', {
        'brokers': brokers,
        'recipient_broker': recipient_broker,
    })


@login_required
@require_POST
def archive_message(request, message_id):
    """Archive a message/conversation."""
    from django.http import JsonResponse
    
    message = get_object_or_404(Message, pk=message_id)
    
    # Check if user has access to this message
    if message.sender != request.user and message.recipient != request.user:
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'})
    
    # Archive the message
    message.archive()
    
    return JsonResponse({'success': True})


@login_required
def create_group_chat(request):
    """Create a new group chat."""
    from .models import Conversation, ConversationParticipant
    
    broker = get_broker(request.user)
    
    if request.method == 'POST':
        group_name = request.POST.get('group_name')
        group_description = request.POST.get('group_description')
        participants_ids = request.POST.getlist('participants')
        
        if not group_name:
            messages.error(request, 'اسم المجموعة مطلوب')
            return redirect('broker_messaging')
        
        if not participants_ids:
            messages.error(request, 'يجب اختيار مشارك واحد على الأقل')
            return redirect('broker_messaging')
        
        # Create conversation
        conversation = Conversation.objects.create(
            conversation_type=Conversation.TYPE_GROUP,
            name=group_name,
            description=group_description,
            created_by=request.user
        )
        
        # Add creator as admin participant
        ConversationParticipant.objects.create(
            conversation=conversation,
            user=request.user,
            role=ConversationParticipant.ROLE_ADMIN
        )
        
        # Add other participants
        for participant_id in participants_ids:
            try:
                participant = User.objects.get(pk=participant_id)
                ConversationParticipant.objects.create(
                    conversation=conversation,
                    user=participant,
                    role=ConversationParticipant.ROLE_MEMBER
                )
            except User.DoesNotExist:
                continue
        
        messages.success(request, 'تم إنشاء المجموعة بنجاح')
        return redirect('broker_messaging')
    
    return redirect('broker_messaging')


@login_required
@require_POST
def add_message_reaction(request, message_id):
    """Add or remove a reaction to a message."""
    from django.http import JsonResponse
    from .models import MessageReaction, ChatMessage
    
    reaction_type = request.POST.get('reaction_type')
    
    if not reaction_type:
        return JsonResponse({'success': False, 'error': 'نوع الرد مطلوب'})
    
    message = get_object_or_404(ChatMessage, pk=message_id)
    
    # Check if user has access to this message
    conversation = message.conversation
    if not conversation.participants.filter(id=request.user.id).exists():
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'})
    
    # Check if reaction already exists
    existing_reaction = MessageReaction.objects.filter(
        message=message,
        user=request.user,
        reaction_type=reaction_type
    ).first()
    
    if existing_reaction:
        # Remove reaction
        existing_reaction.delete()
        return JsonResponse({'success': True, 'action': 'removed'})
    else:
        # Add reaction
        MessageReaction.objects.create(
            message=message,
            user=request.user,
            reaction_type=reaction_type
        )
        return JsonResponse({'success': True, 'action': 'added'})


@login_required
@require_POST
def edit_message(request, message_id):
    """Edit a message."""
    from django.http import JsonResponse
    from .models import ChatMessage
    
    new_content = request.POST.get('content')
    
    if not new_content:
        return JsonResponse({'success': False, 'error': 'محتوى الرسالة مطلوب'})
    
    message = get_object_or_404(ChatMessage, pk=message_id)
    
    # Check if user is the sender
    if message.sender != request.user:
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'})
    
    # Edit the message
    message.edit(new_content)
    
    return JsonResponse({'success': True, 'content': new_content, 'edited_at': message.edited_at.isoformat() if message.edited_at else None})


@login_required
@require_POST
def delete_message(request, message_id):
    """Delete a message (soft delete)."""
    from django.http import JsonResponse
    from .models import ChatMessage
    
    message = get_object_or_404(ChatMessage, pk=message_id)
    
    # Check if user is the sender
    if message.sender != request.user:
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'})
    
    # Soft delete the message
    message.soft_delete()
    
    return JsonResponse({'success': True})


@login_required
@require_POST
def mark_message_read(request, message_id):
    """Mark a message as read."""
    from django.http import JsonResponse
    from .models import ChatMessage, MessageReadStatus
    from django.utils import timezone
    
    message = get_object_or_404(ChatMessage, pk=message_id)
    
    # Check if user is the recipient
    if message.sender == request.user:
        return JsonResponse({'success': False, 'error': 'لا يمكن وضع علامة قراءة على رسالتك'})
    
    # Check if user has access to this message
    conversation = message.conversation
    if not conversation.participants.filter(id=request.user.id).exists():
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'})
    
    # Mark as read
    MessageReadStatus.objects.get_or_create(
        message=message,
        user=request.user,
        defaults={'read_at': timezone.now()}
    )
    
    return JsonResponse({'success': True})


@login_required
def forward_message(request, message_id):
    """Forward a message to another conversation."""
    from .models import ChatMessage, Conversation
    
    original_message = get_object_or_404(ChatMessage, pk=message_id)
    
    # Check if user has access to the original message
    if not original_message.conversation.participants.filter(id=request.user.id).exists():
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('broker_messaging')
    
    if request.method == 'POST':
        target_conversation_id = request.POST.get('target_conversation')
        
        if not target_conversation_id:
            messages.error(request, 'يجب اختيار المحادثة المستهدفة')
            return redirect('broker_messaging')
        
        target_conversation = get_object_or_404(Conversation, pk=target_conversation_id)
        
        # Check if user is a participant in the target conversation
        if not target_conversation.participants.filter(id=request.user.id).exists():
            messages.error(request, 'ليس لديك صلاحية')
            return redirect('broker_messaging')
        
        # Create forwarded message
        ChatMessage.objects.create(
            conversation=target_conversation,
            sender=request.user,
            message_type=ChatMessage.TYPE_TEXT,
            content=original_message.content,
            reply_to=original_message
        )
        
        messages.success(request, 'تم إعادة توجيه الرسالة بنجاح')
        return redirect('broker_messaging')
    
    # Get user's conversations for forwarding
    user_conversations = Conversation.objects.filter(
        participants=request.user,
        is_active=True
    ).exclude(pk=original_message.conversation.pk)
    
    return render(request, 'properties/forward_message.html', {
        'original_message': original_message,
        'conversations': user_conversations,
    })


@login_required
@require_POST
def mute_user(request, user_id):
    """Mute a user."""
    from django.http import JsonResponse
    from .models import MutedUser
    
    user_to_mute = get_object_or_404(User, pk=user_id)
    
    if user_to_mute == request.user:
        return JsonResponse({'success': False, 'error': 'لا يمكن كتم نفسك'})
    
    MutedUser.objects.get_or_create(
        muter=request.user,
        muted=user_to_mute
    )
    
    return JsonResponse({'success': True, 'message': 'تم كتم المستخدم'})


@login_required
@require_POST
def unmute_user(request, user_id):
    """Unmute a user."""
    from django.http import JsonResponse
    from .models import MutedUser
    
    user_to_unmute = get_object_or_404(User, pk=user_id)
    
    MutedUser.objects.filter(
        muter=request.user,
        muted=user_to_unmute
    ).delete()
    
    return JsonResponse({'success': True, 'message': 'تم إلغاء كتم المستخدم'})


@login_required
@require_POST
def block_user_dashboard(request, user_id):
    """Block a user from dashboard."""
    from django.http import JsonResponse
    from .models import BlockedUser

    user_to_block = get_object_or_404(User, pk=user_id)

    if user_to_block == request.user:
        return JsonResponse({'success': False, 'error': 'لا يمكن حظر نفسك'})

    BlockedUser.objects.get_or_create(
        blocker=request.user,
        blocked=user_to_block,
    )

    return JsonResponse({'success': True, 'message': 'تم حظر المستخدم'})


@login_required
@require_POST
def unblock_user_dashboard(request, user_id):
    """Unblock a user from dashboard."""
    from django.http import JsonResponse
    from .models import BlockedUser

    user_to_unblock = get_object_or_404(User, pk=user_id)

    BlockedUser.objects.filter(
        blocker=request.user,
        blocked=user_to_unblock,
    ).delete()

    return JsonResponse({'success': True, 'message': 'تم إلغاء حظر المستخدم'})


@login_required
def message_notification_settings(request):
    """Manage message notification settings."""
    from .models import MessageNotificationSettings
    
    settings_obj, created = MessageNotificationSettings.objects.get_or_create(
        user=request.user
    )
    
    if request.method == 'POST':
        # Update notification type preferences
        settings_obj.new_message_notifications = request.POST.get('new_message_notifications') == 'on'
        settings_obj.mention_notifications = request.POST.get('mention_notifications') == 'on'
        settings_obj.reaction_notifications = request.POST.get('reaction_notifications') == 'on'
        settings_obj.reply_notifications = request.POST.get('reply_notifications') == 'on'
        settings_obj.group_mention_notifications = request.POST.get('group_mention_notifications') == 'on'
        
        # Update platform preferences
        settings_obj.in_app_notifications = request.POST.get('in_app_notifications') == 'on'
        settings_obj.browser_notifications = request.POST.get('browser_notifications') == 'on'
        settings_obj.email_notifications = request.POST.get('email_notifications') == 'on'
        settings_obj.sound_enabled = request.POST.get('sound_enabled') == 'on'
        
        # Update quiet hours
        settings_obj.quiet_hours_enabled = request.POST.get('quiet_hours_enabled') == 'on'
        settings_obj.quiet_hours_start = request.POST.get('quiet_hours_start') or None
        settings_obj.quiet_hours_end = request.POST.get('quiet_hours_end') or None
        
        settings_obj.save()
        messages.success(request, 'تم تحديث إعدادات الإشعارات بنجاح')
        return redirect('message_notification_settings')
    
    return render(request, 'properties/message_notification_settings.html', {
        'settings': settings_obj,
    })


@login_required
def security_settings(request):
    """Manage security settings."""
    from django.contrib.auth import update_session_auth_hash
    
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Change password
        if current_password and new_password:
            if request.user.check_password(current_password):
                if new_password == confirm_password:
                    request.user.set_password(new_password)
                    request.user.save()
                    update_session_auth_hash(request, request.user)
                    messages.success(request, 'تم تغيير كلمة المرور بنجاح')
                else:
                    messages.error(request, 'كلمة المرور الجديدة غير متطابقة')
            else:
                messages.error(request, 'كلمة المرور الحالية غير صحيحة')
        
        return redirect('security_settings')
    
    return render(request, 'properties/security_settings.html')


@login_required
def privacy_settings(request):
    """Manage privacy settings."""
    from .models import UserSettings
    
    settings_obj, created = UserSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Update privacy settings
        settings_obj.profile_visibility = request.POST.get('profile_visibility', 'public')
        settings_obj.show_email = request.POST.get('show_email') == 'on'
        settings_obj.show_phone = request.POST.get('show_phone') == 'on'
        settings_obj.allow_messages = request.POST.get('allow_messages') == 'on'
        settings_obj.show_activity = request.POST.get('show_activity') == 'on'
        
        settings_obj.save()
        messages.success(request, 'تم تحديث إعدادات الخصوصية بنجاح')
        return redirect('privacy_settings')
    
    return render(request, 'properties/privacy_settings.html', {
        'settings': settings_obj,
    })


@login_required
def preferences_settings(request):
    """Manage user preferences."""
    from .models import UserSettings
    
    settings_obj, created = UserSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Update preferences
        settings_obj.language = request.POST.get('language', 'ar')
        settings_obj.theme = request.POST.get('theme', 'light')
        settings_obj.timezone = request.POST.get('timezone', 'Asia/Riyadh')
        settings_obj.currency = request.POST.get('currency', 'SAR')
        
        settings_obj.save()
        messages.success(request, 'تم تحديث التفضيلات بنجاح')
        return redirect('preferences_settings')
    
    return render(request, 'properties/preferences_settings.html', {
        'settings': settings_obj,
    })


@login_required
def account_management(request):
    """Manage account information."""
    if request.method == 'POST':
        # Update account information
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        
        if request.POST.get('phone'):
            request.user.phone = request.POST.get('phone')
        
        request.user.save()
        messages.success(request, 'تم تحديث معلومات الحساب بنجاح')
        return redirect('account_management')
    
    return render(request, 'properties/account_management.html', {
        'user': request.user,
    })


@login_required
def settings_hub(request):
    """Main settings hub page."""
    return render(request, 'properties/settings_hub.html')


@login_required
def activity_page(request):
    """Display user activity."""
    from .models import PropertySave, ChatMessage, PropertyView
    
    # Get user's recent activities
    saved_properties = PropertySave.objects.filter(user=request.user).select_related('property').order_by('-created_at')[:10]
    sent_messages = ChatMessage.objects.filter(sender=request.user).order_by('-created_at')[:10]
    
    return render(request, 'properties/activity_page.html', {
        'saved_properties': saved_properties,
        'sent_messages': sent_messages,
    })


@login_required
@staff_required
def bulk_message_create(request):
    """Create and send bulk messages to users or brokers."""
    from .models import BulkMessage, Broker
    from django.utils import timezone
    
    if request.method == 'POST':
        target_type = request.POST.get('target_type', 'all_users')
        title = request.POST.get('title', '')
        message = request.POST.get('message', '')
        scheduled_at = request.POST.get('scheduled_at')
        
        if not title or not message:
            messages.error(request, 'العنوان والرسالة مطلوبان')
            return redirect('bulk_message_create')
        
        # Create bulk message
        bulk_msg = BulkMessage.objects.create(
            sender=request.user,
            target_type=target_type,
            title=title,
            message=message,
            status='pending'
        )
        
        if scheduled_at:
            from datetime import datetime
            bulk_msg.scheduled_at = datetime.fromisoformat(scheduled_at)
        
        # Get recipients based on target type
        recipients = []
        if target_type == 'all_users':
            recipients = User.objects.filter(is_active=True)
        elif target_type == 'all_brokers':
            recipients = User.objects.filter(broker__isnull=False, is_active=True)
        elif target_type == 'active_users':
            from django.utils import timezone
            thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
            recipients = User.objects.filter(is_active=True, last_login__gte=thirty_days_ago)
        elif target_type == 'active_brokers':
            from django.utils import timezone
            thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
            recipients = User.objects.filter(broker__isnull=False, is_active=True, last_login__gte=thirty_days_ago)
        elif target_type == 'specific_users':
            user_ids = request.POST.getlist('user_ids')
            recipients = User.objects.filter(id__in=user_ids, is_active=True)
        elif target_type == 'specific_brokers':
            broker_ids = request.POST.getlist('broker_ids')
            recipients = User.objects.filter(broker__id__in=broker_ids, is_active=True)
        
        bulk_msg.total_recipients = recipients.count()
        bulk_msg.save()
        
        # Send messages
        sent_count = 0
        failed_count = 0
        
        from .models import ChatMessage, Conversation, ConversationParticipant
        
        for recipient in recipients:
            try:
                # Create or get conversation
                conversation, created = Conversation.objects.get_or_create(
                    conversation_type='direct',
                    defaults={'name': f'{request.user.username} - {recipient.username}'}
                )
                
                if created:
                    # Add participants
                    ConversationParticipant.objects.create(
                        conversation=conversation,
                        user=request.user,
                        role='admin'
                    )
                    ConversationParticipant.objects.create(
                        conversation=conversation,
                        user=recipient,
                        role='member'
                    )
                
                # Create message
                ChatMessage.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    content=message,
                    message_type='text'
                )
                
                sent_count += 1
            except Exception as e:
                failed_count += 1
        
        bulk_msg.sent_count = sent_count
        bulk_msg.failed_count = failed_count
        bulk_msg.status = 'sent'
        bulk_msg.sent_at = timezone.now()
        bulk_msg.save()
        
        messages.success(request, f'تم إرسال الرسالة إلى {sent_count} مستخدم. فشل الإرسال لـ {failed_count} مستخدم.')
        return redirect('bulk_message_list')
    
    # Get users and brokers for selection
    all_users = User.objects.filter(is_active=True).order_by('username')
    all_brokers = User.objects.filter(broker__isnull=False, is_active=True).select_related('broker').order_by('username')
    
    return render(request, 'properties/bulk_message_create.html', {
        'all_users': all_users,
        'all_brokers': all_brokers,
    })


@login_required
@staff_required
def bulk_message_list(request):
    """List all bulk messages."""
    from .models import BulkMessage
    
    bulk_messages = BulkMessage.objects.all().order_by('-created_at')
    
    return render(request, 'properties/bulk_message_list.html', {
        'bulk_messages': bulk_messages,
    })


@login_required
def messaging_dashboard(request):
    """Professional messaging dashboard with dark theme."""
    from .models import Conversation, ConversationParticipant, ChatMessage
    
    user = request.user
    folder = request.GET.get('folder', 'all')
    search = request.GET.get('search', '')
    
    # Get user's conversations
    conversations = Conversation.objects.filter(
        participants=user,
        is_active=True
    ).select_related('created_by').prefetch_related('participants_info')
    
    # Filter by folder
    if folder == 'inbox':
        conversations = conversations.filter(participants_info__user=user, participants_info__folder='inbox')
    elif folder == 'sent':
        conversations = conversations.filter(participants_info__user=user, participants_info__folder='sent')
    elif folder == 'starred':
        conversations = conversations.filter(participants_info__user=user, participants_info__is_starred=True)
    elif folder == 'archived':
        conversations = conversations.filter(participants_info__user=user, participants_info__is_archived=True)
    
    # Search filter
    if search:
        conversations = conversations.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search)
        )
    
    conversations = conversations.order_by('-last_message_at', '-created_at')
    
    # Calculate counts
    all_count = Conversation.objects.filter(participants=user, is_active=True).count()
    inbox_count = ConversationParticipant.objects.filter(user=user, folder='inbox').count()
    
    return render(request, 'properties/messaging_dashboard.html', {
        'conversations': conversations,
        'folder': folder,
        'search': search,
        'all_count': all_count,
        'inbox_count': inbox_count,
    })


@login_required
def api_conversations_list(request):
    """API endpoint to list conversations."""
    from django.http import JsonResponse
    from .models import Conversation, ConversationParticipant, ChatMessage
    
    user = request.user
    folder = request.GET.get('folder', 'all')
    search = request.GET.get('search', '')
    
    conversations = Conversation.objects.filter(
        participants=user,
        is_active=True
    ).select_related('created_by').prefetch_related('participants_info', 'chat_messages')
    
    # Filter by folder
    if folder == 'inbox':
        conversations = conversations.filter(participants_info__user=user, participants_info__folder='inbox')
    elif folder == 'sent':
        conversations = conversations.filter(participants_info__user=user, participants_info__folder='sent')
    elif folder == 'starred':
        conversations = conversations.filter(participants_info__user=user, participants_info__is_starred=True)
    elif folder == 'archived':
        conversations = conversations.filter(participants_info__user=user, participants_info__is_archived=True)
    
    # Search filter
    if search:
        conversations = conversations.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search)
        )
    
    conversations = conversations.order_by('-last_message_at', '-created_at')
    
    # Serialize conversations
    conversations_data = []
    for conv in conversations:
        participant_info = conv.participants_info.filter(user=user).first()
        other_participant = conv.get_other_participant(user)
        last_message = conv.chat_messages.filter(is_deleted=False).first()
        
        conversations_data.append({
            'id': str(conv.conversation_id),
            'name': other_participant.get_full_name() if other_participant else conv.name,
            'avatar': (other_participant.get_full_name() if other_participant else conv.name)[0].upper(),
            'preview': last_message.content[:50] if last_message else 'لا توجد رسائل',
            'time': conv.last_message_at.strftime('%H:%M') if conv.last_message_at else '',
            'unread': not participant_info.last_read_at or (conv.last_message_at and conv.last_message_at > participant_info.last_read_at),
            'starred': participant_info.is_starred if participant_info else False,
            'type': 'مباشر' if conv.conversation_type == 'direct' else 'مجموعة',
        })
    
    # Calculate counts
    all_count = Conversation.objects.filter(participants=user, is_active=True).count()
    inbox_count = ConversationParticipant.objects.filter(user=user, folder='inbox').count()
    
    return JsonResponse({
        'conversations': conversations_data,
        'counts': {
            'all': all_count,
            'inbox': inbox_count,
        }
    })


@login_required
def api_conversation_detail(request, conversation_id):
    """API endpoint to get conversation details with messages."""
    from django.http import JsonResponse
    from .models import Conversation, ChatMessage, MessageReadStatus
    
    try:
        conversation = Conversation.objects.get(conversation_id=conversation_id)
    except Conversation.DoesNotExist:
        return JsonResponse({'error': 'Conversation not found'}, status=404)
    
    # Check if user is participant
    if not conversation.participants.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Not authorized'}, status=403)
    
    other_participant = conversation.get_other_participant(request.user)
    
    # Get messages
    messages = ChatMessage.objects.filter(
        conversation=conversation,
        is_deleted=False
    ).select_related('sender', 'property', 'hotel', 'resort').prefetch_related('attachments').order_by('created_at')
    
    # Serialize messages
    messages_data = []
    for msg in messages:
        message_data = {
            'id': str(msg.message_id),
            'content': msg.content,
            'sender': msg.sender.get_full_name() if msg.sender else 'Unknown',
            'sent_by_me': msg.sender == request.user,
            'time': msg.created_at.strftime('%H:%M'),
            'status': '✓✓' if msg.is_read_by_user(other_participant) else '✓',
        }
        
        # Add attachment
        if msg.attachments.exists():
            attachment = msg.attachments.first()
            message_data['attachment'] = {
                'type': attachment.attachment_type,
                'url': attachment.file.url,
                'name': attachment.file_name,
            }
        
        # Add property/hotel/resort
        if msg.property:
            message_data['property'] = {
                'name': msg.property.title,
                'image': msg.property.main_image.url if msg.property.main_image else '',
                'price': f'{msg.property.price:,} د.ع',
                'location': msg.property.city or msg.property.governorate,
                'url': f'/property/{msg.property.slug}/',
            }
        elif msg.hotel:
            message_data['property'] = {
                'name': msg.hotel.name,
                'image': msg.hotel.main_image.url if msg.hotel.main_image else '',
                'price': msg.hotel.price_range,
                'location': msg.hotel.city or msg.hotel.governorate,
                'url': f'/hotel/{msg.hotel.slug}/',
            }
        elif msg.resort:
            message_data['property'] = {
                'name': msg.resort.name,
                'image': msg.resort.main_image.url if msg.resort.main_image else '',
                'price': msg.resort.price_range,
                'location': msg.resort.city or msg.resort.governorate,
                'url': f'/resort/{msg.resort.slug}/',
            }
        
        messages_data.append(message_data)
    
    return JsonResponse({
        'id': str(conversation.conversation_id),
        'name': other_participant.get_full_name() if other_participant else conversation.name,
        'avatar': (other_participant.get_full_name() if other_participant else conversation.name)[0].upper(),
        'online': False,  # Add online status logic
        'messages': messages_data,
    })


@login_required
def api_conversation_star(request, conversation_id):
    """API endpoint to toggle star on conversation."""
    from django.http import JsonResponse
    from .models import Conversation, ConversationParticipant
    
    try:
        conversation = Conversation.objects.get(conversation_id=conversation_id)
        participant = ConversationParticipant.objects.get(
            conversation=conversation,
            user=request.user
        )
        participant.is_starred = not participant.is_starred
        participant.save()
        
        return JsonResponse({'success': True, 'starred': participant.is_starred})
    except (Conversation.DoesNotExist, ConversationParticipant.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)


@login_required
def api_conversation_archive(request, conversation_id):
    """API endpoint to archive conversation."""
    from django.http import JsonResponse
    from .models import Conversation, ConversationParticipant
    
    try:
        conversation = Conversation.objects.get(conversation_id=conversation_id)
        participant = ConversationParticipant.objects.get(
            conversation=conversation,
            user=request.user
        )
        participant.is_archived = not participant.is_archived
        participant.save()
        
        return JsonResponse({'success': True, 'archived': participant.is_archived})
    except (Conversation.DoesNotExist, ConversationParticipant.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)


@login_required
def api_send_message(request, conversation_id):
    """API endpoint to send a message."""
    from django.http import JsonResponse
    from .models import Conversation, ChatMessage
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        conversation = Conversation.objects.get(conversation_id=conversation_id)
    except Conversation.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Conversation not found'}, status=404)
    
    # Check if user is participant
    if not conversation.participants.filter(id=request.user.id).exists():
        return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)
    
    data = json.loads(request.body)
    content = data.get('content', '').strip()
    
    if not content:
        return JsonResponse({'success': False, 'error': 'Content is required'}, status=400)
    
    # Create message
    message = ChatMessage.objects.create(
        conversation=conversation,
        sender=request.user,
        message_type=ChatMessage.TYPE_TEXT,
        content=content
    )
    
    # Update conversation timestamp
    conversation.last_message_at = timezone.now()
    conversation.save()
    
    return JsonResponse({'success': True, 'message_id': str(message.message_id)})


@login_required
def api_upload_attachment(request):
    """API endpoint to upload file attachments with security validation."""
    from django.http import JsonResponse
    from .models import MessageAttachment
    import magic
    import os
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    if 'file' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'No file provided'}, status=400)
    
    file = request.FILES['file']
    
    # File size validation (max 10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    if file.size > MAX_FILE_SIZE:
        return JsonResponse({'success': False, 'error': 'File size exceeds 10MB limit'}, status=400)
    
    # File type validation using magic numbers
    ALLOWED_MIME_TYPES = {
        'image/jpeg', 'image/png', 'image/gif', 'image/webp',
        'video/mp4', 'video/webm', 'video/quicktime',
        'audio/mpeg', 'audio/wav', 'audio/ogg',
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/zip', 'application/x-zip-compressed',
        'application/x-rar-compressed',
    }
    
    # Read file to detect MIME type
    file.seek(0)
    file_content = file.read()
    file_mime = magic.from_buffer(file_content, mime=True)
    file.seek(0)
    
    if file_mime not in ALLOWED_MIME_TYPES:
        return JsonResponse({'success': False, 'error': f'File type {file_mime} not allowed'}, status=400)
    
    # Additional validation for image dimensions
    if file_mime.startswith('image/'):
        try:
            from PIL import Image
            img = Image.open(file)
            width, height = img.size
            MAX_DIMENSION = 4096
            if width > MAX_DIMENSION or height > MAX_DIMENSION:
                return JsonResponse({'success': False, 'error': f'Image dimensions exceed {MAX_DIMENSION}px limit'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': 'Invalid image file'}, status=400)
    
    # Determine attachment type
    attachment_type = 'file'
    if file_mime.startswith('image/'):
        attachment_type = 'image'
    elif file_mime.startswith('video/'):
        attachment_type = 'video'
    elif file_mime.startswith('audio/'):
        attachment_type = 'audio'
    
    # Save file
    try:
        attachment = MessageAttachment.objects.create(
            attachment_type=attachment_type,
            file=file,
            file_name=file.name,
            file_size=file.size,
            mime_type=file_mime
        )
        
        return JsonResponse({
            'success': True,
            'attachment_id': attachment.id,
            'file_url': attachment.file.url,
            'file_name': attachment.file_name,
            'file_size': attachment.file_size,
            'mime_type': attachment.mime_type
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_attach_property(request):
    """API endpoint to attach a property/hotel/resort to a message."""
    from django.http import JsonResponse
    from .models import Property, Hotel, Resort
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    data = json.loads(request.body)
    property_type = data.get('type')  # 'property', 'hotel', 'resort'
    property_id = data.get('id')
    
    if not property_type or not property_id:
        return JsonResponse({'success': False, 'error': 'Type and ID are required'}, status=400)
    
    try:
        if property_type == 'property':
            property = Property.objects.get(id=property_id)
            return JsonResponse({
                'success': True,
                'type': 'property',
                'name': property.title,
                'image': property.main_image.url if property.main_image else '',
                'price': f'{property.price:,} د.ع',
                'location': property.city or property.governorate,
                'url': f'/property/{property.slug}/',
            })
        elif property_type == 'hotel':
            hotel = Hotel.objects.get(id=property_id)
            return JsonResponse({
                'success': True,
                'type': 'hotel',
                'name': hotel.name,
                'image': hotel.main_image.url if hotel.main_image else '',
                'price': hotel.price_range,
                'location': hotel.city or hotel.governorate,
                'url': f'/hotel/{hotel.slug}/',
            })
        elif property_type == 'resort':
            resort = Resort.objects.get(id=property_id)
            return JsonResponse({
                'success': True,
                'type': 'resort',
                'name': resort.name,
                'image': resort.main_image.url if resort.main_image else '',
                'price': resort.price_range,
                'location': resort.city or resort.governorate,
                'url': f'/resort/{resort.slug}/',
            })
        else:
            return JsonResponse({'success': False, 'error': 'Invalid property type'}, status=400)
    except (Property.DoesNotExist, Hotel.DoesNotExist, Resort.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Property not found'}, status=404)


@login_required
@staff_required
def broker_statistics_view(request):
    """View broker statistics."""
    from .models import BrokerIndividualStats, BrokerSystemStats
    
    # Get system stats
    system_stats = BrokerSystemStats.objects.first()
    
    # Get individual broker stats
    broker_stats = BrokerIndividualStats.objects.select_related('broker').all().order_by('-properties_added')
    
    return render(request, 'properties/broker_statistics.html', {
        'system_stats': system_stats,
        'broker_stats': broker_stats,
    })

# User Settings Views

@login_required
def user_settings(request):
    """Main user settings page with tabs"""
    # Get or create user settings
    settings_obj, created = UserSettings.objects.get_or_create(user=request.user)
    
    # Get user's favorites
    favorite_properties = PropertySave.objects.filter(user=request.user).select_related('property')[:10]
    
    # Get blocked users
    blocked_users = BlockedUser.objects.filter(blocker=request.user).select_related('blocked')
    
    # Get saved searches
    saved_searches = SavedSearch.objects.filter(user=request.user)
    
    # Get recent viewed properties
    from django.core.cache import cache
    viewed_cache_key = f'user_{request.user.id}_viewed_properties'
    viewed_properties = cache.get(viewed_cache_key, [])
    
    context = {
        'settings': settings_obj,
        'favorite_properties': favorite_properties,
        'blocked_users': blocked_users,
        'saved_searches': saved_searches,
        'viewed_properties': viewed_properties[:10],
    }
    
    return render(request, 'properties/user_settings.html', context)


@login_required
def user_settings_profile(request):
    """Update user profile settings"""
    settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        profile_form = UserProfileForm(request.POST, instance=settings_obj)
        basic_form = UserBasicInfoForm(request.POST, instance=request.user)
        
        if profile_form.is_valid() and basic_form.is_valid():
            profile_form.save()
            basic_form.save()
            messages.success(request, 'تم تحديث الملف الشخصي بنجاح')
            return redirect('user_settings_profile')
    else:
        profile_form = UserProfileForm(instance=settings_obj)
        basic_form = UserBasicInfoForm(instance=request.user)
    
    return render(request, 'properties/user_settings_profile.html', {
        'profile_form': profile_form,
        'basic_form': basic_form,
    })


@login_required
def user_settings_security(request):
    """Update user security settings"""
    settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = UserSecurityForm(request.user, request.POST)
        
        if form.is_valid():
            new_password = form.cleaned_data.get('new_password')
            if new_password:
                request.user.set_password(new_password)
                request.user.save()
                messages.success(request, 'تم تغيير كلمة المرور بنجاح')
                return redirect('login')
            else:
                messages.info(request, 'لم يتم تغيير كلمة المرور')
    else:
        form = UserSecurityForm(request.user)
    
    return render(request, 'properties/user_settings_security.html', {
        'form': form,
        'settings': settings_obj,
    })


@login_required
def user_settings_notifications(request):
    """Update user notification settings"""
    settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = UserNotificationForm(request.POST, instance=settings_obj)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث إعدادات الإشعارات بنجاح')
            return redirect('user_settings_notifications')
    else:
        form = UserNotificationForm(instance=settings_obj)
    
    return render(request, 'properties/user_settings_notifications.html', {
        'form': form,
    })


@login_required
def user_settings_privacy(request):
    """Update user privacy settings"""
    settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = UserPrivacyForm(request.POST, instance=settings_obj)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث إعدادات الخصوصية بنجاح')
            return redirect('user_settings_privacy')
    else:
        form = UserPrivacyForm(instance=settings_obj)
    
    return render(request, 'properties/user_settings_privacy.html', {
        'form': form,
    })


@login_required
def user_settings_preferences(request):
    """Update user preferences"""
    settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = UserPreferencesForm(request.POST, instance=settings_obj)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث التفضيلات بنجاح')
            return redirect('user_settings_preferences')
    else:
        form = UserPreferencesForm(instance=settings_obj)
    
    return render(request, 'properties/user_settings_preferences.html', {
        'form': form,
    })


@login_required
def user_settings_favorites(request):
    """View user's favorites"""
    favorite_properties = PropertySave.objects.filter(user=request.user).select_related('property')
    
    return render(request, 'properties/user_settings_favorites.html', {
        'favorite_properties': favorite_properties,
    })


@login_required
def user_settings_messages(request):
    """View user's messages and blocked users"""
    messages_qs = get_accessible_messages(request.user).select_related('sender', 'recipient', 'property')
    blocked_users = BlockedUser.objects.filter(blocker=request.user).select_related('blocked')
    
    return render(request, 'properties/user_settings_messages.html', {
        'messages': messages_qs[:50],
        'blocked_users': blocked_users,
    })


@login_required
@require_POST
def block_user_settings(request):
    form = BlockUserForm(request.user, request.POST)
    
    if form.is_valid():
        blocked_user = form.cleaned_data['blocked_user']
        reason = form.cleaned_data['reason']
        
        BlockedUser.objects.create(
            blocker=request.user,
            blocked=blocked_user,
            reason=reason
        )
        
        messages.success(request, 'تم حظر المستخدم بنجاح')
    else:
        messages.error(request, 'حدث خطأ أثناء حظر المستخدم')
    
    return redirect('user_settings_messages')


@login_required
@require_POST
def unblock_user_settings(request, blocked_user_id):
    """Unblock a user from settings"""
    blocked_user = get_object_or_404(BlockedUser, blocker=request.user, blocked_id=blocked_user_id)
    blocked_user.delete()
    
    messages.success(request, 'تم إلغاء حظر المستخدم بنجاح')
    return redirect('user_settings_messages')


@login_required
def user_settings_activity(request):
    """View user's activity log"""
    from django.core.cache import cache
    
    # Get recently viewed properties
    viewed_cache_key = f'user_{request.user.id}_viewed_properties'
    viewed_properties = cache.get(viewed_cache_key, [])
    
    # Get saved searches
    saved_searches = SavedSearch.objects.filter(user=request.user)
    
    return render(request, 'properties/user_settings_activity.html', {
        'viewed_properties': viewed_properties[:20],
        'saved_searches': saved_searches,
    })


@login_required
def user_settings_account(request):
    """Account management - download data, disable, delete"""
    settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'disable':
            settings_obj.account_disabled = True
            settings_obj.disabled_at = timezone.now()
            settings_obj.disabled_reason = request.POST.get('reason', '')
            settings_obj.save()
            
            # Logout user
            logout(request)
            messages.success(request, 'تم تعطيل حسابك مؤقتاً')
            return redirect('home')
        
        elif action == 'delete':
            # Permanently delete account
            user = request.user
            logout(request)
            user.delete()
            messages.success(request, 'تم حذف حسابك نهائياً')
            return redirect('home')
        
        elif action == 'download':
            # Download user data as JSON
            import json
            from django.http import HttpResponse
            
            user_data = {
                'user': {
                    'username': request.user.username,
                    'email': request.user.email,
                    'first_name': request.user.first_name,
                    'last_name': request.user.last_name,
                    'date_joined': request.user.date_joined.isoformat(),
                },
                'settings': {
                    'phone': settings_obj.phone,
                    'governorate': settings_obj.governorate,
                    'city': settings_obj.city,
                }
            }
            
            response = HttpResponse(json.dumps(user_data, indent=2, ensure_ascii=False), content_type='application/json')
            response['Content-Disposition'] = f'attachment; filename="{request.user.username}_data.json"'
            return response
    
    return render(request, 'properties/user_settings_account.html', {'settings': settings_obj})


# ==================== Admin Panel Views ====================

@login_required
def admin_panel(request):
    """Redirect to unified dashboard — admin section."""
    from .permissions import can_access_admin_panel

    if not can_access_admin_panel(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى لوحة الإدارة')
        return redirect('home')

    # Redirect to dashboard with users tab active
    return redirect(f"{reverse('dashboard')}?tab=users")


@login_required
def admin_users_list(request):
    """قائمة المستخدمين"""
    from .permissions import can_access_admin_panel

    if not can_access_admin_panel(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى لوحة الإدارة')
        return redirect('home')

    from django.contrib.auth.models import User
    from .models import Broker, UserProfile

    # Get all users with their types
    users = User.objects.all().select_related('broker_profile', 'user_profile').order_by('-date_joined')

    # Add user type to each user
    for user in users:
        if user.is_superuser:
            user.user_type = 'admin'
        elif hasattr(user, 'broker_profile') and user.broker_profile:
            user.user_type = 'broker'
        elif hasattr(user, 'user_profile') and user.user_profile:
            user.user_type = 'user'
        else:
            user.user_type = 'unknown'

    context = {
        'users': users,
    }

    return render(request, 'properties/admin_users_list.html', context)


@login_required
def admin_create_user(request):
    """إنشاء مستخدم جديد"""
    from .permissions import can_access_admin_panel

    if not can_access_admin_panel(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى لوحة الإدارة')
        return redirect('home')

    from django.contrib.auth.models import User
    from .models import Broker, UserProfile

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        user_type = request.POST.get('user_type', 'user')  # admin, broker, user

        # Validation
        if not username or not email or not password:
            messages.error(request, 'يرجى ملء جميع الحقول المطلوبة')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'اسم المستخدم مستخدم بالفعل')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'البريد الإلكتروني مستخدم بالفعل')
        else:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
            )

            # Set user type
            if user_type == 'admin':
                user.is_superuser = True
                user.is_staff = True
                user.save()

                # Create broker profile with admin role
                Broker.objects.create(
                    user=user,
                    phone=phone,
                    role=Broker.ROLE_ADMIN,
                    is_active=True,
                )
            elif user_type == 'broker':
                user.is_staff = True
                user.save()

                # Create broker profile
                Broker.objects.create(
                    user=user,
                    phone=phone,
                    role=Broker.ROLE_MAIN,
                    is_active=True,
                )
            else:  # regular user
                user.is_staff = False
                user.save()

                # Create user profile
                UserProfile.objects.create(
                    user=user,
                    phone=phone,
                    is_active=True,
                )

            messages.success(request, 'تم إنشاء المستخدم بنجاح')
            return redirect('admin_users_list')

    return render(request, 'properties/admin_create_user.html')


@login_required
def admin_edit_user(request, user_id):
    """تعديل مستخدم"""
    from .permissions import can_access_admin_panel

    if not can_access_admin_panel(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى لوحة الإدارة')
        return redirect('home')

    from django.contrib.auth.models import User
    from .models import Broker, UserProfile

    user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.email = request.POST.get('email', '').strip()
        user.save()

        # Update profile based on type
        if hasattr(user, 'broker_profile'):
            broker = user.broker_profile
            broker.phone = request.POST.get('phone', '').strip()
            broker.is_active = request.POST.get('is_active') == 'on'
            broker.save()
        elif hasattr(user, 'user_profile'):
            profile = user.user_profile
            profile.phone = request.POST.get('phone', '').strip()
            profile.is_active = request.POST.get('is_active') == 'on'
            profile.save()

        messages.success(request, 'تم تحديث المستخدم بنجاح')
        return redirect('admin_users_list')

    context = {
        'user': user,
    }

    return render(request, 'properties/admin_edit_user.html', context)


@login_required
def admin_delete_user(request, user_id):
    """حذف مستخدم"""
    from .permissions import can_access_admin_panel

    if not can_access_admin_panel(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى لوحة الإدارة')
        return redirect('home')

    from django.contrib.auth.models import User

    user = get_object_or_404(User, pk=user_id)

    # Prevent deleting self
    if user == request.user:
        messages.error(request, 'لا يمكنك حذف حسابك')
        return redirect('admin_users_list')

    if request.method == 'POST':
        user.delete()
        messages.success(request, 'تم حذف المستخدم بنجاح')
        return redirect('admin_users_list')

    context = {
        'user': user,
    }

    return render(request, 'properties/admin_delete_user.html', context)


@login_required
def admin_toggle_user(request, user_id):
    """تفعيل أو إيقاف مستخدم"""
    from .permissions import can_access_admin_panel

    if not can_access_admin_panel(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى لوحة الإدارة')
        return redirect('home')

    from django.contrib.auth.models import User
    from .models import Broker, UserProfile

    user = get_object_or_404(User, pk=user_id)

    # Prevent deactivating self
    if user == request.user:
        messages.error(request, 'لا يمكنك إيقاف حسابك')
        return redirect('admin_users_list')

    # Toggle user active status
    user.is_active = not user.is_active
    user.save()

    # Toggle profile active status
    if hasattr(user, 'broker_profile'):
        broker = user.broker_profile
        broker.is_active = user.is_active
        broker.save()
    elif hasattr(user, 'user_profile'):
        profile = user.user_profile
        profile.is_active = user.is_active
        profile.save()

    status = 'تفعيل' if user.is_active else 'إيقاف'
    messages.success(request, f'تم {status} المستخدم بنجاح')
    return redirect('admin_users_list')


@login_required
def admin_reset_password(request, user_id):
    """إعادة تعيين كلمة المرور"""
    from .permissions import can_access_admin_panel

    if not can_access_admin_panel(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى لوحة الإدارة')
        return redirect('home')

    from django.contrib.auth.models import User

    user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not new_password or len(new_password) < 6:
            messages.error(request, 'كلمة المرور يجب أن تكون 6 أحرف على الأقل')
        elif new_password != confirm_password:
            messages.error(request, 'كلمات المرور غير متطابقة')
        else:
            user.set_password(new_password)
            user.save()
            messages.success(request, 'تم إعادة تعيين كلمة المرور بنجاح')
            return redirect('admin_users_list')

    context = {
        'user': user,
    }

    return render(request, 'properties/admin_reset_password.html', context)


@login_required
def admin_change_user_type(request, user_id):
    """تغيير نوع المستخدم"""
    from .permissions import can_access_admin_panel

    if not can_access_admin_panel(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى لوحة الإدارة')
        return redirect('home')

    from django.contrib.auth.models import User
    from .models import Broker, UserProfile

    user = get_object_or_404(User, pk=user_id)

    # Prevent changing own type
    if user == request.user:
        messages.error(request, 'لا يمكنك تغيير نوع حسابك')
        return redirect('admin_users_list')

    if request.method == 'POST':
        new_type = request.POST.get('user_type', 'user')
        phone = request.POST.get('phone', '').strip()

        # Delete existing profiles
        if hasattr(user, 'broker_profile'):
            user.broker_profile.delete()
        if hasattr(user, 'user_profile'):
            user.user_profile.delete()

        # Create new profile based on type
        if new_type == 'admin':
            user.is_superuser = True
            user.is_staff = True
            user.save()

            Broker.objects.create(
                user=user,
                phone=phone,
                role=Broker.ROLE_ADMIN,
                is_active=True,
            )
        elif new_type == 'broker':
            user.is_superuser = False
            user.is_staff = True
            user.save()

            Broker.objects.create(
                user=user,
                phone=phone,
                role=Broker.ROLE_MAIN,
                is_active=True,
            )
        else:  # regular user
            user.is_superuser = False
            user.is_staff = False
            user.save()

            UserProfile.objects.create(
                user=user,
                phone=phone,
                is_active=True,
            )

        messages.success(request, 'تم تغيير نوع المستخدم بنجاح')
        return redirect('admin_users_list')

    context = {
        'user': user,
    }

    return render(request, 'properties/admin_change_user_type.html', context)


@login_required
def chat_view(request):
    """Main chat view - real-time messaging interface"""
    return render(request, 'properties/chat.html')


def channels_list_view(request):
    """View for displaying all broker channels"""
    channels = BrokerChannel.objects.filter(
        is_active=True,
        is_archived=False
    ).select_related('broker').prefetch_related('followers')
    
    # Get user's follows and saves
    user_follows = set()
    user_saves = set()
    if request.user.is_authenticated:
        user_follows = set(ChannelFollow.objects.filter(
            user=request.user
        ).values_list('channel_id', flat=True))
        user_saves = set(ChannelSave.objects.filter(
            user=request.user
        ).values_list('channel_id', flat=True))
    
    # Pagination
    paginator = Paginator(channels, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'channels': page_obj,
        'user_follows': user_follows,
        'user_saves': user_saves,
        'page_title': 'قنوات الدلالين',
    }
    
    return render(request, 'properties/channels.html', context)


def channel_detail_view(request, slug):
    """View for displaying a single broker channel"""
    channel = get_object_or_404(BrokerChannel, slug=slug, is_active=True, is_archived=False)
    
    # Get tab filter
    tab = request.GET.get('tab', 'all')
    
    # Get listings based on tab
    listings = []
    if tab == 'all':
        listings = channel.get_all_listings()
    elif tab == 'iraq':
        listings = list(channel.get_properties_iraq())
    elif tab == 'outside':
        listings = list(channel.get_properties_outside())
    elif tab == 'hotels':
        listings = list(channel.get_hotels())
    elif tab == 'resorts':
        listings = list(channel.get_resorts())
    elif tab == 'featured':
        listings = channel.get_featured_listings()
    elif tab == 'most_viewed':
        listings = channel.get_most_viewed()
    elif tab == 'latest':
        listings = channel.get_all_listings()
    
    # Increment views
    channel.views_count += 1
    channel.save(update_fields=['views_count'])
    
    # Get user's follows and saves
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
    
    # Pagination
    paginator = Paginator(listings, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'channel': channel,
        'listings': page_obj,
        'page_obj': page_obj,
        'tab': tab,
        'is_following': is_following,
        'is_saved': is_saved,
        'page_title': channel.name,
    }
    
    return render(request, 'properties/channel_detail.html', context)


@login_required
@require_POST
def follow_channel_view(request, channel_id):
    """Follow or unfollow a channel"""
    channel = get_object_or_404(BrokerChannel, id=channel_id, is_active=True)
    
    follow, created = ChannelFollow.objects.get_or_create(
        user=request.user,
        channel=channel
    )
    
    if not created:
        # Unfollow
        follow.delete()
        channel.followers_count = max(0, channel.followers_count - 1)
        action = 'unfollowed'
    else:
        # Follow
        channel.followers_count += 1
        action = 'followed'
    
    channel.save(update_fields=['followers_count'])
    
    return JsonResponse({
        'success': True,
        'action': action,
        'followers_count': channel.followers_count
    })


@login_required
@require_POST
def save_channel_view(request, channel_id):
    """Save or unsave a channel"""
    channel = get_object_or_404(BrokerChannel, id=channel_id, is_active=True)
    
    save, created = ChannelSave.objects.get_or_create(
        user=request.user,
        channel=channel
    )
    
    if not created:
        # Unsave
        save.delete()
        action = 'unsaved'
    else:
        # Save
        action = 'saved'
    
    return JsonResponse({
        'success': True,
        'action': action
    })

