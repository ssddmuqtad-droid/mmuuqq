"""
Chat System API Views
Real-time messaging system views using Django REST Framework
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.db.models import Q, F
from django.utils import timezone

from .models import (
    Conversation, ConversationParticipant, ChatMessage,
    MessageReadStatus, MessageAttachment, MessageReport,
    ChatSettings, BlockedUser
)
from .serializers import (
    ConversationSerializer, ConversationParticipantSerializer,
    ChatMessageSerializer, MessageAttachmentSerializer,
    MessageReportSerializer, ChatSettingsSerializer,
    BlockedUserSerializer, CreateConversationSerializer,
    SendMessageSerializer, UserSerializer
)
from .permissions import can_access_dashboard


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_list(request):
    """Get list of users for creating conversations"""
    users = User.objects.filter(is_active=True).exclude(id=request.user.id)
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)


class ConversationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing conversations"""
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Get conversations for the current user"""
        user = self.request.user
        return Conversation.objects.filter(
            participants=user
        ).select_related('created_by').prefetch_related('participants_info__user')
    
    def perform_create(self, serializer):
        """Create a new conversation"""
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['post'])
    def create_conversation(self, request):
        """Create a new conversation with participants"""
        serializer = CreateConversationSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            
            # Create conversation
            conversation = Conversation.objects.create(
                conversation_type=data['conversation_type'],
                name=data.get('name', ''),
                description=data.get('description', ''),
                created_by=request.user
            )
            
            # Add participants
            participant_ids = data['participant_ids']
            # Include the creator
            if request.user.id not in participant_ids:
                participant_ids.append(request.user.id)
            
            for user_id in participant_ids:
                try:
                    user = User.objects.get(id=user_id)
                    role = ConversationParticipant.ROLE_ADMIN if user == request.user else ConversationParticipant.ROLE_MEMBER
                    ConversationParticipant.objects.create(
                        conversation=conversation,
                        user=user,
                        role=role
                    )
                except User.DoesNotExist:
                    continue
            
            return Response(
                ConversationSerializer(conversation, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark all messages in conversation as read"""
        conversation = self.get_object()
        conversation.mark_as_read_for_user(request.user)
        return Response({'status': 'marked as read'})
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive a conversation"""
        conversation = self.get_object()
        conversation.is_archived = True
        conversation.save()
        return Response({'status': 'archived'})
    
    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        """Unarchive a conversation"""
        conversation = self.get_object()
        conversation.is_archived = False
        conversation.save()
        return Response({'status': 'unarchived'})
    
    @action(detail=True, methods=['post'])
    def pin(self, request, pk=None):
        """Pin a conversation"""
        participant = get_object_or_404(
            ConversationParticipant,
            conversation=pk,
            user=request.user
        )
        participant.is_pinned = True
        participant.save()
        return Response({'status': 'pinned'})
    
    @action(detail=True, methods=['post'])
    def unpin(self, request, pk=None):
        """Unpin a conversation"""
        participant = get_object_or_404(
            ConversationParticipant,
            conversation=pk,
            user=request.user
        )
        participant.is_pinned = False
        participant.save()
        return Response({'status': 'unpinned'})
    
    @action(detail=True, methods=['post'])
    def mute(self, request, pk=None):
        """Mute a conversation"""
        participant = get_object_or_404(
            ConversationParticipant,
            conversation=pk,
            user=request.user
        )
        participant.is_muted = True
        participant.save()
        return Response({'status': 'muted'})
    
    @action(detail=True, methods=['post'])
    def unmute(self, request, pk=None):
        """Unmute a conversation"""
        participant = get_object_or_404(
            ConversationParticipant,
            conversation=pk,
            user=request.user
        )
        participant.is_muted = False
        participant.save()
        return Response({'status': 'unmuted'})
    
    @action(detail=True, methods=['post'])
    def add_participant(self, request, pk=None):
        """Add a participant to the conversation"""
        conversation = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(id=user_id)
            # Check if user is already a participant
            if conversation.participants.filter(id=user_id).exists():
                return Response(
                    {'error': 'User is already a participant'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            ConversationParticipant.objects.create(
                conversation=conversation,
                user=user,
                role=ConversationParticipant.ROLE_MEMBER
            )
            
            return Response({'status': 'participant added'})
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def remove_participant(self, request, pk=None):
        """Remove a participant from the conversation"""
        conversation = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            participant = ConversationParticipant.objects.get(
                conversation=conversation,
                user_id=user_id
            )
            participant.delete()
            return Response({'status': 'participant removed'})
        except ConversationParticipant.DoesNotExist:
            return Response(
                {'error': 'Participant not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """Get messages for a conversation"""
        conversation = self.get_object()
        messages = conversation.chat_messages.filter(
            is_deleted=False
        ).select_related('sender').prefetch_related('attachments')
        
        # Pagination
        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = ChatMessageSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = ChatMessageSerializer(messages, many=True, context={'request': request})
        return Response(serializer.data)


class ChatMessageViewSet(viewsets.ModelViewSet):
    """ViewSet for managing chat messages"""
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Get messages for conversations the user is part of"""
        user = self.request.user
        conversation_id = self.request.query_params.get('conversation_id')
        
        if conversation_id:
            return ChatMessage.objects.filter(
                conversation_id=conversation_id,
                conversation__participants=user
            ).select_related('sender').prefetch_related('attachments')
        
        return ChatMessage.objects.filter(
            conversation__participants=user
        ).select_related('sender').prefetch_related('attachments')
    
    def perform_create(self, serializer):
        """Create a new message"""
        conversation = serializer.validated_data['conversation']
        
        # Check if user is a participant
        if not conversation.participants.filter(id=self.request.user.id).exists():
            raise permissions.PermissionDenied("You are not a participant in this conversation")
        
        # Check if user is blocked
        if BlockedUser.objects.filter(
            blocker__in=conversation.participants.all(),
            blocked=self.request.user
        ).exists():
            raise permissions.PermissionDenied("You are blocked by a participant")
        
        serializer.save(sender=self.request.user)
        
        # Update conversation's last_message_at
        conversation.last_message_at = timezone.now()
        conversation.save()
    
    @action(detail=False, methods=['post'])
    def send_message(self, request):
        """Send a new message"""
        serializer = SendMessageSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            
            try:
                conversation = Conversation.objects.get(
                    conversation_id=data['conversation_id']
                )
            except Conversation.DoesNotExist:
                return Response(
                    {'error': 'Conversation not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if user is a participant
            if not conversation.participants.filter(id=request.user.id).exists():
                return Response(
                    {'error': 'You are not a participant in this conversation'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Create message
            message = ChatMessage.objects.create(
                conversation=conversation,
                sender=request.user,
                message_type=data['message_type'],
                content=data.get('content', '')
            )
            
            # Handle reply_to
            if data.get('reply_to_message_id'):
                try:
                    reply_to = ChatMessage.objects.get(
                        message_id=data['reply_to_message_id']
                    )
                    message.reply_to = reply_to
                    message.save()
                except ChatMessage.DoesNotExist:
                    pass
            
            return Response(
                ChatMessageSerializer(message, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark a message as read"""
        message = self.get_object()
        message.mark_as_read(request.user)
        return Response({'status': 'marked as read'})
    
    @action(detail=True, methods=['post'])
    def edit(self, request, pk=None):
        """Edit a message"""
        message = self.get_object()
        
        # Check if user is the sender
        if message.sender != request.user:
            return Response(
                {'error': 'You can only edit your own messages'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        new_content = request.data.get('content')
        if not new_content:
            return Response(
                {'error': 'content is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        message.edit(new_content)
        return Response(
            ChatMessageSerializer(message, context={'request': request}).data
        )
    
    @action(detail=True, methods=['post'])
    def delete(self, request, pk=None):
        """Delete a message (soft delete)"""
        message = self.get_object()
        
        # Check if user is the sender
        if message.sender != request.user:
            return Response(
                {'error': 'You can only delete your own messages'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        message.soft_delete()
        return Response({'status': 'deleted'})
    
    @action(detail=True, methods=['post'])
    def pin(self, request, pk=None):
        """Pin a message"""
        message = self.get_object()
        message.is_pinned = True
        message.save()
        return Response({'status': 'pinned'})
    
    @action(detail=True, methods=['post'])
    def unpin(self, request, pk=None):
        """Unpin a message"""
        message = self.get_object()
        message.is_pinned = False
        message.save()
        return Response({'status': 'unpinned'})


class MessageAttachmentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing message attachments"""
    serializer_class = MessageAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Get attachments for messages in user's conversations"""
        user = self.request.user
        return MessageAttachment.objects.filter(
            message__conversation__participants=user
        ).select_related('message')
    
    def perform_create(self, serializer):
        """Create a new attachment"""
        message = serializer.validated_data['message']
        
        # Check if user is the sender
        if message.sender != self.request.user:
            raise permissions.PermissionDenied("You can only add attachments to your own messages")
        
        serializer.save()


class MessageReportViewSet(viewsets.ModelViewSet):
    """ViewSet for managing message reports"""
    serializer_class = MessageReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Get reports based on user role"""
        user = self.request.user
        
        # Admins can see all reports
        if can_access_dashboard(user):
            return MessageReport.objects.all().select_related(
                'reporter', 'reported_user', 'message', 'reviewed_by'
            )
        
        # Regular users can only see their own reports
        return MessageReport.objects.filter(
            reporter=user
        ).select_related('reported_user', 'message', 'reviewed_by')
    
    def perform_create(self, serializer):
        """Create a new report"""
        serializer.save(reporter=self.request.user)
    
    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        """Review a report (admin only)"""
        if not can_access_dashboard(request.user):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        report = self.get_object()
        notes = request.data.get('notes', '')
        report.mark_as_reviewed(request.user, notes)
        return Response({'status': 'reviewed'})
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve a report (admin only)"""
        if not can_access_dashboard(request.user):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        report = self.get_object()
        notes = request.data.get('notes', '')
        report.resolve(request.user, notes)
        return Response({'status': 'resolved'})
    
    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        """Dismiss a report (admin only)"""
        if not can_access_dashboard(request.user):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        report = self.get_object()
        notes = request.data.get('notes', '')
        report.dismiss(request.user, notes)
        return Response({'status': 'dismissed'})


class ChatSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for managing chat settings"""
    serializer_class = ChatSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Get settings for the current user"""
        return ChatSettings.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Create settings for the user"""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_settings(self, request):
        """Get current user's chat settings"""
        settings, created = ChatSettings.objects.get_or_create(
            user=request.user
        )
        serializer = ChatSettingsSerializer(settings, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def block_user(self, request):
        """Block a user"""
        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user_to_block = User.objects.get(id=user_id)
            settings, _ = ChatSettings.objects.get_or_create(user=request.user)
            settings.block_user(user_to_block)
            return Response({'status': 'user blocked'})
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def unblock_user(self, request):
        """Unblock a user"""
        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user_to_unblock = User.objects.get(id=user_id)
            settings = ChatSettings.objects.get(user=request.user)
            settings.unblock_user(user_to_unblock)
            return Response({'status': 'user unblocked'})
        except ChatSettings.DoesNotExist:
            return Response(
                {'error': 'Settings not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class BlockedUserViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing blocked users"""
    serializer_class = BlockedUserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Get users blocked by the current user"""
        return BlockedUser.objects.filter(
            blocker=self.request.user
        ).select_related('blocked')
