import logging
import json

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
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
from .forms import MessageForm, PropertyForm, PropertySearchForm, SiteSettingsForm, PropertyNoteForm, VirtualTour360Form, AuctionForm, BidForm, BuildingRequestForm, LandInfoForm, BuildingDetailsForm, BudgetForm, QuoteForm, ContractorBidForm, ContractorRatingForm, ReportForm, FinancialTransactionForm, ExpenseForm, ProfitForm, SubscriptionPlanForm, UserProfileForm, UserBasicInfoForm, UserSecurityForm, UserNotificationForm, UserPrivacyForm, UserPreferencesForm, BlockUserForm, SavedSearchForm, AutoBidForm, AuctionRatingForm, AuctionLiveStreamForm, AuctionAdvertisementForm, HotelSearchForm, ResortSearchForm, PropertyPublicationForm, PropertyPaymentForm, ServiceProviderForm, ServiceAdvertisementForm
from .models import Message, Property, PropertyImage, SiteSettings, PropertyNote, Notification, VirtualTour360, Auction, Bid, BuildingRequest, LandInfo, BuildingDetails, Budget, Blueprint, Quote, ProjectTracking, DeliveryMilestone, ContractorRating, ContractorBid, FinancialTransaction, Expense, Payment, OfficeWallet, WalletTransaction, Broker, Report, ReportAction, PropertyLike, PropertySave, PropertyComment, VirtualTourPoint, VirtualTourConnection, Profit, SubscriptionPlan, ActivityLog, UserSettings, BlockedUser, SavedSearch, AutoBid, AuctionNotification, AuctionRating, AuctionStats, AuctionLiveStream, AuctionAdvertisement, Hotel, Resort, BrokerChannel, ChannelFollow, ChannelSave, PaymentMethod, PropertyPayment, PropertyNotification, ChannelPost, ChannelVideo, AdvancedSubscriptionPlan, BrokerPlanSubscription, SubscriptionRenewalRequest, ServiceProvider, ServiceAdvertisement, AuctionInvitation
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


def broker_standalone_page(request, slug):
    """Display broker's standalone page with their properties only."""
    broker = get_object_or_404(Broker, slug=slug, has_standalone_page=True)
    
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
    
    return render(request, 'properties/broker_standalone_page.html', {
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


@login_required
@broker_required
def broker_standalone_settings(request):
    """Handle broker standalone page settings."""
    broker = get_broker(request.user)
    
    if request.method == 'POST':
        # Toggle standalone page
        has_standalone_page = request.POST.get('has_standalone_page') == 'on'
        broker.has_standalone_page = has_standalone_page
        
        # Update slug if provided
        slug = request.POST.get('slug', '').strip()
        if slug:
            # Check if slug is unique
            if Broker.objects.filter(slug=slug).exclude(id=broker.id).exists():
                messages.error(request, 'هذا الرابط مستخدم بالفعل، اختر رابطاً آخر')
                return redirect('broker_panel')
            broker.slug = slug
        
        # Update cover image if provided
        if 'cover_image' in request.FILES:
            broker.cover_image = request.FILES['cover_image']
        
        # Update bio
        bio = request.POST.get('bio', '').strip()
        broker.bio = bio
        
        broker.save()
        
        if has_standalone_page:
            messages.success(request, 'تم تفعيل الصفحة المستقلة بنجاح')
        else:
            messages.success(request, 'تم إلغاء الصفحة المستقلة')
        
        return redirect('broker_panel')
    
    return redirect('broker_panel')


def login_view(request):
    from .permissions import get_redirect_after_login, get_user_type, can_access_dashboard, get_broker

    if request.user.is_authenticated:
        redirect_url = get_redirect_after_login(request.user)
        return redirect(redirect_url)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        if not username or not password:
            messages.error(request, 'يرجى إدخال اسم المستخدم وكلمة المرور')
        else:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                # Check if user is active
                if not user.is_active:
                    messages.error(request, 'تم تعطيل حسابك. يرجى التواصل مع الإدارة')
                    logger.warning('Login attempt for inactive user: %s', username)
                    return render(request, 'properties/login.html')
                
                login(request, user)
                user_type = get_user_type(user)
                
                # Log successful login
                from .models import ActivityLog
                ActivityLog.log(
                    user=user,
                    action='login',
                    model_type='user',
                    object_id=user.id,
                    object_repr=user.username,
                    description=f'تسجيل دخول ناجح: {user.username}',
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    metadata={'user_type': user_type}
                )
                
                # Redirect based on user type
                if user_type == 'admin':
                    messages.success(request, 'مرحباً بك في لوحة الإدارة')
                    return redirect('admin_panel')
                elif user_type == 'broker':
                    broker = get_broker(user)
                    if broker and not broker.is_active:
                        messages.error(request, 'تم تعطيل حساب الدلال. يرجى التواصل مع الإدارة')
                        logout(request)
                        return render(request, 'properties/login.html')
                    messages.success(request, 'مرحباً بك في لوحة الدلال')
                    return redirect('dashboard')
                else:
                    messages.success(request, 'تم تسجيل الدخول بنجاح')
                    return redirect('home')
            else:
                messages.error(request, 'بيانات الدخول غير صحيحة')
                logger.warning('Failed login attempt for user: %s', username)
    
    return render(request, 'properties/login.html')


def register_view(request):
    """Register a new user account (regular users only)."""
    from django.contrib.auth.models import User
    
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        gender = request.POST.get('gender', '').strip()
        birth_date = request.POST.get('birth_date', '').strip()
        city = request.POST.get('city', '').strip()
        governorate = request.POST.get('governorate', '').strip()
        address = request.POST.get('address', '').strip()
        profile_image = request.FILES.get('profile_image')
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        # Validation
        if not username or not email or not password or not phone:
            messages.error(request, 'يرجى ملء جميع الحقول المطلوبة')
        elif len(username) < 3:
            messages.error(request, 'اسم المستخدم يجب أن يكون 3 أحرف على الأقل')
        elif password != confirm_password:
            messages.error(request, 'كلمات المرور غير متطابقة')
        elif len(password) < 8:
            messages.error(request, 'كلمة المرور يجب أن تكون 8 أحرف على الأقل')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'اسم المستخدم مستخدم بالفعل')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'البريد الإلكتروني مستخدم بالفعل')
        else:
            # Check for duplicate phone in Broker profiles
            from .models import Broker, UserProfile
            if Broker.objects.filter(phone=phone).exists():
                messages.error(request, 'رقم الهاتف مستخدم بالفعل')
            else:
                # Create regular user (no broker profile)
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password=password,
                    is_staff=False  # Regular users are not staff
                )
                
                # Create or update UserProfile with additional information
                user_profile, created = UserProfile.objects.get_or_create(user=user)
                user_profile.phone = phone
                if gender:
                    user_profile.gender = gender
                if birth_date:
                    user_profile.birth_date = birth_date
                if city:
                    user_profile.city = city
                if governorate:
                    user_profile.governorate = governorate
                if address:
                    user_profile.address = address
                if profile_image:
                    user_profile.profile_image = profile_image
                user_profile.save()

                # Create notification for admins
                from .utils import create_notification
                admins = User.objects.filter(is_superuser=True)
                
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


def password_reset_request(request):
    """Handle password reset request."""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        if not email:
            messages.error(request, 'يرجى إدخال البريد الإلكتروني')
        else:
            from django.contrib.auth.models import User
            try:
                user = User.objects.get(email=email)
                # In a real application, send email with reset link
                # For now, just show success message
                messages.success(request, 'تم إرسال رابط إعادة تعيين كلمة المرور إلى بريدك الإلكتروني')
                logger.info('Password reset requested for user: %s', user.username)
                return redirect('login')
            except User.DoesNotExist:
                messages.error(request, 'البريد الإلكتروني غير مسجل في النظام')
    
    return render(request, 'properties/password_reset.html')


@login_required
def password_change(request):
    """Handle password change for logged in users."""
    if request.method == 'POST':
        old_password = request.POST.get('old_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        if not old_password or not new_password:
            messages.error(request, 'يرجى ملء جميع الحقول')
        elif not request.user.check_password(old_password):
            messages.error(request, 'كلمة المرور الحالية غير صحيحة')
        elif new_password != confirm_password:
            messages.error(request, 'كلمات المرور غير متطابقة')
        elif len(new_password) < 8:
            messages.error(request, 'كلمة المرور الجديدة يجب أن تكون 8 أحرف على الأقل')
        else:
            request.user.set_password(new_password)
            request.user.save()
            
            # Log password change
            from .models import ActivityLog
            ActivityLog.log(
                user=request.user,
                action='update',
                model_type='user',
                object_id=request.user.id,
                object_repr=request.user.username,
                description=f'تغيير كلمة المرور: {request.user.username}',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                metadata={'action': 'password_change'}
            )
            
            messages.success(request, 'تم تغيير كلمة المرور بنجاح')
            return redirect('login')
    
    return render(request, 'properties/password_change.html')


@login_required
def user_dashboard(request):
    """لوحة تحكم المستخدمين العاديين"""
    # Get user's saved properties
    saved_properties = []
    try:
        from .models import SavedProperty
        saved_properties = SavedProperty.objects.filter(user=request.user).select_related('property', 'property__owner', 'property__broker')
    except Exception:
        saved_properties = []

    # Get user's notifications
    notifications = []
    unread_notifications_count = 0
    try:
        notifications = Notification.objects.filter(user=request.user)[:20]
        unread_notifications_count = Notification.objects.filter(user=request.user, is_read=False).count()
    except Exception:
        notifications = []
        unread_notifications_count = 0

    # Get auctions user has joined
    user_auctions = []
    try:
        from .models import AuctionParticipant
        user_auctions = AuctionParticipant.objects.filter(user=request.user, verified=True).select_related('auction', 'auction__property')
    except Exception:
        user_auctions = []

    # Get user's activity logs
    activity_logs = []
    try:
        activity_logs = ActivityLog.objects.filter(user=request.user).order_by('-created_at')[:20]
    except Exception:
        activity_logs = []

    return render(request, 'properties/user_dashboard.html', {
        'saved_properties': saved_properties,
        'notifications': notifications,
        'unread_notifications_count': unread_notifications_count,
        'user_auctions': user_auctions,
        'activity_logs': activity_logs,
    })


@login_required
def dashboard(request):
    """لوحة تحكم الإدارة والدلال"""
    # Check if user is admin or broker
    if not request.user.is_superuser and not request.user.is_staff and not get_broker(request.user):
        return redirect('user_dashboard')
    
    properties = get_accessible_properties(request.user).prefetch_related('gallery_images', 'broker', 'owner')
    
    # Add pagination for properties
    paginator = Paginator(properties, 25)
    page_number = request.GET.get('page', 1)
    properties = paginator.get_page(page_number)
    
    # Get unread messages with optimized query
    unread = get_accessible_messages(request.user).filter(is_read=False)[:20]
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
    
    # Get subscription info for timer
    subscription_info = None
    try:
        from .models import BrokerPlanSubscription
        subscription = BrokerPlanSubscription.objects.filter(
            broker=broker,
            status='active'
        ).first()
        if subscription:
            subscription_info = {
                'seconds_remaining': subscription.get_seconds_remaining(),
                'end_date': subscription.end_date,
                'properties_used': subscription.properties_used,
                'max_properties': subscription.plan.max_properties,
                'plan_name': subscription.plan.name
            }
    except Exception:
        subscription_info = None
    
    stats['subscription'] = subscription_info

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
                subscription_requests = SubscriptionRequest.objects.all().select_related('broker', 'requested_plan', 'approved_by').order_by('-created_at')[:50]
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
    
    messages.success(request, f'تم توثيق قناة {channel.name}')
    return redirect('admin_channels_list')


@login_required
@staff_required
def admin_channel_delete(request, channel_id):
    """Delete a broker channel."""
    from .models import BrokerChannel
    
    if not request.user.is_superuser:
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    
    channel = get_object_or_404(BrokerChannel, id=channel_id)
    channel_name = channel.name
    channel.delete()
    
    messages.success(request, f'تم حذف قناة {channel_name}')
    return redirect('admin_channels_list')


@login_required
@staff_required
def admin_channel_activate(request, channel_id):
    """Activate a suspended broker channel."""
    from .models import BrokerChannel
    
    if not request.user.is_superuser:
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    
    channel = get_object_or_404(BrokerChannel, id=channel_id)
    channel.status = 'active'
    channel.save()
    
    messages.success(request, f'تم تفعيل قناة {channel.name}')
    return redirect('admin_channels_list')


@login_required
@staff_required
def admin_channel_properties(request, channel_id):
    """View and manage properties in a broker channel."""
    from .models import BrokerChannel, Property
    
    if not request.user.is_superuser:
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    
    channel = get_object_or_404(BrokerChannel, id=channel_id)
    properties = Property.objects.filter(broker=channel.broker).select_related('owner', 'broker')
    
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        properties = properties.filter(status=status_filter)
    
    properties = properties.order_by('-created_at')
    
    return render(request, 'properties/admin_channel_properties.html', {
        'channel': channel,
        'properties': properties,
        'status_filter': status_filter,
    })


@login_required
@staff_required
def admin_channel_property_delete(request, channel_id, property_id):
    """Delete a property from a broker channel."""
    from .models import BrokerChannel, Property
    
    if not request.user.is_superuser:
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    
    channel = get_object_or_404(BrokerChannel, id=channel_id)
    property = get_object_or_404(Property, id=property_id, broker=channel.broker)
    
    property_title = property.title
    property.delete()
    
    # Update channel stats
    channel.update_stats()
    
    messages.success(request, f'تم حذف عقار {property_title}')
    return redirect('admin_channel_properties', channel_id=channel.id)


@login_required
def my_channel_view(request):
    """View for broker's own channel management."""
    from .models import BrokerChannel, Broker, ChannelPost, ChannelVideo, ChannelFollow, Message
    
    broker = get_broker(request.user)
    
    if not broker:
        messages.error(request, 'ليس لديك قناة')
        return redirect('dashboard')
    
    # Get or create channel
    channel, created = BrokerChannel.objects.get_or_create(
        broker=broker,
        defaults={
            'name': f'قناة {broker.display_name}',
            'description': f'قناة الدلال {broker.display_name}',
            'status': 'pending'
        }
    )
    
    # Get channel properties
    properties = Property.objects.filter(broker=broker).select_related('owner', 'broker')
    
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        properties = properties.filter(status=status_filter)
    
    properties = properties.order_by('-created_at')
    
    # Get channel posts and videos
    posts = ChannelPost.objects.filter(channel=channel).order_by('-is_pinned', '-created_at')
    videos = ChannelVideo.objects.filter(channel=channel).order_by('-is_featured', '-created_at')
    
    # Get last activity items
    last_property = properties.first() if properties.exists() else None
    last_post = posts.first() if posts.exists() else None
    
    # Get last message (if Message model exists)
    try:
        last_message = Message.objects.filter(channel=channel).order_by('-created_at').first()
    except:
        last_message = None
    
    # Get last follower
    try:
        last_follower = ChannelFollow.objects.filter(channel=channel).order_by('-created_at').first()
    except:
        last_follower = None
    
    return render(request, 'properties/my_channel.html', {
        'channel': channel,
        'properties': properties,
        'posts': posts,
        'videos': videos,
        'status_filter': status_filter,
        'broker': broker,
        'last_property': last_property,
        'last_post': last_post,
        'last_message': last_message,
        'last_follower': last_follower,
    })


@login_required
def create_channel_post(request):
    """Create a new post in the channel."""
    from .models import BrokerChannel, Broker, ChannelPost, Property
    
    broker = get_broker(request.user)
    
    if not broker:
        messages.error(request, 'ليس لديك قناة')
        return redirect('dashboard')
    
    channel = get_object_or_404(BrokerChannel, broker=broker)
    
    if request.method == 'POST':
        post_type = request.POST.get('post_type', 'text')
        content = request.POST.get('content', '')
        property_id = request.POST.get('property_id')
        image = request.FILES.get('image')
        video = request.FILES.get('video')
        is_pinned = request.POST.get('is_pinned') == 'on'
        is_advertisement = request.POST.get('is_advertisement') == 'on'
        
        post = ChannelPost.objects.create(
            channel=channel,
            post_type=post_type,
            content=content,
            image=image,
            video=video,
            is_pinned=is_pinned,
            is_advertisement=is_advertisement
        )
        
        if property_id:
            try:
                property = Property.objects.get(id=property_id, broker=broker)
                post.property = property
                post.save()
            except Property.DoesNotExist:
                pass
        
        # Notify followers
        from .utils import create_notification
        followers = channel.followers.all()
        for follower in followers:
            create_notification(
                user=follower.user,
                notification_type='channel_post',
                title='منشور جديد في قناة متابعتك',
                message=f'نشر {broker.display_name} منشوراً جديداً',
                link=f'/channel/{channel.id}/'
            )
        
        messages.success(request, 'تم نشر المنشور بنجاح')
        return redirect('my_channel')
    
    # Get broker's properties for selection
    broker_properties = Property.objects.filter(broker=broker, status='ready')
    
    return render(request, 'properties/create_channel_post.html', {
        'channel': channel,
        'broker_properties': broker_properties,
    })


@login_required
def create_channel_video(request):
    """Create a new short video in the channel."""
    from .models import BrokerChannel, Broker, ChannelVideo
    
    broker = get_broker(request.user)
    
    if not broker:
        messages.error(request, 'ليس لديك قناة')
        return redirect('dashboard')
    
    channel = get_object_or_404(BrokerChannel, broker=broker)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        video_file = request.FILES.get('video_file')
        thumbnail = request.FILES.get('thumbnail')
        duration = request.POST.get('duration', 0)
        is_featured = request.POST.get('is_featured') == 'on'
        tags = request.POST.get('tags', '')
        
        video = ChannelVideo.objects.create(
            channel=channel,
            title=title,
            description=description,
            video_file=video_file,
            thumbnail=thumbnail,
            duration=int(duration),
            is_featured=is_featured,
            tags=tags
        )
        
        # Notify followers
        from .utils import create_notification
        followers = channel.followers.all()
        for follower in followers:
            create_notification(
                user=follower.user,
                notification_type='channel_video',
                title='فيديو جديد في قناة متابعتك',
                message=f'رفع {broker.display_name} فيديو جديداً',
                link=f'/channel/{channel.id}/videos/'
            )
        
        messages.success(request, 'تم رفع الفيديو بنجاح')
        return redirect('my_channel')
    
    return render(request, 'properties/create_channel_video.html', {
        'channel': channel,
    })


@login_required
def toggle_post_like(request, post_id):
    """Toggle like on a channel post."""
    from .models import ChannelPost, ChannelPostLike
    
    post = get_object_or_404(ChannelPost, id=post_id)
    like, created = ChannelPostLike.objects.get_or_create(
        user=request.user,
        post=post
    )
    
    if not created:
        like.delete()
        post.likes_count -= 1
        post.save(update_fields=['likes_count'])
        return JsonResponse({'liked': False, 'likes_count': post.likes_count})
    else:
        post.likes_count += 1
        post.save(update_fields=['likes_count'])
        
        # Notify post author
        if post.channel.broker.user != request.user:
            from .utils import create_notification
            create_notification(
                user=post.channel.broker.user,
                notification_type='post_like',
                title='إعجاب جديد على منشورك',
                message=f'أعجب {request.user.get_full_name() or request.user.username} بمنشورك',
                link=f'/channel/{post.channel.id}/'
            )
        
        return JsonResponse({'liked': True, 'likes_count': post.likes_count})


@login_required
def toggle_video_like(request, video_id):
    """Toggle like on a channel video."""
    from .models import ChannelVideo, ChannelVideoLike
    
    video = get_object_or_404(ChannelVideo, id=video_id)
    like, created = ChannelVideoLike.objects.get_or_create(
        user=request.user,
        video=video
    )
    
    if not created:
        like.delete()
        video.likes_count -= 1
        video.save(update_fields=['likes_count'])
        return JsonResponse({'liked': False, 'likes_count': video.likes_count})
    else:
        video.likes_count += 1
        video.save(update_fields=['likes_count'])
        
        # Notify video author
        if video.channel.broker.user != request.user:
            from .utils import create_notification
            create_notification(
                user=video.channel.broker.user,
                notification_type='video_like',
                title='إعجاب جديد على فيديوك',
                message=f'أعجب {request.user.get_full_name() or request.user.username} بفيديوك',
                link=f'/channel/{video.channel.id}/videos/'
            )
        
        return JsonResponse({'liked': True, 'likes_count': video.likes_count})


@login_required
def channel_public_view(request, channel_id):
    """Public view of a broker's channel for users."""
    from .models import BrokerChannel, ChannelPost, ChannelVideo, Property, Auction, Hotel, Resort, ChannelReview, ChannelFollow
    
    channel = get_object_or_404(BrokerChannel, id=channel_id, status='active')
    
    # Check if user is following
    is_following = False
    if request.user.is_authenticated:
        is_following = ChannelFollow.objects.filter(
            user=request.user,
            channel=channel
        ).exists()
    
    # Get filter parameters
    tab = request.GET.get('tab', 'home')
    property_type = request.GET.get('type', 'all')
    sort_by = request.GET.get('sort', 'newest')
    search_query = request.GET.get('q', '')
    
    # Get properties
    properties = Property.objects.filter(broker=channel.broker)
    
    # Apply filters
    if property_type == 'sale':
        properties = properties.filter(status='ready')
    elif property_type == 'rent':
        properties = properties.filter(status='rent')
    elif property_type == 'auction':
        properties = properties.filter(status='auction')
    
    # Apply search
    if search_query:
        properties = properties.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(location__icontains=search_query)
        )
    
    # Apply sorting
    if sort_by == 'newest':
        properties = properties.order_by('-created_at')
    elif sort_by == 'price_high':
        properties = properties.order_by('-price')
    elif sort_by == 'price_low':
        properties = properties.order_by('price')
    elif sort_by == 'most_viewed':
        properties = properties.order_by('-views_count')
    
    # Get posts and videos
    posts = ChannelPost.objects.filter(channel=channel, is_published=True).order_by('-is_pinned', '-created_at')
    videos = ChannelVideo.objects.filter(channel=channel, is_published=True).order_by('-is_featured', '-created_at')
    
    # Get auctions
    auctions = Auction.objects.filter(broker=channel.broker, approval_status='approved').order_by('-created_at')
    
    # Get hotels and resorts
    hotels = Hotel.objects.filter(broker=channel.broker, is_published=True).order_by('-created_at')
    resorts = Resort.objects.filter(broker=channel.broker, is_published=True).order_by('-created_at')
    
    # Get reviews
    reviews = ChannelReview.objects.filter(channel=channel).order_by('-created_at')
    
    # Calculate real stats
    properties_count = Property.objects.filter(broker=channel.broker).count()
    posts_count = ChannelPost.objects.filter(channel=channel, is_published=True).count()
    auctions_count = Auction.objects.filter(broker=channel.broker, approval_status='approved').count()
    hotels_count = Hotel.objects.filter(broker=channel.broker, is_published=True).count()
    resorts_count = Resort.objects.filter(broker=channel.broker, is_published=True).count()
    
    # Update channel stats
    channel.properties_count = properties_count
    channel.save(update_fields=['properties_count'])
    
    # Increment channel views
    channel.increment_views()
    
    context = {
        'channel': channel,
        'posts': posts,
        'videos': videos,
        'properties': properties,
        'auctions': auctions,
        'hotels': hotels,
        'resorts': resorts,
        'reviews': reviews,
        'is_following': is_following,
        'tab': tab,
        'property_type': property_type,
        'sort_by': sort_by,
        'search_query': search_query,
        'properties_count': properties_count,
        'posts_count': posts_count,
        'auctions_count': auctions_count,
        'hotels_count': hotels_count,
        'resorts_count': resorts_count,
    }
    
    return render(request, 'properties/channel_public.html', context)


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
def social_auth_diagnostics(request):
    """OAuth Diagnostics page for admin."""
    from django.conf import settings
    import os
    
    # Check environment variables
    diagnostics = {
        'google': {
            'client_id': bool(settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY),
            'client_secret': bool(settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET),
            'redirect_uri': settings.SOCIAL_AUTH_GOOGLE_OAUTH2_REDIRECT_URI,
            'status': 'configured' if settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY and settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET else 'missing_keys'
        },
        'facebook': {
            'client_id': bool(settings.SOCIAL_AUTH_FACEBOOK_OAUTH2_KEY),
            'client_secret': bool(settings.SOCIAL_AUTH_FACEBOOK_OAUTH2_SECRET),
            'redirect_uri': settings.SOCIAL_AUTH_FACEBOOK_OAUTH2_REDIRECT_URI,
            'status': 'configured' if settings.SOCIAL_AUTH_FACEBOOK_OAUTH2_KEY and settings.SOCIAL_AUTH_FACEBOOK_OAUTH2_SECRET else 'missing_keys'
        },
        'environment': {
            'debug': settings.DEBUG,
            'railway_domain': os.getenv('RAILWAY_PUBLIC_DOMAIN', 'Not set'),
            'base_url': getattr(settings, 'BASE_URL', 'Not set'),
        },
        'backends': settings.AUTHENTICATION_BACKENDS,
        'pipeline': settings.SOCIAL_AUTH_PIPELINE,
    }
    
    return render(request, 'properties/social_auth_diagnostics.html', {
        'diagnostics': diagnostics,
        'section': 'social_auth',
    })


@login_required
def social_settings(request):
    """Social authentication settings page."""
    from social_django.models import UserSocialAuth
    
    google_association = None
    facebook_association = None
    
    try:
        google_association = UserSocialAuth.objects.get(
            user=request.user,
            provider='google-oauth2'
        )
    except UserSocialAuth.DoesNotExist:
        pass
    
    try:
        facebook_association = UserSocialAuth.objects.get(
            user=request.user,
            provider='facebook'
        )
    except UserSocialAuth.DoesNotExist:
        pass
    
    return render(request, 'properties/social_settings.html', {
        'google_association': google_association,
        'facebook_association': facebook_association,
    })



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
        resort_queryset = Resort.objects.filter(status='active')
        
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
    from .models import BrokerChannel, ChannelPost
    
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
    
    # Get channel posts
    channel_posts = ChannelPost.objects.filter(
        channel=channel,
        status='published'
    ).select_related('author').prefetch_related('likes', 'comments').order_by('-is_pinned', '-created_at')[:20]
    
    # Get featured properties
    featured_properties = Property.objects.filter(
        broker=channel.broker,
        status__in=['ready', 'rent'],
        is_featured=True
    ).select_related('owner', 'broker').prefetch_related('gallery_images')[:6]
    
    # Get most viewed properties
    most_viewed_properties = Property.objects.filter(
        broker=channel.broker,
        status__in=['ready', 'rent']
    ).select_related('owner', 'broker').prefetch_related('gallery_images').order_by('-views_count')[:6]
    
    # Get new properties
    new_properties = Property.objects.filter(
        broker=channel.broker,
        status__in=['ready', 'rent']
    ).select_related('owner', 'broker').prefetch_related('gallery_images').order_by('-created_at')[:6]
    
    # Get user's likes and saves if authenticated
    user_likes = set()
    user_saves = set()
    is_following = False
    notifications_enabled = False
    if request.user.is_authenticated:
        user_likes = set(PropertyLike.objects.filter(user=request.user).values_list('property_id', flat=True))
        user_saves = set(PropertySave.objects.filter(user=request.user).values_list('property_id', flat=True))
        # Check if user is following this channel
        from .models import BrokerSubscription
        is_following = BrokerSubscription.objects.filter(
            user=request.user,
            broker=channel.broker,
            is_active=True
        ).exists()
    
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
        'channel_posts': channel_posts,
        'featured_properties': featured_properties,
        'most_viewed_properties': most_viewed_properties,
        'new_properties': new_properties,
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
    
    # Check subscription status before editing property
    broker = get_broker(request.user)
    if broker:
        broker.check_subscription_status()
        if not broker.is_subscription_active() and not broker.can_edit_properties:
            if broker.is_suspended:
                messages.error(request, 'تم تعطيل حسابك مؤقتاً بسبب انتهاء الاشتراك. يرجى تجديد الاشتراك للاستمرار.')
            elif not broker.is_subscription_active():
                messages.error(request, 'انتهى اشتراكك. يرجى تجديد الاشتراك لتعديل العقارات.')
            else:
                messages.error(request, 'ليس لديك صلاحية تعديل العقارات.')
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
        
        # Check subscription status before deleting property
        broker = get_broker(request.user)
        if broker:
            broker.check_subscription_status()
            if not broker.can_delete_properties and not is_platform_admin(request.user):
                messages.error(request, 'ليس لديك صلاحية حذف العقارات.')
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




def auction_terms(request):
    return render(request, 'properties/auction_terms.html')


@login_required
def building_request_create(request):
    if request.method == 'POST':
        form = BuildingRequestForm(request.POST)
        if form.is_valid():
            building_request = form.save(commit=False)
            building_request.user = request.user
            
            # Set publisher type
            try:
                from .models import Broker
                broker = Broker.objects.get(user=request.user)
                building_request.broker = broker
                building_request.publisher_type = 'broker'
            except Broker.DoesNotExist:
                building_request.publisher_type = 'user'
            
            # Handle featured requests
            if building_request.is_featured:
                from datetime import timedelta
                from django.utils import timezone
                building_request.featured_until = timezone.now() + timedelta(days=30)
            
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


def public_building_requests(request):
    """صفحة عرض طلبات البناء العامة للمستخدمين"""
    from django.db.models import Q
    
    # Get only public requests
    building_requests = BuildingRequest.objects.filter(is_public=True).select_related('broker', 'user').order_by('-is_featured', '-created_at')
    
    # Apply filters
    governorate = request.GET.get('governorate')
    if governorate:
        building_requests = building_requests.filter(governorate=governorate)
    
    project_type = request.GET.get('project_type')
    if project_type:
        building_requests = building_requests.filter(project_type__icontains=project_type)
    
    budget_min = request.GET.get('budget_min')
    budget_max = request.GET.get('budget_max')
    if budget_min:
        building_requests = building_requests.filter(estimated_budget__gte=budget_min)
    if budget_max:
        building_requests = building_requests.filter(estimated_budget__lte=budget_max)
    
    # Search
    search_query = request.GET.get('q')
    if search_query:
        building_requests = building_requests.filter(
            Q(description__icontains=search_query) |
            Q(project_type__icontains=search_query) |
            Q(city__icontains=search_query) |
            Q(district__icontains=search_query)
        )
    
    return render(request, 'properties/public_building_requests.html', {
        'building_requests': building_requests,
        'governorate': governorate,
        'project_type': project_type,
        'budget_min': budget_min,
        'budget_max': budget_max,
        'search_query': search_query,
    })


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
    
    # Check if auction requires access
    if auction.access_type != 'public':
        # Check if user is the broker
        if auction.broker and auction.broker.user == request.user:
            pass  # Broker always has access
        # Check if user has session access
        elif request.session.get(f'auction_access_{auction_id}'):
            pass  # User has access via session
        # Check if user has a valid invitation
        elif request.user.is_authenticated and AuctionInvitation.objects.filter(auction=auction, invited_user=request.user, status='accepted').exists():
            pass  # User has access via invitation
        else:
            # Redirect to access code page
            return redirect('auction_access_code', auction_id=auction_id)
    
    # Get auction data
    highest_bid = auction.get_current_highest_bid()
    total_bids = auction.get_total_bids()
    participant_count = auction.get_participant_count()
    time_remaining = auction.get_time_remaining()
    
    # Get bids list
    bids = auction.bids.select_related('user').all().order_by('-amount', '-created_at')
    
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
        'bids': bids,
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
    resorts = Resort.objects.filter(status='active')
    
    if form.is_valid():
        # Filter by resort type
        if form.cleaned_data.get('resort_type'):
            resorts = resorts.filter(resort_type__in=form.cleaned_data['resort_type'])
        
        # Filter by governorate
        if form.cleaned_data.get('governorate'):
            resorts = resorts.filter(governorate=form.cleaned_data['governorate'])
        
        # Filter by rating
        if form.cleaned_data.get('rating'):
            rating = int(form.cleaned_data['rating'])
            resorts = resorts.filter(rating__gte=rating)
        
        # Filter by price range
        if form.cleaned_data.get('price_range'):
            price_ranges = form.cleaned_data['price_range']
            q_objects = Q()
            for price_range in price_ranges:
                if price_range == '0-50000':
                    q_objects |= Q(max_price__lte=50000) | Q(min_price__lte=50000)
                elif price_range == '50000-100000':
                    q_objects |= Q(min_price__gte=50000, max_price__lte=100000)
                elif price_range == '100000-200000':
                    q_objects |= Q(min_price__gte=100000, max_price__lte=200000)
                elif price_range == '200000-500000':
                    q_objects |= Q(min_price__gte=200000, max_price__lte=500000)
                elif price_range == '500000+':
                    q_objects |= Q(min_price__gte=500000)
            resorts = resorts.filter(q_objects)
    
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
    
    # Filter by archived status (not available on Message model)
    show_archived = request.GET.get('archived') == '1'
    # Note: is_archived field not available on Message model, skipping this filter
    
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
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        profile_form = UserProfileForm(request.POST, instance=settings_obj)
        basic_form = UserBasicInfoForm(request.POST, instance=request.user)
        image_form = UserProfileImageForm(request.POST, request.FILES, instance=user_profile)
        
        if profile_form.is_valid() and basic_form.is_valid() and image_form.is_valid():
            profile_form.save()
            basic_form.save()
            image_form.save()
            messages.success(request, 'تم تحديث الملف الشخصي بنجاح')
            return redirect('user_settings_profile')
    else:
        profile_form = UserProfileForm(instance=settings_obj)
        basic_form = UserBasicInfoForm(instance=request.user)
        image_form = UserProfileImageForm(instance=user_profile)
    
    return render(request, 'properties/user_settings_profile.html', {
        'profile_form': profile_form,
        'basic_form': basic_form,
        'image_form': image_form,
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
    """لوحة تحكم الإدارة الرئيسية"""
    from .permissions import can_access_admin_panel

    if not can_access_admin_panel(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى لوحة الإدارة')
        return redirect('home')

    from django.contrib.auth.models import User
    from .models import Property, Broker, UserProfile, Auction, Bid, Notification, SubscriptionRequest, FinancialTransaction, PropertyPayment, Resort, ResortBooking

    # إحصائيات المستخدمين
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    admin_users = User.objects.filter(is_superuser=True).count()
    broker_users = User.objects.filter(broker_profile__isnull=False).count()
    regular_users = total_users - admin_users - broker_users

    # إحصائيات العقارات
    total_properties = Property.objects.count()
    active_properties = Property.objects.filter(status='published').count()
    pending_properties = Property.objects.filter(status=Property.STATUS_PENDING_APPROVAL).count()
    draft_properties = Property.objects.filter(status=Property.STATUS_DRAFT).count()
    sold_properties = Property.objects.filter(status='sold').count()
    
    # إحصائيات الدفع
    total_payments = PropertyPayment.objects.count()
    pending_payments = PropertyPayment.objects.filter(status=PropertyPayment.STATUS_PENDING).count()
    completed_payments = PropertyPayment.objects.filter(status=PropertyPayment.STATUS_COMPLETED).count()
    total_revenue = PropertyPayment.objects.filter(status=PropertyPayment.STATUS_COMPLETED).aggregate(
        total=Sum('total_amount')
    )['total'] or 0

    # إحصائيات المزادات
    total_auctions = Auction.objects.count()
    active_auctions = Auction.objects.filter(status='active').count()
    pending_auctions = Auction.objects.filter(approval_status='pending').count()
    ended_auctions = Auction.objects.filter(status='ended').count()

    # إحصائيات الدلالين
    total_brokers = Broker.objects.count()
    active_brokers = Broker.objects.filter(is_active=True).count()
    verified_brokers = Broker.objects.filter(is_verified=True).count()

    # إحصائيات المزايدات
    total_bids = Bid.objects.count()

    # إحصائيات المنتجعات
    total_resorts = Resort.objects.count()
    active_resorts = Resort.objects.filter(status='published').count()
    featured_resorts = Resort.objects.filter(is_featured=True).count()

    # إحصائيات الفنادق
    total_hotels = Property.objects.filter(category='hotel').count()
    active_hotels = Property.objects.filter(category='hotel', status='published').count()
    hotel_bookings = ResortBooking.objects.filter(resort__resort_type='hotel').count()

    # إحصائيات الحجوزات
    total_bookings = ResortBooking.objects.count()
    confirmed_bookings = ResortBooking.objects.filter(status='confirmed').count()
    cancelled_bookings = ResortBooking.objects.filter(status='cancelled').count()

    # المستخدمين الجدد (آخر 7 أيام)
    from datetime import timedelta
    week_ago = timezone.now() - timedelta(days=7)
    new_users = User.objects.filter(date_joined__gte=week_ago).count()

    # العقارات الجديدة (آخر 7 أيام)
    new_properties = Property.objects.filter(created_at__gte=week_ago).count()

    # الإشعارات غير المقروءة
    from .models import NotificationRecipient
    unread_notifications = NotificationRecipient.objects.filter(is_read=False).count()

    # طلبات الاشتراك المعلقة
    pending_subscription_requests = SubscriptionRequest.objects.filter(status='pending').count()

    # المعاملات المالية (آخر 30 يوم)
    month_ago = timezone.now() - timedelta(days=30)
    recent_transactions = FinancialTransaction.objects.filter(created_at__gte=month_ago).count()

    # النشاط الحديث
    recent_activity = ActivityLog.objects.select_related('user').order_by('-created_at')[:10]

    # العقارات المعلقة
    pending_properties_list = Property.objects.filter(
        status=Property.STATUS_PENDING_APPROVAL
    ).select_related('owner', 'broker')[:5]
    
    # المدفوعات المعلقة
    pending_payments_list = PropertyPayment.objects.filter(
        status=PropertyPayment.STATUS_PENDING
    ).select_related('property', 'broker')[:5]

    # طلبات الاشتراك المعلقة
    pending_subscription_requests_list = SubscriptionRequest.objects.filter(status='pending').select_related('broker', 'requested_plan')[:5]

    # المستخدمين الجدد
    new_users_list = User.objects.filter(date_joined__gte=week_ago).order_by('-date_joined')[:5]

    # المزادات المعلقة
    pending_auctions_list = Auction.objects.filter(approval_status='pending').select_related('property', 'broker')[:5]

    context = {
        'total_users': total_users,
        'active_users': active_users,
        'admin_users': admin_users,
        'broker_users': broker_users,
        'regular_users': regular_users,
        'total_properties': total_properties,
        'active_properties': active_properties,
        'pending_properties': pending_properties,
        'draft_properties': draft_properties,
        'sold_properties': sold_properties,
        'total_auctions': total_auctions,
        'active_auctions': active_auctions,
        'pending_auctions': pending_auctions,
        'ended_auctions': ended_auctions,
        'total_brokers': total_brokers,
        'active_brokers': active_brokers,
        'verified_brokers': verified_brokers,
        'total_bids': total_bids,
        'new_users': new_users,
        'new_properties': new_properties,
        'unread_notifications': unread_notifications,
        'pending_subscription_requests': pending_subscription_requests,
        'recent_transactions': recent_transactions,
        'recent_activity': recent_activity,
        'pending_properties_list': pending_properties_list,
        'pending_payments_list': pending_payments_list,
        'pending_subscription_requests_list': pending_subscription_requests_list,
        'new_users_list': new_users_list,
        'pending_auctions_list': pending_auctions_list,
        'total_payments': total_payments,
        'pending_payments': pending_payments,
        'completed_payments': completed_payments,
        'total_revenue': total_revenue,
        'total_resorts': total_resorts,
        'active_resorts': active_resorts,
        'featured_resorts': featured_resorts,
        'total_hotels': total_hotels,
        'active_hotels': active_hotels,
        'hotel_bookings': hotel_bookings,
        'total_bookings': total_bookings,
        'confirmed_bookings': confirmed_bookings,
        'cancelled_bookings': cancelled_bookings,
    }

    return render(request, 'properties/admin_panel.html', context)


@login_required
def admin_contact_view(request):
    """صفحة مراسلة الإدارة للدلال والمستخدمين"""
    from .permissions import can_access_admin_panel, get_user_type
    from django.contrib.auth.models import User
    from .models import Broker, UserProfile, Conversation, Message

    user_type = get_user_type(request.user)
    
    # البحث عن المستلمين
    search_query = request.GET.get('search', '')
    
    if user_type == 'admin':
        # الإدارة يمكنها مراسلة الجميع
        recipients = User.objects.filter(is_active=True).exclude(id=request.user.id).select_related('broker_profile', 'user_profile')
    elif user_type == 'broker':
        # الدلال يمكنه مراسلة الإدارة فقط
        recipients = User.objects.filter(
            Q(is_superuser=True) | Q(is_staff=True)
        ).exclude(id=request.user.id).distinct().select_related('broker_profile', 'user_profile')
    else:
        # المستخدم العادي يمكنه مراسلة الإدارة والدلالين فقط
        recipients = User.objects.filter(
            Q(is_superuser=True) | Q(is_staff=True) | Q(broker_profile__isnull=False)
        ).exclude(id=request.user.id).distinct().select_related('broker_profile', 'user_profile')
    
    # تطبيق البحث
    if search_query:
        recipients = recipients.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    # Get conversations for the user
    try:
        conversations = Conversation.objects.filter(
            participants=request.user
        ).prefetch_related('participants', 'messages').order_by('-updated_at')
    except:
        conversations = []
    
    # Get active conversation
    active_conversation_id = request.GET.get('conversation_id')
    active_conversation = None
    messages = []
    
    if active_conversation_id:
        try:
            active_conversation = Conversation.objects.get(
                id=active_conversation_id,
                participants=request.user
            )
            messages = active_conversation.messages.all().order_by('created_at')
        except:
            pass
    
    # Get total messages count
    try:
        total_messages = Message.objects.filter(
            Q(sender=request.user) | Q(recipient=request.user)
        ).count()
    except:
        total_messages = 0
    
    # Get unread count
    try:
        unread_count = Message.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()
    except:
        unread_count = 0
    
    if request.method == 'POST':
        recipient_id = request.POST.get('recipient_id')
        message_content = request.POST.get('message')
        subject = request.POST.get('subject', '')
        message_type = request.POST.get('message_type', 'support')
        priority = request.POST.get('priority', 'normal')
        
        if not all([recipient_id, message_content]):
            messages.error(request, 'يرجى ملء جميع الحقول')
        else:
            recipient = get_object_or_404(User, pk=recipient_id)
            
            # إنشاء محادثة جديدة أو استخدام محادثة موجودة
            try:
                conversation = Conversation.objects.filter(
                    participants=request.user
                ).filter(participants=recipient).first()
                
                if not conversation:
                    conversation = Conversation.objects.create()
                    conversation.participants.add(request.user, recipient)
            except:
                conversation = Conversation.objects.create()
                conversation.participants.add(request.user, recipient)
            
            # إنشاء رسالة جديدة
            msg = Message.objects.create(
                conversation=conversation,
                sender=request.user,
                recipient=recipient,
                content=message_content,
                subject=subject,
                message_type=message_type,
                priority=priority,
                is_read=False
            )
            
            # Update conversation timestamp
            conversation.updated_at = timezone.now()
            conversation.save()
            
            # Create notification for recipient
            from .utils import create_notification
            create_notification(
                user=recipient,
                notification_type='message',
                title='رسالة جديدة',
                message=f'لديك رسالة جديدة من {request.user.get_full_name() or request.user.username}',
                link=f'/dashboard/admin-contact/?conversation_id={conversation.id}'
            )
            
            messages.success(request, 'تم إرسال الرسالة بنجاح')
            return redirect(f'/dashboard/admin-contact/?conversation_id={conversation.id}')
    
    context = {
        'recipients': recipients,
        'user_type': user_type,
        'search_query': search_query,
        'conversations': conversations,
        'active_conversation': active_conversation,
        'messages': messages,
        'active_conversation_id': active_conversation_id,
        'total_messages': total_messages,
        'unread_count': unread_count,
    }
    
    return render(request, 'properties/admin_contact.html', context)


# ==================== Messaging System Views ====================

@login_required
def conversations_list(request):
    """قائمة المحادثات للمستخدم"""
    from .models import Conversation, Message
    
    conversations = Conversation.objects.filter(
        participants=request.user,
        is_active=True
    ).prefetch_related('participants', 'messages')
    
    # ترتيب المحادثات حسب آخر رسالة
    conversations = sorted(
        conversations,
        key=lambda c: c.last_message_at or c.created_at,
        reverse=True
    )
    
    context = {
        'conversations': conversations,
    }
    
    return render(request, 'properties/conversations_list.html', context)


@login_required
def conversation_detail(request, conversation_id):
    """تفاصيل المحادثة"""
    from .models import Conversation, Message
    
    conversation = get_object_or_404(
        Conversation,
        conversation_id=conversation_id,
        participants=request.user
    )
    
    # الحصول على الرسائل
    messages = conversation.messages.filter(
        is_deleted_by_sender=False,
        is_deleted_by_recipient=False
    ).order_by('created_at')
    
    # تحديث آخر رسالة
    if messages.exists():
        conversation.last_message_at = messages.last().created_at
        conversation.save(update_fields=['last_message_at'])
    
    # تحديث الرسائل غير المقروءة
    unread_messages = messages.filter(
        recipient=request.user,
        is_read=False
    )
    unread_messages.update(is_read=True)
    
    context = {
        'conversation': conversation,
        'messages': messages,
    }
    
    return render(request, 'properties/conversation_detail.html', context)


@login_required
def start_conversation(request, user_id):
    """بدء محادثة جديدة مع مستخدم"""
    from .models import Conversation, Message
    from .permissions import can_send_message_to_user
    
    other_user = get_object_or_404(User, pk=user_id)
    
    # التحقق من صلاحية المراسلة
    if not can_send_message_to_user(request.user, other_user):
        messages.error(request, 'ليس لديك صلاحية لمراسلة هذا المستخدم')
        return redirect('conversations_list')
    
    # التحقق من وجود محادثة سابقة
    existing_conversation = Conversation.objects.filter(
        participants=request.user,
        conversation_type=Conversation.TYPE_DIRECT
    ).filter(participants=other_user).first()
    
    if existing_conversation:
        return redirect('conversation_detail', conversation_id=existing_conversation.conversation_id)
    
    # إنشاء محادثة جديدة
    conversation = Conversation.objects.create(
        conversation_type=Conversation.TYPE_DIRECT,
        created_by=request.user
    )
    conversation.participants.add(request.user, other_user)
    
    return redirect('conversation_detail', conversation_id=conversation.conversation_id)


@login_required
def send_message(request):
    """إرسال رسالة جديدة"""
    from .models import Conversation, Message
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    conversation_id = request.POST.get('conversation_id')
    content = request.POST.get('content')
    message_type = request.POST.get('message_type', Message.TYPE_TEXT)
    
    if not all([conversation_id, content]):
        return JsonResponse({'error': 'Missing required fields'}, status=400)
    
    conversation = get_object_or_404(
        Conversation,
        conversation_id=conversation_id,
        participants=request.user
    )
    
    # الحصول على المستلم
    other_user = conversation.participants.exclude(id=request.user.id).first()
    
    if not other_user:
        return JsonResponse({'error': 'No recipient found'}, status=400)
    
    # إنشاء الرسالة
    message = Message.objects.create(
        conversation=conversation,
        sender=request.user,
        recipient=other_user,
        message_type=message_type,
        content=content,
        status=Message.STATUS_SENT
    )
    
    # تحديث آخر رسالة في المحادثة
    conversation.last_message_at = message.created_at
    conversation.save(update_fields=['last_message_at'])
    
    return JsonResponse({
        'success': True,
        'message_id': message.id,
        'content': message.content,
        'created_at': message.created_at.isoformat(),
    })


@login_required
def conversation_archive(request, conversation_id):
    """أرشفة المحادثة"""
    from .models import Conversation
    
    conversation = get_object_or_404(
        Conversation,
        conversation_id=conversation_id,
        participants=request.user
    )
    
    conversation.is_archived = not conversation.is_archived
    conversation.save(update_fields=['is_archived'])
    
    return redirect('conversations_list')


@login_required
def conversation_delete(request, conversation_id):
    """حذف المحادثة من جانب المستخدم"""
    from .models import Conversation, ConversationParticipant
    
    conversation = get_object_or_404(
        Conversation,
        conversation_id=conversation_id,
        participants=request.user
    )
    
    # حذف المشارك من المحادثة
    ConversationParticipant.objects.filter(
        conversation=conversation,
        user=request.user
    ).delete()
    
    return redirect('conversations_list')


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
        try:
            if user.is_superuser:
                user.user_type = 'admin'
            elif hasattr(user, 'broker_profile') and user.broker_profile:
                user.user_type = 'broker'
            elif hasattr(user, 'user_profile') and user.user_profile:
                user.user_type = 'user'
            else:
                user.user_type = 'unknown'
        except:
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
        try:
            if hasattr(user, 'broker') and user.broker:
                broker = user.broker
                broker.phone = request.POST.get('phone', '').strip()
                broker.is_active = request.POST.get('is_active') == 'on'
                broker.save()
            elif hasattr(user, 'userprofile') and user.userprofile:
                profile = user.userprofile
                profile.phone = request.POST.get('phone', '').strip()
                profile.is_active = request.POST.get('is_active') == 'on'
                profile.save()
        except Exception as e:
            messages.error(request, f'حدث خطأ: {str(e)}')

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
    try:
        if hasattr(user, 'broker') and user.broker:
            broker = user.broker
            broker.is_active = user.is_active
            broker.save()
        elif hasattr(user, 'userprofile') and user.userprofile:
            profile = user.userprofile
            profile.is_active = user.is_active
            profile.save()
    except Exception as e:
        messages.error(request, f'حدث خطأ: {str(e)}')

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
        status='active'
    ).select_related('broker').prefetch_related('followers')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        channels = channels.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(broker__display_name__icontains=search_query)
        )
    
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
        'search_query': search_query,
    }
    
    return render(request, 'properties/channels.html', context)


def channel_detail_view(request, slug):
    """View for displaying a single broker channel"""
    channel = get_object_or_404(BrokerChannel, slug=slug, status='active')
    
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


@login_required
def create_auction_view(request):
    """إنشاء مزاد جديد - للإدارة والدلال فقط"""
    from django.utils import timezone
    from decimal import Decimal
    
    # التحقق من الصلاحيات
    if not request.user.is_staff and not hasattr(request.user, 'broker'):
        messages.error(request, 'غير مصرح لك بإنشاء مزادات')
        return redirect('home')
    
    if request.method == 'POST':
        try:
            property_id = request.POST.get('property')
            auction_type = request.POST.get('auction_type')
            title = request.POST.get('title')
            description = request.POST.get('description')
            starting_price = request.POST.get('starting_price')
            minimum_increment = request.POST.get('minimum_increment', 100000)
            reserve_price = request.POST.get('reserve_price')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            deposit_amount = request.POST.get('deposit_amount', 0)
            terms = request.POST.get('terms')
            contact_phone = request.POST.get('contact_phone')
            contact_email = request.POST.get('contact_email')
            max_participants = request.POST.get('max_participants')
            
            # التحقق من البيانات
            if not all([property_id, title, description, starting_price, start_date, end_date, terms]):
                messages.error(request, 'يرجى ملء جميع الحقول المطلوبة')
                return redirect('create_auction')
            
            # الحصول على العقار
            property_obj = get_object_or_404(Property, id=property_id)
            
            # تحديد الدلال
            broker = None
            if hasattr(request.user, 'broker'):
                broker = request.user.broker
            
            # تحديد حالة الموافقة
            approval_status = 'approved' if request.user.is_staff else 'pending'
            approved_by = request.user if request.user.is_staff else None
            approved_at = timezone.now() if request.user.is_staff else None
            
            # إنشاء المزاد
            auction = Auction.objects.create(
                property=property_obj,
                broker=broker,
                auction_type=auction_type,
                title=title,
                description=description,
                starting_price=Decimal(starting_price),
                minimum_increment=Decimal(minimum_increment),
                reserve_price=Decimal(reserve_price) if reserve_price else None,
                start_date=start_date,
                end_date=end_date,
                deposit_amount=Decimal(deposit_amount),
                terms=terms,
                contact_phone=contact_phone,
                contact_email=contact_email,
                max_participants=int(max_participants) if max_participants else None,
                approval_status=approval_status,
                approved_by=approved_by,
                approved_at=approved_at
            )
            
            if request.user.is_staff:
                messages.success(request, 'تم إنشاء المزاد بنجاح')
            else:
                messages.success(request, 'تم إرسال طلب إنشاء المزاد للإدارة للمراجعة')
            
            return redirect('auction_detail', auction.id)
            
        except Exception as e:
            messages.error(request, f'حدث خطأ: {str(e)}')
            return redirect('create_auction')
    
    # عرض نموذج الإنشاء
    properties_list = Property.objects.filter(status='active')
    
    return render(request, 'properties/create_auction.html', {
        'properties': properties_list,
        'auction_types': Auction.AUCTION_TYPES
    })


@login_required
def auction_approval_view(request):
    """إدارة موافقة المزادات - للإدارة فقط"""
    if not request.user.is_staff:
        messages.error(request, 'غير مصرح لك بالوصول إلى هذه الصفحة')
        return redirect('home')
    
    pending_auctions = Auction.objects.filter(approval_status='pending')
    
    if request.method == 'POST':
        auction_id = request.POST.get('auction_id')
        action = request.POST.get('action')
        rejection_reason = request.POST.get('rejection_reason', '')
        
        auction = get_object_or_404(Auction, id=auction_id)
        
        if action == 'approve':
            auction.approval_status = 'approved'
            auction.approved_by = request.user
            auction.approved_at = timezone.now()
            auction.save()
            messages.success(request, 'تمت الموافقة على المزاد')
            
            # إرسال إشعار للدلال
            if auction.broker:
                Notification.objects.create(
                    user=auction.broker.user,
                    title='تمت الموافقة على مزادك',
                    message=f'تمت الموافقة على مزاد "{auction.title}"',
                    link=f'/auction/{auction.id}/'
                )
                
        elif action == 'reject':
            auction.approval_status = 'rejected'
            auction.rejection_reason = rejection_reason
            auction.save()
            messages.success(request, 'تم رفض المزاد')
            
            # إرسال إشعار للدلال
            if auction.broker:
                Notification.objects.create(
                    user=auction.broker.user,
                    title='تم رفض مزادك',
                    message=f'تم رفض مزاد "{auction.title}". السبب: {rejection_reason}',
                    link=f'/auction/{auction.id}/'
                )
                
        elif action == 'request_revision':
            auction.approval_status = 'needs_revision'
            auction.rejection_reason = rejection_reason
            auction.save()
            messages.success(request, 'تم طلب تعديل المزاد')
            
            # إرسال إشعار للدلال
            if auction.broker:
                Notification.objects.create(
                    user=auction.broker.user,
                    title='يحتاج تعديل',
                    message=f'مزاد "{auction.title}" يحتاج تعديل. {rejection_reason}',
                    link=f'/auction/{auction.id}/edit/'
                )
        
        return redirect('auction_approval')
    
    return render(request, 'properties/auction_approval.html', {
        'pending_auctions': pending_auctions
    })


@login_required
def auction_detail_view(request, auction_id):
    """صفحة تفاصيل المزاد مع المزايدة الحية"""
    auction = get_object_or_404(Auction, id=auction_id)
    
    # التحقق من الموافقة للمزادات التي لم تتم الموافقة عليها بعد
    if auction.approval_status != 'approved' and not request.user.is_staff:
        if auction.broker and auction.broker.user == request.user:
            pass  # الدلال يمكنه رؤية مزاده
        else:
            messages.error(request, 'هذا المزاد قيد المراجعة')
            return redirect('auctions_list')
    
    # التحقق من التسجيل
    is_participant = False
    if request.user.is_authenticated:
        is_participant = auction.participants.filter(user=request.user).exists()
    
    # الحصول على المزايدات
    bids = auction.bids.select_related('user').order_by('-created_at')[:10]
    
    # الحصول على أعلى مزايدة
    highest_bid = auction.get_current_highest_bid()
    
    # الوقت المتبقي
    time_remaining = auction.get_time_remaining()
    
    return render(request, 'properties/auction_detail.html', {
        'auction': auction,
        'is_participant': is_participant,
        'bids': bids,
        'highest_bid': highest_bid,
        'time_remaining': time_remaining
    })


@login_required
def join_auction_view(request, auction_id):
    """التسجيل في المزاد"""
    auction = get_object_or_404(Auction, id=auction_id)
    
    # التحقق من أن المزاد موافق عليه
    if auction.approval_status != 'approved':
        messages.error(request, 'هذا المزاد غير متاح للتسجيل')
        return redirect('auction_detail', auction.id)
    
    # التحقق من أن المستخدم ليس مسجلاً بالفعل
    if auction.participants.filter(user=request.user).exists():
        messages.error(request, 'أنت مسجل بالفعل في هذا المزاد')
        return redirect('auction_detail', auction.id)
    
    # التحقق من الحد الأقصى للمشاركين
    if auction.max_participants and auction.participants.count() >= auction.max_participants:
        messages.error(request, 'تم الوصول للحد الأقصى للمشاركين')
        return redirect('auction_detail', auction.id)
    
    if request.method == 'POST':
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        terms_accepted = request.POST.get('terms_accepted')
        
        if not all([phone, email, terms_accepted]):
            messages.error(request, 'يرجى ملء جميع الحقول والموافقة على الشروط')
            return redirect('auction_detail', auction.id)
        
        # إنشاء مشارك
        participant = AuctionParticipant.objects.create(
            auction=auction,
            user=request.user,
            phone=phone,
            email=email,
            approval_status='pending'  # يحتاج موافقة الإدارة إذا كان مفعل
        )
        
        # إذا كان مبلغ التأمين 0، يتم الموافقة تلقائياً
        if auction.deposit_amount == 0:
            participant.approval_status = 'approved'
            participant.approved_at = timezone.now()
            participant.save()
            messages.success(request, 'تم التسجيل في المزاد بنجاح')
        else:
            messages.success(request, 'تم التسجيل في المزاد. يرجى دفع مبلغ التأمين')
        
        return redirect('auction_detail', auction.id)
    
    return redirect('auction_detail', auction.id)


@login_required
def place_bid_view(request, auction_id):
    """المزايدة (AJAX)"""
    from decimal import Decimal
    
    auction = get_object_or_404(Auction, id=auction_id)
    
    # التحقق من أن المزاد نشط
    if not auction.is_active():
        return JsonResponse({
            'success': False,
            'error': 'المزاد غير نشط حالياً'
        })
    
    # التحقق من أن المستخدم مشارك وموافق عليه
    try:
        participant = auction.participants.get(user=request.user)
        if participant.approval_status != 'approved':
            return JsonResponse({
                'success': False,
                'error': 'لم يتم الموافقة على مشاركتك بعد'
            })
    except AuctionParticipant.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'يجب التسجيل في المزاد أولاً'
        })
    
    if request.method == 'POST':
        bid_amount = request.POST.get('bid_amount')
        
        try:
            bid_amount = Decimal(bid_amount)
        except:
            return JsonResponse({
                'success': False,
                'error': 'قيمة المزايدة غير صحيحة'
            })
        
        # التحقق من الحد الأدنى
        current_highest = auction.get_current_highest_bid()
        minimum_bid = current_highest + auction.minimum_increment
        
        if bid_amount < minimum_bid:
            return JsonResponse({
                'success': False,
                'error': f'أقل مزايدة مسموحة هي {minimum_bid:,} د.ع'
            })
        
        # إنشاء المزايدة
        bid = Bid.objects.create(
            auction=auction,
            user=request.user,
            amount=bid_amount
        )
        
        # التحقق من التمديد التلقائي
        if auction.should_extend():
            auction.extend_auction()
        
        return JsonResponse({
            'success': True,
            'bid_amount': str(bid_amount),
            'current_highest': str(auction.get_current_highest_bid()),
            'message': 'تمت المزايدة بنجاح'
        })
    
    return JsonResponse({
        'success': False,
        'error': 'طلب غير صحيح'
    })


# ==================== Payment System Views ====================

@login_required
def property_publication(request, slug):
    """View for choosing publication type and duration"""
    property = get_object_or_404(Property, slug=slug)
    
    # Check ownership
    if property.owner != request.user:
        messages.error(request, 'ليس لديك صلاحية نشر هذا العقار')
        return redirect('property_detail', slug=slug)
    
    # Get pricing settings (default: 50 IQD per day)
    from django.conf import settings
    daily_price = getattr(settings, 'DAILY_PROPERTY_PRICE', 50.00)
    featured_price = getattr(settings, 'FEATURED_PROPERTY_PRICE', 0.00)
    
    if request.method == 'POST':
        form = PropertyPublicationForm(request.POST, daily_price=daily_price, featured_price=featured_price)
        if form.is_valid():
            publication_type = form.cleaned_data['publication_type']
            publication_days = form.cleaned_data['publication_days']
            
            # Store in session for payment step
            request.session['publication_data'] = {
                'property_id': property.id,
                'publication_type': publication_type,
                'publication_days': publication_days,
                'daily_price': str(daily_price),
                'featured_price': str(featured_price),
                'total_amount': str(form.calculate_total()),
            }
            
            return redirect('property_payment', slug=slug)
    else:
        form = PropertyPublicationForm(daily_price=daily_price, featured_price=featured_price)
    
    context = {
        'property': property,
        'form': form,
        'daily_price': daily_price,
        'featured_price': featured_price,
    }
    
    return render(request, 'properties/property_publication.html', context)


@login_required
def property_payment(request, slug):
    """View for processing property payment"""
    property = get_object_or_404(Property, slug=slug)
    
    # Check ownership
    if property.owner != request.user:
        messages.error(request, 'ليس لديك صلاحية دفع هذا العقار')
        return redirect('property_detail', slug=slug)
    
    # Get publication data from session
    publication_data = request.session.get('publication_data')
    if not publication_data or publication_data.get('property_id') != property.id:
        messages.error(request, 'يجب اختيار خطة النشر أولاً')
        return redirect('property_publication', slug=slug)
    
    broker = get_broker(request.user)
    if not broker:
        messages.error(request, 'يجب أن تكون دلالاً لنشر العقارات')
        return redirect('dashboard')
    
    payment_methods = PaymentMethod.objects.filter(is_active=True)
    
    if request.method == 'POST':
        form = PropertyPaymentForm(request.POST, request.FILES)
        if form.is_valid():
            # Create payment record
            payment = PropertyPayment.objects.create(
                property=property,
                broker=broker,
                payment_method=form.cleaned_data['payment_method'],
                publication_type=publication_data['publication_type'],
                days=int(publication_data['publication_days']),
                daily_price=Decimal(publication_data['daily_price']),
                featured_price=Decimal(publication_data['featured_price']),
                total_amount=Decimal(publication_data['total_amount']),
                payment_proof=form.cleaned_data.get('payment_proof'),
                status=PropertyPayment.STATUS_PENDING,
            )
            
            # Update property status
            property.status = Property.STATUS_PAID
            property.publication_type = publication_data['publication_type']
            property.publication_days = int(publication_data['publication_days'])
            property.save()
            
            # Create notification
            PropertyNotification.objects.create(
                user=request.user,
                property=property,
                notification_type=PropertyNotification.TYPE_PAYMENT_SUCCESS,
                title='تم استلام طلب الدفع',
                message=f'تم استلام طلب دفع لنشر العقار: {property.display_title}. سيتم مراجعة الدفع من قبل الإدارة.'
            )
            
            # Clear session data
            del request.session['publication_data']
            
            messages.success(request, 'تم استلام طلب الدفع بنجاح. سيتم مراجعته من قبل الإدارة.')
            return redirect('dashboard')
    else:
        form = PropertyPaymentForm()
    
    context = {
        'property': property,
        'form': form,
        'payment_methods': payment_methods,
        'publication_type_display': 'مميز' if publication_data['publication_type'] == 'featured' else 'عادي',
        'publication_days': publication_data['publication_days'],
        'daily_price': Decimal(publication_data['daily_price']),
        'featured_price': Decimal(publication_data['featured_price']),
        'total_amount': Decimal(publication_data['total_amount']),
    }
    
    return render(request, 'properties/property_payment.html', context)


@login_required
@staff_required
def approve_property_payment(request, payment_id):
    """Admin view to approve property payment"""
    payment = get_object_or_404(PropertyPayment, id=payment_id)
    
    if payment.status != PropertyPayment.STATUS_PENDING:
        messages.error(request, 'هذا الدفع ليس في حالة انتظار')
        return redirect('admin_panel')
    
    if request.method == 'POST':
        payment.status = PropertyPayment.STATUS_COMPLETED
        payment.approved_by = request.user
        payment.approved_at = timezone.now()
        payment.payment_date = timezone.now()
        
        # Set publication dates
        payment.publication_start_date = timezone.now()
        from datetime import timedelta
        payment.publication_end_date = timezone.now() + timedelta(days=payment.days)
        
        payment.save()
        
        # Update property status
        property = payment.property
        property.status = Property.STATUS_PUBLISHED
        property.publication_start_date = payment.publication_start_date
        property.publication_end_date = payment.publication_end_date
        property.save()
        
        # Create notification
        PropertyNotification.objects.create(
            user=payment.broker.user,
            property=property,
            notification_type=PropertyNotification.TYPE_PROPERTY_APPROVED,
            title='تم قبول الدفع وبدء النشر',
            message=f'تم قبول دفع العقار: {property.display_title}. بدأ النشر الآن.'
        )
        
        messages.success(request, 'تم قبول الدفع وبدء النشر بنجاح')
        return redirect('admin_panel')
    
    context = {
        'payment': payment,
        'property': payment.property,
    }
    
    return render(request, 'properties/approve_payment.html', context)


# ==================== New Category Views ====================

def properties_inside_iraq_view(request):
    """View for properties inside Iraq with category selection"""
    # Get filters from query parameters
    property_type = request.GET.get('property_type', 'all')
    listing_type = request.GET.get('listing_type', 'all')
    governorate = request.GET.get('governorate', '')
    city = request.GET.get('city', '')
    price_min = request.GET.get('price_min', '')
    price_max = request.GET.get('price_max', '')
    area_min = request.GET.get('area_min', '')
    area_max = request.GET.get('area_max', '')
    
    # Get properties inside Iraq
    properties = get_public_properties()
    properties = [p for p in properties if p.country and p.country.code == 'IQ']
    
    # Apply filters
    if property_type != 'all':
        properties = [p for p in properties if p.type == property_type]
    
    if listing_type == 'sale':
        properties = [p for p in properties if p.status == 'ready']
    elif listing_type == 'rent':
        properties = [p for p in properties if p.status == 'rent']
    
    if governorate:
        properties = [p for p in properties if p.governorate == governorate]
    
    if city:
        properties = [p for p in properties if p.city == city]
    
    if price_min:
        properties = [p for p in properties if p.price >= int(price_min)]
    if price_max:
        properties = [p for p in properties if p.price <= int(price_max)]
    
    if area_min:
        properties = [p for p in properties if p.area >= int(area_min)]
    if area_max:
        properties = [p for p in properties if p.area <= int(area_max)]
    
    # Get user's likes and saves if authenticated
    user_likes = set()
    user_saves = set()
    if request.user.is_authenticated:
        user_likes = set(PropertyLike.objects.filter(user=request.user).values_list('property_id', flat=True))
        user_saves = set(PropertySave.objects.filter(user=request.user).values_list('property_id', flat=True))
    
    return render(request, 'properties/categories/inside_iraq.html', {
        'properties': properties,
        'property_type': property_type,
        'listing_type': listing_type,
        'governorate': governorate,
        'city': city,
        'user_likes': user_likes,
        'user_saves': user_saves,
        'category_title': 'عقارات داخل العراق',
        'category_icon': '🏠',
    })


def hotels_category_view(request):
    """View for hotels category"""
    from properties.models import PropertyHotel
    
    # Get filters
    star_rating = request.GET.get('star_rating', '')
    price_min = request.GET.get('price_min', '')
    price_max = request.GET.get('price_max', '')
    
    hotels = PropertyHotel.objects.all()
    
    if star_rating:
        hotels = hotels.filter(star_rating=int(star_rating))
    
    if price_min:
        hotels = [h for h in hotels if h.price_per_night and h.price_per_night >= int(price_min)]
    if price_max:
        hotels = [h for h in hotels if h.price_per_night and h.price_per_night <= int(price_max)]
    
    return render(request, 'properties/categories/hotels.html', {
        'hotels': hotels,
        'star_rating': star_rating,
        'price_min': price_min,
        'price_max': price_max,
        'category_title': 'فنادق',
        'category_icon': '🏨',
    })


def resorts_category_view(request):
    """View for resorts category"""
    from properties.models import PropertyResort
    
    # Get filters
    resort_type = request.GET.get('resort_type', '')
    price_min = request.GET.get('price_min', '')
    price_max = request.GET.get('price_max', '')
    
    resorts = PropertyResort.objects.all()
    
    if resort_type:
        resorts = resorts.filter(resort_type=resort_type)
    
    if price_min:
        resorts = [r for r in resorts if r.price_per_night and r.price_per_night >= int(price_min)]
    if price_max:
        resorts = [r for r in resorts if r.price_per_night and r.price_per_night <= int(price_max)]
    
    return render(request, 'properties/categories/resorts.html', {
        'resorts': resorts,
        'resort_type': resort_type,
        'price_min': price_min,
        'price_max': price_max,
        'category_title': 'منتجعات وأماكن سياحية',
        'category_icon': '🏖️',
    })


def outside_iraq_category_view(request):
    """View for properties outside Iraq category"""
    from properties.models import Country, City, Area
    
    # Get filters
    country_id = request.GET.get('country', '')
    city_id = request.GET.get('city', '')
    property_type = request.GET.get('property_type', 'all')
    price_min = request.GET.get('price_min', '')
    price_max = request.GET.get('price_max', '')
    
    properties = get_public_properties()
    properties = [p for p in properties if p.country and p.country.code != 'IQ']
    
    if country_id:
        properties = [p for p in properties if p.country_id == int(country_id)]
    
    if city_id:
        properties = [p for p in properties if p.city_id == int(city_id)]
    
    if property_type != 'all':
        properties = [p for p in properties if p.type == property_type]
    
    if price_min:
        properties = [p for p in properties if p.price >= int(price_min)]
    if price_max:
        properties = [p for p in properties if p.price <= int(price_max)]
    
    # Get all countries
    countries = Country.objects.filter(is_active=True).order_by('name_ar')
    
    # Get user's likes and saves if authenticated
    user_likes = set()
    user_saves = set()
    if request.user.is_authenticated:
        user_likes = set(PropertyLike.objects.filter(user=request.user).values_list('property_id', flat=True))
        user_saves = set(PropertySave.objects.filter(user=request.user).values_list('property_id', flat=True))
    
    return render(request, 'properties/categories/outside_iraq.html', {
        'properties': properties,
        'countries': countries,
        'country_id': country_id,
        'city_id': city_id,
        'property_type': property_type,
        'price_min': price_min,
        'price_max': price_max,
        'user_likes': user_likes,
        'user_saves': user_saves,
        'category_title': 'عقارات خارج العراق',
        'category_icon': '🌍',
    })


# ==================== Dynamic Property Addition View ====================

def handle_media_uploads(request, property):
    """Handle media uploads for properties (images, videos, 360°)"""
    from .models import PropertyImage, PropertyVideo
    
    # Handle cover image (main property field)
    if 'cover_image' in request.FILES:
        property.cover_image = request.FILES['cover_image']
        property.save(update_fields=['cover_image'])
    
    # Handle personal image
    if 'personal_image' in request.FILES:
        property.personal_image = request.FILES['personal_image']
        property.save(update_fields=['personal_image'])
    
    # Handle additional images (max 10) - stored in PropertyImage model
    if 'additional_images' in request.FILES:
        additional_files = request.FILES.getlist('additional_images')
        for idx, img_file in enumerate(additional_files[:10]):  # Limit to 10 images
            PropertyImage.objects.create(
                property=property,
                image=img_file,
                is_primary=False,
                image_type='photo',
                sort_order=idx + 1
            )
    
    # Handle property video
    if 'property_video' in request.FILES:
        video_file = request.FILES['property_video']
        PropertyVideo.objects.create(
            property=property,
            video=video_file,
            sort_order=0
        )
    
    # Handle 360° images
    if '360_images' in request.FILES:
        files_360 = request.FILES.getlist('360_images')
        for idx, img_360 in enumerate(files_360):
            PropertyImage.objects.create(
                property=property,
                image=img_360,
                is_primary=False,
                image_type='360',
                sort_order=idx + 100  # Use higher sort order for 360 images
            )


@login_required
def dynamic_add_property(request):
    """View for dynamic property addition based on category"""
    from .forms import (
        DynamicPropertyForm, PropertyInsideIraqForm, 
        PropertyOutsideIraqForm, PropertyHotelForm, PropertyResortForm
    )
    from .models import PropertyImage, PropertyVideo, BrokerPlanSubscription
    from django.utils import timezone
    from datetime import timedelta
    
    category_form = DynamicPropertyForm(request.POST or None)
    property_form = None
    template_name = 'properties/dynamic_add_property.html'
    
    if request.method == 'POST':
        category = request.POST.get('category')
        publication_type = request.POST.get('publication_type', 'normal')
        publication_days = request.POST.get('publication_days')
        
        # Check if user has premium subscription for featured/pinned ads
        if publication_type in ['featured', 'pinned']:
            if hasattr(request.user, 'broker'):
                active_subscription = BrokerPlanSubscription.objects.filter(
                    broker=request.user.broker,
                    status='active',
                    end_date__gt=timezone.now()
                ).first()
                
                if not active_subscription or active_subscription.plan.tier != 'premium':
                    messages.error(request, 'يتطلب الإعلان المميز أو المثبت اشتراك مميز. يرجى ترقية اشتراكك.')
                    return render(request, template_name, {
                        'category_form': category_form,
                        'property_form': property_form,
                        'category': category,
                    })
        
        if category == 'inside_iraq':
            property_form = PropertyInsideIraqForm(request.POST, request.FILES)
            if property_form.is_valid():
                property = property_form.save(commit=False)
                property.category = 'property_iraq'
                property.owner = request.user
                
                # Handle publication type
                if publication_type == 'featured':
                    property.is_featured = True
                    if publication_days:
                        property.promotion_until = timezone.now().date() + timedelta(days=int(publication_days))
                elif publication_type == 'pinned':
                    property.is_pinned = True
                    if publication_days:
                        property.pinned_until = timezone.now() + timedelta(days=int(publication_days))
                
                property.save()
                
                # Handle media uploads
                handle_media_uploads(request, property)
                
                messages.success(request, 'تم إضافة العقار داخل العراق بنجاح')
                return redirect('dashboard')
                
        elif category == 'outside_iraq':
            property_form = PropertyOutsideIraqForm(request.POST, request.FILES)
            if property_form.is_valid():
                property = property_form.save(commit=False)
                property.category = 'property_outside'
                property.owner = request.user
                
                # Handle publication type
                if publication_type == 'featured':
                    property.is_featured = True
                    if publication_days:
                        property.promotion_until = timezone.now().date() + timedelta(days=int(publication_days))
                elif publication_type == 'pinned':
                    property.is_pinned = True
                    if publication_days:
                        property.pinned_until = timezone.now() + timedelta(days=int(publication_days))
                
                property.save()
                
                # Handle media uploads
                handle_media_uploads(request, property)
                
                messages.success(request, 'تم إضافة العقار خارج العراق بنجاح')
                return redirect('dashboard')
                
        elif category == 'hotel':
            property_form = PropertyHotelForm(request.POST, request.FILES)
            if property_form.is_valid():
                # Create base property first
                property = Property.objects.create(
                    title=property_form.cleaned_data['hotel_name'],
                    category='hotel',
                    owner=request.user,
                    status='published',
                    price=property_form.cleaned_data.get('price_per_night') or 0,
                    currency=property_form.cleaned_data.get('currency', 'USD'),
                )
                
                # Handle publication type for hotel
                if publication_type == 'featured':
                    property.is_featured = True
                    if publication_days:
                        property.promotion_until = timezone.now().date() + timedelta(days=int(publication_days))
                elif publication_type == 'pinned':
                    property.is_pinned = True
                    if publication_days:
                        property.pinned_until = timezone.now() + timedelta(days=int(publication_days))
                
                property.save()
                
                # Create hotel details
                hotel = property_form.save(commit=False)
                hotel.property = property
                hotel.save()
                
                # Handle media uploads
                handle_media_uploads(request, property)
                
                messages.success(request, 'تم إضافة الفندق بنجاح')
                return redirect('dashboard')
                
        elif category == 'resort':
            # Handle resort creation directly
            name = request.POST.get('name')
            resort_type = request.POST.get('resort_type')
            description = request.POST.get('description')
            governorate = request.POST.get('governorate')
            city = request.POST.get('city')
            district = request.POST.get('district')
            full_address = request.POST.get('full_address')
            phone = request.POST.get('phone')
            whatsapp = request.POST.get('whatsapp')
            email = request.POST.get('email')
            website = request.POST.get('website')
            working_hours = request.POST.get('working_hours')
            working_days = request.POST.get('working_days')
            min_price = request.POST.get('min_price')
            max_price = request.POST.get('max_price')
            currency = request.POST.get('currency', 'د.ع')
            advance_booking = request.POST.get('advance_booking') == 'on'
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            video_url = request.POST.get('video_url')
            meta_title = request.POST.get('meta_title')
            meta_description = request.POST.get('meta_description')
            keywords = request.POST.get('keywords')
            
            # Handle publication type for resort
            publication_type = request.POST.get('publication_type', 'normal')
            publication_days = request.POST.get('publication_days')
            
            if name and resort_type and description and governorate and city and full_address and phone:
                from .models import Resort, ResortAmenity, ResortService
                
                # Create base property first
                property = Property.objects.create(
                    title=name,
                    category='resort',
                    owner=request.user,
                    status='published',
                    price=min_price or 0,
                    currency=currency,
                )
                
                # Handle publication type for resort
                if publication_type == 'featured':
                    property.is_featured = True
                    if publication_days:
                        property.promotion_until = timezone.now().date() + timedelta(days=int(publication_days))
                elif publication_type == 'pinned':
                    property.is_pinned = True
                    if publication_days:
                        property.pinned_until = timezone.now() + timedelta(days=int(publication_days))
                
                property.save()
                
                # Handle media uploads
                handle_media_uploads(request, property)
                
                resort = Resort.objects.create(
                    name=name,
                    resort_type=resort_type,
                    description=description,
                    governorate=governorate,
                    city=city,
                    district=district,
                    full_address=full_address,
                    phone=phone,
                    whatsapp=whatsapp,
                    email=email,
                    website=website,
                    working_hours=working_hours,
                    working_days=working_days,
                    min_price=min_price,
                    max_price=max_price,
                    currency=currency,
                    advance_booking=advance_booking,
                    latitude=latitude,
                    longitude=longitude,
                    video_url=video_url,
                    meta_title=meta_title,
                    meta_description=meta_description,
                    keywords=keywords,
                    broker=request.user.broker if hasattr(request.user, 'broker') else None,
                    user=request.user,
                    property=property,  # Link resort to property
                )
                
                # Handle logo (separate from cover_image)
                if 'logo' in request.FILES:
                    resort.logo = request.FILES['logo']
                
                resort.save()
                
                # Add amenities
                amenities = request.POST.getlist('amenities')
                for amenity in amenities:
                    ResortAmenity.objects.create(
                        resort=resort,
                        amenity_type=amenity,
                        is_available=True
                    )
                
                # Add services
                services = request.POST.getlist('services')
                for service in services:
                    ResortService.objects.create(
                        resort=resort,
                        service_type=service,
                        is_available=True
                    )
                
                messages.success(request, 'تم إضافة المنتجع بنجاح')
                return redirect('resort_detail', slug=resort.slug)
            else:
                messages.error(request, 'يرجى ملء جميع الحقول المطلوبة')
    
    # Get the appropriate form based on selected category
    category = request.GET.get('category') or request.POST.get('category')
    
    # Initialize all forms for instant switching
    inside_iraq_form = PropertyInsideIraqForm()
    outside_iraq_form = PropertyOutsideIraqForm()
    hotel_form = PropertyHotelForm()
    resort_form = PropertyResortForm()
    
    # Default form if no category selected
    if category == 'inside_iraq':
        property_form = PropertyInsideIraqForm()
    elif category == 'outside_iraq':
        property_form = PropertyOutsideIraqForm()
    elif category == 'hotel':
        property_form = PropertyHotelForm()
    elif category == 'resort':
        property_form = PropertyResortForm()
    else:
        # Default to inside_iraq form if no category selected
        property_form = PropertyInsideIraqForm()
    
    return render(request, template_name, {
        'category_form': category_form,
        'property_form': property_form,
        'category': category,
        'inside_iraq_form': inside_iraq_form,
        'outside_iraq_form': outside_iraq_form,
        'hotel_form': hotel_form,
        'resort_form': resort_form,
    })


@login_required
@staff_required
def reject_property_payment(request, payment_id):
    """Admin view to reject property payment"""
    payment = get_object_or_404(PropertyPayment, id=payment_id)
    
    if payment.status != PropertyPayment.STATUS_PENDING:
        messages.error(request, 'هذا الدفع ليس في حالة انتظار')
        return redirect('admin_panel')
    
    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason', '')
        
        payment.status = PropertyPayment.STATUS_FAILED
        payment.rejection_reason = rejection_reason
        payment.approved_by = request.user
        payment.approved_at = timezone.now()
        payment.save()
        
        # Update property status
        property = payment.property
        property.status = Property.STATUS_REJECTED
        property.rejection_reason = rejection_reason
        property.save()
        
        # Create notification
        PropertyNotification.objects.create(
            user=payment.broker.user,
            property=property,
            notification_type=PropertyNotification.TYPE_PROPERTY_REJECTED,
            title='تم رفض الدفع',
            message=f'تم رفض دفع العقار: {property.display_title}. السبب: {rejection_reason}'
        )
        
        messages.success(request, 'تم رفض الدفع')
        return redirect('admin_panel')
    
    context = {
        'payment': payment,
        'property': payment.property,
    }
    
    return render(request, 'properties/reject_payment.html', context)


@login_required
@staff_required
def content_moderation_view(request):
    """لوحة الموافقة على المحتوى - منشورات، قنوات، عقارات"""
    
    # فلترة حسب النوع
    content_type = request.GET.get('type', 'all')
    status_filter = request.GET.get('status', 'pending')
    
    # القنوات المعلقة
    pending_channels = BrokerChannel.objects.filter(status='pending').select_related('broker', 'broker__user')
    
    # المنشورات المعلقة
    pending_posts = ChannelPost.objects.filter(is_published=False).select_related('channel', 'channel__broker')
    
    # الفيديوهات المعلقة
    pending_videos = ChannelVideo.objects.filter(is_published=False).select_related('channel', 'channel__broker')
    
    # العقارات المعلقة
    pending_properties = Property.objects.filter(status=Property.STATUS_PENDING_APPROVAL).select_related('broker', 'owner')
    
    # القنوات المحجوبة
    suspended_channels = BrokerChannel.objects.filter(status='suspended').select_related('broker', 'broker__user')
    
    # الدلالين المحجوبين
    suspended_brokers = Broker.objects.filter(is_active=False).select_related('user')
    
    context = {
        'pending_channels': pending_channels,
        'pending_posts': pending_posts,
        'pending_videos': pending_videos,
        'pending_properties': pending_properties,
        'suspended_channels': suspended_channels,
        'suspended_brokers': suspended_brokers,
        'content_type': content_type,
        'status_filter': status_filter,
    }
    
    return render(request, 'properties/content_moderation.html', context)


@login_required
@staff_required
def approve_channel(request, channel_id):
    """الموافقة على قناة"""
    channel = get_object_or_404(BrokerChannel, id=channel_id)
    channel.status = BrokerChannel.STATUS_ACTIVE
    channel.save()
    
    messages.success(request, f'تم تفعيل قناة {channel.name} بنجاح')
    return redirect('content_moderation')


@login_required
@staff_required
def reject_channel(request, channel_id):
    """رفض قناة"""
    channel = get_object_or_404(BrokerChannel, id=channel_id)
    channel.status = BrokerChannel.STATUS_INACTIVE
    channel.save()
    
    messages.success(request, f'تم رفض قناة {channel.name}')
    return redirect('content_moderation')


@login_required
@staff_required
def suspend_channel(request, channel_id):
    """حجب قناة"""
    channel = get_object_or_404(BrokerChannel, id=channel_id)
    channel.status = BrokerChannel.STATUS_SUSPENDED
    channel.save()
    
    messages.success(request, f'تم حجب قناة {channel.name}')
    return redirect('content_moderation')


@login_required
@staff_required
def unsuspend_channel(request, channel_id):
    """فك حجب قناة"""
    channel = get_object_or_404(BrokerChannel, id=channel_id)
    channel.status = BrokerChannel.STATUS_ACTIVE
    channel.save()
    
    messages.success(request, f'تم فك حجب قناة {channel.name}')
    return redirect('content_moderation')


@login_required
@staff_required
def approve_post(request, post_id):
    """الموافقة على منشور"""
    post = get_object_or_404(ChannelPost, id=post_id)
    post.is_published = True
    post.save()
    
    messages.success(request, 'تم نشر المنشور بنجاح')
    return redirect('content_moderation')


@login_required
@staff_required
def reject_post(request, post_id):
    """رفض منشور"""
    post = get_object_or_404(ChannelPost, id=post_id)
    post.delete()
    
    messages.success(request, 'تم حذف المنشور')
    return redirect('content_moderation')


@login_required
@staff_required
def approve_video(request, video_id):
    """الموافقة على فيديو"""
    video = get_object_or_404(ChannelVideo, id=video_id)
    video.is_published = True
    video.save()
    
    messages.success(request, 'تم نشر الفيديو بنجاح')
    return redirect('content_moderation')


@login_required
@staff_required
def reject_video(request, video_id):
    """رفض فيديو"""
    video = get_object_or_404(ChannelVideo, id=video_id)
    video.delete()
    
    messages.success(request, 'تم حذف الفيديو')
    return redirect('content_moderation')


@login_required
@staff_required
def suspend_broker(request, broker_id):
    """حجب دلال"""
    broker = get_object_or_404(Broker, id=broker_id)
    broker.is_active = False
    broker.save()
    
    # حجب القناة أيضاً
    if hasattr(broker, 'channel'):
        broker.channel.status = BrokerChannel.STATUS_SUSPENDED
        broker.channel.save()
    
    messages.success(request, f'تم حجب الدلال {broker.display_name}')
    return redirect('content_moderation')


@login_required
@staff_required
def unsuspend_broker(request, broker_id):
    """فك حجب دلال"""
    broker = get_object_or_404(Broker, id=broker_id)
    broker.is_active = True
    broker.save()
    
    # تفعيل القناة أيضاً
    if hasattr(broker, 'channel'):
        broker.channel.status = BrokerChannel.STATUS_ACTIVE
        broker.channel.save()
    
    messages.success(request, f'تم فك حجب الدلال {broker.display_name}')
    return redirect('content_moderation')


@login_required
@staff_required
def user_monitoring_view(request):
    """لوحة مراقبة المستخدمين - حذف، حجب، تقيد، إنذار"""
    from django.contrib.auth.models import User
    
    # البحث والفلترة
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    user_type_filter = request.GET.get('user_type', 'all')
    
    users = User.objects.all().select_related('broker_profile', 'user_profile')
    
    # تطبيق البحث
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    # فلترة حسب الحالة
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    elif status_filter == 'suspended':
        users = users.filter(is_active=False)
    
    # فلترة حسب نوع المستخدم
    if user_type_filter == 'admin':
        users = users.filter(is_superuser=True)
    elif user_type_filter == 'broker':
        users = users.filter(broker_profile__isnull=False)
    elif user_type_filter == 'regular':
        users = users.filter(broker_profile__isnull=True, is_superuser=False, is_staff=False)
    
    # استبعاد المستخدم الحالي
    users = users.exclude(id=request.user.id)
    
    # ترتيب حسب تاريخ التسجيل
    users = users.order_by('-date_joined')
    
    context = {
        'users': users,
        'search_query': search_query,
        'status_filter': status_filter,
        'user_type_filter': user_type_filter,
    }
    
    return render(request, 'properties/user_monitoring.html', context)


@login_required
@staff_required
def delete_user(request, user_id):
    """حذف مستخدم"""
    user = get_object_or_404(User, id=user_id)
    
    if user.is_superuser:
        messages.error(request, 'لا يمكن حذف المشرفين')
        return redirect('user_monitoring')
    
    username = user.username
    user.delete()
    
    messages.success(request, f'تم حذف المستخدم {username} بنجاح')
    return redirect('user_monitoring')


@login_required
@staff_required
def suspend_user(request, user_id):
    """حجب مستخدم"""
    user = get_object_or_404(User, id=user_id)
    
    if user.is_superuser:
        messages.error(request, 'لا يمكن حجب المشرفين')
        return redirect('user_monitoring')
    
    user.is_active = False
    user.save()
    
    # حجب الدلال أيضاً إذا كان دلال
    if hasattr(user, 'broker_profile'):
        user.broker_profile.is_active = False
        user.broker_profile.save()
        
        # حجب القناة أيضاً
        if hasattr(user.broker_profile, 'channel'):
            user.broker_profile.channel.status = BrokerChannel.STATUS_SUSPENDED
            user.broker_profile.channel.save()
    
    messages.success(request, f'تم حجب المستخدم {user.username}')
    return redirect('user_monitoring')


@login_required
@staff_required
def unsuspend_user(request, user_id):
    """فك حجب مستخدم"""
    user = get_object_or_404(User, id=user_id)
    user.is_active = True
    user.save()
    
    # تفعيل الدلال أيضاً إذا كان دلال
    if hasattr(user, 'broker_profile'):
        user.broker_profile.is_active = True
        user.broker_profile.save()
        
        # تفعيل القناة أيضاً
        if hasattr(user.broker_profile, 'channel'):
            user.broker_profile.channel.status = BrokerChannel.STATUS_ACTIVE
            user.broker_profile.channel.save()
    
    messages.success(request, f'تم فك حجب المستخدم {user.username}')
    return redirect('user_monitoring')


@login_required
@staff_required
def restrict_user(request, user_id):
    """تقيد مستخدم"""
    user = get_object_or_404(User, id=user_id)
    
    if user.is_superuser:
        messages.error(request, 'لا يمكن تقيد المشرفين')
        return redirect('user_monitoring')
    
    # تقيد المستخدم - منع نشر العقارات
    if hasattr(user, 'broker_profile'):
        user.broker_profile.can_post_properties = False
        user.broker_profile.save()
    
    messages.success(request, f'تم تقيد المستخدم {user.username}')
    return redirect('user_monitoring')


@login_required
@staff_required
def unrestrict_user(request, user_id):
    """فك تقيد مستخدم"""
    user = get_object_or_404(User, id=user_id)
    
    # فك تقيد المستخدم
    if hasattr(user, 'broker_profile'):
        user.broker_profile.can_post_properties = True
        user.broker_profile.save()
    
    messages.success(request, f'تم فك تقيد المستخدم {user.username}')
    return redirect('user_monitoring')


@login_required
@staff_required
def warn_user(request, user_id):
    """إنذار مستخدم"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        warning_message = request.POST.get('warning_message', '')
        
        if not warning_message:
            messages.error(request, 'يرجى كتابة رسالة الإنذار')
        else:
            # إنشاء إشعار للمستخدم
            Notification.objects.create(
                user=user,
                notification_type='warning',
                title='إنذار من الإدارة',
                message=warning_message
            )
            
            messages.success(request, f'تم إرسال إنذار للمستخدم {user.username}')
            return redirect('user_monitoring')
    
    context = {
        'user': user,
    }
    
    return render(request, 'properties/warn_user.html', context)


@login_required
@broker_required
def broker_create_building_request(request):
    """إنشاء طلب بناء جديد من قبل الدلال"""
    from .models import BuildingRequest
    
    if request.method == 'POST':
        # معلومات العميل
        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        
        # معلومات المشروع
        governorate = request.POST.get('governorate', '').strip()
        city = request.POST.get('city', '').strip()
        district = request.POST.get('district', '').strip()
        address = request.POST.get('address', '').strip()
        
        # تفاصيل البناء
        project_type = request.POST.get('project_type', '').strip()
        estimated_area = request.POST.get('estimated_area')
        estimated_budget = request.POST.get('estimated_budget')
        expected_start_date = request.POST.get('expected_start_date')
        expected_completion_date = request.POST.get('expected_completion_date')
        
        # حالة الطلب
        priority = request.POST.get('priority', 'medium')
        
        # وصف المشروع
        description = request.POST.get('description', '').strip()
        requirements = request.POST.get('requirements', '').strip()
        
        # التحقق من الحقول المطلوبة
        if not all([full_name, phone, governorate, city, project_type]):
            messages.error(request, 'يرجى ملء جميع الحقول المطلوبة')
        else:
            # الحصول على الدلال
            broker = request.user.broker_profile
            
            # إنشاء طلب البناء
            building_request = BuildingRequest.objects.create(
                broker=broker,
                full_name=full_name,
                phone=phone,
                email=email,
                governorate=governorate,
                city=city,
                district=district,
                address=address,
                project_type=project_type,
                estimated_area=int(estimated_area) if estimated_area else None,
                estimated_budget=int(estimated_budget) if estimated_budget else None,
                expected_start_date=expected_start_date if expected_start_date else None,
                expected_completion_date=expected_completion_date if expected_completion_date else None,
                priority=priority,
                description=description,
                requirements=requirements,
                status='pending'
            )
            
            # إشعار للإدارة
            from .utils import create_notification
            admins = User.objects.filter(is_superuser=True)
            
            for admin in admins:
                create_notification(
                    user=admin,
                    notification_type='building_request',
                    title='طلب بناء جديد',
                    message=f'طلب بناء جديد من الدلال {broker.display_name} في {city}',
                    link=f'/admin-panel/building-requests/{building_request.id}/',
                    metadata={'request_id': building_request.id}
                )
            
            messages.success(request, 'تم إنشاء طلب البناء بنجاح. بانتظار موافقة الإدارة')
            return redirect('broker_building_requests')
    
    return render(request, 'properties/broker_create_building_request.html')


@login_required
@broker_required
def broker_building_requests(request):
    """عرض طلبات البناء الخاصة بالدلال"""
    from .models import BuildingRequest
    
    broker = request.user.broker_profile
    requests = BuildingRequest.objects.filter(broker=broker).order_by('-created_at')
    
    context = {
        'requests': requests,
    }
    
    return render(request, 'properties/broker_building_requests.html', context)


@login_required
def building_request_contact(request, request_id):
    """تواصل مع صاحب طلب البناء"""
    building_request = get_object_or_404(BuildingRequest, pk=request_id)
    
    if request.method == 'POST':
        message_content = request.POST.get('message', '').strip()
        
        if not message_content:
            messages.error(request, 'يرجى كتابة رسالة')
        else:
            # Create a message using the existing messaging system
            try:
                from .models import Message
                recipient = building_request.user if building_request.user else building_request.broker.user
                
                message = Message.objects.create(
                    sender=request.user,
                    recipient=recipient,
                    subject=f'بخصوص طلب البناء: {building_request.project_type}',
                    content=message_content,
                    related_building_request=building_request
                )
                
                # Create notification for the recipient
                try:
                    from .utils import create_notification
                    create_notification(
                        user=recipient,
                        notification_type='message',
                        title='رسالة جديدة بخصوص طلب بناء',
                        message=f'رسالة من {request.user.get_full_name() or request.user.username} بخصوص طلب بناء في {building_request.city}',
                        link='/messages/',
                        metadata={'request_id': building_request.id}
                    )
                except:
                    pass  # Notification creation is optional
                
                messages.success(request, 'تم إرسال رسالتك بنجاح')
                return redirect('building_request_detail', request_id=request_id)
            except Exception as e:
                messages.error(request, 'حدث خطأ أثناء إرسال الرسالة')
    
    return render(request, 'properties/building_request_contact.html', {
        'building_request': building_request
    })


@login_required
def service_provider_register(request):
    """تسجيل مقدم خدمة جديد"""
    try:
        provider = ServiceProvider.objects.get(user=request.user)
        return redirect('service_provider_dashboard')
    except ServiceProvider.DoesNotExist:
        pass
    
    if request.method == 'POST':
        form = ServiceProviderForm(request.POST, request.FILES)
        if form.is_valid():
            provider = form.save(commit=False)
            provider.user = request.user
            provider.save()
            messages.success(request, 'تم إنشاء حساب مقدم الخدمة بنجاح')
            return redirect('service_provider_dashboard')
    else:
        form = ServiceProviderForm()
    
    return render(request, 'properties/service_provider_register.html', {'form': form})


@login_required
def service_provider_dashboard(request):
    """لوحة تحكم مقدم الخدمة"""
    try:
        provider = ServiceProvider.objects.get(user=request.user)
    except ServiceProvider.DoesNotExist:
        return redirect('service_provider_register')
    
    advertisements = ServiceAdvertisement.objects.filter(service_provider=provider).order_by('-created_at')
    
    return render(request, 'properties/service_provider_dashboard.html', {
        'provider': provider,
        'advertisements': advertisements,
    })


@login_required
def create_service_advertisement(request):
    """إنشاء إعلان خدمة جديد"""
    try:
        provider = ServiceProvider.objects.get(user=request.user)
    except ServiceProvider.DoesNotExist:
        messages.error(request, 'يرجى تسجيل حساب مقدم خدمة أولاً')
        return redirect('service_provider_register')
    
    if request.method == 'POST':
        form = ServiceAdvertisementForm(request.POST, request.FILES)
        if form.is_valid():
            advertisement = form.save(commit=False)
            advertisement.service_provider = provider
            
            # Handle featured ads
            if advertisement.is_featured:
                from datetime import timedelta
                advertisement.featured_until = timezone.now() + timedelta(days=30)
            
            advertisement.status = 'active'
            advertisement.save()
            messages.success(request, 'تم إنشاء الإعلان بنجاح')
            return redirect('service_provider_dashboard')
    else:
        form = ServiceAdvertisementForm()
    
    return render(request, 'properties/create_service_advertisement.html', {'form': form})


def public_service_advertisements(request):
    """صفحة عرض إعلانات الخدمات العامة"""
    from django.db.models import Q
    
    # Get only active advertisements
    advertisements = ServiceAdvertisement.objects.filter(status='active').select_related('service_provider').order_by('-is_featured', '-created_at')
    
    # Apply filters
    service_type = request.GET.get('service_type')
    if service_type:
        advertisements = advertisements.filter(service_type=service_type)
    
    governorate = request.GET.get('governorate')
    if governorate:
        advertisements = advertisements.filter(governorate=governorate)
    
    price_min = request.GET.get('price_min')
    price_max = request.GET.get('price_max')
    if price_min:
        advertisements = advertisements.filter(price__gte=price_min)
    if price_max:
        advertisements = advertisements.filter(price__lte=price_max)
    
    # Search
    search_query = request.GET.get('q')
    if search_query:
        advertisements = advertisements.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(location__icontains=search_query)
        )
    
    return render(request, 'properties/public_service_advertisements.html', {
        'advertisements': advertisements,
        'service_type': service_type,
        'governorate': governorate,
        'price_min': price_min,
        'price_max': price_max,
        'search_query': search_query,
    })


@login_required
def service_advertisement_detail(request, ad_id):
    """عرض تفاصيل إعلان الخدمة"""
    advertisement = get_object_or_404(ServiceAdvertisement, pk=ad_id)
    
    # Increment views
    advertisement.views_count += 1
    advertisement.save()
    
    return render(request, 'properties/service_advertisement_detail.html', {
        'advertisement': advertisement
    })


@login_required
def contact_service_provider(request, ad_id):
    """التواصل مع مقدم الخدمة"""
    advertisement = get_object_or_404(ServiceAdvertisement, pk=ad_id)
    
    if request.method == 'POST':
        message_content = request.POST.get('message', '').strip()
        
        if not message_content:
            messages.error(request, 'يرجى كتابة رسالة')
        else:
            try:
                from .models import Message
                recipient = advertisement.service_provider.user
                
                message = Message.objects.create(
                    sender=request.user,
                    recipient=recipient,
                    subject=f'بخصوص إعلان الخدمة: {advertisement.title}',
                    content=message_content,
                )
                
                # Increment inquiries count
                advertisement.inquiries_count += 1
                advertisement.save()
                
                messages.success(request, 'تم إرسال رسالتك بنجاح')
                return redirect('service_advertisement_detail', ad_id=ad_id)
            except Exception as e:
                messages.error(request, 'حدث خطأ أثناء إرسال الرسالة')
    
    return render(request, 'properties/contact_service_provider.html', {
        'advertisement': advertisement
    })


@login_required
def auction_access_code(request, auction_id):
    """صفحة إدخال رقم المزاد"""
    auction = get_object_or_404(Auction, pk=auction_id)
    
    # Check if access code is required
    if auction.access_type == 'public':
        return redirect('auction_detail', auction_id=auction_id)
    
    # Check if user already has access
    if request.user.is_authenticated:
        # Check if user is the broker
        if auction.broker and auction.broker.user == request.user:
            return redirect('auction_detail', auction_id=auction_id)
        
        # Check if user has a valid invitation
        if AuctionInvitation.objects.filter(auction=auction, invited_user=request.user, status='accepted').exists():
            return redirect('auction_detail', auction_id=auction_id)
    
    if request.method == 'POST':
        access_code = request.POST.get('access_code', '').strip()
        invitation_code = request.POST.get('invitation_code', '').strip()
        
        if access_code:
            # Check access code
            if auction.access_code == access_code:
                # Store access in session
                request.session[f'auction_access_{auction_id}'] = True
                messages.success(request, 'تم الدخول بنجاح')
                return redirect('auction_detail', auction_id=auction_id)
            else:
                messages.error(request, 'رقم الدخول غير صحيح')
        
        elif invitation_code:
            # Check invitation code
            try:
                invitation = AuctionInvitation.objects.get(auction=auction, invitation_code=invitation_code)
                if invitation.status == 'pending':
                    invitation.status = 'accepted'
                    invitation.accepted_at = timezone.now()
                    if request.user.is_authenticated:
                        invitation.invited_user = request.user
                    invitation.save()
                    messages.success(request, 'تم قبول الدعوة بنجاح')
                    return redirect('auction_detail', auction_id=auction_id)
                elif invitation.status == 'accepted':
                    messages.success(request, 'الدعوة مقبولة مسبقاً')
                    return redirect('auction_detail', auction_id=auction_id)
                else:
                    messages.error(request, 'الدعوة غير صالحة')
            except AuctionInvitation.DoesNotExist:
                messages.error(request, 'كود الدعوة غير صحيح')
    
    return render(request, 'properties/auction_access_code.html', {
        'auction': auction
    })


@login_required
def create_auction_invitation(request, auction_id):
    """إنشاء دعوة لمزاد"""
    auction = get_object_or_404(Auction, pk=auction_id)
    
    # Check if user is the broker
    if not auction.broker or auction.broker.user != request.user:
        messages.error(request, 'ليس لديك صلاحية إنشاء دعوات لهذا المزاد')
        return redirect('auction_detail', auction_id=auction_id)
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        user_id = request.POST.get('user_id')
        
        invitation = AuctionInvitation(auction=auction, email=email, phone=phone)
        
        if user_id:
            try:
                user = User.objects.get(pk=user_id)
                invitation.invited_user = user
            except User.DoesNotExist:
                messages.error(request, 'المستخدم غير موجود')
                return redirect('auction_detail', auction_id=auction_id)
        
        invitation.generate_code()
        invitation.save()
        
        # Send notification (you can implement email/SMS sending here)
        messages.success(request, f'تم إنشاء الدعوة بنجاح. كود الدعوة: {invitation.invitation_code}')
        return redirect('auction_detail', auction_id=auction_id)
    
    return render(request, 'properties/create_auction_invitation.html', {
        'auction': auction
    })


@login_required
def auction_invitations(request, auction_id):
    """عرض دعوات المزاد"""
    auction = get_object_or_404(Auction, pk=auction_id)
    
    # Check if user is the broker
    if not auction.broker or auction.broker.user != request.user:
        messages.error(request, 'ليس لديك صلاحية عرض دعوات هذا المزاد')
        return redirect('auction_detail', auction_id=auction_id)
    
    invitations = auction.invitations.all().order_by('-created_at')
    
    return render(request, 'properties/auction_invitations.html', {
        'auction': auction,
        'invitations': invitations
    })


@login_required
def building_request_detail(request, request_id):
    """عرض تفاصيل طلب البناء"""
    from .models import BuildingRequest
    
    building_request = get_object_or_404(BuildingRequest, id=request_id)
    
    context = {
        'building_request': building_request,
    }
    
    return render(request, 'properties/building_request_detail.html', context)


@login_required
@staff_required
def admin_building_requests(request):
    """عرض طلبات البناء للإدارة"""
    from .models import BuildingRequest
    
    status_filter = request.GET.get('status', 'all')
    governorate_filter = request.GET.get('governorate', 'all')
    
    requests = BuildingRequest.objects.all().select_related('broker', 'broker__user', 'user')
    
    if status_filter != 'all':
        requests = requests.filter(status=status_filter)
    
    if governorate_filter != 'all':
        requests = requests.filter(governorate=governorate_filter)
    
    requests = requests.order_by('-created_at')
    
    context = {
        'requests': requests,
        'status_filter': status_filter,
        'governorate_filter': governorate_filter,
    }
    
    return render(request, 'properties/admin_building_requests.html', context)


@login_required
@staff_required
def admin_approve_building_request(request, request_id):
    """الموافقة على طلب بناء"""
    from .models import BuildingRequest
    
    building_request = get_object_or_404(BuildingRequest, id=request_id)
    building_request.status = 'approved'
    building_request.save()
    
    # إشعار للدلال
    if building_request.broker:
        from .utils import create_notification
        create_notification(
            user=building_request.broker.user,
            notification_type='building_request',
            title='تمت الموافقة على طلب البناء',
            message=f'تمت الموافقة على طلب بنائك في {building_request.city}',
            link=f'/broker/building-requests/{building_request.id}/',
            metadata={'request_id': building_request.id}
        )
    
    messages.success(request, 'تمت الموافقة على طلب البناء')
    return redirect('admin_building_requests')


@login_required
@staff_required
def admin_reject_building_request(request, request_id):
    """رفض طلب بناء"""
    from .models import BuildingRequest
    
    building_request = get_object_or_404(BuildingRequest, id=request_id)
    building_request.status = 'cancelled'
    building_request.save()
    
    # إشعار للدلال
    if building_request.broker:
        from .utils import create_notification
        create_notification(
            user=building_request.broker.user,
            notification_type='building_request',
            title='تم رفض طلب البناء',
            message=f'تم رفض طلب بنائك في {building_request.city}',
            link=f'/broker/building-requests/{building_request.id}/',
            metadata={'request_id': building_request.id}
        )
    
    messages.success(request, 'تم رفض طلب البناء')
    return redirect('admin_building_requests')


@login_required
@broker_required
def broker_create_auction(request):
    """إنشاء مزاد جديد من قبل الدلال"""
    from .models import Auction, Property, BrokerPlanSubscription
    import secrets
    
    broker = request.user.broker_profile
    
    # التحقق من الاشتراك
    try:
        subscription = BrokerPlanSubscription.objects.filter(broker=broker, status='active').first()
        if not subscription or not subscription.is_active():
            messages.error(request, 'يجب أن يكون لديك اشتراك نشط لإنشاء مزاد')
            return redirect('broker_auctions')
        
        if not subscription.can_add_auction():
            remaining = subscription.plan.max_auctions - subscription.auctions_used
            messages.error(request, f'لقد استنفذت عدد المزادات المسموح بها في اشتراكك. المتبقي: {remaining}')
            return redirect('broker_auctions')
    except Exception as e:
        messages.error(request, 'حدث خطأ في التحقق من الاشتراك')
        return redirect('broker_auctions')
    
    if request.method == 'POST':
        # معلومات المزاد
        property_id = request.POST.get('property')
        auction_type = request.POST.get('auction_type')
        title = request.POST.get('title')
        description = request.POST.get('description')
        starting_price = request.POST.get('starting_price')
        minimum_increment = request.POST.get('minimum_increment')
        reserve_price = request.POST.get('reserve_price')
        start_date = request.POST.get('start_date')
        start_time = request.POST.get('start_time')
        end_date = request.POST.get('end_date')
        end_time = request.POST.get('end_time')
        auto_extend_minutes = request.POST.get('auto_extend_minutes')
        deposit_amount = request.POST.get('deposit_amount')
        access_type = request.POST.get('access_type')
        access_code = request.POST.get('access_code')
        max_participants = request.POST.get('max_participants')
        terms = request.POST.get('terms')
        contact_phone = request.POST.get('contact_phone')
        contact_email = request.POST.get('contact_email')
        
        # التحقق من الحقول المطلوبة
        if not all([property_id, auction_type, title, description, starting_price, start_date, start_time, end_date, end_time]):
            messages.error(request, 'يرجى ملء جميع الحقول المطلوبة')
        else:
            # الحصول على العقار
            property_obj = get_object_or_404(Property, id=property_id)
            
            # التحقق من أن العقار يملكه الدلال
            if property_obj.broker != broker:
                messages.error(request, 'يمكنك إنشاء مزاد فقط لعقاراتك')
            else:
                # دمج التاريخ والوقت
                from datetime import datetime
                start_datetime = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
                end_datetime = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
                
                # توليد كود دخول عشوائي إذا لم يتم توفيره
                if not access_code and access_type == 'private':
                    access_code = secrets.token_hex(4).upper()
                
                # استخدام مزاد من الحصة
                if not subscription.use_auction():
                    messages.error(request, 'حدث خطأ في استخدام حصة المزاد')
                    return redirect('broker_auctions')
                
                # إنشاء المزاد
                auction = Auction.objects.create(
                    property=property_obj,
                    broker=broker,
                    auction_type=auction_type,
                    title=title,
                    description=description,
                    starting_price=starting_price,
                    minimum_increment=int(minimum_increment) if minimum_increment else 100000,
                    reserve_price=int(reserve_price) if reserve_price else None,
                    start_date=start_datetime,
                    end_date=end_datetime,
                    auto_extend_minutes=int(auto_extend_minutes) if auto_extend_minutes else 5,
                    deposit_amount=int(deposit_amount) if deposit_amount else 0,
                    access_type=access_type if access_type else 'public',
                    access_code=access_code,
                    max_participants=int(max_participants) if max_participants else None,
                    terms=terms,
                    contact_phone=contact_phone,
                    contact_email=contact_email,
                    status='upcoming',
                    approval_status='pending'
                )
                
                # إشعار للإدارة
                from .utils import create_notification
                admins = User.objects.filter(is_superuser=True)
                
                for admin in admins:
                    create_notification(
                        user=admin,
                        notification_type='auction',
                        title='مزاد جديد بانتظار الموافقة',
                        message=f'مزاد جديد من الدلال {broker.display_name}: {title}',
                        link=f'/admin-panel/auctions/{auction.id}/',
                        metadata={'auction_id': auction.id}
                    )
                
                messages.success(request, 'تم إنشاء المزاد بنجاح. بانتظار موافقة الإدارة')
                return redirect('broker_auctions')
    
    # الحصول على عقارات الدلال
    broker = request.user.broker_profile
    properties = Property.objects.filter(broker=broker, is_active=True)
    
    context = {
        'properties': properties,
    }
    
    return render(request, 'properties/broker_create_auction.html', context)


@login_required
@broker_required
def broker_auctions(request):
    """عرض المزادات الخاصة بالدلال"""
    from .models import Auction, BrokerPlanSubscription
    
    broker = request.user.broker_profile
    auctions = Auction.objects.filter(broker=broker).order_by('-created_at')
    
    # Get subscription info
    subscription = BrokerPlanSubscription.objects.filter(broker=broker, status='active').first()
    auctions_remaining = 0
    auctions_used = 0
    max_auctions = 0
    
    if subscription and subscription.is_active():
        auctions_used = subscription.auctions_used
        max_auctions = subscription.plan.max_auctions
        auctions_remaining = max_auctions - auctions_used
    
    context = {
        'auctions': auctions,
        'subscription': subscription,
        'auctions_remaining': auctions_remaining,
        'auctions_used': auctions_used,
        'max_auctions': max_auctions,
    }
    
    return render(request, 'properties/broker_auctions.html', context)


@login_required
@staff_required
def admin_auctions(request):
    """عرض المزادات للإدارة"""
    from .models import Auction
    
    status_filter = request.GET.get('status', 'all')
    approval_filter = request.GET.get('approval', 'all')
    
    auctions = Auction.objects.all().select_related('broker', 'broker__user', 'property')
    
    if status_filter != 'all':
        auctions = auctions.filter(status=status_filter)
    
    if approval_filter != 'all':
        auctions = auctions.filter(approval_status=approval_filter)
    
    auctions = auctions.order_by('-created_at')
    
    context = {
        'auctions': auctions,
        'status_filter': status_filter,
        'approval_filter': approval_filter,
    }
    
    return render(request, 'properties/admin_auctions.html', context)


@login_required
@staff_required
def admin_approve_auction(request, auction_id):
    """الموافقة على مزاد"""
    from .models import Auction
    
    auction = get_object_or_404(Auction, id=auction_id)
    auction.approval_status = 'approved'
    auction.approved_by = request.user
    auction.approved_at = timezone.now()
    auction.save()
    
    # إشعار للدلال
    if auction.broker:
        from .utils import create_notification
        create_notification(
            user=auction.broker.user,
            notification_type='auction',
            title='تمت الموافقة على المزاد',
            message=f'تمت الموافقة على مزادك: {auction.title}',
            link=f'/broker/auctions/{auction.id}/',
            metadata={'auction_id': auction.id}
        )
    
    messages.success(request, 'تمت الموافقة على المزاد')
    return redirect('admin_auctions')


@login_required
@staff_required
def admin_reject_auction(request, auction_id):
    """رفض مزاد"""
    from .models import Auction
    
    if request.method == 'POST':
        auction = get_object_or_404(Auction, id=auction_id)
        rejection_reason = request.POST.get('rejection_reason', '')
        
        auction.approval_status = 'rejected'
        auction.rejection_reason = rejection_reason
        auction.save()
        
        # إشعار للدلال
        if auction.broker:
            from .utils import create_notification
            create_notification(
                user=auction.broker.user,
                notification_type='auction',
                title='تم رفض المزاد',
                message=f'تم رفض مزادك: {auction.title}. السبب: {rejection_reason}',
                link=f'/broker/auctions/{auction.id}/',
                metadata={'auction_id': auction.id}
            )
        
        messages.success(request, 'تم رفض المزاد')
        return redirect('admin_auctions')
    
    auction = get_object_or_404(Auction, id=auction_id)
    context = {
        'auction': auction,
    }
    
    return render(request, 'properties/admin_reject_auction.html', context)


@login_required
def auction_detail(request, auction_id):
    """عرض تفاصيل المزاد"""
    from .models import Auction
    
    auction = get_object_or_404(Auction, id=auction_id)
    
    context = {
        'auction': auction,
    }
    
    return render(request, 'properties/auction_detail.html', context)


@login_required
def auction_join(request, auction_id):
    """الانضمام إلى المزاد"""
    from .models import Auction, AuctionParticipant
    
    auction = get_object_or_404(Auction, id=auction_id)
    
    if request.method == 'POST':
        access_code = request.POST.get('access_code', '').strip()
        
        # التحقق من كود الدخول
        if auction.access_code and access_code != auction.access_code:
            messages.error(request, 'كود الدخول غير صحيح')
            return redirect('auction_detail', auction_id=auction_id)
        
        # التحقق من أن المستخدم لم ينضم بعد
        if AuctionParticipant.objects.filter(auction=auction, user=request.user).exists():
            messages.warning(request, 'أنت منضم بالفعل لهذا المزاد')
            return redirect('auction_detail', auction_id=auction_id)
        
        # التحقق من الحد الأقصى للمشاركين
        if auction.max_participants:
            current_participants = auction.participants.count()
            if current_participants >= auction.max_participants:
                messages.error(request, 'وصل المزاد إلى الحد الأقصى للمشاركين')
                return redirect('auction_detail', auction_id=auction_id)
        
        # إنشاء مشارك جديد
        participant = AuctionParticipant.objects.create(
            auction=auction,
            user=request.user,
            is_verified=True
        )
        
        messages.success(request, 'تم الانضمام إلى المزاد بنجاح')
        return redirect('auction_live', auction_id=auction_id)
    
    context = {
        'auction': auction,
    }
    
    return render(request, 'properties/auction_join.html', context)


@login_required
def auction_live(request, auction_id):
    """المزاد الحي"""
    from .models import Auction, Bid
    
    auction = get_object_or_404(Auction, id=auction_id)
    
    # التحقق من أن المستخدم مشارك
    if not AuctionParticipant.objects.filter(auction=auction, user=request.user).exists():
        messages.error(request, 'يجب الانضمام إلى المزاد أولاً')
        return redirect('auction_detail', auction_id=auction_id)
    
    # الحصول على المزايدات
    bids = auction.bids.all().order_by('-created_at')[:10]
    
    context = {
        'auction': auction,
        'bids': bids,
    }
    
    return render(request, 'properties/auction_live.html', context)


@login_required
def place_bid(request, auction_id):
    """وضع مزايدة"""
    from .models import Auction, Bid
    
    auction = get_object_or_404(Auction, id=auction_id)
    
    if request.method == 'POST':
        bid_amount = request.POST.get('bid_amount')
        
        # التحقق من أن المستخدم مشارك
        if not AuctionParticipant.objects.filter(auction=auction, user=request.user).exists():
            messages.error(request, 'يجب الانضمام إلى المزاد أولاً')
            return redirect('auction_detail', auction_id=auction_id)
        
        # التحقق من أن المزاد نشط
        if not auction.is_active():
            messages.error(request, 'المزاد غير نشط حالياً')
            return redirect('auction_detail', auction_id=auction_id)
        
        # التحقق من المبلغ
        try:
            bid_amount = int(bid_amount)
        except:
            messages.error(request, 'يرجى إدخال مبلغ صحيح')
            return redirect('auction_live', auction_id=auction_id)
        
        # التحقق من الحد الأدنى للزيادة
        current_highest = auction.get_current_highest_bid()
        if bid_amount < current_highest + auction.minimum_increment:
            messages.error(request, f'يجب أن تكون المزايدة أعلى من {current_highest + auction.minimum_increment}')
            return redirect('auction_live', auction_id=auction_id)
        
        # إنشاء المزايدة
        bid = Bid.objects.create(
            auction=auction,
            user=request.user,
            amount=bid_amount
        )
        
        # تمديد المزاد إذا لزم الأمر
        auction.extend_auction()
        
        messages.success(request, 'تم وضع المزايدة بنجاح')
        return redirect('auction_live', auction_id=auction_id)
    
    return redirect('auction_live', auction_id=auction_id)


@login_required
@staff_required
def determine_auction_winner(request, auction_id):
    """تحديد الفائز في المزاد"""
    from .models import Auction, Bid
    
    auction = get_object_or_404(Auction, id=auction_id)
    
    if auction.status != 'ended':
        messages.error(request, 'يمكن تحديد الفائز فقط للمزادات المنتهية')
        return redirect('admin_auctions')
    
    if auction.winner_announced:
        messages.warning(request, 'تم الإعلان عن الفائز بالفعل')
        return redirect('admin_auctions')
    
    # الحصول على أعلى مزايدة
    winning_bid = auction.bids.order_by('-amount').first()
    
    if winning_bid:
        auction.winner = winning_bid.user
        auction.winning_bid = winning_bid
        auction.winner_announced = True
        auction.save()
        
        # إشعار للفائز
        from .utils import create_notification
        create_notification(
            user=winning_bid.user,
            notification_type='auction',
            title='🎉 فزت بالمزاد!',
            message=f'تهانينا! فزت بمزاد {auction.title} بمبلغ {winning_bid.amount}',
            link=f'/auction/{auction.id}/',
            metadata={'auction_id': auction.id}
        )
        
        messages.success(request, 'تم تحديد الفائز بنجاح')
    else:
        messages.error(request, 'لا توجد مزايدات لهذا المزاد')
    
    return redirect('admin_auctions')


# ==================== User Moderation Views ====================

@login_required
def user_moderation_panel(request):
    """لوحة تحكم مراقبة المستخدمين"""
    from .permissions import is_platform_admin
    
    if not is_platform_admin(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    
    from django.contrib.auth.models import User
    from .models import UserWarning, UserSuspension, UserModerationAction, ActivityLog
    
    # إحصائيات
    total_users = User.objects.filter(is_active=True).count()
    suspended_users = UserSuspension.objects.filter(status='active').count()
    active_warnings = UserWarning.objects.filter(is_acknowledged=False).count()
    recent_actions = UserModerationAction.objects.all()[:10]
    
    # قائمة المستخدمين مع الفلترة
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    
    users = User.objects.all().select_related('broker_profile', 'user_profile')
    
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    if status_filter == 'suspended':
        users = [u for u in users if UserSuspension.objects.filter(user=u, status='active').exists()]
    elif status_filter == 'warned':
        users = [u for u in users if UserWarning.objects.filter(user=u, is_acknowledged=False).exists()]
    
    # إضافة معلومات المراقبة لكل مستخدم
    users_with_moderation = []
    for user in users:
        active_suspension = UserSuspension.objects.filter(user=user, status='active').first()
        active_warnings = UserWarning.objects.filter(user=user, is_acknowledged=False).count()
        recent_activity = ActivityLog.objects.filter(user=user).order_by('-created_at')[:5]
        
        users_with_moderation.append({
            'user': user,
            'is_suspended': active_suspension is not None,
            'suspension': active_suspension,
            'warning_count': active_warnings,
            'recent_activity': recent_activity,
        })
    
    context = {
        'total_users': total_users,
        'suspended_users': suspended_users,
        'active_warnings': active_warnings,
        'recent_actions': recent_actions,
        'users': users_with_moderation,
        'search_query': search_query,
        'status_filter': status_filter,
    }
    
    return render(request, 'properties/user_moderation_panel.html', context)


@login_required
def user_detail_moderation(request, user_id):
    """تفاصيل مراقبة مستخدم معين"""
    from .permissions import is_platform_admin
    
    if not is_platform_admin(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    
    from django.contrib.auth.models import User
    from .models import UserWarning, UserSuspension, UserModerationAction, ActivityLog
    
    user = get_object_or_404(User, id=user_id)
    
    # بيانات المستخدم
    warnings = UserWarning.objects.filter(user=user).order_by('-created_at')
    suspensions = UserSuspension.objects.filter(user=user).order_by('-start_date')
    moderation_actions = UserModerationAction.objects.filter(user=user).order_by('-created_at')
    recent_activity = ActivityLog.objects.filter(user=user).order_by('-created_at')[:20]
    
    # التحقق من حالة التعطيل الحالية
    active_suspension = UserSuspension.objects.filter(user=user, status='active').first()
    
    context = {
        'target_user': user,
        'warnings': warnings,
        'suspensions': suspensions,
        'moderation_actions': moderation_actions,
        'recent_activity': recent_activity,
        'active_suspension': active_suspension,
    }
    
    return render(request, 'properties/user_moderation_detail.html', context)


@login_required
def issue_user_warning(request, user_id):
    """إصدار إنذار لمستخدم"""
    from .permissions import is_platform_admin
    
    if not is_platform_admin(request.user):
        messages.error(request, 'ليس لديك صلاحية للقيام بهذا الإجراء')
        return redirect('dashboard')
    
    from django.contrib.auth.models import User
    from .models import UserWarning, UserModerationAction
    
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        warning_type = request.POST.get('warning_type')
        severity = request.POST.get('severity', 'medium')
        reason = request.POST.get('reason')
        duration_days = request.POST.get('duration_days')
        
        if not all([warning_type, reason]):
            messages.error(request, 'يرجى ملء جميع الحقول المطلوبة')
        else:
            from django.utils import timezone
            from datetime import timedelta
            
            expires_at = None
            if duration_days:
                expires_at = timezone.now() + timedelta(days=int(duration_days))
            
            # إنشاء الإنذار
            warning = UserWarning.objects.create(
                user=user,
                issued_by=request.user,
                warning_type=warning_type,
                severity=severity,
                reason=reason,
                expires_at=expires_at
            )
            
            # تسجيل الإجراء
            UserModerationAction.objects.create(
                user=user,
                moderator=request.user,
                action='warning',
                reason=f'{warning_type}: {reason}',
                duration=timedelta(days=int(duration_days)) if duration_days else None,
                ip_address=get_client_ip(request)
            )
            
            # إشعار للمستخدم
            from .utils import create_notification
            create_notification(
                user=user,
                notification_type='warning',
                title='⚠️ إنذار جديد',
                message=f'لقد تلقيت إنذاراً: {reason}',
                metadata={'warning_id': warning.id}
            )
            
            messages.success(request, 'تم إصدار الإنذار بنجاح')
            return redirect('user_moderation_detail', user_id=user.id)
    
    context = {
        'target_user': user,
        'warning_types': UserWarning.TYPE_CHOICES,
        'severity_choices': UserWarning.SEVERITY_CHOICES,
    }
    
    return render(request, 'properties/issue_warning.html', context)


@login_required
def suspend_user(request, user_id):
    """تعطيل مستخدم"""
    from .permissions import is_platform_admin
    
    if not is_platform_admin(request.user):
        messages.error(request, 'ليس لديك صلاحية للقيام بهذا الإجراء')
        return redirect('dashboard')
    
    from django.contrib.auth.models import User
    from .models import UserSuspension, UserModerationAction
    
    user = get_object_or_404(User, id=user_id)
    
    # التحقق من عدم تعطيل المستخدم بالفعل
    if UserSuspension.objects.filter(user=user, status='active').exists():
        messages.error(request, 'المستخدم معطل بالفعل')
        return redirect('user_moderation_detail', user_id=user.id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason')
        description = request.POST.get('description')
        duration_days = request.POST.get('duration_days')
        
        if not all([reason, description]):
            messages.error(request, 'يرجى ملء جميع الحقول المطلوبة')
        else:
            from django.utils import timezone
            from datetime import timedelta
            
            end_date = None
            if duration_days:
                end_date = timezone.now() + timedelta(days=int(duration_days))
            
            # إنشاء التعطيل
            suspension = UserSuspension.objects.create(
                user=user,
                suspended_by=request.user,
                reason=reason,
                description=description,
                end_date=end_date
            )
            
            # تعطيل حساب المستخدم
            user.is_active = False
            user.save()
            
            # تسجيل الإجراء
            UserModerationAction.objects.create(
                user=user,
                moderator=request.user,
                action='suspend',
                reason=f'{reason}: {description}',
                duration=timedelta(days=int(duration_days)) if duration_days else None,
                ip_address=get_client_ip(request)
            )
            
            # إشعار للمستخدم
            from .utils import create_notification
            create_notification(
                user=user,
                notification_type='suspension',
                title='🚫 تم تعطيل حسابك',
                message=f'تم تعطيل حسابك للسبب: {description}',
                metadata={'suspension_id': suspension.id}
            )
            
            messages.success(request, 'تم تعطيل المستخدم بنجاح')
            return redirect('user_moderation_detail', user_id=user.id)
    
    context = {
        'target_user': user,
        'reason_choices': UserSuspension.REASON_CHOICES,
    }
    
    return render(request, 'properties/suspend_user.html', context)


@login_required
def lift_suspension(request, user_id):
    """رفع تعطيل مستخدم"""
    from .permissions import is_platform_admin
    
    if not is_platform_admin(request.user):
        messages.error(request, 'ليس لديك صلاحية للقيام بهذا الإجراء')
        return redirect('dashboard')
    
    from django.contrib.auth.models import User
    from .models import UserSuspension, UserModerationAction
    
    user = get_object_or_404(User, id=user_id)
    suspension = UserSuspension.objects.filter(user=user, status='active').first()
    
    if not suspension:
        messages.error(request, 'المستخدم غير معطل حالياً')
        return redirect('user_moderation_detail', user_id=user.id)
    
    if request.method == 'POST':
        lift_reason = request.POST.get('lift_reason', '')
        
        # رفع التعطيل
        suspension.lift(lifted_by=request.user, reason=lift_reason)
        
        # تفعيل حساب المستخدم
        user.is_active = True
        user.save()
        
        # تسجيل الإجراء
        UserModerationAction.objects.create(
            user=user,
            moderator=request.user,
            action='unsuspend',
            reason=f'رفع التعطيل: {lift_reason}',
            ip_address=get_client_ip(request)
        )
        
        # إشعار للمستخدم
        from .utils import create_notification
        create_notification(
            user=user,
            notification_type='activation',
            title='✅ تم تفعيل حسابك',
            message='تم رفع التعطيل عن حسابك بنجاح',
            metadata={'suspension_id': suspension.id}
        )
        
        messages.success(request, 'تم رفع التعطيل بنجاح')
        return redirect('user_moderation_detail', user_id=user.id)
    
    context = {
        'target_user': user,
        'suspension': suspension,
    }
    
    return render(request, 'properties/lift_suspension.html', context)


@login_required
def delete_user(request, user_id):
    """حذف مستخدم"""
    from .permissions import is_platform_admin
    
    if not is_platform_admin(request.user):
        messages.error(request, 'ليس لديك صلاحية للقيام بهذا الإجراء')
        return redirect('dashboard')
    
    from django.contrib.auth.models import User
    from .models import UserModerationAction
    
    user = get_object_or_404(User, id=user_id)
    
    if user.is_superuser:
        messages.error(request, 'لا يمكن حذف المشرفين')
        return redirect('user_moderation_detail', user_id=user.id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason')
        
        # تسجيل الإجراء قبل الحذف
        UserModerationAction.objects.create(
            user=user,
            moderator=request.user,
            action='delete',
            reason=reason or 'حذف حساب',
            ip_address=get_client_ip(request)
        )
        
        # حذف المستخدم
        username = user.username
        user.delete()
        
        messages.success(request, f'تم حذف المستخدم {username} بنجاح')
        return redirect('user_moderation_panel')
    
    context = {
        'target_user': user,
    }
    
    return render(request, 'properties/delete_user.html', context)


@login_required
def subscription_renewal_request(request):
    """طلب تجديد اشتراك"""
    broker = get_broker(request.user)
    if not broker:
        messages.error(request, 'يجب أن تكون دلالاً للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    
    # Get current subscription
    current_subscription = BrokerPlanSubscription.objects.filter(
        broker=broker,
        status='active'
    ).first()
    
    if request.method == 'POST':
        property_types = request.POST.getlist('property_types')
        regular_count = int(request.POST.get('regular_count', 0))
        premium_count = int(request.POST.get('premium_count', 0))
        days_requested = int(request.POST.get('days_requested', 0))
        notes = request.POST.get('notes', '')
        
        # property_types now only includes property types (iraq, outside, hotels, resorts)
        # building_requests and auctions are handled separately
        
        if regular_count < 0 or premium_count < 0:
            messages.error(request, 'يجب إدخال أعداد صحيحة')
            return render(request, 'properties/subscription_renewal_request.html', {
                'current_subscription': current_subscription
            })
        
        if regular_count == 0 and premium_count == 0:
            messages.error(request, 'يجب تحديد عدد عقارات واحد على الأقل')
            return render(request, 'properties/subscription_renewal_request.html', {
                'current_subscription': current_subscription
            })
        
        if days_requested < 1:
            messages.error(request, 'يجب إدخال عدد أيام صحيح')
            return render(request, 'properties/subscription_renewal_request.html', {
                'current_subscription': current_subscription
            })
        
        # Calculate cost
        regular_price = 50
        premium_price = 1000
        regular_cost = regular_price * regular_count * days_requested
        premium_cost = premium_price * premium_count * days_requested
        estimated_cost = regular_cost + premium_cost
        total_properties = regular_count + premium_count
        
        # Create combined plan name
        plan_name_parts = []
        if regular_count > 0:
            plan_name_parts.append(f'{regular_count} عادي')
        if premium_count > 0:
            plan_name_parts.append(f'{premium_count} مميز')
        plan_name = f'اشتراك مركب - {", ".join(plan_name_parts)}'
        
        # Find or create appropriate plan
        plan = AdvancedSubscriptionPlan.objects.filter(
            plan_type='combined',
            name=plan_name
        ).first()
        
        if not plan:
            # Create plan if it doesn't exist
            plan = AdvancedSubscriptionPlan.objects.create(
                name=plan_name,
                plan_type='combined',
                tier='mixed',
                price_per_day=estimated_cost // days_requested if days_requested > 0 else 0,
                max_properties=total_properties,
                allow_property_replacement=True,
                is_active=True
            )
        
        # Create renewal request
        renewal_request = SubscriptionRenewalRequest.objects.create(
            broker=broker,
            current_subscription=current_subscription,
            plan=plan,
            days_requested=days_requested,
            property_count=total_properties,
            regular_count=regular_count,
            premium_count=premium_count,
            property_types=property_types,
            estimated_cost=estimated_cost,
            notes=notes,
            status='pending'
        )
        
        messages.success(request, 'تم إرسال طلب التجديد بنجاح')
        return redirect('dashboard')
    
    return render(request, 'properties/subscription_renewal_request.html', {
        'current_subscription': current_subscription
    })


@login_required
def subscription_renewal_requests_list(request):
    """قائمة طلبات التجديد (للإدارة)"""
    from .permissions import is_platform_admin
    
    if not is_platform_admin(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    
    requests = SubscriptionRenewalRequest.objects.all().select_related('broker', 'plan').order_by('-created_at')
    
    return render(request, 'properties/subscription_renewal_requests_list.html', {
        'requests': requests
    })


@login_required
def approve_subscription_renewal(request, request_id):
    """الموافقة على طلب تجديد اشتراك"""
    from .permissions import is_platform_admin
    
    if not is_platform_admin(request.user):
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'})
    
    renewal_request = get_object_or_404(SubscriptionRenewalRequest, id=request_id)
    
    if renewal_request.status != 'pending':
        return JsonResponse({'success': False, 'error': 'الطلب ليس في حالة انتظار'})
    
    # Create or update subscription
    subscription = renewal_request.current_subscription
    if not subscription:
        # Create new subscription
        subscription = BrokerPlanSubscription.objects.create(
            broker=renewal_request.broker,
            plan=renewal_request.plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=renewal_request.days_requested),
            status='active',
            total_paid=renewal_request.estimated_cost
        )
    else:
        # Renew existing subscription
        subscription.renew(renewal_request.days_requested)
        subscription.total_paid += renewal_request.estimated_cost
        subscription.save()
    
    # Update request status
    renewal_request.status = 'approved'
    renewal_request.approved_by = request.user
    renewal_request.approved_at = timezone.now()
    renewal_request.save()
    
    return JsonResponse({'success': True})


@login_required
def reject_subscription_renewal(request, request_id):
    """رفض طلب تجديد اشتراك"""
    from .permissions import is_platform_admin
    
    if not is_platform_admin(request.user):
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية'})
    
    renewal_request = get_object_or_404(SubscriptionRenewalRequest, id=request_id)
    
    if renewal_request.status != 'pending':
        return JsonResponse({'success': False, 'error': 'الطلب ليس في حالة انتظار'})
    
    renewal_request.status = 'rejected'
    renewal_request.rejection_reason = request.POST.get('reason', '')
    renewal_request.save()
    
    return JsonResponse({'success': True})


@login_required
def user_monitoring_panel(request):
    """لوحة مراقبة المستخدمين"""
    from .permissions import is_platform_admin
    
    if not is_platform_admin(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    
    users = User.objects.all().select_related('user_profile', 'broker_profile').order_by('-date_joined')
    
    # Get additional info for each user
    users_data = []
    for user in users:
        broker = None
        try:
            broker = Broker.objects.get(user=user)
        except Broker.DoesNotExist:
            pass
        
        subscription = None
        if broker:
            try:
                subscription = BrokerPlanSubscription.objects.filter(
                    broker=broker,
                    status='active'
                ).first()
            except:
                pass
        
        user_data = {
            'user': user,
            'broker': broker,
            'subscription': subscription,
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
            'is_active': user.is_active,
            'date_joined': user.date_joined,
            'last_login': user.last_login,
            'email': user.email,
        }
        users_data.append(user_data)
    
    return render(request, 'properties/user_monitoring_panel.html', {
        'users_data': users_data
    })


@login_required
def user_monitoring_detail(request, user_id):
    """تفاصيل مراقبة مستخدم محدد"""
    from .permissions import is_platform_admin
    
    if not is_platform_admin(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    
    user = get_object_or_404(User, id=user_id)
    
    # Get broker info
    broker = None
    try:
        broker = Broker.objects.get(user=user)
    except Broker.DoesNotExist:
        pass
    
    # Get subscription info
    subscriptions = []
    if broker:
        subscriptions = BrokerPlanSubscription.objects.filter(
            broker=broker
        ).order_by('-created_at')
    
    # Get properties
    properties = []
    if broker:
        properties = Property.objects.filter(
            broker=broker
        ).order_by('-created_at')[:20]
    
    # Get activity logs
    activity_logs = []
    try:
        activity_logs = ActivityLog.objects.filter(
            user=user
        ).order_by('-created_at')[:50]
    except:
        pass
    
    # Get messages
    messages_sent = []
    messages_received = []
    try:
        messages_sent = Message.objects.filter(
            sender=user
        ).order_by('-created_at')[:20]
        messages_received = Message.objects.filter(
            recipient=user
        ).order_by('-created_at')[:20]
    except:
        pass
    
    return render(request, 'properties/user_monitoring_detail.html', {
        'user': user,
        'broker': broker,
        'subscriptions': subscriptions,
        'properties': properties,
        'activity_logs': activity_logs,
        'messages_sent': messages_sent,
        'messages_received': messages_received,
    })


def get_client_ip(request):
    """الحصول على عنوان IP للعميل"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ==================== NOTIFICATIONS VIEWS ====================

@login_required
def notification_center(request):
    """مركز الإشعارات للمستخدم"""
    from .models import Notification, NotificationRecipient
    
    # Get all notifications for the user
    notifications = NotificationRecipient.objects.filter(
        user=request.user,
        is_archived=False
    ).select_related('notification').order_by('-created_at')
    
    # Get unread count
    unread_count = notifications.filter(is_read=False).count()
    
    # Filter by read status
    filter_type = request.GET.get('filter', 'all')
    if filter_type == 'unread':
        notifications = notifications.filter(is_read=False)
    elif filter_type == 'read':
        notifications = notifications.filter(is_read=True)
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        notifications = notifications.filter(
            notification__title__icontains=search_query
        )
    
    context = {
        'notifications': notifications,
        'unread_count': unread_count,
        'filter_type': filter_type,
        'search_query': search_query,
    }
    
    return render(request, 'properties/notification_center.html', context)


@login_required
def notification_detail(request, notification_id):
    """عرض تفاصيل إشعار"""
    from .models import Notification, NotificationRecipient
    
    try:
        recipient = NotificationRecipient.objects.get(
            notification_id=notification_id,
            user=request.user
        )
        
        # Mark as read
        recipient.mark_as_read()
        
        # If button link exists, redirect
        if recipient.notification.button_link:
            return redirect(recipient.notification.button_link)
        
        context = {
            'recipient': recipient,
            'notification': recipient.notification,
        }
        
        return render(request, 'properties/notification_detail.html', context)
    
    except NotificationRecipient.DoesNotExist:
        messages.error(request, 'الإشعار غير موجود')
        return redirect('notification_center')


@login_required
def mark_notification_read(request, notification_id):
    """تعليم إشعار كمقروء"""
    from .models import NotificationRecipient
    
    if request.method == 'POST':
        try:
            recipient = NotificationRecipient.objects.get(
                notification_id=notification_id,
                user=request.user
            )
            recipient.mark_as_read()
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            
            messages.success(request, 'تم تعليم الإشعار كمقروء')
        except NotificationRecipient.DoesNotExist:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'الإشعار غير موجود'})
            messages.error(request, 'الإشعار غير موجود')
    
    return redirect('notification_center')


@login_required
def mark_notification_clicked(request, notification_id):
    """تعليم إشعار كتم النقر"""
    from .models import NotificationRecipient
    
    if request.method == 'POST':
        try:
            recipient = NotificationRecipient.objects.get(
                notification_id=notification_id,
                user=request.user
            )
            recipient.mark_as_clicked()
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            
        except NotificationRecipient.DoesNotExist:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False})
    
    return JsonResponse({'success': True})


@login_required
def archive_notification(request, notification_id):
    """أرشفة إشعار"""
    from .models import NotificationRecipient
    
    if request.method == 'POST':
        try:
            recipient = NotificationRecipient.objects.get(
                notification_id=notification_id,
                user=request.user
            )
            recipient.archive()
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            
            messages.success(request, 'تم أرشفة الإشعار')
        except NotificationRecipient.DoesNotExist:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'الإشعار غير موجود'})
            messages.error(request, 'الإشعار غير موجود')
    
    return redirect('notification_center')


@login_required
def delete_notification(request, notification_id):
    """حذف إشعار"""
    from .models import NotificationRecipient
    
    if request.method == 'POST':
        try:
            recipient = NotificationRecipient.objects.get(
                notification_id=notification_id,
                user=request.user
            )
            recipient.delete()
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            
            messages.success(request, 'تم حذف الإشعار')
        except NotificationRecipient.DoesNotExist:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'الإشعار غير موجود'})
            messages.error(request, 'الإشعار غير موجود')
    
    return redirect('notification_center')


@login_required
def mark_all_read(request):
    """تعليم جميع الإشعارات كمقروءة"""
    from .models import NotificationRecipient
    
    if request.method == 'POST':
        NotificationRecipient.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True)
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        
        messages.success(request, 'تم تعليم جميع الإشعارات كمقروءة')
    
    return redirect('notification_center')


@login_required
def get_unread_count(request):
    """الحصول على عدد الإشعارات غير المقروءة (AJAX)"""
    from .models import NotificationRecipient
    
    count = NotificationRecipient.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    return JsonResponse({'count': count})


@login_required
def admin_notification_panel(request):
    """لوحة إدارة الإشعارات"""
    from .models import Notification, NotificationLog
    from .permissions import can_access_admin_panel
    
    if not can_access_admin_panel(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    
    notifications = Notification.objects.all().order_by('-created_at')
    
    # Stats
    total_sent = notifications.filter(status='sent').count()
    total_draft = notifications.filter(status='draft').count()
    total_scheduled = notifications.filter(status='scheduled').count()
    
    context = {
        'notifications': notifications,
        'total_sent': total_sent,
        'total_draft': total_draft,
        'total_scheduled': total_scheduled,
    }
    
    return render(request, 'properties/admin_notification_panel.html', context)


@login_required
def admin_create_notification(request):
    """إنشاء إشعار جديد"""
    from .models import Notification
    from .permissions import can_access_admin_panel
    
    if not can_access_admin_panel(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        notification_type = request.POST.get('notification_type', 'info')
        priority = request.POST.get('priority', 'normal')
        delivery_type = request.POST.get('delivery_type', 'in_app')
        icon = request.POST.get('icon', '')
        color = request.POST.get('color', '#0d9488')
        button_text = request.POST.get('button_text', '')
        button_link = request.POST.get('button_link', '')
        
        # Targeting
        target_all_users = request.POST.get('target_all_users') == 'on'
        target_all_brokers = request.POST.get('target_all_brokers') == 'on'
        target_all_admins = request.POST.get('target_all_admins') == 'on'
        target_office_owners = request.POST.get('target_office_owners') == 'on'
        target_managers = request.POST.get('target_managers') == 'on'
        target_active_users = request.POST.get('target_active_users') == 'on'
        target_new_users = request.POST.get('target_new_users') == 'on'
        target_inactive_users = request.POST.get('target_inactive_users') == 'on'
        
        # Account type targeting
        target_account_type = request.POST.get('target_account_type', '')
        target_subscription_type = request.POST.get('target_subscription_type', '')
        target_account_status = request.POST.get('target_account_status', '')
        
        # Properties targeting
        target_has_properties_str = request.POST.get('target_has_properties', '')
        target_has_properties = None
        if target_has_properties_str == 'true':
            target_has_properties = True
        elif target_has_properties_str == 'false':
            target_has_properties = False
        
        # Location targeting
        target_governorate = request.POST.get('target_governorate', '')
        target_city = request.POST.get('target_city', '')
        target_area = request.POST.get('target_area', '')
        
        # Property type targeting
        target_property_type = request.POST.get('target_property_type', '')
        
        # Broker targeting
        target_premium_brokers = request.POST.get('target_premium_brokers') == 'on'
        target_min_properties = request.POST.get('target_min_properties')
        target_min_rating = request.POST.get('target_min_rating')
        
        # Scheduling
        scheduled_for = request.POST.get('scheduled_for')
        expires_at = request.POST.get('expires_at')
        
        # Action
        action = request.POST.get('action', 'send')  # send, schedule, draft
        
        # Create notification
        notification = Notification.objects.create(
            title=title,
            description=description,
            notification_type=notification_type,
            priority=priority,
            delivery_type=delivery_type,
            icon=icon,
            color=color,
            button_text=button_text,
            button_link=button_link,
            target_all_users=target_all_users,
            target_all_brokers=target_all_brokers,
            target_all_admins=target_all_admins,
            target_office_owners=target_office_owners,
            target_managers=target_managers,
            target_active_users=target_active_users,
            target_new_users=target_new_users,
            target_inactive_users=target_inactive_users,
            target_account_type=target_account_type,
            target_subscription_type=target_subscription_type,
            target_account_status=target_account_status,
            target_has_properties=target_has_properties,
            target_governorate=target_governorate,
            target_city=target_city,
            target_area=target_area,
            target_property_type=target_property_type,
            target_premium_brokers=target_premium_brokers,
            target_min_properties=int(target_min_properties) if target_min_properties else None,
            target_min_rating=float(target_min_rating) if target_min_rating else None,
            scheduled_for=scheduled_for if scheduled_for else None,
            expires_at=expires_at if expires_at else None,
            created_by=request.user,
            status='draft' if action == 'draft' else ('scheduled' if scheduled_for else 'sent')
        )
        
        # If sending immediately
        if action == 'send' and not scheduled_for:
            from .services import NotificationService
            service = NotificationService()
            service.send_notification(notification)
        
        messages.success(request, 'تم إنشاء الإشعار بنجاح')
        return redirect('admin_notification_panel')
    
    return render(request, 'properties/admin_create_notification.html')


@login_required
def admin_edit_notification(request, notification_id):
    """تعديل إشعار (فقط للمسودات والمجدولة)"""
    from .models import Notification
    from .permissions import can_access_admin_panel
    
    if not can_access_admin_panel(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    
    notification = get_object_or_404(Notification, id=notification_id)
    
    # Only allow editing drafts and scheduled notifications
    if notification.status not in ['draft', 'scheduled']:
        messages.error(request, 'لا يمكن تعديل الإشعارات المرسلة')
        return redirect('admin_notification_detail', notification_id=notification_id)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        notification_type = request.POST.get('notification_type', 'info')
        priority = request.POST.get('priority', 'normal')
        delivery_type = request.POST.get('delivery_type', 'in_app')
        icon = request.POST.get('icon', '')
        color = request.POST.get('color', '#0d9488')
        button_text = request.POST.get('button_text', '')
        button_link = request.POST.get('button_link', '')
        
        # Targeting
        target_all_users = request.POST.get('target_all_users') == 'on'
        target_all_brokers = request.POST.get('target_all_brokers') == 'on'
        target_all_admins = request.POST.get('target_all_admins') == 'on'
        target_office_owners = request.POST.get('target_office_owners') == 'on'
        target_managers = request.POST.get('target_managers') == 'on'
        target_active_users = request.POST.get('target_active_users') == 'on'
        target_new_users = request.POST.get('target_new_users') == 'on'
        target_inactive_users = request.POST.get('target_inactive_users') == 'on'
        
        # Account type targeting
        target_account_type = request.POST.get('target_account_type', '')
        target_subscription_type = request.POST.get('target_subscription_type', '')
        target_account_status = request.POST.get('target_account_status', '')
        
        # Properties targeting
        target_has_properties_str = request.POST.get('target_has_properties', '')
        target_has_properties = None
        if target_has_properties_str == 'true':
            target_has_properties = True
        elif target_has_properties_str == 'false':
            target_has_properties = False
        
        # Location targeting
        target_governorate = request.POST.get('target_governorate', '')
        target_city = request.POST.get('target_city', '')
        target_area = request.POST.get('target_area', '')
        
        # Property type targeting
        target_property_type = request.POST.get('target_property_type', '')
        
        # Broker targeting
        target_premium_brokers = request.POST.get('target_premium_brokers') == 'on'
        target_min_properties = request.POST.get('target_min_properties')
        target_min_rating = request.POST.get('target_min_rating')
        
        # Scheduling
        scheduled_for = request.POST.get('scheduled_for')
        expires_at = request.POST.get('expires_at')
        
        # Action
        action = request.POST.get('action', 'send')  # send, schedule, draft
        
        # Update notification
        notification.title = title
        notification.description = description
        notification.notification_type = notification_type
        notification.priority = priority
        notification.delivery_type = delivery_type
        notification.icon = icon
        notification.color = color
        notification.button_text = button_text
        notification.button_link = button_link
        notification.target_all_users = target_all_users
        notification.target_all_brokers = target_all_brokers
        notification.target_all_admins = target_all_admins
        notification.target_office_owners = target_office_owners
        notification.target_managers = target_managers
        notification.target_active_users = target_active_users
        notification.target_new_users = target_new_users
        notification.target_inactive_users = target_inactive_users
        notification.target_account_type = target_account_type
        notification.target_subscription_type = target_subscription_type
        notification.target_account_status = target_account_status
        notification.target_has_properties = target_has_properties
        notification.target_governorate = target_governorate
        notification.target_city = target_city
        notification.target_area = target_area
        notification.target_property_type = target_property_type
        notification.target_premium_brokers = target_premium_brokers
        notification.target_min_properties = int(target_min_properties) if target_min_properties else None
        notification.target_min_rating = float(target_min_rating) if target_min_rating else None
        notification.scheduled_for = scheduled_for if scheduled_for else None
        notification.expires_at = expires_at if expires_at else None
        notification.status = 'draft' if action == 'draft' else ('scheduled' if scheduled_for else 'sent')
        notification.save()
        
        # If sending immediately
        if action == 'send' and not scheduled_for:
            from .services import NotificationService
            service = NotificationService()
            service.send_notification(notification)
        
        messages.success(request, 'تم تحديث الإشعار بنجاح')
        return redirect('admin_notification_detail', notification_id=notification.id)
    
    context = {
        'notification': notification,
        'edit_mode': True,
    }
    return render(request, 'properties/admin_create_notification.html', context)


@login_required
def admin_resend_notification(request, notification_id):
    """إعادة إرسال إشعار"""
    from .models import Notification
    from .permissions import can_access_admin_panel
    
    if not can_access_admin_panel(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    
    notification = get_object_or_404(Notification, id=notification_id)
    
    # Create a copy of the notification
    new_notification = Notification.objects.create(
        title=notification.title,
        description=notification.description,
        notification_type=notification.notification_type,
        priority=notification.priority,
        delivery_type=notification.delivery_type,
        icon=notification.icon,
        color=notification.color,
        button_text=notification.button_text,
        button_link=notification.button_link,
        target_all_users=notification.target_all_users,
        target_all_brokers=notification.target_all_brokers,
        target_all_admins=notification.target_all_admins,
        target_office_owners=notification.target_office_owners,
        target_managers=notification.target_managers,
        target_active_users=notification.target_active_users,
        target_new_users=notification.target_new_users,
        target_inactive_users=notification.target_inactive_users,
        target_account_type=notification.target_account_type,
        target_subscription_type=notification.target_subscription_type,
        target_account_status=notification.target_account_status,
        target_has_properties=notification.target_has_properties,
        target_governorate=notification.target_governorate,
        target_city=notification.target_city,
        target_area=notification.target_area,
        target_property_type=notification.target_property_type,
        target_premium_brokers=notification.target_premium_brokers,
        target_min_properties=notification.target_min_properties,
        target_min_rating=notification.target_min_rating,
        created_by=request.user,
        status='sent'
    )
    
    # Send the notification
    from .services import NotificationService
    service = NotificationService()
    service.send_notification(new_notification)
    
    messages.success(request, 'تم إعادة إرسال الإشعار بنجاح')
    return redirect('admin_notification_detail', notification_id=new_notification.id)


@login_required
def admin_notification_detail(request, notification_id):
    """عرض تفاصيل إشعار للإدارة"""
    from .models import Notification, NotificationLog
    from .permissions import can_access_admin_panel
    
    if not can_access_admin_panel(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    
    notification = get_object_or_404(Notification, id=notification_id)
    logs = notification.logs.all()
    
    context = {
        'notification': notification,
        'logs': logs,
    }
    
    return render(request, 'properties/admin_notification_detail.html', context)


@login_required
def admin_send_notification(request, notification_id):
    """إرسال إشعار"""
    from .models import Notification
    from .permissions import can_access_admin_panel
    
    if not can_access_admin_panel(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    
    notification = get_object_or_404(Notification, id=notification_id)
    
    from .services import NotificationService
    service = NotificationService()
    service.send_notification(notification)
    
    messages.success(request, 'تم إرسال الإشعار بنجاح')
    return redirect('admin_notification_detail', notification_id=notification_id)


@login_required
def admin_delete_notification(request, notification_id):
    """حذف إشعار"""
    from .models import Notification
    from .permissions import can_access_admin_panel
    
    if not can_access_admin_panel(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    
    notification = get_object_or_404(Notification, id=notification_id)
    notification.delete()
    
    messages.success(request, 'تم حذف الإشعار')
    return redirect('admin_notification_panel')


@login_required
def admin_bulk_messaging(request):
    """صفحة المراسلة الجماعية للإدارة"""
    from .models import Broker, User, UserProfile
    from .permissions import can_send_to_all_brokers, can_send_to_all_users
    
    if not can_send_to_all_brokers(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('admin_panel')
    
    # الحصول على قائمة الدلالين
    brokers = Broker.objects.filter(is_active=True).select_related('user')
    
    # الحصول على قائمة المستخدمين
    users = User.objects.filter(
        is_active=True,
        broker_profile__isnull=True
    ).select_related('user_profile')
    
    if request.method == 'POST':
        message_type = request.POST.get('message_type')
        content = request.POST.get('content')
        target_type = request.POST.get('target_type')  # 'brokers', 'users', 'all'
        selected_brokers = request.POST.getlist('selected_brokers')
        selected_users = request.POST.getlist('selected_users')
        
        if not content:
            messages.error(request, 'يرجى إدخال محتوى الرسالة')
        else:
            from .models import Conversation, Message
            
            recipients = []
            
            if target_type == 'brokers' or target_type == 'all':
                if selected_brokers:
                    recipients.extend([User.objects.get(id=int(bid)) for bid in selected_brokers])
                else:
                    recipients.extend([broker.user for broker in brokers])
            
            if target_type == 'users' or target_type == 'all':
                if selected_users:
                    recipients.extend([User.objects.get(id=int(uid)) for uid in selected_users])
                else:
                    recipients.extend(list(users))
            
            # إنشاء محادثات جماعية
            for recipient in recipients:
                # التحقق من وجود محادثة سابقة
                existing_conversation = Conversation.objects.filter(
                    participants=request.user,
                    conversation_type=Conversation.TYPE_DIRECT
                ).filter(participants=recipient).first()
                
                if existing_conversation:
                    conversation = existing_conversation
                else:
                    conversation = Conversation.objects.create(
                        conversation_type=Conversation.TYPE_DIRECT,
                        created_by=request.user
                    )
                    conversation.participants.add(request.user, recipient)
                
                # إرسال الرسالة
                Message.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    recipient=recipient,
                    message_type=message_type or Message.TYPE_TEXT,
                    content=content,
                    status=Message.STATUS_SENT
                )
            
            messages.success(request, f'تم إرسال الرسالة إلى {len(recipients)} مستخدم')
            return redirect('admin_bulk_messaging')
    
    context = {
        'brokers': brokers,
        'users': users,
        'total_brokers': brokers.count(),
        'total_users': users.count(),
    }
    
    return render(request, 'properties/admin_bulk_messaging.html', context)


@login_required
def broker_bulk_messaging(request):
    """صفحة المراسلة الجماعية للدلال"""
    from .models import User, UserProfile
    from .permissions import can_send_to_all_users
    
    if not can_send_to_all_users(request.user):
        messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
        return redirect('dashboard')
    
    # الحصول على قائمة المستخدمين
    users = User.objects.filter(
        is_active=True,
        broker_profile__isnull=True
    ).select_related('user_profile')
    
    if request.method == 'POST':
        message_type = request.POST.get('message_type')
        content = request.POST.get('content')
        selected_users = request.POST.getlist('selected_users')
        
        if not content:
            messages.error(request, 'يرجى إدخال محتوى الرسالة')
        else:
            from .models import Conversation, Message
            
            recipients = []
            
            if selected_users:
                recipients.extend([User.objects.get(id=int(uid)) for uid in selected_users])
            else:
                recipients.extend(list(users))
            
            # إنشاء محادثات جماعية
            for recipient in recipients:
                # التحقق من وجود محادثة سابقة
                existing_conversation = Conversation.objects.filter(
                    participants=request.user,
                    conversation_type=Conversation.TYPE_DIRECT
                ).filter(participants=recipient).first()
                
                if existing_conversation:
                    conversation = existing_conversation
                else:
                    conversation = Conversation.objects.create(
                        conversation_type=Conversation.TYPE_DIRECT,
                        created_by=request.user
                    )
                    conversation.participants.add(request.user, recipient)
                
                # إرسال الرسالة
                Message.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    recipient=recipient,
                    message_type=message_type or Message.TYPE_TEXT,
                    content=content,
                    status=Message.STATUS_SENT
                )
            
            messages.success(request, f'تم إرسال الرسالة إلى {len(recipients)} مستخدم')
            return redirect('broker_bulk_messaging')
    
    context = {
        'users': users,
        'total_users': users.count(),
    }
    
    return render(request, 'properties/broker_bulk_messaging.html', context)


# ==================== Resort Views ====================

def resort_detail(request, slug):
    """View for resort details"""
    resort = get_object_or_404(Resort, slug=slug, status='active')
    resort.increment_views()
    
    # Get reviews
    reviews = resort.reviews.filter(is_approved=True)[:10]
    
    # Get offers
    offers = resort.offers.filter(is_active=True)
    
    # Get amenities
    amenities = resort.amenities.filter(is_available=True)
    
    # Get services
    services = resort.services.filter(is_available=True)
    
    # Check if user liked this resort
    is_liked = False
    if request.user.is_authenticated:
        is_liked = ResortLike.objects.filter(resort=resort, user=request.user).exists()
    
    # Check if user reviewed this resort
    has_reviewed = False
    if request.user.is_authenticated:
        has_reviewed = ResortReview.objects.filter(resort=resort, user=request.user).exists()
    
    context = {
        'resort': resort,
        'reviews': reviews,
        'offers': offers,
        'amenities': amenities,
        'services': services,
        'is_liked': is_liked,
        'has_reviewed': has_reviewed,
    }
    
    return render(request, 'properties/resort_detail.html', context)


@login_required
def resort_create(request):
    """View for creating a new resort"""
    if request.method == 'POST':
        name = request.POST.get('name')
        resort_type = request.POST.get('resort_type')
        description = request.POST.get('description')
        governorate = request.POST.get('governorate')
        city = request.POST.get('city')
        district = request.POST.get('district')
        full_address = request.POST.get('full_address')
        phone = request.POST.get('phone')
        whatsapp = request.POST.get('whatsapp')
        email = request.POST.get('email')
        website = request.POST.get('website')
        working_hours = request.POST.get('working_hours')
        working_days = request.POST.get('working_days')
        min_price = request.POST.get('min_price')
        max_price = request.POST.get('max_price')
        currency = request.POST.get('currency', 'د.ع')
        advance_booking = request.POST.get('advance_booking') == 'on'
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        video_url = request.POST.get('video_url')
        meta_title = request.POST.get('meta_title')
        meta_description = request.POST.get('meta_description')
        keywords = request.POST.get('keywords')
        
        resort = Resort.objects.create(
            name=name,
            resort_type=resort_type,
            description=description,
            governorate=governorate,
            city=city,
            district=district,
            full_address=full_address,
            phone=phone,
            whatsapp=whatsapp,
            email=email,
            website=website,
            working_hours=working_hours,
            working_days=working_days,
            min_price=min_price,
            max_price=max_price,
            currency=currency,
            advance_booking=advance_booking,
            latitude=latitude,
            longitude=longitude,
            video_url=video_url,
            meta_title=meta_title,
            meta_description=meta_description,
            keywords=keywords,
            broker=request.user.broker if hasattr(request.user, 'broker') else None,
            user=request.user,
        )
        
        # Handle cover image
        if 'cover_image' in request.FILES:
            resort.cover_image = request.FILES['cover_image']
        
        # Handle logo
        if 'logo' in request.FILES:
            resort.logo = request.FILES['logo']
        
        resort.save()
        
        # Add amenities
        amenities = request.POST.getlist('amenities')
        for amenity in amenities:
            ResortAmenity.objects.create(
                resort=resort,
                amenity_type=amenity,
                is_available=True
            )
        
        # Add services
        services = request.POST.getlist('services')
        for service in services:
            ResortService.objects.create(
                resort=resort,
                service_type=service,
                is_available=True
            )
        
        messages.success(request, 'تم إضافة المنتجع بنجاح')
        return redirect('resort_detail', slug=resort.slug)
    
    return render(request, 'properties/resort_form.html')


@login_required
def resort_update(request, slug):
    """View for updating a resort"""
    resort = get_object_or_404(Resort, slug=slug)
    
    # Check ownership
    if resort.broker and resort.broker.user != request.user:
        if resort.user != request.user:
            messages.error(request, 'ليس لديك صلاحية تعديل هذا المنتجع')
            return redirect('resort_detail', slug=slug)
    
    if request.method == 'POST':
        resort.name = request.POST.get('name', resort.name)
        resort.resort_type = request.POST.get('resort_type', resort.resort_type)
        resort.description = request.POST.get('description', resort.description)
        resort.governorate = request.POST.get('governorate', resort.governorate)
        resort.city = request.POST.get('city', resort.city)
        resort.district = request.POST.get('district', resort.district)
        resort.full_address = request.POST.get('full_address', resort.full_address)
        resort.phone = request.POST.get('phone', resort.phone)
        resort.whatsapp = request.POST.get('whatsapp', resort.whatsapp)
        resort.email = request.POST.get('email', resort.email)
        resort.website = request.POST.get('website', resort.website)
        resort.working_hours = request.POST.get('working_hours', resort.working_hours)
        resort.working_days = request.POST.get('working_days', resort.working_days)
        
        min_price = request.POST.get('min_price')
        if min_price:
            resort.min_price = min_price
        
        max_price = request.POST.get('max_price')
        if max_price:
            resort.max_price = max_price
        
        resort.currency = request.POST.get('currency', resort.currency)
        resort.advance_booking = request.POST.get('advance_booking') == 'on'
        
        # Handle cover image
        if 'cover_image' in request.FILES:
            resort.cover_image = request.FILES['cover_image']
        
        # Handle logo
        if 'logo' in request.FILES:
            resort.logo = request.FILES['logo']
        
        resort.save()
        
        # Update amenities
        amenities = request.POST.getlist('amenities')
        resort.amenities.all().delete()
        for amenity in amenities:
            ResortAmenity.objects.create(
                resort=resort,
                amenity_type=amenity,
                is_available=True
            )
        
        # Update services
        services = request.POST.getlist('services')
        resort.services.all().delete()
        for service in services:
            ResortService.objects.create(
                resort=resort,
                service_type=service,
                is_available=True
            )
        
        messages.success(request, 'تم تحديث المنتجع بنجاح')
        return redirect('resort_detail', slug=resort.slug)
    
    context = {
        'resort': resort,
    }
    
    return render(request, 'properties/resort_form.html', context)


@login_required
def resort_delete(request, slug):
    """View for deleting a resort"""
    resort = get_object_or_404(Resort, slug=slug)
    
    # Check ownership
    if resort.broker and resort.broker.user != request.user:
        if resort.user != request.user:
            messages.error(request, 'ليس لديك صلاحية حذف هذا المنتجع')
            return redirect('resort_detail', slug=slug)
    
    if request.method == 'POST':
        resort.delete()
        messages.success(request, 'تم حذف المنتجع بنجاح')
        return redirect('resorts_list')
    
    context = {
        'resort': resort,
    }
    
    return render(request, 'properties/resort_confirm_delete.html', context)


@login_required
def resort_booking(request, slug):
    """View for booking a resort"""
    resort = get_object_or_404(Resort, slug=slug, status='active')
    
    if request.method == 'POST':
        check_in = request.POST.get('check_in')
        check_out = request.POST.get('check_out')
        guests = request.POST.get('guests', 1)
        special_requests = request.POST.get('special_requests', '')
        
        # Calculate total price
        from datetime import datetime, timedelta
        check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
        check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
        nights = (check_out_date - check_in_date).days
        
        if nights <= 0:
            messages.error(request, 'تاريخ المغادرة يجب أن يكون بعد تاريخ الوصول')
            return redirect('resort_detail', slug=slug)
        
        # Use average price if min and max are different
        if resort.min_price and resort.max_price:
            avg_price = (resort.min_price + resort.max_price) / 2
        elif resort.min_price:
            avg_price = resort.min_price
        elif resort.max_price:
            avg_price = resort.max_price
        else:
            avg_price = 0
        
        total_price = avg_price * nights
        
        booking = ResortBooking.objects.create(
            resort=resort,
            user=request.user,
            check_in=check_in_date,
            check_out=check_out_date,
            guests=int(guests),
            total_price=total_price,
            special_requests=special_requests,
            status='pending'
        )
        
        # Create notification
        Notification.create(
            user=resort.broker.user if resort.broker else resort.user,
            notification_type='message_received',
            title='حجز جديد',
            message=f'حجز جديد للمنتجع {resort.name} من {request.user.username}',
            link=f'/resorts/{resort.slug}/bookings/'
        )
        
        messages.success(request, 'تم إرسال طلب الحجز بنجاح')
        return redirect('resort_detail', slug=slug)
    
    context = {
        'resort': resort,
    }
    
    return render(request, 'properties/resort_booking.html', context)


@login_required
def resort_review(request, slug):
    """View for adding a review to a resort"""
    resort = get_object_or_404(Resort, slug=slug, status='active')
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        
        # Check if user already reviewed
        existing_review = ResortReview.objects.filter(resort=resort, user=request.user).first()
        if existing_review:
            existing_review.rating = int(rating)
            existing_review.comment = comment
            existing_review.save()
            messages.success(request, 'تم تحديث تقييمك بنجاح')
        else:
            ResortReview.objects.create(
                resort=resort,
                user=request.user,
                rating=int(rating),
                comment=comment,
                is_approved=False
            )
            messages.success(request, 'تم إضافة تقييمك بنجاح وسيتم مراجعته')
        
        return redirect('resort_detail', slug=slug)
    
    context = {
        'resort': resort,
    }
    
    return render(request, 'properties/resort_review.html', context)


@login_required
def resort_like(request, slug):
    """View for liking/unliking a resort"""
    resort = get_object_or_404(Resort, slug=slug, status='active')
    
    like = ResortLike.objects.filter(resort=resort, user=request.user).first()
    
    if like:
        like.delete()
        resort.likes_count -= 1
        resort.save(update_fields=['likes_count'])
        return JsonResponse({'liked': False, 'likes_count': resort.likes_count})
    else:
        ResortLike.objects.create(resort=resort, user=request.user)
        return JsonResponse({'liked': True, 'likes_count': resort.likes_count})


@login_required
def resort_my_resorts(request):
    """View for user's resorts"""
    resorts = Resort.objects.filter(
        Q(broker__user=request.user) | Q(user=request.user)
    ).order_by('-created_at')
    
    context = {
        'resorts': resorts,
    }
    
    return render(request, 'properties/resort_my_resorts.html', context)


@login_required
def resort_my_bookings(request):
    """View for user's resort bookings"""
    bookings = ResortBooking.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'bookings': bookings,
    }
    
    return render(request, 'properties/resort_my_bookings.html', context)
