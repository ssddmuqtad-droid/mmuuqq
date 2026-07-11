"""إشارات Django لربط الإشعارات بالأحداث"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Property, Message, BrokerRating, Broker, BrokerPlanSubscription
from .services import NotificationService


@receiver(post_save, sender=Property)
def property_created_notification(sender, instance, created, **kwargs):
    """إرسال إشعار عند إنشاء عقار جديد"""
    if created:
        service = NotificationService()
        
        # إشعار للدلالين في نفس المحافظة
        if instance.governorate:
            from django.contrib.auth.models import User
            from .models import Broker
            
            # الحصول على الدلالين في نفس المحافظة
            brokers_in_governorate = Broker.objects.filter(
                governorate=instance.governorate,
                is_active=True
            )
            
            if brokers_in_governorate.exists():
                users = [broker.user for broker in brokers_in_governorate]
                service.send_to_users(
                    users,
                    title=f'عقار جديد في {instance.governorate}',
                    description=f'تم إضافة عقار جديد: {instance.title}',
                    notification_type='property',
                    icon='🏠',
                    button_text='عرض العقار',
                    button_link=f'/property/{instance.id}/'
                )


@receiver(post_save, sender=Message)
def message_received_notification(sender, instance, created, **kwargs):
    """إرسال إشعار عند استلام رسالة جديدة"""
    if created:
        service = NotificationService()
        
        # إشعار للمستلم
        recipient = instance.recipient if hasattr(instance, 'recipient') else None
        if recipient:
            sender_name = instance.sender.username if hasattr(instance.sender, 'username') else 'مستخدم'
            service.send_to_user(
                recipient,
                title='رسالة جديدة',
                description=f'لديك رسالة جديدة من {sender_name}',
                notification_type='message',
                icon='💬',
                button_text='عرض الرسالة',
                button_link=f'/dashboard/messages/{instance.id}/'
            )


@receiver(post_save, sender=BrokerRating)
def rating_received_notification(sender, instance, created, **kwargs):
    """إرسال إشعار عند استلام تقييم جديد"""
    if created:
        service = NotificationService()
        
        # إشعار للدلال
        if instance.broker:
            service.send_to_user(
                instance.broker.user,
                title='تقييم جديد',
                description=f'حصلت على تقييم جديد: {instance.rating}/5',
                notification_type='rating',
                icon='⭐',
                button_text='عرض التقييم',
                button_link=f'/broker/{instance.broker.id}/'
            )


@receiver(post_save, sender=BrokerPlanSubscription)
def subscription_notification(sender, instance, created, **kwargs):
    """إرسال إشعار عند إنشاء اشتراك جديد"""
    if created:
        service = NotificationService()
        
        service.send_to_user(
            instance.broker.user,
            title='اشتراك جديد',
            description=f'تم تفعيل اشتراكك في خطة {instance.plan.name}',
            notification_type='subscription',
            icon='✅',
            button_text='عرض الاشتراك',
            button_link=f'/dashboard/broker/{instance.broker.id}/'
        )


def notify_property_approved(property_obj):
    """إرسال إشعار عند موافقة على عقار"""
    service = NotificationService()
    
    if property_obj.owner:
        service.send_to_user(
            property_obj.owner,
            title='تمت الموافقة على عقارك',
            description=f'تمت الموافقة على عقارك: {property_obj.title}',
            notification_type='success',
            icon='✅',
            button_text='عرض العقار',
            button_link=f'/property/{property_obj.id}/'
        )


def notify_property_rejected(property_obj, reason=''):
    """إرسال إشعار عند رفض عقار"""
    service = NotificationService()
    
    if property_obj.owner:
        description = f'تم رفض عقارك: {property_obj.title}'
        if reason:
            description += f'\nالسبب: {reason}'
        
        service.send_to_user(
            property_obj.owner,
            title='تم رفض عقارك',
            description=description,
            notification_type='error',
            icon='❌',
            button_link=f'/dashboard/properties/'
        )


def notify_subscription_expiring(broker, days_remaining):
    """إرسال إشعار عند اقتراب انتهاء الاشتراك"""
    service = NotificationService()
    
    service.send_to_user(
        broker.user,
        title='اشتراكك على وشك الانتهاء',
        description=f'اشتراكك سينتهي خلال {days_remaining} يوم',
        notification_type='warning',
        icon='⚠️',
        button_text='تجديد الاشتراك',
        button_link='/subscription/renewal/'
    )


def notify_new_user(user):
    """إرسال إشعار للمشرفين عند تسجيل مستخدم جديد"""
    service = NotificationService()
    
    # إرسال للمشرفين فقط
    from django.contrib.auth.models import User
    admins = User.objects.filter(is_superuser=True)
    
    if admins.exists():
        service.send_to_users(
            admins,
            title='مستخدم جديد',
            description=f'تم تسجيل مستخدم جديد: {user.username}',
            notification_type='info',
            icon='👤',
            button_link=f'/admin-panel/users/'
        )


def notify_password_changed(user):
    """إرسال إشعار عند تغيير كلمة المرور"""
    service = NotificationService()
    
    service.send_to_user(
        user,
        title='تم تغيير كلمة المرور',
        description='تم تغيير كلمة المرور لحسابك بنجاح',
        notification_type='info',
        icon='🔐'
    )


def notify_new_device_login(user, ip_address):
    """إرسال إشعار عند تسجيل دخول من جهاز جديد"""
    service = NotificationService()
    
    service.send_to_user(
        user,
        title='تسجيل دخول جديد',
        description=f'تم تسجيل الدخول من جهاز جديد (IP: {ip_address})',
        notification_type='warning',
        icon='🔒'
    )
