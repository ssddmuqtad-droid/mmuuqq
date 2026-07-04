from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Message, Property, PropertyImage, SiteSettings, Broker, BrokerJoinRequest, Office,
    PropertyRating, BrokerRating, TwoFactorAuth, SecurityLog,
    DallalGlobalSettings, BasicDallalSettings, PremiumDallalSettings,
    DallalSubscription, PropertyDallalAssignment, SubscriptionPlan, BrokerChannel
)


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = ('image', 'caption', 'sort_order', 'is_primary')


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        'display_title', 'type', 'district', 'price', 'status',
        'is_featured', 'is_promoted', 'views_count', 'created_at',
    )
    list_filter = ('type', 'status', 'district', 'is_featured', 'is_promoted', 'parking', 'furnished')
    search_fields = ('title', 'location', 'district', 'street', 'description', 'phone', 'slug')
    list_editable = ('is_featured', 'is_promoted')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('views_count', 'created_at', 'updated_at')
    inlines = [PropertyImageInline]
    list_per_page = 25

    fieldsets = (
        ('أساسي', {'fields': ('title', 'slug', 'type', 'status', 'is_featured', 'is_promoted', 'promotion_until')}),
        ('المالك والدلال', {'fields': ('owner', 'broker', 'office')}),
        ('الموقع', {'fields': ('district', 'street', 'location', 'latitude', 'longitude')}),
        ('التفاصيل', {'fields': ('area', 'price', 'bedrooms', 'bathrooms', 'floors', 'year_built', 'parking', 'furnished')}),
        ('المحتوى', {'fields': ('description', 'phone', 'image')}),
        ('إحصائيات', {'fields': ('views_count', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'property', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('name', 'message', 'email', 'phone')
    list_editable = ('is_read',)
    actions = ['mark_read', 'mark_unread']

    @admin.action(description='تعليم كمقروء')
    def mark_read(self, request, queryset):
        queryset.update(is_read=True)

    @admin.action(description='تعليم كغير مقروء')
    def mark_unread(self, request, queryset):
        queryset.update(is_read=False)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ('property', 'sort_order', 'is_primary', 'preview')
    list_filter = ('is_primary',)

    @admin.display(description='معاينة')
    def preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="80" style="border-radius:8px"/>', obj.image.url)
        return '-'

@admin.register(Broker)
class BrokerAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'role', 'phone', 'subscription_plan', 'is_verified', 'is_active')
    list_filter = ('role', 'subscription_plan', 'is_verified', 'is_active')
    search_fields = ('user__username', 'user__first_name', 'phone', 'office_name')


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'period', 'ads_limit', 'price', 'is_active')
    list_filter = ('period', 'is_active')
    search_fields = ('name',)
    list_editable = ('is_active',)


@admin.register(Office)
class OfficeAdmin(admin.ModelAdmin):
    list_display = ('name', 'governorate', 'phone', 'broker_count', 'is_active')
    search_fields = ('name', 'address')


@admin.register(BrokerJoinRequest)
class BrokerJoinRequestAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'governorate', 'office_name', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name', 'phone', 'office_name')


@admin.register(PropertyRating)
class PropertyRatingAdmin(admin.ModelAdmin):
    list_display = ('property_obj', 'user', 'rating', 'average_detailed_rating', 'is_verified', 'created_at')
    list_filter = ('rating', 'is_verified', 'created_at')
    search_fields = ('property_obj__title', 'user__username', 'review')
    readonly_fields = ('average_detailed_rating', 'created_at', 'updated_at')
    list_per_page = 25


@admin.register(BrokerRating)
class BrokerRatingAdmin(admin.ModelAdmin):
    list_display = ('broker', 'user', 'rating', 'average_detailed_rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('broker__name', 'user__username', 'review')
    readonly_fields = ('average_detailed_rating', 'created_at', 'updated_at')
    list_per_page = 25


@admin.register(TwoFactorAuth)
class TwoFactorAuthAdmin(admin.ModelAdmin):
    list_display = ('user', 'method', 'is_enabled', 'last_used', 'created_at')
    list_filter = ('method', 'is_enabled', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('secret_key', 'backup_codes', 'created_at', 'updated_at')


@admin.register(SecurityLog)
class SecurityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'ip_address', 'success', 'created_at')
    list_filter = ('action', 'success', 'created_at')
    search_fields = ('user__username', 'ip_address')
    readonly_fields = ('created_at',)
    list_per_page = 50


@admin.register(DallalGlobalSettings)
class DallalGlobalSettingsAdmin(admin.ModelAdmin):
    list_display = ('is_dallal_system_enabled', 'max_brokers_per_user', 'max_properties_per_dallal', 'show_dallal_on_homepage', 'dallal_display_order')
    fieldsets = (
        ('الإعدادات العامة', {
            'fields': ('is_dallal_system_enabled', 'max_brokers_per_user', 'max_properties_per_dallal')
        }),
        ('العرض', {
            'fields': ('show_dallal_on_homepage', 'dallal_display_order', 'show_expired_dallal')
        }),
    )

    def has_add_permission(self, request):
        return not DallalGlobalSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BasicDallalSettings)
class BasicDallalSettingsAdmin(admin.ModelAdmin):
    list_display = ('max_properties', 'duration_days', 'auto_renewal', 'impressions_limit', 'cost', 'is_enabled')
    fieldsets = (
        ('الحدود', {
            'fields': ('max_properties', 'impressions_limit')
        }),
        ('المدة والتجديد', {
            'fields': ('duration_days', 'auto_renewal')
        }),
        ('التكلفة', {
            'fields': ('cost',)
        }),
        ('التفعيل', {
            'fields': ('is_enabled',)
        }),
    )

    def has_add_permission(self, request):
        return not BasicDallalSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PremiumDallalSettings)
class PremiumDallalSettingsAdmin(admin.ModelAdmin):
    list_display = ('max_properties', 'duration_days', 'priority_display', 'impressions_limit', 'cost', 'is_enabled', 'visual_badge', 'highlight_effect')
    fieldsets = (
        ('الحدود', {
            'fields': ('max_properties', 'impressions_limit')
        }),
        ('المدة والأولوية', {
            'fields': ('duration_days', 'priority_display')
        }),
        ('التكلفة', {
            'fields': ('cost',)
        }),
        ('التفعيل', {
            'fields': ('is_enabled',)
        }),
        ('المظهر', {
            'fields': ('visual_badge', 'highlight_effect')
        }),
    )

    def has_add_permission(self, request):
        return not PremiumDallalSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DallalSubscription)
class DallalSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('broker', 'subscription_type', 'start_date', 'end_date', 'properties_used', 'impressions_count', 'is_active', 'auto_renewal')
    list_filter = ('subscription_type', 'is_active', 'auto_renewal', 'start_date', 'end_date')
    search_fields = ('broker__display_name', 'broker__user__username')
    readonly_fields = ('get_days_remaining', 'get_days_elapsed', 'get_properties_remaining', 'is_expired')
    fieldsets = (
        ('معلومات الاشتراك', {
            'fields': ('broker', 'subscription_type', 'start_date', 'end_date')
        }),
        ('الاستخدام', {
            'fields': ('properties_used', 'impressions_count')
        }),
        ('الحالة', {
            'fields': ('is_active', 'auto_renewal')
        }),
        ('معلومات إضافية', {
            'fields': ('get_days_remaining', 'get_days_elapsed', 'get_properties_remaining', 'is_expired')
        }),
    )


@admin.register(PropertyDallalAssignment)
class PropertyDallalAssignmentAdmin(admin.ModelAdmin):
    list_display = ('property', 'dallal_subscription', 'assigned_at')
    list_filter = ('assigned_at',)
    search_fields = ('property__title', 'dallal_subscription__broker__display_name')
    readonly_fields = ('assigned_at',)


@admin.register(BrokerChannel)
class BrokerChannelAdmin(admin.ModelAdmin):
    list_display = ('name', 'broker', 'status', 'is_verified', 'followers_count', 'views_count', 'created_at')
    list_filter = ('status', 'is_verified', 'created_at')
    search_fields = ('name', 'description', 'broker__display_name', 'broker__user__username')
    readonly_fields = ('properties_count', 'ads_count', 'views_count', 'followers_count', 'created_at', 'updated_at')
    list_editable = ('status', 'is_verified')
    fieldsets = (
        ('معلومات القناة', {
            'fields': ('broker', 'name', 'description', 'status', 'is_verified')
        }),
        ('الصور', {
            'fields': ('logo', 'cover_image')
        }),
        ('الإحصائيات', {
            'fields': ('followers_count', 'views_count', 'properties_count', 'ads_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )