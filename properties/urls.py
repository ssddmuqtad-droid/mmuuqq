from django.urls import path

from . import views, api, broker_views, dallal_views
try:
    from . import api_views_enterprise as api_enterprise
except ImportError:
    api_enterprise = None

urlpatterns = [
    # Existing template-based routes
    path('', views.home, name='home'),
    path('property/<str:slug>/', views.property_detail, name='property_detail'),
    path('property/id/<int:property_id>/', views.property_detail_legacy, name='property_detail_legacy'),
    path('about/', views.about_page, name='about'),
    path('contact/', views.contact_page, name='contact'),
    path('explore/', views.explore_view, name='explore'),
    path('properties-outside-iraq/', views.properties_outside_iraq_view, name='properties_outside_iraq'),
    path('search/', views.unified_search_view, name='unified_search'),
    # Channel pages
    path('channels/', views.channels_view, name='channels'),
    path('channel/brokers/', views.channel_brokers_view, name='channel_brokers'),
    path('channel/users/', views.channel_users_view, name='channel_users'),
    path('channel/admin/', views.channel_admin_view, name='channel_admin'),
    path('channel/broker/<int:channel_id>/', views.broker_channel_detail, name='broker_channel_detail'),
    path('explore/like/<int:property_id>/', views.like_property, name='like_property'),
    path('explore/save/<int:property_id>/', views.save_property, name='save_property'),
    path('explore/unsave/<int:property_id>/', views.unsave_property, name='unsave_property'),
    
    # Dashboard routes
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/properties/', views.dashboard_properties, name='dashboard_properties'),
    path('dashboard/properties/add/', views.property_add, name='property_add'),
    path('dashboard/properties/<int:property_id>/edit/', views.property_edit, name='property_edit'),
    path('dashboard/properties/<int:property_id>/delete/', views.property_delete, name='property_delete'),
    path('dashboard/properties/<int:property_id>/toggle-featured/', views.toggle_featured, name='toggle_featured'),
    path('dashboard/properties/<int:property_id>/toggle-status/', views.toggle_property_status, name='toggle_property_status'),
    path('dashboard/properties/<int:property_id>/duplicate/', views.duplicate_property, name='duplicate_property'),
    path('dashboard/properties/<int:property_id>/images/', views.property_images, name='property_images'),
    path('dashboard/properties/<int:property_id>/images/add/', views.property_image_add, name='property_image_add'),
    path('dashboard/properties/<int:property_id>/images/<int:image_id>/delete/', views.property_image_delete, name='property_image_delete'),
    path('dashboard/properties/<int:property_id>/images/<int:image_id>/set-primary/', views.property_image_set_primary, name='property_image_set_primary'),
    path('dashboard/properties/<int:property_id>/virtual-tours/', views.property_virtual_tours, name='property_virtual_tours'),
    path('dashboard/properties/<int:property_id>/virtual-tours/add/', views.property_virtual_tour_add, name='property_virtual_tour_add'),
    path('dashboard/properties/<int:property_id>/virtual-tours/<int:tour_id>/delete/', views.property_virtual_tour_delete, name='property_virtual_tour_delete'),
    path('dashboard/properties/<int:property_id>/notes/', views.property_notes, name='property_notes'),
    path('dashboard/properties/<int:property_id>/notes/add/', views.property_note_add, name='property_note_add'),
    path('dashboard/properties/<int:property_id>/notes/<int:note_id>/delete/', views.property_note_delete, name='property_note_delete'),
    path('dashboard/properties/<int:property_id>/notes/<int:note_id>/complete/', views.property_note_complete, name='property_note_complete'),
    path('dashboard/properties/<int:property_id>/analytics/', views.property_analytics, name='property_analytics'),
    path('dashboard/settings/', views.settings_general, name='settings_general'),
    path('dashboard/settings/preferences/', views.preferences_settings, name='preferences_settings'),
    path('dashboard/settings/account/', views.account_management, name='account_management'),
    path('dashboard/user-settings/', views.settings_hub, name='settings_hub'),
    path('dashboard/activity/', views.activity_page, name='activity_page'),
    path('dashboard/bulk-messages/create/', views.bulk_message_create, name='bulk_message_create'),
    path('dashboard/bulk-messages/', views.bulk_message_list, name='bulk_message_list'),
    path('dashboard/broker-statistics/', views.broker_statistics_view, name='broker_statistics'),

    # Notifications
    path('dashboard/notifications/', broker_views.notifications_view, name='notifications'),

    # Broker system routes
    path('dashboard/broker/', broker_views.broker_panel, name='broker_panel'),
    path('dashboard/brokers/', broker_views.broker_list, name='broker_list'),
    path('dashboard/brokers/create/', broker_views.broker_create, name='broker_create'),
    path('dashboard/brokers/<int:broker_id>/edit/', broker_views.broker_edit, name='broker_edit'),
    path('dashboard/brokers/<int:broker_id>/toggle/', broker_views.broker_toggle_active, name='broker_toggle_active'),
    path('dashboard/brokers/<int:broker_id>/delete/', broker_views.broker_delete, name='broker_delete'),
    path('dashboard/brokers/<int:broker_id>/renew/', broker_views.broker_renew_subscription, name='broker_renew_subscription'),
    path('dashboard/brokers/export/', broker_views.export_brokers, name='export_brokers'),
    path('dashboard/brokers/activity-log/', broker_views.activity_log, name='activity_log'),
    path('dashboard/brokers/statistics/', broker_views.broker_statistics, name='broker_statistics_admin'),
    path('dashboard/brokers/messaging/', broker_views.broker_messaging, name='broker_messaging'),
    path('dashboard/brokers/main-panel/', views.main_broker_panel, name='main_broker_panel'),
    # Broker channel management
    path('dashboard/broker/channel/settings/', broker_views.broker_channel_settings, name='broker_channel_settings'),
    path('dashboard/broker/channel/stats/', broker_views.broker_channel_stats, name='broker_channel_stats'),
    path('dashboard/subscription-plans/', views.subscription_plans_list, name='subscription_plans_list'),
    path('dashboard/subscription-plans/create/', views.subscription_plan_create, name='subscription_plan_create'),
    path('dashboard/subscription-plans/<int:plan_id>/edit/', views.subscription_plan_edit, name='subscription_plan_edit'),
    path('dashboard/subscription-plans/<int:plan_id>/delete/', views.subscription_plan_delete, name='subscription_plan_delete'),
    path('dashboard/map/', broker_views.properties_map, name='properties_map'),
    path('dashboard/map/api/properties/', broker_views.map_api_properties, name='map_api_properties'),
    path('dashboard/map/api/nearby-places/', broker_views.map_api_nearby_places, name='map_api_nearby_places'),
    path('dashboard/map/api/directions/', broker_views.map_api_directions, name='map_api_directions'),
    path('dashboard/map/api/offices/', broker_views.map_api_offices, name='map_api_offices'),
    path('dashboard/map/api/brokers/', broker_views.map_api_brokers, name='map_api_brokers'),
    path('dashboard/map/api/favorite-areas/', broker_views.map_api_save_favorite_area, name='map_api_save_favorite_area'),
    path('dashboard/map/api/comparison/', broker_views.map_api_add_to_comparison, name='map_api_add_to_comparison'),
    path('dashboard/map/api/comparison/list/', broker_views.map_api_comparison_list, name='map_api_comparison_list'),
    path('dashboard/map/api/comparison/<int:comparison_id>/remove/', broker_views.map_api_remove_from_comparison, name='map_api_remove_from_comparison'),
    path('dashboard/map/api/update-location/', broker_views.map_api_update_property_location, name='map_api_update_property_location'),
    path('dashboard/map/api/bulk-update-coordinates/', broker_views.map_api_bulk_update_coordinates, name='map_api_bulk_update_coordinates'),
    path('dashboard/map/api/validate-coordinates/', broker_views.map_api_validate_coordinates, name='map_api_validate_coordinates'),
    path('dashboard/join-requests/', broker_views.join_requests_list, name='join_requests_list'),
    path('dashboard/join-requests/<int:request_id>/approve/', broker_views.join_request_approve, name='join_request_approve'),
    path('dashboard/join-requests/<int:request_id>/reject/', broker_views.join_request_reject, name='join_request_reject'),
    path('dashboard/office/', broker_views.office_panel, name='office_panel'),
    path('dashboard/office/presence/', broker_views.office_presence_settings, name='office_presence_settings'),
    path('dashboard/office/presence/update/', broker_views.update_presence_status, name='update_presence_status'),
    path('office/<int:office_id>/presence/', broker_views.get_office_presence, name='get_office_presence'),
    path('office/<int:office_id>/subscribe/', broker_views.subscribe_presence_notification, name='subscribe_presence_notification'),
    path('dashboard/admin/presence/', broker_views.admin_presence_dashboard, name='admin_presence_dashboard'),
    path('dashboard/admin/presence/<int:presence_id>/edit/', broker_views.admin_update_presence, name='admin_update_presence'),
    path('broker/<int:broker_id>/subscribe/', broker_views.toggle_broker_subscription, name='toggle_broker_subscription'),
    path('broker/<int:broker_id>/notification-settings/', broker_views.update_broker_notification_settings, name='update_broker_notification_settings'),
    path('subscriptions/', broker_views.user_subscriptions, name='user_subscriptions'),
    path('dashboard/broker/subscriptions/', broker_views.broker_subscription_stats, name='broker_subscription_stats'),
    path('dashboard/admin/broker-subscriptions/', broker_views.admin_broker_subscriptions, name='admin_broker_subscriptions'),
    
    # Dallal system routes
    path('dashboard/dallal/settings/', dallal_views.dallal_settings, name='dallal_settings'),
    path('dashboard/dallal/subscriptions/', dallal_views.dallal_subscriptions_list, name='dallal_subscriptions_list'),
    path('dashboard/dallal/subscriptions/create/', dallal_views.dallal_subscription_create, name='dallal_subscription_create'),
    path('dashboard/dallal/subscriptions/<int:subscription_id>/edit/', dallal_views.dallal_subscription_edit, name='dallal_subscription_edit'),
    
    # New API endpoints for Next.js frontend
    path('api/health/', api.api_health, name='api_health'),
    path('api/properties/', api.api_properties, name='api_properties'),
    path('api/property/<str:slug>/', api.api_property_detail, name='api_property_detail'),
    path('api/featured/', api.api_featured_properties, name='api_featured_properties'),
    path('api/settings/', api.api_site_settings, name='api_site_settings'),
    path('api/search/suggestions/', api.api_search_suggestions, name='api_search_suggestions'),
    path('api/statistics/', api.api_statistics, name='api_statistics'),
    path('api/subscription/expire/', views.subscription_expire_notification, name='subscription_expire_notification'),
]

# Enterprise API endpoints (only if available)
if api_enterprise:
    urlpatterns += [
        path('api/v1/system/status/', api_enterprise.api_system_status, name='api_system_status'),
        path('api/v1/system/errors/', api_enterprise.api_error_logs, name='api_error_logs'),
        path('api/v1/export/', api_enterprise.api_export_data, name='api_export_data'),
        path('api/v1/search/', api_enterprise.api_search, name='api_search'),
        path('api/v1/notifications/', api_enterprise.api_notifications, name='api_notifications'),
        path('api/v1/notifications/<int:notification_id>/read/', api_enterprise.api_mark_notification_read, name='api_mark_notification_read'),
        path('api/v1/sessions/', api_enterprise.api_sessions, name='api_sessions'),
        path('api/v1/keys/', api_enterprise.api_api_keys, name='api_api_keys'),
        path('api/v1/performance/', api_enterprise.api_performance_metrics, name='api_performance_metrics'),
    ]
