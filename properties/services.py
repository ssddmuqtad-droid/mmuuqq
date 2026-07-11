"""خدمات الإشعارات"""
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
from .models import Notification, NotificationRecipient, NotificationLog, Broker


class NotificationService:
    """خدمة إرسال الإشعارات"""
    
    def send_notification(self, notification):
        """إرسال إشعار للمستلمين المستهدفين"""
        # Get target users
        users = self.get_target_users(notification)
        
        # Create recipients
        recipients = []
        for user in users:
            recipient, created = NotificationRecipient.objects.get_or_create(
                notification=notification,
                user=user
            )
            if created:
                recipients.append(recipient)
        
        # Mark notification as sent
        notification.mark_as_sent()
        
        # Create log
        self.create_log(notification, len(recipients))
        
        return recipients
    
    def get_target_users(self, notification):
        """الحصول على المستخدمين المستهدفين"""
        from django.contrib.auth.models import User
        from django.db.models import Count
        
        users = User.objects.all()
        
        # Filter by user type
        if notification.target_all_users:
            pass  # All users
        elif notification.target_all_brokers:
            users = users.filter(broker_profile__isnull=False)
        elif notification.target_all_admins:
            users = users.filter(is_staff=True)
        elif notification.target_office_owners:
            users = users.filter(broker_profile__has_office=True)
        elif notification.target_managers:
            users = users.filter(broker_profile__role='manager')
        elif notification.target_active_users:
            users = users.filter(last_login__gte=timezone.now() - timezone.timedelta(days=30))
        elif notification.target_new_users:
            users = users.filter(date_joined__gte=timezone.now() - timezone.timedelta(days=7))
        elif notification.target_inactive_users:
            users = users.filter(last_login__lt=timezone.now() - timezone.timedelta(days=30))
        
        # Filter by account type
        if notification.target_account_type:
            if notification.target_account_type == 'broker':
                users = users.filter(broker_profile__isnull=False)
            elif notification.target_account_type == 'user':
                users = users.filter(user_profile__isnull=False)
        
        # Filter by subscription type
        if notification.target_subscription_type:
            from .models import BrokerPlanSubscription
            broker_ids = BrokerPlanSubscription.objects.filter(
                plan__name=notification.target_subscription_type,
                status='active'
            ).values_list('broker_id', flat=True)
            users = users.filter(broker_profile__id__in=broker_ids)
        
        # Filter by account status
        if notification.target_account_status:
            if notification.target_account_status == 'active':
                users = users.filter(is_active=True)
            elif notification.target_account_status == 'inactive':
                users = users.filter(is_active=False)
        
        # Filter by properties ownership
        if notification.target_has_properties is not None:
            if notification.target_has_properties:
                users = users.filter(
                    Q(broker_profile__properties__isnull=False) |
                    Q(user_profile__properties__isnull=False)
                ).distinct()
            else:
                users = users.exclude(
                    Q(broker_profile__properties__isnull=False) |
                    Q(user_profile__properties__isnull=False)
                )
        
        # Filter by location
        if notification.target_governorate:
            users = users.filter(
                Q(user_profile__governorate=notification.target_governorate) |
                Q(broker_profile__governorate=notification.target_governorate)
            )
        
        if notification.target_city:
            users = users.filter(
                Q(user_profile__city=notification.target_city) |
                Q(broker_profile__city=notification.target_city)
            )
        
        if notification.target_area:
            users = users.filter(
                Q(user_profile__area=notification.target_area) |
                Q(broker_profile__area=notification.target_area)
            )
        
        # Filter by property type
        if notification.target_property_type:
            from .models import Property
            property_owners = Property.objects.filter(
                property_type=notification.target_property_type
            ).values_list('owner', flat=True)
            users = users.filter(id__in=property_owners)
        
        # Filter by broker criteria
        if notification.target_premium_brokers:
            from .models import BrokerPlanSubscription
            broker_ids = BrokerPlanSubscription.objects.filter(
                plan__name__icontains='premium',
                status='active'
            ).values_list('broker_id', flat=True)
            users = users.filter(broker_profile__id__in=broker_ids)
        
        if notification.target_min_properties:
            from .models import Property
            broker_ids = Property.objects.filter(
                broker__isnull=False
            ).values('broker').annotate(
                count=Count('id')
            ).filter(
                count__gte=notification.target_min_properties
            ).values_list('broker', flat=True)
            users = users.filter(broker_profile__id__in=broker_ids)
        
        if notification.target_min_rating:
            from .models import BrokerRating
            broker_ids = BrokerRating.objects.filter(
                rating__gte=notification.target_min_rating
            ).values_list('broker_id', flat=True)
            users = users.filter(broker_profile__id__in=broker_ids)
        
        return users.distinct()
    
    def create_log(self, notification, sent_count):
        """إنشاء سجل الإرسال"""
        log = NotificationLog.objects.create(
            notification=notification,
            total_sent=sent_count,
            total_delivered=sent_count,  # Assuming all delivered for now
            total_read=notification.get_read_count(),
            total_clicked=notification.get_clicked_count(),
        )
        
        # Calculate rates
        if sent_count > 0:
            log.delivery_rate = (log.total_delivered / sent_count) * 100
            log.read_rate = (log.total_read / sent_count) * 100
            log.click_rate = (log.total_clicked / sent_count) * 100
            log.save()
        
        return log
    
    def send_to_user(self, user, title, description, notification_type='info', **kwargs):
        """إرسال إشعار لمستخدم محدد"""
        notification = Notification.objects.create(
            title=title,
            description=description,
            notification_type=notification_type,
            **kwargs
        )
        
        recipient = NotificationRecipient.objects.create(
            notification=notification,
            user=user
        )
        
        notification.mark_as_sent()
        
        return recipient
    
    def send_to_users(self, users, title, description, notification_type='info', **kwargs):
        """إرسال إشعار لمجموعة مستخدمين"""
        notification = Notification.objects.create(
            title=title,
            description=description,
            notification_type=notification_type,
            **kwargs
        )
        
        recipients = []
        for user in users:
            recipient = NotificationRecipient.objects.create(
                notification=notification,
                user=user
            )
            recipients.append(recipient)
        
        notification.mark_as_sent()
        
        return recipients
