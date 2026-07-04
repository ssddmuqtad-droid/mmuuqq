"""
Analytics Dashboard Utilities
أدوات لوحة التحكم التحليلية
"""
from django.db.models import Count, Avg, Sum, F, Q
from django.db.models.functions import TruncDate, TruncMonth, TruncYear
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from .models import Property, PropertyRating, BrokerRating, Message, Auction, Bid, PropertyLike, PropertySave
from .cache_utils import cache_result


class AnalyticsDashboard:
    """لوحة التحكم التحليلية"""
    
    def __init__(self, start_date=None, end_date=None):
        """
        تهيئة لوحة التحكم
        
        Args:
            start_date: تاريخ البداية
            end_date: تاريخ النهاية
        """
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        self.start_date = start_date
        self.end_date = end_date
    
    @cache_result(timeout=300, key_prefix='analytics_overview')
    def get_overview_stats(self):
        """الحصول على إحصائيات عامة"""
        total_properties = Property.objects.count()
        active_properties = Property.objects.filter(status='ready').count()
        total_users = Property.objects.values('owner').distinct().count()
        total_brokers = BrokerRating.objects.values('broker').distinct().count()
        
        return {
            'total_properties': total_properties,
            'active_properties': active_properties,
            'total_users': total_users,
            'total_brokers': total_brokers,
            'properties_growth': self._calculate_growth(Property.objects, 'created_at'),
        }
    
    @cache_result(timeout=300, key_prefix='analytics_properties')
    def get_property_stats(self):
        """إحصائيات العقارات"""
        properties = Property.objects.filter(
            created_at__range=(self.start_date, self.end_date)
        )
        
        # توزيع حسب النوع
        by_type = properties.values('type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # توزيع حسب الحالة
        by_status = properties.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # توزيع حسب الحي
        by_district = properties.values('district').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # متوسط الأسعار
        avg_price = properties.aggregate(
            avg_price=Avg('price')
        )['avg_price'] or 0
        
        # أكثر العقارات مشاهدة
        most_viewed = Property.objects.order_by('-views_count')[:10]
        
        return {
            'by_type': list(by_type),
            'by_status': list(by_status),
            'by_district': list(by_district),
            'avg_price': avg_price,
            'most_viewed': most_viewed,
        }
    
    @cache_result(timeout=300, key_prefix='analytics_ratings')
    def get_rating_stats(self):
        """إحصائيات التقييمات"""
        property_ratings = PropertyRating.objects.filter(
            created_at__range=(self.start_date, self.end_date)
        )
        
        broker_ratings = BrokerRating.objects.filter(
            created_at__range=(self.start_date, self.end_date)
        )
        
        # متوسط تقييمات العقارات
        property_avg = property_ratings.aggregate(
            avg_rating=Avg('rating'),
            total_ratings=Count('id')
        )
        
        # متوسط تقييمات الدلالين
        broker_avg = broker_ratings.aggregate(
            avg_rating=Avg('rating'),
            total_ratings=Count('id')
        )
        
        # توزيع التقييمات
        rating_distribution = property_ratings.values('rating').annotate(
            count=Count('id')
        ).order_by('rating')
        
        return {
            'property_avg_rating': property_avg['avg_rating'] or 0,
            'property_total_ratings': property_avg['total_ratings'] or 0,
            'broker_avg_rating': broker_avg['avg_rating'] or 0,
            'broker_total_ratings': broker_avg['total_ratings'] or 0,
            'rating_distribution': list(rating_distribution),
        }
    
    @cache_result(timeout=300, key_prefix='analytics_engagement')
    def get_engagement_stats(self):
        """إحصائيات التفاعل"""
        likes = PropertyLike.objects.filter(
            created_at__range=(self.start_date, self.end_date)
        ).count()
        
        saves = PropertySave.objects.filter(
            created_at__range=(self.start_date, self.end_date)
        ).count()
        
        messages = Message.objects.filter(
            created_at__range=(self.start_date, self.end_date)
        ).count()
        
        views = Property.objects.filter(
            created_at__range=(self.start_date, self.end_date)
        ).aggregate(total_views=Sum('views_count'))['total_views'] or 0
        
        return {
            'total_likes': likes,
            'total_saves': saves,
            'total_messages': messages,
            'total_views': views,
        }
    
    @cache_result(timeout=300, key_prefix='analytics_auctions')
    def get_auction_stats(self):
        """إحصائيات المزادات"""
        auctions = Auction.objects.filter(
            created_at__range=(self.start_date, self.end_date)
        )
        
        total_auctions = auctions.count()
        active_auctions = auctions.filter(status='active').count()
        completed_auctions = auctions.filter(status='ended').count()
        
        total_bids = Bid.objects.filter(
            created_at__range=(self.start_date, self.end_date)
        ).count()
        
        # متوسط عدد المزايدات لكل مزاد
        avg_bids_per_auction = auctions.annotate(
            bid_count=Count('bids')
        ).aggregate(avg_bids=Avg('bid_count'))['avg_bids'] or 0
        
        return {
            'total_auctions': total_auctions,
            'active_auctions': active_auctions,
            'completed_auctions': completed_auctions,
            'total_bids': total_bids,
            'avg_bids_per_auction': avg_bids_per_auction,
        }
    
    def get_time_series_data(self, period='daily'):
        """
        الحصول على بيانات السلاسل الزمنية
        
        Args:
            period: الفترة الزمنية (daily, weekly, monthly)
        """
        properties = Property.objects.filter(
            created_at__range=(self.start_date, self.end_date)
        )
        
        if period == 'daily':
            trunc_func = TruncDate
        elif period == 'monthly':
            trunc_func = TruncMonth
        elif period == 'yearly':
            trunc_func = TruncYear
        else:
            trunc_func = TruncDate
        
        time_series = properties.annotate(
            period=trunc_func('created_at')
        ).values('period').annotate(
            count=Count('id'),
            avg_price=Avg('price')
        ).order_by('period')
        
        return list(time_series)
    
    def get_top_performers(self, limit=10):
        """الحصول على أفضل الأداء"""
        # أكثر العقارات مشاهدة
        top_viewed = Property.objects.order_by('-views_count')[:limit]
        
        # أكثر العقارات تقييماً
        top_rated = Property.objects.annotate(
            avg_rating=Avg('ratings__rating'),
            rating_count=Count('ratings')
        ).filter(rating_count__gt=0).order_by('-avg_rating')[:limit]
        
        # أكثر العقارات إعجاباً
        top_liked = Property.objects.annotate(
            like_count=Count('likes')
        ).order_by('-like_count')[:limit]
        
        return {
            'top_viewed': top_viewed,
            'top_rated': top_rated,
            'top_liked': top_liked,
        }
    
    def get_user_activity(self):
        """نشاط المستخدمين"""
        # مستخدمون نشطون (قاموا بتفاعل في آخر 30 يوم)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        active_users = PropertyLike.objects.filter(
            created_at__gte=thirty_days_ago
        ).values('user').distinct().count()
        
        # نمو المستخدمين
        user_growth = self._calculate_growth(
            PropertyLike.objects,
            'created_at',
            field='user'
        )
        
        return {
            'active_users': active_users,
            'user_growth': user_growth,
        }
    
    def _calculate_growth(self, queryset, date_field, field=None):
        """حساب النمو المئوي"""
        current_period = queryset.filter(
            **{f'{date_field}__range': (self.start_date, self.end_date)}
        )
        
        previous_start = self.start_date - (self.end_date - self.start_date)
        previous_end = self.start_date
        
        previous_period = queryset.filter(
            **{f'{date_field}__range': (previous_start, previous_end)}
        )
        
        if field:
            current_count = current_period.values(field).distinct().count()
            previous_count = previous_period.values(field).distinct().count()
        else:
            current_count = current_period.count()
            previous_count = previous_period.count()
        
        if previous_count == 0:
            return 100 if current_count > 0 else 0
        
        growth = ((current_count - previous_count) / previous_count) * 100
        return round(growth, 2)
    
    def export_data(self, format='json'):
        """
        تصدير البيانات
        
        Args:
            format: تنسيق التصدير (json, csv)
        """
        data = {
            'overview': self.get_overview_stats(),
            'properties': self.get_property_stats(),
            'ratings': self.get_rating_stats(),
            'engagement': self.get_engagement_stats(),
            'auctions': self.get_auction_stats(),
            'time_series': self.get_time_series_data(),
            'top_performers': {
                'top_viewed': [p.id for p in self.get_top_performers()['top_viewed']],
                'top_rated': [p.id for p in self.get_top_performers()['top_rated']],
                'top_liked': [p.id for p in self.get_top_performers()['top_liked']],
            },
            'user_activity': self.get_user_activity(),
        }
        
        if format == 'json':
            import json
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        
        return data


class RealTimeAnalytics:
    """تحليلات الوقت الفعلي"""
    
    @staticmethod
    def get_online_users():
        """الحصول على عدد المستخدمين المتصلين حالياً"""
        from django.contrib.sessions.models import Session
        from django.utils import timezone
        
        active_sessions = Session.objects.filter(
            expire_date__gte=timezone.now()
        ).count()
        
        return active_sessions
    
    @staticmethod
    def get_recent_activity(limit=20):
        """الحصول على النشاط الأخير"""
        recent_properties = Property.objects.order_by('-created_at')[:limit]
        recent_messages = Message.objects.order_by('-created_at')[:limit]
        recent_bids = Bid.objects.order_by('-created_at')[:limit]
        
        return {
            'recent_properties': recent_properties,
            'recent_messages': recent_messages,
            'recent_bids': recent_bids,
        }
    
    @staticmethod
    def get_hot_properties(hours=24, limit=10):
        """الحصول على العقارات الساخنة (الأكثر مشاهدة في آخر X ساعة)"""
        since = timezone.now() - timedelta(hours=hours)
        
        hot_properties = Property.objects.filter(
            updated_at__gte=since
        ).order_by('-views_count')[:limit]
        
        return hot_properties


class ReportGenerator:
    """مولد التقارير"""
    
    @staticmethod
    def generate_property_report(property_id):
        """توليد تقرير عن عقار"""
        try:
            property_obj = Property.objects.get(id=property_id)
        except Property.DoesNotExist:
            return None
        
        ratings = PropertyRating.objects.filter(property_obj=property_obj)
        
        report = {
            'property': {
                'id': property_obj.id,
                'title': property_obj.display_title,
                'type': property_obj.get_type_display(),
                'status': property_obj.get_status_display(),
                'price': property_obj.price,
                'area': property_obj.area,
                'district': property_obj.district,
                'views': property_obj.views_count,
                'created_at': property_obj.created_at,
            },
            'ratings': {
                'count': ratings.count(),
                'average': ratings.aggregate(avg=Avg('rating'))['avg'] or 0,
                'distribution': list(ratings.values('rating').annotate(
                    count=Count('id')
                ).order_by('rating')),
            },
            'engagement': {
                'likes': property_obj.likes.count(),
                'saves': property_obj.saves.count(),
                'comments': property_obj.comments.count(),
                'inquiries': property_obj.inquiries.count(),
            },
        }
        
        return report
    
    @staticmethod
    def generate_broker_report(broker_id):
        """توليد تقرير عن دلال"""
        from .models import Broker
        
        try:
            broker = Broker.objects.get(id=broker_id)
        except Broker.DoesNotExist:
            return None
        
        ratings = BrokerRating.objects.filter(broker=broker)
        properties = broker.properties.all()
        
        report = {
            'broker': {
                'id': broker.id,
                'name': broker.name,
                'role': broker.get_role_display(),
                'phone': broker.phone,
                'governorate': broker.governorate,
                'is_verified': broker.is_verified,
                'is_active': broker.is_active,
            },
            'properties': {
                'count': properties.count(),
                'by_type': list(properties.values('type').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'total_views': properties.aggregate(total=Sum('views_count'))['total'] or 0,
            },
            'ratings': {
                'count': ratings.count(),
                'average': ratings.aggregate(avg=Avg('rating'))['avg'] or 0,
                'distribution': list(ratings.values('rating').annotate(
                    count=Count('id')
                ).order_by('rating')),
            },
        }
        
        return report
