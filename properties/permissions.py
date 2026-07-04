"""نظام صلاحيات الدلالين."""

from django.db.models import Q

from .models import Broker, Property, UserProfile


SUBSCRIPTION_LIMITS = {
    'basic': 250,
    'silver': 500,
    'gold': 1000,
    'platinum': 1500,
    'diamond': 2000,
}


def get_broker(user):
    if not user or not user.is_authenticated:
        return None
    try:
        return user.broker_profile
    except Broker.DoesNotExist:
        return None


def get_user_profile(user):
    """Get user profile for regular users."""
    if not user or not user.is_authenticated:
        return None
    try:
        return user.user_profile
    except UserProfile.DoesNotExist:
        return None


def get_user_type(user):
    """Get user type: 'admin', 'broker', or 'user'."""
    if not user or not user.is_authenticated:
        return None

    # Check if superuser (admin)
    if user.is_superuser:
        return 'admin'

    # Check if broker
    broker = get_broker(user)
    if broker and broker.is_active:
        if broker.role == Broker.ROLE_ADMIN:
            return 'admin'
        return 'broker'

    # Check if regular user
    user_profile = get_user_profile(user)
    if user_profile and user_profile.is_active:
        return 'user'

    return None


def is_platform_admin(user):
    if not user or not user.is_authenticated:
        return False
    broker = get_broker(user)
    return user.is_superuser or (broker and broker.role == Broker.ROLE_ADMIN and broker.is_active)


def is_main_broker(user):
    broker = get_broker(user)
    return broker and broker.role == Broker.ROLE_MAIN and broker.is_active


def is_sub_broker(user):
    broker = get_broker(user)
    return broker and broker.role == Broker.ROLE_SUB and broker.is_active


def can_access_dashboard(user):
    if not user or not user.is_authenticated:
        return False
    # Superusers can always access
    if user.is_superuser:
        return True
    broker = get_broker(user)
    if not broker or not broker.is_active:
        return False
    return True


def can_access_admin_panel(user):
    """Check if user can access admin panel."""
    if not user or not user.is_authenticated:
        return False
    return get_user_type(user) == 'admin'


def can_access_broker_panel(user):
    """Check if user can access broker panel."""
    if not user or not user.is_authenticated:
        return False
    user_type = get_user_type(user)
    return user_type in ['admin', 'broker']


def is_regular_user(user):
    """Check if user is a regular user (not admin or broker)."""
    if not user or not user.is_authenticated:
        return False
    return get_user_type(user) == 'user'


def get_redirect_after_login(user):
    """Get redirect URL after login based on user type."""
    user_type = get_user_type(user)
    if user_type in ('admin', 'broker'):
        return 'dashboard'
    return 'home'


def can_manage_brokers(user):
    return is_platform_admin(user) or is_main_broker(user)


def can_manage_site_settings(user):
    return is_platform_admin(user)


def can_manage_join_requests(user):
    return is_platform_admin(user)


def get_managed_brokers(user):
    broker = get_broker(user)
    if not broker:
        return Broker.objects.none()
    if is_platform_admin(user):
        return Broker.objects.select_related('user', 'office', 'parent').all()
    if is_main_broker(user):
        q = Q(pk=broker.pk) | Q(parent=broker)
        if broker.office_id:
            q |= Q(office=broker.office, role=Broker.ROLE_SUB)
        return Broker.objects.filter(q).select_related('user', 'office', 'parent')
    return Broker.objects.filter(pk=broker.pk)


def get_accessible_properties(user):
    if not can_access_dashboard(user):
        return Property.objects.none()
    if is_platform_admin(user):
        return Property.objects.all()
    broker = get_broker(user)
    if not broker:
        return Property.objects.none()
    if is_main_broker(user):
        sub_ids = get_managed_brokers(user).values_list('user_id', flat=True)
        return Property.objects.filter(Q(owner_id__in=sub_ids) | Q(broker=broker))
    return Property.objects.filter(Q(owner=user) | Q(broker=broker))


def can_edit_property(user, prop):
    if is_platform_admin(user):
        return True
    if not prop:
        return False
    broker = get_broker(user)
    if not broker:
        return False
    if prop.owner_id == user.id or prop.broker_id == broker.id:
        return True
    if is_main_broker(user):
        managed = get_managed_brokers(user)
        if prop.broker_id and managed.filter(pk=prop.broker_id).exists():
            return True
        if prop.owner_id and managed.filter(user_id=prop.owner_id).exists():
            return True
    return False


def can_delete_property(user, prop):
    if is_platform_admin(user):
        return True
    if is_main_broker(user):
        return can_edit_property(user, prop)
    broker = get_broker(user)
    return broker and (prop.owner_id == user.id or prop.broker_id == broker.id)


def can_add_property(user):
    broker = get_broker(user)
    if not broker or not broker.is_active:
        return is_platform_admin(user)
    if is_platform_admin(user):
        return True
    return broker.can_add_property()


def can_replace_property(user):
    """Check if user can replace a property (delete and add without counting towards limit)."""
    broker = get_broker(user)
    if not broker or not broker.is_active:
        return is_platform_admin(user)
    if is_platform_admin(user):
        return True
    # Allow replacement if user has at least one property
    current = Property.objects.filter(Q(owner=user) | Q(broker=broker)).count()
    return current > 0


def can_view_activity_log(user):
    """Check if user can view activity log."""
    return is_platform_admin(user) or is_main_broker(user)


def can_view_statistics(user):
    """Check if user can view statistics."""
    return is_platform_admin(user) or is_main_broker(user)


def can_send_messages(user):
    """Check if user can send messages."""
    broker = get_broker(user)
    return broker and broker.is_active


def can_manage_notifications(user):
    """Check if user can manage notifications."""
    return user.is_authenticated


def can_export_data(user):
    """Check if user can export data."""
    return is_platform_admin(user) or is_main_broker(user)


def get_accessible_messages(user):
    from .models import Message

    if is_platform_admin(user):
        return Message.objects.all()
    broker = get_broker(user)
    if not broker:
        return Message.objects.none()
    props = get_accessible_properties(user)
    return Message.objects.filter(property__in=props)


def get_broker_stats(user):
    props = get_accessible_properties(user)
    messages = get_accessible_messages(user)
    brokers = get_managed_brokers(user)

    sold = props.filter(status='sold').count()
    rent = props.filter(status='rent').count()
    investment = props.filter(status='investment').count()
    total_views = sum(props.values_list('views_count', flat=True))

    stats = {
        'total_properties': props.count(),
        'featured_properties': props.filter(is_featured=True).count(),
        'total_brokers': brokers.count(),
        'total_views': total_views,
        'unread_messages': messages.filter(is_read=False, is_archived=False).count(),
        'sold_properties': sold,
        'rent_properties': rent,
        'investment_properties': investment,
        'pending_join_requests': 0,
    }

    if can_manage_join_requests(user):
        from .models import BrokerJoinRequest
        stats['pending_join_requests'] = BrokerJoinRequest.objects.filter(
            status=BrokerJoinRequest.STATUS_PENDING
        ).count()

    broker = get_broker(user)
    if broker:
        from .models import FinancialTransaction, BuildingRequest, Expense
        # Financial stats
        commissions = FinancialTransaction.objects.filter(
            user=user, transaction_type='commission', status='completed'
        )
        stats['total_commissions'] = sum(
            c.commission_amount or 0 for c in commissions
        )
        stats['subscription_plan'] = broker.subscription_plan.name if broker.subscription_plan else 'غير مشترك'
        stats['property_limit'] = broker.subscription_plan.ads_limit if broker.subscription_plan else 0
        stats['properties_used'] = Property.objects.filter(
            Q(owner=user) | Q(broker=broker)
        ).count()
        stats['is_verified'] = broker.is_verified
        
        # Subscription stats
        stats['subscription_status'] = broker.get_subscription_status()
        stats['subscription_status_display'] = broker.get_subscription_status_display()
        stats['days_remaining'] = broker.get_days_remaining()
        stats['days_elapsed'] = broker.get_days_elapsed()
        stats['remaining_properties'] = broker.get_remaining_properties()
        
        # Building requests stats
        building_requests = BuildingRequest.objects.filter(user=user)
        stats['total_building_requests'] = building_requests.count()
        stats['pending_building_requests'] = building_requests.filter(status='pending').count()
        stats['in_progress_building_requests'] = building_requests.filter(status='in_progress').count()
        stats['completed_building_requests'] = building_requests.filter(status='completed').count()
        
        # Expenses stats
        expenses = Expense.objects.filter(user=user)
        stats['total_expenses'] = sum(e.amount or 0 for e in expenses)
        stats['total_expenses_count'] = expenses.count()

    return stats
