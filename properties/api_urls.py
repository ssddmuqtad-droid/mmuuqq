from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from .api_views import PropertyViewSet
from .chat_views import (
    ConversationViewSet, ChatMessageViewSet,
    MessageAttachmentViewSet, MessageReportViewSet,
    ChatSettingsViewSet, BlockedUserViewSet,
    user_list
)


schema_view = get_schema_view(
    openapi.Info(
        title="دلال API",
        default_version='v1',
        description="API للعقارات العراقية - تصفح حسب المحافظة",
        terms_of_service="https://www.daluailiraq.com/terms/",
        contact=openapi.Contact(email="info@daluailiraq.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

router = DefaultRouter()
router.register(r'properties', PropertyViewSet, basename='property')

# Chat System Routes
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'messages', ChatMessageViewSet, basename='chatmessage')
router.register(r'attachments', MessageAttachmentViewSet, basename='messageattachment')
router.register(r'reports', MessageReportViewSet, basename='messagereport')
router.register(r'chat-settings', ChatSettingsViewSet, basename='chatsettings')
router.register(r'blocked-users', BlockedUserViewSet, basename='blockeduser')

urlpatterns = [
    path('users/', user_list, name='user-list'),
    path('', include(router.urls)),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
