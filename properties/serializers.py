from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Property, PropertyImage, Broker,
    Conversation, ConversationParticipant, ChatMessage,
    MessageReadStatus, MessageAttachment, MessageReport,
    ChatSettings, BlockedUser
)


class PropertyImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyImage
        fields = ['id', 'image', 'is_primary', 'sort_order']


class BrokerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Broker
        fields = ['id', 'office_name', 'phone', 'governorate', 'is_verified', 'is_active']


class PropertySerializer(serializers.ModelSerializer):
    images = PropertyImageSerializer(many=True, read_only=True)
    broker = BrokerSerializer(read_only=True)
    property_type_display = serializers.CharField(source='get_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    days_since_creation = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = [
            'id', 'title', 'slug', 'type', 'property_type_display',
            'status', 'status_display', 'district', 'street', 'location',
            'area', 'price', 'description', 'phone', 'bedrooms',
            'bathrooms', 'floors', 'year_built', 'parking', 'furnished',
            'latitude', 'longitude', 'is_featured', 'is_promoted',
            'views_count', 'created_at', 'updated_at', 'images', 'broker',
            'days_since_creation'
        ]

    def get_days_since_creation(self, obj):
        from django.utils import timezone
        delta = timezone.now() - obj.created_at
        return delta.days


class PropertyListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views"""
    primary_image = serializers.SerializerMethodField()
    property_type_display = serializers.CharField(source='get_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Property
        fields = [
            'id', 'title', 'slug', 'type', 'property_type_display',
            'status', 'status_display', 'district', 'location',
            'area', 'price', 'phone', 'bedrooms', 'bathrooms',
            'is_featured', 'is_promoted', 'views_count', 'created_at',
            'primary_image'
        ]

    def get_primary_image(self, obj):
        primary = obj.images.filter(is_primary=True).first()
        if primary:
            return primary.image.url if primary.image else None
        first = obj.images.first()
        return first.image.url if first and first.image else None


# ==================== Chat System Serializers ====================

class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']


class ConversationParticipantSerializer(serializers.ModelSerializer):
    """Serializer for conversation participants"""
    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = ConversationParticipant
        fields = ['id', 'user', 'user_id', 'role', 'nickname', 'is_muted', 'is_pinned', 'last_read_at', 'joined_at']
        read_only_fields = ['id', 'joined_at']


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer for conversations"""
    participants = ConversationParticipantSerializer(many=True, read_only=True)
    created_by = UserSerializer(read_only=True)
    unread_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'conversation_id', 'conversation_type', 'name', 'description',
            'group_avatar', 'created_by', 'is_active', 'is_archived',
            'last_message_at', 'created_at', 'updated_at', 'participants',
            'unread_count', 'last_message'
        ]
        read_only_fields = ['conversation_id', 'created_at', 'updated_at']
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.get_unread_count(request.user)
        return 0
    
    def get_last_message(self, obj):
        last_msg = obj.get_last_message()
        if last_msg:
            return ChatMessageSerializer(last_msg, context=self.context).data
        return None


class MessageAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for message attachments"""
    file_size_display = serializers.CharField(source='get_file_size_display', read_only=True)
    
    class Meta:
        model = MessageAttachment
        fields = [
            'id', 'attachment_type', 'file', 'thumbnail', 'file_name',
            'file_size', 'file_size_display', 'mime_type', 'width', 'height',
            'duration', 'uploaded_at'
        ]
        read_only_fields = ['id', 'uploaded_at']


class MessageReadStatusSerializer(serializers.ModelSerializer):
    """Serializer for message read status"""
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = MessageReadStatus
        fields = ['id', 'message', 'user', 'read_at']
        read_only_fields = ['id', 'read_at']


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for chat messages"""
    sender = UserSerializer(read_only=True)
    reply_to = serializers.SerializerMethodField()
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    read_by_users = UserSerializer(many=True, source='read_by', read_only=True)
    is_read_by_current_user = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatMessage
        fields = [
            'message_id', 'conversation', 'sender', 'message_type', 'content',
            'reply_to', 'is_edited', 'edited_at', 'is_deleted', 'deleted_at',
            'is_pinned', 'read_by_users', 'is_read_by_current_user',
            'created_at', 'updated_at', 'attachments'
        ]
        read_only_fields = ['message_id', 'created_at', 'updated_at']
    
    def get_reply_to(self, obj):
        if obj.reply_to:
            return ChatMessageSerializer(obj.reply_to, context=self.context).data
        return None
    
    def get_is_read_by_current_user(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.is_read_by_user(request.user)
        return False


class MessageReportSerializer(serializers.ModelSerializer):
    """Serializer for message reports"""
    reporter = UserSerializer(read_only=True)
    reported_user = UserSerializer(read_only=True)
    message = ChatMessageSerializer(read_only=True)
    reviewed_by = UserSerializer(read_only=True)
    
    class Meta:
        model = MessageReport
        fields = [
            'id', 'reporter', 'message', 'reported_user', 'report_type',
            'description', 'status', 'admin_notes', 'reviewed_by',
            'reviewed_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'reviewed_at', 'status']


class ChatSettingsSerializer(serializers.ModelSerializer):
    """Serializer for chat settings"""
    user = UserSerializer(read_only=True)
    blocked_users = UserSerializer(many=True, read_only=True)
    
    class Meta:
        model = ChatSettings
        fields = [
            'id', 'user', 'enable_notifications', 'enable_sound',
            'enable_typing_indicator', 'enable_read_receipts',
            'enable_online_status', 'auto_archive_days',
            'message_retention_days', 'blocked_users',
            'muted_conversations', 'theme', 'font_size',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class BlockedUserSerializer(serializers.ModelSerializer):
    """Serializer for blocked users"""
    blocker = UserSerializer(read_only=True)
    blocked = UserSerializer(read_only=True)
    
    class Meta:
        model = BlockedUser
        fields = ['id', 'blocker', 'blocked', 'reason', 'blocked_at']
        read_only_fields = ['id', 'blocked_at']


class CreateConversationSerializer(serializers.Serializer):
    """Serializer for creating a new conversation"""
    conversation_type = serializers.ChoiceField(choices=Conversation.TYPE_CHOICES)
    name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    
    def validate(self, attrs):
        if attrs['conversation_type'] == Conversation.TYPE_GROUP:
            if not attrs.get('name'):
                raise serializers.ValidationError({'name': 'اسم المجموعة مطلوب للمحادثات الجماعية'})
        return attrs


class SendMessageSerializer(serializers.Serializer):
    """Serializer for sending a message"""
    conversation_id = serializers.UUIDField()
    message_type = serializers.ChoiceField(choices=ChatMessage.TYPE_CHOICES, default=ChatMessage.TYPE_TEXT)
    content = serializers.CharField(required=False, allow_blank=True)
    reply_to_message_id = serializers.UUIDField(required=False, allow_null=True)
    
    def validate(self, attrs):
        if attrs['message_type'] == ChatMessage.TYPE_TEXT and not attrs.get('content'):
            raise serializers.ValidationError({'content': 'المحتوى مطلوب للرسائل النصية'})
        return attrs
