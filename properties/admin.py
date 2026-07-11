from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Message, Property, PropertyImage, SiteSettings, Broker, BrokerJoinRequest, Office,
    PropertyRating, BrokerRating, TwoFactorAuth, SecurityLog,
    DallalGlobalSettings, BasicDallalSettings, PremiumDallalSettings,
    DallalSubscription, PropertyDallalAssignment, SubscriptionPlan, BrokerChannel,
    Conversation, MessageAttachment, MessageReaction, MessageReport,
    Country, City, Area, LiveStream, LiveStreamComment, PropertyVideo, PropertyDocument,
    PropertyMediaStats, PropertyViewStats, PropertyEngagementStats, PropertyConversionStats,
    AdvancedSubscriptionPlan, BrokerPlanSubscription, SubscriptionRenewalRequest,
    BuildingRequestSubscription, AuctionSubscription, Role, UserRole, PermissionLog
)


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = ('image', 'caption', 'sort_order', 'is_primary', 'image_type')


class PropertyVideoInline(admin.TabularInline):
    model = PropertyVideo
    extra = 1
    fields = ('video', 'caption', 'sort_order', 'video_type', 'duration')


class PropertyDocumentInline(admin.TabularInline):
    model = PropertyDocument
    extra = 1
    fields = ('document_type', 'title', 'file', 'description')


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        'display_title', 'type', 'district', 'price', 'status',
        'is_featured', 'is_promoted', 'views_count', 'created_at',
    )
    list_filter = ('type', 'status', 'category', 'governorate', 'is_featured', 'is_promoted', 'parking', 'furnished')
    search_fields = ('title', 'location', 'district', 'street', 'description', 'phone', 'slug', 'property_number')
    list_editable = ('is_featured', 'is_promoted')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('views_count', 'created_at', 'updated_at', 'short_share_code')
    inlines = [PropertyImageInline, PropertyVideoInline, PropertyDocumentInline]
    list_per_page = 25

    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('title', 'slug', 'property_number', 'category', 'type', 'status', 
                      'is_featured', 'is_promoted', 'promotion_until', 'publication_type')
        }),
        ('المالك والدلال', {
            'fields': ('owner', 'owner_name', 'broker', 'office')
        }),
        ('الموقع داخل العراق', {
            'fields': ('governorate', 'city', 'district', 'subdistrict', 'nahiyah', 
                      'street', 'landmark', 'location')
        }),
        ('الموقع خارج العراق', {
            'fields': ('country', 'city_outside', 'area_outside', 'postal_code',
                      'taxes', 'registration_fees', 'foreign_ownership_laws'),
            'classes': ('collapse',)
        }),
        ('الإحداثيات', {
            'fields': ('latitude', 'longitude', 'nearest_landmark', 
                      'distance_to_city_center', 'distance_to_airport')
        }),
        ('السعر والعملة', {
            'fields': ('price', 'currency', 'original_price', 'negotiable')
        }),
        ('المساحة والبناء', {
            'fields': ('total_area', 'building_area', 'area', 'facade', 'direction', 
                      'year_built', 'building_condition', 'total_floors', 'floor_number',
                      'property_age', 'last_renovation')
        }),
        ('الغرف والمرافق', {
            'fields': ('bedrooms', 'living_rooms', 'dining_rooms', 'bathrooms', 
                      'kitchens', 'balconies', 'parking_spaces', 'parking_type')
        }),
        ('المرافق الأساسية', {
            'fields': ('parking', 'furnished', 'has_pool', 'has_garden', 'has_elevator', 
                      'has_generator', 'has_national_electricity', 'has_water', 'has_internet', 
                      'has_sewerage', 'has_heating', 'has_cooling', 'has_solar_power')
        }),
        ('الأمان', {
            'fields': ('has_security_system', 'has_cctv', 'has_alarm'),
            'classes': ('collapse',)
        }),
        ('معلومات الفنادق والمنتجعات', {
            'fields': ('hotel_stars', 'hotel_rating', 'hotel_rooms', 'hotel_suites', 
                      'hotel_family_rooms', 'has_restaurant', 'has_cafe', 'has_swimming_pool', 
                      'has_gym', 'has_spa', 'has_conference_hall', 'has_wifi', 'has_parking', 
                      'has_room_service', 'has_laundry', 'has_airport_shuttle'),
            'classes': ('collapse',)
        }),
        ('معلومات المنتجعات السياحية', {
            'fields': ('resort_capacity', 'resort_activities', 'booking_available', 
                      'booking_url', 'min_booking_duration', 'max_booking_duration'),
            'classes': ('collapse',)
        }),
        ('الجولات الافتراضية والوسائط', {
            'fields': ('virtual_tour_url', 'vr_tour_url', 'ar_available', 'qr_code', 
                      'short_share_code'),
            'classes': ('collapse',)
        }),
        ('البث المباشر', {
            'fields': ('live_stream_enabled', 'live_stream_url', 'live_stream_scheduled', 
                      'live_stream_status'),
            'classes': ('collapse',)
        }),
        ('الذكاء الاصطناعي', {
            'fields': ('ai_generated_description', 'ai_suggested_price', 'ai_keywords', 
                      'ai_image_enhanced'),
            'classes': ('collapse',)
        }),
        ('الرسوم الإضافية', {
            'fields': ('maintenance_fee', 'hoa_fee'),
            'classes': ('collapse',)
        }),
        ('إمكانية الوصول', {
            'fields': ('wheelchair_accessible', 'has_ramp', 'has_elevator_accessibility'),
            'classes': ('collapse',)
        }),
        ('الميزات الخضراء', {
            'fields': ('energy_efficient', 'has_green_building_cert', 'has_smart_home', 
                      'has_double_glazing', 'has_insulation'),
            'classes': ('collapse',)
        }),
        ('الإطلالة', {
            'fields': ('view_type',)
        }),
        ('المحتوى', {
            'fields': ('description', 'phone')
        }),
        ('إحصائيات', {
            'fields': ('views_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_participants', 'created_at', 'updated_at')
    search_fields = ('participants__username',)
    
    def get_participants(self, obj):
        return ', '.join([p.username for p in obj.participants.all()])
    get_participants.short_description = 'المشاركون'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'recipient', 'message_type', 'status', 'is_read', 'created_at')
    list_filter = ('message_type', 'status', 'is_read', 'created_at')
    search_fields = ('content', 'sender__username', 'recipient__username')
    list_editable = ('is_read',)
    actions = ['mark_read', 'mark_unread']

    @admin.action(description='تعليم كمقروء')
    def mark_read(self, request, queryset):
        queryset.update(is_read=True)

    @admin.action(description='تعليم كغير مقروء')
    def mark_unread(self, request, queryset):
        queryset.update(is_read=False)


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ('message', 'attachment_type', 'file_name', 'file_size')
    list_filter = ('attachment_type',)
    search_fields = ('file_name', 'message__content')


@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    list_display = ('message', 'user', 'reaction_type', 'created_at')
    list_filter = ('reaction_type', 'created_at')
    search_fields = ('user__username', 'message__content')


@admin.register(MessageReport)
class MessageReportAdmin(admin.ModelAdmin):
    list_display = ('message', 'reporter', 'report_type', 'status', 'created_at')
    list_filter = ('report_type', 'status', 'created_at')
    search_fields = ('reporter__username', 'description')
    list_editable = ('status',)


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


@admin.register(AdvancedSubscriptionPlan)
class AdvancedSubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_type', 'tier', 'price_per_day', 'max_properties', 'is_active')
    list_filter = ('plan_type', 'tier', 'is_active')
    search_fields = ('name',)
    list_editable = ('is_active',)


@admin.register(BrokerPlanSubscription)
class BrokerPlanSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('broker', 'plan', 'start_date', 'end_date', 'status', 'properties_used', 'get_seconds_remaining')
    list_filter = ('status', 'plan__plan_type', 'plan__tier')
    search_fields = ('broker__display_name', 'plan__name')
    readonly_fields = ('get_seconds_remaining', 'created_at', 'updated_at')
    
    def get_seconds_remaining(self, obj):
        return obj.get_seconds_remaining()
    get_seconds_remaining.short_description = 'الثواني المتبقية'


@admin.register(SubscriptionRenewalRequest)
class SubscriptionRenewalRequestAdmin(admin.ModelAdmin):
    list_display = ('broker', 'plan', 'days_requested', 'estimated_cost', 'status', 'created_at')
    list_filter = ('status', 'plan__plan_type')
    search_fields = ('broker__display_name', 'plan__name')
    list_editable = ('status',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(BuildingRequestSubscription)
class BuildingRequestSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('broker', 'annual_price', 'start_date', 'end_date', 'status', 'requests_used', 'max_requests')
    list_filter = ('status',)
    search_fields = ('broker__display_name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AuctionSubscription)
class AuctionSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('broker', 'price_per_auction', 'status', 'auctions_used', 'auctions_paid', 'total_paid')
    list_filter = ('status',)
    search_fields = ('broker__display_name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'priority', 'is_active')
    list_filter = ('is_active', 'priority')
    search_fields = ('name', 'display_name')
    list_editable = ('is_active',)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'assigned_at', 'expires_at', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('user__username', 'role__display_name')
    readonly_fields = ('assigned_at',)


@admin.register(PermissionLog)
class PermissionLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'action', 'performed_by', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('user__username', 'role__display_name')
    readonly_fields = ('created_at',)


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
    readonly_fields = ('properties_count', 'views_count', 'followers_count', 'created_at', 'updated_at')
    list_editable = ('status', 'is_verified')
    fieldsets = (
        ('معلومات القناة', {
            'fields': ('broker', 'name', 'description', 'status', 'is_verified')
        }),
        ('الصور', {
            'fields': ('logo', 'cover_image')
        }),
        ('الإحصائيات', {
            'fields': ('followers_count', 'views_count', 'properties_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('name_ar', 'name_en', 'code', 'currency_code', 'is_active')
    search_fields = ('name_ar', 'name_en', 'code')
    list_filter = ('is_active', 'currency_code')


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('name_ar', 'name_en', 'country', 'governorate_state', 'is_active')
    search_fields = ('name_ar', 'name_en', 'country__name_ar')
    list_filter = ('country', 'is_active')


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ('name_ar', 'name_en', 'city', 'is_active')
    search_fields = ('name_ar', 'name_en', 'city__name_ar')
    list_filter = ('city', 'is_active')


@admin.register(LiveStream)
class LiveStreamAdmin(admin.ModelAdmin):
    list_display = ('title', 'property', 'broker', 'status', 'scheduled_start', 'viewers_count')
    list_filter = ('status', 'platform', 'scheduled_start')
    search_fields = ('title', 'description', 'property__title', 'broker__display_name')
    readonly_fields = ('actual_start', 'actual_end', 'created_at', 'updated_at')
    list_editable = ('status',)
    actions = ['start_streams', 'end_streams', 'cancel_streams']

    @admin.action(description='بدء البث المباشر')
    def start_streams(self, request, queryset):
        for stream in queryset.filter(status='scheduled'):
            stream.start_stream()
        self.message_user(request, f'تم بدء {queryset.count()} بث مباشر')

    @admin.action(description='إنهاء البث المباشر')
    def end_streams(self, request, queryset):
        for stream in queryset.filter(status='live'):
            stream.end_stream()
        self.message_user(request, f'تم إنهاء {queryset.count()} بث مباشر')

    @admin.action(description='إلغاء البث المباشر')
    def cancel_streams(self, request, queryset):
        for stream in queryset.filter(status__in=['scheduled', 'live']):
            stream.cancel_stream()
        self.message_user(request, f'تم إلغاء {queryset.count()} بث مباشر')


@admin.register(LiveStreamComment)
class LiveStreamCommentAdmin(admin.ModelAdmin):
    list_display = ('author_name', 'live_stream', 'comment', 'created_at')
    list_filter = ('created_at', 'live_stream')
    search_fields = ('author_name', 'comment', 'live_stream__title')


@admin.register(PropertyVideo)
class PropertyVideoAdmin(admin.ModelAdmin):
    list_display = ('property', 'video_type', 'sort_order', 'duration', 'created_at')
    list_filter = ('video_type', 'created_at')
    search_fields = ('property__title', 'caption')


@admin.register(PropertyDocument)
class PropertyDocumentAdmin(admin.ModelAdmin):
    list_display = ('property', 'document_type', 'title', 'created_at')
    list_filter = ('document_type', 'created_at')
    search_fields = ('property__title', 'title', 'description')


@admin.register(PropertyMediaStats)
class PropertyMediaStatsAdmin(admin.ModelAdmin):
    list_display = ('property', 'total_images', 'total_videos', 'total_360_tours', 'updated_at')
    search_fields = ('property__title',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PropertyViewStats)
class PropertyViewStatsAdmin(admin.ModelAdmin):
    list_display = ('property', 'total_views', 'unique_views', 'views_today', 'updated_at')
    search_fields = ('property__title',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PropertyEngagementStats)
class PropertyEngagementStatsAdmin(admin.ModelAdmin):
    list_display = ('property', 'total_favorites', 'total_shares', 'total_calls', 'updated_at')
    search_fields = ('property__title',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PropertyConversionStats)
class PropertyConversionStatsAdmin(admin.ModelAdmin):
    list_display = ('property', 'total_leads', 'total_appointments', 'total_sales', 'updated_at')
    search_fields = ('property__title',)
    readonly_fields = ('created_at', 'updated_at')