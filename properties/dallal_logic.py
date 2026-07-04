"""منطق التحكم في نظام الدلال"""

from django.db.models import Q
from .models import (
    DallalGlobalSettings, BasicDallalSettings, PremiumDallalSettings,
    DallalSubscription, PropertyDallalAssignment
)


def get_dallal_global_settings():
    """الحصول على الإعدادات العامة للدلال"""
    return DallalGlobalSettings.get_settings()


def is_dallal_system_enabled():
    """التحقق من تفعيل نظام الدلال"""
    settings = get_dallal_global_settings()
    return settings.is_dallal_system_enabled


def get_basic_dallal_settings():
    """الحصول على إعدادات الدلال العادي"""
    return BasicDallalSettings.get_settings()


def get_premium_dallal_settings():
    """الحصول على إعدادات الدلال المميز"""
    return PremiumDallalSettings.get_settings()


def get_active_dallal_subscriptions(broker=None):
    """الحصول على اشتراكات الدلال النشطة"""
    subscriptions = DallalSubscription.objects.filter(is_active=True)
    if broker:
        subscriptions = subscriptions.filter(broker=broker)
    return subscriptions


def get_expired_dallal_subscriptions(broker=None):
    """الحصول على اشتراكات الدلال المنتهية"""
    subscriptions = DallalSubscription.objects.filter(is_active=False)
    if broker:
        subscriptions = subscriptions.filter(broker=broker)
    return subscriptions


def get_broker_dallal_subscriptions(broker):
    """الحصول على جميع اشتراكات الدلال لدلال معين"""
    return DallalSubscription.objects.filter(broker=broker)


def can_broker_have_dallal_subscription(broker, subscription_type):
    """التحقق من إمكانية الدلال الحصول على اشتراك"""
    global_settings = get_dallal_global_settings()
    
    if not is_dallal_system_enabled():
        return False, 'نظام الدلال غير مفعل'
    
    if subscription_type == 'basic' and not get_basic_dallal_settings().is_enabled:
        return False, 'الدلال العادي غير مفعل'
    
    if subscription_type == 'premium' and not get_premium_dallal_settings().is_enabled:
        return False, 'الدلال المميز غير مفعل'
    
    # التحقق من الحد الأقصى للدلالات لكل مستخدم
    current_subscriptions = get_broker_dallal_subscriptions(broker).count()
    if current_subscriptions >= global_settings.max_brokers_per_user:
        return False, 'وصلت للحد الأقصى من الاشتراكات'
    
    return True, 'يمكن إنشاء اشتراك'


def can_add_property_to_dallal_subscription(subscription):
    """التحقق من إمكانية إضافة عقار لاشتراك"""
    if not subscription.is_active:
        return False, 'الاشتراك غير نشط'
    
    remaining = subscription.get_properties_remaining()
    if remaining <= 0:
        return False, 'وصلت للحد الأقصى من العقارات'
    
    return True, 'يمكن إضافة عقار'


def assign_property_to_dallal_subscription(property_obj, subscription):
    """ربط عقار باشتراك دلال"""
    can_add, message = can_add_property_to_dallal_subscription(subscription)
    if not can_add:
        return False, message
    
    # إنشاء الربط
    assignment = PropertyDallalAssignment.objects.create(
        property=property_obj,
        dallal_subscription=subscription
    )
    
    # تحديث عداد العقارات المستخدمة
    subscription.properties_used += 1
    subscription.save()
    
    return True, 'تم ربط العقار بنجاح'


def get_property_dallal_subscription(property_obj):
    """الحصول على اشتراك الدلال للعقار"""
    try:
        assignment = PropertyDallalAssignment.objects.get(property=property_obj)
        return assignment.dallal_subscription
    except PropertyDallalAssignment.DoesNotExist:
        return None


def get_dallal_properties_for_display():
    """الحصول على العقارات المرتبطة بالدلال للعرض"""
    global_settings = get_dallal_global_settings()
    
    if not global_settings.show_dallal_on_homepage:
        return []
    
    if not is_dallal_system_enabled():
        return []
    
    # الحصول على الاشتراكات النشطة
    active_subscriptions = get_active_dallal_subscriptions()
    
    if not global_settings.show_expired_dallal:
        active_subscriptions = active_subscriptions.filter(is_active=True)
    
    # ترتيب حسب نوع الاشتراك
    if global_settings.dallal_display_order == 'premium_first':
        active_subscriptions = active_subscriptions.order_by(
            '-subscription_type',  # premium أولاً
            '-start_date'
        )
    elif global_settings.dallal_display_order == 'basic_first':
        active_subscriptions = active_subscriptions.order_by(
            'subscription_type',  # basic أولاً
            '-start_date'
        )
    else:  # mixed
        active_subscriptions = active_subscriptions.order_by('-start_date')
    
    # الحصول على العقارات
    property_ids = PropertyDallalAssignment.objects.filter(
        dallal_subscription__in=active_subscriptions
    ).values_list('property_id', flat=True)
    
    from .models import Property
    return Property.objects.filter(id__in=property_ids)


def increment_dallal_impressions(subscription):
    """زيادة عداد الظهور لاشتراك"""
    subscription.impressions_count += 1
    subscription.save()
    
    # التحقق من الوصول للحد الأقصى
    if subscription.subscription_type == 'basic':
        settings = get_basic_dallal_settings()
    else:
        settings = get_premium_dallal_settings()
    
    if subscription.impressions_count >= settings.impressions_limit:
        subscription.is_active = False
        subscription.save()
        return False, 'وصلت للحد الأقصى للظهور'
    
    return True, 'تم زيادة العداد'


def deactivate_expired_subscriptions():
    """إيقاف الاشتراكات المنتهية تلقائياً"""
    subscriptions = DallalSubscription.objects.filter(is_active=True)
    count = 0
    
    for subscription in subscriptions:
        if subscription.is_expired():
            subscription.deactivate_if_expired()
            count += 1
    
    return count


def get_dallal_statistics():
    """الحصول على إحصائيات نظام الدلال"""
    basic_settings = get_basic_dallal_settings()
    premium_settings = get_premium_dallal_settings()
    
    basic_subscriptions = DallalSubscription.objects.filter(subscription_type='basic')
    premium_subscriptions = DallalSubscription.objects.filter(subscription_type='premium')
    
    return {
        'basic': {
            'enabled': basic_settings.is_enabled,
            'max_properties': basic_settings.max_properties,
            'duration_days': basic_settings.duration_days,
            'active_count': basic_subscriptions.filter(is_active=True).count(),
            'expired_count': basic_subscriptions.filter(is_active=False).count(),
            'total_count': basic_subscriptions.count(),
        },
        'premium': {
            'enabled': premium_settings.is_enabled,
            'max_properties': premium_settings.max_properties,
            'duration_days': premium_settings.duration_days,
            'active_count': premium_subscriptions.filter(is_active=True).count(),
            'expired_count': premium_subscriptions.filter(is_active=False).count(),
            'total_count': premium_subscriptions.count(),
        },
        'global': {
            'enabled': is_dallal_system_enabled(),
            'max_brokers_per_user': get_dallal_global_settings().max_brokers_per_user,
            'show_on_homepage': get_dallal_global_settings().show_dallal_on_homepage,
        }
    }
