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
    STATUS_CHOICES = STATUS_CHOICES

    title = models.CharField(max_length=200, blank=True, default='', verbose_name='عنوان الإعلان')
    slug = models.SlugField(max_length=220, unique=True, blank=True, default='', allow_unicode=True)
    category = models.CharField(max_length=20, choices=PROPERTY_CATEGORIES, blank=True, null=True, verbose_name='تصنيف العقار')
    type = models.CharField(max_length=50, choices=PROPERTY_TYPES, verbose_name='نوع العقار')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ready', verbose_name='الحالة')

    # Location fields
    district = models.CharField(max_length=100, verbose_name='الحي', help_text='اسم الحي')
    street = models.CharField(max_length=100, blank=True, verbose_name='الشارع', help_text='اسم الشارع')
    location = models.CharField(max_length=200, verbose_name='العنوان التفصيلي', help_text='العنوان الكامل')
    
    # Outside Iraq location fields
    country = models.ForeignKey('Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='properties', verbose_name='الدولة')
    city = models.ForeignKey('City', on_delete=models.SET_NULL, null=True, blank=True, related_name='properties', verbose_name='المدينة')
    area_outside = models.ForeignKey('Area', on_delete=models.SET_NULL, null=True, blank=True, related_name='properties', verbose_name='المنطقة')

    area = models.PositiveIntegerField(verbose_name='المساحة (م²)')
    price = models.BigIntegerField(verbose_name='السعر (د.ع)')
    
    # Currency for outside Iraq properties
    currency = models.CharField(max_length=3, blank=True, default='IQD', verbose_name='العملة')
    original_price = models.BigIntegerField(null=True, blank=True, verbose_name='السعر الأصلي بالعملة الأجنبية')
    description = models.TextField(verbose_name='وصف العقار')
    phone = models.CharField(max_length=20, verbose_name='رقم التواصل')

    bedrooms = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='عدد الغرف')
    bathrooms = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='عدد الحمامات')
    floors = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='عدد الطوابق')
    year_built = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='سنة البناء')
    parking = models.BooleanField(default=False, verbose_name='موقف سيارة')
    furnished = models.BooleanField(default=False, verbose_name='مفروش')

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='خط العرض')
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='خط الطول')

    # image field removed - column does not exist in database
    # image = models.ImageField(upload_to=property_image_path, null=True, blank=True, verbose_name='الصورة الرئيسية')
    images = models.TextField(blank=True, help_text='روابط صور إضافية (قديم)')

    is_featured = models.BooleanField(default=False, verbose_name='عقار مميز')
    is_promoted = models.BooleanField(default=False, verbose_name='إعلان خاص')
    promotion_until = models.DateField(null=True, blank=True, verbose_name='انتهاء الترويج')

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
        ordering = ['-is_featured', '-is_promoted', '-created_at']
        indexes = [
            models.Index(fields=['district']),
            models.Index(fields=['type', 'status']),
            models.Index(fields=['price']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['is_featured', 'is_promoted']),
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


class PropertyImage(models.Model):
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='gallery_images', verbose_name='العقار'
    )
    image = models.ImageField(upload_to=property_image_path, verbose_name='الصورة')
    caption = models.CharField(max_length=200, blank=True, verbose_name='تعليق')
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name='الترتيب')
    is_primary = models.BooleanField(default=False, verbose_name='رئيسية')
    is_360 = models.BooleanField(default=False, verbose_name='صورة 360°')
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'فيديو عقار'
        verbose_name_plural = 'فيديوهات العقارات'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'فيديو {self.property_id} #{self.pk}'


class Message(models.Model):
    # Message types
    TYPE_PROPERTY_INQUIRY = 'property_inquiry'
    TYPE_BROKER_MESSAGE = 'broker_message'
    TYPE_USER_BROKER = 'user_broker'
    
    TYPE_CHOICES = [
        (TYPE_PROPERTY_INQUIRY, 'استفسار عن عقار'),
        (TYPE_BROKER_MESSAGE, 'رسالة بين دلالين'),
        (TYPE_USER_BROKER, 'رسالة بين مستخدم ودلال'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='الاسم')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    phone = models.CharField(max_length=20, blank=True, verbose_name='رقم الهاتف')
    message = models.TextField(verbose_name='الرسالة')
    message_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default=TYPE_PROPERTY_INQUIRY,
        verbose_name='نوع الرسالة'
    )
    
    # For property inquiries
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, null=True, blank=True, related_name='inquiries'
    )
    
    # For broker-to-broker and user-to-broker messaging
    sender = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sent_messages', verbose_name='المرسل'
    )
    recipient = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='received_messages', verbose_name='المستلم'
    )
    
    broker = models.ForeignKey(
        'Broker', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='inquiries', verbose_name='الدلال'
    )
    reply = models.TextField(blank=True, verbose_name='الرد')
    replied_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الرد')
    replied_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='message_replies', verbose_name='رد بواسطة'
    )
    is_archived = models.BooleanField(default=False, verbose_name='مؤرشف')
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False, verbose_name='مقروء')
    is_deleted_by_sender = models.BooleanField(default=False, verbose_name='محذوف من المرسل')
    is_deleted_by_recipient = models.BooleanField(default=False, verbose_name='محذوف من المستلم')

    class Meta:
        verbose_name = 'رسالة'
        verbose_name_plural = 'الرسائل'
        ordering = ['-created_at']

    def __str__(self):
        if self.message_type == self.TYPE_BROKER_MESSAGE:
            return f'رسالة من {self.sender.username if self.sender else self.name}'
        elif self.message_type == self.TYPE_USER_BROKER:
            return f'رسالة من {self.sender.username if self.sender else self.name}'
        return f'رسالة من {self.name}'
    
    def get_other_user(self, user):
        """Get the other user in the conversation."""
        if self.sender == user:
            return self.recipient
        return self.sender
    
    def mark_as_read(self):
        """Mark message as read."""
        self.is_read = True
        self.save(update_fields=['is_read'])
    
    def archive(self):
        """Archive message."""
        self.is_archived = True
        self.save(update_fields=['is_archived'])
    
    def delete_for_user(self, user):
        """Soft delete message for a specific user."""
        if self.sender == user:
            self.is_deleted_by_sender = True
        elif self.recipient == user:
            self.is_deleted_by_recipient = True
        self.save(update_fields=['is_deleted_by_sender', 'is_deleted_by_recipient'])


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
    
    AUCTION_TYPES = [
        ('home', 'مزاد بيع منزل'),
        ('land', 'مزاد بيع أرض'),
        ('shop', 'مزاد بيع محل تجاري'),
        ('building', 'مزاد بيع عمارة'),
        ('investment', 'مزاد استثماري'),
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


class AuctionParticipant(models.Model):
    """Track auction participants with verification"""
    
    PAYMENT_STATUS = [
        ('pending', 'قيد الانتظار'),
        ('paid', 'مدفوع'),
        ('refunded', 'مسترد'),
        ('failed', 'فشل'),
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


class Resort(models.Model):
    """نموذج المنتجعات"""
    
    RESORT_TYPES = [
        ('beach', 'منتجع شاطئي'),
        ('mountain', 'منتجع جبلي'),
        ('desert', 'منتجع صحراوي'),
        ('rural', 'منتجع ريفي'),
        ('spa', 'منتجع صحي (Spa Resort)'),
        ('family', 'منتجع عائلي'),
        ('luxury', 'منتجع فاخر'),
        ('eco', 'منتجع بيئي'),
    ]
    
    ACCOMMODATION_TYPES = [
        ('room', 'غرفة'),
        ('suite', 'جناح'),
        ('villa', 'فيلا'),
        ('chalet', 'شاليه'),
        ('cottage', 'كوخ'),
        ('bungalow', 'بنغلو'),
    ]
    
    SUITABLE_FOR = [
        ('families', 'العائلات'),
        ('honeymoon', 'شهر العسل'),
        ('events', 'المناسبات'),
        ('relaxation', 'الاسترخاء'),
        ('summer', 'الإجازات الصيفية'),
    ]
    
    name = models.CharField(max_length=200, verbose_name='اسم المنتجع')
    description = models.TextField(verbose_name='الوصف')
    resort_type = models.CharField(max_length=20, choices=RESORT_TYPES, verbose_name='نوع المنتجع')
    facilities = models.JSONField(default=list, verbose_name='المرافق')
    accommodation_types = models.JSONField(default=list, verbose_name='أنواع الإقامة')
    suitable_for = models.JSONField(default=list, verbose_name='مناسب لـ')
    
    # Location
    governorate = models.CharField(max_length=50, choices=IRAQ_GOVERNORATES, verbose_name='المحافظة')
    city = models.CharField(max_length=100, verbose_name='المدينة')
    address = models.TextField(verbose_name='العنوان')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='خط العرض')
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='خط الطول')
    
    # Pricing
    price_range = models.CharField(max_length=20, choices=Hotel.PRICE_RANGES, verbose_name='السعر')
    
    # Contact
    phone = models.CharField(max_length=20, verbose_name='رقم الهاتف')
    email = models.EmailField(verbose_name='البريد الإلكتروني')
    website = models.URLField(blank=True, verbose_name='الموقع الإلكتروني')
    
    # Media
    image = models.ImageField(upload_to='resorts/', verbose_name='الصورة الرئيسية')
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    is_featured = models.BooleanField(default=False, verbose_name='مميز')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'منتجع'
        verbose_name_plural = 'المنتجعات'
        ordering = ['-is_featured', 'name']
    
    def __str__(self):
        return f'{self.name} - {self.get_resort_type_display()}'


class ResortImage(models.Model):
    """صور المنتجعات"""
    resort = models.ForeignKey(Resort, on_delete=models.CASCADE, related_name='images', verbose_name='المنتجع')
    image = models.ImageField(upload_to='resorts/gallery/', verbose_name='الصورة')
    caption = models.CharField(max_length=200, blank=True, verbose_name='التعليق')
    is_primary = models.BooleanField(default=False, verbose_name='رئيسية')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الرفع')
    
    class Meta:
        verbose_name = 'صورة منتجع'
        verbose_name_plural = 'صور المنتجعات'
        ordering = ['-is_primary', 'id']
    
    def __str__(self):
        return f'صورة {self.resort.name}'


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
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='building_requests', verbose_name='المستخدم')
    full_name = models.CharField(max_length=200, blank=True, verbose_name='الاسم الكامل')
    phone = models.CharField(max_length=20, blank=True, verbose_name='رقم الهاتف')
    email = models.EmailField(blank=True, verbose_name='البريد الإلكتروني')
    
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


class SubscriptionRequest(models.Model):
    """نموذج طلبات الاشتراك"""
    
    REQUEST_TYPE_UPGRADE = 'upgrade'
    REQUEST_TYPE_REACTIVATE = 'reactivate'
    
    REQUEST_TYPE_CHOICES = [
        (REQUEST_TYPE_UPGRADE, 'تطوير خطة الاشتراك'),
        (REQUEST_TYPE_REACTIVATE, 'تفعيل اشتراك معطل'),
    ]
    
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'قيد الانتظار'),
        (STATUS_APPROVED, 'موافق عليه'),
        (STATUS_REJECTED, 'مرفوض'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='المستخدم')
    request_type = models.CharField(
        max_length=20,
        choices=REQUEST_TYPE_CHOICES,
        verbose_name='نوع الطلب'
    )
    current_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='upgrade_requests',
        verbose_name='الخطة الحالية'
    )
    requested_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requested_by',
        verbose_name='الخطة المطلوبة'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name='الحالة'
    )
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    admin_notes = models.TextField(blank=True, verbose_name='ملاحظات الإدارة')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ المعالجة')
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_requests',
        verbose_name='تمت المعالجة بواسطة'
    )
    
    class Meta:
        verbose_name = 'طلب اشتراك'
        verbose_name_plural = 'طلبات الاشتراك'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.get_request_type_display()} - {self.user.username}'
    
    def approve(self, admin_user):
        """موافقة على الطلب"""
        self.status = self.STATUS_APPROVED
        self.processed_by = admin_user
        self.processed_at = timezone.now()
        self.save()
        
        # تنفيذ الإجراء بناءً على نوع الطلب
        if self.request_type == self.REQUEST_TYPE_UPGRADE and self.requested_plan:
            # تطوير الخطة
            from .models import Broker
            try:
                broker = self.user.broker
                broker.subscription_plan = self.requested_plan
                broker.save()
            except Broker.DoesNotExist:
                pass
        elif self.request_type == self.REQUEST_TYPE_REACTIVATE:
            # تفعيل اشتراك معطل
            from .models import Broker
            try:
                broker = self.user.broker
                broker.is_suspended = False
                broker.save()
            except Broker.DoesNotExist:
                pass
    
    def reject(self, admin_user, notes=''):
        """رفض الطلب"""
        self.status = self.STATUS_REJECTED
        self.admin_notes = notes
        self.processed_by = admin_user
        self.processed_at = timezone.now()
        self.save()


class UserProfile(models.Model):
    """نموذج المستخدم العادي"""
    user = models.OneToOneField(
        'auth.User', on_delete=models.CASCADE, related_name='user_profile'
    )
    phone = models.CharField(max_length=20, blank=True, verbose_name='الهاتف')
    governorate = models.CharField(max_length=100, blank=True, verbose_name='المحافظة')
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
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_SUB, verbose_name='الدور')
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sub_brokers', verbose_name='الدلال الرئيسي'
    )
    is_verified = models.BooleanField(default=False, verbose_name='دلال موثق')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    subscription_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='brokers',
        verbose_name='خطة الاشتراك'
    )
    custom_ads_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='عدد العقارات المخصص',
        help_text='عدد العقارات المسموح به (يستخدم بدلاً من خطة الاشتراك إذا تم تحديده)'
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
    max_properties = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='الحد الأقصى للعقارات'
    )
    subscription_start_date = models.DateField(
        null=True, blank=True, verbose_name='تاريخ بداية الاشتراك'
    )
    subscription_end_date = models.DateField(
        null=True, blank=True, verbose_name='تاريخ انتهاء الاشتراك'
    )
    is_suspended = models.BooleanField(
        default=False, verbose_name='مجمد'
    )
    id_card_image = models.ImageField(
        upload_to='broker_ids/', null=True, blank=True, verbose_name='صورة الهوية'
    )
    bio = models.TextField(blank=True, verbose_name='نبذة')
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
                Notification.objects.create(
                    user=self.user,
                    title='انتهاء الاشتراك',
                    message=f'انتهى اشتراكك في {self.subscription_end_date}. تم تعطيل حسابك مؤقتاً. يرجى تجديد الاشتراك للاستمرار.',
                    type='subscription'
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
    
    STATUS_CHOICES = [
        ('active', 'نشط'),
        ('inactive', 'غير نشط'),
        ('suspended', 'موقوف'),
        ('pending', 'بانتظار الموافقة'),
    ]
    
    broker = models.OneToOneField(
        Broker, on_delete=models.CASCADE, related_name='channel', verbose_name='الدلال'
    )
    name = models.CharField(max_length=200, verbose_name='اسم القناة')
    description = models.TextField(blank=True, verbose_name='وصف القناة')
    logo = models.ImageField(
        upload_to='channels/logos/', null=True, blank=True, verbose_name='شعار القناة'
    )
    cover_image = models.ImageField(
        upload_to='channels/covers/', null=True, blank=True, verbose_name='صورة الغلاف'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='الحالة'
    )
    is_verified = models.BooleanField(default=False, verbose_name='موثق')
    followers_count = models.PositiveIntegerField(default=0, verbose_name='عدد المتابعين')
    views_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاهدات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'قناة دلال'
        verbose_name_plural = 'قنوات الدلالين'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.name} - {self.broker.display_name}'
    
    @property
    def properties_count(self):
        """عدد العقارات النشطة في القناة"""
        return Property.objects.filter(
            broker=self.broker,
            status__in=['ready', 'rent']
        ).count()
    
    @property
    def ads_count(self):
        """عدد الإعلانات في القناة"""
        return self.properties_count
    
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


class Notification(models.Model):
    """نظام الإشعارات والتنبيهات"""
    
    TYPE_CHOICES = [
        ('info', 'معلومة'),
        ('success', 'نجاح'),
        ('warning', 'تحذير'),
        ('error', 'خطأ'),
        ('broker_created', 'إنشاء دلال'),
        ('broker_updated', 'تعديل دلال'),
        ('broker_deleted', 'حذف دلال'),
        ('broker_suspended', 'إيقاف دلال'),
        ('broker_activated', 'تفعيل دلال'),
        ('subscription_expiring', 'اشتراك منتهي قريباً'),
        ('subscription_expired', 'اشتراك منتهي'),
        ('property_limit_reached', 'وصول لحد العقارات'),
        ('message_received', 'رسالة جديدة'),
    ]
    
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='المستخدم'
    )
    notification_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
        verbose_name='نوع الإشعار'
    )
    title = models.CharField(
        max_length=200,
        verbose_name='العنوان'
    )
    message = models.TextField(
        verbose_name='الرسالة'
    )
    link = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='رابط'
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name='مقروء'
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
        verbose_name = 'إشعار'
        verbose_name_plural = 'الإشعارات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['is_read', '-created_at']),
            models.Index(fields=['notification_type', '-created_at']),
        ]
    
    def __str__(self):
        return f'{self.title} - {self.user.username}'
    
    @classmethod
    def create(cls, user, notification_type, title, message, link='', metadata=None):
        """إنشاء إشعار جديد"""
        return cls.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
            metadata=metadata or {}
        )
    
    def mark_as_read(self):
        """تعليم الإشعار كمقروء"""
        self.is_read = True
        self.save(update_fields=['is_read'])


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


class MessageAttachment(models.Model):
    """مرفقات الرسالة"""
    
    ATTACHMENT_IMAGE = 'image'
    ATTACHMENT_VIDEO = 'video'
    ATTACHMENT_AUDIO = 'audio'
    ATTACHMENT_FILE = 'file'
    
    ATTACHMENT_TYPE_CHOICES = [
        (ATTACHMENT_IMAGE, 'صورة'),
        (ATTACHMENT_VIDEO, 'فيديو'),
        (ATTACHMENT_AUDIO, 'صوت'),
        (ATTACHMENT_FILE, 'ملف'),
    ]
    
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='الرسالة'
    )
    attachment_type = models.CharField(
        max_length=20,
        choices=ATTACHMENT_TYPE_CHOICES,
        verbose_name='نوع المرفق'
    )
    file = models.FileField(
        upload_to=chat_attachment_path,
        verbose_name='الملف'
    )
    thumbnail = models.ImageField(
        upload_to=chat_image_path,
        blank=True,
        null=True,
        verbose_name='الصورة المصغرة'
    )
    file_name = models.CharField(
        max_length=255,
        verbose_name='اسم الملف'
    )
    file_size = models.PositiveIntegerField(
        verbose_name='حجم الملف (بايت)'
    )
    mime_type = models.CharField(
        max_length=100,
        verbose_name='نوع MIME'
    )
    width = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='العرض'
    )
    height = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='الارتفاع'
    )
    duration = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='المدة (ثواني)'
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الرفع'
    )
    
    class Meta:
        verbose_name = 'مرفق الرسالة'
        verbose_name_plural = 'مرفقات الرسائل'
        indexes = [
            models.Index(fields=['message', 'attachment_type']),
        ]
    
    def __str__(self):
        return f'{self.file_name} - {self.message}'
    
    def get_file_size_display(self):
        """Get human-readable file size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.file_size < 1024:
                return f'{self.file_size:.1f} {unit}'
            self.file_size /= 1024
        return f'{self.file_size:.1f} TB'


class MessageReaction(models.Model):
    """رد فعل على رسالة"""
    
    REACTION_LIKE = 'like'
    REACTION_LOVE = 'love'
    REACTION_LAUGH = 'laugh'
    REACTION_SAD = 'sad'
    REACTION_ANGRY = 'angry'
    REACTION_THUMBS_UP = 'thumbs_up'
    REACTION_THUMBS_DOWN = 'thumbs_down'
    REACTION_CLAP = 'clap'
    
    REACTION_CHOICES = [
        (REACTION_LIKE, '👍'),
        (REACTION_LOVE, '❤️'),
        (REACTION_LAUGH, '😂'),
        (REACTION_SAD, '😢'),
        (REACTION_ANGRY, '😠'),
        (REACTION_THUMBS_UP, '👍'),
        (REACTION_THUMBS_DOWN, '👎'),
        (REACTION_CLAP, '👏'),
    ]
    
    REACTION_EMOJIS = {
        REACTION_LIKE: '👍',
        REACTION_LOVE: '❤️',
        REACTION_LAUGH: '😂',
        REACTION_SAD: '😢',
        REACTION_ANGRY: '😠',
        REACTION_THUMBS_UP: '👍',
        REACTION_THUMBS_DOWN: '👎',
        REACTION_CLAP: '👏',
    }
    
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name='reactions',
        verbose_name='الرسالة'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='message_reactions',
        verbose_name='المستخدم'
    )
    reaction_type = models.CharField(
        max_length=20,
        choices=REACTION_CHOICES,
        verbose_name='نوع الرد'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الإضافة'
    )
    
    class Meta:
        verbose_name = 'رد فعل'
        verbose_name_plural = 'ردود الفعل'
        unique_together = ['message', 'user', 'reaction_type']
        indexes = [
            models.Index(fields=['message', 'reaction_type']),
        ]
    
    def __str__(self):
        return f'{self.user.username} {self.get_reaction_emoji()} على {self.message}'
    
    def get_reaction_emoji(self):
        return self.REACTION_EMOJIS.get(self.reaction_type, '')


class MessageReport(models.Model):
    """بلاغ عن رسالة"""
    
    REPORT_TYPE_SPAM = 'spam'
    REPORT_TYPE_HARASSMENT = 'harassment'
    REPORT_TYPE_INAPPROPRIATE = 'inappropriate'
    REPORT_TYPE_SCAM = 'scam'
    REPORT_TYPE_OTHER = 'other'
    
    REPORT_TYPE_CHOICES = [
        (REPORT_TYPE_SPAM, 'رسائل مزعجة'),
        (REPORT_TYPE_HARASSMENT, 'مضايقة'),
        (REPORT_TYPE_INAPPROPRIATE, 'محتوى غير لائق'),
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
        (STATUS_DISMISSED, 'مرفوض'),
    ]
    
    reporter = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='message_reports',
        verbose_name='المبلغ'
    )
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.SET_NULL,
        null=True,
        related_name='reports',
        verbose_name='الرسالة'
    )
    reported_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='reports_against',
        verbose_name='المستخدم المبلغ ضده'
    )
    report_type = models.CharField(
        max_length=20,
        choices=REPORT_TYPE_CHOICES,
        verbose_name='نوع البلاغ'
    )
    description = models.TextField(
        verbose_name='الوصف'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name='الحالة'
    )
    admin_notes = models.TextField(
        blank=True,
        verbose_name='ملاحظات المسؤول'
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_reports',
        verbose_name='راجع بواسطة'
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='تاريخ المراجعة'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ البلاغ'
    )
    
    class Meta:
        verbose_name = 'بلاغ عن رسالة'
        verbose_name_plural = 'البلاغات عن الرسائل'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['reporter', '-created_at']),
            models.Index(fields=['reported_user', '-created_at']),
        ]
    
    def __str__(self):
        return f'بلاغ #{self.id} - {self.get_report_type_display()}'
    
    def mark_as_reviewed(self, admin, notes=''):
        """Mark report as reviewed"""
        self.status = self.STATUS_REVIEWED
        self.reviewed_by = admin
        self.reviewed_at = timezone.now()
        self.admin_notes = notes
        self.save()
    
    def resolve(self, admin, notes=''):
        """Resolve report"""
        self.status = self.STATUS_RESOLVED
        self.reviewed_by = admin
        self.reviewed_at = timezone.now()
        self.admin_notes = notes
        self.save()
    
    def dismiss(self, admin, notes=''):
        """Dismiss report"""
        self.status = self.STATUS_DISMISSED
        self.reviewed_by = admin
        self.reviewed_at = timezone.now()
        self.admin_notes = notes
        self.save()


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


# Signals for automatic stats updates
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
