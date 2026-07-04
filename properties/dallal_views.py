"""views لإدارة نظام الدلال"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .decorators import broker_required, manage_brokers_required
from .models import (
    DallalGlobalSettings, BasicDallalSettings, PremiumDallalSettings,
    DallalSubscription, PropertyDallalAssignment
)
from .permissions import is_platform_admin


@login_required
@manage_brokers_required
def dallal_settings(request):
    """صفحة إعدادات نظام الدلال"""
    if not is_platform_admin(request.user):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    
    global_settings = DallalGlobalSettings.get_settings()
    basic_settings = BasicDallalSettings.get_settings()
    premium_settings = PremiumDallalSettings.get_settings()
    
    if request.method == 'POST':
        # تحديث الإعدادات العامة
        if 'update_global' in request.POST:
            global_settings.is_dallal_system_enabled = request.POST.get('is_dallal_system_enabled') == 'on'
            global_settings.max_brokers_per_user = int(request.POST.get('max_brokers_per_user', 1))
            global_settings.max_properties_per_dallal = int(request.POST.get('max_properties_per_dallal', 100))
            global_settings.show_dallal_on_homepage = request.POST.get('show_dallal_on_homepage') == 'on'
            global_settings.dallal_display_order = request.POST.get('dallal_display_order', 'premium_first')
            global_settings.show_expired_dallal = request.POST.get('show_expired_dallal') == 'on'
            global_settings.save()
            messages.success(request, 'تم تحديث الإعدادات العامة')
        
        # تحديث إعدادات الدلال العادي
        elif 'update_basic' in request.POST:
            basic_settings.max_properties = int(request.POST.get('max_properties', 20))
            basic_settings.duration_days = int(request.POST.get('duration_days', 30))
            basic_settings.auto_renewal = request.POST.get('auto_renewal') == 'on'
            basic_settings.impressions_limit = int(request.POST.get('impressions_limit', 1000))
            basic_settings.cost = float(request.POST.get('cost', 0))
            basic_settings.is_enabled = request.POST.get('is_enabled') == 'on'
            basic_settings.save()
            messages.success(request, 'تم تحديث إعدادات الدلال العادي')
        
        # تحديث إعدادات الدلال المميز
        elif 'update_premium' in request.POST:
            premium_settings.max_properties = int(request.POST.get('max_properties', 100))
            premium_settings.duration_days = int(request.POST.get('duration_days', 90))
            premium_settings.priority_display = request.POST.get('priority_display') == 'on'
            premium_settings.impressions_limit = int(request.POST.get('impressions_limit', 5000))
            premium_settings.cost = float(request.POST.get('cost', 0))
            premium_settings.is_enabled = request.POST.get('is_enabled') == 'on'
            premium_settings.visual_badge = request.POST.get('visual_badge') == 'on'
            premium_settings.highlight_effect = request.POST.get('highlight_effect') == 'on'
            premium_settings.save()
            messages.success(request, 'تم تحديث إعدادات الدلال المميز')
        
        return redirect('dallal_settings')
    
    # الحصول على إحصائيات الاشتراكات
    basic_subscriptions = DallalSubscription.objects.filter(subscription_type='basic')
    premium_subscriptions = DallalSubscription.objects.filter(subscription_type='premium')
    
    stats = {
        'basic_active': basic_subscriptions.filter(is_active=True).count(),
        'basic_expired': basic_subscriptions.filter(is_active=False).count(),
        'premium_active': premium_subscriptions.filter(is_active=True).count(),
        'premium_expired': premium_subscriptions.filter(is_active=False).count(),
    }
    
    return render(request, 'properties/dallal_settings.html', {
        'global_settings': global_settings,
        'basic_settings': basic_settings,
        'premium_settings': premium_settings,
        'stats': stats,
    })


@login_required
@manage_brokers_required
def dallal_subscriptions_list(request):
    """قائمة اشتراكات الدلال"""
    if not is_platform_admin(request.user):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    
    subscriptions = DallalSubscription.objects.select_related('broker').all()
    
    return render(request, 'properties/dallal_subscriptions_list.html', {
        'subscriptions': subscriptions,
    })


@login_required
@manage_brokers_required
@require_http_methods(['GET', 'POST'])
def dallal_subscription_create(request):
    """إنشاء اشتراك دلال جديد"""
    if not is_platform_admin(request.user):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    
    from .dallal_forms import DallalSubscriptionForm
    
    if request.method == 'POST':
        form = DallalSubscriptionForm(request.POST)
        if form.is_valid():
            subscription = form.save()
            messages.success(request, f'تم إنشاء اشتراك {subscription.get_subscription_type_display()}')
            return redirect('dallal_subscriptions_list')
    else:
        form = DallalSubscriptionForm()
    
    return render(request, 'properties/dallal_subscription_form.html', {
        'form': form,
        'title': 'إنشاء اشتراك دلال',
    })


@login_required
@manage_brokers_required
@require_http_methods(['GET', 'POST'])
def dallal_subscription_edit(request, subscription_id):
    """تعديل اشتراك دلال"""
    if not is_platform_admin(request.user):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('dashboard')
    
    subscription = DallalSubscription.objects.get(pk=subscription_id)
    
    from .dallal_forms import DallalSubscriptionForm
    
    if request.method == 'POST':
        form = DallalSubscriptionForm(request.POST, instance=subscription)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث الاشتراك')
            return redirect('dallal_subscriptions_list')
    else:
        form = DallalSubscriptionForm(instance=subscription)
    
    return render(request, 'properties/dallal_subscription_form.html', {
        'form': form,
        'title': 'تعديل اشتراك دلال',
        'subscription': subscription,
    })
