import os
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Max, Q
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils.text import slugify
from django.utils import timezone
from django.urls import reverse
from django.core.validators import MinValueValidator, MaxValueValidator

from .constants import (
    IRAQ_GOVERNORATES,
    PROPERTY_CATEGORIES,
    PROPERTY_TYPES,
    TRANSACTION_TYPES,
    STATUS_CHOICES,
    SUBSCRIPTION_PERIODS,
)


def property_image_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()[:10]
    prop_id = getattr(instance, 'property_id', None) or getattr(instance, 'id', None) or 'new'
    name = uuid.uuid4().hex[:10]
    return os.path.join('properties/', f'{prop_id}_{name}.{ext}')


def property_video_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()[:10]
    prop_id = getattr(instance, 'property_id', None) or getattr(instance, 'id', None) or 'new'
    name = uuid.uuid4().hex[:10]
    return os.path.join('properties/videos/', f'{prop_id}_{name}.{ext}')


class FavoriteArea(models.Model):
    """User's favorite map areas for property notifications"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_areas', verbose_name='المستخدم')
    name = models.CharField(max_length=100, verbose_name='اسم المنطقة')
    south = models.DecimalField(max_digits=10, decimal_places=7, verbose_name='الحد الجنوبي')
    north = models.DecimalField(max_digits=10, decimal_places=7, verbose_name='الحد الشمالي')
    west = models.DecimalField(max_digits=10, decimal_places=7, verbose_name='الحد الغربي')
    east = models.DecimalField(max_digits=10, decimal_places=7, verbose_name='الحد الشرقي')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    
    class Meta:
        verbose_name = 'منطقة مفضلة'
        verbose_name_plural = 'المناطق المفضلة'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.name} - {self.user.username}'
    
    def contains_property(self, property):
        """Check if a property is within this favorite area"""
        if not property.latitude or not property.longitude:
            return False
        return (self.south <= float(property.latitude) <= self.north and
                self.west <= float(property.longitude) <= self.east)


class PropertyComparison(models.Model):
    """Property comparison list for users"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='property_comparisons', verbose_name='المستخدم')
    property = models.ForeignKey('Property', on_delete=models.CASCADE, related_name='comparisons', verbose_name='العقار')
    added_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')
    
    class Meta:
        verbose_name = 'مقارنة عقار'
        verbose_name_plural = 'مقارنات العقارات'
        unique_together = ['user', 'property']
        ordering = ['-added_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.property.display_title}'


class UserSettings(models.Model):
    """User settings for regular users"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='settings', verbose_name='المستخدم')
    
    # Profile Settings
    phone = models.CharField(max_length=20, blank=True, verbose_name='رقم الهاتف')
    birth_date = models.DateField(null=True, blank=True, verbose_name='تاريخ الميلاد')
    gender = models.CharField(max_length=10, choices=[('male', 'ذكر'), ('female', 'أنثى')], blank=True, verbose_name='الجنس')
    governorate = models.CharField(max_length=50, choices=IRAQ_GOVERNORATES, blank=True, verbose_name='المحافظة')
    city = models.CharField(max_length=100, blank=True, verbose_name='المدينة')
    address = models.TextField(blank=True, verbose_name='العنوان')
    bio = models.TextField(blank=True, verbose_name='نبذة قصيرة')
    
    # Security Settings
    two_factor_enabled = models.BooleanField(default=False, verbose_name='المصادقة الثنائية مفعلة')
    
    # Notification Settings
    notification_new_properties = models.BooleanField(default=True, verbose_name='إشعارات العقارات الجديدة')
    notification_messages = models.BooleanField(default=True, verbose_name='إشعارات الرسائل')
    notification_offers = models.BooleanField(default=True, verbose_name='إشعارات العروض والخصومات')
    notification_matching = models.BooleanField(default=True, verbose_name='إشعارات العقارات المطابقة')
    email_notifications = models.BooleanField(default=True, verbose_name='إشعارات البريد الإلكتروني')
    app_notifications = models.BooleanField(default=True, verbose_name='إشعارات التطبيق')
    
    # Privacy Settings
    show_phone = models.BooleanField(default=True, verbose_name='إظهار رقم الهاتف')
    show_email = models.BooleanField(default=False, verbose_name='إظهار البريد الإلكتروني')
    who_can_message = models.CharField(max_length=20, choices=[('everyone', 'الجميع'), ('favorites', 'المفضلة فقط'), ('none', 'لا أحد')], default='everyone', verbose_name='من يمكنه مراسلتي')
    
    # Preferences
    dark_mode = models.BooleanField(default=False, verbose_name='الوضع الليلي')
    language = models.CharField(max_length=5, choices=[('ar', 'العربية'), ('en', 'English')], default='ar', verbose_name='اللغة')
    currency = models.CharField(max_length=3, choices=[('IQD', 'دينار عراقي'), ('USD', 'دولار أمريكي')], default='IQD', verbose_name='العملة')
    property_view_mode = models.CharField(max_length=10, choices=[('grid', 'شبكة'), ('list', 'قائمة')], default='grid', verbose_name='طريقة عرض العقارات')
    properties_per_page = models.IntegerField(default=12, choices=[(6, 6), (12, 12), (24, 24), (48, 48)], verbose_name='عدد العقارات في الصفحة')
    
    # Account Status
    account_disabled = models.BooleanField(default=False, verbose_name='حساب معطل مؤقتاً')
    disabled_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ التعطيل')
    disabled_reason = models.TextField(blank=True, verbose_name='سبب التعطيل')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'إعدادات المستخدم'
        verbose_name_plural = 'إعدادات المستخدمين'
    
    def __str__(self):
        return f'إعدادات {self.user.username}'


class MessageNotificationSettings(models.Model):
    """User notification settings for messages"""
    
    NOTIFICATION_TYPE_NEW_MESSAGE = 'new_message'
    NOTIFICATION_TYPE_MENTION = 'mention'
    NOTIFICATION_TYPE_REACTION = 'reaction'
    NOTIFICATION_TYPE_REPLY = 'reply'
    NOTIFICATION_TYPE_GROUP_MENTION = 'group_mention'
    
    NOTIFICATION_TYPE_CHOICES = [
        (NOTIFICATION_TYPE_NEW_MESSAGE, 'رسالة جديدة'),
        (NOTIFICATION_TYPE_MENTION, 'ذكر'),
        (NOTIFICATION_TYPE_REACTION, 'رد فعل'),
        (NOTIFICATION_TYPE_REPLY, 'رد'),
        (NOTIFICATION_TYPE_GROUP_MENTION, 'ذكر في مجموعة'),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='message_notification_settings',
        verbose_name='المستخدم'
    )
    
    # Notification types enabled
    new_message_notifications = models.BooleanField(default=True, verbose_name='إشعارات الرسائل الجديدة')
    mention_notifications = models.BooleanField(default=True, verbose_name='إشعارات الذكر')
    reaction_notifications = models.BooleanField(default=False, verbose_name='إشعارات الردود الفعل')
    reply_notifications = models.BooleanField(default=True, verbose_name='إشعارات الردود')
    group_mention_notifications = models.BooleanField(default=True, verbose_name='إشعارات الذكر في المجموعات')
    
    # Platform preferences
    in_app_notifications = models.BooleanField(default=True, verbose_name='إشعارات داخل التطبيق')
    browser_notifications = models.BooleanField(default=False, verbose_name='إشعارات المتصفح')
    email_notifications = models.BooleanField(default=False, verbose_name='إشعارات البريد الإلكتروني')
    sound_enabled = models.BooleanField(default=True, verbose_name='صوت الإشعارات')
    
    # Quiet hours
    quiet_hours_enabled = models.BooleanField(default=False, verbose_name='تفعيل الساعات الهادئة')
    quiet_hours_start = models.TimeField(null=True, blank=True, verbose_name='بداية الساعات الهادئة')
    quiet_hours_end = models.TimeField(null=True, blank=True, verbose_name='نهاية الساعات الهادئة')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'إعدادات إشعارات الرسائل'
        verbose_name_plural = 'إعدادات إشعارات الرسائل'
    
    def __str__(self):
        return f'إعدادات إشعارات {self.user.username}'
    
    def should_send_notification(self, notification_type):
        """Check if notification should be sent based on settings"""
        if notification_type == self.NOTIFICATION_TYPE_NEW_MESSAGE:
            return self.new_message_notifications
        elif notification_type == self.NOTIFICATION_TYPE_MENTION:
            return self.mention_notifications
        elif notification_type == self.NOTIFICATION_TYPE_REACTION:
            return self.reaction_notifications
        elif notification_type == self.NOTIFICATION_TYPE_REPLY:
            return self.reply_notifications
        elif notification_type == self.NOTIFICATION_TYPE_GROUP_MENTION:
            return self.group_mention_notifications
        return True
    
    def is_quiet_hours(self):
        """Check if current time is within quiet hours"""
        if not self.quiet_hours_enabled:
            return False
        
        if not self.quiet_hours_start or not self.quiet_hours_end:
            return False
        
        from django.utils import timezone
        now = timezone.now().time()
        
        if self.quiet_hours_start <= self.quiet_hours_end:
            return self.quiet_hours_start <= now <= self.quiet_hours_end
        else:
            # Overnight quiet hours (e.g., 22:00 to 07:00)
            return now >= self.quiet_hours_start or now <= self.quiet_hours_end


class BulkMessage(models.Model):
    """Bulk messages sent by admin to users or brokers"""
    
    TARGET_CHOICES = [
        ('all_users', 'جميع المستخدمين'),
        ('all_brokers', 'جميع الدلالين'),
        ('active_users', 'المستخدمين النشطين'),
        ('active_brokers', 'الدلالين النشطين'),
        ('specific_users', 'مستخدمين محددين'),
        ('specific_brokers', 'دلالين محددين'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('pending', 'قيد الإرسال'),
        ('sent', 'تم الإرسال'),
        ('failed', 'فشل الإرسال'),
    ]
    
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_bulk_messages', verbose_name='المرسل')
    target_type = models.CharField(max_length=20, choices=TARGET_CHOICES, default='all_users', verbose_name='نوع المستهدفين')
    title = models.CharField(max_length=200, verbose_name='العنوان')
    message = models.TextField(verbose_name='الرسالة')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='الحالة')
    
    # Statistics
    total_recipients = models.IntegerField(default=0, verbose_name='إجمالي المستلمين')
    sent_count = models.IntegerField(default=0, verbose_name='عدد الرسائل المرسلة')
    failed_count = models.IntegerField(default=0, verbose_name='عدد الرسائل الفاشلة')
    
    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True, verbose_name='موعد الإرسال المجدول')
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الإرسال')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'رسالة جماعية'
        verbose_name_plural = 'الرسائل الجماعية'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.title} - {self.get_target_type_display()}'


class MutedUser(models.Model):
    """Muted users list"""
    
    muter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='muted_users', verbose_name='الكاتم')
    muted = models.ForeignKey(User, on_delete=models.CASCADE, related_name='muted_by', verbose_name='المكتوم')
    muted_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الكتم')
    
    class Meta:
        verbose_name = 'مستخدم مكتوم'
        verbose_name_plural = 'المستخدمون المكتومون'
        unique_together = ['muter', 'muted']
        indexes = [
            models.Index(fields=['muter', 'muted']),
        ]
    
    def __str__(self):
        return f'{self.muter.username} كتم {self.muted.username}'


class BlockedUser(models.Model):
    """Blocked users list"""
    
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_users', verbose_name='الحاجب')
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_by', verbose_name='المحظور')
    blocked_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الحظر')
    reason = models.TextField(blank=True, verbose_name='السبب')
    
    class Meta:
        verbose_name = 'مستخدم محظور'
        verbose_name_plural = 'المستخدمون المحظورون'
        unique_together = ['blocker', 'blocked']
    
    def __str__(self):
        return f'{self.blocker.username} حظر {self.blocked.username}'


class SavedSearch(models.Model):
    """User's saved property searches"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_searches', verbose_name='المستخدم')
    name = models.CharField(max_length=100, verbose_name='اسم البحث')
    filters = models.JSONField(verbose_name='الفلاتر')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الحفظ')
    
    class Meta:
        verbose_name = 'بحث محفوظ'
        verbose_name_plural = 'عمليات البحث المحفوظة'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.name} - {self.user.username}'


class OfficePresence(models.Model):
    """Office presence status and availability"""
    
    STATUS_CHOICES = [
        ('online', 'متواجد الآن في المكتب'),
        ('busy', 'مشغول مع عميل'),
        ('offline', 'غير متواجد'),
        ('out', 'خارج المكتب'),
        ('remote', 'يعمل عن بُعد'),
        ('closed', 'المكتب مغلق'),
        ('vacation', 'في إجازة'),
    ]
    
    office = models.OneToOneField('Office', on_delete=models.CASCADE, related_name='presence', verbose_name='المكتب')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline', verbose_name='الحالة')
    last_seen = models.DateTimeField(auto_now=True, verbose_name='آخر ظهور')
    expected_return = models.DateTimeField(null=True, blank=True, verbose_name='العودة المتوقعة')
    absence_reason = models.TextField(blank=True, verbose_name='سبب الغياب')
    auto_update_enabled = models.BooleanField(default=True, verbose_name='تحديث تلقائي حسب ساعات العمل')
    
    # Working hours
    work_start = models.TimeField(null=True, blank=True, verbose_name='بداية العمل')
    work_end = models.TimeField(null=True, blank=True, verbose_name='نهاية العمل')
    work_days = models.JSONField(default=list, verbose_name='أيام العمل')
    
    # Statistics
    total_online_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='إجمالي ساعات التواجد')
    last_online_duration = models.DurationField(null=True, blank=True, verbose_name='مدة آخر تواجد')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'حالة تواجد المكتب'
        verbose_name_plural = 'حالات تواجد المكاتب'
    
    def __str__(self):
        return f'{self.office.name} - {self.get_status_display()}'
    
    def is_online(self):
        """Check if office is currently online"""
        return self.status in ['online', 'busy', 'remote']
    
    def get_status_emoji(self):
        """Get emoji for current status"""
        emojis = {
            'online': '🟢',
            'busy': '🟡',
            'offline': '🔴',
            'out': '🚗',
            'remote': '🏡',
            'closed': '🌙',
            'vacation': '🏖️',
        }
        return emojis.get(self.status, '⚪')
    
    def get_last_seen_display(self):
        """Get human-readable last seen time"""
        from django.utils import timezone
        now = timezone.now()
        diff = now - self.last_seen
        
        if diff.days == 0:
            if diff.seconds < 3600:
                minutes = diff.seconds // 60
                return f'قبل {minutes} دقيقة' if minutes > 1 else 'الآن'
            else:
                hours = diff.seconds // 3600
                return f'قبل {hours} ساعة' if hours > 1 else 'قبل ساعة'
        elif diff.days == 1:
            return f'أمس الساعة {self.last_seen.strftime("%I:%M %p")}'
        else:
            return f'قبل {diff.days} أيام'
    
    def get_expected_return_display(self):
        """Get human-readable expected return time"""
        if not self.expected_return:
            return 'غير محدد'
        
        from django.utils import timezone
        now = timezone.now()
        diff = self.expected_return - now
        
        if diff.total_seconds() < 0:
            return 'متأخر'
        elif diff.days == 0:
            if diff.seconds < 3600:
                minutes = diff.seconds // 60
                return f'بعد {minutes} دقيقة' if minutes > 1 else 'قريباً'
            else:
                return self.expected_return.strftime('اليوم الساعة %I:%M %p')
        elif diff.days == 1:
            return self.expected_return.strftime('غداً الساعة %I:%M %p')
        else:
            return self.expected_return.strftime('%Y-%m-%d الساعة %I:%M %p')


class PresenceNotification(models.Model):
    """Notifications for users when office comes online"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='presence_notifications', verbose_name='المستخدم')
    office = models.ForeignKey('Office', on_delete=models.CASCADE, related_name='presence_subscribers', verbose_name='المكتب')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    notified = models.BooleanField(default=False, verbose_name='تم الإشعار')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الاشتراك')
    notified_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الإشعار')
    
    class Meta:
        verbose_name = 'إشعار تواجد'
        verbose_name_plural = 'إشعارات التواجد'
        unique_together = ['user', 'office']
    
    def __str__(self):
        return f'{self.user.username} - {self.office.name}'


class BrokerSubscription(models.Model):
    """User subscription to broker channels"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='broker_subscriptions', verbose_name='المستخدم')
    broker = models.ForeignKey('Broker', on_delete=models.CASCADE, related_name='subscribers', verbose_name='الدلال')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    subscribed_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الاشتراك')
    unsubscribed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ إلغاء الاشتراك')
    
    # Statistics
    notifications_sent = models.IntegerField(default=0, verbose_name='الإشعارات المرسلة')
    notifications_read = models.IntegerField(default=0, verbose_name='الإشعارات المقروءة')
    last_notification_at = models.DateTimeField(null=True, blank=True, verbose_name='آخر إشعار')
    
    class Meta:
        verbose_name = 'اشتراك دلال'
        verbose_name_plural = 'اشتراكات الدلالين'
        unique_together = ['user', 'broker']
    
    def __str__(self):
        return f'{self.user.username} - {self.broker.display_name}'
    
    def get_subscription_duration(self):
        """Get subscription duration in days"""
        if self.unsubscribed_at:
            return (self.unsubscribed_at - self.subscribed_at).days
        from django.utils import timezone
        return (timezone.now() - self.subscribed_at).days


class BrokerNotificationSettings(models.Model):
    """User notification settings for specific broker"""
    
    NOTIFICATION_CHOICES = [
        ('all', 'جميع الإشعارات'),
        ('none', 'إيقاف جميع الإشعارات'),
        ('new_properties', 'العقارات الجديدة فقط'),
        ('featured', 'العقارات المميزة فقط'),
        ('offers', 'العروض والتخفيضات'),
        ('posts', 'البث والمنشورات'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='broker_notification_settings', verbose_name='المستخدم')
    broker = models.ForeignKey('Broker', on_delete=models.CASCADE, related_name='notification_settings', verbose_name='الدلال')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_CHOICES, default='all', verbose_name='نوع الإشعارات')
    
    # Platform preferences
    in_app_notifications = models.BooleanField(default=True, verbose_name='إشعارات داخل التطبيق')
    browser_notifications = models.BooleanField(default=False, verbose_name='إشعارات المتصفح')
    email_notifications = models.BooleanField(default=False, verbose_name='إشعارات البريد الإلكتروني')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'إعدادات إشعارات الدلال'
        verbose_name_plural = 'إعدادات إشعارات الدلالين'
        unique_together = ['user', 'broker']
    
    def __str__(self):
        return f'{self.user.username} - {self.broker.display_name} ({self.get_notification_type_display()})'


class BrokerSubscriptionStats(models.Model):
    """Statistics for broker subscriptions"""
    
    broker = models.OneToOneField('Broker', on_delete=models.CASCADE, related_name='subscription_stats', verbose_name='الدلال')
    total_subscribers = models.IntegerField(default=0, verbose_name='إجمالي المشتركين')
    new_subscribers_today = models.IntegerField(default=0, verbose_name='المشتركون الجدد اليوم')
    notification_enabled = models.IntegerField(default=0, verbose_name='المشتركون المفعلون للإشعارات')
    property_views = models.IntegerField(default=0, verbose_name='مشاهدات العقارات')
    notification_clicks = models.IntegerField(default=0, verbose_name='نقرات الإشعارات')
    
    # Daily tracking
    subscribers_history = models.JSONField(default=dict, verbose_name='تاريخ المشتركين')
    notification_history = models.JSONField(default=dict, verbose_name='تاريخ الإشعارات')
    
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'إحصائيات اشتراكات الدلال'
        verbose_name_plural = 'إحصائيات اشتراكات الدلالين'
    
    def __str__(self):
        return f'إحصائيات {self.broker.display_name}'
    
    def update_subscriber_count(self):
        """Update subscriber count"""
        self.total_subscribers = self.broker.subscribers.filter(is_active=True).count()
        self.notification_enabled = BrokerNotificationSettings.objects.filter(
            broker=self.broker,
            notification_type__in=['all', 'new_properties', 'featured', 'offers', 'posts']
        ).count()


class BrokerSystemStats(models.Model):
    """System-wide broker statistics"""
    
    total_brokers = models.IntegerField(default=0, verbose_name='إجمالي الدلالين')
    active_brokers = models.IntegerField(default=0, verbose_name='الدلالين النشطين')
    suspended_brokers = models.IntegerField(default=0, verbose_name='الدلالين الموقوفين')
    new_brokers_today = models.IntegerField(default=0, verbose_name='الدلالين الجدد اليوم')
    new_brokers_this_month = models.IntegerField(default=0, verbose_name='الدلالين الجدد هذا الشهر')
    
    # Role breakdown
    main_brokers = models.IntegerField(default=0, verbose_name='الدلالين الرئيسيين')
    sub_brokers = models.IntegerField(default=0, verbose_name='الدلالين الفرعيين')
    
    # Activity tracking
    total_properties_posted = models.IntegerField(default=0, verbose_name='إجمالي العقارات المنشورة')
    total_messages_sent = models.IntegerField(default=0, verbose_name='إجمالي الرسائل المرسلة')
    
    # Daily history
    daily_history = models.JSONField(default=dict, verbose_name='تاريخ يومي')
    
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'إحصائيات نظام الدلالين'
        verbose_name_plural = 'إحصائيات نظام الدلالين'
    
    def __str__(self):
        return 'إحصائيات نظام الدلالين'
    
    @classmethod
    def update_stats(cls):
        """Update all broker statistics"""
        from django.utils import timezone
        from datetime import datetime, timedelta
        
        stats, created = cls.objects.get_or_create(pk=1)
        
        # Count brokers
        all_brokers = Broker.objects.all()
        stats.total_brokers = all_brokers.count()
        stats.active_brokers = all_brokers.filter(is_active=True).count()
        stats.suspended_brokers = all_brokers.filter(is_suspended=True).count()
        
        # Count by role
        stats.main_brokers = all_brokers.filter(role='main').count()
        stats.sub_brokers = all_brokers.filter(role='sub').count()
        
        # Count new brokers
        today = timezone.now().date()
        month_start = today.replace(day=1)
        stats.new_brokers_today = all_brokers.filter(created_at__date=today).count()
        stats.new_brokers_this_month = all_brokers.filter(created_at__date__gte=month_start).count()
        
        # Count properties
        from .models import Property
        stats.total_properties_posted = Property.objects.filter(broker__isnull=False).count()
        
        # Count messages
        from .models import ChatMessage
        stats.total_messages_sent = ChatMessage.objects.count()
        
        # Update daily history
        today_str = today.isoformat()
        if not stats.daily_history:
            stats.daily_history = {}
        stats.daily_history[today_str] = {
            'total_brokers': stats.total_brokers,
            'active_brokers': stats.active_brokers,
            'new_brokers': stats.new_brokers_today,
        }
        
        stats.save()
        return stats


class BrokerIndividualStats(models.Model):
    """Individual broker statistics"""
    
    broker = models.OneToOneField('Broker', on_delete=models.CASCADE, related_name='individual_stats', verbose_name='الدلال')
    
    # Properties
    properties_added = models.IntegerField(default=0, verbose_name='العقارات المضافة')
    properties_deleted = models.IntegerField(default=0, verbose_name='العقارات المحذوفة')
    properties_active = models.IntegerField(default=0, verbose_name='العقارات النشطة')
    
    # Views
    total_views = models.IntegerField(default=0, verbose_name='إجمالي المشاهدات')
    views_today = models.IntegerField(default=0, verbose_name='المشاهدات اليوم')
    views_this_month = models.IntegerField(default=0, verbose_name='المشاهدات هذا الشهر')
    
    # Response time (in minutes)
    average_response_time = models.FloatField(default=0, verbose_name='متوسط وقت الاستجابة (دقيقة)')
    fastest_response_time = models.FloatField(default=0, verbose_name='أسرع وقت استجابة (دقيقة)')
    slowest_response_time = models.FloatField(default=0, verbose_name='أبطأ وقت استجابة (دقيقة)')
    
    # Rating
    performance_score = models.FloatField(default=0, verbose_name='درجة الأداء')
    rating = models.FloatField(default=0, verbose_name='التقييم')
    total_ratings = models.IntegerField(default=0, verbose_name='إجمالي التقييمات')
    
    # Activity
    last_login = models.DateTimeField(null=True, blank=True, verbose_name='آخر تسجيل دخول')
    last_property_added = models.DateTimeField(null=True, blank=True, verbose_name='آخر عقار مضاف')
    last_message_sent = models.DateTimeField(null=True, blank=True, verbose_name='آخر رسالة مرسلة')
    
    # Daily tracking
    daily_stats = models.JSONField(default=dict, verbose_name='إحصائيات يومية')
    
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'إحصائيات الدلال'
        verbose_name_plural = 'إحصائيات الدلالين'
    
    def __str__(self):
        return f'إحصائيات {self.broker.display_name}'
    
    def calculate_performance_score(self):
        """Calculate performance score based on various metrics"""
        score = 0
        
        # Properties added (max 30 points)
        if self.properties_added > 50:
            score += 30
        elif self.properties_added > 20:
            score += 20
        elif self.properties_added > 10:
            score += 10
        elif self.properties_added > 0:
            score += 5
        
        # Views (max 25 points)
        if self.total_views > 1000:
            score += 25
        elif self.total_views > 500:
            score += 20
        elif self.total_views > 100:
            score += 15
        elif self.total_views > 50:
            score += 10
        elif self.total_views > 0:
            score += 5
        
        # Response time (max 25 points) - lower is better
        if self.average_response_time > 0:
            if self.average_response_time < 5:
                score += 25
            elif self.average_response_time < 15:
                score += 20
            elif self.average_response_time < 30:
                score += 15
            elif self.average_response_time < 60:
                score += 10
            else:
                score += 5
        
        # Active properties (max 20 points)
        if self.properties_active > 20:
            score += 20
        elif self.properties_active > 10:
            score += 15
        elif self.properties_active > 5:
            score += 10
        elif self.properties_active > 0:
            score += 5
        
        self.performance_score = score
        self.save()
        return score
    
    def update_properties_stats(self):
        """Update properties statistics"""
        from .models import Property
        self.properties_active = Property.objects.filter(broker=self.broker, status='active').count()
        self.save()
    
    def update_views_stats(self):
        """Update views statistics"""
        from django.utils import timezone
        from .models import PropertyView
        
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        # Get all properties by this broker
        properties = Property.objects.filter(broker=self.broker)
        property_ids = properties.values_list('id', flat=True)
        
        # Count views
        self.total_views = PropertyView.objects.filter(property_id__in=property_ids).count()
        self.views_today = PropertyView.objects.filter(
            property_id__in=property_ids,
            viewed_at__date=today
        ).count()
        self.views_this_month = PropertyView.objects.filter(
            property_id__in=property_ids,
            viewed_at__date__gte=month_start
        ).count()
        
        self.save()
    
    def update_response_time(self, response_time_minutes):
        """Update response time statistics"""
        if self.average_response_time == 0:
            self.average_response_time = response_time_minutes
            self.fastest_response_time = response_time_minutes
            self.slowest_response_time = response_time_minutes
        else:
            # Update average
            total_responses = self.average_response_time  # This should be tracked separately
            self.average_response_time = (self.average_response_time + response_time_minutes) / 2
            
            # Update fastest/slowest
            if response_time_minutes < self.fastest_response_time or self.fastest_response_time == 0:
                self.fastest_response_time = response_time_minutes
            if response_time_minutes > self.slowest_response_time:
                self.slowest_response_time = response_time_minutes
        
        self.save()
    
    @classmethod
    def track_property_added(cls, broker):
        """Track when a broker adds a property"""
        from django.utils import timezone
        stats, created = cls.objects.get_or_create(broker=broker)
        stats.properties_added += 1
        stats.last_property_added = timezone.now()
        stats.update_properties_stats()
        stats.save()
    
    @classmethod
    def track_property_deleted(cls, broker):
        """Track when a broker deletes a property"""
        stats, created = cls.objects.get_or_create(broker=broker)
        stats.properties_deleted += 1
        stats.update_properties_stats()
        stats.save()
    
    @classmethod
    def track_message_sent(cls, broker):
        """Track when a broker sends a message"""
        from django.utils import timezone
        stats, created = cls.objects.get_or_create(broker=broker)
        stats.last_message_sent = timezone.now()
        stats.save()


class Role(models.Model):
    """نظام الأدوار والصلاحيات المتقدم"""
    
    ROLE_CHOICES = [
        ('super_admin', 'مسؤول النظام'),
        ('admin', 'مسؤول'),
        ('main_broker', 'دلال رئيسي'),
        ('sub_broker', 'دلال فرعي'),
        ('verified_broker', 'دلال موثق'),
        ('regular_broker', 'دلال عادي'),
        ('premium_user', 'مستخدم مميز'),
        ('regular_user', 'مستخدم عادي'),
    ]
    
    name = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True, verbose_name='اسم الدور')
    display_name = models.CharField(max_length=100, verbose_name='الاسم المعروض')
    description = models.TextField(blank=True, verbose_name='الوصف')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    priority = models.IntegerField(default=0, verbose_name='الأولوية')
    
    # Permissions flags
    can_access_admin_panel = models.BooleanField(default=False, verbose_name='الوصول للوحة الإدارة')
    can_manage_users = models.BooleanField(default=False, verbose_name='إدارة المستخدمين')
    can_manage_brokers = models.BooleanField(default=False, verbose_name='إدارة الدلالين')
    can_manage_properties = models.BooleanField(default=False, verbose_name='إدارة العقارات')
    can_manage_auctions = models.BooleanField(default=False, verbose_name='إدارة المزادات')
    can_manage_building_requests = models.BooleanField(default=False, verbose_name='إدارة طلبات البناء')
    can_approve_content = models.BooleanField(default=False, verbose_name='الموافقة على المحتوى')
    can_view_statistics = models.BooleanField(default=False, verbose_name='عرض الإحصائيات')
    can_export_data = models.BooleanField(default=False, verbose_name='تصدير البيانات')
    can_manage_settings = models.BooleanField(default=False, verbose_name='إدارة الإعدادات')
    can_send_notifications = models.BooleanField(default=False, verbose_name='إرسال إشعارات')
    can_moderate_users = models.BooleanField(default=False, verbose_name='مراقبة المستخدمين')
    can_issue_warnings = models.BooleanField(default=False, verbose_name='إصدار إنذارات')
    can_suspend_users = models.BooleanField(default=False, verbose_name='تعطيل المستخدمين')
    can_delete_users = models.BooleanField(default=False, verbose_name='حذف المستخدمين')
    
    # Property permissions
    can_add_properties = models.BooleanField(default=False, verbose_name='إضافة عقارات')
    can_edit_own_properties = models.BooleanField(default=False, verbose_name='تعديل عقاراته')
    can_edit_all_properties = models.BooleanField(default=False, verbose_name='تعديل جميع العقارات')
    can_delete_own_properties = models.BooleanField(default=False, verbose_name='حذف عقاراته')
    can_delete_all_properties = models.BooleanField(default=False, verbose_name='حذف جميع العقارات')
    can_feature_properties = models.BooleanField(default=False, verbose_name='تمييز العقارات')
    
    # Broker permissions
    can_verify_brokers = models.BooleanField(default=False, verbose_name='توثيق الدلالين')
    can_assign_roles = models.BooleanField(default=False, verbose_name='تعيين الأدوار')
    can_manage_sub_brokers = models.BooleanField(default=False, verbose_name='إدارة الدلالين الفرعيين')
    can_view_broker_stats = models.BooleanField(default=False, verbose_name='عرض إحصائيات الدلالين')
    
    # Financial permissions
    can_view_financial_data = models.BooleanField(default=False, verbose_name='عرض البيانات المالية')
    can_manage_payments = models.BooleanField(default=False, verbose_name='إدارة المدفوعات')
    can_manage_subscriptions = models.BooleanField(default=False, verbose_name='إدارة الاشتراكات')
    can_view_commissions = models.BooleanField(default=False, verbose_name='عرض العمولات')
    
    # Content permissions
    can_create_posts = models.BooleanField(default=False, verbose_name='إنشاء منشورات')
    can_edit_all_posts = models.BooleanField(default=False, verbose_name='تعديل جميع المنشورات')
    can_delete_posts = models.BooleanField(default=False, verbose_name='حذف المنشورات')
    can_upload_videos = models.BooleanField(default=False, verbose_name='رفع فيديوهات')
    
    # Communication permissions
    can_send_messages = models.BooleanField(default=False, verbose_name='إرسال رسائل')
    can_view_all_messages = models.BooleanField(default=False, verbose_name='عرض جميع الرسائل')
    can_broadcast_messages = models.BooleanField(default=False, verbose_name='بث رسائل')
    
    # Regional permissions
    allowed_governorates = models.JSONField(default=list, blank=True, verbose_name='المحافظات المسموحة')
    can_access_all_regions = models.BooleanField(default=False, verbose_name='الوصول لجميع المناطق')
    
    # Limits
    max_properties = models.IntegerField(null=True, blank=True, verbose_name='الحد الأقصى للعقارات')
    max_sub_brokers = models.IntegerField(null=True, blank=True, verbose_name='الحد الأقصى للدلالين الفرعيين')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'دور'
        verbose_name_plural = 'الأدوار'
        ordering = ['-priority', 'name']
    
    def __str__(self):
        return self.display_name
    
    def has_permission(self, permission_name):
        """Check if role has specific permission"""
        return getattr(self, permission_name, False)


class UserRole(models.Model):
    """ربط المستخدم بالأدوار"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles', verbose_name='المستخدم')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='role_users', verbose_name='الدور')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_roles', verbose_name='عين بواسطة')
    assigned_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التعيين')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الانتهاء')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    
    class Meta:
        verbose_name = 'دور مستخدم'
        verbose_name_plural = 'أدوار المستخدمين'
        unique_together = ['user', 'role']
    
    def __str__(self):
        return f'{self.user.username} - {self.role.display_name}'
    
    def is_valid(self):
        """Check if role assignment is still valid"""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True


class AdvancedSubscriptionPlan(models.Model):
    """نماذج الاشتراكات المتخصصة"""
    
    PLAN_TYPE_CHOICES = [
        ('properties_iraq', 'عقارات داخل العراق'),
        ('properties_outside', 'عقارات خارج العراق'),
        ('hotels', 'فنادق'),
        ('resorts', 'منتجعات'),
        ('building_requests', 'طلبات بناء'),
        ('auctions', 'مزادات'),
        ('combined', 'اشتراك مركب'),
    ]
    
    TIER_CHOICES = [
        ('regular', 'عادي'),
        ('premium', 'مميز'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='اسم الخطة')
    plan_type = models.CharField(max_length=30, choices=PLAN_TYPE_CHOICES, verbose_name='نوع الخطة')
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, verbose_name='المستوى')
    
    # Pricing
    price_per_day = models.DecimalField(max_digits=10, decimal_places=0, verbose_name='السعر باليوم')
    price_per_month = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name='السعر بالشهر')
    price_per_year = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name='السعر بالسنة')
    
    # Limits
    max_properties = models.IntegerField(default=1, verbose_name='الحد الأقصى للعقارات')
    max_auctions = models.IntegerField(default=0, verbose_name='الحد الأقصى للمزادات')
    max_building_requests = models.IntegerField(default=0, verbose_name='الحد الأقصى لطلبات البناء')
    
    # Features
    allow_property_replacement = models.BooleanField(default=True, verbose_name='السماح باستبدال العقارات')
    allow_subscription_renewal = models.BooleanField(default=True, verbose_name='السماح بتجديد الاشتراك')
    allow_expired_renewal = models.BooleanField(default=True, verbose_name='السماح بالتجديد على اشتراك منتهي')
    
    # Time calculation
    extend_on_property_display = models.BooleanField(default=False, verbose_name='تمديد الوقت عند عرض العقار')
    extend_days_per_display = models.IntegerField(default=0, verbose_name='أيام التمديد لكل عرض')
    
    description = models.TextField(blank=True, verbose_name='الوصف')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'خطة اشتراك متقدمة'
        verbose_name_plural = 'خطط الاشتراك المتقدمة'
        ordering = ['plan_type', 'tier']
    
    def __str__(self):
        return f'{self.name} - {self.get_tier_display()}'


class BrokerPlanSubscription(models.Model):
    """اشتراكات الدلالين"""
    
    STATUS_CHOICES = [
        ('active', 'نشط'),
        ('expired', 'منتهي'),
        ('suspended', 'معلق'),
        ('pending', 'قيد الانتظار'),
    ]
    
    broker = models.ForeignKey('Broker', on_delete=models.CASCADE, related_name='plan_subscriptions', verbose_name='الدلال')
    plan = models.ForeignKey(AdvancedSubscriptionPlan, on_delete=models.PROTECT, related_name='plan_subscriptions', verbose_name='الخطة')
    
    # Time tracking
    start_date = models.DateTimeField(verbose_name='تاريخ البداية')
    end_date = models.DateTimeField(verbose_name='تاريخ النهاية')
    actual_end_date = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الانتهاء الفعلي')
    
    # Usage tracking
    properties_used = models.IntegerField(default=0, verbose_name='العقارات المستخدمة')
    properties_replaced = models.IntegerField(default=0, verbose_name='العقارات المستبدلة')
    auctions_used = models.IntegerField(default=0, verbose_name='المزادات المستخدمة')
    building_requests_used = models.IntegerField(default=0, verbose_name='طلبات البناء المستخدمة')
    
    # Property replacement tracking
    last_replaced_at = models.DateTimeField(null=True, blank=True, verbose_name='آخر استبدال')
    replacement_history = models.JSONField(default=list, blank=True, verbose_name='تاريخ الاستبدال')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name='الحالة')
    is_auto_renew = models.BooleanField(default=False, verbose_name='تجديد تلقائي')
    
    # Payment
    total_paid = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='المبلغ المدفوع')
    payment_method = models.CharField(max_length=50, blank=True, verbose_name='طريقة الدفع')
    
    # Notes
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'اشتراك خطة دلال'
        verbose_name_plural = 'اشتراكات خطط الدلالين'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.broker.display_name} - {self.plan.name}'
    
    def get_seconds_remaining(self):
        """حساب الثواني المتبقية بدقة"""
        from django.utils import timezone
        now = timezone.now()
        if self.actual_end_date:
            end = self.actual_end_date
        else:
            end = self.end_date
        
        if end > now:
            delta = end - now
            return int(delta.total_seconds())
        return 0
    
    def is_active(self):
        """التحقق من أن الاشتراك نشط"""
        from django.utils import timezone
        return self.status == 'active' and self.get_seconds_remaining() > 0
    
    def can_add_property(self):
        """التحقق من إمكانية إضافة عقار"""
        if not self.is_active():
            return False
        return self.properties_used < self.plan.max_properties
    
    def can_replace_property(self):
        """التحقق من إمكانية استبدال عقار"""
        if not self.is_active():
            return False
        if not self.plan.allow_property_replacement:
            return False
        return self.properties_used > 0
    
    def can_add_auction(self):
        """التحقق من إمكانية إضافة مزاد"""
        if not self.is_active():
            return False
        return self.auctions_used < self.plan.max_auctions
    
    def use_auction(self):
        """استخدام مزاد من الحصة"""
        if not self.can_add_auction():
            return False
        self.auctions_used += 1
        self.save()
        return True
    
    def replace_property(self, old_property_id, new_property_id):
        """استبدال عقار"""
        if not self.can_replace_property():
            return False
        
        from django.utils import timezone
        self.properties_replaced += 1
        self.last_replaced_at = timezone.now()
        
        # Add to replacement history
        self.replacement_history.append({
            'old_property_id': old_property_id,
            'new_property_id': new_property_id,
            'replaced_at': timezone.now().isoformat(),
        })
        
        self.save()
        return True
    
    def extend_on_display(self):
        """تمديد الوقت عند عرض العقار"""
        if not self.plan.extend_on_property_display:
            return False
        
        from django.utils import timezone, timedelta
        days = self.plan.extend_days_per_display
        if self.actual_end_date:
            self.actual_end_date += timedelta(days=days)
        else:
            self.end_date += timedelta(days=days)
        
        self.save()
        return True
    
    def renew(self, days):
        """تجديد الاشتراك"""
        from django.utils import timezone, timedelta
        
        if self.actual_end_date:
            new_end = max(timezone.now(), self.actual_end_date) + timedelta(days=days)
            self.actual_end_date = new_end
        else:
            new_end = max(timezone.now(), self.end_date) + timedelta(days=days)
            self.end_date = new_end
        
        self.status = 'active'
        self.save()
        return True


class SubscriptionRenewalRequest(models.Model):
    """طلبات تجديد الاشتراك"""
    
    STATUS_CHOICES = [
        ('pending', 'قيد الانتظار'),
        ('approved', 'موافق عليه'),
        ('rejected', 'مرفوض'),
        ('completed', 'مكتمل'),
    ]
    
    broker = models.ForeignKey('Broker', on_delete=models.CASCADE, related_name='renewal_requests', verbose_name='الدلال')
    current_subscription = models.ForeignKey(BrokerPlanSubscription, on_delete=models.SET_NULL, null=True, blank=True, related_name='renewal_requests', verbose_name='الاشتراك الحالي')
    
    plan = models.ForeignKey(AdvancedSubscriptionPlan, on_delete=models.PROTECT, verbose_name='الخطة المطلوبة')
    days_requested = models.IntegerField(verbose_name='الأيام المطلوبة')
    property_count = models.IntegerField(default=1, verbose_name='عدد العقارات الإجمالي')
    regular_count = models.IntegerField(default=0, verbose_name='عدد العقارات العادية')
    premium_count = models.IntegerField(default=0, verbose_name='عدد العقارات المميزة')
    
    # Property type selection
    property_types = models.JSONField(default=list, verbose_name='أنواع العقارات المطلوبة')
    
    # Pricing
    estimated_cost = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='التكلفة التقديرية')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة')
    rejection_reason = models.TextField(blank=True, verbose_name='سبب الرفض')
    
    approved_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_renewals', verbose_name='تمت الموافقة بواسطة')
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الموافقة')
    approval_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP الموافقة')
    
    rejected_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='rejected_renewals', verbose_name='تم الرفض بواسطة')
    rejected_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الرفض')
    rejection_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP الرفض')
    
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    
    # Security tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP العنوان')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'طلب تجديد اشتراك'
        verbose_name_plural = 'طلبات تجديد الاشتراكات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.broker.display_name} - {self.plan.name}'


class BuildingRequestSubscription(models.Model):
    """اشتراكات طلبات البناء"""
    
    broker = models.ForeignKey('Broker', on_delete=models.CASCADE, related_name='building_plan_subscriptions', verbose_name='الدلال')
    
    # Pricing
    annual_price = models.DecimalField(max_digits=15, decimal_places=0, default=150000, verbose_name='السعر السنوي')
    
    # Time tracking
    start_date = models.DateTimeField(verbose_name='تاريخ البداية')
    end_date = models.DateTimeField(verbose_name='تاريخ النهاية')
    
    # Usage
    requests_used = models.IntegerField(default=0, verbose_name='الطلبات المستخدمة')
    max_requests = models.IntegerField(default=1, verbose_name='الحد الأقصى للطلبات')
    
    status = models.CharField(max_length=20, choices=BrokerPlanSubscription.STATUS_CHOICES, default='active', verbose_name='الحالة')
    
    total_paid = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='المبلغ المدفوع')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'اشتراك طلبات بناء'
        verbose_name_plural = 'اشتراكات طلبات البناء'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.broker.display_name} - طلبات بناء'


class AuctionSubscription(models.Model):
    """اشتراكات المزادات"""
    
    broker = models.ForeignKey('Broker', on_delete=models.CASCADE, related_name='auction_plan_subscriptions', verbose_name='الدلال')
    
    # Pricing
    price_per_auction = models.DecimalField(max_digits=15, decimal_places=0, default=100000, verbose_name='السعر لكل مزاد')
    
    # Usage
    auctions_used = models.IntegerField(default=0, verbose_name='المزادات المستخدمة')
    auctions_paid = models.IntegerField(default=0, verbose_name='المزادات المدفوعة')
    
    status = models.CharField(max_length=20, choices=BrokerPlanSubscription.STATUS_CHOICES, default='active', verbose_name='الحالة')
    
    total_paid = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='المبلغ المدفوع')
    
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'اشتراك مزادات'
        verbose_name_plural = 'اشتراكات المزادات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.broker.display_name} - مزادات'
    
    def can_create_auction(self):
        """التحقق من إمكانية إنشاء مزاد"""
        return self.status == 'active'
    
    def pay_for_auction(self):
        """دفع مقابل مزاد"""
        from django.utils import timezone
        self.auctions_paid += 1
        self.total_paid += self.price_per_auction
        self.save()


class PermissionLog(models.Model):
    """سجل تغييرات الصلاحيات"""
    
    ACTION_CHOICES = [
        ('assigned', 'تعيين'),
        ('revoked', 'إلغاء'),
        ('modified', 'تعديل'),
        ('expired', 'انتهاء'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='permission_logs', verbose_name='المستخدم')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='permission_logs', verbose_name='الدور')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='الإجراء')
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='permitted_logs', verbose_name='نفذ بواسطة')
    changes = models.JSONField(default=dict, verbose_name='التغييرات')
    reason = models.TextField(blank=True, verbose_name='السبب')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التغيير')
    
    class Meta:
        verbose_name = 'سجل صلاحية'
        verbose_name_plural = 'سجلات الصلاحيات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.action} - {self.role.display_name}'


class SiteSettings(models.Model):
    
    # General Settings
    site_name = models.CharField(max_length=100, default='دلال', verbose_name='اسم الموقع')
    tagline = models.CharField(max_length=200, blank=True, verbose_name='الشعار')
    favicon = models.ImageField(upload_to='site/', blank=True, verbose_name='الأيقونة (Favicon)')
    site_description = models.TextField(blank=True, verbose_name='وصف الموقع')
    default_language = models.CharField(max_length=10, default='ar', verbose_name='اللغة الافتراضية')
    timezone = models.CharField(max_length=50, default='Asia/Baghdad', verbose_name='المنطقة الزمنية')
    date_format = models.CharField(max_length=20, default='Y-m-d', verbose_name='تنسيق التاريخ')
    time_format = models.CharField(max_length=20, default='H:i', verbose_name='تنسيق الوقت')
    
    # Theme Settings
    theme_mode = models.CharField(max_length=10, choices=[('light', 'فاتح'), ('dark', 'داكن')], default='light', verbose_name='الوضع')
    primary_color = models.CharField(max_length=7, default='#0d9488', verbose_name='اللون الرئيسي')
    secondary_color = models.CharField(max_length=7, default='#f97316', verbose_name='اللون الثانوي')
    font_family = models.CharField(max_length=50, default='Cairo', verbose_name='نوع الخط')
    font_size = models.IntegerField(default=16, verbose_name='حجم الخط')
    button_style = models.CharField(max_length=20, default='rounded', verbose_name='شكل الأزرار')
    layout_style = models.CharField(max_length=20, default='boxed', verbose_name='تخطيط الصفحة')
    
    # Homepage Settings
    hero_banner_title = models.CharField(max_length=200, blank=True, verbose_name='عنوان البنر الرئيسي')
    hero_banner_subtitle = models.CharField(max_length=300, blank=True, verbose_name='عنوان فرعي للبنر')
    hero_banner_image = models.ImageField(upload_to='site/', blank=True, verbose_name='صورة البنر')
    show_featured_properties = models.BooleanField(default=True, verbose_name='إظهار العقارات المميزة')
    show_latest_properties = models.BooleanField(default=True, verbose_name='إظهار أحدث العقارات')
    show_brokers_section = models.BooleanField(default=True, verbose_name='إظهار قسم الدلالين')
    featured_properties_count = models.IntegerField(default=6, verbose_name='عدد العقارات المميزة')
    latest_properties_count = models.IntegerField(default=12, verbose_name='عدد أحدث العقارات')
    
    # User & Permissions Settings
    allow_registration = models.BooleanField(default=True, verbose_name='السماح بالتسجيل')
    require_email_verification = models.BooleanField(default=False, verbose_name='التحقق من البريد')
    require_phone_verification = models.BooleanField(default=False, verbose_name='التحقق من الهاتف')
    auto_activate_accounts = models.BooleanField(default=True, verbose_name='تفعيل الحساب تلقائياً')
    default_user_role = models.CharField(max_length=20, default='user', verbose_name='الدور الافتراضي')
    
    # Property Settings
    default_currency = models.CharField(max_length=3, default='IQD', verbose_name='العملة الافتراضية')
    area_unit = models.CharField(max_length=10, choices=[('m2', 'متر مربع'), ('ft2', 'قدم مربع')], default='m2', verbose_name='وحدة المساحة')
    max_images_per_property = models.IntegerField(default=20, verbose_name='الحد الأقصى للصور')
    allow_video_upload = models.BooleanField(default=True, verbose_name='السماح برفع الفيديو')
    allow_virtual_tours = models.BooleanField(default=True, verbose_name='السماح بالجولات الافتراضية')
    
    # Media Settings
    max_image_size = models.IntegerField(default=5242880, verbose_name='الحد الأقصى لحجم الصور (بايت)')
    allowed_image_types = models.CharField(max_length=200, default='jpg,jpeg,png,webp', verbose_name='أنواع الصور المسموحة')
    max_video_size = models.IntegerField(default=52428800, verbose_name='الحد الأقصى لحجم الفيديو (بايت)')
    allowed_video_types = models.CharField(max_length=200, default='mp4,webm', verbose_name='أنواع الفيديو المسموحة')
    
    # Notification Settings
    enable_site_notifications = models.BooleanField(default=True, verbose_name='إشعارات داخل الموقع')
    enable_email_notifications = models.BooleanField(default=True, verbose_name='إشعارات البريد الإلكتروني')
    enable_sms_notifications = models.BooleanField(default=False, verbose_name='إشعارات الرسائل النصية')
    enable_push_notifications = models.BooleanField(default=False, verbose_name='الإشعارات الفورية')
    
    # Payment Settings
    payment_methods = models.CharField(max_length=200, default='cash,bank_transfer', verbose_name='طرق الدفع')
    enable_subscriptions = models.BooleanField(default=True, verbose_name='تفعيل الاشتراكات')
    subscription_price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='سعر الاشتراك الشهري')
    subscription_price_yearly = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='سعر الاشتراك السنوي')
    enable_invoices = models.BooleanField(default=True, verbose_name='تفعيل الفواتير')
    
    # Security Settings
    enable_two_factor = models.BooleanField(default=False, verbose_name='المصادقة الثنائية')
    password_min_length = models.IntegerField(default=8, verbose_name='الحد الأدنى لكلمة المرور')
    require_special_chars = models.BooleanField(default=True, verbose_name='تطلب أحرف خاصة')
    session_timeout = models.IntegerField(default=3600, verbose_name='مدة الجلسة (ثواني)')
    log_login_attempts = models.BooleanField(default=True, verbose_name='تسجيل محاولات الدخول')
    
    # Report Settings
    enable_reports = models.BooleanField(default=True, verbose_name='تفعيل البلاغات')
    auto_review_reports = models.BooleanField(default=False, verbose_name='مراجعة تلقائية للبلاغات')
    report_priority_threshold = models.CharField(max_length=20, default='high', verbose_name='عتبة أولوية البلاغات')
    
    # Backup Settings
    auto_backup_enabled = models.BooleanField(default=False, verbose_name='النسخ الاحتياطي التلقائي')
    backup_frequency = models.CharField(max_length=20, default='daily', verbose_name='تكرار النسخ')
    backup_retention_days = models.IntegerField(default=30, verbose_name='مدة الاحتفاظ بالنسخ')
    
    # SEO Settings
    seo_title = models.CharField(max_length=200, blank=True, verbose_name='عنوان الموقع')
    seo_description = models.CharField(max_length=300, blank=True, verbose_name='وصف SEO')
    seo_keywords = models.CharField(max_length=500, blank=True, verbose_name='الكلمات المفتاحية')
    enable_og_tags = models.BooleanField(default=True, verbose_name='تفعيل Open Graph')
    
    # API Settings
    enable_api = models.BooleanField(default=False, verbose_name='تفعيل API')
    api_rate_limit = models.IntegerField(default=1000, verbose_name='حد الطلبات')
    api_key_required = models.BooleanField(default=True, verbose_name='تطلب مفتاح API')
    
    # System Info
    system_version = models.CharField(max_length=20, default='1.0.0', verbose_name='إصدار النظام')
    license_key = models.CharField(max_length=100, blank=True, verbose_name='مفتاح الترخيص')
    
    # Contact Info
    broker_phone = models.CharField(max_length=30, default='07701234567', verbose_name='هاتف التواصل')
    broker_email = models.EmailField(blank=True, verbose_name='البريد')
    broker_address = models.CharField(max_length=300, blank=True, verbose_name='العنوان')
    whatsapp = models.CharField(max_length=30, blank=True, verbose_name='واتساب')
    
    # About Section
    about_title = models.CharField(max_length=200, default='من نحن', verbose_name='عنوان من نحن')
    about_content = models.TextField(blank=True, verbose_name='محتوى من نحن')
    mission = models.TextField(blank=True, verbose_name='رسالتنا')
    
    # Social Media
    facebook_url = models.URLField(blank=True, verbose_name='فيسبوك')
    instagram_url = models.URLField(blank=True, verbose_name='إنستغرام')
    twitter_url = models.URLField(blank=True, verbose_name='تويتر')
    linkedin_url = models.URLField(blank=True, verbose_name='لينكد إن')

    # Maintenance Mode Settings
    maintenance_mode = models.BooleanField(default=False, verbose_name='وضع الصيانة')
    maintenance_message = models.TextField(
        default='الموقع تحت الصيانة، سنعود قريبًا. نعمل حاليًا على تحسين خدماتنا لتقديم تجربة أفضل.',
        verbose_name='رسالة الصيانة'
    )
    maintenance_end_time = models.DateTimeField(null=True, blank=True, verbose_name='وقت انتهاء الصيانة')
    allow_admins_during_maintenance = models.BooleanField(default=True, verbose_name='السماح للمشرفين أثناء الصيانة')

    class Meta:
        verbose_name = 'إعدادات الموقع'
        verbose_name_plural = 'إعدادات الموقع'

    def __str__(self):
        return self.site_name

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Property(models.Model):
    # Flatten PROPERTY_TYPES dictionary for choices
    def get_property_type_choices():
        choices = []
        for category, types in PROPERTY_TYPES.items():
            for type_code, type_name in types:
                choices.append((type_code, type_name))
        return choices

    PROPERTY_TYPES = get_property_type_choices()
    
    # New status choices for payment-based system
    STATUS_DRAFT = 'draft'
    STATUS_PAID = 'paid'
    STATUS_PENDING_APPROVAL = 'pending_approval'
    STATUS_PUBLISHED = 'published'
    STATUS_REJECTED = 'rejected'
    STATUS_EXPIRED = 'expired'
    STATUS_RENEWED = 'renewed'
    
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'مسودة'),
        (STATUS_PAID, 'تم الدفع'),
        (STATUS_PENDING_APPROVAL, 'بانتظار الموافقة'),
        (STATUS_PUBLISHED, 'منشور'),
        (STATUS_REJECTED, 'مرفوض'),
        (STATUS_EXPIRED, 'منتهي'),
        (STATUS_RENEWED, 'مجدد'),
    ]

    title = models.CharField(max_length=200, blank=True, default='', verbose_name='عنوان الإعلان')
    slug = models.SlugField(max_length=220, unique=True, blank=True, default='', allow_unicode=True)
    category = models.CharField(max_length=20, choices=PROPERTY_CATEGORIES, blank=True, null=True, verbose_name='تصنيف العقار')
    type = models.CharField(max_length=50, choices=PROPERTY_TYPES, verbose_name='نوع العقار')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, verbose_name='الحالة')
    
    # Property Purpose and Condition
    PURPOSE_CHOICES = [
        ('sale', 'بيع'),
        ('rent', 'إيجار'),
        ('investment', 'استثمار'),
        ('auction', 'مزاد'),
    ]
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, blank=True, null=True, verbose_name='الغرض')
    
    CONDITION_CHOICES = [
        ('new', 'جديد'),
        ('used', 'مستعمل'),
        ('under_construction', 'قيد الإنشاء'),
    ]
    property_condition = models.CharField(max_length=30, choices=CONDITION_CHOICES, blank=True, null=True, verbose_name='حالة العقار')
    
    OWNERSHIP_CHOICES = [
        ('title_deed', 'طابو'),
        ('agricultural', 'زراعي'),
        ('investment', 'استثماري'),
        ('commercial', 'تجاري'),
        ('other', 'أخرى'),
    ]
    ownership_status = models.CharField(max_length=30, choices=OWNERSHIP_CHOICES, blank=True, null=True, verbose_name='حالة الملكية')
    
    # Property ID and Owner Information
    property_number = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name='رقم الإعلان')
    owner_name = models.CharField(max_length=100, blank=True, null=True, verbose_name='اسم المالك (اختياري)')
    
    # Price and Currency
    negotiable = models.BooleanField(default=False, verbose_name='قابل للتفاوض')
    
    # Location fields - Iraq
    governorate = models.CharField(max_length=50, blank=True, null=True, verbose_name='المحافظة')
    city = models.CharField(max_length=50, blank=True, null=True, verbose_name='المدينة')
    district = models.CharField(max_length=100, verbose_name='الحي', help_text='اسم الحي')
    subdistrict = models.CharField(max_length=100, blank=True, null=True, verbose_name='القضاء')
    nahiyah = models.CharField(max_length=100, blank=True, null=True, verbose_name='الناحية')
    area = models.CharField(max_length=100, blank=True, null=True, verbose_name='المنطقة')
    street = models.CharField(max_length=100, blank=True, verbose_name='الشارع', help_text='اسم الشارع')
    landmark = models.CharField(max_length=200, blank=True, null=True, verbose_name='أقرب نقطة دالة')
    location = models.CharField(max_length=200, verbose_name='العنوان التفصيلي', help_text='العنوان الكامل')
    
    # Outside Iraq location fields
    country = models.ForeignKey('Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='properties', verbose_name='الدولة')
    city_outside = models.ForeignKey('City', on_delete=models.SET_NULL, null=True, blank=True, related_name='properties', verbose_name='المدينة')
    area_outside = models.ForeignKey('Area', on_delete=models.SET_NULL, null=True, blank=True, related_name='properties', verbose_name='المنطقة')
    postal_code = models.CharField(max_length=20, blank=True, null=True, verbose_name='الرمز البريدي')
    
    # GPS Coordinates
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='خط العرض')
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='خط الطول')
    
    # Area and Building
    total_area = models.PositiveIntegerField(null=True, blank=True, verbose_name='المساحة الكلية (م²)')
    building_area = models.PositiveIntegerField(null=True, blank=True, verbose_name='مساحة البناء (م²)')
    area = models.PositiveIntegerField(verbose_name='المساحة (م²)')  # Keep for backward compatibility
    price = models.BigIntegerField(verbose_name='السعر (د.ع)')
    
    # Currency for outside Iraq properties
    currency = models.CharField(max_length=3, blank=True, default='IQD', verbose_name='العملة')
    original_price = models.BigIntegerField(null=True, blank=True, verbose_name='السعر الأصلي بالعملة الأجنبية')
    
    # Additional Price Details
    price_per_meter = models.BigIntegerField(null=True, blank=True, verbose_name='سعر المتر')
    down_payment = models.BigIntegerField(null=True, blank=True, verbose_name='الدفعة الأولى')
    installments = models.TextField(blank=True, null=True, verbose_name='الأقساط (إن وجدت)')
    annual_maintenance_fee = models.BigIntegerField(null=True, blank=True, verbose_name='رسوم الصيانة السنوية')
    
    # Building Details
    facade = models.CharField(max_length=50, blank=True, null=True, verbose_name='الواجهة')
    direction = models.CharField(max_length=50, blank=True, null=True, verbose_name='الاتجاه')
    year_built = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='سنة البناء')
    building_condition = models.CharField(max_length=50, blank=True, null=True, verbose_name='حالة البناء')
    total_floors = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='عدد الطوابق')
    floor_number = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='رقم الطابق')
    
    # Additional Building Details
    floor_type = models.CharField(max_length=50, blank=True, null=True, verbose_name='نوع الأرضية')
    roof_type = models.CharField(max_length=50, blank=True, null=True, verbose_name='نوع السقف')
    wall_type = models.CharField(max_length=50, blank=True, null=True, verbose_name='نوع الجدران')
    finish_condition = models.CharField(max_length=50, blank=True, null=True, verbose_name='حالة التشطيب')
    last_maintenance = models.DateField(null=True, blank=True, verbose_name='آخر صيانة')
    
    # Room Details
    bedrooms = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='عدد الغرف')
    living_rooms = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='عدد الصالات')
    dining_rooms = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='عدد غرف الطعام')
    bathrooms = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='عدد الحمامات')
    kitchens = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='عدد المطابخ')
    balconies = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='عدد الشرفات')
    
    # Parking
    parking_spaces = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='عدد مواقف السيارات')
    parking = models.BooleanField(default=False, verbose_name='موقف سيارة')  # Keep for backward compatibility
    
    # Amenities
    furnished = models.BooleanField(default=False, verbose_name='مفروش')
    has_pool = models.BooleanField(default=False, verbose_name='مسبح')
    has_garden = models.BooleanField(default=False, verbose_name='حديقة')
    has_elevator = models.BooleanField(default=False, verbose_name='مصعد')
    has_generator = models.BooleanField(default=False, verbose_name='مولد')
    has_national_electricity = models.BooleanField(default=False, verbose_name='الكهرباء الوطنية')
    has_water = models.BooleanField(default=False, verbose_name='الماء')
    has_internet = models.BooleanField(default=False, verbose_name='الإنترنت')
    has_sewerage = models.BooleanField(default=False, verbose_name='المجاري')
    has_heating = models.BooleanField(default=False, verbose_name='التدفئة')
    has_cooling = models.BooleanField(default=False, verbose_name='التبريد')
    has_solar_power = models.BooleanField(default=False, verbose_name='نظام الطاقة الشمسية')
    
    # Security
    has_security_system = models.BooleanField(default=False, verbose_name='نظام الأمان')
    has_cctv = models.BooleanField(default=False, verbose_name='كاميرات المراقبة')
    has_alarm = models.BooleanField(default=False, verbose_name='نظام الإنذار')
    
    # Description
    description = models.TextField(verbose_name='وصف العقار')
    phone = models.CharField(max_length=20, verbose_name='رقم التواصل')
    
    # Floors (keep for backward compatibility)
    floors = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='عدد الطوابق')
    
    # Payment and publication fields
    publication_type = models.CharField(
        max_length=20,
        choices=[('normal', 'عادي'), ('featured', 'مميز')],
        default='normal',
        verbose_name='نوع النشر'
    )
    publication_days = models.PositiveIntegerField(null=True, blank=True, verbose_name='مدة النشر (أيام)')
    publication_start_date = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ بدء النشر')
    publication_end_date = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ انتهاء النشر')
    rejection_reason = models.TextField(blank=True, verbose_name='سبب الرفض')

    # image field removed - column does not exist in database
    # image = models.ImageField(upload_to=property_image_path, null=True, blank=True, verbose_name='الصورة الرئيسية')
    images = models.TextField(blank=True, help_text='روابط صور إضافية (قديم)')

    is_featured = models.BooleanField(default=False, verbose_name='عقار مميز')
    is_promoted = models.BooleanField(default=False, verbose_name='إعلان خاص')
    promotion_until = models.DateField(null=True, blank=True, verbose_name='انتهاء الترويج')
    is_pinned = models.BooleanField(default=False, verbose_name='مثبت في الأعلى')
    pinned_until = models.DateTimeField(null=True, blank=True, verbose_name='مثبت حتى')
    
    # Cover and personal images
    cover_image = models.ImageField(upload_to='property_covers/', null=True, blank=True, verbose_name='صورة الغلاف')
    personal_image = models.ImageField(upload_to='property_personal/', null=True, blank=True, verbose_name='صورة شخصية')

    views_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاهدات')
    view_commission_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=50.00,
        verbose_name='عمولة المشاهدة (دينار)',
        help_text='عمولة كل مشاهدة للعقار'
    )
    total_view_commission = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='إجمالي عمولة المشاهدات'
    )
    paid_view_commission = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='عمولة المشاهدات المدفوعة'
    )
    pending_view_commission = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='عمولة المشاهدات المعلقة'
    )

    owner = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='owned_properties', verbose_name='صاحب الإعلان'
    )
    broker = models.ForeignKey(
        'Broker', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='properties', verbose_name='الدلال'
    )
    office = models.ForeignKey(
        'Office', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='properties', verbose_name='المكتب العقاري'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'عقار'
        verbose_name_plural = 'العقارات'
        ordering = ['-is_pinned', '-is_featured', '-is_promoted', '-created_at']
        indexes = [
            models.Index(fields=['district']),
            models.Index(fields=['type', 'status']),
            models.Index(fields=['price']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['is_featured', 'is_promoted', 'is_pinned']),
        ]

    def __str__(self):
        return self.display_title

    @property
    def display_title(self):
        if self.title:
            return self.title
        return f'{self.get_type_display()} - {self.district}'

    @property
    def full_location(self):
        parts = []
        if self.district:
            parts.append(self.district)
        if self.street:
            parts.append(self.street)
        if self.location:
            parts.append(self.location)
        return '، '.join(p for p in parts if p)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.title:
            self.title = f'{self.get_type_display()} - {self.district}'
        super().save(*args, **kwargs)
        if is_new or not self.slug:
            base = slugify(f'{self.title}-{self.district}-{self.pk}', allow_unicode=True)
            if not base:
                base = f'property-{self.pk}'
            slug = base
            counter = 1
            while Property.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{counter}'
                counter += 1
            Property.objects.filter(pk=self.pk).update(slug=slug)
            self.slug = slug

    def get_absolute_url(self):
        return reverse('property_detail', kwargs={'slug': self.slug})

    def get_all_images(self):
        urls = []
        for img in self.gallery_images.all():
            if img.image:
                urls.append(img.image.url)
        # image field removed - column does not exist in database
        # if self.image and self.image.url not in urls:
        #     urls.insert(0, self.image.url)
        if self.images:
            for url in self.images.split(','):
                url = url.strip()
                if url and url not in urls:
                    urls.append(url)
        return urls or ['/static/img/placeholder-property.svg']

    def get_main_image(self):
        imgs = self.get_all_images()
        return imgs[0] if imgs else None

    def increment_views(self):
        Property.objects.filter(pk=self.pk).update(views_count=models.F('views_count') + 1)
        self.refresh_from_db(fields=['views_count'])
        
        # Calculate and add view commission
        commission_amount = self.view_commission_rate
        self.total_view_commission += commission_amount
        self.pending_view_commission += commission_amount
        self.save(update_fields=['total_view_commission', 'pending_view_commission'])
        
        # Update broker's total commissions if broker exists
        if self.broker:
            self.broker.total_commissions += commission_amount
            self.broker.pending_commissions += commission_amount
            self.broker.save(update_fields=['total_commissions', 'pending_commissions'])
    
    def pay_view_commission(self, amount):
        """دفع عمولة المشاهدات"""
        if amount > self.pending_view_commission:
            raise ValueError('المبلغ المطلوب أكبر من العمولة المعلقة')
        
        self.paid_view_commission += amount
        self.pending_view_commission -= amount
        self.save(update_fields=['paid_view_commission', 'pending_view_commission'])
        
        # Update broker's commissions if broker exists
        if self.broker:
            self.broker.paid_commissions += amount
            self.broker.pending_commissions -= amount
            self.broker.save(update_fields=['paid_commissions', 'pending_commissions'])
    
    def get_view_commission_summary(self):
        """الحصول على ملخص عمولات المشاهدات"""
        return {
            'rate': self.view_commission_rate,
            'total': self.total_view_commission,
            'paid': self.paid_view_commission,
            'pending': self.pending_view_commission,
            'balance': self.total_view_commission - self.paid_view_commission,
            'views': self.views_count,
        }

    def has_map(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def price_formatted(self):
        return f'{self.price:,}'
    
    def is_expired(self):
        """Check if property publication has expired"""
        if not self.expiry_date:
            return False
        from django.utils import timezone
        return timezone.now() > self.expiry_date
    
    def freeze(self, reason='انتهاء الاشتراك'):
        """Freeze the property"""
        from django.utils import timezone
        self.is_frozen = True
        self.frozen_at = timezone.now()
        self.frozen_reason = reason
        self.status = 'draft'  # Change status to draft to hide from public
        self.save(update_fields=['is_frozen', 'frozen_at', 'frozen_reason', 'status'])
    
    def unfreeze(self):
        """Unfreeze the property"""
        self.is_frozen = False
        self.frozen_at = None
        self.frozen_reason = ''
        self.status = 'published'  # Restore published status
        self.save(update_fields=['is_frozen', 'frozen_at', 'frozen_reason', 'status'])
    
    def calculate_expiry_date(self, broker):
        """Calculate expiry date based on broker's subscription"""
        from django.utils import timezone
        from datetime import timedelta
        
        if not broker or not broker.subscription_end_date:
            # Default 30 days if no subscription
            return timezone.now() + timedelta(days=30)
        
        # Use subscription end date as expiry
        return broker.subscription_end_date
    
    def save(self, *args, **kwargs):
        # Set publication date on first save if not set
        if not self.pk and not self.publication_date:
            from django.utils import timezone
            self.publication_date = timezone.now()
        
        # Calculate expiry date on first save if not set
        if not self.pk and not self.expiry_date and hasattr(self, 'owner'):
            try:
                from .models import Broker
                broker = Broker.objects.filter(user=self.owner).first()
                if broker:
                    self.expiry_date = self.calculate_expiry_date(broker)
            except:
                pass
        
        # Check if property should be frozen due to expired subscription
        if self.pk and not self.is_frozen:
            try:
                from .models import Broker
                broker = Broker.objects.filter(user=self.owner).first()
                if broker and broker.is_subscription_expired():
                    self.freeze('انتهاء الاشتراك')
            except:
                pass
        
        super().save(*args, **kwargs)
    
    # Hotel/Resort specific fields
    hotel_stars = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='عدد النجوم')
    hotel_rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True, verbose_name='التقييم')
    hotel_rooms = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='عدد الغرف')
    hotel_suites = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='عدد الأجنحة')
    hotel_family_rooms = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='الغرف العائلية')
    
    # Publication expiry and subscription tracking
    publication_date = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ النشر')
    expiry_date = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ انتهاء الصلاحية')
    is_frozen = models.BooleanField(default=False, verbose_name='مجمد')
    frozen_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ التجميد')
    frozen_reason = models.CharField(max_length=200, blank=True, verbose_name='سبب التجميد')
    
    # Hotel services
    has_restaurant = models.BooleanField(default=False, verbose_name='مطعم')
    has_cafe = models.BooleanField(default=False, verbose_name='مقهى')
    has_swimming_pool = models.BooleanField(default=False, verbose_name='مسبح')
    has_gym = models.BooleanField(default=False, verbose_name='نادي رياضي')
    has_spa = models.BooleanField(default=False, verbose_name='سبا')
    has_conference_hall = models.BooleanField(default=False, verbose_name='قاعة مؤتمرات')
    has_wifi = models.BooleanField(default=False, verbose_name='واي فاي')
    has_parking = models.BooleanField(default=False, verbose_name='موقف سيارات')
    has_room_service = models.BooleanField(default=False, verbose_name='خدمة الغرف')
    has_laundry = models.BooleanField(default=False, verbose_name='خدمة الغسيل')
    has_airport_shuttle = models.BooleanField(default=False, verbose_name='نقل من المطار')
    
    # Resort/Tourism specific fields
    resort_capacity = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='سعة الاستيعاب')
    resort_activities = models.TextField(blank=True, verbose_name='الأنشطة المتاحة')
    booking_available = models.BooleanField(default=False, verbose_name='الحجز متاح')
    booking_url = models.URLField(blank=True, verbose_name='رابط الحجز')
    min_booking_duration = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='أقل مدة حجز (أيام)')
    max_booking_duration = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='أقصى مدة حجز (أيام)')
    
    # Outside Iraq specific fields
    taxes = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='الضرائب (%)')
    registration_fees = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='رسوم التسجيل')
    foreign_ownership_laws = models.TextField(blank=True, verbose_name='قوانين التملك للأجانب')
    
    # Virtual Tour and Media
    virtual_tour_url = models.URLField(blank=True, verbose_name='رابط الجولة الافتراضية')
    vr_tour_url = models.URLField(blank=True, verbose_name='رابط جولة VR')
    ar_available = models.BooleanField(default=False, verbose_name='دعم الواقع المعزز')
    qr_code = models.ImageField(upload_to='qr_codes/', null=True, blank=True, verbose_name='QR Code')
    short_share_code = models.CharField(max_length=20, unique=True, blank=True, verbose_name='رمز المشاركة المختصر')
    
    # Live Streaming
    live_stream_enabled = models.BooleanField(default=False, verbose_name='تفعيل البث المباشر')
    live_stream_url = models.URLField(blank=True, verbose_name='رابط البث المباشر')
    live_stream_scheduled = models.DateTimeField(null=True, blank=True, verbose_name='موعد البث المجدول')
    live_stream_status = models.CharField(
        max_length=20,
        choices=[('scheduled', 'مجدول'), ('live', 'مباشر'), ('ended', 'منتهي'), ('cancelled', 'ملغي')],
        blank=True,
        verbose_name='حالة البث'
    )
    
    # AI Features
    ai_generated_description = models.TextField(blank=True, verbose_name='وصف مولد بالذكاء الاصطناعي')
    ai_suggested_price = models.BigIntegerField(null=True, blank=True, verbose_name='السعر المقترح')
    ai_keywords = models.TextField(blank=True, verbose_name='كلمات مفتاحية مقترحة')
    ai_image_enhanced = models.BooleanField(default=False, verbose_name='تم تحسين الصور')
    
    # Additional location details
    nearest_landmark = models.CharField(max_length=200, blank=True, verbose_name='أقرب معلم')
    distance_to_city_center = models.PositiveIntegerField(null=True, blank=True, verbose_name='المسافة لمركز المدينة (كم)')
    distance_to_airport = models.PositiveIntegerField(null=True, blank=True, verbose_name='المسافة للمطار (كم)')
    
    # Additional property details
    property_age = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='عمر العقار (سنوات)')
    last_renovation = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='سنة آخر ترميم')
    maintenance_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='رسوم الصيانة الشهرية')
    hoa_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='رسوم الجمعية')
    
    # Accessibility
    wheelchair_accessible = models.BooleanField(default=False, verbose_name='مخصص للكراسي المتحركة')
    has_ramp = models.BooleanField(default=False, verbose_name='منحدر')
    has_elevator_accessibility = models.BooleanField(default=False, verbose_name='مصعد متاح')
    
    # Green features
    energy_efficient = models.BooleanField(default=False, verbose_name='موفر للطاقة')
    has_green_building_cert = models.BooleanField(default=False, verbose_name='شهادة بناء أخضر')
    has_smart_home = models.BooleanField(default=False, verbose_name='منزل ذكي')
    has_double_glazing = models.BooleanField(default=False, verbose_name='زجاج مزدوج')
    has_insulation = models.BooleanField(default=False, verbose_name='عزل حراري')
    
    # Parking details
    parking_type = models.CharField(
        max_length=20,
        choices=[('covered', 'مغطى'), ('open', 'مفتوح'), ('underground', 'تحت الأرض'), ('garage', 'مرآب')],
        blank=True,
        verbose_name='نوع الموقف'
    )
    
    # View and orientation
    view_type = models.CharField(
        max_length=50,
        choices=[
            ('city', 'إطلالة مدينة'),
            ('sea', 'إطلالة بحر'),
            ('mountain', 'إطلالة جبل'),
            ('garden', 'إطلالة حديقة'),
            ('street', 'إطلالة شارع'),
            ('park', 'إطلالة حديقة عامة'),
            ('none', 'لا يوجد'),
        ],
        blank=True,
        verbose_name='نوع الإطلالة'
    )


class PropertyImage(models.Model):
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='gallery_images', verbose_name='العقار'
    )
    image = models.ImageField(upload_to=property_image_path, verbose_name='الصورة')
    caption = models.CharField(max_length=200, blank=True, verbose_name='تعليق')
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name='الترتيب')
    is_primary = models.BooleanField(default=False, verbose_name='رئيسية')
    is_360 = models.BooleanField(default=False, verbose_name='صورة 360°')
    image_type = models.CharField(
        max_length=20,
        choices=[
            ('photo', 'صورة عادية'),
            ('360', 'صورة 360°'),
            ('floor_plan', 'مخطط طابق'),
            ('site_plan', 'مخطط موقع'),
            ('drone', 'تصوير جوي'),
        ],
        default='photo',
        verbose_name='نوع الصورة'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'صورة عقار'
        verbose_name_plural = 'صور العقارات'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'صورة {self.property_id} #{self.pk}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # image field removed - column does not exist in database
        # if self.is_primary and self.image:
        #     prop = self.property
        #     prop.image = self.image
        #     prop.save(update_fields=['image'])


class PropertyVideo(models.Model):
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='gallery_videos', verbose_name='العقار'
    )
    video = models.FileField(upload_to=property_video_path, verbose_name='الفيديو')
    caption = models.CharField(max_length=200, blank=True, verbose_name='تعليق')
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name='الترتيب')
    video_type = models.CharField(
        max_length=20,
        choices=[
            ('regular', 'فيديو عادي'),
            ('drone', 'فيديو Drone'),
            ('intro', 'فيديو تعريفي'),
            ('virtual_tour', 'جولة افتراضية'),
        ],
        default='regular',
        verbose_name='نوع الفيديو'
    )
    duration = models.PositiveIntegerField(null=True, blank=True, verbose_name='المدة (ثواني)')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'فيديو عقار'
        verbose_name_plural = 'فيديوهات العقارات'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'فيديو {self.property_id} #{self.pk}'


class PropertyDocument(models.Model):
    """نموذج للمستندات والملفات"""
    
    DOCUMENT_TYPES = [
        ('pdf', 'ملف PDF'),
        ('ownership', 'وثيقة الملكية'),
        ('contract', 'عقد'),
        ('floor_plan', 'مخطط الطابق'),
        ('site_plan', 'مخطط الموقع'),
        ('other', 'أخرى'),
    ]
    
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='documents',
        verbose_name='العقار'
    )
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, verbose_name='نوع المستند')
    title = models.CharField(max_length=200, verbose_name='عنوان المستند')
    file = models.FileField(upload_to='property_documents/', verbose_name='الملف')
    description = models.TextField(blank=True, verbose_name='الوصف')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'مستند عقار'
        verbose_name_plural = 'مستندات العقارات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.title} - {self.property.display_title}'


class PropertyMediaStats(models.Model):
    """إحصائيات الوسائط للعقارات"""
    
    property = models.OneToOneField(
        Property, on_delete=models.CASCADE, related_name='media_stats',
        verbose_name='العقار'
    )
    
    # Image stats
    total_images = models.PositiveIntegerField(default=0, verbose_name='عدد الصور')
    image_views = models.PositiveIntegerField(default=0, verbose_name='مشاهدات الصور')
    
    # Video stats
    total_videos = models.PositiveIntegerField(default=0, verbose_name='عدد الفيديوهات')
    video_views = models.PositiveIntegerField(default=0, verbose_name='مشاهدات الفيديوهات')
    
    # 360 tour stats
    total_360_tours = models.PositiveIntegerField(default=0, verbose_name='عدد الجولات 360°')
    tour_views = models.PositiveIntegerField(default=0, verbose_name='مشاهدات الجولات')
    
    # Document stats
    total_documents = models.PositiveIntegerField(default=0, verbose_name='عدد المستندات')
    document_downloads = models.PositiveIntegerField(default=0, verbose_name='تحميلات المستندات')
    
    # VR/AR stats
    vr_views = models.PositiveIntegerField(default=0, verbose_name='مشاهدات VR')
    ar_views = models.PositiveIntegerField(default=0, verbose_name='مشاهدات AR')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'إحصائيات الوسائط'
        verbose_name_plural = 'إحصائيات الوسائط'
    
    def __str__(self):
        return f'إحصائيات وسائط {self.property.display_title}'


class PropertyViewStats(models.Model):
    """إحصائيات المشاهدات التفصيلية للعقارات"""
    
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='view_stats',
        verbose_name='العقار'
    )
    
    # View tracking
    total_views = models.PositiveIntegerField(default=0, verbose_name='إجمالي المشاهدات')
    unique_views = models.PositiveIntegerField(default=0, verbose_name='المشاهدات الفريدة')
    
    # Daily views
    views_today = models.PositiveIntegerField(default=0, verbose_name='مشاهدات اليوم')
    views_yesterday = models.PositiveIntegerField(default=0, verbose_name='مشاهدات الأمس')
    views_this_week = models.PositiveIntegerField(default=0, verbose_name='مشاهدات هذا الأسبوع')
    views_this_month = models.PositiveIntegerField(default=0, verbose_name='مشاهدات هذا الشهر')
    
    # Peak viewing times
    peak_hour = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='ساعة الذروة')
    peak_day = models.CharField(max_length=20, blank=True, verbose_name='يوم الذروة')
    
    # View sources
    views_from_search = models.PositiveIntegerField(default=0, verbose_name='مشاهدات من البحث')
    views_from_direct = models.PositiveIntegerField(default=0, verbose_name='مشاهدات مباشرة')
    views_from_social = models.PositiveIntegerField(default=0, verbose_name='مشاهدات من التواصل الاجتماعي')
    views_from_referral = models.PositiveIntegerField(default=0, verbose_name='مشاهدات من إحالات')
    
    # Device breakdown
    views_desktop = models.PositiveIntegerField(default=0, verbose_name='مشاهدات من سطح المكتب')
    views_mobile = models.PositiveIntegerField(default=0, verbose_name='مشاهدات من الجوال')
    views_tablet = models.PositiveIntegerField(default=0, verbose_name='مشاهدات من الأجهزة اللوحية')
    
    # Location data
    top_viewing_locations = models.JSONField(default=dict, blank=True, verbose_name='أهم مواقع المشاهدة')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'إحصائيات المشاهدات'
        verbose_name_plural = 'إحصائيات المشاهدات'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f'إحصائيات مشاهدات {self.property.display_title}'


class PropertyEngagementStats(models.Model):
    """إحصائيات التفاعل مع العقارات"""
    
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='engagement_stats',
        verbose_name='العقار'
    )
    
    # Favorites
    total_favorites = models.PositiveIntegerField(default=0, verbose_name='إجمالي المفضلة')
    active_favorites = models.PositiveIntegerField(default=0, verbose_name='المفضلة النشطة')
    
    # Shares
    total_shares = models.PositiveIntegerField(default=0, verbose_name='إجمالي المشاركات')
    shares_whatsapp = models.PositiveIntegerField(default=0, verbose_name='مشاركات واتساب')
    shares_facebook = models.PositiveIntegerField(default=0, verbose_name='مشاركات فيسبوك')
    shares_twitter = models.PositiveIntegerField(default=0, verbose_name='مشاركات تويتر')
    shares_telegram = models.PositiveIntegerField(default=0, verbose_name='مشاركات تيليجرام')
    
    # Contact actions
    total_calls = models.PositiveIntegerField(default=0, verbose_name='إجمالي المكالمات')
    total_messages = models.PositiveIntegerField(default=0, verbose_name='إجمالي الرسائل')
    total_inquiries = models.PositiveIntegerField(default=0, verbose_name='إجمالي الاستفسارات')
    
    # Comparisons
    added_to_comparison = models.PositiveIntegerField(default=0, verbose_name='أضيف للمقارنة')
    
    # Time on page
    avg_time_on_page = models.PositiveIntegerField(default=0, verbose_name='متوسط الوقت على الصفحة (ثواني)')
    
    # Bounce rate
    bounce_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='معدل الارتداد (%)')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'إحصائيات التفاعل'
        verbose_name_plural = 'إحصائيات التفاعل'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f'إحصائيات تفاعل {self.property.display_title}'


class PropertyConversionStats(models.Model):
    """إحصائيات التحويل للعقارات"""
    
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='conversion_stats',
        verbose_name='العقار'
    )
    
    # Lead generation
    total_leads = models.PositiveIntegerField(default=0, verbose_name='إجمالي العملاء المحتملين')
    qualified_leads = models.PositiveIntegerField(default=0, verbose_name='العملاء المؤهلين')
    converted_leads = models.PositiveIntegerField(default=0, verbose_name='العملاء المحولين')
    
    # Appointments
    total_appointments = models.PositiveIntegerField(default=0, verbose_name='إجمالي المواعيد')
    completed_appointments = models.PositiveIntegerField(default=0, verbose_name='المواعيد المكتملة')
    cancelled_appointments = models.PositiveIntegerField(default=0, verbose_name='المواعيد الملغاة')
    
    # Offers
    total_offers = models.PositiveIntegerField(default=0, verbose_name='إجمالي العروض')
    accepted_offers = models.PositiveIntegerField(default=0, verbose_name='العروض المقبولة')
    rejected_offers = models.PositiveIntegerField(default=0, verbose_name='العروض المرفوضة')
    
    # Sales
    total_sales = models.PositiveIntegerField(default=0, verbose_name='إجمالي المبيعات')
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='إجمالي الإيرادات')
    
    # Conversion rates
    view_to_inquiry_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='معدل التحويل من مشاهدة لاستفسار (%)')
    inquiry_to_appointment_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='معدل التحويل من استفسار لموعد (%)')
    appointment_to_sale_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='معدل التحويل من موعد لبيع (%)')
    
    # Time metrics
    avg_time_to_first_contact = models.PositiveIntegerField(default=0, verbose_name='متوسط الوقت للتواصل الأول (ساعات)')
    avg_time_to_appointment = models.PositiveIntegerField(default=0, verbose_name='متوسط الوقت للموعد (أيام)')
    avg_time_to_sale = models.PositiveIntegerField(default=0, verbose_name='متوسط الوقت للبيع (أيام)')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'إحصائيات التحويل'
        verbose_name_plural = 'إحصائيات التحويل'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f'إحصائيات تحويل {self.property.display_title}'


class LiveStream(models.Model):
    """Live streaming for properties"""
    
    STATUS_CHOICES = [
        ('scheduled', 'مجدول'),
        ('live', 'مباشر'),
        ('ended', 'منتهي'),
        ('cancelled', 'ملغي'),
    ]
    
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='live_streams',
        verbose_name='العقار'
    )
    broker = models.ForeignKey(
        'Broker', on_delete=models.CASCADE, related_name='live_streams',
        verbose_name='الدلال'
    )
    
    title = models.CharField(max_length=200, verbose_name='عنوان البث')
    description = models.TextField(blank=True, verbose_name='وصف البث')
    
    # Stream details
    stream_url = models.URLField(verbose_name='رابط البث')
    stream_key = models.CharField(max_length=200, blank=True, verbose_name='مفتاح البث')
    platform = models.CharField(
        max_length=20,
        choices=[
            ('youtube', 'يوتيوب'),
            ('facebook', 'فيسبوك'),
            ('instagram', 'إنستغرام'),
            ('tiktok', 'تيك توك'),
            ('twitch', 'توتش'),
            ('custom', 'مخصص'),
        ],
        default='youtube',
        verbose_name='منصة البث'
    )
    
    # Scheduling
    scheduled_start = models.DateTimeField(verbose_name='موعد البدء المجدول')
    scheduled_end = models.DateTimeField(null=True, blank=True, verbose_name='موعد الانتهاء المجدول')
    actual_start = models.DateTimeField(null=True, blank=True, verbose_name='وقت البدء الفعلي')
    actual_end = models.DateTimeField(null=True, blank=True, verbose_name='وقت الانتهاء الفعلي')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled', verbose_name='الحالة')
    is_active = models.BooleanField(default=False, verbose_name='نشط')
    
    # Statistics
    viewers_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاهدين')
    peak_viewers = models.PositiveIntegerField(default=0, verbose_name='أقصى عدد مشاهدين')
    comments_count = models.PositiveIntegerField(default=0, verbose_name='عدد التعليقات')
    shares_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاركات')
    
    # Recording
    is_recorded = models.BooleanField(default=False, verbose_name='تم التسجيل')
    recording_url = models.URLField(blank=True, verbose_name='رابط التسجيل')
    thumbnail = models.ImageField(upload_to='live_streams/', null=True, blank=True, verbose_name='صورة مصغرة')
    
    # Notifications
    notify_subscribers = models.BooleanField(default=True, verbose_name='إشعار المشتركين')
    notification_sent = models.BooleanField(default=False, verbose_name='تم إرسال الإشعار')
    notification_time = models.DateTimeField(null=True, blank=True, verbose_name='وقت الإشعار')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'بث مباشر'
        verbose_name_plural = 'البثوث المباشرة'
        ordering = ['-scheduled_start']
    
    def __str__(self):
        return f'{self.title} - {self.property.display_title}'
    
    def start_stream(self):
        """Start the live stream"""
        from django.utils import timezone
        self.status = 'live'
        self.is_active = True
        self.actual_start = timezone.now()
        self.save()
    
    def end_stream(self):
        """End the live stream"""
        from django.utils import timezone
        self.status = 'ended'
        self.is_active = False
        self.actual_end = timezone.now()
        self.save()
    
    def cancel_stream(self):
        """Cancel the live stream"""
        self.status = 'cancelled'
        self.is_active = False
        self.save()
    
    def get_duration(self):
        """Get stream duration in minutes"""
        if self.actual_start and self.actual_end:
            duration = self.actual_end - self.actual_start
            return int(duration.total_seconds() / 60)
        return 0


class LiveStreamComment(models.Model):
    """Comments on live streams"""
    
    live_stream = models.ForeignKey(
        LiveStream, on_delete=models.CASCADE, related_name='comments',
        verbose_name='البث المباشر'
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='المستخدم'
    )
    author_name = models.CharField(max_length=100, verbose_name='اسم الكاتب')
    author_phone = models.CharField(max_length=20, blank=True, verbose_name='رقم الهاتف')
    comment = models.TextField(verbose_name='التعليق')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')
    
    class Meta:
        verbose_name = 'تعليق بث مباشر'
        verbose_name_plural = 'تعليقات البث المباشر'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.author_name}: {self.comment[:50]}'


class WhatsAppMessage(models.Model):
    """نموذج رسائل الواتساب"""
    
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='whatsapp_messages',
        verbose_name='العقار'
    )
    sender_name = models.CharField(max_length=100, verbose_name='اسم المرسل')
    sender_phone = models.CharField(max_length=20, verbose_name='رقم هاتف المرسل')
    message = models.TextField(verbose_name='الرسالة')
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name='وقت الإرسال')
    is_read = models.BooleanField(default=False, verbose_name='تمت القراءة')
    
    class Meta:
        verbose_name = 'رسالة واتساب'
        verbose_name_plural = 'رسائل الواتساب'
        ordering = ['-sent_at']
    
    def __str__(self):
        return f'واتساب من {self.sender_name} - {self.property.display_title}'


class TelegramMessage(models.Model):
    """نموذج رسائل تيليجرام"""
    
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='telegram_messages',
        verbose_name='العقار'
    )
    sender_name = models.CharField(max_length=100, verbose_name='اسم المرسل')
    sender_username = models.CharField(max_length=100, blank=True, verbose_name='اسم المستخدم')
    message = models.TextField(verbose_name='الرسالة')
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name='وقت الإرسال')
    is_read = models.BooleanField(default=False, verbose_name='تمت القراءة')
    
    class Meta:
        verbose_name = 'رسالة تيليجرام'
        verbose_name_plural = 'رسائل تيليجرام'
        ordering = ['-sent_at']
    
    def __str__(self):
        return f'تيليجرام من {self.sender_name} - {self.property.display_title}'


class AppointmentBooking(models.Model):
    """نموذج حجز المواعيد"""
    
    STATUS_CHOICES = [
        ('pending', 'قيد الانتظار'),
        ('confirmed', 'مؤكد'),
        ('completed', 'مكتمل'),
        ('cancelled', 'ملغي'),
    ]
    
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='appointments',
        verbose_name='العقار'
    )
    client_name = models.CharField(max_length=100, verbose_name='اسم العميل')
    client_phone = models.CharField(max_length=20, verbose_name='رقم هاتف العميل')
    client_email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    appointment_date = models.DateTimeField(verbose_name='تاريخ الموعد')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الحجز')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')
    
    class Meta:
        verbose_name = 'حجز موعد'
        verbose_name_plural = 'حجوز المواعيد'
        ordering = ['-appointment_date']
    
    def __str__(self):
        return f'موعد {self.client_name} - {self.appointment_date.strftime("%Y-%m-%d %H:%M")}'


class PropertyInquiry(models.Model):
    """نموذج الاستفسارات المتقدمة"""
    
    INQUIRY_TYPES = [
        ('general', 'استفسار عام'),
        ('price', 'استفسار عن السعر'),
        ('viewing', 'طلب مشاهدة'),
        ('financing', 'استفسار عن التمويل'),
        ('documents', 'طلب مستندات'),
        ('other', 'أخرى'),
    ]
    
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='inquiries',
        verbose_name='العقار'
    )
    inquiry_type = models.CharField(max_length=20, choices=INQUIRY_TYPES, verbose_name='نوع الاستفسار')
    name = models.CharField(max_length=100, verbose_name='الاسم')
    email = models.EmailField(verbose_name='البريد الإلكتروني')
    phone = models.CharField(max_length=20, verbose_name='رقم الهاتف')
    subject = models.CharField(max_length=200, verbose_name='الموضوع')
    message = models.TextField(verbose_name='الرسالة')
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=[('email', 'البريد الإلكتروني'), ('phone', 'الهاتف'), ('whatsapp', 'واتساب')],
        default='email',
        verbose_name='طريقة التواصل المفضلة'
    )
    is_resolved = models.BooleanField(default=False, verbose_name='تم الحل')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإرسال')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')
    
    class Meta:
        verbose_name = 'استفسار'
        verbose_name_plural = 'الاستفسارات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.get_inquiry_type_display()} من {self.name} - {self.property.display_title}'


class Message(models.Model):
    """نموذج الرسائل المحسّن"""
    
    # أنواع الرسائل
    TYPE_TEXT = 'text'
    TYPE_IMAGE = 'image'
    TYPE_VIDEO = 'video'
    TYPE_AUDIO = 'audio'
    TYPE_FILE = 'file'
    TYPE_LOCATION = 'location'
    TYPE_LINK = 'link'
    TYPE_PROPERTY_CARD = 'property_card'
    TYPE_BROKER_MESSAGE = 'broker_message'
    TYPE_SYSTEM = 'system'
    
    TYPE_CHOICES = [
        (TYPE_TEXT, 'نص'),
        (TYPE_IMAGE, 'صورة'),
        (TYPE_VIDEO, 'فيديو'),
        (TYPE_AUDIO, 'صوت'),
        (TYPE_FILE, 'ملف'),
        (TYPE_LOCATION, 'موقع'),
        (TYPE_LINK, 'رابط'),
        (TYPE_PROPERTY_CARD, 'بطاقة عقار'),
        (TYPE_BROKER_MESSAGE, 'رسالة دلال'),
        (TYPE_SYSTEM, 'نظام'),
    ]
    
    # حالة الرسالة
    STATUS_SENT = 'sent'
    STATUS_DELIVERED = 'delivered'
    STATUS_READ = 'read'
    STATUS_FAILED = 'failed'
    
    STATUS_CHOICES = [
        (STATUS_SENT, 'مرسلة'),
        (STATUS_DELIVERED, 'مستلمة'),
        (STATUS_READ, 'مقروءة'),
        (STATUS_FAILED, 'فشلت'),
    ]
    
    conversation = models.ForeignKey(
        'Conversation', on_delete=models.CASCADE, related_name='messages',
        null=True, blank=True, verbose_name='المحادثة'
    )
    
    sender = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sent_messages', verbose_name='المرسل'
    )
    
    recipient = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='received_messages', verbose_name='المستلم'
    )
    
    message_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default=TYPE_TEXT,
        verbose_name='نوع الرسالة'
    )
    
    content = models.TextField(blank=True, verbose_name='المحتوى')
    
    # للموقع الجغرافي
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='خط العرض'
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='خط الطول'
    )
    location_name = models.CharField(max_length=255, blank=True, verbose_name='اسم الموقع')
    
    # للروابط
    link_url = models.URLField(blank=True, verbose_name='رابط')
    link_title = models.CharField(max_length=255, blank=True, verbose_name='عنوان الرابط')
    link_description = models.TextField(blank=True, verbose_name='وصف الرابط')
    link_image = models.URLField(blank=True, verbose_name='صورة الرابط')
    
    # حالة الرسالة
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_SENT,
        verbose_name='الحالة'
    )
    
    # الرد على رسالة
    reply_to = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='replies', verbose_name='رد على'
    )
    
    # حذف الرسالة
    is_deleted_by_sender = models.BooleanField(default=False, verbose_name='محذوف من المرسل')
    is_deleted_by_recipient = models.BooleanField(default=False, verbose_name='محذوف من المستلم')
    
    # وقت الحذف (للسماح بالحذف خلال فترة معينة)
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الحذف')
    
    # قراءة الرسالة
    is_read = models.BooleanField(default=False, verbose_name='مقروء')
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='وقت القراءة')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'رسالة'
        verbose_name_plural = 'الرسائل'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'رسالة {self.id} من {self.sender.username if self.sender else "مجهول"}'
    
    def mark_as_delivered(self):
        """تحديد الرسالة كمستلمة"""
        self.status = self.STATUS_DELIVERED
        self.save(update_fields=['status'])
    
    def mark_as_read(self):
        """تحديد الرسالة كمقروءة"""
        self.status = self.STATUS_READ
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['status', 'is_read', 'read_at'])
    
    def delete_for_user(self, user):
        """حذف الرسالة من جانب مستخدم معين"""
        if self.sender == user:
            self.is_deleted_by_sender = True
        elif self.recipient == user:
            self.is_deleted_by_recipient = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted_by_sender', 'is_deleted_by_recipient', 'deleted_at'])
    
    def can_delete(self, user):
        """التحقق مما إذا كان يمكن للمستخدم حذف الرسالة"""
        time_since_creation = timezone.now() - self.created_at
        # يمكن الحذف خلال 24 ساعة
        return time_since_creation.total_seconds() < 86400


class MessageAttachment(models.Model):
    """مرفقات الرسائل"""
    
    ATTACHMENT_IMAGE = 'image'
    ATTACHMENT_VIDEO = 'video'
    ATTACHMENT_AUDIO = 'audio'
    ATTACHMENT_FILE = 'file'
    ATTACHMENT_DOCUMENT = 'document'
    
    ATTACHMENT_TYPE_CHOICES = [
        (ATTACHMENT_IMAGE, 'صورة'),
        (ATTACHMENT_VIDEO, 'فيديو'),
        (ATTACHMENT_AUDIO, 'صوت'),
        (ATTACHMENT_FILE, 'ملف'),
        (ATTACHMENT_DOCUMENT, 'مستند'),
    ]
    
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name='attachments',
        verbose_name='الرسالة'
    )
    
    attachment_type = models.CharField(
        max_length=20, choices=ATTACHMENT_TYPE_CHOICES,
        verbose_name='نوع المرفق'
    )
    
    file = models.FileField(
        upload_to='message_attachments/%Y/%m/%d/',
        verbose_name='الملف'
    )
    
    file_name = models.CharField(max_length=255, verbose_name='اسم الملف')
    file_size = models.BigIntegerField(verbose_name='حجم الملف (بايت)')
    file_type = models.CharField(max_length=100, blank=True, verbose_name='نوع الملف')
    
    # للصور والفيديو
    thumbnail = models.ImageField(
        upload_to='message_attachments/thumbnails/%Y/%m/%d/',
        null=True, blank=True, verbose_name='الصورة المصغرة'
    )
    
    # للمستندات
    page_count = models.IntegerField(null=True, blank=True, verbose_name='عدد الصفحات')
    
    created_at = models.DateTimeField(default=timezone.now, verbose_name='تاريخ الرفع')
    
    class Meta:
        verbose_name = 'مرفق رسالة'
        verbose_name_plural = 'مرفقات الرسائل'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.file_name}'
    
    def get_file_size_display(self):
        """عرض حجم الملف بشكل مقروء"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} TB'


class MessageReaction(models.Model):
    """ردود فعل على الرسائل"""
    
    REACTION_LIKE = 'like'
    REACTION_LOVE = 'love'
    REACTION_HAHA = 'haha'
    REACTION_WOW = 'wow'
    REACTION_SAD = 'sad'
    REACTION_ANGRY = 'angry'
    REACTION_THUMBS_UP = 'thumbs_up'
    REACTION_THUMBS_DOWN = 'thumbs_down'
    
    REACTION_CHOICES = [
        (REACTION_LIKE, 'إعجاب'),
        (REACTION_LOVE, 'حب'),
        (REACTION_HAHA, 'ضحك'),
        (REACTION_WOW, 'دهشة'),
        (REACTION_SAD, 'حزن'),
        (REACTION_ANGRY, 'غضب'),
        (REACTION_THUMBS_UP, 'إبهام للأعلى'),
        (REACTION_THUMBS_DOWN, 'إبهام للأسفل'),
    ]
    
    REACTION_EMOJIS = {
        REACTION_LIKE: '👍',
        REACTION_LOVE: '❤️',
        REACTION_HAHA: '😂',
        REACTION_WOW: '😮',
        REACTION_SAD: '😢',
        REACTION_ANGRY: '😡',
        REACTION_THUMBS_UP: '👍',
        REACTION_THUMBS_DOWN: '👎',
    }
    
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name='reactions',
        verbose_name='الرسالة'
    )
    
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='message_reactions',
        verbose_name='المستخدم'
    )
    
    reaction_type = models.CharField(
        max_length=20, choices=REACTION_CHOICES,
        verbose_name='نوع الرد'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الرد')
    
    class Meta:
        verbose_name = 'رد فعل'
        verbose_name_plural = 'ردود الفعل'
        unique_together = ['message', 'user']
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.reaction_type}'
    
    def get_emoji(self):
        """الحصول على الرموز التعبيرية للرد"""
        return self.REACTION_EMOJIS.get(self.reaction_type, '')


class MessageReport(models.Model):
    """بلاغ عن رسالة"""
    
    REPORT_TYPE_SPAM = 'spam'
    REPORT_TYPE_INAPPROPRIATE = 'inappropriate'
    REPORT_TYPE_HARASSMENT = 'harassment'
    REPORT_TYPE_SCAM = 'scam'
    REPORT_TYPE_OTHER = 'other'
    
    REPORT_TYPE_CHOICES = [
        (REPORT_TYPE_SPAM, 'رسائل مزعجة'),
        (REPORT_TYPE_INAPPROPRIATE, 'محتوى غير لائق'),
        (REPORT_TYPE_HARASSMENT, 'مضايقة'),
        (REPORT_TYPE_SCAM, 'احتيال'),
        (REPORT_TYPE_OTHER, 'أخرى'),
    ]
    
    STATUS_PENDING = 'pending'
    STATUS_REVIEWED = 'reviewed'
    STATUS_RESOLVED = 'resolved'
    STATUS_DISMISSED = 'dismissed'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'قيد المراجعة'),
        (STATUS_REVIEWED, 'تمت المراجعة'),
        (STATUS_RESOLVED, 'تم الحل'),
        (STATUS_DISMISSED, 'تم الرفض'),
    ]
    
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name='reports',
        null=True, blank=True, verbose_name='الرسالة'
    )
    
    reporter = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='message_reports',
        null=True, blank=True, verbose_name='المبلغ'
    )
    
    report_type = models.CharField(
        max_length=20, choices=REPORT_TYPE_CHOICES,
        verbose_name='نوع البلاغ'
    )
    
    description = models.TextField(verbose_name='وصف البلاغ')
    
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING,
        verbose_name='الحالة'
    )
    
    reviewed_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_reports', verbose_name='راجع بواسطة'
    )
    
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ المراجعة')
    
    resolution_notes = models.TextField(blank=True, verbose_name='ملاحظات الحل')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ البلاغ')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'بلاغ رسالة'
        verbose_name_plural = 'بلاغات الرسائل'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'بلاغ {self.id} - {self.report_type}'


class PropertyNote(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'منخفض'),
        ('medium', 'متوسط'),
        ('high', 'عالي'),
        ('urgent', 'عاجل'),
    ]
    
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='notes', null=True, blank=True
    )
    title = models.CharField(max_length=200, verbose_name='العنوان')
    content = models.TextField(verbose_name='المحتوى')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', verbose_name='الأولوية')
    is_completed = models.BooleanField(default=False, verbose_name='مكتمل')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')

    class Meta:
        verbose_name = 'ملاحظة عقار'
        verbose_name_plural = 'ملاحظات العقارات'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} - {self.property.display_title}'


class VirtualTour360(models.Model):
    TOUR_TYPE_CHOICES = [
        ('image', 'صورة بانورامية 360°'),
        ('file', 'ملف جولة 360° جاهز'),
        ('external', 'رابط خارجي'),
        ('multi', 'جولة من عدة صور مترابطة'),
    ]
    
    EXTERNAL_SERVICE_CHOICES = [
        ('matterport', 'Matterport'),
        ('kuula', 'Kuula'),
        ('google', 'Google Street View'),
        ('other', 'خدمة أخرى'),
    ]
    
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='virtual_tours'
    )
    title = models.CharField(max_length=200, verbose_name='العنوان')
    tour_type = models.CharField(
        max_length=20, choices=TOUR_TYPE_CHOICES, default='image',
        verbose_name='نوع الجولة'
    )
    image = models.ImageField(
        upload_to='virtual_tours/', blank=True, null=True,
        verbose_name='صورة 360°'
    )
    tour_file = models.FileField(
        upload_to='virtual_tours/files/', blank=True, null=True,
        verbose_name='ملف الجولة'
    )
    external_url = models.URLField(
        blank=True, verbose_name='رابط خارجي'
    )
    external_service = models.CharField(
        max_length=20, choices=EXTERNAL_SERVICE_CHOICES, blank=True,
        verbose_name='خدمة خارجية'
    )
    description = models.TextField(blank=True, verbose_name='الوصف')
    order = models.IntegerField(default=0, verbose_name='الترتيب')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    # 360° Tour Features
    auto_rotate = models.BooleanField(default=False, verbose_name='تدوير تلقائي')
    auto_rotate_speed = models.IntegerField(default=1, verbose_name='سرعة التدوير')
    enable_zoom = models.BooleanField(default=True, verbose_name='تفعيل التكبير')
    min_zoom = models.FloatField(default=0.5, verbose_name='أدنى تكبير')
    max_zoom = models.FloatField(default=3.0, verbose_name='أقصى تكبير')
    enable_fullscreen = models.BooleanField(default=True, verbose_name='تفعيل ملء الشاشة')
    enable_vr = models.BooleanField(default=False, verbose_name='تفعيل دعم VR')
    initial_view_pitch = models.FloatField(default=0, verbose_name='زاوية الميل الأولية')
    initial_view_yaw = models.FloatField(default=0, verbose_name='زاوية الدوران الأولية')
    start_in_autoplay = models.BooleanField(default=False, verbose_name='بدء التشغيل التلقائي')
    autoplay_duration = models.IntegerField(default=10, verbose_name='مدة التشغيل التلقائي (ثواني)')

    class Meta:
        verbose_name = 'جولة افتراضية'
        verbose_name_plural = 'الجولات الافتراضية'
        ordering = ['order']

    def __str__(self):
        return f'{self.title} - {self.property.display_title}'


class VirtualTourPoint(models.Model):
    """Points within a virtual tour (e.g., Entrance, Living Room, etc.)"""
    virtual_tour = models.ForeignKey(
        VirtualTour360, on_delete=models.CASCADE, related_name='tour_points'
    )
    name = models.CharField(max_length=100, verbose_name='اسم النقطة')
    description = models.TextField(blank=True, verbose_name='الوصف')
    image = models.ImageField(
        upload_to='virtual_tours/points/', verbose_name='صورة 360° للنقطة'
    )
    order = models.IntegerField(default=0, verbose_name='الترتيب')
    
    class Meta:
        verbose_name = 'نقطة جولة'
        verbose_name_plural = 'نقاط الجولة'
        ordering = ['order']
    
    def __str__(self):
        return f'{self.name} - {self.virtual_tour.title}'


class VirtualTourConnection(models.Model):
    """Connections between tour points for navigation"""
    from_point = models.ForeignKey(
        VirtualTourPoint, on_delete=models.CASCADE, related_name='outgoing_connections'
    )
    to_point = models.ForeignKey(
        VirtualTourPoint, on_delete=models.CASCADE, related_name='incoming_connections'
    )
    label = models.CharField(max_length=50, blank=True, verbose_name='التسمية')
    
    class Meta:
        verbose_name = 'اتصال جولة'
        verbose_name_plural = 'اتصالات الجولة'
        unique_together = ('from_point', 'to_point')
    
    def __str__(self):
        return f'{self.from_point.name} → {self.to_point.name}'


class Auction(models.Model):
    STATUS_CHOICES = [
        ('upcoming', 'قادم'),
        ('active', 'نشط'),
        ('ended', 'منتهي'),
        ('cancelled', 'ملغي'),
    ]
    
    APPROVAL_STATUS_CHOICES = [
        ('pending', 'قيد المراجعة'),
        ('approved', 'موافق عليه'),
        ('rejected', 'مرفوض'),
        ('needs_revision', 'يحتاج تعديل'),
    ]
    
    AUCTION_TYPES = [
        ('home', 'مزاد بيع منزل'),
        ('land', 'مزاد بيع أرض'),
        ('shop', 'مزاد بيع محل تجاري'),
        ('building', 'مزاد بيع عمارة'),
        ('investment', 'مزاد استثماري'),
    ]
    
    ACCESS_TYPE_CHOICES = [
        ('public', 'عام'),
        ('private', 'خاص برقم'),
        ('invitation_only', 'بدعوة فقط'),
    ]
    
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='auctions'
    )
    broker = models.ForeignKey('Broker', on_delete=models.CASCADE, related_name='auctions', null=True, blank=True, verbose_name='الدلال')
    auction_type = models.CharField(max_length=20, choices=AUCTION_TYPES, default='home', verbose_name='نوع المزاد')
    title = models.CharField(max_length=200, verbose_name='عنوان المزاد')
    description = models.TextField(verbose_name='وصف المزاد')
    starting_price = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='سعر البداية')
    minimum_increment = models.DecimalField(max_digits=15, decimal_places=0, default=100000, verbose_name='أقل زيادة')
    reserve_price = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name='السعر الاحتياطي')
    start_date = models.DateTimeField(verbose_name='تاريخ البداية')
    end_date = models.DateTimeField(verbose_name='تاريخ النهاية')
    auto_extend_minutes = models.PositiveSmallIntegerField(default=5, verbose_name='تمديد تلقائي (دقائق)')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming', verbose_name='الحالة')
    deposit_amount = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='مبلغ التأمين للدخول')
    access_type = models.CharField(max_length=20, choices=ACCESS_TYPE_CHOICES, default='public', verbose_name='نوع الوصول')
    access_code = models.CharField(max_length=20, blank=True, verbose_name='كود الدخول')
    is_closed = models.BooleanField(default=False, verbose_name='مزاد مغلق')
    is_featured = models.BooleanField(default=False, verbose_name='مزاد مميز')
    is_advertised = models.BooleanField(default=False, verbose_name='معلن عنه')
    advertisement_budget = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='ميزانية الإعلان')
    terms = models.TextField(verbose_name='شروط المزاد')
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name='رقم التواصل')
    contact_email = models.EmailField(blank=True, verbose_name='بريد التواصل')
    max_participants = models.IntegerField(null=True, blank=True, verbose_name='الحد الأقصى للمشاركين')
    winner_announced = models.BooleanField(default=False, verbose_name='تم الإعلان عن الفائز')
    winner = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='won_auctions', verbose_name='الفائز')
    winning_bid = models.ForeignKey('Bid', on_delete=models.SET_NULL, null=True, blank=True, related_name='winning_auction', verbose_name='المزايدة الفائزة')
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='pending', verbose_name='حالة الموافقة')
    rejection_reason = models.TextField(blank=True, verbose_name='سبب الرفض')
    approved_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_auctions', verbose_name='تمت الموافقة بواسطة')
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الموافقة')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')

    class Meta:
        verbose_name = 'مزاد'
        verbose_name_plural = 'المزادات'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} - {self.property.display_title}'

    def get_current_highest_bid(self):
        from django.db.models import Max
        try:
            result = self.bids.aggregate(max_bid=Max('amount'))['max_bid']
            return result if result is not None else self.starting_price
        except:
            return self.starting_price

    def get_total_bids(self):
        try:
            return self.bids.count()
        except:
            return 0

    def is_active(self):
        from django.utils import timezone
        now = timezone.now()
        return self.status == 'active' and self.start_date <= now <= self.end_date

    def get_time_remaining(self):
        from django.utils import timezone
        now = timezone.now()
        if now < self.start_date:
            return self.start_date - now
        elif now <= self.end_date:
            return self.end_date - now
        else:
            return None

    def get_participant_count(self):
        try:
            return self.participants.count()
        except:
            return 0

    def should_extend(self):
        """Check if auction should be auto-extended"""
        from django.utils import timezone
        now = timezone.now()
        if self.is_active():
            time_remaining = self.end_date - now
            # Extend if bid placed in last minute
            return time_remaining.total_seconds() <= 60
        return False

    def extend_auction(self):
        """Extend auction by auto_extend_minutes"""
        from django.utils import timezone, timedelta
        if self.should_extend():
            self.end_date = self.end_date + timedelta(minutes=self.auto_extend_minutes)
            self.save()
            return True
        return False

    def generate_access_code(self):
        """Generate a random access code for the auction"""
        import random
        import string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self.access_code = code
        self.save()
        return code


class AuctionInvitation(models.Model):
    """دعوات المزاد للمزادات الخاصة"""
    
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='invitations', verbose_name='المزاد')
    invited_user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='auction_invitations', null=True, blank=True, verbose_name='المستخدم المدعو')
    invited_broker = models.ForeignKey('Broker', on_delete=models.CASCADE, related_name='auction_invitations', null=True, blank=True, verbose_name='الدلال المدعو')
    
    # معلومات الدعوة
    invitation_code = models.CharField(max_length=20, unique=True, verbose_name='كود الدعوة')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    phone = models.CharField(max_length=20, blank=True, verbose_name='رقم الهاتف')
    
    # الحالة
    STATUS_CHOICES = [
        ('pending', 'قيد الانتظار'),
        ('accepted', 'مقبول'),
        ('declined', 'مرفوض'),
        ('used', 'تم الاستخدام'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة')
    
    # التواريخ
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإرسال')
    accepted_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ القبول')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    
    class Meta:
        verbose_name = 'دعوة مزاد'
        verbose_name_plural = 'دعوات المزادات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invitation_code']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        recipient = self.invited_user.username if self.invited_user else (self.invited_broker.display_name if self.invited_broker else self.email)
        return f'{self.auction.title} - {recipient}'
    
    def generate_code(self):
        """Generate a unique invitation code"""
        import random
        import string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        self.invitation_code = code
        self.save()
        return code


class AuctionParticipant(models.Model):
    """Track auction participants with verification"""
    
    PAYMENT_STATUS = [
        ('pending', 'قيد الانتظار'),
        ('paid', 'مدفوع'),
        ('refunded', 'مسترد'),
        ('failed', 'فشل'),
    ]
    
    APPROVAL_STATUS_CHOICES = [
        ('pending', 'قيد المراجعة'),
        ('approved', 'موافق عليه'),
        ('rejected', 'مرفوض'),
    ]
    
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='auction_participations')
    phone = models.CharField(max_length=20, verbose_name='رقم الهاتف')
    email = models.EmailField(verbose_name='البريد الإلكتروني')
    identity_verified = models.BooleanField(default=False, verbose_name='تم توثيق الهوية')
    deposit_paid = models.BooleanField(default=False, verbose_name='تم دفع التأمين')
    deposit_amount = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='مبلغ التأمين المدفوع')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending', verbose_name='حالة الدفع')
    payment_reference = models.CharField(max_length=100, blank=True, verbose_name='رقم مرجع الدفع')
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='pending', verbose_name='حالة الموافقة')
    approved_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_participants', verbose_name='تمت الموافقة بواسطة')
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الموافقة')
    rejection_reason = models.TextField(blank=True, verbose_name='سبب الرفض')
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الانضمام')

    class Meta:
        verbose_name = 'مشارك في المزاد'
        verbose_name_plural = 'المشاركون في المزادات'
        unique_together = ['auction', 'user']

    def __str__(self):
        return f'{self.user.username} - {self.auction.title}'


class Bid(models.Model):
    auction = models.ForeignKey(
        Auction, on_delete=models.CASCADE, related_name='bids'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='bids'
    )
    amount = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='المبلغ')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ المزايدة')
    is_auto_extended = models.BooleanField(default=False, verbose_name='تم التمديد التلقائي')

    class Meta:
        verbose_name = 'مزايدة'
        verbose_name_plural = 'المزايدات'
        ordering = ['-amount', '-created_at']

    def __str__(self):
        return f'{self.user.username} - {self.amount:,} - {self.auction.title}'

    def is_valid(self):
        """Check if bid is valid (higher than current highest + minimum increment)"""
        current_highest = self.auction.get_current_highest_bid()
        min_required = current_highest + self.auction.minimum_increment
        return self.amount >= min_required

    def save(self, *args, **kwargs):
        """Override save to check validity and trigger auto-extension"""
        if not self.is_valid():
            raise ValueError(f'المبلغ يجب أن يكون على الأقل {self.auction.minimum_increment:,} أعلى من أعلى عرض حالي')
        
        # Check if auction should be extended
        if self.auction.should_extend():
            self.auction.extend_auction()
            self.is_auto_extended = True
        
        super().save(*args, **kwargs)


class AutoBid(models.Model):
    """Automatic bidding system for auctions"""
    
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='auto_bids', verbose_name='المزاد')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='auto_bids', verbose_name='المستخدم')
    max_amount = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='الحد الأقصى للمزايدة')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    current_bid = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='المزايدة الحالية')
    total_bids_placed = models.IntegerField(default=0, verbose_name='إجمالي المزايدات الموضوعة')
    last_bid_at = models.DateTimeField(null=True, blank=True, verbose_name='آخر مزايدة')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'مزايدة آلية'
        verbose_name_plural = 'المزايدات الآلية'
        unique_together = ['auction', 'user']
    
    def __str__(self):
        return f'{self.user.username} - {self.max_amount:,} - {self.auction.title}'
    
    def should_place_bid(self, current_highest):
        """Check if auto-bid should place a bid"""
        if not self.is_active:
            return False
        if self.current_bid >= self.max_amount:
            return False
        if current_highest + self.auction.minimum_increment > self.max_amount:
            return False
        return True
    
    def place_bid(self):
        """Place an automatic bid"""
        from django.utils import timezone
        current_highest = self.auction.get_current_highest_bid()
        if not self.should_place_bid(current_highest):
            return False
        
        new_amount = current_highest + self.auction.minimum_increment
        if new_amount > self.max_amount:
            new_amount = self.max_amount
        
        bid = Bid.objects.create(
            auction=self.auction,
            user=self.user,
            amount=new_amount
        )
        self.current_bid = new_amount
        self.total_bids_placed += 1
        self.last_bid_at = timezone.now()
        self.save()
        return bid


class AuctionNotification(models.Model):
    """Notifications for auction events"""
    
    NOTIFICATION_TYPES = [
        ('new_bid', 'مزايدة جديدة'),
        ('outbid', 'تم تجاوز مزايدتك'),
        ('auction_starting', 'المزاد سيبدأ قريباً'),
        ('auction_ending', 'المزاد ينتهي قريباً'),
        ('auction_won', 'فزت بالمزاد'),
        ('auction_lost', 'خسرت المزاد'),
        ('price_reached', 'وصل السعر للحد المطلوب'),
    ]
    
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='notifications', verbose_name='المزاد')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='auction_notifications', verbose_name='المستخدم')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, verbose_name='نوع الإشعار')
    title = models.CharField(max_length=200, verbose_name='العنوان')
    message = models.TextField(verbose_name='الرسالة')
    amount = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name='المبلغ')
    is_read = models.BooleanField(default=False, verbose_name='تم القراءة')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    
    class Meta:
        verbose_name = 'إشعار مزاد'
        verbose_name_plural = 'إشعارات المزادات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.title}'


class AuctionRating(models.Model):
    """Rating system for auction participants and sellers"""
    
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='ratings', verbose_name='المزاد')
    rater = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='auction_ratings_given', verbose_name='المقيم')
    rated_user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='auction_ratings_received', verbose_name='المقيم')
    rating = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)], verbose_name='التقييم')
    comment = models.TextField(blank=True, verbose_name='التعليق')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التقييم')
    
    class Meta:
        verbose_name = 'تقييم مزاد'
        verbose_name_plural = 'تقييمات المزادات'
        unique_together = ['auction', 'rater', 'rated_user']
    
    def __str__(self):
        return f'{self.rater.username} - {self.rating} - {self.rated_user.username}'


class AuctionStats(models.Model):
    """Statistics and analytics for auctions"""
    
    auction = models.OneToOneField(Auction, on_delete=models.CASCADE, related_name='stats', verbose_name='المزاد')
    total_views = models.IntegerField(default=0, verbose_name='إجمالي المشاهدات')
    unique_visitors = models.IntegerField(default=0, verbose_name='الزوار الفريدين')
    total_bids = models.IntegerField(default=0, verbose_name='إجمالي المزايدات')
    unique_bidders = models.IntegerField(default=0, verbose_name='المزايدون الفريدون')
    avg_bid_amount = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name='متوسط المزايدة')
    peak_bid_time = models.DateTimeField(null=True, blank=True, verbose_name='وقت ذروة المزايدة')
    total_watchers = models.IntegerField(default=0, verbose_name='إجمالي المتابعين')
    watchers_joined = models.IntegerField(default=0, verbose_name='المتابعون الذين انضموا للمزايدة')
    auto_bid_count = models.IntegerField(default=0, verbose_name='عدد المزايدات الآلية')
    extension_count = models.IntegerField(default=0, verbose_name='عدد التمديدات')
    final_price = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name='السعر النهائي')
    price_increase_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='نسبة زيادة السعر')
    
    # Time-based stats
    bids_by_hour = models.JSONField(default=dict, verbose_name='المزايدات بالساعة')
    views_by_hour = models.JSONField(default=dict, verbose_name='المشاهدات بالساعة')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'إحصائيات مزاد'
        verbose_name_plural = 'إحصائيات المزادات'
    
    def __str__(self):
        return f'إحصائيات {self.auction.title}'
    
    def update_stats(self):
        """Update statistics based on current auction state"""
        from django.db.models import Avg, Count
        from django.utils import timezone
        
        self.total_bids = self.auction.bids.count()
        self.unique_bidders = self.auction.bids.values('user').distinct().count()
        
        if self.total_bids > 0:
            avg_result = self.auction.bids.aggregate(avg_amount=Avg('amount'))
            self.avg_bid_amount = avg_result['avg_amount']
        
        if self.auction.status == 'ended':
            self.final_price = self.auction.get_current_highest_bid()
            if self.final_price and self.auction.starting_price:
                increase = ((self.final_price - self.auction.starting_price) / self.auction.starting_price) * 100
                self.price_increase_percentage = round(increase, 2)
        
        self.auto_bid_count = self.auction.auto_bids.count()
        self.save()


class AuctionLiveStream(models.Model):
    """Live streaming for auctions"""
    
    auction = models.OneToOneField(Auction, on_delete=models.CASCADE, related_name='live_stream', verbose_name='المزاد')
    stream_url = models.URLField(verbose_name='رابط البث')
    stream_key = models.CharField(max_length=100, blank=True, verbose_name='مفتاح البث')
    platform = models.CharField(max_length=50, choices=[
        ('youtube', 'YouTube'),
        ('facebook', 'Facebook'),
        ('twitch', 'Twitch'),
        ('custom', 'مخصص'),
    ], default='youtube', verbose_name='المنصة')
    is_live = models.BooleanField(default=False, verbose_name='بث مباشر')
    viewer_count = models.IntegerField(default=0, verbose_name='عدد المشاهدين')
    chat_enabled = models.BooleanField(default=True, verbose_name='الشات مفعّل')
    recording_enabled = models.BooleanField(default=True, verbose_name='التسجيل مفعّل')
    recording_url = models.URLField(blank=True, verbose_name='رابط التسجيل')
    start_time = models.DateTimeField(null=True, blank=True, verbose_name='وقت البدء')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='وقت الانتهاء')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'بث مباشر للمزاد'
        verbose_name_plural = 'البث المباشر للمزادات'
    
    def __str__(self):
        return f'بث {self.auction.title}'
    
    def is_streaming(self):
        """Check if stream is currently live"""
        from django.utils import timezone
        if not self.is_live:
            return False
        if self.start_time and self.end_time:
            now = timezone.now()
            return self.start_time <= now <= self.end_time
        return self.is_live


class AuctionAdvertisement(models.Model):
    """Advertisements for auctions"""
    
    PLATFORM_CHOICES = [
        ('facebook', 'فيسبوك'),
        ('instagram', 'إنستغرام'),
        ('twitter', 'تويتر'),
        ('google', 'جوجل'),
        ('tiktok', 'تيك توك'),
        ('snapchat', 'سناب شات'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'قيد الانتظار'),
        ('active', 'نشط'),
        ('paused', 'موقوف'),
        ('completed', 'مكتمل'),
        ('cancelled', 'ملغي'),
    ]
    
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='advertisements', verbose_name='المزاد')
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, verbose_name='المنصة')
    title = models.CharField(max_length=100, verbose_name='عنوان الإعلان')
    description = models.TextField(verbose_name='وصف الإعلان')
    image_url = models.URLField(blank=True, verbose_name='رابط الصورة')
    budget = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='الميزانية')
    spent = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='المبلغ المصروف')
    impressions = models.IntegerField(default=0, verbose_name='عدد الظهور')
    clicks = models.IntegerField(default=0, verbose_name='عدد النقرات')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة')
    start_date = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ البدء')
    end_date = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الانتهاء')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'إعلان مزاد'
        verbose_name_plural = 'إعلانات المزادات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.title} - {self.auction.title}'
    
    def get_ctr(self):
        """Calculate Click-Through Rate"""
        if self.impressions > 0:
            return round((self.clicks / self.impressions) * 100, 2)
        return 0
    
    def get_remaining_budget(self):
        """Get remaining budget"""
        return self.budget - self.spent


class Hotel(models.Model):
    """نموذج الفنادق"""
    
    STAR_RATINGS = [
        (1, 'نجمة واحدة'),
        (2, 'نجمتان'),
        (3, 'ثلاث نجوم'),
        (4, 'أربع نجوم'),
        (5, 'خمس نجوم'),
    ]
    
    PRICE_RANGES = [
        ('economy', 'اقتصادي'),
        ('medium', 'متوسط'),
        ('luxury', 'فاخر'),
        ('budget', 'حسب الميزانية'),
    ]
    
    ROOM_TYPES = [
        ('single', 'مفردة'),
        ('double', 'مزدوجة'),
        ('triple', 'ثلاثية'),
        ('family', 'عائلية'),
        ('suite', 'جناح'),
        ('royal_suite', 'جناح ملكي'),
        ('connecting', 'غرفة متصلة'),
    ]
    
    MEAL_PLANS = [
        ('no_meals', 'بدون وجبات'),
        ('breakfast', 'إفطار مجاني'),
        ('half_board', 'نصف إقامة'),
        ('full_board', 'إقامة كاملة'),
        ('all_inclusive', 'شامل كلياً'),
    ]
    
    FACILITIES = [
        ('pool', 'مسبح'),
        ('indoor_pool', 'مسبح داخلي'),
        ('outdoor_pool', 'مسبح خارجي'),
        ('private_beach', 'شاطئ خاص'),
        ('spa', 'سبا'),
        ('sauna', 'ساونا'),
        ('jacuzzi', 'جاكوزي'),
        ('gym', 'نادي رياضي'),
        ('playground', 'ملعب أطفال'),
        ('meeting_room', 'قاعة اجتماعات'),
        ('event_hall', 'قاعة حفلات'),
        ('restaurant', 'مطعم'),
        ('cafe', 'مقهى'),
        ('elevator', 'مصعد'),
        ('room_service', 'خدمة الغرف 24 ساعة'),
    ]
    
    SERVICES = [
        ('parking', 'موقف سيارات'),
        ('wifi', 'واي فاي مجاني'),
        ('ac', 'تكييف'),
        ('reception_24h', 'استقبال 24 ساعة'),
        ('airport_transfer', 'نقل من وإلى المطار'),
        ('laundry', 'خدمة غسيل الملابس'),
        ('ev_charging', 'شحن سيارات كهربائية'),
        ('safe', 'خزنة داخل الغرفة'),
    ]
    
    SUITABLE_FOR = [
        ('families', 'العائلات'),
        ('couples', 'الأزواج'),
        ('business', 'رجال الأعمال'),
        ('honeymoon', 'شهر العسل'),
        ('special_needs', 'ذوي الاحتياجات الخاصة'),
        ('pets', 'يسمح بالحيوانات الأليفة'),
    ]
    
    HOTEL_TYPES = [
        ('economy', 'فندق اقتصادي'),
        ('business', 'فندق أعمال'),
        ('luxury', 'فندق فاخر'),
        ('boutique', 'بوتيك هوتيل'),
        ('resort', 'منتجع فندقي'),
        ('apartment', 'شقق فندقية'),
        ('inn', 'نُزل'),
        ('guesthouse', 'بيت ضيافة'),
    ]
    
    BOOKING_METHODS = [
        ('instant', 'حجز فوري'),
        ('pay_at_arrival', 'الدفع عند الوصول'),
        ('free_cancellation', 'إلغاء مجاني'),
        ('no_credit_card', 'حجز بدون بطاقة ائتمانية'),
    ]
    
    name = models.CharField(max_length=200, verbose_name='اسم الفندق')
    description = models.TextField(verbose_name='الوصف')
    star_rating = models.IntegerField(choices=STAR_RATINGS, verbose_name='التصنيف')
    price_range = models.CharField(max_length=20, choices=PRICE_RANGES, verbose_name='السعر')
    room_types = models.JSONField(default=list, verbose_name='أنواع الغرف')
    meal_plan = models.CharField(max_length=20, choices=MEAL_PLANS, blank=True, verbose_name='خطة الوجبات')
    services = models.JSONField(default=list, verbose_name='الخدمات')
    suitable_for = models.JSONField(default=list, verbose_name='مناسب لـ')
    
    # Location
    governorate = models.CharField(max_length=50, choices=IRAQ_GOVERNORATES, verbose_name='المحافظة')
    city = models.CharField(max_length=100, verbose_name='المدينة')
    address = models.TextField(verbose_name='العنوان')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='خط العرض')
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='خط الطول')
    
    # Contact
    phone = models.CharField(max_length=20, verbose_name='رقم الهاتف')
    email = models.EmailField(verbose_name='البريد الإلكتروني')
    website = models.URLField(blank=True, verbose_name='الموقع الإلكتروني')
    
    # Media
    image = models.ImageField(upload_to='hotels/', verbose_name='الصورة الرئيسية')
    
    # Link to HotelPage
    page = models.ForeignKey(
        'HotelPage', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hotel_listings', verbose_name='الصفحة'
    )
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    is_featured = models.BooleanField(default=False, verbose_name='مميز')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'فندق'
        verbose_name_plural = 'الفنادق'
        ordering = ['-is_featured', '-star_rating', 'name']
    
    def __str__(self):
        return f'{self.name} - {self.get_star_rating_display()}'


class HotelImage(models.Model):
    """صور الفنادق"""
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='images', verbose_name='الفندق')
    image = models.ImageField(upload_to='hotels/gallery/', verbose_name='الصورة')
    caption = models.CharField(max_length=200, blank=True, verbose_name='التعليق')
    is_primary = models.BooleanField(default=False, verbose_name='رئيسية')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الرفع')
    
    class Meta:
        verbose_name = 'صورة فندق'
        verbose_name_plural = 'صور الفنادق'
        ordering = ['-is_primary', 'id']
    
    def __str__(self):
        return f'صورة {self.hotel.name}'


class BuildingRequest(models.Model):
    """نظام طلبات بناء حسب المحافظة"""
    
    STATUS_CHOICES = [
        ('pending', 'قيد الانتظار'),
        ('in_review', 'قيد المراجعة'),
        ('approved', 'موافق عليه'),
        ('in_progress', 'قيد التنفيذ'),
        ('completed', 'مكتمل'),
        ('cancelled', 'ملغي'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'منخفض'),
        ('medium', 'متوسط'),
        ('high', 'عالي'),
        ('urgent', 'عاجل'),
    ]
    
    # معلومات العميل
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='building_requests', verbose_name='المستخدم', null=True, blank=True)
    broker = models.ForeignKey('Broker', on_delete=models.CASCADE, related_name='building_requests', verbose_name='الدلال', null=True, blank=True)
    full_name = models.CharField(max_length=200, blank=True, verbose_name='الاسم الكامل')
    phone = models.CharField(max_length=20, blank=True, verbose_name='رقم الهاتف')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    
    # نوع الناشر
    publisher_type = models.CharField(
        max_length=20,
        choices=[
            ('user', 'مستخدم'),
            ('broker', 'دلال'),
            ('admin', 'إدارة'),
        ],
        default='user',
        verbose_name='نوع الناشر'
    )
    
    # حالة العرض للجمهور
    is_public = models.BooleanField(default=False, verbose_name='عرض للجمهور')
    is_featured = models.BooleanField(default=False, verbose_name='مميز')
    featured_until = models.DateTimeField(null=True, blank=True, verbose_name='نهاية التمييز')
    
    # معلومات المشروع
    governorate = models.CharField(max_length=100, choices=IRAQ_GOVERNORATES, blank=True, verbose_name='المحافظة')
    city = models.CharField(max_length=100, blank=True, verbose_name='المدينة')
    district = models.CharField(max_length=100, blank=True, verbose_name='المنطقة')
    address = models.TextField(blank=True, verbose_name='العنوان التفصيلي')
    
    # تفاصيل البناء
    project_type = models.CharField(max_length=50, blank=True, verbose_name='نوع المشروع')
    estimated_area = models.PositiveIntegerField(null=True, blank=True, verbose_name='المساحة المقدرة (م²)')
    estimated_budget = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name='الميزانية المقدرة')
    expected_start_date = models.DateField(null=True, blank=True, verbose_name='تاريخ البدء المتوقع')
    expected_completion_date = models.DateField(null=True, blank=True, verbose_name='تاريخ الإنجاز المتوقع')
    
    # حالة الطلب
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', verbose_name='الأولوية')
    
    # وصف المشروع
    description = models.TextField(blank=True, verbose_name='وصف المشروع')
    requirements = models.TextField(blank=True, verbose_name='المتطلبات الخاصة')
    
    # معلومات إضافية
    assigned_broker = models.ForeignKey('Broker', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_building_requests', verbose_name='الدلال المكلف')
    notes = models.TextField(blank=True, verbose_name='ملاحظات الإدارة')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'طلب بناء'
        verbose_name_plural = 'طلبات البناء'
        ordering = ['-created_at', '-priority']
        indexes = [
            models.Index(fields=['governorate']),
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f'{self.full_name} - {self.get_governorate_display()} - {self.project_type}'
    
    def get_days_since_creation(self):
        """حساب عدد الأيام منذ إنشاء الطلب"""
        from django.utils import timezone
        delta = timezone.now() - self.created_at
        return delta.days
    
    def is_overdue(self):
        """التحقق مما إذا كان الطلب متأخراً"""
        if self.expected_completion_date and self.status in ['in_progress', 'pending', 'in_review']:
            from django.utils import timezone
            return timezone.now().date() > self.expected_completion_date
        return False


class LandInfo(models.Model):
    LAND_TYPE_CHOICES = [
        ('residential', 'سكني'),
        ('commercial', 'تجاري'),
        ('agricultural', 'زراعي'),
    ]
    
    building_request = models.OneToOneField(
        BuildingRequest, on_delete=models.CASCADE, related_name='land_info'
    )
    plot_location = models.CharField(max_length=200, verbose_name='موقع القطعة')
    area = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='مساحة الأرض (متر مربع)')
    width = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='العرض (متر)')
    length = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='الطول (متر)')
    land_type = models.CharField(max_length=20, choices=LAND_TYPE_CHOICES, verbose_name='نوع الأرض')
    deed_image = models.ImageField(upload_to='building_deeds/', verbose_name='صورة السند أو المخطط', blank=True, null=True)

    class Meta:
        verbose_name = 'معلومات الأرض'
        verbose_name_plural = 'معلومات الأراضي'

    def __str__(self):
        return f'{self.building_request.full_name} - {self.plot_location}'


class BuildingDetails(models.Model):
    ARCHITECTURAL_STYLE_CHOICES = [
        ('modern', 'مودرن'),
        ('classic', 'كلاسيكي'),
        ('contemporary', 'حديث'),
    ]
    
    building_request = models.OneToOneField(
        BuildingRequest, on_delete=models.CASCADE, related_name='building_details'
    )
    floors = models.IntegerField(verbose_name='عدد الطوابق')
    rooms = models.IntegerField(verbose_name='عدد الغرف')
    bathrooms = models.IntegerField(verbose_name='عدد الحمامات')
    has_garage = models.BooleanField(default=False, verbose_name='وجود كراج')
    has_garden = models.BooleanField(default=False, verbose_name='وجود حديقة')
    has_elevator = models.BooleanField(default=False, verbose_name='وجود مصعد')
    architectural_style = models.CharField(max_length=20, choices=ARCHITECTURAL_STYLE_CHOICES, verbose_name='النمط المعماري')

    class Meta:
        verbose_name = 'تفاصيل البناء'
        verbose_name_plural = 'تفاصيل البناء'

    def __str__(self):
        return f'{self.building_request.owner_name} - {self.floors} طوابق'


class Budget(models.Model):
    FINISHING_LEVEL_CHOICES = [
        ('economy', 'اقتصادي'),
        ('medium', 'متوسط'),
        ('luxury', 'فاخر'),
        ('super_deluxe', 'سوبر ديلوكس'),
    ]
    
    building_request = models.OneToOneField(
        BuildingRequest, on_delete=models.CASCADE, related_name='budget'
    )
    estimated_budget = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='الميزانية التقريبية')
    finishing_level = models.CharField(max_length=20, choices=FINISHING_LEVEL_CHOICES, verbose_name='مستوى التشطيب')

    class Meta:
        verbose_name = 'الميزانية'
        verbose_name_plural = 'الميزانيات'

    def __str__(self):
        return f'{self.building_request.owner_name} - {self.estimated_budget:,}'


class Blueprint(models.Model):
    FILE_TYPE_CHOICES = [
        ('pdf', 'مخطط PDF'),
        ('image', 'صور توضيحية'),
        ('autocad', 'ملف AutoCAD'),
    ]
    
    building_request = models.ForeignKey(
        BuildingRequest, on_delete=models.CASCADE, related_name='blueprints'
    )
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, verbose_name='نوع الملف')
    file = models.FileField(upload_to='building_blueprints/', verbose_name='الملف')
    description = models.CharField(max_length=200, verbose_name='الوصف', blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الرفع')

    class Meta:
        verbose_name = 'مخطط'
        verbose_name_plural = 'المخططات'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.building_request.owner_name} - {self.get_file_type_display()}'


class Quote(models.Model):
    QUOTE_TYPE_CHOICES = [
        ('company', 'عرض من شركة بناء'),
        ('engineer', 'عرض من مهندس'),
    ]
    
    building_request = models.ForeignKey(
        BuildingRequest, on_delete=models.CASCADE, related_name='quotes'
    )
    quote_type = models.CharField(max_length=20, choices=QUOTE_TYPE_CHOICES, verbose_name='نوع العرض')
    provider_name = models.CharField(max_length=200, verbose_name='اسم المزود')
    price = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='السعر')
    duration_days = models.IntegerField(verbose_name='مدة التنفيذ (أيام)')
    description = models.TextField(verbose_name='الوصف', blank=True)
    is_accepted = models.BooleanField(default=False, verbose_name='مقبول')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ العرض')

    class Meta:
        verbose_name = 'عرض سعر'
        verbose_name_plural = 'عروض الأسعار'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.provider_name} - {self.price:,}'


class FinancialTransaction(models.Model):
    """Track sales and commissions"""
    TRANSACTION_TYPES = [
        ('sale', 'بيع عقار'),
        ('commission', 'عمولة'),
        ('refund', 'استرجاع'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'قيد الانتظار'),
        ('completed', 'مكتمل'),
        ('cancelled', 'ملغي'),
    ]
    
    COMMISSION_TYPES = [
        ('percentage', 'نسبة مئوية'),
        ('fixed', 'مبلغ ثابت'),
    ]
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='financial_transactions', null=True, blank=True)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, verbose_name='نوع المعاملة')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة')
    
    # Sale details
    sale_price = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name='سعر البيع')
    
    # Commission details
    commission_type = models.CharField(max_length=20, choices=COMMISSION_TYPES, default='percentage', verbose_name='نوع العمولة')
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='نسبة العمولة (%)')
    commission_amount = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name='مبلغ العمولة')
    
    # Owner details
    owner_name = models.CharField(max_length=200, blank=True, verbose_name='اسم صاحب العقار')
    owner_amount = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name='المبلغ المستحق لصاحب العقار')
    additional_fees = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='رسوم إضافية')
    
    # Platform commission
    platform_commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='نسبة المنصة (%)')
    platform_commission_amount = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='مبلغ عمولة المنصة')
    
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='financial_transactions')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ المعاملة')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الإتمام')
    
    class Meta:
        verbose_name = 'معاملة مالية'
        verbose_name_plural = 'المعاملات المالية'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.get_transaction_type_display()} - {self.sale_price:,}'
    
    def calculate_commission(self):
        """Calculate commission based on type and rate"""
        if self.commission_type == 'percentage' and self.commission_rate and self.sale_price:
            return (self.sale_price * self.commission_rate) / 100
        elif self.commission_type == 'fixed' and self.commission_amount:
            return self.commission_amount
        return 0
    
    def calculate_owner_amount(self):
        """Calculate amount due to property owner"""
        commission = self.calculate_commission()
        platform_commission = (self.sale_price * self.platform_commission_rate) / 100 if self.platform_commission_rate and self.sale_price else 0
        return self.sale_price - commission - platform_commission - self.additional_fees
    
    def save(self, *args, **kwargs):
        """Auto-calculate amounts before saving"""
        if self.sale_price:
            self.commission_amount = self.calculate_commission()
            self.owner_amount = self.calculate_owner_amount()
            if self.platform_commission_rate:
                self.platform_commission_amount = (self.sale_price * self.platform_commission_rate) / 100
        super().save(*args, **kwargs)


class Expense(models.Model):
    """Track office operating expenses"""
    EXPENSE_CATEGORIES = [
        ('rent', 'إيجار المكتب'),
        ('salary', 'رواتب الموظفين'),
        ('marketing', 'إعلانات وتسويق'),
        ('fuel', 'وقود وتنقل'),
        ('internet', 'إنترنت واتصالات'),
        ('utilities', 'مرافق'),
        ('other', 'مصاريف أخرى'),
    ]
    
    category = models.CharField(max_length=20, choices=EXPENSE_CATEGORIES, verbose_name='فئة المصروف')
    title = models.CharField(max_length=200, blank=True, verbose_name='العنوان')
    amount = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name='المبلغ')
    date = models.DateField(null=True, blank=True, verbose_name='التاريخ')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    receipt_image = models.ImageField(upload_to=property_image_path, null=True, blank=True, verbose_name='صورة الإيصال')
    
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='expenses')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإدخال')
    
    class Meta:
        verbose_name = 'مصروف'
        verbose_name_plural = 'المصاريف'
        ordering = ['-date']
    
    def __str__(self):
        return f'{self.title} - {self.amount:,}'


class Payment(models.Model):
    """Track payments to property owners"""
    PAYMENT_TYPES = [
        ('full', 'دفعة كاملة'),
        ('partial', 'دفعة جزئية'),
        ('advance', 'سلفة'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'قيد الانتظار'),
        ('completed', 'مكتمل'),
        ('cancelled', 'ملغي'),
    ]
    
    financial_transaction = models.ForeignKey(FinancialTransaction, on_delete=models.CASCADE, related_name='payments')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES, verbose_name='نوع الدفعة')
    amount = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='المبلغ')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة')
    payment_date = models.DateField(null=True, blank=True, verbose_name='تاريخ الدفع')
    payment_method = models.CharField(max_length=100, blank=True, verbose_name='طريقة الدفع')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='payments')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإدخال')
    
    class Meta:
        verbose_name = 'دفعة'
        verbose_name_plural = 'المدفوعات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.financial_transaction.owner_name} - {self.amount:,}'
    
    def get_remaining_amount(self):
        """Calculate remaining amount to be paid"""
        total_paid = self.financial_transaction.payments.filter(status='completed').aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        return self.financial_transaction.owner_amount - total_paid


class OfficeWallet(models.Model):
    """Financial wallet for each office/user"""
    TRANSACTION_TYPES = [
        ('commission', 'عمولة'),
        ('withdrawal', 'سحب'),
        ('deposit', 'إيداع'),
        ('adjustment', 'تعديل'),
    ]
    
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='wallet')
    current_balance = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='الرصيد الحالي')
    pending_commissions = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='الأرباح المعلقة')
    received_commissions = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='الأرباح المستلمة')
    withdrawn_amount = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='الأرباح المسحوبة')
    
    class Meta:
        verbose_name = 'محفظة مالية'
        verbose_name_plural = 'المحافظ المالية'
    
    def __str__(self):
        return f'محفظة {self.user.username} - {self.current_balance:,}'
    
    def get_total_available(self):
        """Get total available balance"""
        return self.current_balance + self.pending_commissions


class WalletTransaction(models.Model):
    """Track individual wallet transactions"""
    wallet = models.ForeignKey(OfficeWallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=OfficeWallet.TRANSACTION_TYPES, verbose_name='نوع المعاملة')
    amount = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='المبلغ')
    balance_before = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='الرصيد قبل')
    balance_after = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='الرصيد بعد')
    description = models.TextField(verbose_name='الوصف')
    related_transaction = models.ForeignKey(FinancialTransaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='wallet_transactions')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='التاريخ')
    
    class Meta:
        verbose_name = 'معاملة محفظة'
        verbose_name_plural = 'معاملات المحفظة'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.get_transaction_type_display()} - {self.amount:,}'


class ProjectTracking(models.Model):
    building_request = models.OneToOneField(
        BuildingRequest, on_delete=models.CASCADE, related_name='project_tracking'
    )
    progress_percentage = models.IntegerField(default=0, verbose_name='نسبة الإنجاز')
    weekly_photos = models.TextField(verbose_name='صور أسبوعية للموقع', blank=True)
    engineer_reports = models.TextField(verbose_name='تقارير المهندس', blank=True)
    payment_schedule = models.TextField(verbose_name='جدول الدفعات', blank=True)
    last_updated = models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')

    class Meta:
        verbose_name = 'متابعة المشروع'
        verbose_name_plural = 'متابعة المشاريع'

    def __str__(self):
        return f'{self.building_request.owner_name} - {self.progress_percentage}%'


class DeliveryMilestone(models.Model):
    MILESTONE_TYPE_CHOICES = [
        ('structure', 'استلام الهيكل'),
        ('finishing', 'استلام التشطيبات'),
        ('utilities', 'استلام الكهرباء والماء'),
        ('final', 'استلام المفتاح النهائي'),
    ]
    
    building_request = models.ForeignKey(
        BuildingRequest, on_delete=models.CASCADE, related_name='delivery_milestones'
    )
    milestone_type = models.CharField(max_length=20, choices=MILESTONE_TYPE_CHOICES, verbose_name='نوع المرحلة')
    is_completed = models.BooleanField(default=False, verbose_name='مكتمل')
    completed_date = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الإنجاز')
    notes = models.TextField(verbose_name='ملاحظات', blank=True)

    class Meta:
        verbose_name = 'مرحلة تسليم'
        verbose_name_plural = 'مراحل التسليم'
        ordering = ['id']

    def __str__(self):
        return f'{self.building_request.owner_name} - {self.get_milestone_type_display()}'


class ContractorRating(models.Model):
    building_request = models.ForeignKey(
        BuildingRequest, on_delete=models.CASCADE, related_name='contractor_ratings'
    )
    contractor_name = models.CharField(max_length=200, verbose_name='اسم المقاول')
    rating = models.IntegerField(verbose_name='التقييم (1-5)')
    review = models.TextField(verbose_name='التقييم المفصل')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التقييم')

    class Meta:
        verbose_name = 'تقييم مقاول'
        verbose_name_plural = 'تقييمات المقاولين'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.contractor_name} - {self.rating}/5'


class ContractorBid(models.Model):
    building_request = models.ForeignKey(
        BuildingRequest, on_delete=models.CASCADE, related_name='contractor_bids'
    )
    contractor_name = models.CharField(max_length=200, verbose_name='اسم المقاول')
    bid_amount = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='مبلغ المزايدة')
    bid_description = models.TextField(verbose_name='وصف العرض', blank=True)
    is_winning = models.BooleanField(default=False, verbose_name='الفائز')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ المزايدة')

    class Meta:
        verbose_name = 'مزايدة مقاول'
        verbose_name_plural = 'مزايدات المقاولين'
        ordering = ['-bid_amount', '-created_at']

    def __str__(self):
        return f'{self.contractor_name} - {self.bid_amount:,}'


class ServiceProvider(models.Model):
    """نموذج مقدمي الخدمات (مقاولين، كهربائيين، سباكين، إلخ)"""
    
    SERVICE_TYPE_CHOICES = [
        ('construction', 'بناء وتشطيب'),
        ('electricity', 'كهرباء'),
        ('plumbing', 'سباكة'),
        ('carpentry', 'نجارة'),
        ('painting', 'دهان'),
        ('hvac', 'تكييف وتبريد'),
        ('landscaping', 'تنسيق حدائق'),
        ('security', 'أمن وحراسة'),
        ('cleaning', 'تنظيف'),
        ('moving', 'نقل عفش'),
        ('other', 'خدمات أخرى'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'نشط'),
        ('inactive', 'غير نشط'),
        ('suspended', 'موقوف'),
    ]
    
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='service_provider', verbose_name='المستخدم')
    business_name = models.CharField(max_length=200, verbose_name='اسم العمل/الشركة')
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES, verbose_name='نوع الخدمة')
    description = models.TextField(verbose_name='وصف الخدمات', blank=True)
    
    # معلومات التواصل
    phone = models.CharField(max_length=20, verbose_name='رقم الهاتف')
    whatsapp = models.CharField(max_length=20, blank=True, verbose_name='واتساب')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    address = models.CharField(max_length=300, blank=True, verbose_name='العنوان')
    governorate = models.CharField(max_length=100, choices=IRAQ_GOVERNORATES, blank=True, verbose_name='المحافظة')
    
    # معلومات العمل
    years_experience = models.IntegerField(default=0, verbose_name='سنوات الخبرة')
    team_size = models.IntegerField(default=1, verbose_name='حجم الفريق')
    working_hours = models.CharField(max_length=100, blank=True, verbose_name='ساعات العمل')
    
    # الأسعار
    min_price = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name='أقل سعر')
    max_price = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name='أعلى سعر')
    price_unit = models.CharField(max_length=50, blank=True, verbose_name='وحدة السعر (متر مربع، مشروع، إلخ)')
    
    # الشهادات والتراخيص
    licenses = models.TextField(blank=True, verbose_name='التراخيص والشهادات')
    
    # الوسائط
    logo = models.ImageField(upload_to='service_providers/logos/', blank=True, null=True, verbose_name='الشعار')
    cover_image = models.ImageField(upload_to='service_providers/covers/', blank=True, null=True, verbose_name='صورة الغلاف')
    
    # التقييم
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0, verbose_name='التقييم')
    reviews_count = models.IntegerField(default=0, verbose_name='عدد التقييمات')
    completed_projects = models.IntegerField(default=0, verbose_name='المشاريع المكتملة')
    
    # الحالة
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name='الحالة')
    is_verified = models.BooleanField(default=False, verbose_name='موثق')
    is_featured = models.BooleanField(default=False, verbose_name='مميز')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'مقدم خدمة'
        verbose_name_plural = 'مقدمو الخدمات'
        ordering = ['-is_featured', '-rating', '-created_at']
        indexes = [
            models.Index(fields=['service_type']),
            models.Index(fields=['governorate']),
            models.Index(fields=['status']),
            models.Index(fields=['-rating']),
        ]
    
    def __str__(self):
        return f'{self.business_name} - {self.get_service_type_display()}'


class ServiceAdvertisement(models.Model):
    """إعلانات الخدمات لمقدمي الخدمات"""
    
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('active', 'نشط'),
        ('paused', 'متوقف'),
        ('expired', 'منتهي'),
    ]
    
    service_provider = models.ForeignKey(ServiceProvider, on_delete=models.CASCADE, related_name='advertisements', verbose_name='مقدم الخدمة')
    title = models.CharField(max_length=200, verbose_name='عنوان الإعلان')
    description = models.TextField(verbose_name='وصف الإعلان')
    service_type = models.CharField(max_length=20, choices=ServiceProvider.SERVICE_TYPE_CHOICES, verbose_name='نوع الخدمة')
    
    # معلومات المشروع
    project_type = models.CharField(max_length=100, blank=True, verbose_name='نوع المشروع')
    location = models.CharField(max_length=200, blank=True, verbose_name='الموقع')
    governorate = models.CharField(max_length=100, choices=IRAQ_GOVERNORATES, blank=True, verbose_name='المحافظة')
    
    # الأسعار
    price = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True, verbose_name='السعر')
    price_description = models.CharField(max_length=200, blank=True, verbose_name='وصف السعر')
    
    # التفاصيل
    completion_time = models.CharField(max_length=100, blank=True, verbose_name='وقت الإنجاز')
    includes = models.TextField(blank=True, verbose_name='ما يشمله العرض')
    requirements = models.TextField(blank=True, verbose_name='المتطلبات')
    
    # الوسائط
    cover_image = models.ImageField(upload_to='service_ads/covers/', blank=True, null=True, verbose_name='صورة الغلاف')
    
    # الحالة
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='الحالة')
    is_featured = models.BooleanField(default=False, verbose_name='مميز')
    featured_until = models.DateTimeField(null=True, blank=True, verbose_name='نهاية التمييز')
    
    # الإحصائيات
    views_count = models.IntegerField(default=0, verbose_name='عدد المشاهدات')
    inquiries_count = models.IntegerField(default=0, verbose_name='عدد الاستفسارات')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الانتهاء')
    
    class Meta:
        verbose_name = 'إعلان خدمة'
        verbose_name_plural = 'إعلانات الخدمات'
        ordering = ['-is_featured', '-created_at']
        indexes = [
            models.Index(fields=['service_type']),
            models.Index(fields=['governorate']),
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f'{self.title} - {self.service_provider.business_name}'


class ServiceAdvertisementImage(models.Model):
    """صور إعلانات الخدمات"""
    advertisement = models.ForeignKey(ServiceAdvertisement, on_delete=models.CASCADE, related_name='images', verbose_name='الإعلان')
    image = models.ImageField(upload_to='service_ads/images/', verbose_name='الصورة')
    caption = models.CharField(max_length=200, blank=True, verbose_name='التعليق')
    is_cover = models.BooleanField(default=False, verbose_name='صورة الغلاف')
    order = models.IntegerField(default=0, verbose_name='الترتيب')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الرفع')
    
    class Meta:
        verbose_name = 'صورة إعلان'
        verbose_name_plural = 'صور الإعلانات'
        ordering = ['order', '-created_at']
    
    def __str__(self):
        return f'{self.advertisement.title} - صورة {self.order}'


class ServiceAdvertisementVideo(models.Model):
    """فيديوهات إعلانات الخدمات"""
    advertisement = models.ForeignKey(ServiceAdvertisement, on_delete=models.CASCADE, related_name='videos', verbose_name='الإعلان')
    video = models.FileField(upload_to='service_ads/videos/', verbose_name='الفيديو')
    thumbnail = models.ImageField(upload_to='service_ads/thumbnails/', blank=True, null=True, verbose_name='الصورة المصغرة')
    caption = models.CharField(max_length=200, blank=True, verbose_name='التعليق')
    duration = models.IntegerField(null=True, blank=True, verbose_name='المدة (ثواني)')
    order = models.IntegerField(default=0, verbose_name='الترتيب')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الرفع')
    
    class Meta:
        verbose_name = 'فيديو إعلان'
        verbose_name_plural = 'فيديوهات الإعلانات'
        ordering = ['order', '-created_at']
    
    def __str__(self):
        return f'{self.advertisement.title} - فيديو {self.order}'


class BrokerServicePromotion(models.Model):
    """ترقية إعلانات الخدمات من قبل الدلال"""
    
    broker = models.ForeignKey('Broker', on_delete=models.CASCADE, related_name='service_promotions', verbose_name='الدلال')
    advertisement = models.ForeignKey(ServiceAdvertisement, on_delete=models.CASCADE, related_name='broker_promotions', verbose_name='الإعلان')
    
    # تفاصيل الترقية
    posts_count = models.IntegerField(default=1, verbose_name='عدد المنشورات')
    duration_days = models.IntegerField(default=7, verbose_name='عدد الأيام')
    
    # التواريخ
    start_date = models.DateTimeField(verbose_name='تاريخ البدء')
    end_date = models.DateTimeField(verbose_name='تاريخ الانتهاء')
    
    # الحالة
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    posts_published = models.IntegerField(default=0, verbose_name='المنشورات المنشورة')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    
    class Meta:
        verbose_name = 'ترقية خدمة'
        verbose_name_plural = 'ترقيات الخدمات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.broker.display_name} - {self.advertisement.title}'


class Office(models.Model):
    name = models.CharField(max_length=200, verbose_name='اسم المكتب')
    address = models.CharField(max_length=300, blank=True, verbose_name='العنوان')
    phone = models.CharField(max_length=30, blank=True, verbose_name='الهاتف')
    governorate = models.CharField(max_length=100, blank=True, verbose_name='المحافظة')
    owner = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='owned_offices', verbose_name='المالك'
    )
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'مكتب عقاري'
        verbose_name_plural = 'المكاتب العقارية'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def broker_count(self):
        return self.brokers.filter(is_active=True).count()

    @property
    def property_count(self):
        return self.properties.count()


class Profit(models.Model):
    """تتبع الأرباح من المقاولات والمعاملات"""
    
    PROFIT_TYPES = [
        ('sale', 'بيع عقار'),
        ('rent', 'إيجار عقار'),
        ('commission', 'عمولة'),
        ('other', 'أخرى'),
    ]
    
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='profits',
        verbose_name='المستخدم'
    )
    profit_type = models.CharField(
        max_length=20, choices=PROFIT_TYPES, verbose_name='نوع الربح'
    )
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name='مبلغ الربح'
    )
    property = models.ForeignKey(
        Property, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='profits', verbose_name='العقار'
    )
    client_name = models.CharField(
        max_length=200, blank=True, verbose_name='اسم العميل'
    )
    client_phone = models.CharField(
        max_length=20, blank=True, verbose_name='رقم العميل'
    )
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    date = models.DateField(
        default=timezone.now, verbose_name='تاريخ الربح'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')
    
    class Meta:
        verbose_name = 'ربح'
        verbose_name_plural = 'الأرباح'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f'{self.get_profit_type_display()} - {self.amount:,}'


class SubscriptionPlan(models.Model):
    """نماذج خطط الاشتراك"""
    
    period = models.CharField(
        max_length=20, 
        choices=SUBSCRIPTION_PERIODS,
        verbose_name='فترة الاشتراك'
    )
    ads_limit = models.PositiveIntegerField(verbose_name='حد الإعلانات')
    name = models.CharField(max_length=200, verbose_name='اسم الخطة')
    color = models.CharField(max_length=50, verbose_name='اللون')
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name='السعر الكلي'
    )
    price_per_property = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=50.00,
        verbose_name='سعر العقار اليومي (د.ع)',
        help_text='السعر الافتراضي: 50 دينار لكل عقار في اليوم'
    )
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'خطة اشتراك'
        verbose_name_plural = 'خطط الاشتراك'
        ordering = ['period', 'ads_limit']
    
    def __str__(self):
        return f'{self.name} - {self.ads_limit} إعلان'
    
    def get_daily_cost(self, property_count):
        """حساب التكلفة اليومية"""
        return property_count * self.price_per_property
    
    def get_monthly_cost(self, property_count):
        """حساب التكلفة الشهرية"""
        return self.get_daily_cost(property_count) * 30
    
    def get_yearly_cost(self, property_count):
        """حساب التكلفة السنوية"""
        return self.get_monthly_cost(property_count) * 12
    
    def get_five_year_cost(self, property_count):
        """حساب التكلفة لـ 5 سنوات"""
        return self.get_yearly_cost(property_count) * 5


class UserProfile(models.Model):
    """نموذج المستخدم العادي"""
    user = models.OneToOneField(
        'auth.User', on_delete=models.CASCADE, related_name='user_profile'
    )
    phone = models.CharField(max_length=20, blank=True, verbose_name='الهاتف')
    governorate = models.CharField(max_length=100, blank=True, verbose_name='المحافظة')
    profile_image = models.ImageField(upload_to='user_profiles/', blank=True, null=True, verbose_name='الصورة الشخصية')
    cover_image = models.ImageField(upload_to='user_covers/', blank=True, null=True, verbose_name='غلاف الصفحة')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'مستخدم عادي'
        verbose_name_plural = 'المستخدمين العاديين'

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    @property
    def display_name(self):
        full = self.user.get_full_name()
        return full or self.user.username


class Broker(models.Model):
    ROLE_ADMIN = 'admin'
    ROLE_MAIN = 'main'
    ROLE_SUB = 'sub'

    ROLE_CHOICES = [
        (ROLE_ADMIN, 'مدير النظام'),
        (ROLE_MAIN, 'دلال رئيسي'),
        (ROLE_SUB, 'دلال فرعي'),
    ]

    # User type constants
    TYPE_ADMIN = 'admin'
    TYPE_BROKER = 'broker'
    TYPE_USER = 'user'

    TYPE_CHOICES = [
        (TYPE_ADMIN, 'مدير'),
        (TYPE_BROKER, 'دلال'),
        (TYPE_USER, 'مستخدم عادي'),
    ]

    SUBSCRIPTION_MONTH = 'month'
    SUBSCRIPTION_3_MONTHS = '3_months'
    SUBSCRIPTION_6_MONTHS = '6_months'
    SUBSCRIPTION_YEAR = 'year'
    SUBSCRIPTION_5_YEARS = '5_years'
    SUBSCRIPTION_UNLIMITED = 'unlimited'

    SUBSCRIPTION_CHOICES = [
        (SUBSCRIPTION_MONTH, 'شهر (20 عقار)'),
        (SUBSCRIPTION_3_MONTHS, '3 أشهر (60 عقار)'),
        (SUBSCRIPTION_6_MONTHS, '6 أشهر (120 عقار)'),
        (SUBSCRIPTION_YEAR, 'سنة (300 عقار)'),
        (SUBSCRIPTION_5_YEARS, '5 سنوات (2000 عقار)'),
        (SUBSCRIPTION_UNLIMITED, 'غير محدود'),
    ]

    SUBSCRIPTION_LIMITS = {
        SUBSCRIPTION_MONTH: 20,
        SUBSCRIPTION_3_MONTHS: 60,
        SUBSCRIPTION_6_MONTHS: 120,
        SUBSCRIPTION_YEAR: 300,
        SUBSCRIPTION_5_YEARS: 2000,
        SUBSCRIPTION_UNLIMITED: float('inf'),
    }

    DURATION_MONTH = 'month'
    DURATION_3_MONTHS = '3_months'
    DURATION_6_MONTHS = '6_months'
    DURATION_YEAR = 'year'
    DURATION_5_YEARS = '5_years'
    DURATION_UNLIMITED = 'unlimited'

    DURATION_CHOICES = [
        (DURATION_MONTH, 'شهر'),
        (DURATION_3_MONTHS, '3 أشهر'),
        (DURATION_6_MONTHS, '6 أشهر'),
        (DURATION_YEAR, 'سنة'),
        (DURATION_5_YEARS, '5 سنوات'),
        (DURATION_UNLIMITED, 'غير محدود'),
    ]

    DURATION_DAYS = {
        DURATION_MONTH: 30,
        DURATION_3_MONTHS: 90,
        DURATION_6_MONTHS: 180,
        DURATION_YEAR: 365,
        DURATION_5_YEARS: 1825,
        DURATION_UNLIMITED: float('inf'),
    }

    user = models.OneToOneField(
        'auth.User', on_delete=models.CASCADE, related_name='broker_profile'
    )
    phone = models.CharField(max_length=20, verbose_name='الهاتف')
    office_name = models.CharField(max_length=200, blank=True, verbose_name='اسم المكتب')
    office = models.ForeignKey(
        Office, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='brokers', verbose_name='المكتب العقاري'
    )
    governorate = models.CharField(max_length=100, blank=True, verbose_name='المحافظة')
    profile_image = models.ImageField(upload_to='broker_profiles/', blank=True, null=True, verbose_name='الصورة الشخصية')
    cover_image = models.ImageField(upload_to='broker_covers/', blank=True, null=True, verbose_name='غلاف الصفحة')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_SUB, verbose_name='الدور')
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sub_brokers', verbose_name='الدلال الرئيسي'
    )
    is_verified = models.BooleanField(default=False, verbose_name='دلال موثق')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    slug = models.SlugField(max_length=100, unique=True, blank=True, null=True, allow_unicode=True, verbose_name='رابط الصفحة')
    
    PAGE_DISPLAY_CHOICES = [
        ('main_only', 'الصفحة الرئيسية فقط'),
        ('standalone_only', 'الصفحة المستقلة فقط'),
        ('both', 'الاثنين معاً'),
    ]
    
    page_display_mode = models.CharField(
        max_length=20,
        choices=PAGE_DISPLAY_CHOICES,
        default='main_only',
        verbose_name='طريقة عرض الصفحة',
        help_text='اختر أين تظهر عقاراتك'
    )
    
    # Subscription plan (for chat-based subscriptions only)
    subscription_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='brokers',
        verbose_name='خطة الاشتراك',
        help_text='يتم تفعيل الاشتراك فقط بعد المحادثة مع الإدارة'
    )
    subscription_start_date = models.DateField(
        null=True, blank=True, verbose_name='تاريخ بداية الاشتراك'
    )
    subscription_end_date = models.DateField(
        null=True, blank=True, verbose_name='تاريخ انتهاء الاشتراك'
    )
    # Sub-broker specific fields
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='نسبة العمولة',
        help_text='نسبة العمولة من مبيعات العقارات (0-100)'
    )
    commission_type = models.CharField(
        max_length=20, choices=[
            ('percentage', 'نسبة مئوية'),
            ('fixed', 'مبلغ ثابت'),
        ], default='percentage', verbose_name='نوع العمولة'
    )
    fixed_commission = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='العمولة الثابتة',
        help_text='مبلغ العمولة الثابت لكل عقار'
    )
    total_commissions = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='إجمالي العمولات'
    )
    paid_commissions = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='العمولات المدفوعة'
    )
    pending_commissions = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='العمولات المعلقة'
    )
    sales_count = models.PositiveIntegerField(
        default=0, verbose_name='عدد المبيعات'
    )
    target_sales = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='هدف المبيعات'
    )
    performance_rating = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True,
        verbose_name='تقييم الأداء',
        help_text='تقييم الأداء من 0 إلى 5'
    )
    can_add_properties = models.BooleanField(
        default=True, verbose_name='يمكن إضافة عقارات'
    )
    can_edit_properties = models.BooleanField(
        default=True, verbose_name='يمكن تعديل عقارات'
    )
    can_delete_properties = models.BooleanField(
        default=False, verbose_name='يمكن حذف عقارات'
    )
    is_suspended = models.BooleanField(
        default=False, verbose_name='مجمد'
    )
    id_card_image = models.ImageField(
        upload_to='broker_ids/', null=True, blank=True, verbose_name='صورة الهوية'
    )
    bio = models.TextField(blank=True, verbose_name='نبذة')
    
    # Standalone page settings
    site_name = models.CharField(max_length=200, blank=True, verbose_name='اسم الموقع')
    logo = models.ImageField(upload_to='broker_logos/', blank=True, null=True, verbose_name='الشعار')
    job_title = models.CharField(max_length=100, blank=True, verbose_name='المسمى الوظيفي')
    mission = models.TextField(blank=True, verbose_name='رسالتنا')
    vision = models.TextField(blank=True, verbose_name='رؤيتنا')
    years_of_experience = models.PositiveIntegerField(default=0, verbose_name='سنوات الخبرة')
    clients_count = models.PositiveIntegerField(default=0, verbose_name='عدد العملاء')
    working_governorates = models.TextField(blank=True, verbose_name='المحافظات التي يعمل بها', help_text='افصل بين المحافظات بفاصلة')
    
    # Contact information
    whatsapp = models.CharField(max_length=20, blank=True, verbose_name='واتساب')
    telegram = models.CharField(max_length=100, blank=True, verbose_name='تيليجرام')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    website = models.URLField(blank=True, verbose_name='الموقع الإلكتروني')
    address = models.TextField(blank=True, verbose_name='العنوان')
    working_hours = models.CharField(max_length=100, blank=True, verbose_name='ساعات العمل')
    google_maps_url = models.URLField(blank=True, verbose_name='رابط Google Maps')
    
    # Social media
    facebook = models.URLField(blank=True, verbose_name='فيسبوك')
    instagram = models.URLField(blank=True, verbose_name='إنستغرام')
    tiktok = models.URLField(blank=True, verbose_name='تيك توك')
    snapchat = models.URLField(blank=True, verbose_name='سناب شات')
    twitter = models.URLField(blank=True, verbose_name='تويتر (X)')
    youtube = models.URLField(blank=True, verbose_name='يوتيوب')
    linkedin = models.URLField(blank=True, verbose_name='لينكد إن')
    
    # SEO
    seo_title = models.CharField(max_length=200, blank=True, verbose_name='عنوان الصفحة')
    seo_description = models.TextField(blank=True, verbose_name='وصف SEO')
    seo_keywords = models.CharField(max_length=500, blank=True, verbose_name='الكلمات المفتاحية', help_text='افصل بين الكلمات بفاصلة')
    og_image = models.ImageField(upload_to='broker_og_images/', blank=True, null=True, verbose_name='صورة المشاركة')
    
    # Customization
    page_color = models.CharField(max_length=7, blank=True, default='#FF7A00', verbose_name='لون الصفحة')
    button_color = models.CharField(max_length=7, blank=True, default='#FF7A00', verbose_name='لون الأزرار')
    text_color = models.CharField(max_length=7, blank=True, default='#333333', verbose_name='لون النص')
    background_color = models.CharField(max_length=7, blank=True, default='#FFFFFF', verbose_name='لون الخلفية')
    font_family = models.CharField(max_length=50, blank=True, default='Cairo', verbose_name='نوع الخط')
    background_image = models.ImageField(upload_to='broker_backgrounds/', blank=True, null=True, verbose_name='صورة الخلفية')
    banner_image = models.ImageField(upload_to='broker_banners/', blank=True, null=True, verbose_name='بانر الصفحة')
    
    # Display settings
    show_phone = models.BooleanField(default=True, verbose_name='إظهار رقم الهاتف')
    show_email = models.BooleanField(default=True, verbose_name='إظهار البريد الإلكتروني')
    show_whatsapp = models.BooleanField(default=True, verbose_name='إظهار واتساب')
    show_social_media = models.BooleanField(default=True, verbose_name='إظهار مواقع التواصل')
    show_address = models.BooleanField(default=True, verbose_name='إظهار العنوان')
    show_properties = models.BooleanField(default=True, verbose_name='إظهار العقارات')
    show_stats = models.BooleanField(default=True, verbose_name='إظهار الإحصائيات')
    show_ratings = models.BooleanField(default=True, verbose_name='إظهار التقييمات')
    show_working_hours = models.BooleanField(default=True, verbose_name='إظهار ساعات العمل')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'دلال'
        verbose_name_plural = 'الدلالين'
        ordering = ['-created_at']

    def get_property_limit(self):
        if self.subscription_plan:
            return self.subscription_plan.ads_limit
        return 0

    def get_published_properties_count(self):
        """Get count of published properties for this broker."""
        return self.properties.count()

    def get_remaining_properties(self):
        """Get remaining property slots based on subscription."""
        limit = self.get_property_limit()
        if limit == 0:
            return 0
        published = self.get_published_properties_count()
        remaining = limit - published
        return max(0, remaining)

    def get_days_remaining(self):
        """Get days remaining until subscription expires."""
        if not self.subscription_end_date:
            return None
        from django.utils import timezone
        today = timezone.now().date()
        if self.subscription_end_date < today:
            return 0
        delta = self.subscription_end_date - today
        return delta.days

    def get_days_elapsed(self):
        """Get days elapsed since subscription started."""
        if not self.subscription_start_date:
            return None
        from django.utils import timezone
        today = timezone.now().date()
        if self.subscription_start_date > today:
            return 0
        delta = today - self.subscription_start_date
        return delta.days

    def get_subscription_status(self):
        """Get subscription status: active, expired, or suspended."""
        if self.is_suspended:
            return 'suspended'
        if self.is_subscription_expired():
            return 'expired'
        return 'active'

    def is_subscription_expired(self):
        """Check if subscription is expired."""
        if not self.subscription_end_date:
            return False
        from django.utils import timezone
        today = timezone.now().date()
        return self.subscription_end_date < today

    def is_subscription_active(self):
        """Check if subscription is active."""
        if not self.subscription_end_date:
            return False
        from django.utils import timezone
        today = timezone.now().date()
        return self.subscription_end_date >= today and not self.is_suspended

    def check_subscription_status(self):
        """Check and update subscription status automatically."""
        if not self.subscription_end_date:
            return
        
        from django.utils import timezone
        today = timezone.now().date()
        
        if self.subscription_end_date < today and not self.is_suspended:
            # Subscription expired, suspend account
            self.is_suspended = True
            self.can_add_properties = False
            self.can_edit_properties = False
            self.save()
            
            # Create notification for user
            try:
                from .models import Notification
                Notification.create_for_user(
                    user=self.user,
                    notification_type='subscription',
                    title='انتهاء الاشتراك',
                    message=(
                        f'انتهى اشتراكك في {self.subscription_end_date}. '
                        'تم تعطيل حسابك مؤقتاً. يرجى تجديد الاشتراك للاستمرار.'
                    ),
                )
            except Exception:
                pass

    def can_publish_property(self):
        """Check if broker can publish property."""
        if self.is_suspended:
            return False
        if not self.is_subscription_active():
            return False
        if not self.can_add_properties:
            return False
        
        # Check property limit
        remaining = self.get_remaining_properties()
        return remaining > 0

    def save(self, *args, **kwargs):
        """Override save to auto-suspend if expired."""
        # Auto-suspend if subscription is expired
        if self.is_subscription_expired() and not self.is_suspended:
            self.is_suspended = True
        super().save(*args, **kwargs)

    def get_subscription_status_display(self):
        """Get Arabic display for subscription status."""
        status = self.get_subscription_status()
        status_map = {
            'active': '🟢 فعال',
            'expired': '🔴 منتهي',
            'suspended': '🟡 موقوف',
        }
        return status_map.get(status, 'غير معروف')

    def is_subscription_active(self):
        """Check if subscription is active (not expired and not suspended)."""
        if self.is_suspended:
            return False
        if self.is_subscription_expired():
            return False
        return True

    def can_add_property(self):
        """Check if broker can add more properties."""
        if not self.is_subscription_active():
            return False
        if not self.can_add_properties:
            return False
        remaining = self.get_remaining_properties()
        if remaining == float('inf'):
            return True
        return remaining > 0

    def calculate_commission(self, property_price):
        """Calculate commission for a property sale."""
        if self.commission_type == 'percentage':
            return (property_price * self.commission_rate) / 100
        else:
            return self.fixed_commission or 0

    def add_commission(self, amount, status='pending'):
        """Add commission to broker's records."""
        self.total_commissions += amount
        if status == 'paid':
            self.paid_commissions += amount
        elif status == 'pending':
            self.pending_commissions += amount
        self.save()

    def get_commission_summary(self):
        """Get commission summary."""
        return {
            'total': self.total_commissions,
            'paid': self.paid_commissions,
            'pending': self.pending_commissions,
            'balance': self.total_commissions - self.paid_commissions
        }

    def get_sales_performance(self):
        """Get sales performance metrics."""
        if self.target_sales and self.target_sales > 0:
            achievement = (self.sales_count / self.target_sales) * 100
        else:
            achievement = 0
        return {
            'sales_count': self.sales_count,
            'target_sales': self.target_sales,
            'achievement_percentage': achievement,
            'performance_rating': self.performance_rating
        }

    def get_sub_broker_permissions(self):
        """Get sub-broker specific permissions."""
        return {
            'can_add': self.can_add_properties,
            'can_edit': self.can_edit_properties,
            'can_delete': self.can_delete_properties,
            'max_properties': self.max_properties or self.get_property_limit()
        }

    def renew_subscription(self, duration=None):
        """Renew subscription for specified duration."""
        from django.utils import timezone
        if duration:
            self.subscription_duration = duration
        days = self.DURATION_DAYS.get(self.subscription_duration, 30)
        if days == float('inf'):
            self.subscription_start_date = timezone.now().date()
            self.subscription_end_date = None
        else:
            self.subscription_start_date = timezone.now().date()
            self.subscription_end_date = self.subscription_start_date + timezone.timedelta(days=days)
        self.is_suspended = False
        self.save()

    def __str__(self):
        verified = ' ✅' if self.is_verified else ''
        return f'{self.display_name}{verified}'

    @property
    def display_name(self):
        full = self.user.get_full_name()
        return full or self.user.username

    def is_platform_admin(self):
        """Check if this broker is a platform admin."""
        return self.role == self.ROLE_ADMIN

    def is_main_broker(self):
        """Check if this broker is a main broker."""
        return self.role == self.ROLE_MAIN

    def is_sub_broker(self):
        """Check if this broker is a sub broker."""
        return self.role == self.ROLE_SUB

    def get_user_type(self):
        """Get user type for this broker."""
        if self.role == self.ROLE_ADMIN:
            return self.TYPE_ADMIN
        return self.TYPE_BROKER


class Report(models.Model):
    """نظام البلاغات للمنصة."""
    
    # أنواع البلاغات
    TYPE_USER = 'user'
    TYPE_OFFICE = 'office'
    TYPE_COMMENT = 'comment'
    TYPE_TECHNICAL = 'technical'
    
    TYPE_CHOICES = [
        (TYPE_USER, 'بلاغ على مستخدم'),
        (TYPE_OFFICE, 'بلاغ على مكتب عقاري'),
        (TYPE_COMMENT, 'بلاغ على تعليق أو مراجعة'),
        (TYPE_TECHNICAL, 'بلاغ تقني'),
    ]
    
    # أسباب بلاغ المستخدم
    REASON_USER_IMPERSONATION = 'impersonation'
    REASON_USER_ABUSE = 'abuse'
    REASON_USER_SCAM = 'scam'
    REASON_USER_MISINFO = 'misinfo'
    REASON_USER_FAKE = 'fake'
    REASON_USER_OTHER = 'other'
    
    USER_REASON_CHOICES = [
        (REASON_USER_IMPERSONATION, 'انتحال شخصية'),
        (REASON_USER_ABUSE, 'إساءة في المحادثة'),
        (REASON_USER_SCAM, 'محاولة نصب أو احتيال'),
        (REASON_USER_MISINFO, 'نشر معلومات مضللة'),
        (REASON_USER_FAKE, 'حساب مزيف'),
        (REASON_USER_OTHER, 'أخرى'),
    ]
    
    # أسباب بلاغ المكتب
    REASON_OFFICE_WRONG_INFO = 'wrong_info'
    REASON_OFFICE_UNPROFESSIONAL = 'unprofessional'
    REASON_OFFICE_SCAM = 'scam'
    REASON_OFFICE_NO_AGREEMENT = 'no_agreement'
    REASON_OFFICE_UNLICENSED = 'unlicensed'
    REASON_OFFICE_OTHER = 'other'
    
    OFFICE_REASON_CHOICES = [
        (REASON_OFFICE_WRONG_INFO, 'معلومات غير صحيحة'),
        (REASON_OFFICE_UNPROFESSIONAL, 'تعامل غير مهني'),
        (REASON_OFFICE_SCAM, 'نصب أو احتيال'),
        (REASON_OFFICE_NO_AGREEMENT, 'عدم الالتزام بالاتفاق'),
        (REASON_OFFICE_UNLICENSED, 'مكتب غير مرخص'),
        (REASON_OFFICE_OTHER, 'أخرى'),
    ]
    
    # أسباب بلاغ التعليق
    REASON_COMMENT_ABUSE = 'abuse'
    REASON_COMMENT_MISINFO = 'misinfo'
    REASON_COMMENT_SPAM = 'spam'
    REASON_COMMENT_INAPPROPRIATE = 'inappropriate'
    REASON_COMMENT_OTHER = 'other'
    
    COMMENT_REASON_CHOICES = [
        (REASON_COMMENT_ABUSE, 'إساءة أو شتائم'),
        (REASON_COMMENT_MISINFO, 'معلومات مضللة'),
        (REASON_COMMENT_SPAM, 'سبام'),
        (REASON_COMMENT_INAPPROPRIATE, 'محتوى غير لائق'),
        (REASON_COMMENT_OTHER, 'أخرى'),
    ]
    
    # أسباب البلاغ التقني
    REASON_TECH_SITE = 'site_issue'
    REASON_TECH_PAGE = 'page_error'
    REASON_TECH_UPLOAD = 'upload_issue'
    REASON_TECH_LOGIN = 'login_issue'
    REASON_TECH_PAYMENT = 'payment_issue'
    REASON_TECH_OTHER = 'other'
    
    TECHNICAL_REASON_CHOICES = [
        (REASON_TECH_SITE, 'مشكلة في الموقع'),
        (REASON_TECH_PAGE, 'خطأ في الصفحة'),
        (REASON_TECH_UPLOAD, 'مشكلة في رفع الصور'),
        (REASON_TECH_LOGIN, 'مشكلة في تسجيل الدخول'),
        (REASON_TECH_PAYMENT, 'مشكلة في الدفع'),
        (REASON_TECH_OTHER, 'أخرى'),
    ]
    
    # حالات البلاغ
    STATUS_NEW = 'new'
    STATUS_REVIEWING = 'reviewing'
    STATUS_WAITING_REPORTER = 'waiting_reporter'
    STATUS_WAITING_REPORTED = 'waiting_reported'
    STATUS_RESOLVED = 'resolved'
    STATUS_REJECTED = 'rejected'
    STATUS_CLOSED = 'closed'
    
    STATUS_CHOICES = [
        (STATUS_NEW, 'جديد'),
        (STATUS_REVIEWING, 'قيد المراجعة'),
        (STATUS_WAITING_REPORTER, 'بانتظار رد المبلغ'),
        (STATUS_WAITING_REPORTED, 'بانتظار رد الطرف الآخر'),
        (STATUS_RESOLVED, 'تم الحل'),
        (STATUS_REJECTED, 'مرفوض'),
        (STATUS_CLOSED, 'مغلق'),
    ]
    
    # الأولويات
    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_URGENT = 'urgent'
    
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'منخفضة'),
        (PRIORITY_MEDIUM, 'متوسطة'),
        (PRIORITY_HIGH, 'عالية'),
        (PRIORITY_URGENT, 'عاجلة'),
    ]
    
    # الإجراءات
    ACTION_DELETE_AD = 'delete_ad'
    ACTION_HIDE_AD = 'hide_ad'
    ACTION_SUSPEND_ACCOUNT = 'suspend_account'
    ACTION_SEND_WARNING = 'send_warning'
    ACTION_REQUEST_EDIT = 'request_edit'
    ACTION_REJECT_REPORT = 'reject_report'
    ACTION_CLOSE_REPORT = 'close_report'
    
    ACTION_CHOICES = [
        (ACTION_DELETE_AD, 'حذف الإعلان'),
        (ACTION_HIDE_AD, 'إخفاء الإعلان مؤقتًا'),
        (ACTION_SUSPEND_ACCOUNT, 'إيقاف الحساب'),
        (ACTION_SEND_WARNING, 'إرسال تحذير'),
        (ACTION_REQUEST_EDIT, 'طلب تعديل البيانات'),
        (ACTION_REJECT_REPORT, 'رفض البلاغ'),
        (ACTION_CLOSE_REPORT, 'إغلاق البلاغ بعد الحل'),
    ]
    
    reporter = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='reports_made',
        verbose_name='المُبلِّغ'
    )
    report_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, verbose_name='نوع البلاغ'
    )
    reason = models.CharField(max_length=50, verbose_name='سبب البلاغ')
    description = models.TextField(verbose_name='وصف المشكلة')
    
    # الكيانات المُبلَّغ عنها
    reported_user = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reports_received', verbose_name='المستخدم المُبلَّغ عنه'
    )
    reported_broker = models.ForeignKey(
        Broker, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reports', verbose_name='الدلال المُبلَّغ عنه'
    )
    reported_office = models.ForeignKey(
        Office, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reports', verbose_name='المكتب المُبلَّغ عنه'
    )
    reported_property = models.ForeignKey(
        Property, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reports', verbose_name='العقار المُبلَّغ عنه'
    )
    reported_comment = models.TextField(
        blank=True, verbose_name='التعليق المُبلَّغ عنه'
    )
    
    # المرفقات
    attachments = models.JSONField(
        default=list, blank=True, verbose_name='المرفقات'
    )
    
    # الحالة والأولوية
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW,
        verbose_name='حالة البلاغ'
    )
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM,
        verbose_name='الأولوية'
    )
    
    # الإدارة
    admin_notes = models.TextField(blank=True, verbose_name='ملاحظات الإدارة')
    assigned_to = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_reports', verbose_name='المسؤول'
    )
    
    # التواريخ
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الحل')
    
    class Meta:
        verbose_name = 'بلاغ'
        verbose_name_plural = 'البلاغات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'بلاغ #{self.id} - {self.get_report_type_display()}'
    
    def get_reason_display(self):
        """Get display text for reason based on report type."""
        if self.report_type == self.TYPE_USER:
            return dict(self.USER_REASON_CHOICES).get(self.reason, self.reason)
        elif self.report_type == self.TYPE_OFFICE:
            return dict(self.OFFICE_REASON_CHOICES).get(self.reason, self.reason)
        elif self.report_type == self.TYPE_COMMENT:
            return dict(self.COMMENT_REASON_CHOICES).get(self.reason, self.reason)
        elif self.report_type == self.TYPE_TECHNICAL:
            return dict(self.TECHNICAL_REASON_CHOICES).get(self.reason, self.reason)
        return self.reason


class ReportAction(models.Model):
    """سجل الإجراءات على البلاغات."""
    
    report = models.ForeignKey(
        Report, on_delete=models.CASCADE, related_name='actions',
        verbose_name='البلاغ'
    )
    action = models.CharField(
        max_length=50, choices=Report.ACTION_CHOICES,
        verbose_name='الإجراء'
    )
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    performed_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True,
        related_name='report_actions', verbose_name='قام بالإجراء'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإجراء')
    
    class Meta:
        verbose_name = 'إجراء بلاغ'
        verbose_name_plural = 'إجراءات البلاغات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.get_action_display()} - بلاغ #{self.report.id}'


class BrokerJoinRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'قيد المراجعة'),
        (STATUS_APPROVED, 'مقبول'),
        (STATUS_REJECTED, 'مرفوض'),
    ]

    name = models.CharField(max_length=200, verbose_name='الاسم')
    phone = models.CharField(max_length=20, verbose_name='الهاتف')
    governorate = models.CharField(max_length=100, verbose_name='المحافظة')
    office_name = models.CharField(max_length=200, verbose_name='المكتب العقاري')
    id_card_image = models.ImageField(upload_to='broker_requests/', verbose_name='صورة الهوية')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    notes = models.TextField(blank=True, verbose_name='ملاحظات المتقدم')
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name='الحالة'
    )
    reviewed_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_join_requests', verbose_name='راجع بواسطة'
    )
    review_notes = models.TextField(blank=True, verbose_name='ملاحظات المراجعة')
    created_user = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='join_request', verbose_name='الحساب المُنشأ'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'طلب انضمام دلال'
        verbose_name_plural = 'طلبات انضمام الدلالين'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} - {self.office_name}'


class PropertyLike(models.Model):
    """Model for property likes."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='likes', verbose_name='العقار')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='property_likes', verbose_name='المستخدم')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإعجاب')

    class Meta:
        verbose_name = 'إعجاب'
        verbose_name_plural = 'الإعجابات'
        unique_together = ('property', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} أعجب بـ {self.property.title}'


class PropertySave(models.Model):
    """Model for saved properties."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='saves', verbose_name='العقار')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='property_saves', verbose_name='المستخدم')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الحفظ')

    class Meta:
        verbose_name = 'حفظ'
        verbose_name_plural = 'المحفوظات'
        unique_together = ('property', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} حفظ {self.property.title}'


class PropertyComment(models.Model):
    """Model for property comments."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='comments', verbose_name='العقار')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='property_comments', verbose_name='المستخدم')
    content = models.TextField(verbose_name='محتوى التعليق')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies', verbose_name='رد على')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التعليق')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')

    class Meta:
        verbose_name = 'تعليق'
        verbose_name_plural = 'التعليقات'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username}: {self.content[:50]}...'


class PropertyRating(models.Model):
    """نظام تقييم العقارات"""
    
    RATING_CHOICES = [
        (1, '⭐'),
        (2, '⭐⭐'),
        (3, '⭐⭐⭐'),
        (4, '⭐⭐⭐⭐'),
        (5, '⭐⭐⭐⭐⭐'),
    ]
    
    property_obj = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='ratings', verbose_name='العقار'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='property_ratings', verbose_name='المستخدم'
    )
    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES, verbose_name='التقييم'
    )
    
    # تقييمات مفصلة
    location_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='تقييم الموقع',
        help_text='1-5'
    )
    price_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='تقييم السعر',
        help_text='1-5'
    )
    condition_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='تقييم الحالة',
        help_text='1-5'
    )
    communication_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='تقييم التواصل',
        help_text='1-5'
    )
    
    review = models.TextField(blank=True, verbose_name='مراجعة مفصلة')
    is_verified = models.BooleanField(
        default=False, verbose_name='مراجعة موثقة',
        help_text='هل قام المستخدم بزيارة العقار فعلياً؟'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التقييم')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'تقييم عقار'
        verbose_name_plural = 'تقييمات العقارات'
        unique_together = ('property_obj', 'user')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['property_obj', 'rating']),
            models.Index(fields=['-rating']),
        ]
    
    def __str__(self):
        return f'{self.user.username} - {self.property_obj.display_title} - {self.rating}⭐'
    
    @property
    def average_detailed_rating(self):
        """حساب متوسط التقييمات المفصلة"""
        ratings = [
            self.location_rating, self.price_rating, 
            self.condition_rating, self.communication_rating
        ]
        valid_ratings = [r for r in ratings if r is not None]
        if valid_ratings:
            return sum(valid_ratings) / len(valid_ratings)
        return None
    
    def save(self, *args, **kwargs):
        # التحقق من صحة التقييمات المفصلة
        for field in ['location_rating', 'price_rating', 'condition_rating', 'communication_rating']:
            value = getattr(self, field)
            if value is not None and not 1 <= value <= 5:
                raise ValueError(f'{field} يجب أن يكون بين 1 و 5')
        super().save(*args, **kwargs)


class BrokerChannel(models.Model):
    """قناة الدلال - لعرض جميع عقارات الدلال في مكان واحد"""
    
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_SUSPENDED = 'suspended'
    STATUS_PENDING = 'pending'
    
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'نشط'),
        (STATUS_INACTIVE, 'غير نشط'),
        (STATUS_SUSPENDED, 'موقوف'),
        (STATUS_PENDING, 'بانتظار الموافقة'),
    ]
    
    CHANNEL_TYPE_BASIC = 'basic'
    CHANNEL_TYPE_PREMIUM = 'premium'
    CHANNEL_TYPE_ELITE = 'elite'
    
    CHANNEL_TYPE_CHOICES = [
        (CHANNEL_TYPE_BASIC, 'أساسي'),
        (CHANNEL_TYPE_PREMIUM, 'مميز'),
        (CHANNEL_TYPE_ELITE, 'نخبوي'),
    ]
    
    broker = models.OneToOneField(
        Broker, on_delete=models.CASCADE, related_name='channel', verbose_name='الدلال'
    )
    name = models.CharField(max_length=200, verbose_name='اسم القناة')
    slug = models.SlugField(max_length=250, unique=True, blank=True, null=True, verbose_name='الرابط المختصر')
    description = models.TextField(blank=True, verbose_name='وصف القناة')
    logo = models.ImageField(
        upload_to='channels/logos/', null=True, blank=True, verbose_name='شعار القناة'
    )
    cover_image = models.ImageField(
        upload_to='channels/covers/', null=True, blank=True, verbose_name='صورة الغلاف'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name='الحالة'
    )
    is_verified = models.BooleanField(default=False, verbose_name='موثق')
    channel_type = models.CharField(
        max_length=20, choices=CHANNEL_TYPE_CHOICES, default=CHANNEL_TYPE_BASIC, verbose_name='نوع القناة'
    )
    
    # Stats - Basic
    followers_count = models.PositiveIntegerField(default=0, verbose_name='عدد المتابعين')
    views_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاهدات')
    properties_count = models.PositiveIntegerField(default=0, verbose_name='عدد العقارات')
    
    # Stats - Advanced
    profile_views = models.PositiveIntegerField(default=0, verbose_name='مشاهدات الملف الشخصي')
    contact_clicks = models.PositiveIntegerField(default=0, verbose_name='نقرات التواصل')
    whatsapp_clicks = models.PositiveIntegerField(default=0, verbose_name='نقرات واتساب')
    phone_clicks = models.PositiveIntegerField(default=0, verbose_name='نقرات الهاتف')
    property_inquiries = models.PositiveIntegerField(default=0, verbose_name='استفسارات العقارات')
    shares_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاركات')
    saves_count = models.PositiveIntegerField(default=0, verbose_name='عدد الحفظ')
    
    # Engagement metrics
    engagement_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name='معدل التفاعل')
    average_session_duration = models.PositiveIntegerField(default=0, verbose_name='متوسط مدة الجلسة (ثانية)')
    
    # Rating
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, verbose_name='التقييم')
    rating_count = models.PositiveIntegerField(default=0, verbose_name='عدد التقييمات')
    
    # Social links
    whatsapp = models.CharField(max_length=20, blank=True, verbose_name='واتساب')
    facebook = models.URLField(blank=True, verbose_name='فيسبوك')
    instagram = models.URLField(blank=True, verbose_name='انستغرام')
    telegram = models.CharField(max_length=50, blank=True, verbose_name='تيليجرام')
    youtube = models.URLField(blank=True, verbose_name='يوتيوب')
    tiktok = models.URLField(blank=True, verbose_name='تيك توك')
    
    # Personal Information
    phone = models.CharField(max_length=20, blank=True, verbose_name='رقم الهاتف')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    address = models.TextField(blank=True, verbose_name='العنوان')
    work_area = models.CharField(max_length=200, blank=True, verbose_name='منطقة العمل')
    governorate = models.CharField(max_length=100, choices=IRAQ_GOVERNORATES, blank=True, verbose_name='المحافظة')
    city = models.CharField(max_length=100, blank=True, verbose_name='المدينة')
    office_name = models.CharField(max_length=200, blank=True, verbose_name='المكتب العقاري')
    experience_years = models.IntegerField(null=True, blank=True, verbose_name='سنوات الخبرة')
    specialization = models.CharField(max_length=200, blank=True, verbose_name='التخصص')
    working_hours = models.CharField(max_length=100, blank=True, verbose_name='ساعات العمل')
    languages = models.CharField(max_length=200, blank=True, verbose_name='اللغات')
    about_me = models.TextField(blank=True, verbose_name='عني')
    achievements = models.TextField(blank=True, verbose_name='الإنجازات')
    website = models.URLField(blank=True, verbose_name='الموقع الإلكتروني')
    
    # Online status
    is_online = models.BooleanField(default=False, verbose_name='متصل الآن')
    last_seen = models.DateTimeField(null=True, blank=True, verbose_name='آخر ظهور')
    
    # Stats - Sales and Rentals
    sales_count = models.PositiveIntegerField(default=0, verbose_name='عدد المبيعات')
    rentals_count = models.PositiveIntegerField(default=0, verbose_name='عدد التأجيرات')
    deals_count = models.PositiveIntegerField(default=0, verbose_name='عدد الصفقات')
    clients_count = models.PositiveIntegerField(default=0, verbose_name='عدد العملاء')
    
    # SEO
    meta_title = models.CharField(max_length=70, blank=True, verbose_name='عنوان SEO')
    meta_description = models.CharField(max_length=160, blank=True, verbose_name='وصف SEO')
    keywords = models.CharField(max_length=255, blank=True, verbose_name='كلمات مفتاحية')
    
    # Subscription
    subscription_expires_at = models.DateTimeField(null=True, blank=True, verbose_name='انتهاء الاشتراك')
    is_featured = models.BooleanField(default=False, verbose_name='قناة مميزة')
    featured_until = models.DateTimeField(null=True, blank=True, verbose_name='تمييز حتى')
    
    # Analytics
    last_analytics_update = models.DateTimeField(null=True, blank=True, verbose_name='آخر تحليل')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'قناة دلال'
        verbose_name_plural = 'قنوات الدلالين'
        ordering = ['-is_featured', '-followers_count', '-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status']),
            models.Index(fields=['channel_type']),
            models.Index(fields=['is_verified']),
            models.Index(fields=['-followers_count']),
            models.Index(fields=['-rating']),
        ]
    
    def __str__(self):
        return f'{self.name} - {self.broker.display_name}'
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('broker_channel_detail', kwargs={'pk': self.pk})
    
    @property
    def display_name(self):
        """اسم العرض للقناة"""
        return self.name or f'{self.broker.display_name} - قناة'
    
    @property
    def active_properties_count(self):
        """عدد العقارات النشطة في القناة"""
        return Property.objects.filter(
            broker=self.broker,
            status__in=['ready', 'rent', 'published']
        ).count()
    
    @property
    def ads_count(self):
        """عدد الإعلانات في القناة"""
        return self.active_properties_count
    
    @property
    def is_premium(self):
        """هل القناة مميزة"""
        return self.channel_type in [self.CHANNEL_TYPE_PREMIUM, self.CHANNEL_TYPE_ELITE]
    
    @property
    def is_subscription_active(self):
        """هل الاشتراك نشط"""
        if not self.subscription_expires_at:
            return False
        return self.subscription_expires_at > timezone.now()
    
    @property
    def is_featured_active(self):
        """هل التمييز نشط"""
        if not self.is_featured:
            return False
        if not self.featured_until:
            return True
        return self.featured_until > timezone.now()
    
    def increment_views(self):
        """زيادة عدد المشاهدات"""
        self.views_count += 1
        self.save(update_fields=['views_count'])
    
    def increment_followers(self):
        """زيادة عدد المتابعين"""
        self.followers_count += 1
        self.save(update_fields=['followers_count'])
    
    def decrement_followers(self):
        """تقليل عدد المتابعين"""
        if self.followers_count > 0:
            self.followers_count -= 1
            self.save(update_fields=['followers_count'])
    
    def increment_profile_views(self):
        """زيادة مشاهدات الملف الشخصي"""
        self.profile_views += 1
        self.save(update_fields=['profile_views'])
    
    def increment_contact_clicks(self):
        """زيادة نقرات التواصل"""
        self.contact_clicks += 1
        self.save(update_fields=['contact_clicks'])
    
    def increment_whatsapp_clicks(self):
        """زيادة نقرات واتساب"""
        self.whatsapp_clicks += 1
        self.save(update_fields=['whatsapp_clicks'])
    
    def increment_phone_clicks(self):
        """زيادة نقرات الهاتف"""
        self.phone_clicks += 1
        self.save(update_fields=['phone_clicks'])
    
    def increment_property_inquiries(self):
        """زيادة استفسارات العقارات"""
        self.property_inquiries += 1
        self.save(update_fields=['property_inquiries'])
    
    def increment_shares(self):
        """زيادة المشاركات"""
        self.shares_count += 1
        self.save(update_fields=['shares_count'])
    
    def increment_saves(self):
        """زيادة الحفظ"""
        self.saves_count += 1
        self.save(update_fields=['saves_count'])
    
    def notify_followers(self, title, message, link=None):
        """إرسال إشعار لجميع متابعي القناة"""
        from properties.models import Notification, NotificationRecipient
        
        # إنشاء الإشعار
        notification = Notification.objects.create(
            title=title,
            description=message,
            notification_type='info',
            priority='normal',
            status='sent',
            delivery_type='in_app',
            icon='📢',
            button_link=link or f'/channel/{self.id}/',
        )
        
        # إرسال لجميع المتابعين
        for follow in self.followers.all():
            NotificationRecipient.objects.create(
                notification=notification,
                user=follow.user,
                is_read=False
            )
    
    def update_stats(self):
        """تحديث إحصائيات القناة"""
        self.properties_count = self.active_properties_count
        
        # حساب معدل التفاعل
        total_interactions = self.followers_count + self.shares_count + self.saves_count
        if self.views_count > 0:
            self.engagement_rate = (total_interactions / self.views_count) * 100
        else:
            self.engagement_rate = 0.00
        
        self.save(update_fields=['properties_count', 'engagement_rate'])
        self.last_analytics_update = timezone.now()
    
    def calculate_engagement_rate(self):
        """حساب معدل التفاعل المتقدم"""
        if self.views_count == 0:
            return 0.00
        
        interactions = (
            self.followers_count * 0.1 +
            self.shares_count * 0.3 +
            self.saves_count * 0.2 +
            self.contact_clicks * 0.2 +
            self.property_inquiries * 0.2
        )
        
        return round((interactions / self.views_count) * 100, 2)
    
    def get_weekly_stats(self):
        """الحصول على إحصائيات أسبوعية"""
        week_ago = timezone.now() - timezone.timedelta(days=7)
        
        return {
            'new_followers': self.followers.filter(followed_at__gte=week_ago).count(),
            'new_views': self.views_count,  # يمكن تحسين هذا باستخدام Analytics model
            'new_inquiries': self.property_inquiries,
            'new_shares': self.shares.filter(created_at__gte=week_ago).count(),
        }
    
    def get_monthly_stats(self):
        """الحصول على إحصائيات شهرية"""
        month_ago = timezone.now() - timezone.timedelta(days=30)
        
        return {
            'new_followers': self.followers.filter(followed_at__gte=month_ago).count(),
            'new_views': self.views_count,
            'new_inquiries': self.property_inquiries,
            'new_shares': self.shares.filter(created_at__gte=month_ago).count(),
        }


class ChannelFollow(models.Model):
    """Channel followers"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='channel_follows', verbose_name='المستخدم')
    channel = models.ForeignKey(BrokerChannel, on_delete=models.CASCADE, related_name='followers', verbose_name='القناة')
    followed_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ المتابعة')
    
    class Meta:
        verbose_name = 'متابعة قناة'
        verbose_name_plural = 'متابعات القنوات'
        unique_together = ['user', 'channel']
        ordering = ['-followed_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.channel.name}'


class ChannelSave(models.Model):
    """Saved channels by users"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_channels', verbose_name='المستخدم')
    channel = models.ForeignKey(BrokerChannel, on_delete=models.CASCADE, related_name='saved_by', verbose_name='القناة')
    saved_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الحفظ')
    
    class Meta:
        verbose_name = 'قناة محفوظة'
        verbose_name_plural = 'القنوات المحفوظة'
        unique_together = ['user', 'channel']
        ordering = ['-saved_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.channel.name}'


class BrokerRating(models.Model):
    """نظام تقييم الدلالين"""
    
    RATING_CHOICES = [
        (1, '⭐'),
        (2, '⭐⭐'),
        (3, '⭐⭐⭐'),
        (4, '⭐⭐⭐⭐'),
        (5, '⭐⭐⭐⭐⭐'),
    ]
    
    broker = models.ForeignKey(
        Broker, on_delete=models.CASCADE, related_name='ratings', verbose_name='الدلال'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='broker_ratings', verbose_name='المستخدم'
    )
    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES, verbose_name='التقييم العام'
    )
    
    # تقييمات مفصلة
    professionalism_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='الاحترافية',
        help_text='1-5'
    )
    responsiveness_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='سرعة الرد',
        help_text='1-5'
    )
    knowledge_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='المعرفة بالسوق',
        help_text='1-5'
    )
    honesty_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='الأمانة',
        help_text='1-5'
    )
    
    review = models.TextField(blank=True, verbose_name='مراجعة مفصلة')
    property_dealt = models.ForeignKey(
        Property, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='broker_ratings', verbose_name='العقار المتعامل معه'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التقييم')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'تقييم دلال'
        verbose_name_plural = 'تقييمات الدلالين'
        unique_together = ('broker', 'user')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['broker', 'rating']),
            models.Index(fields=['-rating']),
        ]
    
    def __str__(self):
        return f'{self.user.username} - {self.broker.name} - {self.rating}⭐'
    
    @property
    def average_detailed_rating(self):
        """حساب متوسط التقييمات المفصلة"""
        ratings = [
            self.professionalism_rating, self.responsiveness_rating,
            self.knowledge_rating, self.honesty_rating
        ]
        valid_ratings = [r for r in ratings if r is not None]
        if valid_ratings:
            return sum(valid_ratings) / len(valid_ratings)
        return None


class ChannelRating(models.Model):
    """نظام تقييم قنوات الدلالين"""
    
    RATING_CHOICES = [
        (1, '⭐'),
        (2, '⭐⭐'),
        (3, '⭐⭐⭐'),
        (4, '⭐⭐⭐⭐'),
        (5, '⭐⭐⭐⭐⭐'),
    ]
    
    channel = models.ForeignKey(
        BrokerChannel, on_delete=models.CASCADE, related_name='ratings', verbose_name='القناة'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='channel_ratings', verbose_name='المستخدم'
    )
    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES, verbose_name='التقييم العام'
    )
    
    # تقييمات مفصلة للقناة
    content_quality_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='جودة المحتوى',
        help_text='1-5'
    )
    response_speed_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='سرعة الرد',
        help_text='1-5'
    )
    trust_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='الثقة',
        help_text='1-5'
    )
    variety_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='تنوع العقارات',
        help_text='1-5'
    )
    
    review = models.TextField(blank=True, verbose_name='مراجعة مفصلة')
    is_verified = models.BooleanField(default=False, verbose_name='مراجعة موثقة')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التقييم')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'تقييم قناة'
        verbose_name_plural = 'تقييمات القنوات'
        unique_together = ('channel', 'user')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['channel', 'rating']),
            models.Index(fields=['-rating']),
            models.Index(fields=['is_verified']),
        ]
    
    def __str__(self):
        return f'{self.user.username} - {self.channel.name} - {self.rating}⭐'
    
    @property
    def average_detailed_rating(self):
        """حساب متوسط التقييمات المفصلة"""
        ratings = [
            self.content_quality_rating, self.response_speed_rating,
            self.trust_rating, self.variety_rating
        ]
        valid_ratings = [r for r in ratings if r is not None]
        if valid_ratings:
            return sum(valid_ratings) / len(valid_ratings)
        return None


class ChannelReview(models.Model):
    """مراجعات مفصلة للقنوات"""
    
    channel = models.ForeignKey(
        BrokerChannel, on_delete=models.CASCADE, related_name='reviews', verbose_name='القناة'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='channel_reviews', verbose_name='المستخدم'
    )
    
    title = models.CharField(max_length=200, verbose_name='عنوان المراجعة')
    content = models.TextField(verbose_name='محتوى المراجعة')
    
    # صور المراجعة
    images = models.JSONField(default=list, blank=True, verbose_name='صور المراجعة')
    
    # هل يوصي بالقناة
    would_recommend = models.BooleanField(default=True, verbose_name='يوصي بالقناة')
    
    # التقييم العام
    overall_rating = models.PositiveSmallIntegerField(
        choices=BrokerRating.RATING_CHOICES, verbose_name='التقييم العام'
    )
    
    # الإحصائيات
    helpful_count = models.PositiveIntegerField(default=0, verbose_name='عدد الإعجابات')
    reply_count = models.PositiveIntegerField(default=0, verbose_name='عدد الردود')
    
    # الحالة
    is_approved = models.BooleanField(default=False, verbose_name='موافق عليه')
    is_featured = models.BooleanField(default=False, verbose_name='مراجعة مميزة')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'مراجعة قناة'
        verbose_name_plural = 'مراجعات القنوات'
        ordering = ['-is_featured', '-helpful_count', '-created_at']
        indexes = [
            models.Index(fields=['channel', '-created_at']),
            models.Index(fields=['is_approved']),
            models.Index(fields=['is_featured']),
        ]
    
    def __str__(self):
        return f'{self.title} - {self.channel.name}'
    
    def increment_helpful(self):
        """زيادة عدد الإعجابات"""
        self.helpful_count += 1
        self.save(update_fields=['helpful_count'])
    
    def decrement_helpful(self):
        """تقليل عدد الإعجابات"""
        if self.helpful_count > 0:
            self.helpful_count -= 1
            self.save(update_fields=['helpful_count'])


class ChannelReviewReply(models.Model):
    """ردود على مراجعات القنوات"""
    
    review = models.ForeignKey(
        ChannelReview, on_delete=models.CASCADE, related_name='replies', verbose_name='المراجعة'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='review_replies', verbose_name='المستخدم'
    )
    content = models.TextField(verbose_name='محتوى الرد')
    
    # هل الرد من صاحب القناة
    is_channel_owner = models.BooleanField(default=False, verbose_name='رد من صاحب القناة')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'رد مراجعة'
        verbose_name_plural = 'ردود المراجعات'
        ordering = ['created_at']
    
    def __str__(self):
        return f'رد على {self.review.title}'


class ChannelShare(models.Model):
    """مشاركة القنوات"""
    
    SHARE_PLATFORM_CHOICES = [
        ('whatsapp', 'واتساب'),
        ('facebook', 'فيسبوك'),
        ('twitter', 'تويتر'),
        ('telegram', 'تيليجرام'),
        ('email', 'بريد إلكتروني'),
        ('link', 'نسخ الرابط'),
    ]
    
    channel = models.ForeignKey(
        BrokerChannel, on_delete=models.CASCADE, related_name='shares', verbose_name='القناة'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='channel_shares', verbose_name='المستخدم'
    )
    platform = models.CharField(
        max_length=20, choices=SHARE_PLATFORM_CHOICES, verbose_name='منصة المشاركة'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ المشاركة')
    
    class Meta:
        verbose_name = 'مشاركة قناة'
        verbose_name_plural = 'مشاركات القنوات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['channel', '-created_at']),
            models.Index(fields=['platform']),
        ]
    
    def __str__(self):
        return f'{self.user.username} - {self.channel.name} - {self.get_platform_display()}'


class ChannelNotification(models.Model):
    """إشعارات القنوات"""
    
    NOTIFICATION_TYPE_CHOICES = [
        ('new_property', 'عقار جديد'),
        ('price_drop', 'انخفاض السعر'),
        ('featured_property', 'عقار مميز'),
        ('channel_update', 'تحديث القناة'),
        ('new_review', 'مراجعة جديدة'),
        ('reply_to_review', 'رد على مراجعة'),
        ('milestone', 'إنجاز'),
    ]
    
    channel = models.ForeignKey(
        BrokerChannel, on_delete=models.CASCADE, related_name='notifications', verbose_name='القناة'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='channel_notifications', verbose_name='المستخدم'
    )
    notification_type = models.CharField(
        max_length=30, choices=NOTIFICATION_TYPE_CHOICES, verbose_name='نوع الإشعار'
    )
    title = models.CharField(max_length=200, verbose_name='العنوان')
    message = models.TextField(verbose_name='الرسالة')
    
    # رابط ذو صلة
    link = models.URLField(blank=True, verbose_name='رابط')
    
    # البيانات الإضافية
    metadata = models.JSONField(default=dict, blank=True, verbose_name='بيانات إضافية')
    
    is_read = models.BooleanField(default=False, verbose_name='تمت القراءة')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    
    class Meta:
        verbose_name = 'إشعار قناة'
        verbose_name_plural = 'إشعارات القنوات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['channel', '-created_at']),
            models.Index(fields=['is_read']),
        ]
    
    def __str__(self):
        return f'{self.title} - {self.user.username}'


class ChannelAnalytics(models.Model):
    """إحصائيات متقدمة للقنوات"""
    
    channel = models.OneToOneField(
        BrokerChannel, on_delete=models.CASCADE, related_name='analytics', verbose_name='القناة'
    )
    
    # إحصائيات الزيارات
    daily_views = models.JSONField(default=dict, blank=True, verbose_name='المشاهدات اليومية')
    weekly_views = models.JSONField(default=dict, blank=True, verbose_name='المشاهدات الأسبوعية')
    monthly_views = models.JSONField(default=dict, blank=True, verbose_name='المشاهدات الشهرية')
    
    # إحصائيات المتابعين
    daily_followers = models.JSONField(default=dict, blank=True, verbose_name='المتابعين اليوميين')
    weekly_followers = models.JSONField(default=dict, blank=True, verbose_name='المتابعين الأسبوعيين')
    monthly_followers = models.JSONField(default=dict, blank=True, verbose_name='المتابعين الشهريين')
    
    # إحصائيات التفاعل
    total_shares = models.PositiveIntegerField(default=0, verbose_name='إجمالي المشاركات')
    total_saves = models.PositiveIntegerField(default=0, verbose_name='إجمالي الحفظ')
    total_reviews = models.PositiveIntegerField(default=0, verbose_name='إجمالي المراجعات')
    
    # إحصائيات الأداء
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, verbose_name='متوسط التقييم')
    response_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name='نسبة الرد')
    average_response_time = models.PositiveIntegerField(default=0, verbose_name='متوسط وقت الرد (دقيقة)')
    
    # إحصائيات العقارات
    properties_viewed = models.PositiveIntegerField(default=0, verbose_name='عقارات تمت مشاهدتها')
    properties_contacted = models.PositiveIntegerField(default=0, verbose_name='عقارات تم التواصل بشأنها')
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name='نسبة التحويل')
    
    # التواريخ
    last_updated = models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    
    class Meta:
        verbose_name = 'إحصائيات قناة'
        verbose_name_plural = 'إحصائيات القنوات'
    
    def __str__(self):
        return f'إحصائيات {self.channel.name}'
    
    def update_daily_views(self, date=None):
        """تحديث المشاهدات اليومية"""
        from django.utils import timezone
        if not date:
            date = timezone.now().date()
        date_str = date.isoformat()
        self.daily_views[date_str] = self.daily_views.get(date_str, 0) + 1
        self.save(update_fields=['daily_views', 'last_updated'])
    
    def update_daily_followers(self, date=None):
        """تحديث المتابعين اليوميين"""
        from django.utils import timezone
        if not date:
            date = timezone.now().date()
        date_str = date.isoformat()
        self.daily_followers[date_str] = self.daily_followers.get(date_str, 0) + 1
        self.save(update_fields=['daily_followers', 'last_updated'])
    
    def calculate_conversion_rate(self):
        """حساب نسبة التحويل"""
        if self.properties_viewed > 0:
            self.conversion_rate = (self.properties_contacted / self.properties_viewed) * 100
            self.save(update_fields=['conversion_rate'])


class ChannelMilestone(models.Model):
    """إنجازات القنوات"""
    
    MILESTONE_TYPE_CHOICES = [
        ('followers', 'عدد المتابعين'),
        ('views', 'عدد المشاهدات'),
        ('properties', 'عدد العقارات'),
        ('reviews', 'عدد المراجعات'),
        ('rating', 'التقييم'),
        ('years', 'سنوات النشاط'),
    ]
    
    channel = models.ForeignKey(
        BrokerChannel, on_delete=models.CASCADE, related_name='milestones', verbose_name='القناة'
    )
    milestone_type = models.CharField(
        max_length=20, choices=MILESTONE_TYPE_CHOICES, verbose_name='نوع الإنجاز'
    )
    target_value = models.PositiveIntegerField(verbose_name='القيمة المستهدفة')
    current_value = models.PositiveIntegerField(default=0, verbose_name='القيمة الحالية')
    
    is_achieved = models.BooleanField(default=False, verbose_name='تم تحقيقه')
    achieved_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الإنجاز')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    
    class Meta:
        verbose_name = 'إنجاز قناة'
        verbose_name_plural = 'إنجازات القنوات'
        ordering = ['-achieved_at', '-created_at']
        unique_together = ['channel', 'milestone_type', 'target_value']
    
    def __str__(self):
        status = '✓' if self.is_achieved else '○'
        return f'{status} {self.channel.name} - {self.get_milestone_type_display()}: {self.current_value}/{self.target_value}'
    
    def check_achievement(self):
        """التحقق من تحقيق الإنجاز"""
        if self.current_value >= self.target_value and not self.is_achieved:
            self.is_achieved = True
            from django.utils import timezone
            self.achieved_at = timezone.now()
            self.save(update_fields=['is_achieved', 'achieved_at'])
            
            # إنشاء إشعار للقناة
            ChannelNotification.objects.create(
                channel=self.channel,
                user=self.channel.broker.user,
                notification_type='milestone',
                title=f'🎉 إنجاز جديد!',
                message=f'حققت قناتك إنجازاً جديداً: {self.get_milestone_type_display()} {self.target_value}',
                link=self.channel.get_absolute_url()
            )
            return True
        return False


class TwoFactorAuth(models.Model):
    """نظام المصادقة الثنائية"""
    
    METHOD_CHOICES = [
        ('totp', 'تطبيق المصادقة (TOTP)'),
        ('sms', 'رسالة نصية (SMS)'),
        ('email', 'بريد إلكتروني'),
    ]
    
    user = models.OneToOneField(
        'auth.User', on_delete=models.CASCADE, related_name='two_factor_auth',
        verbose_name='المستخدم'
    )
    method = models.CharField(
        max_length=10, choices=METHOD_CHOICES, default='totp',
        verbose_name='طريقة المصادقة'
    )
    secret_key = models.CharField(
        max_length=32, blank=True, verbose_name='مفتاح سري'
    )
    is_enabled = models.BooleanField(
        default=False, verbose_name='مفعل'
    )
    phone_number = models.CharField(
        max_length=20, blank=True, verbose_name='رقم الهاتف للـ SMS'
    )
    backup_codes = models.JSONField(
        default=list, blank=True, verbose_name='رموز النسخ الاحتياطي'
    )
    last_used = models.DateTimeField(
        null=True, blank=True, verbose_name='آخر استخدام'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'مصادقة ثنائية'
        verbose_name_plural = 'المصادقات الثنائية'
    
    def __str__(self):
        return f'{self.user.username} - {self.get_method_display()}'
    
    def generate_secret_key(self):
        """توليد مفتاح سري جديد"""
        import pyotp
        self.secret_key = pyotp.random_base32()
        self.save()
        return self.secret_key
    
    def generate_backup_codes(self, count=10):
        """توليد رموز النسخ الاحتياطي"""
        import secrets
        self.backup_codes = [
            secrets.token_hex(4).upper() for _ in range(count)
        ]
        self.save()
        return self.backup_codes
    
    def verify_totp(self, token):
        """التحقق من رمز TOTP"""
        import pyotp
        if not self.secret_key:
            return False
        
        totp = pyotp.TOTP(self.secret_key)
        return totp.verify(token, valid_window=1)
    
    def get_qr_code_url(self):
        """الحصول على رابط QR Code"""
        import pyotp
        if not self.secret_key:
            self.generate_secret_key()
        
        totp = pyotp.TOTP(self.secret_key)
        return totp.provisioning_uri(
            name=self.user.email,
            issuer_name='دلال - منصة العقارات'
        )
    
    def use_backup_code(self, code):
        """استخدام رمز النسخ الاحتياطي"""
        if code.upper() in self.backup_codes:
            self.backup_codes.remove(code.upper())
            self.save()
            return True
        return False


class SecurityLog(models.Model):
    """سجل الأمان"""
    
    ACTION_CHOICES = [
        ('login', 'تسجيل دخول'),
        ('login_failed', 'فشل تسجيل الدخول'),
        ('logout', 'تسجيل خروج'),
        ('password_change', 'تغيير كلمة المرور'),
        ('2fa_enabled', 'تفعيل المصادقة الثنائية'),
        ('2fa_disabled', 'تعطيل المصادقة الثنائية'),
        ('2fa_verify', 'التحقق من المصادقة الثنائية'),
        ('password_reset', 'إعادة تعيين كلمة المرور'),
        ('suspicious_activity', 'نشاط مشبوه'),
    ]
    
    user = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='security_logs', verbose_name='المستخدم'
    )
    action = models.CharField(
        max_length=30, choices=ACTION_CHOICES, verbose_name='الإجراء'
    )
    ip_address = models.GenericIPAddressField(
        null=True, blank=True, verbose_name='عنوان IP'
    )
    user_agent = models.TextField(
        blank=True, verbose_name='معلومات المتصفح'
    )
    details = models.JSONField(
        blank=True, null=True, verbose_name='التفاصيل'
    )
    success = models.BooleanField(
        default=True, verbose_name='نجاح'
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='التاريخ'
    )

    class Meta:
        verbose_name = 'سجل أمان'
        verbose_name_plural = 'سجلات الأمان'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_action_display()} - {self.user}'


class DallalGlobalSettings(models.Model):
    """الإعدادات العامة لنظام الدلال"""
    
    is_dallal_system_enabled = models.BooleanField(
        default=True, verbose_name='تفعيل نظام الدلال'
    )
    max_brokers_per_user = models.IntegerField(
        default=1, verbose_name='الحد الأقصى للدلالات لكل مستخدم'
    )
    max_properties_per_dallal = models.IntegerField(
        default=100, verbose_name='الحد الأقصى للعقارات لكل دلال'
    )
    show_dallal_on_homepage = models.BooleanField(
        default=True, verbose_name='عرض الدلال في الصفحة الرئيسية'
    )
    dallal_display_order = models.CharField(
        max_length=20,
        choices=[
            ('premium_first', 'المميز أولاً ثم العادي'),
            ('basic_first', 'العادي أولاً ثم المميز'),
            ('mixed', 'مختلط'),
        ],
        default='premium_first',
        verbose_name='ترتيب ظهور الدلال'
    )
    show_expired_dallal = models.BooleanField(
        default=False, verbose_name='عرض الدلال المنتهي'
    )
    
    class Meta:
        verbose_name = 'إعدادات الدلال العامة'
        verbose_name_plural = 'إعدادات الدلال العامة'

    def __str__(self):
        return 'إعدادات الدلال العامة'

    @classmethod
    def get_settings(cls):
        return cls.objects.first() or cls.objects.create()


class BasicDallalSettings(models.Model):
    """إعدادات الدلال العادي"""
    
    max_properties = models.IntegerField(
        default=20, verbose_name='الحد الأقصى للعقارات'
    )
    duration_days = models.IntegerField(
        default=30, verbose_name='مدة الاشتراك بالأيام'
    )
    auto_renewal = models.BooleanField(
        default=False, verbose_name='التجديد التلقائي'
    )
    impressions_limit = models.IntegerField(
        default=1000, verbose_name='الحد الأقصى للظهور'
    )
    cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='التكلفة'
    )
    is_enabled = models.BooleanField(
        default=True, verbose_name='تفعيل الدلال العادي'
    )
    
    class Meta:
        verbose_name = 'إعدادات الدلال العادي'
        verbose_name_plural = 'إعدادات الدلال العادي'

    def __str__(self):
        return 'إعدادات الدلال العادي'

    @classmethod
    def get_settings(cls):
        return cls.objects.first() or cls.objects.create()


class PremiumDallalSettings(models.Model):
    """إعدادات الدلال المميز"""
    
    max_properties = models.IntegerField(
        default=100, verbose_name='الحد الأقصى للعقارات'
    )
    duration_days = models.IntegerField(
        default=90, verbose_name='مدة الاشتراك بالأيام'
    )
    priority_display = models.BooleanField(
        default=True, verbose_name='أولوية الظهور'
    )
    impressions_limit = models.IntegerField(
        default=5000, verbose_name='الحد الأقصى للظهور'
    )
    cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='التكلفة'
    )
    is_enabled = models.BooleanField(
        default=True, verbose_name='تفعيل الدلال المميز'
    )
    visual_badge = models.BooleanField(
        default=True, verbose_name='تمييز بصري (Badge)'
    )
    highlight_effect = models.BooleanField(
        default=True, verbose_name='تأثير التمييز (Glow)'
    )
    
    class Meta:
        verbose_name = 'إعدادات الدلال المميز'
        verbose_name_plural = 'إعدادات الدلال المميز'

    def __str__(self):
        return 'إعدادات الدلال المميز'

    @classmethod
    def get_settings(cls):
        return cls.objects.first() or cls.objects.create()


class DallalSubscription(models.Model):
    """اشتراك الدلال (عادي أو مميز)"""
    
    SUBSCRIPTION_TYPE_CHOICES = [
        ('basic', 'دلال عادي'),
        ('premium', 'دلال مميز'),
    ]
    
    broker = models.ForeignKey(
        Broker, on_delete=models.CASCADE,
        related_name='dallal_subscriptions',
        verbose_name='الدلال'
    )
    subscription_type = models.CharField(
        max_length=10, choices=SUBSCRIPTION_TYPE_CHOICES,
        verbose_name='نوع الاشتراك'
    )
    start_date = models.DateField(
        verbose_name='تاريخ البداية'
    )
    end_date = models.DateField(
        verbose_name='تاريخ النهاية'
    )
    properties_used = models.IntegerField(
        default=0, verbose_name='العقارات المستخدمة'
    )
    impressions_count = models.IntegerField(
        default=0, verbose_name='عدد الظهور'
    )
    is_active = models.BooleanField(
        default=True, verbose_name='نشط'
    )
    auto_renewal = models.BooleanField(
        default=False, verbose_name='التجديد التلقائي'
    )
    
    class Meta:
        verbose_name = 'اشتراك دلال'
        verbose_name_plural = 'اشتراكات الدلال'
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.broker.display_name} - {self.get_subscription_type_display()}'

    def get_days_remaining(self):
        """الأيام المتبقية"""
        from django.utils import timezone
        if not self.end_date:
            return None
        today = timezone.now().date()
        if self.end_date < today:
            return 0
        delta = self.end_date - today
        return delta.days

    def get_days_elapsed(self):
        """الأيام المنقضية"""
        from django.utils import timezone
        if not self.start_date:
            return None
        today = timezone.now().date()
        if self.start_date > today:
            return 0
        delta = today - self.start_date
        return delta.days

    def get_properties_remaining(self):
        """العقارات المتبقية"""
        if self.subscription_type == 'basic':
            settings = BasicDallalSettings.get_settings()
        else:
            settings = PremiumDallalSettings.get_settings()
        remaining = settings.max_properties - self.properties_used
        return max(0, remaining)

    def is_expired(self):
        """هل الاشتراك منتهي؟"""
        from django.utils import timezone
        if not self.end_date:
            return False
        return timezone.now().date() > self.end_date

    def deactivate_if_expired(self):
        """إيقاف الاشتراك إذا انتهى"""
        if self.is_expired() and self.is_active:
            self.is_active = False
            self.save()


class PropertyDallalAssignment(models.Model):
    """ربط العقار بنوع الدلال"""
    
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE,
        related_name='dallal_assignments',
        verbose_name='العقار'
    )
    dallal_subscription = models.ForeignKey(
        DallalSubscription, on_delete=models.CASCADE,
        related_name='property_assignments',
        verbose_name='اشتراك الدلال'
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True, verbose_name='تاريخ الربط'
    )
    
    class Meta:
        verbose_name = 'ربط عقار بدلال'
        verbose_name_plural='ربط العقارات بالدلال'


class ActivityLog(models.Model):
    """سجل النشاطات لتتبع العمليات"""
    
    ACTION_CHOICES = [
        ('create', 'إنشاء'),
        ('update', 'تعديل'),
        ('delete', 'حذف'),
        ('login', 'تسجيل دخول'),
        ('logout', 'تسجيل خروج'),
        ('view', 'عرض'),
        ('export', 'تصدير'),
        ('import', 'استيراد'),
        ('approve', 'موافقة'),
        ('reject', 'رفض'),
        ('suspend', 'إيقاف'),
        ('activate', 'تفعيل'),
        ('renew', 'تجديد'),
        ('message', 'رسالة'),
        ('notification', 'إشعار'),
    ]
    
    MODEL_CHOICES = [
        ('broker', 'دلال'),
        ('property', 'عقار'),
        ('user', 'مستخدم'),
        ('subscription', 'اشتراك'),
        ('office', 'مكتب'),
        ('system', 'نظام'),
    ]
    
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activities',
        verbose_name='المستخدم'
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name='الإجراء'
    )
    model_type = models.CharField(
        max_length=20,
        choices=MODEL_CHOICES,
        verbose_name='نوع النموذج'
    )
    object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='معرف الكائن'
    )
    object_repr = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='تمثيل الكائن'
    )
    description = models.TextField(
        blank=True,
        verbose_name='الوصف'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='عنوان IP'
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name='معلومات المتصفح'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='بيانات إضافية'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='التاريخ والوقت'
    )
    
    class Meta:
        verbose_name = 'سجل نشاط'
        verbose_name_plural = 'سجلات النشاطات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['model_type', 'object_id']),
        ]
    
    def __str__(self):
        return f'{self.get_action_display()} - {self.model_type}'
    
    @classmethod
    def log(cls, user, action, model_type, object_id=None, object_repr='', description='', ip_address=None, user_agent='', metadata=None):
        """تسجيل نشاط جديد"""
        return cls.objects.create(
            user=user,
            action=action,
            model_type=model_type,
            object_id=object_id,
            object_repr=object_repr,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {}
        )


# ==================== Resort & Tourism Models ====================

def resort_cover_path(instance, filename):
    """Path for resort cover image"""
    return f'resorts/covers/{instance.id}/{filename}'


def resort_logo_path(instance, filename):
    """Path for resort logo"""
    return f'resorts/logos/{instance.id}/{filename}'


def resort_gallery_path(instance, filename):
    """Path for resort gallery images"""
    return f'resorts/gallery/{instance.resort.id}/{filename}'


class Resort(models.Model):
    """المنتجعات والأماكن السياحية"""
    
    RESORT_TYPE_CHOICES = [
        ('resort', 'منتجع سياحي'),
        ('hotel', 'فندق'),
        ('chalet', 'شاليه'),
        ('cabin', 'كوخ'),
        ('camp', 'مخيم سياحي'),
        ('amusement_park', 'مدينة ألعاب'),
        ('park', 'منتزه'),
        ('public_garden', 'حديقة عامة'),
        ('pool', 'مسبح'),
        ('rest_house', 'استراحة'),
        ('tourist_farm', 'مزرعة سياحية'),
        ('tourist_island', 'جزيرة سياحية'),
        ('archaeological_site', 'موقع أثري'),
        ('tourist_restaurant', 'مطعم سياحي'),
        ('tourist_cafe', 'مقهى سياحي'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'بانتظار الموافقة'),
        ('active', 'نشط'),
        ('inactive', 'غير نشط'),
        ('rejected', 'مرفوض'),
        ('suspended', 'موقوف'),
    ]
    
    # Owner - يمكن أن يكون دلال، مكتب، شركة، أو مالك
    broker = models.ForeignKey(
        Broker, on_delete=models.CASCADE, related_name='resorts',
        null=True, blank=True, verbose_name='الدلال'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='resorts',
        null=True, blank=True, verbose_name='المستخدم المالك'
    )
    
    # Basic Information
    name = models.CharField(max_length=200, verbose_name='الاسم')
    slug = models.SlugField(max_length=250, unique=True, blank=True, null=True, verbose_name='الرابط المختصر')
    resort_type = models.CharField(
        max_length=50, choices=RESORT_TYPE_CHOICES, verbose_name='نوع المكان'
    )
    description = models.TextField(verbose_name='الوصف')
    
    # Location
    governorate = models.CharField(max_length=100, blank=True, verbose_name='المحافظة')
    city = models.CharField(max_length=100, blank=True, verbose_name='المدينة')
    district = models.CharField(max_length=100, blank=True, verbose_name='المنطقة')
    full_address = models.TextField(blank=True, verbose_name='العنوان الكامل')
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='خط العرض'
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='خط الطول'
    )
    
    # Contact Information
    phone = models.CharField(max_length=20, blank=True, verbose_name='رقم الهاتف')
    whatsapp = models.CharField(max_length=20, blank=True, verbose_name='واتساب')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    website = models.URLField(blank=True, verbose_name='الموقع الإلكتروني')
    
    # Media
    cover_image = models.ImageField(
        upload_to=resort_cover_path, null=True, blank=True, verbose_name='صورة الغلاف'
    )
    logo = models.ImageField(
        upload_to=resort_logo_path, null=True, blank=True, verbose_name='الشعار'
    )
    video_url = models.URLField(blank=True, verbose_name='رابط الفيديو')
    
    # Working Hours
    working_hours = models.CharField(max_length=100, blank=True, verbose_name='ساعات العمل')
    working_days = models.CharField(max_length=100, blank=True, verbose_name='أيام العمل')
    
    # Pricing
    min_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='أقل سعر'
    )
    max_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='أعلى سعر'
    )
    currency = models.CharField(max_length=10, default='د.ع', verbose_name='العملة')
    advance_booking = models.BooleanField(default=True, verbose_name='الحجز المسبق')
    
    # Status & Verification
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة'
    )
    is_verified = models.BooleanField(default=False, verbose_name='موثق')
    is_featured = models.BooleanField(default=False, verbose_name='مميز')
    featured_until = models.DateTimeField(null=True, blank=True, verbose_name='تمييز حتى')
    
    # Statistics
    views_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاهدات')
    bookings_count = models.PositiveIntegerField(default=0, verbose_name='عدد الحجوزات')
    likes_count = models.PositiveIntegerField(default=0, verbose_name='عدد الإعجابات')
    shares_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاركات')
    reviews_count = models.PositiveIntegerField(default=0, verbose_name='عدد التقييمات')
    
    # Rating
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, verbose_name='التقييم')
    rating_count = models.PositiveIntegerField(default=0, verbose_name='عدد التقييمات')
    
    # SEO
    meta_title = models.CharField(max_length=70, blank=True, verbose_name='عنوان SEO')
    meta_description = models.CharField(max_length=160, blank=True, verbose_name='وصف SEO')
    keywords = models.CharField(max_length=255, blank=True, verbose_name='كلمات مفتاحية')
    
    # Link to HotelPage
    page = models.ForeignKey(
        'HotelPage', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resort_listings', verbose_name='الصفحة'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'منتجع سياحي'
        verbose_name_plural = 'المنتجعات السياحية'
        ordering = ['-is_verified', '-rating', '-created_at']
        indexes = [
            models.Index(fields=['resort_type', '-created_at']),
            models.Index(fields=['governorate', 'city']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['is_verified', '-rating']),
            models.Index(fields=['-rating', '-created_at']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('resort_detail', kwargs={'slug': self.slug})
    
    def increment_views(self):
        self.views_count += 1
        self.save(update_fields=['views_count'])
    
    def increment_bookings(self):
        self.bookings_count += 1
        self.save(update_fields=['bookings_count'])
    
    def increment_likes(self):
        self.likes_count += 1
        self.save(update_fields=['likes_count'])
    
    def increment_shares(self):
        self.shares_count += 1
        self.save(update_fields=['shares_count'])
    
    def update_rating(self):
        reviews = self.reviews.all()
        if reviews.exists():
            avg_rating = reviews.aggregate(models.Avg('rating'))['rating__avg']
            self.rating = round(avg_rating, 2)
            self.rating_count = reviews.count()
            self.save(update_fields=['rating', 'rating_count'])


class ResortGallery(models.Model):
    """صور المنتجع"""
    
    resort = models.ForeignKey(
        Resort, on_delete=models.CASCADE, related_name='gallery', verbose_name='المنتجع'
    )
    image = models.ImageField(upload_to=resort_gallery_path, verbose_name='الصورة')
    caption = models.CharField(max_length=200, blank=True, verbose_name='الوصف')
    is_primary = models.BooleanField(default=False, verbose_name='صورة رئيسية')
    order = models.PositiveIntegerField(default=0, verbose_name='الترتيب')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')
    
    class Meta:
        verbose_name = 'صورة منتجع'
        verbose_name_plural = 'صور المنتجع'
        ordering = ['order', '-created_at']
    
    def __str__(self):
        return f'{self.resort.name} - {self.caption or "صورة"}'


class ResortAmenity(models.Model):
    """مرافق المنتجع"""
    
    AMENITY_CHOICES = [
        ('parking', 'موقف سيارات'),
        ('wifi', 'واي فاي'),
        ('pool', 'مسبح'),
        ('playground', 'ألعاب أطفال'),
        ('restaurant', 'مطعم'),
        ('cafeteria', 'كافتيريا'),
        ('family_seating', 'جلسات عائلية'),
        ('private_seating', 'جلسات خاصة'),
        ('ac', 'تكييف'),
        ('elevator', 'مصعد'),
        ('event_hall', 'قاعة مناسبات'),
        ('conference_hall', 'قاعة مؤتمرات'),
        ('beach', 'شاطئ'),
        ('gym', 'صالة رياضية'),
        ('spa', 'سبا'),
        ('sauna', 'ساونا'),
        ('jacuzzi', 'جاكوزي'),
        ('security', 'أمن وحراسة'),
        ('cctv', 'كاميرات مراقبة'),
        ('generator', 'مولد كهرباء'),
        ('disability_access', 'خدمات لذوي الإعاقة'),
    ]
    
    resort = models.ForeignKey(
        Resort, on_delete=models.CASCADE, related_name='amenities', verbose_name='المنتجع'
    )
    amenity_type = models.CharField(
        max_length=50, choices=AMENITY_CHOICES, verbose_name='نوع المرفق'
    )
    is_available = models.BooleanField(default=True, verbose_name='متوفر')
    description = models.TextField(blank=True, verbose_name='وصف المرفق')
    
    class Meta:
        verbose_name = 'مرفق منتجع'
        verbose_name_plural = 'مرافق المنتجع'
        unique_together = ['resort', 'amenity_type']
    
    def __str__(self):
        return f'{self.resort.name} - {self.get_amenity_type_display()}'


class ResortService(models.Model):
    """خدمات المنتجع"""
    
    SERVICE_CHOICES = [
        ('online_booking', 'الحجز الإلكتروني'),
        ('online_payment', 'الدفع الإلكتروني'),
        ('offers_discounts', 'العروض والخصومات'),
        ('events', 'الفعاليات'),
        ('trips', 'الرحلات'),
        ('hall_rental', 'تأجير القاعات'),
        ('cabin_rental', 'تأجير الأكواخ'),
        ('chalet_rental', 'تأجير الشاليهات'),
    ]
    
    resort = models.ForeignKey(
        Resort, on_delete=models.CASCADE, related_name='services', verbose_name='المنتجع'
    )
    service_type = models.CharField(
        max_length=50, choices=SERVICE_CHOICES, verbose_name='نوع الخدمة'
    )
    is_available = models.BooleanField(default=True, verbose_name='متوفر')
    description = models.TextField(blank=True, verbose_name='وصف الخدمة')
    price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='السعر'
    )
    
    class Meta:
        verbose_name = 'خدمة منتجع'
        verbose_name_plural = 'خدمات المنتجع'
        unique_together = ['resort', 'service_type']
    
    def __str__(self):
        return f'{self.resort.name} - {self.get_service_type_display()}'


class ResortReview(models.Model):
    """تقييمات المنتجع"""
    
    resort = models.ForeignKey(
        Resort, on_delete=models.CASCADE, related_name='reviews', verbose_name='المنتجع'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='resort_reviews', verbose_name='المستخدم'
    )
    rating = models.PositiveIntegerField(verbose_name='التقييم بالنجوم')
    comment = models.TextField(verbose_name='التعليق')
    images = models.JSONField(default=list, blank=True, verbose_name='صور من الزائر')
    is_approved = models.BooleanField(default=False, verbose_name='موافق عليه')
    owner_reply = models.TextField(blank=True, verbose_name='رد المالك')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التقييم')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'تقييم منتجع'
        verbose_name_plural = 'تقييمات المنتجع'
        ordering = ['-created_at']
        unique_together = ['resort', 'user']
    
    def __str__(self):
        return f'{self.resort.name} - {self.user.username} - {self.rating}⭐'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.resort.update_rating()


class ResortBooking(models.Model):
    """حجوزات المنتجع"""
    
    STATUS_CHOICES = [
        ('pending', 'بانتظار الموافقة'),
        ('confirmed', 'مؤكد'),
        ('rejected', 'مرفوض'),
        ('cancelled', 'ملغي'),
        ('completed', 'مكتمل'),
    ]
    
    resort = models.ForeignKey(
        Resort, on_delete=models.CASCADE, related_name='bookings', verbose_name='المنتجع'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='resort_bookings', verbose_name='المستخدم'
    )
    check_in = models.DateField(verbose_name='تاريخ الوصول')
    check_out = models.DateField(verbose_name='تاريخ المغادرة')
    guests = models.PositiveIntegerField(default=1, verbose_name='عدد الضيوف')
    total_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='السعر الإجمالي')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة')
    special_requests = models.TextField(blank=True, verbose_name='طلبات خاصة')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الحجز')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'حجز منتجع'
        verbose_name_plural = 'حجوزات المنتجع'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.resort.name} - {self.user.username} - {self.check_in}'
    
    def save(self, *args, **kwargs):
        if self.status == 'confirmed' and not self.pk:
            self.resort.increment_bookings()
        super().save(*args, **kwargs)


class ResortOffer(models.Model):
    """عروض المنتجع"""
    
    resort = models.ForeignKey(
        Resort, on_delete=models.CASCADE, related_name='offers', verbose_name='المنتجع'
    )
    title = models.CharField(max_length=200, verbose_name='عنوان العرض')
    description = models.TextField(verbose_name='وصف العرض')
    discount_percentage = models.PositiveIntegerField(verbose_name='نسبة الخصم')
    original_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='السعر الأصلي')
    discounted_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='السعر بعد الخصم')
    valid_from = models.DateTimeField(verbose_name='صالح من')
    valid_until = models.DateTimeField(verbose_name='صالح حتى')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')
    
    class Meta:
        verbose_name = 'عرض منتجع'
        verbose_name_plural = 'عروض المنتجع'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.resort.name} - {self.title}'
    
    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        return self.is_active and self.valid_from <= now <= self.valid_until


class ResortLike(models.Model):
    """إعجابات المنتجع"""
    
    resort = models.ForeignKey(
        Resort, on_delete=models.CASCADE, related_name='likes', verbose_name='المنتجع'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='resort_likes', verbose_name='المستخدم'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإعجاب')
    
    class Meta:
        verbose_name = 'إعجاب منتجع'
        verbose_name_plural = 'إعجابات المنتجع'
        unique_together = ['resort', 'user']
    
    def __str__(self):
        return f'{self.user.username} - {self.resort.name}'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.resort.increment_likes()


# ==================== Chat System Models ====================

def chat_attachment_path(instance, filename):
    """Path for chat attachments"""
    ext = filename.rsplit('.', 1)[-1].lower()[:10]
    name = uuid.uuid4().hex[:10]
    return os.path.join('chat/attachments/', f'{name}.{ext}')


def chat_image_path(instance, filename):
    """Path for chat images"""
    ext = filename.rsplit('.', 1)[-1].lower()[:10]
    name = uuid.uuid4().hex[:10]
    return os.path.join('chat/images/', f'{name}.{ext}')


def chat_voice_path(instance, filename):
    """Path for chat voice messages"""
    ext = filename.rsplit('.', 1)[-1].lower()[:10]
    name = uuid.uuid4().hex[:10]
    return os.path.join('chat/voice/', f'{name}.{ext}')


class Conversation(models.Model):
    """محادثة بين مستخدمين"""
    
    TYPE_DIRECT = 'direct'
    TYPE_GROUP = 'group'
    TYPE_SUPPORT = 'support'
    
    TYPE_CHOICES = [
        (TYPE_DIRECT, 'محادثة مباشرة'),
        (TYPE_GROUP, 'مجموعة'),
        (TYPE_SUPPORT, 'دعم فني'),
    ]
    
    conversation_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name='معرف المحادثة'
    )
    conversation_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_DIRECT,
        verbose_name='نوع المحادثة'
    )
    participants = models.ManyToManyField(
        User,
        through='ConversationParticipant',
        related_name='conversations',
        verbose_name='المشاركون'
    )
    name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='اسم المحادثة'
    )
    description = models.TextField(
        blank=True,
        verbose_name='الوصف'
    )
    group_avatar = models.ImageField(
        upload_to=chat_image_path,
        blank=True,
        null=True,
        verbose_name='صورة المجموعة'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_conversations',
        verbose_name='أنشأ بواسطة'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='نشط'
    )
    is_archived = models.BooleanField(
        default=False,
        verbose_name='مؤرشف'
    )
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='آخر رسالة'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الإنشاء'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='تاريخ التحديث'
    )
    
    class Meta:
        verbose_name = 'محادثة'
        verbose_name_plural = 'المحادثات'
        ordering = ['-last_message_at', '-created_at']
        indexes = [
            models.Index(fields=['conversation_id']),
            models.Index(fields=['-last_message_at']),
            models.Index(fields=['is_active', '-last_message_at']),
        ]
    
    def __str__(self):
        if self.conversation_type == self.TYPE_DIRECT:
            participants = self.participants.all()
            if len(participants) == 2:
                return f'محادثة بين {participants[0].username} و {participants[1].username}'
        return self.name or f'محادثة {self.conversation_id}'
    
    def get_other_participant(self, user):
        """Get the other participant in a direct conversation"""
        if self.conversation_type != self.TYPE_DIRECT:
            return None
        return self.participants.exclude(id=user.id).first()
    
    def get_last_message(self):
        """Get the last message in the conversation"""
        return self.chat_messages.first()
    
    def mark_as_read_for_user(self, user):
        """Mark all messages as read for a user"""
        unread_messages = self.chat_messages.filter(
            ~Q(read_by=user)
        )
        for message in unread_messages:
            message.mark_as_read(user)
    
    def get_unread_count(self, user):
        """Get unread message count for a user"""
        return self.chat_messages.exclude(
            read_by=user
        ).exclude(
            sender=user
        ).count()


class ConversationParticipant(models.Model):
    """المشارك في المحادثة"""
    
    ROLE_ADMIN = 'admin'
    ROLE_MODERATOR = 'moderator'
    ROLE_MEMBER = 'member'
    
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'مسؤول'),
        (ROLE_MODERATOR, 'مشرف'),
        (ROLE_MEMBER, 'عضو'),
    ]
    
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='participants_info',
        verbose_name='المحادثة'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='conversation_participations',
        verbose_name='المستخدم'
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_MEMBER,
        verbose_name='الدور'
    )
    nickname = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='الاسم المستعار'
    )
    is_muted = models.BooleanField(
        default=False,
        verbose_name='مكتوم'
    )
    is_pinned = models.BooleanField(
        default=False,
        verbose_name='مثبت'
    )
    is_starred = models.BooleanField(
        default=False,
        verbose_name='مميز'
    )
    is_archived = models.BooleanField(
        default=False,
        verbose_name='مؤرشف'
    )
    folder = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='المجلد',
        choices=[
            ('', 'الرئيسي'),
            ('inbox', 'الوارد'),
            ('sent', 'الصادر'),
            ('important', 'مهم'),
            ('spam', 'غير مرغوب'),
        ]
    )
    last_read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='آخر قراءة'
    )
    joined_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الانضمام'
    )
    
    class Meta:
        verbose_name = 'مشارك في المحادثة'
        verbose_name_plural = 'المشاركون في المحادثات'
        unique_together = ['conversation', 'user']
        indexes = [
            models.Index(fields=['conversation', 'user']),
            models.Index(fields=['user', '-last_read_at']),
            models.Index(fields=['is_pinned', '-last_read_at']),
        ]
    
    def __str__(self):
        return f'{self.user.username} في {self.conversation}'


class ChatMessage(models.Model):
    """رسالة المحادثة"""
    
    TYPE_TEXT = 'text'
    TYPE_IMAGE = 'image'
    TYPE_VIDEO = 'video'
    TYPE_AUDIO = 'audio'
    TYPE_FILE = 'file'
    TYPE_LOCATION = 'location'
    TYPE_PROPERTY = 'property'
    TYPE_SYSTEM = 'system'
    
    TYPE_CHOICES = [
        (TYPE_TEXT, 'نص'),
        (TYPE_IMAGE, 'صورة'),
        (TYPE_VIDEO, 'فيديو'),
        (TYPE_AUDIO, 'صوت'),
        (TYPE_FILE, 'ملف'),
        (TYPE_LOCATION, 'موقع'),
        (TYPE_PROPERTY, 'عقار'),
        (TYPE_SYSTEM, 'نظام'),
    ]
    
    message_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name='معرف الرسالة'
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='chat_messages',
        verbose_name='المحادثة'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_chat_messages',
        verbose_name='المرسل'
    )
    message_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_TEXT,
        verbose_name='نوع الرسالة'
    )
    content = models.TextField(
        blank=True,
        verbose_name='المحتوى'
    )
    reply_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name='رد على'
    )
    # Property/Hotel/Resort attachment
    property = models.ForeignKey(
        Property,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_messages',
        verbose_name='العقار'
    )
    hotel = models.ForeignKey(
        Hotel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_messages',
        verbose_name='الفندق'
    )
    resort = models.ForeignKey(
        Resort,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_messages',
        verbose_name='المنتجع'
    )
    is_edited = models.BooleanField(
        default=False,
        verbose_name='معدلة'
    )
    edited_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='تاريخ التعديل'
    )
    is_deleted = models.BooleanField(
        default=False,
        verbose_name='محذوفة'
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='تاريخ الحذف'
    )
    is_pinned = models.BooleanField(
        default=False,
        verbose_name='مثبتة'
    )
    read_by = models.ManyToManyField(
        User,
        through='MessageReadStatus',
        related_name='read_messages',
        verbose_name='مقروءة من قبل'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الإرسال'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='تاريخ التحديث'
    )
    
    class Meta:
        verbose_name = 'رسالة محادثة'
        verbose_name_plural = 'رسائل المحادثات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['message_id']),
            models.Index(fields=['conversation', '-created_at']),
            models.Index(fields=['sender', '-created_at']),
            models.Index(fields=['is_deleted', '-created_at']),
            models.Index(fields=['is_pinned', '-created_at']),
        ]
    
    def __str__(self):
        return f'{self.sender.username if self.sender else "Unknown"}: {self.content[:50] if self.content else self.message_type}'
    
    def mark_as_read(self, user):
        """Mark message as read by user"""
        MessageReadStatus.objects.get_or_create(
            message=self,
            user=user,
            defaults={'read_at': timezone.now()}
        )
    
    def is_read_by_user(self, user):
        """Check if message is read by user"""
        return self.read_by.filter(id=user.id).exists()
    
    def get_read_users(self):
        """Get list of users who read this message"""
        return self.read_by.all()
    
    def edit(self, new_content):
        """Edit message content"""
        self.content = new_content
        self.is_edited = True
        self.edited_at = timezone.now()
        self.save()
    
    def soft_delete(self):
        """Soft delete message"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class MessageReadStatus(models.Model):
    """حالة قراءة الرسالة"""
    
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name='read_statuses',
        verbose_name='الرسالة'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='message_read_statuses',
        verbose_name='المستخدم'
    )
    read_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='وقت القراءة'
    )
    
    class Meta:
        verbose_name = 'حالة قراءة الرسالة'
        verbose_name_plural = 'حالات قراءة الرسائل'
        unique_together = ['message', 'user']
        indexes = [
            models.Index(fields=['message', 'user']),
            models.Index(fields=['user', '-read_at']),
        ]
    
    def __str__(self):
        return f'{self.user.username} قرأ {self.message}'




class ChatSettings(models.Model):
    """إعدادات المحادثة للمستخدم"""
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='chat_settings',
        verbose_name='المستخدم'
    )
    enable_notifications = models.BooleanField(
        default=True,
        verbose_name='تفعيل الإشعارات'
    )
    enable_sound = models.BooleanField(
        default=True,
        verbose_name='تفعيل الصوت'
    )
    enable_typing_indicator = models.BooleanField(
        default=True,
        verbose_name='تفعيل مؤشر الكتابة'
    )
    enable_read_receipts = models.BooleanField(
        default=True,
        verbose_name='تفعيل إيصالات القراءة'
    )
    enable_online_status = models.BooleanField(
        default=True,
        verbose_name='تفعيل حالة الاتصال'
    )
    auto_archive_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='أرشفة تلقائية (أيام)'
    )
    message_retention_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='احتفاظ بالرسائل (أيام)'
    )
    blocked_users = models.ManyToManyField(
        User,
        blank=True,
        related_name='chat_blocked_by_settings',
        verbose_name='المستخدمون المحجوبون'
    )
    muted_conversations = models.ManyToManyField(
        Conversation,
        blank=True,
        related_name='muted_by',
        verbose_name='المحادثات المكتومة'
    )
    theme = models.CharField(
        max_length=20,
        default='light',
        verbose_name='المظهر'
    )
    font_size = models.CharField(
        max_length=10,
        default='medium',
        verbose_name='حجم الخط'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الإنشاء'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='تاريخ التحديث'
    )
    
    class Meta:
        verbose_name = 'إعدادات المحادثة'
        verbose_name_plural = 'إعدادات المحادثات'
    
    def __str__(self):
        return f'إعدادات {self.user.username}'
    
    def block_user(self, user):
        """Block a user using existing BlockedUser model"""
        self.blocked_users.add(user)
        # BlockedUser is already defined in this file
        BlockedUser.objects.get_or_create(
            blocker=self.user,
            blocked=user
        )
    
    def unblock_user(self, user):
        """Unblock a user"""
        self.blocked_users.remove(user)
        BlockedUser.objects.filter(
            blocker=self.user,
            blocked=user
        ).delete()
    
    def mute_conversation(self, conversation):
        """Mute a conversation"""
        self.muted_conversations.add(conversation)
    
    def unmute_conversation(self, conversation):
        """Unmute a conversation"""
        self.muted_conversations.remove(conversation)


class Country(models.Model):
    """Countries for properties outside Iraq"""
    
    name_ar = models.CharField(max_length=100, verbose_name='الاسم بالعربية')
    name_en = models.CharField(max_length=100, verbose_name='الاسم بالإنجليزية')
    flag_emoji = models.CharField(max_length=10, verbose_name='علم الدولة')
    code = models.CharField(max_length=3, unique=True, verbose_name='كود الدولة')
    currency_code = models.CharField(max_length=3, verbose_name='كود العملة')
    currency_name_ar = models.CharField(max_length=50, verbose_name='اسم العملة بالعربية')
    currency_name_en = models.CharField(max_length=50, verbose_name='اسم العملة بالإنجليزية')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    order = models.PositiveIntegerField(default=0, verbose_name='الترتيب')
    
    class Meta:
        verbose_name = 'دولة'
        verbose_name_plural = 'الدول'
        ordering = ['order', 'name_ar']
    
    def __str__(self):
        return f'{self.flag_emoji} {self.name_ar}'


class City(models.Model):
    """Cities for properties outside Iraq"""
    
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='cities', verbose_name='الدولة')
    name_ar = models.CharField(max_length=100, verbose_name='الاسم بالعربية')
    name_en = models.CharField(max_length=100, verbose_name='الاسم بالإنجليزية')
    governorate_state = models.CharField(max_length=100, blank=True, verbose_name='المحافظة/الولاية')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    
    class Meta:
        verbose_name = 'مدينة'
        verbose_name_plural = 'المدن'
        ordering = ['name_ar']
        unique_together = ['country', 'name_ar']
    
    def __str__(self):
        return f'{self.name_ar} - {self.country.name_ar}'


class Area(models.Model):
    """Areas/Districts for properties outside Iraq"""
    
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='areas', verbose_name='المدينة')
    name_ar = models.CharField(max_length=100, verbose_name='الاسم بالعربية')
    name_en = models.CharField(max_length=100, blank=True, verbose_name='الاسم بالإنجليزية')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    
    class Meta:
        verbose_name = 'منطقة'
        verbose_name_plural = 'المناطق'
        ordering = ['name_ar']
        unique_together = ['city', 'name_ar']
    
    def __str__(self):
        return f'{self.name_ar} - {self.city.name_ar}'


# Property types for outside Iraq properties
OUTSIDE_IRAQ_PROPERTY_TYPES = [
    ('apartment', 'شقة'),
    ('villa', 'فيلا'),
    ('palace', 'قصر'),
    ('farm', 'مزرعة'),
    ('land', 'أرض'),
    ('office', 'مكتب'),
    ('store', 'محل تجاري'),
    ('building', 'عمارة'),
    ('warehouse', 'مستودع'),
    ('residential_project', 'مشروع سكني'),
    ('chalet', 'شاليه'),
    ('house', 'بيت'),
]


# ==================== Payment System Models ====================

class PaymentMethod(models.Model):
    """طرق الدفع المتاحة في النظام"""
    
    METHOD_VISA = 'visa'
    METHOD_MASTERCARD = 'mastercard'
    METHOD_PAYPAL = 'paypal'
    METHOD_ZAIN_CASH = 'zain_cash'
    METHOD_QI_CARD = 'qi_card'
    METHOD_ASIA_HAWALA = 'asia_hawala'
    METHOD_BANK_TRANSFER = 'bank_transfer'
    METHOD_CASH = 'cash'
    
    METHOD_CHOICES = [
        (METHOD_VISA, 'Visa'),
        (METHOD_MASTERCARD, 'Mastercard'),
        (METHOD_PAYPAL, 'PayPal'),
        (METHOD_ZAIN_CASH, 'Zain Cash'),
        (METHOD_QI_CARD, 'Qi Card'),
        (METHOD_ASIA_HAWALA, 'Asia Hawala'),
        (METHOD_BANK_TRANSFER, 'التحويل البنكي'),
        (METHOD_CASH, 'نقداً'),
    ]
    
    name = models.CharField(max_length=50, choices=METHOD_CHOICES, unique=True, verbose_name='طريقة الدفع')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    icon = models.CharField(max_length=50, blank=True, verbose_name='أيقونة')
    description = models.TextField(blank=True, verbose_name='الوصف')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'طريقة دفع'
        verbose_name_plural = 'طرق الدفع'
        ordering = ['name']
    
    def __str__(self):
        return self.get_name_display()


class PropertyPayment(models.Model):
    """مدفوعات نشر العقارات"""
    
    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_REFUNDED = 'refunded'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'قيد الانتظار'),
        (STATUS_COMPLETED, 'مكتمل'),
        (STATUS_FAILED, 'فشل'),
        (STATUS_REFUNDED, 'مسترد'),
    ]
    
    PUBLICATION_TYPE_NORMAL = 'normal'
    PUBLICATION_TYPE_FEATURED = 'featured'
    
    PUBLICATION_TYPE_CHOICES = [
        (PUBLICATION_TYPE_NORMAL, 'نشر عادي'),
        (PUBLICATION_TYPE_FEATURED, 'نشر مميز'),
    ]
    
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='payments', verbose_name='العقار'
    )
    broker = models.ForeignKey(
        Broker, on_delete=models.CASCADE, related_name='property_payments', verbose_name='الدلال'
    )
    payment_method = models.ForeignKey(
        PaymentMethod, on_delete=models.SET_NULL, null=True, verbose_name='طريقة الدفع'
    )
    
    # Publication details
    publication_type = models.CharField(
        max_length=20, choices=PUBLICATION_TYPE_CHOICES, default=PUBLICATION_TYPE_NORMAL,
        verbose_name='نوع النشر'
    )
    days = models.PositiveIntegerField(verbose_name='عدد الأيام')
    daily_price = models.DecimalField(max_digits=10, decimal_places=2, default=50.00, verbose_name='سعر اليوم (د.ع)')
    featured_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, verbose_name='سعر المميز (د.ع)'
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='المبلغ الإجمالي (د.ع)')
    
    # Payment status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name='الحالة')
    transaction_id = models.CharField(max_length=200, blank=True, verbose_name='رقم العملية')
    payment_proof = models.ImageField(upload_to='payment_proofs/', null=True, blank=True, verbose_name='إيصال الدفع')
    
    # Dates
    payment_date = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الدفع')
    publication_start_date = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ بدء النشر')
    publication_end_date = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ انتهاء النشر')
    
    # Admin actions
    approved_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_payments', verbose_name='وافق عليه'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الموافقة')
    rejection_reason = models.TextField(blank=True, verbose_name='سبب الرفض')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'دفع نشر عقار'
        verbose_name_plural = 'مدفوعات نشر العقارات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'دفع {self.property.display_title} - {self.total_amount:,} د.ع'
    
    def calculate_total(self):
        """حساب المبلغ الإجمالي"""
        base_amount = self.days * self.daily_price
        if self.publication_type == self.PUBLICATION_TYPE_FEATURED:
            base_amount += self.featured_price
        return base_amount
    
    def save(self, *args, **kwargs):
        if not self.total_amount:
            self.total_amount = self.calculate_total()
        super().save(*args, **kwargs)
    
    def is_publication_active(self):
        """التحقق من أن النشر لا يزال نشطاً"""
        if not self.publication_end_date:
            return False
        from django.utils import timezone
        return timezone.now() < self.publication_end_date
    
    def get_days_remaining(self):
        """حساب الأيام المتبقية للنشر"""
        if not self.publication_end_date:
            return 0
        from django.utils import timezone
        remaining = self.publication_end_date - timezone.now()
        return max(0, remaining.days)


class PropertyNotification(models.Model):
    """إشعارات العقارات"""
    
    TYPE_PROPERTY_ADDED = 'property_added'
    TYPE_PAYMENT_SUCCESS = 'payment_success'
    TYPE_PROPERTY_APPROVED = 'property_approved'
    TYPE_PROPERTY_REJECTED = 'property_rejected'
    TYPE_PUBLICATION_EXPIRING = 'publication_expiring'
    TYPE_PUBLICATION_EXPIRED = 'publication_expired'
    TYPE_PUBLICATION_RENEWED = 'publication_renewed'
    
    TYPE_CHOICES = [
        (TYPE_PROPERTY_ADDED, 'إضافة عقار'),
        (TYPE_PAYMENT_SUCCESS, 'نجاح الدفع'),
        (TYPE_PROPERTY_APPROVED, 'قبول العقار'),
        (TYPE_PROPERTY_REJECTED, 'رفض العقار'),
        (TYPE_PUBLICATION_EXPIRING, 'قرب انتهاء النشر'),
        (TYPE_PUBLICATION_EXPIRED, 'انتهاء النشر'),
        (TYPE_PUBLICATION_RENEWED, 'تجديد النشر'),
    ]
    
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='property_notifications', verbose_name='المستخدم')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='notifications', verbose_name='العقار')
    notification_type = models.CharField(max_length=50, choices=TYPE_CHOICES, verbose_name='نوع الإشعار')
    title = models.CharField(max_length=200, verbose_name='العنوان')
    message = models.TextField(verbose_name='الرسالة')
    is_read = models.BooleanField(default=False, verbose_name='تمت القراءة')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'إشعار عقار'
        verbose_name_plural = 'إشعارات العقارات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.title} - {self.user.username}'


# ==================== Admin Chat Model ====================

class AdminChat(models.Model):
    """محادثة بين الدلال والإدارة"""
    
    MESSAGE_TYPE_TEXT = 'text'
    MESSAGE_TYPE_IMAGE = 'image'
    MESSAGE_TYPE_FILE = 'file'
    MESSAGE_TYPE_PAYMENT_PROOF = 'payment_proof'
    
    MESSAGE_TYPE_CHOICES = [
        (MESSAGE_TYPE_TEXT, 'نص'),
        (MESSAGE_TYPE_IMAGE, 'صورة'),
        (MESSAGE_TYPE_FILE, 'ملف'),
        (MESSAGE_TYPE_PAYMENT_PROOF, 'إيصال دفع'),
    ]
    
    broker = models.ForeignKey(Broker, on_delete=models.CASCADE, related_name='admin_chats', verbose_name='الدلال')
    sender = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='sent_admin_chats', verbose_name='المرسل')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default=MESSAGE_TYPE_TEXT, verbose_name='نوع الرسالة')
    content = models.TextField(blank=True, verbose_name='المحتوى')
    file = models.FileField(upload_to='admin_chats/', null=True, blank=True, verbose_name='الملف')
    image = models.ImageField(upload_to='admin_chats/images/', null=True, blank=True, verbose_name='الصورة')
    
    # Read status
    is_read = models.BooleanField(default=False, verbose_name='تمت القراءة')
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='وقت القراءة')
    
    # Subscription request reference
    subscription_request = models.ForeignKey(
        'SubscriptionRequest', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='chat_messages', verbose_name='طلب الاشتراك'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'محادثة إدارة'
        verbose_name_plural = 'محادثات الإدارة'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.sender.username} - {self.broker.display_name}'
    
    def mark_as_read(self):
        """تحديد الرسالة كمقروءة"""
        if not self.is_read:
            self.is_read = True
            from django.utils import timezone
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


# ==================== Subscription Request (Updated) ====================

class SubscriptionRequest(models.Model):
    """طلب اشتراك جديد (للمحادثة مع الإدارة)"""
    
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_NEGOTIATING = 'negotiating'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'قيد الانتظار'),
        (STATUS_APPROVED, 'موافق عليه'),
        (STATUS_REJECTED, 'مرفوض'),
        (STATUS_NEGOTIATING, 'قيد التفاوض'),
    ]
    
    broker = models.ForeignKey(Broker, on_delete=models.CASCADE, related_name='subscription_requests', null=True, blank=True, verbose_name='الدلال')
    requested_plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='requested_by', verbose_name='الخطة المطلوبة'
    )
    custom_plan_name = models.CharField(max_length=200, blank=True, verbose_name='اسم الخطة المخصصة')
    custom_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='السعر المطلوب'
    )
    custom_duration = models.CharField(max_length=50, blank=True, verbose_name='المدة المطلوبة')
    custom_properties_limit = models.PositiveIntegerField(null=True, blank=True, verbose_name='عدد العقارات المطلوب')
    
    message = models.TextField(blank=True, verbose_name='الرسالة')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name='الحالة')
    
    # Admin response
    admin_response = models.TextField(blank=True, verbose_name='رد الإدارة')
    admin_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='السعر المقترح'
    )
    payment_details = models.TextField(blank=True, verbose_name='بيانات الدفع')
    
    # Finalization
    approved_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_subscription_requests', verbose_name='وافق عليه'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الموافقة')
    rejection_reason = models.TextField(blank=True, verbose_name='سبب الرفض')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'طلب اشتراك'
        verbose_name_plural = 'طلبات الاشتراك'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'طلب اشتراك - {self.broker.display_name}'
    
    def approve(self, admin_user, final_price=None):
        """موافقة على الطلب وتفعيل الاشتراك"""
        from django.utils import timezone
        
        self.status = self.STATUS_APPROVED
        self.approved_by = admin_user
        self.approved_at = timezone.now()
        
        if final_price:
            self.admin_price = final_price
        
        self.save()
        
        # Activate broker subscription
        if self.requested_plan:
            self.broker.subscription_plan = self.requested_plan
        else:
            # Create custom plan
            custom_plan = SubscriptionPlan.objects.create(
                name=self.custom_plan_name or 'خطة مخصصة',
                period=self.custom_duration or 'month',
                ads_limit=self.custom_properties_limit or 100,
                price=self.admin_price or self.custom_price or 0,
                price_per_property=50.00,
                color='#FF6B35'
            )
            self.broker.subscription_plan = custom_plan
        
        from datetime import timedelta
        self.broker.subscription_start_date = timezone.now().date()
        
        # Calculate end date based on duration
        duration_days = 30  # Default
        if self.custom_duration:
            if 'شهر' in self.custom_duration:
                duration_days = 30
            elif 'سنة' in self.custom_duration:
                duration_days = 365
            elif '3 أشهر' in self.custom_duration:
                duration_days = 90
            elif '6 أشهر' in self.custom_duration:
                duration_days = 180
            elif '5 سنوات' in self.custom_duration:
                duration_days = 1825
        
        self.broker.subscription_end_date = (timezone.now() + timedelta(days=duration_days)).date()
        self.broker.save()
        
        # Send notification
        PropertyNotification.objects.create(
            user=self.broker.user,
            property=None,
            notification_type=PropertyNotification.TYPE_PROPERTY_APPROVED,
            title='تم قبول طلب الاشتراك',
            message=f'تم قبول طلب اشتراكك. خطة الاشتراك: {self.broker.subscription_plan.name}'
        )




# Signals for automatic stats updates
@receiver(post_save, sender=Broker)
def create_broker_channel(sender, instance, created, **kwargs):
    """Create channel automatically when broker is created"""
    if created:
        channel_name = f'قناة {instance.display_name}'
        
        BrokerChannel.objects.create(
            broker=instance,
            name=channel_name,
            description=f'قناة {instance.display_name} للعقارات'
        )


@receiver(post_save, sender=Broker)
def create_broker_stats(sender, instance, created, **kwargs):
    """Create individual stats when a broker is created"""
    if created:
        BrokerIndividualStats.objects.get_or_create(broker=instance)


@receiver(post_save, sender=Property)
def update_property_stats(sender, instance, created, **kwargs):
    """Update broker stats when a property is added/modified"""
    if created and instance.owner:
        try:
            broker = Broker.objects.get(user=instance.owner)
            stats, _ = BrokerIndividualStats.objects.get_or_create(broker=broker)
            stats.properties_added += 1
            stats.last_property_added = timezone.now()
            stats.save()
        except Broker.DoesNotExist:
            pass


@receiver(post_delete, sender=Property)
def update_property_delete_stats(sender, instance, **kwargs):
    """Update broker stats when a property is deleted"""
    if instance.owner:
        try:
            broker = Broker.objects.get(user=instance.owner)
            stats, _ = BrokerIndividualStats.objects.get_or_create(broker=broker)
            stats.properties_deleted += 1
            stats.save()
        except Broker.DoesNotExist:
            pass


class OutsideProperty(models.Model):
    """نموذج للعقارات خارج العراق"""
    
    property = models.OneToOneField(
        Property, on_delete=models.CASCADE, related_name='outside_details',
        verbose_name='العقار'
    )
    
    # Location details for outside Iraq
    state_province = models.CharField(max_length=100, blank=True, null=True, verbose_name='الولاية أو المحافظة')
    local_currency = models.CharField(max_length=3, blank=True, null=True, verbose_name='العملة المحلية')
    
    # Financial details
    taxes = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='الضرائب')
    registration_fees = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='رسوم التسجيل')
    
    # Ownership laws
    foreign_ownership_laws = models.TextField(blank=True, verbose_name='قوانين التملك للأجانب')
    
    # Additional features
    hoa_fees = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='رسوم جمعية المالكين')
    property_tax = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='ضريبة العقار')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'عقار خارج العراق'
        verbose_name_plural = 'عقارات خارج العراق'
    
    def __str__(self):
        return f'{self.property.display_title} - {self.property.country}'


class PropertyHotel(models.Model):
    """نموذج للفنادق المرتبطة بالعقارات"""
    
    property = models.OneToOneField(
        Property, on_delete=models.CASCADE, related_name='hotel_details',
        verbose_name='العقار'
    )
    
    # Hotel Information
    hotel_name = models.CharField(max_length=200, verbose_name='اسم الفندق')
    star_rating = models.PositiveSmallIntegerField(
        choices=[(i, f'{i} نجوم') for i in range(1, 6)],
        verbose_name='عدد النجوم'
    )
    classification = models.CharField(max_length=50, blank=True, null=True, verbose_name='التصنيف')
    
    # Room Details
    total_rooms = models.PositiveIntegerField(verbose_name='عدد الغرف')
    suites = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='الأجنحة')
    family_rooms = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='الغرف العائلية')
    
    # Pricing
    price_per_night = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='السعر لليلة')
    currency = models.CharField(max_length=3, default='USD', verbose_name='العملة')
    
    # Services
    has_restaurant = models.BooleanField(default=False, verbose_name='مطاعم')
    has_cafe = models.BooleanField(default=False, verbose_name='مقاهي')
    has_pool = models.BooleanField(default=False, verbose_name='مسابح')
    has_gym = models.BooleanField(default=False, verbose_name='نادي رياضي')
    has_spa = models.BooleanField(default=False, verbose_name='سبا')
    has_conference_hall = models.BooleanField(default=False, verbose_name='قاعة مؤتمرات')
    
    # Booking
    direct_booking = models.BooleanField(default=False, verbose_name='الحجز المباشر')
    booking_url = models.URLField(blank=True, verbose_name='رابط الحجز')
    
    # Rating
    overall_rating = models.DecimalField(max_digits=3, decimal_places=1, default=0, verbose_name='التقييم العام')
    review_count = models.PositiveIntegerField(default=0, verbose_name='عدد التقييمات')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'فندق عقاري'
        verbose_name_plural = 'فنادق عقارية'
    
    def __str__(self):
        return f'{self.hotel_name} ({self.get_star_rating_display()})'


class PropertyResort(models.Model):
    """نموذج للمنتجعات والأماكن السياحية المرتبطة بالعقارات"""
    
    RESORT_TYPES = [
        ('resort', 'منتجع'),
        ('chalet', 'شاليه'),
        ('cabin', 'كوخ'),
        ('tourism_farm', 'مزرعة سياحية'),
        ('beach', 'شاطئ'),
        ('rest_house', 'استراحة'),
        ('camp', 'مخيم'),
        ('tourism_city', 'مدينة سياحية'),
    ]
    
    property = models.OneToOneField(
        Property, on_delete=models.CASCADE, related_name='resort_details',
        verbose_name='العقار'
    )
    
    resort_type = models.CharField(max_length=20, choices=RESORT_TYPES, verbose_name='نوع المنتجع')
    resort_name = models.CharField(max_length=200, verbose_name='اسم المنتجع')
    
    # Location
    governorate = models.CharField(max_length=100, blank=True, verbose_name='المحافظة')
    city = models.CharField(max_length=100, blank=True, verbose_name='المدينة')
    district = models.CharField(max_length=100, blank=True, verbose_name='القضاء')
    address = models.TextField(blank=True, verbose_name='العنوان التفصيلي')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='خط العرض')
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='خط الطول')
    
    # Capacity
    max_guests = models.PositiveIntegerField(verbose_name='عدد الأشخاص الأقصى')
    min_guests = models.PositiveSmallIntegerField(default=1, verbose_name='عدد الأشخاص الأدنى')
    max_rooms = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='عدد الغرف')
    
    # Pricing
    price_per_night = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='السعر لليلة')
    price_per_week = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='السعر للأسبوع')
    price_per_month = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='السعر للشهر')
    currency = models.CharField(max_length=3, default='USD', verbose_name='العملة')
    
    # Booking
    min_booking_duration = models.PositiveSmallIntegerField(default=1, verbose_name='مدة الحجز الدنيا (أيام)')
    max_booking_duration = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='مدة الحجز القصوى (أيام)')
    check_in_time = models.TimeField(null=True, blank=True, verbose_name='وقت تسجيل الدخول')
    check_out_time = models.TimeField(null=True, blank=True, verbose_name='وقت تسجيل الخروج')
    
    # Services
    has_wifi = models.BooleanField(default=False, verbose_name='واي فاي')
    has_kitchen = models.BooleanField(default=False, verbose_name='مطبخ')
    has_bbq = models.BooleanField(default=False, verbose_name='شواء')
    has_playground = models.BooleanField(default=False, verbose_name='ملعب أطفال')
    has_parking = models.BooleanField(default=False, verbose_name='موقف سيارات')
    has_pool = models.BooleanField(default=False, verbose_name='مسبح')
    has_gym = models.BooleanField(default=False, verbose_name='نادي رياضي')
    has_spa = models.BooleanField(default=False, verbose_name='سبا')
    has_restaurant = models.BooleanField(default=False, verbose_name='مطعم')
    has_ac = models.BooleanField(default=False, verbose_name='تكييف')
    has_heating = models.BooleanField(default=False, verbose_name='تدفئة')
    has_security = models.BooleanField(default=False, verbose_name='أمن وحراسة')
    has_laundry = models.BooleanField(default=False, verbose_name='خدمة غسيل')
    has_room_service = models.BooleanField(default=False, verbose_name='خدمة الغرف')
    has_concierge = models.BooleanField(default=False, verbose_name='خدمة الاستقبال')
    
    # Activities
    activities = models.TextField(blank=True, verbose_name='الأنشطة المتاحة')
    
    # Description
    description = models.TextField(blank=True, verbose_name='الوصف')
    rules = models.TextField(blank=True, verbose_name='القواعد والشروط')
    
    # Contact
    phone = models.CharField(max_length=20, blank=True, verbose_name='رقم الهاتف')
    whatsapp = models.CharField(max_length=20, blank=True, verbose_name='رقم الواتساب')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    website = models.URLField(blank=True, verbose_name='الموقع الإلكتروني')
    
    # Rating
    overall_rating = models.DecimalField(max_digits=3, decimal_places=1, default=0, verbose_name='التقييم العام')
    review_count = models.PositiveIntegerField(default=0, verbose_name='عدد التقييمات')
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    featured = models.BooleanField(default=False, verbose_name='مميز')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'منتجع عقاري'
        verbose_name_plural = 'المنتجعات العقارية'
    
    def __str__(self):
        return f'{self.resort_name} ({self.get_resort_type_display()})'


class ChannelPost(models.Model):
    """منشورات القناة - مثل فيسبوك"""
    
    POST_TYPE_CHOICES = [
        ('text', 'نص'),
        ('image', 'صورة'),
        ('video', 'فيديو'),
        ('property', 'عقار'),
        ('ad', 'إعلان'),
    ]
    
    channel = models.ForeignKey(
        BrokerChannel, on_delete=models.CASCADE, related_name='posts', verbose_name='القناة'
    )
    post_type = models.CharField(max_length=20, choices=POST_TYPE_CHOICES, default='text', verbose_name='نوع المنشور')
    
    # Content
    content = models.TextField(verbose_name='المحتوى')
    image = models.ImageField(upload_to='channel_posts/images/', null=True, blank=True, verbose_name='صورة')
    video = models.FileField(upload_to='channel_posts/videos/', null=True, blank=True, verbose_name='فيديو')
    
    # Property reference
    property = models.ForeignKey(
        Property, on_delete=models.SET_NULL, null=True, blank=True, related_name='channel_posts',
        verbose_name='العقار المرتبط'
    )
    
    # Stats
    likes_count = models.PositiveIntegerField(default=0, verbose_name='عدد الإعجابات')
    comments_count = models.PositiveIntegerField(default=0, verbose_name='عدد التعليقات')
    shares_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاركات')
    views_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاهدات')
    
    # Status
    is_published = models.BooleanField(default=True, verbose_name='منشور')
    is_pinned = models.BooleanField(default=False, verbose_name='مثبت')
    is_advertisement = models.BooleanField(default=False, verbose_name='إعلان مدفوع')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ النشر')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'منشور قناة'
        verbose_name_plural = 'منشورات القنوات'
        ordering = ['-is_pinned', '-created_at']
    
    def __str__(self):
        return f'{self.channel.name} - {self.post_type}'
    
    def increment_views(self):
        """زيادة عدد المشاهدات"""
        self.views_count += 1
        self.save(update_fields=['views_count'])


class ChannelVideo(models.Model):
    """فيديوهات قصيرة للقناة - مثل TikTok/Reels"""
    
    channel = models.ForeignKey(
        BrokerChannel, on_delete=models.CASCADE, related_name='videos', verbose_name='القناة'
    )
    
    title = models.CharField(max_length=200, verbose_name='عنوان الفيديو')
    description = models.TextField(blank=True, verbose_name='وصف الفيديو')
    video_file = models.FileField(upload_to='channel_videos/', verbose_name='ملف الفيديو')
    thumbnail = models.ImageField(upload_to='channel_videos/thumbnails/', null=True, blank=True, verbose_name='صورة مصغرة')
    
    # Duration in seconds
    duration = models.PositiveIntegerField(default=0, verbose_name='مدة الفيديو (ثانية)')
    
    # Stats
    views_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاهدات')
    likes_count = models.PositiveIntegerField(default=0, verbose_name='عدد الإعجابات')
    comments_count = models.PositiveIntegerField(default=0, verbose_name='عدد التعليقات')
    shares_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاركات')
    
    # Status
    is_published = models.BooleanField(default=True, verbose_name='منشور')
    is_featured = models.BooleanField(default=False, verbose_name='مميز')
    
    # Tags
    tags = models.CharField(max_length=500, blank=True, verbose_name='الوسوم (مفصولة بفاصلة)')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الرفع')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'فيديو قناة'
        verbose_name_plural = 'فيديوهات القنوات'
        ordering = ['-is_featured', '-created_at']
    
    def __str__(self):
        return f'{self.channel.name} - {self.title}'
    
    def increment_views(self):
        """زيادة عدد المشاهدات"""
        self.views_count += 1
        self.save(update_fields=['views_count'])


class ChannelPostLike(models.Model):
    """إعجابات منشورات القناة"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='channel_post_likes', verbose_name='المستخدم')
    post = models.ForeignKey(ChannelPost, on_delete=models.CASCADE, related_name='likes', verbose_name='المنشور')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإعجاب')
    
    class Meta:
        verbose_name = 'إعجاب منشور'
        verbose_name_plural = 'إعجابات المنشورات'
        unique_together = ['user', 'post']
    
    def __str__(self):
        return f'{self.user.username} - {self.post.id}'


class ChannelVideoLike(models.Model):
    """إعجابات فيديوهات القناة"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='channel_video_likes', verbose_name='المستخدم')
    video = models.ForeignKey(ChannelVideo, on_delete=models.CASCADE, related_name='likes', verbose_name='الفيديو')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإعجاب')
    
    class Meta:
        verbose_name = 'إعجاب فيديو'
        verbose_name_plural = 'إعجابات الفيديوهات'
        unique_together = ['user', 'video']
    
    def __str__(self):
        return f'{self.user.username} - {self.video.title}'


class ChannelPostComment(models.Model):
    """تعليقات منشورات القناة"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='channel_post_comments', verbose_name='المستخدم')
    post = models.ForeignKey(ChannelPost, on_delete=models.CASCADE, related_name='comments', verbose_name='المنشور')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies', verbose_name='الرد على')
    
    content = models.TextField(verbose_name='المحتوى')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التعليق')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'تعليق منشور'
        verbose_name_plural = 'تعليقات المنشورات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.post.id}'


class ChannelVideoComment(models.Model):
    """تعليقات فيديوهات القناة"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='channel_video_comments', verbose_name='المستخدم')
    video = models.ForeignKey(ChannelVideo, on_delete=models.CASCADE, related_name='comments', verbose_name='الفيديو')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies', verbose_name='الرد على')
    
    content = models.TextField(verbose_name='المحتوى')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التعليق')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'تعليق فيديو'
        verbose_name_plural = 'تعليقات الفيديوهات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.video.title}'


class UserWarning(models.Model):
    """نظام إنذارات المستخدمين"""
    
    SEVERITY_CHOICES = [
        ('low', 'منخفض'),
        ('medium', 'متوسط'),
        ('high', 'عالي'),
        ('critical', 'حرج'),
    ]
    
    TYPE_CHOICES = [
        ('spam', 'رسائل مزعجة'),
        ('inappropriate', 'محتوى غير لائق'),
        ('harassment', 'مضايقة'),
        ('fraud', 'احتيال'),
        ('violation', 'انتهاك القواعد'),
        ('other', 'أخرى'),
    ]
    
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='warnings',
        verbose_name='المستخدم'
    )
    issued_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='issued_warnings',
        verbose_name='صادر من'
    )
    warning_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name='نوع الإنذار'
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='medium',
        verbose_name='الشدة'
    )
    reason = models.TextField(
        verbose_name='السبب'
    )
    related_content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='نوع المحتوى المرتبط'
    )
    related_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='معرف المحتوى المرتبط'
    )
    is_acknowledged = models.BooleanField(
        default=False,
        verbose_name='تم الاعتراف'
    )
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='تاريخ الاعتراف'
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='تاريخ الانتهاء'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الإنشاء'
    )
    
    class Meta:
        verbose_name = 'إنذار مستخدم'
        verbose_name_plural = 'إنذارات المستخدمين'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['severity', '-created_at']),
            models.Index(fields=['is_acknowledged']),
        ]
    
    def __str__(self):
        return f'{self.user.username} - {self.get_warning_type_display()}'
    
    def is_active(self):
        """التحقق إذا كان الإنذار لا يزال نشطاً"""
        if self.expires_at:
            from django.utils import timezone
            return timezone.now() < self.expires_at
        return not self.is_acknowledged


class UserSuspension(models.Model):
    """نظام تعطيل المستخدمين"""
    
    REASON_CHOICES = [
        ('violation', 'انتهاك القواعد'),
        ('spam', 'رسائل مزعجة'),
        ('fraud', 'احتيال'),
        ('harassment', 'مضايقة'),
        ('inappropriate', 'محتوى غير لائق'),
        ('multiple_warnings', 'إنذارات متعددة'),
        ('admin_decision', 'قرار إداري'),
        ('other', 'أخرى'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'نشط'),
        ('expired', 'منتهي'),
        ('lifted', 'مرفوع'),
    ]
    
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='suspensions',
        verbose_name='المستخدم'
    )
    suspended_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='suspended_users',
        verbose_name='معطل من قبل'
    )
    reason = models.CharField(
        max_length=20,
        choices=REASON_CHOICES,
        verbose_name='السبب'
    )
    description = models.TextField(
        verbose_name='الوصف'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name='الحالة'
    )
    start_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ البدء'
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='تاريخ الانتهاء'
    )
    lifted_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lifted_suspensions',
        verbose_name='مرفوع من قبل'
    )
    lifted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='تاريخ الرفع'
    )
    lift_reason = models.TextField(
        blank=True,
        verbose_name='سبب الرفع'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='بيانات إضافية'
    )
    
    class Meta:
        verbose_name = 'تعطيل مستخدم'
        verbose_name_plural = 'تعطيلات المستخدمين'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['user', '-start_date']),
            models.Index(fields=['status', '-start_date']),
        ]
    
    def __str__(self):
        return f'{self.user.username} - {self.get_reason_display()}'
    
    def is_active(self):
        """التحقق إذا كان التعطيل لا يزال نشطاً"""
        if self.status != 'active':
            return False
        if self.end_date:
            from django.utils import timezone
            return timezone.now() < self.end_date
        return True
    
    def lift(self, lifted_by, reason=''):
        """رفع التعطيل"""
        from django.utils import timezone
        self.status = 'lifted'
        self.lifted_by = lifted_by
        self.lifted_at = timezone.now()
        self.lift_reason = reason
        self.save()


class UserModerationAction(models.Model):
    """سجل إجراءات المراقبة"""
    
    ACTION_CHOICES = [
        ('warning', 'إنذار'),
        ('suspend', 'تعطيل'),
        ('unsuspend', 'رفع التعطيل'),
        ('delete', 'حذف'),
        ('ban', 'حظر'),
        ('unban', 'رفع الحظر'),
        ('mute', 'كتم'),
        ('unmute', 'رفع الكتم'),
        ('flag', 'إشارة'),
        ('unflag', 'إزالة الإشارة'),
    ]
    
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='moderation_actions',
        verbose_name='المستخدم'
    )
    moderator = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='moderation_actions_taken',
        verbose_name='المشرف'
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name='الإجراء'
    )
    reason = models.TextField(
        verbose_name='السبب'
    )
    related_content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='نوع المحتوى المرتبط'
    )
    related_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='معرف المحتوى المرتبط'
    )
    duration = models.DurationField(
        null=True,
        blank=True,
        verbose_name='المدة'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='عنوان IP'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='بيانات إضافية'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الإجراء'
    )
    
    class Meta:
        verbose_name = 'إجراء مراقبة'
        verbose_name_plural = 'إجراءات المراقبة'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['moderator', '-created_at']),
        ]
    
    def __str__(self):
        return f'{self.user.username} - {self.get_action_display()}'


# ==================== NOTIFICATIONS SYSTEM ====================

class Notification(models.Model):
    """نموذج الإشعارات الرئيسي"""
    
    TYPE_CHOICES = [
        ('info', 'معلومة'),
        ('success', 'نجاح'),
        ('warning', 'تحذير'),
        ('error', 'خطأ'),
        ('property', 'عقار'),
        ('message', 'رسالة'),
        ('rating', 'تقييم'),
        ('subscription', 'اشتراك'),
        ('auction', 'مزاد'),
        ('building', 'بناء'),
        ('system', 'نظام'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'منخفضة'),
        ('normal', 'عادية'),
        ('high', 'عالية'),
        ('urgent', 'عاجلة'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('scheduled', 'مجدولة'),
        ('sent', 'مرسلة'),
        ('failed', 'فشلت'),
    ]
    
    DELIVERY_TYPE_CHOICES = [
        ('in_app', 'داخلي فقط'),
        ('push', 'Push Notification فقط'),
        ('both', 'كلاهما'),
    ]
    
    # Basic Info
    title = models.CharField(max_length=200, verbose_name='العنوان')
    description = models.TextField(default='', verbose_name='الوصف')
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info', verbose_name='النوع')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal', verbose_name='الأولوية')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='الحالة')
    delivery_type = models.CharField(max_length=20, choices=DELIVERY_TYPE_CHOICES, default='in_app', verbose_name='نوع الإرسال')
    
    # Visual Elements
    icon = models.CharField(max_length=50, blank=True, verbose_name='الأيقونة')
    image = models.ImageField(upload_to='notifications/', blank=True, verbose_name='الصورة')
    color = models.CharField(max_length=7, default='#0d9488', verbose_name='اللون')
    
    # Action Elements
    button_text = models.CharField(max_length=50, blank=True, verbose_name='نص الزر')
    button_link = models.URLField(blank=True, verbose_name='رابط الزر')
    
    # Targeting
    target_all_users = models.BooleanField(default=False, verbose_name='جميع المستخدمين')
    target_all_brokers = models.BooleanField(default=False, verbose_name='جميع الدلالين')
    target_all_admins = models.BooleanField(default=False, verbose_name='جميع المشرفين')
    target_office_owners = models.BooleanField(default=False, verbose_name='أصحاب المكاتب')
    target_managers = models.BooleanField(default=False, verbose_name='المدراء')
    target_active_users = models.BooleanField(default=False, verbose_name='المستخدمين النشطين')
    target_new_users = models.BooleanField(default=False, verbose_name='المستخدمين الجدد')
    target_inactive_users = models.BooleanField(default=False, verbose_name='المستخدمين غير النشطين')
    
    # Account Type Targeting
    target_account_type = models.CharField(max_length=50, blank=True, verbose_name='نوع الحساب')
    target_subscription_type = models.CharField(max_length=50, blank=True, verbose_name='نوع الاشتراك')
    target_account_status = models.CharField(max_length=50, blank=True, verbose_name='حالة الحساب')
    target_has_properties = models.BooleanField(null=True, blank=True, verbose_name='لديه عقارات')
    
    # Location Targeting
    target_governorate = models.CharField(max_length=100, blank=True, verbose_name='المحافظة')
    target_city = models.CharField(max_length=100, blank=True, verbose_name='المدينة')
    target_area = models.CharField(max_length=100, blank=True, verbose_name='المنطقة')
    
    # Property Type Targeting
    target_property_type = models.CharField(max_length=50, blank=True, verbose_name='نوع العقار')
    
    # Broker Targeting
    target_premium_brokers = models.BooleanField(default=False, verbose_name='الدلالين المميزين')
    target_min_properties = models.IntegerField(null=True, blank=True, verbose_name='أقل عدد عقارات')
    target_min_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, verbose_name='أقل تقييم')
    
    # Scheduling
    scheduled_for = models.DateTimeField(null=True, blank=True, verbose_name='مجدولة للإرسال في')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='تنتهي في')
    
    # Tags
    tags = models.JSONField(default=list, blank=True, verbose_name='الوسوم')
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True, verbose_name='بيانات إضافية')
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_notifications', verbose_name='أنشأ بواسطة')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الإرسال')
    
    # Related Object
    related_content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='نوع المحتوى المرتبط')
    related_object_id = models.PositiveIntegerField(null=True, blank=True, verbose_name='معرف المحتوى المرتبط')
    
    class Meta:
        verbose_name = 'إشعار'
        verbose_name_plural = 'الإشعارات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['notification_type', '-created_at']),
            models.Index(fields=['priority', '-created_at']),
            models.Index(fields=['scheduled_for']),
        ]
    
    def __str__(self):
        return self.title
    
    def get_recipients_count(self):
        """عدد المستلمين"""
        return self.recipients.count()
    
    def get_read_count(self):
        """عدد المقروءة"""
        return self.recipients.filter(is_read=True).count()
    
    def get_clicked_count(self):
        """عدد النقرات"""
        return self.recipients.filter(is_clicked=True).count()
    
    def mark_as_sent(self):
        """تعليم كمرسلة"""
        from django.utils import timezone
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save()

    @classmethod
    def _normalize_notification_type(cls, notification_type):
        valid_types = {choice[0] for choice in cls.TYPE_CHOICES}
        if notification_type in valid_types:
            return notification_type
        legacy_map = {
            'broker_created': 'system',
            'broker_updated': 'system',
            'broker_deleted': 'system',
            'broker_suspended': 'system',
            'broker_activated': 'system',
            'subscription_expiring': 'subscription',
            'subscription_expired': 'subscription',
            'property_limit_reached': 'property',
            'message_received': 'message',
            'new_property': 'property',
            'property_update': 'property',
            'price_change': 'property',
            'presence': 'info',
            'subscription': 'subscription',
        }
        return legacy_map.get(notification_type, 'info')

    @classmethod
    def create_for_user(cls, user, notification_type, title, message, link='', metadata=None):
        """إنشاء إشعار مباشر لمستخدم واحد."""
        from django.utils import timezone

        notification = cls.objects.create(
            title=title,
            description=message,
            notification_type=cls._normalize_notification_type(notification_type),
            status='sent',
            delivery_type='in_app',
            button_link=link or '',
            metadata=metadata or {},
            sent_at=timezone.now(),
        )
        recipient = NotificationRecipient.objects.create(
            notification=notification,
            user=user,
        )
        return recipient

    @classmethod
    def create(cls, user, notification_type, title, message, link='', metadata=None):
        return cls.create_for_user(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
            metadata=metadata,
        )

    @classmethod
    def create_for_users(cls, users, notification_type, title, message, link='', metadata=None):
        """إنشاء إشعار واحد لعدة مستخدمين."""
        from django.utils import timezone

        notification = cls.objects.create(
            title=title,
            description=message,
            notification_type=cls._normalize_notification_type(notification_type),
            status='sent',
            delivery_type='in_app',
            button_link=link or '',
            metadata=metadata or {},
            sent_at=timezone.now(),
        )
        recipients = [
            NotificationRecipient.objects.create(notification=notification, user=user)
            for user in users
        ]
        return notification, recipients


class NotificationRecipient(models.Model):
    """ربط الإشعارات بالمستلمين"""
    
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='recipients', verbose_name='الإشعار')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name='المستخدم')
    
    is_read = models.BooleanField(default=False, verbose_name='مقروءة')
    is_clicked = models.BooleanField(default=False, verbose_name='تم النقر')
    is_archived = models.BooleanField(default=False, verbose_name='مؤرشفة')
    
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ القراءة')
    clicked_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ النقر')
    archived_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الأرشفة')
    
    # Delivery Tracking
    delivery_status = models.CharField(max_length=20, default='pending', verbose_name='حالة التسليم')
    sent_via_email = models.BooleanField(default=False, verbose_name='أرسلت عبر البريد')
    sent_via_push = models.BooleanField(default=False, verbose_name='أرسلت كإشعار دفع')
    sent_via_sms = models.BooleanField(default=False, verbose_name='أرسلت عبر SMS')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    
    class Meta:
        verbose_name = 'مستلم إشعار'
        verbose_name_plural = 'مستلمو الإشعارات'
        ordering = ['-created_at']
        unique_together = ['notification', 'user']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['notification', 'is_read']),
        ]
    
    def __str__(self):
        return f'{self.user.username} - {self.notification.title}'

    @property
    def title(self):
        return self.notification.title

    @property
    def message(self):
        return self.notification.description

    @property
    def link(self):
        return self.notification.button_link or ''

    @property
    def notification_type(self):
        return self.notification.notification_type

    def mark_as_read(self):
        """تعليم كمقروءة"""
        from django.utils import timezone
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    def mark_as_clicked(self):
        """تعليم كتم النقر"""
        from django.utils import timezone
        if not self.is_clicked:
            self.is_clicked = True
            self.clicked_at = timezone.now()
            self.save()
    
    def archive(self):
        """أرشفة"""
        from django.utils import timezone
        if not self.is_archived:
            self.is_archived = True
            self.archived_at = timezone.now()
            self.save()


class NotificationTemplate(models.Model):
    """قوالب الإشعارات الجاهزة"""
    
    name = models.CharField(max_length=100, verbose_name='اسم القالب')
    title_template = models.CharField(max_length=200, verbose_name='قالب العنوان')
    description_template = models.TextField(verbose_name='قالب الوصف')
    notification_type = models.CharField(max_length=20, choices=Notification.TYPE_CHOICES, default='info', verbose_name='النوع')
    icon = models.CharField(max_length=50, blank=True, verbose_name='الأيقونة')
    
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'قالب إشعار'
        verbose_name_plural = 'قوالب الإشعارات'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class NotificationLog(models.Model):
    """سجل عمليات الإرسال"""
    
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='logs', verbose_name='الإشعار')
    
    # Stats
    total_sent = models.IntegerField(default=0, verbose_name='العدد المرسل')
    total_delivered = models.IntegerField(default=0, verbose_name='العدد المستلم')
    total_read = models.IntegerField(default=0, verbose_name='العدد المقروء')
    total_clicked = models.IntegerField(default=0, verbose_name='عدد النقرات')
    total_failed = models.IntegerField(default=0, verbose_name='عدد الفشل')
    
    # Rates
    delivery_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='نسبة التسليم')
    read_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='نسبة القراءة')
    click_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='نسبة النقر')
    
    # Error Info
    error_message = models.TextField(blank=True, verbose_name='رسالة الخطأ')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    
    class Meta:
        verbose_name = 'سجل إشعار'
        verbose_name_plural = 'سجلات الإشعارات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.notification.title} - {self.total_sent} مرسلة'


# ==================== نظام الفنادق والمنتجعات الجديد ====================

class HotelPage(models.Model):
    """صفحة الفندق أو المنتجع - مثل Facebook Page"""
    
    PAGE_TYPE_CHOICES = [
        ('hotel', 'فندق'),
        ('resort', 'منتجع'),
        ('chalet', 'شاليه'),
        ('cabin', 'كوخ'),
        ('guesthouse', 'بيت ضيافة'),
        ('inn', 'نُزل'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'بانتظار الموافقة'),
        ('active', 'نشط'),
        ('inactive', 'غير نشط'),
        ('suspended', 'موقوف'),
    ]
    
    # Owner
    broker = models.ForeignKey(
        Broker, on_delete=models.CASCADE, related_name='hotel_pages',
        null=True, blank=True, verbose_name='الدلال المالك'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='hotel_pages',
        null=True, blank=True, verbose_name='المستخدم المالك'
    )
    
    # Basic Information
    page_type = models.CharField(max_length=20, choices=PAGE_TYPE_CHOICES, verbose_name='نوع الصفحة')
    name = models.CharField(max_length=200, verbose_name='اسم الصفحة')
    slug = models.SlugField(max_length=250, unique=True, verbose_name='الرابط المختصر')
    description = models.TextField(verbose_name='وصف الصفحة')
    
    # Branding
    cover_image = models.ImageField(upload_to='hotel_pages/covers/', verbose_name='صورة الغلاف')
    logo = models.ImageField(upload_to='hotel_pages/logos/', verbose_name='الشعار')
    
    # Location
    governorate = models.CharField(max_length=50, choices=IRAQ_GOVERNORATES, verbose_name='المحافظة')
    city = models.CharField(max_length=100, verbose_name='المدينة')
    district = models.CharField(max_length=100, blank=True, verbose_name='المنطقة')
    address = models.TextField(verbose_name='العنوان')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='خط العرض')
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='خط الطول')
    
    # Contact
    phone = models.CharField(max_length=20, verbose_name='رقم الهاتف')
    whatsapp = models.CharField(max_length=20, blank=True, verbose_name='واتساب')
    email = models.EmailField(verbose_name='البريد الإلكتروني')
    website = models.URLField(blank=True, verbose_name='الموقع الإلكتروني')
    
    # Working Hours
    working_hours = models.CharField(max_length=100, blank=True, verbose_name='ساعات العمل')
    working_days = models.CharField(max_length=100, blank=True, verbose_name='أيام العمل')
    
    # Statistics
    followers_count = models.PositiveIntegerField(default=0, verbose_name='عدد المتابعين')
    posts_count = models.PositiveIntegerField(default=0, verbose_name='عدد المنشورات')
    rooms_count = models.PositiveIntegerField(default=0, verbose_name='عدد الغرف')
    offers_count = models.PositiveIntegerField(default=0, verbose_name='عدد العروض')
    views_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاهدات')
    
    # Rating
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, verbose_name='التقييم')
    rating_count = models.PositiveIntegerField(default=0, verbose_name='عدد التقييمات')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة')
    is_verified = models.BooleanField(default=False, verbose_name='موثق')
    is_featured = models.BooleanField(default=False, verbose_name='مميز')
    
    # SEO
    meta_title = models.CharField(max_length=70, blank=True, verbose_name='عنوان SEO')
    meta_description = models.CharField(max_length=160, blank=True, verbose_name='وصف SEO')
    keywords = models.CharField(max_length=255, blank=True, verbose_name='كلمات مفتاحية')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'صفحة فندق'
        verbose_name_plural = 'صفحات الفنادق'
        ordering = ['-is_verified', '-followers_count', '-rating']
        indexes = [
            models.Index(fields=['page_type', '-created_at']),
            models.Index(fields=['governorate', 'city']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['is_verified', '-followers_count']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('hotel_page_detail', kwargs={'slug': self.slug})
    
    def increment_followers(self):
        self.followers_count += 1
        self.save(update_fields=['followers_count'])
    
    def decrement_followers(self):
        if self.followers_count > 0:
            self.followers_count -= 1
            self.save(update_fields=['followers_count'])
    
    def increment_posts(self):
        self.posts_count += 1
        self.save(update_fields=['posts_count'])
    
    def increment_views(self):
        self.views_count += 1
        self.save(update_fields=['views_count'])
    
    def update_rating(self):
        ratings = self.ratings.all()
        if ratings.exists():
            avg_rating = ratings.aggregate(models.Avg('rating'))['rating__avg']
            self.rating = round(avg_rating, 2)
            self.rating_count = ratings.count()
            self.save(update_fields=['rating', 'rating_count'])


class HotelPost(models.Model):
    """منشورات صفحة الفندق"""
    
    POST_TYPE_CHOICES = [
        ('listing', 'إعلان'),
        ('offer', 'عرض'),
        ('discount', 'خصم'),
        ('news', 'خبر'),
        ('event', 'مناسبة'),
        ('opening', 'افتتاح'),
        ('announcement', 'إعلان'),
        ('gallery', 'معرض صور'),
        ('video', 'فيديو'),
        ('tour_360', 'جولة 360°'),
        ('promotion', 'ترويج'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('published', 'منشور'),
        ('archived', 'مؤرشف'),
    ]
    
    page = models.ForeignKey(
        HotelPage, on_delete=models.CASCADE, related_name='posts', verbose_name='الصفحة'
    )
    
    # Content
    post_type = models.CharField(max_length=20, choices=POST_TYPE_CHOICES, verbose_name='نوع المنشور')
    title = models.CharField(max_length=200, verbose_name='العنوان')
    content = models.TextField(verbose_name='المحتوى')
    
    # Media
    images = models.JSONField(default=list, verbose_name='الصور')
    video_url = models.URLField(blank=True, verbose_name='رابط الفيديو')
    tour_360_url = models.URLField(blank=True, verbose_name='رابط جولة 360°')
    
    # Pricing (for listings/offers)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='السعر')
    currency = models.CharField(max_length=10, default='د.ع', verbose_name='العملة')
    discount_percentage = models.IntegerField(null=True, blank=True, verbose_name='نسبة الخصم')
    
    # Validity (for offers/discounts)
    valid_from = models.DateTimeField(null=True, blank=True, verbose_name='صالح من')
    valid_until = models.DateTimeField(null=True, blank=True, verbose_name='صالح حتى')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='الحالة')
    is_pinned = models.BooleanField(default=False, verbose_name='مثبت')
    is_featured = models.BooleanField(default=False, verbose_name='مميز')
    
    # Statistics
    views_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاهدات')
    likes_count = models.PositiveIntegerField(default=0, verbose_name='عدد الإعجابات')
    comments_count = models.PositiveIntegerField(default=0, verbose_name='عدد التعليقات')
    shares_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاركات')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ النشر')
    
    class Meta:
        verbose_name = 'منشور فندق'
        verbose_name_plural = 'منشورات الفنادق'
        ordering = ['-is_pinned', '-published_at', '-created_at']
        indexes = [
            models.Index(fields=['page', '-created_at']),
            models.Index(fields=['post_type', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        return f'{self.page.name} - {self.title}'
    
    def publish(self):
        self.status = 'published'
        self.published_at = timezone.now()
        self.save(update_fields=['status', 'published_at'])
        self.page.increment_posts()
    
    def increment_views(self):
        self.views_count += 1
        self.save(update_fields=['views_count'])
    
    def increment_likes(self):
        self.likes_count += 1
        self.save(update_fields=['likes_count'])
    
    def decrement_likes(self):
        if self.likes_count > 0:
            self.likes_count -= 1
            self.save(update_fields=['likes_count'])
    
    def increment_comments(self):
        self.comments_count += 1
        self.save(update_fields=['comments_count'])
    
    def increment_shares(self):
        self.shares_count += 1
        self.save(update_fields=['shares_count'])
    
    def is_valid(self):
        if self.valid_from and self.valid_until:
            now = timezone.now()
            return self.valid_from <= now <= self.valid_until
        return True


class HotelRoom(models.Model):
    """غرف الفندق - كل غرفة تعتبر إعلان مستقل"""
    
    ROOM_TYPE_CHOICES = [
        ('single', 'غرفة مفردة'),
        ('double', 'غرفة مزدوجة'),
        ('triple', 'غرفة ثلاثية'),
        ('family', 'غرفة عائلية'),
        ('suite', 'جناح'),
        ('royal_suite', 'جناح ملكي'),
        ('connecting', 'غرفة متصلة'),
        ('penthouse', 'بنتهاوس'),
    ]
    
    STATUS_CHOICES = [
        ('available', 'متاحة'),
        ('booked', 'محجوزة'),
        ('maintenance', 'تحت الصيانة'),
    ]
    
    page = models.ForeignKey(
        HotelPage, on_delete=models.CASCADE, related_name='rooms', verbose_name='الصفحة'
    )
    
    # Basic Information
    room_type = models.CharField(max_length=20, choices=ROOM_TYPE_CHOICES, verbose_name='نوع الغرفة')
    room_number = models.CharField(max_length=20, verbose_name='رقم الغرفة')
    title = models.CharField(max_length=200, verbose_name='العنوان')
    description = models.TextField(verbose_name='الوصف')
    
    # Capacity
    max_adults = models.IntegerField(default=2, verbose_name='أقصى عدد بالغين')
    max_children = models.IntegerField(default=0, verbose_name='أقصى عدد أطفال')
    max_guests = models.IntegerField(default=2, verbose_name='أقصى عدد ضيوف')
    
    # Pricing
    price_per_night = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='السعر لليلة')
    currency = models.CharField(max_length=10, default='د.ع', verbose_name='العملة')
    
    # Amenities
    amenities = models.JSONField(default=list, verbose_name='المرافق')
    
    # Media
    images = models.JSONField(default=list, verbose_name='الصور')
    video_url = models.URLField(blank=True, verbose_name='رابط الفيديو')
    tour_360_url = models.URLField(blank=True, verbose_name='رابط جولة 360°')
    
    # Size
    area = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='المساحة (متر مربع)')
    floor = models.IntegerField(null=True, blank=True, verbose_name='الطابق')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available', verbose_name='الحالة')
    is_featured = models.BooleanField(default=False, verbose_name='مميز')
    
    # Statistics
    views_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاهدات')
    bookings_count = models.PositiveIntegerField(default=0, verbose_name='عدد الحجوزات')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'غرفة فندق'
        verbose_name_plural = 'غرف الفنادق'
        ordering = ['-is_featured', 'room_number']
        indexes = [
            models.Index(fields=['page', 'room_number']),
            models.Index(fields=['room_type', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        return f'{self.page.name} - {self.title}'
    
    def increment_views(self):
        self.views_count += 1
        self.save(update_fields=['views_count'])
    
    def increment_bookings(self):
        self.bookings_count += 1
        self.save(update_fields=['bookings_count'])


class HotelOffer(models.Model):
    """عروض الفندق"""
    
    OFFER_TYPE_CHOICES = [
        ('discount', 'خصم'),
        ('package', 'باقة'),
        ('promotion', 'ترويج'),
        ('seasonal', 'عرض موسمي'),
        ('last_minute', 'عرض اللحظة الأخيرة'),
        ('early_bird', 'عرض الحجز المبكر'),
    ]
    
    page = models.ForeignKey(
        HotelPage, on_delete=models.CASCADE, related_name='offers', verbose_name='الصفحة'
    )
    
    # Basic Information
    offer_type = models.CharField(max_length=20, choices=OFFER_TYPE_CHOICES, verbose_name='نوع العرض')
    title = models.CharField(max_length=200, verbose_name='العنوان')
    description = models.TextField(verbose_name='الوصف')
    
    # Pricing
    original_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='السعر الأصلي')
    discounted_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='السعر بعد الخصم')
    discount_percentage = models.IntegerField(verbose_name='نسبة الخصم')
    currency = models.CharField(max_length=10, default='د.ع', verbose_name='العملة')
    
    # Validity
    valid_from = models.DateTimeField(verbose_name='صالح من')
    valid_until = models.DateTimeField(verbose_name='صالح حتى')
    
    # Media
    images = models.JSONField(default=list, verbose_name='الصور')
    
    # Terms
    terms_and_conditions = models.TextField(blank=True, verbose_name='الشروط والأحكام')
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    is_featured = models.BooleanField(default=False, verbose_name='مميز')
    
    # Statistics
    views_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاهدات')
    bookings_count = models.PositiveIntegerField(default=0, verbose_name='عدد الحجوزات')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'عرض فندق'
        verbose_name_plural = 'عروض الفنادق'
        ordering = ['-is_featured', '-created_at']
        indexes = [
            models.Index(fields=['page', '-created_at']),
            models.Index(fields=['offer_type', '-created_at']),
            models.Index(fields=['valid_from', 'valid_until']),
        ]
    
    def __str__(self):
        return f'{self.page.name} - {self.title}'
    
    def is_valid(self):
        now = timezone.now()
        return self.is_active and self.valid_from <= now <= self.valid_until
    
    def increment_views(self):
        self.views_count += 1
        self.save(update_fields=['views_count'])
    
    def increment_bookings(self):
        self.bookings_count += 1
        self.save(update_fields=['bookings_count'])


class HotelGallery(models.Model):
    """معرض صور الفندق"""
    
    page = models.ForeignKey(
        HotelPage, on_delete=models.CASCADE, related_name='gallery', verbose_name='الصفحة'
    )
    image = models.ImageField(upload_to='hotel_pages/gallery/', verbose_name='الصورة')
    caption = models.CharField(max_length=200, blank=True, verbose_name='الوصف')
    is_primary = models.BooleanField(default=False, verbose_name='صورة رئيسية')
    order = models.PositiveIntegerField(default=0, verbose_name='الترتيب')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')
    
    class Meta:
        verbose_name = 'صورة فندق'
        verbose_name_plural = 'صور الفندق'
        ordering = ['order', '-created_at']
    
    def __str__(self):
        return f'{self.page.name} - {self.caption or "صورة"}'


class HotelVideo(models.Model):
    """فيديوهات الفندق"""
    
    page = models.ForeignKey(
        HotelPage, on_delete=models.CASCADE, related_name='videos', verbose_name='الصفحة'
    )
    title = models.CharField(max_length=200, verbose_name='العنوان')
    video_url = models.URLField(verbose_name='رابط الفيديو')
    thumbnail = models.ImageField(upload_to='hotel_pages/videos/thumbnails/', blank=True, verbose_name='الصورة المصغرة')
    description = models.TextField(blank=True, verbose_name='الوصف')
    is_primary = models.BooleanField(default=False, verbose_name='رئيسي')
    order = models.PositiveIntegerField(default=0, verbose_name='الترتيب')
    views_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاهدات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')
    
    class Meta:
        verbose_name = 'فيديو فندق'
        verbose_name_plural = 'فيديوهات الفندق'
        ordering = ['order', '-created_at']
    
    def __str__(self):
        return f'{self.page.name} - {self.title}'
    
    def increment_views(self):
        self.views_count += 1
        self.save(update_fields=['views_count'])


class Hotel360(models.Model):
    """جولات 360° للفندق"""
    
    page = models.ForeignKey(
        HotelPage, on_delete=models.CASCADE, related_name='tours_360', verbose_name='الصفحة'
    )
    title = models.CharField(max_length=200, verbose_name='العنوان')
    tour_url = models.URLField(verbose_name='رابط الجولة')
    thumbnail = models.ImageField(upload_to='hotel_pages/360/thumbnails/', blank=True, verbose_name='الصورة المصغرة')
    description = models.TextField(blank=True, verbose_name='الوصف')
    is_primary = models.BooleanField(default=False, verbose_name='رئيسي')
    order = models.PositiveIntegerField(default=0, verbose_name='الترتيب')
    views_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاهدات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')
    
    class Meta:
        verbose_name = 'جولة 360°'
        verbose_name_plural = 'جولات 360°'
        ordering = ['order', '-created_at']
    
    def __str__(self):
        return f'{self.page.name} - {self.title}'
    
    def increment_views(self):
        self.views_count += 1
        self.save(update_fields=['views_count'])


class HotelFollower(models.Model):
    """متابعو صفحة الفندق"""
    
    page = models.ForeignKey(
        HotelPage, on_delete=models.CASCADE, related_name='followers', verbose_name='الصفحة'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='followed_hotels', verbose_name='المستخدم'
    )
    
    followed_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ المتابعة')
    
    class Meta:
        verbose_name = 'متابع فندق'
        verbose_name_plural = 'متابعو الفندق'
        unique_together = ['page', 'user']
        ordering = ['-followed_at']
    
    def __str__(self):
        return f'{self.user.username} يتابع {self.page.name}'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.page.increment_followers()
    
    def delete(self, *args, **kwargs):
        self.page.decrement_followers()
        super().delete(*args, **kwargs)


class HotelComment(models.Model):
    """التعليقات على منشورات الفندق"""
    
    post = models.ForeignKey(
        HotelPost, on_delete=models.CASCADE, related_name='comments', verbose_name='المنشور'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='hotel_comments', verbose_name='المستخدم'
    )
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies', verbose_name='رد على'
    )
    
    content = models.TextField(verbose_name='المحتوى')
    
    is_approved = models.BooleanField(default=True, verbose_name='موافق عليه')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'تعليق فندق'
        verbose_name_plural = 'تعليقات الفندق'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.content[:50]}'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.post.increment_comments()


class HotelRating(models.Model):
    """تقييمات صفحة الفندق"""
    
    page = models.ForeignKey(
        HotelPage, on_delete=models.CASCADE, related_name='ratings', verbose_name='الصفحة'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='hotel_ratings', verbose_name='المستخدم'
    )
    
    rating = models.IntegerField(verbose_name='التقييم', validators=[MinValueValidator(1), MaxValueValidator(5)])
    review = models.TextField(blank=True, verbose_name='المراجعة')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'تقييم فندق'
        verbose_name_plural = 'تقييمات الفندق'
        unique_together = ['page', 'user']
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.rating} نجوم'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.page.update_rating()


class HotelBooking(models.Model):
    """حجوزات الفندق"""
    
    STATUS_CHOICES = [
        ('pending', 'بانتظار التأكيد'),
        ('confirmed', 'مؤكد'),
        ('checked_in', 'تم تسجيل الوصول'),
        ('checked_out', 'تم تسجيل المغادرة'),
        ('cancelled', 'ملغي'),
        ('no_show', 'لم يظهر'),
    ]
    
    page = models.ForeignKey(
        HotelPage, on_delete=models.CASCADE, related_name='bookings', verbose_name='الصفحة'
    )
    room = models.ForeignKey(
        HotelRoom, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings', verbose_name='الغرفة'
    )
    offer = models.ForeignKey(
        HotelOffer, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings', verbose_name='العرض'
    )
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='hotel_bookings', verbose_name='المستخدم'
    )
    
    # Booking Details
    check_in = models.DateField(verbose_name='تاريخ الوصول')
    check_out = models.DateField(verbose_name='تاريخ المغادرة')
    guests = models.IntegerField(default=1, verbose_name='عدد الضيوف')
    
    # Pricing
    total_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='السعر الإجمالي')
    currency = models.CharField(max_length=10, default='د.ع', verbose_name='العملة')
    
    # Contact
    guest_name = models.CharField(max_length=200, verbose_name='اسم الضيف')
    guest_phone = models.CharField(max_length=20, verbose_name='رقم هاتف الضيف')
    guest_email = models.EmailField(blank=True, verbose_name='بريد إلكتروني الضيف')
    
    # Special Requests
    special_requests = models.TextField(blank=True, verbose_name='طلبات خاصة')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة')
    
    # Payment
    is_paid = models.BooleanField(default=False, verbose_name='مدفوع')
    payment_method = models.CharField(max_length=50, blank=True, verbose_name='طريقة الدفع')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الحجز')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'حجز فندق'
        verbose_name_plural = 'حجوزات الفندق'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['page', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['check_in', 'check_out']),
        ]
    
    def __str__(self):
        return f'{self.guest_name} - {self.page.name}'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.room:
            self.room.increment_bookings()
        if self.offer:
            self.offer.increment_bookings()
    
    @property
    def nights(self):
        return (self.check_out - self.check_in).days


# ==================== Service Provider System ====================

class ServiceProviderCategory(models.Model):
    """فئات مقدمي الخدمات"""
    
    CATEGORY_CHOICES = [
        ('construction_contractor', '🏗️ مقاول بناء'),
        ('construction_worker', '👷 عامل بناء'),
        ('brick_mason', '🧱 معلم طابوق'),
        ('concrete_contractor', '🏢 مقاول عظم'),
        ('finishing_contractor', '🏠 مقاول تشطيب'),
        ('painter', '🎨 صباغ'),
        ('carpenter', '🧰 نجار'),
        ('aluminum_blacksmith', '🚪 ألمنيوم وحداد'),
        ('glass', '🪟 زجاج'),
        ('decorations', '🪵 ديكورات'),
        ('electrician', '💡 كهربائي'),
        ('electrical_installation', '🔌 تأسيس كهرباء'),
        ('cameras', '📡 كاميرات مراقبة'),
        ('networks', '🌐 شبكات وإنترنت'),
        ('plumber', '🚿 سباك'),
        ('water_installation', '💧 تأسيس ماء'),
        ('sewage', '🚽 مجاري'),
        ('heating', '🔥 تدفئة'),
        ('cooling', '❄️ تبريد'),
        ('solar_energy', '☀️ طاقة شمسية'),
        ('stone_marble', '🪨 حجر ومرمر'),
        ('ceramic', '🧱 سيراميك'),
        ('gypsum_board', '🪜 جبسن بورد'),
        ('pools', '🏊 مسابح'),
        ('gardens', '🌳 حدائق'),
        ('excavation', '🚜 حفريات'),
        ('material_transport', '🚛 نقل مواد'),
        ('cranes', '🏗️ كرينات'),
        ('cleaning', '🧹 تنظيف'),
        ('interior_design', '🛋️ تصميم داخلي'),
        ('architect', '📐 مهندس معماري'),
        ('civil_engineer', '🏢 مهندس مدني'),
        ('electrical_engineer', '⚡ مهندس كهرباء'),
        ('mechanical_engineer', '🚰 مهندس ميكانيك'),
        ('3d_designer', '🖥️ مصمم ثلاثي الأبعاد'),
    ]
    
    category_id = models.CharField(max_length=50, choices=CATEGORY_CHOICES, unique=True, verbose_name='معرف الفئة')
    name_ar = models.CharField(max_length=100, verbose_name='الاسم بالعربية')
    name_en = models.CharField(max_length=100, verbose_name='الاسم بالإنجليزية')
    icon = models.CharField(max_length=10, verbose_name='الأيقونة')
    description = models.TextField(blank=True, verbose_name='الوصف')
    order = models.IntegerField(default=0, verbose_name='الترتيب')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'فئة مقدم الخدمة'
        verbose_name_plural = 'فئات مقدمي الخدمات'
        ordering = ['order', 'name_ar']
    
    def __str__(self):
        return self.name_ar


class ServiceProviderPage(models.Model):
    """صفحة مقدم الخدمة"""
    
    PAGE_TYPE_CHOICES = [
        ('individual', 'فرد'),
        ('company', 'شركة'),
        ('freelancer', 'عمل حر'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'بانتظار الموافقة'),
        ('active', 'نشط'),
        ('suspended', 'موقوف'),
        ('inactive', 'غير نشط'),
    ]
    
    AVAILABILITY_CHOICES = [
        ('available', 'متاح الآن'),
        ('busy', 'مشغول'),
        ('on_vacation', 'إجازة'),
    ]
    
    # Basic Information
    page_type = models.CharField(max_length=20, choices=PAGE_TYPE_CHOICES, default='individual', verbose_name='نوع الصفحة')
    name = models.CharField(max_length=200, verbose_name='الاسم')
    slug = models.SlugField(max_length=250, unique=True, verbose_name='الرابط المختصر')
    description = models.TextField(verbose_name='نبذة')
    
    # Branding
    profile_image = models.ImageField(upload_to='service_providers/profiles/', blank=True, null=True, verbose_name='الصورة الشخصية')
    cover_image = models.ImageField(upload_to='service_providers/covers/', blank=True, null=True, verbose_name='صورة الغلاف')
    logo = models.ImageField(upload_to='service_providers/logos/', blank=True, null=True, verbose_name='الشعار')
    
    # Professional Info
    category = models.ForeignKey(ServiceProviderCategory, on_delete=models.SET_NULL, null=True, related_name='providers', verbose_name='الفئة')
    sub_categories = models.ManyToManyField(ServiceProviderCategory, blank=True, related_name='sub_providers', verbose_name='الفئات الفرعية')
    years_of_experience = models.IntegerField(default=0, verbose_name='سنوات الخبرة')
    projects_count = models.IntegerField(default=0, verbose_name='عدد المشاريع')
    clients_count = models.IntegerField(default=0, verbose_name='عدد العملاء')
    
    # Location
    governorate = models.CharField(max_length=100, verbose_name='المحافظة')
    city = models.CharField(max_length=100, verbose_name='المدينة')
    working_areas = models.TextField(blank=True, verbose_name='المناطق التي يعمل بها')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='خط العرض')
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='خط الطول')
    
    # Contact
    phone = models.CharField(max_length=20, blank=True, verbose_name='رقم الهاتف')
    whatsapp = models.CharField(max_length=20, blank=True, verbose_name='واتساب')
    telegram = models.CharField(max_length=100, blank=True, verbose_name='تلغرام')
    facebook = models.URLField(blank=True, verbose_name='فيسبوك')
    instagram = models.URLField(blank=True, verbose_name='انستغرام')
    website = models.URLField(blank=True, verbose_name='الموقع الإلكتروني')
    
    # Working Hours
    working_hours = models.TextField(blank=True, verbose_name='أوقات الدوام')
    availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default='available', verbose_name='الحالة')
    
    # Statistics
    views_count = models.IntegerField(default=0, verbose_name='عدد المشاهدات')
    contacts_count = models.IntegerField(default=0, verbose_name='عدد الاتصالات')
    quotes_count = models.IntegerField(default=0, verbose_name='عدد طلبات الأسعار')
    followers_count = models.IntegerField(default=0, verbose_name='عدد المتابعين')
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0, verbose_name='التقييم')
    reviews_count = models.IntegerField(default=0, verbose_name='عدد التقييمات')
    
    # Status & Verification
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة')
    is_verified = models.BooleanField(default=False, verbose_name='موثق')
    verification_date = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ التوثيق')
    
    # Owner
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='service_provider_pages', verbose_name='المستخدم')
    broker = models.ForeignKey('Broker', on_delete=models.SET_NULL, null=True, blank=True, related_name='service_provider_pages', verbose_name='الدلال')
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True, verbose_name='عنوان SEO')
    meta_description = models.TextField(blank=True, verbose_name='وصف SEO')
    meta_keywords = models.CharField(max_length=500, blank=True, verbose_name='كلمات مفتاحية SEO')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'صفحة مقدم الخدمة'
        verbose_name_plural = 'صفحات مقدمي الخدمات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status']),
            models.Index(fields=['category']),
            models.Index(fields=['governorate']),
            models.Index(fields=['rating']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('service_provider_detail', kwargs={'slug': self.slug})


class ServiceProviderWork(models.Model):
    """الأعمال المنجزة لمقدم الخدمة"""
    
    page = models.ForeignKey(ServiceProviderPage, on_delete=models.CASCADE, related_name='works', verbose_name='الصفحة')
    title = models.CharField(max_length=200, verbose_name='العنوان')
    description = models.TextField(verbose_name='الوصف')
    location = models.CharField(max_length=200, blank=True, verbose_name='الموقع')
    
    # Dates & Duration
    execution_date = models.DateField(null=True, blank=True, verbose_name='تاريخ التنفيذ')
    duration = models.CharField(max_length=100, blank=True, verbose_name='المدة')
    
    # Pricing
    estimated_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='السعر التقريبي')
    
    # Before/After
    before_image = models.ImageField(upload_to='service_providers/works/before/', blank=True, null=True, verbose_name='صورة قبل')
    after_image = models.ImageField(upload_to='service_providers/works/after/', blank=True, null=True, verbose_name='صورة بعد')
    
    # Media
    images = models.ManyToManyField('ServiceProviderGallery', blank=True, related_name='works', verbose_name='الصور')
    video = models.ForeignKey('ServiceProviderVideo', on_delete=models.SET_NULL, null=True, blank=True, related_name='works', verbose_name='الفيديو')
    tour_360 = models.ForeignKey('ServiceProvider360', on_delete=models.SET_NULL, null=True, blank=True, related_name='works', verbose_name='جولة 360°')
    
    # Status
    is_featured = models.BooleanField(default=False, verbose_name='مميز')
    status = models.CharField(max_length=20, choices=[('draft', 'مسودة'), ('published', 'منشور')], default='draft', verbose_name='الحالة')
    
    # Statistics
    views_count = models.IntegerField(default=0, verbose_name='عدد المشاهدات')
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0, verbose_name='التقييم')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'عمل منجز'
        verbose_name_plural = 'الأعمال المنجزة'
        ordering = ['-is_featured', '-created_at']
    
    def __str__(self):
        return f'{self.title} - {self.page.name}'


class ServiceProviderService(models.Model):
    """الخدمات المقدمة من مقدم الخدمة"""
    
    page = models.ForeignKey(ServiceProviderPage, on_delete=models.CASCADE, related_name='services', verbose_name='الصفحة')
    name = models.CharField(max_length=200, verbose_name='اسم الخدمة')
    description = models.TextField(blank=True, verbose_name='الوصف')
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='السعر')
    price_unit = models.CharField(max_length=50, blank=True, verbose_name='وحدة السعر')
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    order = models.IntegerField(default=0, verbose_name='الترتيب')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'خدمة مقدمة'
        verbose_name_plural = 'الخدمات المقدمة'
        ordering = ['order', 'name']
    
    def __str__(self):
        return f'{self.name} - {self.page.name}'


class ServiceProviderGallery(models.Model):
    """معرض صور مقدم الخدمة"""
    
    page = models.ForeignKey(ServiceProviderPage, on_delete=models.CASCADE, related_name='gallery', verbose_name='الصفحة')
    image = models.ImageField(upload_to='service_providers/gallery/', verbose_name='الصورة')
    caption = models.CharField(max_length=200, blank=True, verbose_name='الوصف')
    is_primary = models.BooleanField(default=False, verbose_name='صورة رئيسية')
    order = models.IntegerField(default=0, verbose_name='الترتيب')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    
    class Meta:
        verbose_name = 'صورة معرض'
        verbose_name_plural = 'معرض الصور'
        ordering = ['order', '-created_at']
    
    def __str__(self):
        return f'{self.caption or "صورة"} - {self.page.name}'


class ServiceProviderVideo(models.Model):
    """فيديوهات مقدم الخدمة"""
    
    page = models.ForeignKey(ServiceProviderPage, on_delete=models.CASCADE, related_name='videos', verbose_name='الصفحة')
    title = models.CharField(max_length=200, verbose_name='العنوان')
    video_url = models.URLField(verbose_name='رابط الفيديو')
    thumbnail = models.ImageField(upload_to='service_providers/videos/thumbnails/', blank=True, null=True, verbose_name='الصورة المصغرة')
    description = models.TextField(blank=True, verbose_name='الوصف')
    is_primary = models.BooleanField(default=False, verbose_name='فيديو رئيسي')
    order = models.IntegerField(default=0, verbose_name='الترتيب')
    
    # Statistics
    views_count = models.IntegerField(default=0, verbose_name='عدد المشاهدات')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    
    class Meta:
        verbose_name = 'فيديو'
        verbose_name_plural = 'الفيديوهات'
        ordering = ['order', '-created_at']
    
    def __str__(self):
        return f'{self.title} - {self.page.name}'


class ServiceProvider360(models.Model):
    """جولات 360 درجة لمقدم الخدمة"""
    
    page = models.ForeignKey(ServiceProviderPage, on_delete=models.CASCADE, related_name='tours_360', verbose_name='الصفحة')
    title = models.CharField(max_length=200, verbose_name='العنوان')
    tour_url = models.URLField(verbose_name='رابط الجولة')
    thumbnail = models.ImageField(upload_to='service_providers/360/thumbnails/', blank=True, null=True, verbose_name='الصورة المصغرة')
    description = models.TextField(blank=True, verbose_name='الوصف')
    is_primary = models.BooleanField(default=False, verbose_name='جولة رئيسية')
    order = models.IntegerField(default=0, verbose_name='الترتيب')
    
    # Statistics
    views_count = models.IntegerField(default=0, verbose_name='عدد المشاهدات')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    
    class Meta:
        verbose_name = 'جولة 360°'
        verbose_name_plural = 'جولات 360°'
        ordering = ['order', '-created_at']
    
    def __str__(self):
        return f'{self.title} - {self.page.name}'


class ServiceProviderFollower(models.Model):
    """متابعو صفحة مقدم الخدمة"""
    
    page = models.ForeignKey(ServiceProviderPage, on_delete=models.CASCADE, related_name='followers', verbose_name='الصفحة')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='followed_providers', verbose_name='المستخدم')
    
    # Timestamps
    followed_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ المتابعة')
    
    class Meta:
        verbose_name = 'متابع'
        verbose_name_plural = 'المتابعون'
        unique_together = ['page', 'user']
    
    def __str__(self):
        return f'{self.user.username} - {self.page.name}'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.page.followers_count = self.page.followers.count()
        self.page.save()
    
    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self.page.followers_count = self.page.followers.count()
        self.page.save()


class ServiceProviderRating(models.Model):
    """تقييمات مقدم الخدمة"""
    
    page = models.ForeignKey(ServiceProviderPage, on_delete=models.CASCADE, related_name='ratings', verbose_name='الصفحة')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='provider_ratings', verbose_name='المستخدم')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name='التقييم')
    review = models.TextField(blank=True, verbose_name='التعليق')
    
    # Customer Photos
    customer_images = models.ManyToManyField(ServiceProviderGallery, blank=True, related_name='ratings', verbose_name='صور العميل')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التقييم')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'تقييم'
        verbose_name_plural = 'التقييمات'
        unique_together = ['page', 'user']
    
    def __str__(self):
        return f'{self.rating} نجوم - {self.page.name}'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update page rating
        ratings = self.page.ratings.all()
        if ratings:
            avg_rating = sum(r.rating for r in ratings) / len(ratings)
            self.page.rating = round(avg_rating, 2)
            self.page.reviews_count = ratings.count()
            self.page.save()


class ServiceProviderContact(models.Model):
    """طلبات التواصل مع مقدم الخدمة"""
    
    CONTACT_TYPE_CHOICES = [
        ('call', 'اتصال'),
        ('whatsapp', 'واتساب'),
        ('telegram', 'تلغرام'),
        ('message', 'مراسلة'),
        ('quote', 'طلب عرض سعر'),
        ('visit', 'طلب زيارة'),
        ('appointment', 'حجز موعد'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'بانتظار الرد'),
        ('responded', 'تم الرد'),
        ('completed', 'مكتمل'),
        ('cancelled', 'ملغي'),
    ]
    
    page = models.ForeignKey(ServiceProviderPage, on_delete=models.CASCADE, related_name='contacts', verbose_name='الصفحة')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='provider_contacts', verbose_name='المستخدم')
    
    contact_type = models.CharField(max_length=20, choices=CONTACT_TYPE_CHOICES, verbose_name='نوع التواصل')
    name = models.CharField(max_length=200, verbose_name='الاسم')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    phone = models.CharField(max_length=20, verbose_name='رقم الهاتف')
    message = models.TextField(verbose_name='الرسالة')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'طلب تواصل'
        verbose_name_plural = 'طلبات التواصل'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.name} - {self.page.name}'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.page.contacts_count = self.page.contacts.count()
        self.page.save()


class ServiceProviderQuote(models.Model):
    """طلبات عرض السعر"""
    
    STATUS_CHOICES = [
        ('pending', 'بانتظار الرد'),
        ('sent', 'تم الإرسال'),
        ('accepted', 'مقبول'),
        ('rejected', 'مرفوض'),
        ('expired', 'منتهي'),
    ]
    
    page = models.ForeignKey(ServiceProviderPage, on_delete=models.CASCADE, related_name='quotes', verbose_name='الصفحة')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='provider_quotes', verbose_name='المستخدم')
    
    # Project Details
    project_title = models.CharField(max_length=200, verbose_name='عنوان المشروع')
    project_description = models.TextField(verbose_name='وصف المشروع')
    location = models.CharField(max_length=200, verbose_name='الموقع')
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='الميزانية المتوقعة')
    
    # Contact Info
    name = models.CharField(max_length=200, verbose_name='الاسم')
    email = models.EmailField(verbose_name='البريد الإلكتروني')
    phone = models.CharField(max_length=20, verbose_name='رقم الهاتف')
    
    # Quote Details
    quoted_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='السعر المعروض')
    quote_notes = models.TextField(blank=True, verbose_name='ملاحظات العرض')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'طلب عرض سعر'
        verbose_name_plural = 'طلبات عروض الأسعار'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.project_title} - {self.page.name}'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.page.quotes_count = self.page.quotes.count()
        self.page.save()
