# دليل التثبيت والإعداد - منصة دلال

## المتطلبات الأساسية

- Python 3.8 أو أحدث
- pip (مدير حزم Python)
- Git (اختياري)

## خطوات التثبيت

### 1. تثبيت المكتبات المطلوبة

قم بتشغيل الأمر التالي لتثبيت جميع المكتبات المطلوبة:

```bash
pip install -r requirements.txt
```

### 2. إعداد متغيرات البيئة

أنشئ ملف `.env` في جذر المشروع (إذا لم يكن موجوداً) وأضف المتغيرات التالية:

```env
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
```

### 3. تطبيق الترحيلات (Migrations)

```bash
python manage.py migrate
```

### 4. إنشاء مستخدم مدير (اختياري)

```bash
python manage.py createsuperuser
```

### 5. تشغيل الخادم

```bash
python manage.py runserver
```

## المكتبات الجديدة المضافة

تم إضافة المكتبات التالية إلى المشروع:

### للأداء والـ Caching
- `redis>=5.0.0` - قاعدة بيانات Redis للـ caching
- `django-redis>=5.4.0` - تكامل Django مع Redis

### للمصادقة الثنائية (2FA)
- `pyotp>=2.9.0` - مكتبة TOTP للمصادقة الثنائية
- `qrcode>=7.4.0` - توليد QR Codes
- `django-ratelimit>=4.1.0` - تحديد معدل الطلبات

### للإشعارات الحية (WebSocket)
- `channels>=4.0.0` - Django Channels للـ WebSocket
- `channels-redis>=4.2.0` - تكامل Channels مع Redis
- `daphne>=4.0.0` - خادم ASGI للـ WebSocket

### لتوثيق API
- `djangorestframework>=3.14.0` - Django REST Framework
- `drf-yasg>=1.21.0` - توثيق Swagger/OpenAPI

## الميزات الجديدة

### 1. نظام اختبارات شامل
- ملف `properties/tests.py` يحتوي على اختبارات للنماذج والواجهات

### 2. تحسين الأداء مع Redis Cache
- ملف `properties/cache_utils.py` يحتوي على أدوات caching
- دعم cache للجلسات والبيانات

### 3. نظام التقييمات
- `PropertyRating` - تقييمات العقارات مع تقييمات مفصلة
- `BrokerRating` - تقييمات الدلالين مع تقييمات مفصلة

### 4. محرك بحث وفلترة متقدم
- ملف `properties/search_utils.py` يحتوي على:
  - `PropertySearchEngine` - محرك بحث للعقارات
  - `BrokerSearchEngine` - محرك بحث للدلالين
  - `PropertyRecommendationEngine` - محرك التوصيات
  - `AdvancedFilterBuilder` - بناء الفلاتر المتقدمة

### 5. المصادقة الثنائية (2FA)
- `TwoFactorAuth` - نموذج المصادقة الثنائية
- `SecurityLog` - سجل الأمان
- دعم TOTP و SMS والبريد الإلكتروني

### 6. الإشعارات الحية (WebSocket)
- ملف `dalal_project/consumers.py` - WebSocket consumers
- ملف `dalal_project/routing.py` - WebSocket routing
- دعم الإشعارات والمزادات والدردشة الحية

### 7. تصميم واجهة مستخدم حديث
- ملف `static/css/modern-design.css` - نظام تصميم حديث
- دعم Dark Mode
- مكونات UI حديثة

### 8. لوحة تحكم تحليلية
- ملف `properties/analytics.py` - أدوات التحليل
- `AnalyticsDashboard` - إحصائيات عامة
- `RealTimeAnalytics` - تحليلات الوقت الفعلي
- `ReportGenerator` - توليد التقارير

### 9. توثيق API
- Swagger UI: `http://localhost:8000/swagger/`
- ReDoc: `http://localhost:8000/redoc/`
- JSON Schema: `http://localhost:8000/swagger.json`

## الترحيلات الجديدة

تم إنشاء الترحيلات التالية:

- `0028_brokerrating_propertyrating_delete_usersettings_and_more.py` - نماذج التقييمات
- `0029_twofactorauth_securitylog.py` - المصادقة الثنائية وسجل الأمان

## استكشاف الأخطاء

### خطأ: ModuleNotFoundError: No module named 'channels'
**الحل:** قم بتثبيت المكتبات المطلوبة:
```bash
pip install -r requirements.txt
```

### خطأ: ModuleNotFoundError: No module named 'djangorestframework'
**الحل:** قم بتثبيت Django REST Framework:
```bash
pip install djangorestframework
```

### خطأ: ModuleNotFoundError: No module named 'drf_yasg'
**الحل:** قم بتثبيت drf-yasg:
```bash
pip install drf-yasg
```

### خطأ: Redis connection error
**الحل:** تأكد من تشغيل Redis أو استخدم cache backend الافتراضي (LocMemCache)

## التشغيل في بيئة الإنتاج

### Railway
1. ارفع المشروع إلى GitHub
2. قم بربطه بـ Railway
3. أضف خدمات PostgreSQL و Redis
4. اضبط متغيرات البيئة في Railway

### Docker
```bash
docker-compose up -d
```

## الدعم

للمساعدة والدعم، يرجى مراجعة:
- README.md - معلومات عامة عن المشروع
- DEPLOYMENT.md - دليل النشر
- SECURITY_REPORT.md - تقرير الأمان

## الأخطاء التي تم إصلاحها

1. **consumers.py** - إضافة استيراد `timezone` المفقود
2. **cache_utils.py** - إصلاح استخدام `cache.delete_pattern()` غير المدعوم في cache backend الافتراضي

## ملاحظات مهمة

- تأكد من تثبيت جميع المكتبات قبل تشغيل المشروع
- في بيئة التطوير، يتم استخدام InMemoryChannelLayer للـ WebSocket
- في بيئة الإنتاج، يجب استخدام Redis للـ WebSocket و caching
- تأكد من تطبيق الترحيلات بعد تثبيت المكتبات الجديدة
