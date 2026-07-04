"""
Chat System WebSocket Consumers
Real-time messaging using Django Channels
"""

import json
import uuid
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone

from .models import (
    Conversation, ConversationParticipant, ChatMessage,
    MessageReadStatus, BlockedUser, ChatSettings
)


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"
        
        # Check if user is a participant in the conversation
        is_participant = await self.is_conversation_participant()
        if not is_participant:
            await self.close()
            return
        
        # Check if user is blocked
        is_blocked = await self.is_user_blocked()
        if is_blocked:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send user joined notification
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_joined",
                "user_id": self.user.id,
                "username": self.user.username,
                "timestamp": timezone.now().isoformat()
            }
        )
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'room_group_name'):
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            # Send user left notification
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "user_left",
                    "user_id": self.user.id,
                    "username": self.user.username,
                    "timestamp": timezone.now().isoformat()
                }
            )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")
            
            if message_type == "chat_message":
                await self.handle_chat_message(data)
            elif message_type == "typing":
                await self.handle_typing_indicator(data)
            elif message_type == "mark_read":
                await self.handle_mark_read(data)
            elif message_type == "edit_message":
                await self.handle_edit_message(data)
            elif message_type == "delete_message":
                await self.handle_delete_message(data)
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            await self.send_error(str(e))
    
    async def handle_chat_message(self, data):
        """Handle sending a chat message"""
        content = data.get("content", "")
        reply_to_id = data.get("reply_to")
        
        if not content:
            await self.send_error("Message content is required")
            return
        
        # Create message
        message = await self.create_message(content, reply_to_id)
        
        # Serialize message
        message_data = await self.serialize_message(message)
        
        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message_data,
                "sender_id": self.user.id,
                "timestamp": timezone.now().isoformat()
            }
        )
        
        # Update conversation last_message_at
        await self.update_conversation_timestamp()
    
    async def handle_typing_indicator(self, data):
        """Handle typing indicator"""
        is_typing = data.get("is_typing", False)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "typing_indicator",
                "user_id": self.user.id,
                "username": self.user.username,
                "is_typing": is_typing,
                "timestamp": timezone.now().isoformat()
            }
        )
    
    async def handle_mark_read(self, data):
        """Handle marking messages as read"""
        message_id = data.get("message_id")
        
        if message_id:
            await self.mark_message_as_read(message_id)
            
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "message_read",
                    "message_id": message_id,
                    "user_id": self.user.id,
                    "timestamp": timezone.now().isoformat()
                }
            )
    
    async def handle_edit_message(self, data):
        """Handle editing a message"""
        message_id = data.get("message_id")
        new_content = data.get("content")
        
        if not message_id or not new_content:
            await self.send_error("message_id and content are required")
            return
        
        message = await self.edit_message(message_id, new_content)
        if message:
            message_data = await self.serialize_message(message)
            
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "message_edited",
                    "message": message_data,
                    "timestamp": timezone.now().isoformat()
                }
            )
    
    async def handle_delete_message(self, data):
        """Handle deleting a message"""
        message_id = data.get("message_id")
        
        if not message_id:
            await self.send_error("message_id is required")
            return
        
        success = await self.delete_message(message_id)
        if success:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "message_deleted",
                    "message_id": message_id,
                    "deleted_by": self.user.id,
                    "timestamp": timezone.now().isoformat()
                }
            )
    
    async def chat_message(self, event):
        """Send chat message to WebSocket"""
        await self.send(text_data=json.dumps({
            "type": "chat_message",
            "message": event["message"],
            "sender_id": event["sender_id"],
            "timestamp": event["timestamp"]
        }))
    
    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket"""
        await self.send(text_data=json.dumps({
            "type": "typing_indicator",
            "user_id": event["user_id"],
            "username": event["username"],
            "is_typing": event["is_typing"],
            "timestamp": event["timestamp"]
        }))
    
    async def message_read(self, event):
        """Send message read notification to WebSocket"""
        await self.send(text_data=json.dumps({
            "type": "message_read",
            "message_id": event["message_id"],
            "user_id": event["user_id"],
            "timestamp": event["timestamp"]
        }))
    
    async def message_edited(self, event):
        """Send message edited notification to WebSocket"""
        await self.send(text_data=json.dumps({
            "type": "message_edited",
            "message": event["message"],
            "timestamp": event["timestamp"]
        }))
    
    async def message_deleted(self, event):
        """Send message deleted notification to WebSocket"""
        await self.send(text_data=json.dumps({
            "type": "message_deleted",
            "message_id": event["message_id"],
            "deleted_by": event["deleted_by"],
            "timestamp": event["timestamp"]
        }))
    
    async def user_joined(self, event):
        """Send user joined notification to WebSocket"""
        await self.send(text_data=json.dumps({
            "type": "user_joined",
            "user_id": event["user_id"],
            "username": event["username"],
            "timestamp": event["timestamp"]
        }))
    
    async def user_left(self, event):
        """Send user left notification to WebSocket"""
        await self.send(text_data=json.dumps({
            "type": "user_left",
            "user_id": event["user_id"],
            "username": event["username"],
            "timestamp": event["timestamp"]
        }))
    
    async def send_error(self, message):
        """Send error message to WebSocket"""
        await self.send(text_data=json.dumps({
            "type": "error",
            "message": message
        }))
    
    # Database operations (sync to async)
    
    @database_sync_to_async
    def is_conversation_participant(self):
        """Check if user is a participant in the conversation"""
        try:
            conversation = Conversation.objects.get(conversation_id=self.conversation_id)
            return conversation.participants.filter(id=self.user.id).exists()
        except Conversation.DoesNotExist:
            return False
    
    @database_sync_to_async
    def is_user_blocked(self):
        """Check if user is blocked by any participant"""
        try:
            conversation = Conversation.objects.get(conversation_id=self.conversation_id)
            participants = conversation.participants.all()
            return BlockedUser.objects.filter(
                blocker__in=participants,
                blocked=self.user
            ).exists()
        except Conversation.DoesNotExist:
            return False
    
    @database_sync_to_async
    def create_message(self, content, reply_to_id=None):
        """Create a new message"""
        try:
            conversation = Conversation.objects.get(conversation_id=self.conversation_id)
            message = ChatMessage.objects.create(
                conversation=conversation,
                sender=self.user,
                message_type=ChatMessage.TYPE_TEXT,
                content=content
            )
            
            if reply_to_id:
                try:
                    reply_to = ChatMessage.objects.get(message_id=reply_to_id)
                    message.reply_to = reply_to
                    message.save()
                except ChatMessage.DoesNotExist:
                    pass
            
            return message
        except Conversation.DoesNotExist:
            return None
    
    @database_sync_to_async
    def mark_message_as_read(self, message_id):
        """Mark a message as read"""
        try:
            message = ChatMessage.objects.get(message_id=message_id)
            MessageReadStatus.objects.get_or_create(
                message=message,
                user=self.user,
                defaults={'read_at': timezone.now()}
            )
        except ChatMessage.DoesNotExist:
            pass
    
    @database_sync_to_async
    def edit_message(self, message_id, new_content):
        """Edit a message"""
        try:
            message = ChatMessage.objects.get(message_id=message_id)
            if message.sender == self.user:
                message.edit(new_content)
                return message
        except ChatMessage.DoesNotExist:
            return None
        return None
    
    @database_sync_to_async
    def delete_message(self, message_id):
        """Delete a message (soft delete)"""
        try:
            message = ChatMessage.objects.get(message_id=message_id)
            if message.sender == self.user:
                message.soft_delete()
                return True
        except ChatMessage.DoesNotExist:
            return False
        return False
    
    @database_sync_to_async
    def update_conversation_timestamp(self):
        """Update conversation's last_message_at"""
        try:
            conversation = Conversation.objects.get(conversation_id=self.conversation_id)
            conversation.last_message_at = timezone.now()
            conversation.save()
        except Conversation.DoesNotExist:
            pass
    
    @database_sync_to_async
    def serialize_message(self, message):
        """Serialize message for WebSocket transmission"""
        return {
            "message_id": str(message.message_id),
            "conversation_id": str(message.conversation.conversation_id),
            "sender_id": message.sender.id if message.sender else None,
            "sender_username": message.sender.username if message.sender else "Unknown",
            "message_type": message.message_type,
            "content": message.content,
            "reply_to": str(message.reply_to.message_id) if message.reply_to else None,
            "is_edited": message.is_edited,
            "edited_at": message.edited_at.isoformat() if message.edited_at else None,
            "is_deleted": message.is_deleted,
            "created_at": message.created_at.isoformat(),
            "updated_at": message.updated_at.isoformat()
        }


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time notifications"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.user_group_name = f"notifications_{self.user.id}"
        
        # Join user's notification group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
    
    async def notification(self, event):
        """Send notification to WebSocket"""
        await self.send(text_data=json.dumps({
            "type": "notification",
            "notification": event["notification"],
            "timestamp": event["timestamp"]
        }))
    
    async def typing(self, event):
        """Send typing indicator to WebSocket"""
        await self.send(text_data=json.dumps({
            "type": "typing",
            "user_id": event["user_id"],
            "is_typing": event["is_typing"],
            "timestamp": event["timestamp"]
        }))
