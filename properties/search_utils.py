"""
Advanced search and filtering utilities for properties
"""
from django.db.models import Q, Count, Avg, F
from django.db.models.functions import Coalesce
from .models import Property, PropertyRating, BrokerRating
from .cache_utils import cache_result


class PropertySearchEngine:
    """محرك بحث متقدم للعقارات"""
    
    def __init__(self, user=None):
        self.base_queryset = Property.objects.all()
        self.user = user
    
    def search(self, query=None, filters=None, sort_by=None, page=1, per_page=25, user_only=False):
        """
        البحث والفلترة المتقدمة
        
        Args:
            query: نص البحث
            filters: قاموس الفلاتر
            sort_by: طريقة الترتيب
            page: رقم الصفحة
            per_page: عدد النتائج لكل صفحة
            user_only: عرض عقارات المستخدم فقط
        
        Returns:
            queryset من العقارات المفلترة
        """
        queryset = self.base_queryset
        
        # تصفية حسب المستخدم إذا طُلب
        if user_only and self.user:
            queryset = queryset.filter(
                Q(owner=self.user) | Q(broker__user=self.user)
            ).distinct()
        
        # تطبيق البحث النصي
        if query:
            queryset = self._apply_text_search(queryset, query)
        
        # تطبيق الفلاتر
        if filters:
            queryset = self._apply_filters(queryset, filters)
        
        # تطبيق الترتيب
        if sort_by:
            queryset = self._apply_sorting(queryset, sort_by)
        
        # إضافة التقييمات المتوسطة
        queryset = queryset.annotate(
            avg_rating=Coalesce(
                Avg('ratings__rating'),
                0
            ),
            rating_count=Count('ratings')
        )
        
        return queryset
    
    def _apply_text_search(self, queryset, query):
        """تطبيق البحث النصي"""
        search_fields = [
            'title__icontains',
            'description__icontains',
            'district__icontains',
            'street__icontains',
            'location__icontains',
        ]
        
        q_objects = Q()
        for field in search_fields:
            q_objects |= Q(**{field: query})
        
        return queryset.filter(q_objects).distinct()
    
    def _apply_filters(self, queryset, filters):
        """تطبيق الفلاتر"""
        # فلتر نوع العقار
        if filters.get('type'):
            queryset = queryset.filter(type=filters['type'])
        
        # فلتر الحالة
        if filters.get('status'):
            queryset = queryset.filter(status=filters['status'])
        
        # فلتر الحي
        if filters.get('district'):
            queryset = queryset.filter(district__icontains=filters['district'])
        
        # فلتر نطاق السعر
        if filters.get('min_price'):
            queryset = queryset.filter(price__gte=filters['min_price'])
        if filters.get('max_price'):
            queryset = queryset.filter(price__lte=filters['max_price'])
        
        # فلتر نطاق المساحة
        if filters.get('min_area'):
            queryset = queryset.filter(area__gte=filters['min_area'])
        if filters.get('max_area'):
            queryset = queryset.filter(area__lte=filters['max_area'])
        
        # فلتر عدد الغرف
        if filters.get('min_bedrooms'):
            queryset = queryset.filter(bedrooms__gte=filters['min_bedrooms'])
        if filters.get('max_bedrooms'):
            queryset = queryset.filter(bedrooms__lte=filters['max_bedrooms'])
        
        # فلتر عدد الحمامات
        if filters.get('min_bathrooms'):
            queryset = queryset.filter(bathrooms__gte=filters['min_bathrooms'])
        if filters.get('max_bathrooms'):
            queryset = queryset.filter(bathrooms__lte=filters['max_bathrooms'])
        
        # فلتر عدد الطوابق
        if filters.get('min_floors'):
            queryset = queryset.filter(floors__gte=filters['min_floors'])
        if filters.get('max_floors'):
            queryset = queryset.filter(floors__lte=filters['max_floors'])
        
        # فلتر سنة البناء
        if filters.get('min_year_built'):
            queryset = queryset.filter(year_built__gte=filters['min_year_built'])
        if filters.get('max_year_built'):
            queryset = queryset.filter(year_built__lte=filters['max_year_built'])
        
        # فلتر المميزات
        if filters.get('parking'):
            queryset = queryset.filter(parking=True)
        if filters.get('furnished'):
            queryset = queryset.filter(furnished=True)
        
        # فلتر العقارات المميزة
        if filters.get('featured'):
            queryset = queryset.filter(is_featured=True)
        
        # فلتر العقارات المروجة
        if filters.get('promoted'):
            queryset = queryset.filter(is_promoted=True)
        
        # فلتر حسب الدلال
        if filters.get('broker'):
            queryset = queryset.filter(broker_id=filters['broker'])
        
        # فلتر حسب المكتب
        if filters.get('office'):
            queryset = queryset.filter(office_id=filters['office'])
        
        # فلتر حسب التقييم
        if filters.get('min_rating'):
            queryset = queryset.annotate(
                avg_rating=Avg('ratings__rating')
            ).filter(avg_rating__gte=filters['min_rating'])
        
        # فلتر العقارات الموثقة
        if filters.get('verified_only'):
            queryset = queryset.filter(
                ratings__is_verified=True
            ).distinct()
        
        return queryset
    
    def _apply_sorting(self, queryset, sort_by):
        """تطبيق الترتيب"""
        sort_options = {
            'price_asc': 'price',
            'price_desc': '-price',
            'area_asc': 'area',
            'area_desc': '-area',
            'newest': '-created_at',
            'oldest': 'created_at',
            'most_viewed': '-views_count',
            'rating': '-avg_rating',
            'rating_count': '-rating_count',
        }
        
        if sort_by in sort_options:
            return queryset.order_by(sort_options[sort_by])
        
        return queryset.order_by('-is_featured', '-is_promoted', '-created_at')


class BrokerSearchEngine:
    """محرك بحث متقدم للدلالين"""
    
    def __init__(self, user=None):
        self.base_queryset = Broker.objects.all()
        self.user = user
    
    def search(self, query=None, filters=None, sort_by=None, user_only=False):
        """البحث والفلترة للدلالين"""
        queryset = self.base_queryset
        
        # تصفية حسب المستخدم إذا طُلب
        if user_only and self.user:
            queryset = queryset.filter(user=self.user)
        
        # البحث النصي
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) |
                Q(user__username__icontains=query) |
                Q(office_name__icontains=query) |
                Q(governorate__icontains=query)
            )
        
        # الفلاتر
        if filters:
            if filters.get('role'):
                queryset = queryset.filter(role=filters['role'])
            if filters.get('governorate'):
                queryset = queryset.filter(governorate__icontains=filters['governorate'])
            if filters.get('is_verified'):
                queryset = queryset.filter(is_verified=True)
            if filters.get('is_active'):
                queryset = queryset.filter(is_active=True)
            if filters.get('subscription_type'):
                queryset = queryset.filter(subscription_type=filters['subscription_type'])
        
        # إضافة التقييمات
        queryset = queryset.annotate(
            avg_rating=Coalesce(
                Avg('ratings__rating'),
                0
            ),
            rating_count=Count('ratings'),
            property_count=Count('properties')
        )
        
        # الترتيب
        if sort_by == 'rating':
            queryset = queryset.order_by('-avg_rating')
        elif sort_by == 'property_count':
            queryset = queryset.order_by('-property_count')
        else:
            queryset = queryset.order_by('-created_at')
        
        return queryset


class PropertyRecommendationEngine:
    """محرك التوصيات للعقارات"""
    
    @staticmethod
    @cache_result(timeout=3600, key_prefix='similar_properties')
    def get_similar_properties(property_id, limit=6):
        """
        الحصول على عقارات مشابهة
        
        Args:
            property_id: معرف العقار
            limit: عدد النتائج
        
        Returns:
            queryset من العقارات المشابهة
        """
        try:
            target_property = Property.objects.get(id=property_id)
        except Property.DoesNotExist:
            return Property.objects.none()
        
        # البحث عن عقارات مشابهة حسب:
        # - نفس النوع
        # - نفس الحي
        # - نطاق سعر مشابه
        # - نطاق مساحة مشابه
        
        price_range = target_property.price * 0.2  # 20% tolerance
        area_range = target_property.area * 0.2    # 20% tolerance
        
        similar = Property.objects.filter(
            type=target_property.type,
            status='ready',
            price__gte=target_property.price - price_range,
            price__lte=target_property.price + price_range,
            area__gte=target_property.area - area_range,
            area__lte=target_property.area + area_range,
        ).exclude(id=property_id)
        
        # إعطاء أولوية لنفس الحي
        if target_property.district:
            similar = similar.filter(district=target_property.district)
        
        return similar[:limit]
    
    @staticmethod
    @cache_result(timeout=3600, key_prefix='recommended_properties')
    def get_recommended_for_user(user_id, limit=10):
        """
        الحصول على عقارات موصى بها للمستخدم
        
        Args:
            user_id: معرف المستخدم
            limit: عدد النتائج
        
        Returns:
            queryset من العقارات الموصى بها
        """
        # التوصيات بناءً على:
        # - العقارات التي أعجب بها المستخدم
        # - العقارات التي حفظها المستخدم
        # - العقارات التي قيمها المستخدم
        
        from django.contrib.auth.models import User
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Property.objects.filter(is_featured=True)[:limit]
        
        # الحصول على أنواع العقارات التي أعجب بها المستخدم
        liked_properties = Property.objects.filter(
            likes__user=user
        ).values_list('type', flat=True).distinct()
        
        if liked_properties:
            recommended = Property.objects.filter(
                type__in=liked_properties,
                status='ready',
                is_featured=True
            )
        else:
            # إذا لم يكن هناك تفضيلات، أظهر العقارات المميزة
            recommended = Property.objects.filter(
                status='ready',
                is_featured=True
            )
        
        return recommended[:limit]


class AdvancedFilterBuilder:
    """بناء فلاتر متقدمة"""
    
    @staticmethod
    def build_price_ranges():
        """بناء نطاقات السعر الشائعة"""
        return [
            {'label': 'أقل من 50 مليون', 'min': 0, 'max': 50000000},
            {'label': '50 - 100 مليون', 'min': 50000000, 'max': 100000000},
            {'label': '100 - 200 مليون', 'min': 100000000, 'max': 200000000},
            {'label': '200 - 500 مليون', 'min': 200000000, 'max': 500000000},
            {'label': 'أكثر من 500 مليون', 'min': 500000000, 'max': None},
        ]
    
    @staticmethod
    def build_area_ranges():
        """بناء نطاقات المساحة الشائعة"""
        return [
            {'label': 'أقل من 100 م²', 'min': 0, 'max': 100},
            {'label': '100 - 200 م²', 'min': 100, 'max': 200},
            {'label': '200 - 400 م²', 'min': 200, 'max': 400},
            {'label': '400 - 800 م²', 'min': 400, 'max': 800},
            {'label': 'أكثر من 800 م²', 'min': 800, 'max': None},
        ]
    
    @staticmethod
    def get_popular_districts(limit=10):
        """الحصول على أكثر الأحيان شعبية"""
        return Property.objects.values('district').annotate(
            count=Count('id')
        ).order_by('-count')[:limit]
    
    @staticmethod
    def get_search_suggestions(query, limit=10):
        """
        الحصول على اقتراحات البحث
        
        Args:
            query: نص البحث
            limit: عدد الاقتراحات
        
        Returns:
            قائمة من الاقتراحات
        """
        suggestions = []
        
        # اقتراحات من الأحياء
        districts = Property.objects.filter(
            district__icontains=query
        ).values_list('district', flat=True).distinct()[:5]
        
        for district in districts:
            suggestions.append({
                'type': 'district',
                'text': district,
                'icon': '📍'
            })
        
        # اقتراحات من أنواع العقارات
        types = [t[1] for t in Property.PROPERTY_TYPES if query.lower() in t[1].lower()]
        for prop_type in types[:3]:
            suggestions.append({
                'type': 'type',
                'text': prop_type,
                'icon': '🏠'
            })
        
        return suggestions[:limit]
