"""
WebSocket consumers for real-time notifications
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone
from properties.models import Notification, Auction, Bid


class NotificationConsumer(AsyncWebsocketConsumer):
    """Consumer for real-time notifications"""
    
    async def connect(self):
        self.user = self.scope["user"]
        
        if self.user.is_anonymous:
            await self.close()
            return
        
        self.room_group_name = f'notifications_{self.user.id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type')
        
        if message_type == 'mark_read':
            notification_id = text_data_json.get('notification_id')
            await self.mark_notification_read(notification_id)
    
    async def notification_message(self, event):
        """Receive notification from channel layer"""
        notification = event['notification']
        
        # Send notification to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': notification
        }))
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark notification as read"""
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=self.user
            )
            notification.is_read = True
            notification.save()
        except Notification.DoesNotExist:
            pass


class AuctionConsumer(AsyncWebsocketConsumer):
    """Consumer for real-time auction updates"""
    
    async def connect(self):
        self.auction_id = self.scope['url_route']['kwargs']['auction_id']
        self.user = self.scope["user"]
        
        if self.user.is_anonymous:
            await self.close()
            return
        
        self.room_group_name = f'auction_{self.auction_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type')
        
        if message_type == 'bid':
            bid_amount = text_data_json.get('amount')
            update = await self.place_bid(bid_amount)
            if update:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'auction_update',
                        'update': update,
                    },
                )
    
    async def auction_update(self, event):
        """Receive auction update from channel layer"""
        update = event['update']
        
        # Send update to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'auction_update',
            'update': update
        }))
    
    @database_sync_to_async
    def place_bid(self, amount):
        """Place a bid on the auction."""
        try:
            auction = Auction.objects.get(id=self.auction_id)
            bid = Bid.objects.create(
                auction=auction,
                user=self.user,
                amount=amount,
            )
            return {
                'bid_amount': str(amount),
                'bidder': self.user.username,
                'timestamp': bid.created_at.isoformat(),
                'current_highest': str(auction.get_current_highest_bid()),
            }
        except Auction.DoesNotExist:
            return None


class ChatConsumer(AsyncWebsocketConsumer):
    """Consumer for real-time chat"""
    
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.user = self.scope["user"]
        
        if self.user.is_anonymous:
            await self.close()
            return
        
        self.room_group_name = f'chat_{self.room_name}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json.get('message')
        
        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'user': self.user.username,
                'timestamp': str(timezone.now())
            }
        )
    
    async def chat_message(self, event):
        """Receive message from room group"""
        message = event['message']
        user = event['user']
        
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'chat',
            'message': message,
            'user': user,
            'timestamp': event['timestamp']
        }))
