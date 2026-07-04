# خريطة مسارات التطبيق (Routes & Views)

## 🏠 المسارات العامة (Public Routes)

### الصفحات الرئيسية

| المسار | الدالة | الوصف |
|--------|--------|------|
| `/` | `home()` | الصفحة الرئيسية - عرض العقارات مع البحث |
| `/about/` | `about_page()` | صفحة من نحن |
| `/contact/` | `contact_page()` | صفحة التواصل |
| `/robots.txt` | Django Template | ملف robots |
| `/health/` | JSON | فحص صحة التطبيق |

### عرض وإدارة العقارات

| المسار | الدالة | الوصف |
|--------|--------|------|
| `/property/<slug>/` | `property_detail()` | تفاصيل العقار |
| `/property/id/<id>/` | `property_detail_legacy()` | رابط قديم (إعادة توجيه) |
| `/send-message/` | `send_message()` | إرسال رسالة استفسار |

---

## 🔐 مسارات المسؤول (Staff Only - يتطلب تسجيل الدخول)

### الدخول والخروج

| المسار | الدالة | الوصف | طريقة |
|--------|--------|------|--------|
| `/login/` | `login_view()` | دخول المسؤول | GET, POST |
| `/logout/` | `logout_view()` | خروج المسؤول | GET |

### لوحة التحكم

| المسار | الدالة | الوصف | طريقة |
|--------|--------|------|--------|
| `/dashboard/` | `dashboard()` | لوحة التحكم الرئيسية | GET |
| `/dashboard/settings/` | `update_site_settings()` | تحديث إعدادات الموقع | POST |
| `/dashboard/add/` | `add_property()` | إضافة عقار جديد | POST |
| `/dashboard/edit/<id>/` | `edit_property()` | تعديل عقار | GET, POST |
| `/dashboard/delete/<id>/` | `delete_property()` | حذف عقار | POST |
| `/dashboard/image/delete/<id>/` | `delete_property_image()` | حذف صورة | POST |
| `/dashboard/message/<id>/read/` | `mark_message_read()` | وضع علامة على الرسالة | POST |

---

## 🗺️ خريطة الموقع والـ SEO

| المسار | الدالة | الوصف |
|--------|--------|------|
| `/sitemap.xml` | Django Sitemap | خريطة الموقع (XML) |
| `/sitemap.xml?section=properties` | Property Sitemap | عقارات فقط |
| `/sitemap.xml?section=static` | Static Sitemap | صفحات ثابتة |

---

## 📋 نماذج (Forms)

### PropertySearchForm
- `q` - بحث عام
- `province` - المحافظة
- `city` - المدينة
- `district` - المنطقة
- `type` - نوع العقار
- `status` - حالة العقار
- `price_min`, `price_max` - نطاق السعر
- `area_min`, `area_max` - نطاق المساحة
- `bedrooms` - عدد الغرف
- `sort` - الترتيب

### PropertyForm
- `title`, `type`, `status`
- `province`, `city`, `district`, `location`
- `area`, `price`, `description`
- `phone`, `bedrooms`, `bathrooms`, `floors`, `year_built`
- `parking`, `furnished`
- `latitude`, `longitude` (خريطة)
- `is_featured`, `is_promoted`
- `image` (صورة رئيسية)

### MessageForm
- `name` - الاسم
- `email` - البريد الإلكتروني
- `phone` - رقم الهاتف
- `message` - الرسالة

### SiteSettingsForm
- `site_name`, `tagline`
- `broker_phone`, `broker_email`, `broker_address`
- `whatsapp`
- `mission`, `meta_description`
- `facebook_url`, `instagram_url`

---

## 🗄️ نماذج قاعدة البيانات (Models)

### Property
المتغيرات الرئيسية:
- `title` - عنوان الإعلان
- `slug` - الرابط الودود (يُولَّد تلقائياً)
- `type` - نوع العقار (أرض، بيت، شقة، إلخ)
- `status` - الحالة (جاهز، قيد الإنشاء، مباع، إيجار)
- `province`, `city`, `district`, `location` - الموقع
- `area` - المساحة بالمتر المربع
- `price` - السعر بالدينار العراقي
- `description` - الوصف التفصيلي
- `phone` - رقم التواصل
- `bedrooms`, `bathrooms`, `floors`, `year_built`
- `parking`, `furnished` - مميزات إضافية
- `latitude`, `longitude` - إحداثيات الخريطة
- `image` - الصورة الرئيسية
- `is_featured`, `is_promoted` - عقار مميز/ترويجي
- `views_count` - عدد المشاهدات
- `created_at`, `updated_at` - التواريخ

الدوال المهمة:
- `get_absolute_url()` - الرابط الدائم
- `get_all_images()` - كل الصور (معرض)
- `get_main_image()` - الصورة الرئيسية
- `increment_views()` - زيادة المشاهدات
- `has_map()` - هل له خريطة؟
- `price_formatted` - السعر منسق

### PropertyImage
- `property` - العقار (مفتاح أجنبي)
- `image` - الصورة
- `caption` - تعليق
- `sort_order` - الترتيب
- `is_primary` - هل رئيسية؟
- `created_at` - التاريخ

### Message
- `name` - اسم المرسل
- `email` - البريد الإلكتروني
- `phone` - الهاتف
- `message` - نص الرسالة
- `property` - العقار المتعلق (اختياري)
- `is_read` - هل تمت قراءتها؟
- `created_at` - التاريخ

### SiteSettings
إعدادات الموقع (نموذج واحد فقط):
- `site_name` - اسم الموقع
- `tagline` - الشعار
- `broker_phone`, `broker_email`, `broker_address`
- `whatsapp`
- `about_title`, `about_content` - من نحن
- `mission` - الرسالة
- `meta_description` - وصف SEO
- `facebook_url`, `instagram_url`

---

## 🔧 الدوال المساعدة (Utils)

### filter_properties(queryset, params)
تطبيق مرشحات البحث:
- بحث بالنص
- تصفية حسب المحافظة والمدينة
- نطاق السعر والمساحة
- عدد الغرف

### sort_properties(queryset, sort_key)
ترتيب العقارات:
- الأحدث
- السعر (تصاعدي/تنازلي)
- المساحة (تصاعدي/تنازلي)
- الأكثر مشاهدة

### get_public_properties()
الحصول على العقارات المتاحة (ليست مباعة)

### save_gallery_images(property_obj, files)
حفظ صور المعرض

---

## 🛡️ المعايير الأمنية (Decorators)

### @rate_limit(key_prefix, limit, period)
معايرة معدل الطلبات:
```python
@rate_limit('login', limit=5, period=300)  # 5 محاولات كل 5 دقائق
def login_view(request): ...

@rate_limit('message', limit=5, period=300)  # 5 رسائل كل 5 دقائق
def send_message(request): ...
```

### @login_required
يتطلب تسجيل الدخول

### @staff_required
يتطلب أن يكون موظفاً (مسؤولاً)

### @require_http_methods(['GET', 'POST'])
تحديد طرق HTTP المسموحة

### @require_POST
السماح بـ POST فقط

---

## 📊 الخوارزميات

### توليد الـ Slug
```python
slug = slugify(f'{title}-{city}-{pk}')
# إذا كان مستخدماً: slug = f'{base}-{counter}'
```

### حفظ صورة العقار
```python
# المسار: properties/{property_id}_{random_hash}.{ext}
def property_image_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()[:10]
    prop_id = getattr(instance, 'property_id', None) or instance.id
    name = uuid.uuid4().hex[:10]
    return os.path.join('properties/', f'{prop_id}_{name}.{ext}')
```

### معايرة معدل الطلبات
```python
# حفظ في الـ cache مع مفتاح يعتمد على IP والـ key_prefix
# إذا تجاوز الحد: HttpResponseForbidden
```

---

## 🌍 البيانات الثابتة (Constants)

### IRAQ_GOVERNORATES
قائمة 18 محافظة عراقية

### GOVERNORATE_CITIES
قاموس يحتوي على مدن كل محافظة (40+ مدينة)

### SORT_CHOICES
خيارات الترتيب:
- newest (الأحدث)
- price_asc (السعر: من الأقل)
- price_desc (السعر: من الأعلى)
- area_asc (المساحة: من الأصغر)
- area_desc (المساحة: من الأكبر)
- views (الأكثر مشاهدة)

### PROPERTY_TYPES
أنواع العقارات: أرض، بيت، بناية، شقة، محل، مستودع

### STATUS_CHOICES
حالات العقار: جاهز، قيد الإنشاء، مباع، إيجار

---

## 📱 معالجات السياق (Context Processors)

### site_context(request)
يوفر للقوالب:
- `site_settings` - إعدادات الموقع
- `governorates` - قائمة المحافظات
- `governorate_cities_json` - JSON للمدن

---

## 🔌 الـ Middleware

### SecurityHeadersMiddleware
إضافة رؤوس الأمان:
- X-Content-Type-Options
- X-Frame-Options
- Referrer-Policy
- Permissions-Policy
- Strict-Transport-Security (HTTPS)

---

## 📡 طرق الوصول إلى البيانات

### البحث
```
GET /?q=شقة&province=baghdad&price_min=100000&price_max=500000&sort=price_asc
```

### التصفح
```
GET /?province=baghdad&city=بغداد&bedrooms=2
```

### الترتيب
```
GET /?sort=newest|price_asc|price_desc|area_asc|area_desc|views
```

---

## 🧪 أمثلة على الاستخدام

### إضافة عقار (في الكود)
```python
from properties.models import Property

prop = Property.objects.create(
    title="شقة فاخرة في بغداد",
    type="apartment",
    status="ready",
    province="baghdad",
    city="بغداد",
    area=150,
    price=200000000,
    description="شقة حديثة مع جميع المرافق",
    phone="07701234567"
)
```

### البحث
```python
from properties.models import Property
from properties.utils import filter_properties, sort_properties

params = {'q': 'شقة', 'province': 'baghdad', 'sort': 'price_asc'}
results = filter_properties(Property.objects.all(), params)
results = sort_properties(results, 'price_asc')
```

---

**آخر تحديث**: يونيو 4، 2026
