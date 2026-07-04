from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from .models import Property, PropertyImage, Message, Broker, Auction, Bid, SiteSettings
import json


class PropertyModelTest(TestCase):
    """اختبارات نموذج العقارات"""
    
    def setUp(self):
        self.property = Property.objects.create(
            type='house',
            status='ready',
            district='الحي السكني',
            location='الناصرية، الحي السكني',
            area=150,
            price=100000000,
            description='بيت جميل في موقع ممتاز',
            phone='07701234567',
            bedrooms=3,
            bathrooms=2,
            floors=2,
        )
    
    def test_property_creation(self):
        """اختبار إنشاء عقار"""
        self.assertTrue(isinstance(self.property, Property))
        self.assertEqual(self.property.type, 'house')
        self.assertEqual(self.property.district, 'الحي السكني')
    
    def test_property_str(self):
        """اختبار تمثيل النص"""
        self.assertEqual(str(self.property), self.property.display_title)
    
    def test_property_slug_generation(self):
        """اختبار توليد slug"""
        self.property.save()
        self.assertTrue(self.property.slug)
        self.assertIn('house', self.property.slug.lower())
    
    def test_property_price_formatted(self):
        """اختبار تنسيق السعر"""
        formatted = self.property.price_formatted
        self.assertIn(',', formatted)
        self.assertIn('100', formatted)


class PropertyImageViewTest(TestCase):
    """اختبارات صور العقارات"""
    
    def setUp(self):
        self.property = Property.objects.create(
            type='apartment',
            status='ready',
            district='الحي التجاري',
            location='الناصرية، الحي التجاري',
            area=80,
            price=50000000,
            description='شقة واسعة',
            phone='07701234567',
        )
    
    def test_property_image_creation(self):
        """اختبار إنشاء صورة عقار"""
        # Note: This would need actual image file in real test
        image = PropertyImage.objects.create(
            property=self.property,
            caption='الصورة الرئيسية',
            sort_order=1,
            is_primary=True
        )
        self.assertTrue(isinstance(image, PropertyImage))
        self.assertEqual(image.property, self.property)


class MessageModelTest(TestCase):
    """اختبارات نظام الرسائل"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.property = Property.objects.create(
            type='land',
            status='ready',
            district='الحي الصناعي',
            location='الناصرية، الحي الصناعي',
            area=500,
            price=75000000,
            description='أرض واسعة للبناء',
            phone='07701234567',
        )
    
    def test_property_inquiry_creation(self):
        """اختبار إنشاء استفسار عن عقار"""
        message = Message.objects.create(
            name='أحمد محمد',
            email='ahmed@example.com',
            phone='07801234567',
            message='أريد الاستفسار عن هذا العقار',
            message_type='property_inquiry',
            property=self.property
        )
        self.assertTrue(isinstance(message, Message))
        self.assertEqual(message.message_type, 'property_inquiry')
        self.assertEqual(message.property, self.property)


class AuctionModelTest(TestCase):
    """اختبارات نظام المزادات"""
    
    def setUp(self):
        self.property = Property.objects.create(
            type='building',
            status='ready',
            district='الحي المركزي',
            location='الناصرية، الحي المركزي',
            area=300,
            price=200000000,
            description='بناية تجارية',
            phone='07701234567',
        )
        self.auction = Auction.objects.create(
            property=self.property,
            auction_type='building',
            title='مزاد بيع بناية تجارية',
            description='بناية ممتازة في موقع استراتيجي',
            starting_price=Decimal('150000000'),
            minimum_increment=Decimal('5000000'),
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=7),
            terms='شروط المزاد...'
        )
    
    def test_auction_creation(self):
        """اختبار إنشاء مزاد"""
        self.assertTrue(isinstance(self.auction, Auction))
        self.assertEqual(self.auction.auction_type, 'building')
        self.assertEqual(self.auction.property, self.property)
    
    def test_auction_current_highest_bid(self):
        """اختبار أعلى مزايدة حالية"""
        highest = self.auction.get_current_highest_bid()
        self.assertEqual(highest, self.auction.starting_price)
    
    def test_auction_is_active(self):
        """اختبار نشاط المزاد"""
        self.assertTrue(self.auction.is_active())


class SiteSettingsTest(TestCase):
    """اختبارات إعدادات الموقع"""
    
    def test_site_settings_singleton(self):
        """اختبار أن إعدادات الموقع singleton"""
        settings1 = SiteSettings.get_solo()
        settings2 = SiteSettings.get_solo()
        self.assertEqual(settings1.pk, settings2.pk)
    
    def test_site_settings_defaults(self):
        """اختبار القيم الافتراضية"""
        settings = SiteSettings.get_solo()
        self.assertEqual(settings.site_name, 'دلال')
        self.assertEqual(settings.default_language, 'ar')
        self.assertEqual(settings.timezone, 'Asia/Baghdad')


class PropertyViewsTest(TestCase):
    """اختبارات واجهات العقارات"""
    
    def setUp(self):
        self.client = Client()
        self.property = Property.objects.create(
            type='house',
            status='ready',
            district='الحي السكني',
            location='الناصرية، الحي السكني',
            area=150,
            price=100000000,
            description='بيت جميل',
            phone='07701234567',
        )
    
    def test_homepage(self):
        """اختبار الصفحة الرئيسية"""
        response = self.client.get('')
        self.assertEqual(response.status_code, 200)
    
    def test_property_list(self):
        """اختبار قائمة العقارات"""
        response = self.client.get('/properties/')
        self.assertEqual(response.status_code, 200)
    
    def test_property_detail(self):
        """اختبار تفاصيل العقار"""
        self.property.save()
        url = reverse('property_detail', kwargs={'slug': self.property.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class PropertyFilterTest(TestCase):
    """اختبارات فلترة العقارات"""
    
    def setUp(self):
        self.client = Client()
        # Create multiple properties for filtering
        Property.objects.create(
            type='house', status='ready', district='الحي الأول',
            location='الناصرية', area=100, price=50000000,
            description='بيت صغير', phone='07701234567'
        )
        Property.objects.create(
            type='apartment', status='ready', district='الحي الثاني',
            location='الناصرية', area=80, price=40000000,
            description='شقة', phone='07701234567'
        )
        Property.objects.create(
            type='land', status='sold', district='الحي الثالث',
            location='الناصرية', area=200, price=80000000,
            description='أرض', phone='07701234567'
        )
    
    def test_filter_by_type(self):
        """اختبار الفلترة حسب النوع"""
        response = self.client.get('/properties/?type=house')
        self.assertEqual(response.status_code, 200)
    
    def test_filter_by_status(self):
        """اختبار الفلترة حسب الحالة"""
        response = self.client.get('/properties/?status=ready')
        self.assertEqual(response.status_code, 200)
    
    def test_filter_by_price_range(self):
        """اختبار الفلترة حسب نطاق السعر"""
        response = self.client.get('/properties/?min_price=30000000&max_price=60000000')
        self.assertEqual(response.status_code, 200)


class SearchTest(TestCase):
    """اختبارات البحث"""
    
    def setUp(self):
        self.client = Client()
        Property.objects.create(
            type='house', status='ready', district='الحي الجميل',
            location='الناصرية، الحي الجميل', area=120,
            price=90000000, description='بيت في حي جميل',
            phone='07701234567'
        )
    
    def test_search_by_district(self):
        """اختبار البحث حسب الحي"""
        response = self.client.get('/properties/?q=الجميل')
        self.assertEqual(response.status_code, 200)
    
    def test_search_by_description(self):
        """اختبار البحث في الوصف"""
        response = self.client.get('/properties/?q=بيت')
        self.assertEqual(response.status_code, 200)


class AdminTest(TestCase):
    """اختبارات لوحة التحكم"""
    
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )
    
    def test_admin_login(self):
        """اختبار دخول المسؤول"""
        self.client.login(username='admin', password='admin123')
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
    
    def test_admin_property_list(self):
        """اختبار قائمة العقارات في لوحة التحكم"""
        self.client.login(username='admin', password='admin123')
        response = self.client.get('/admin/properties/property/')
        self.assertEqual(response.status_code, 200)
