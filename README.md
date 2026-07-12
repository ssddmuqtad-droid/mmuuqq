# دلال - منصة العقارات العراقية

منصة عقارات عراقية متكاملة مبنية على Django لإدارة وعرض العقارات (أراضي، بيوت، بنايات، شقق) مع نظام فلترة متقدم ولوحة تحكم شاملة.

## 🏠 المميزات

### نظام العقارات
- **نظام عقارات كامل**: إدارة كاملة للعقارات مع معلومات تفصيلية وصور
- **فلترة متقدمة**: بحث وفلترة حسب النوع، الحالة، السعر، الموقع، والمزيد
- **خرائط تفاعلية**: دعم خرائط Leaflet لعرض المواقع
- **أنواع متعددة**: أراضي، بيوت، بنايات، شقق، محلات تجارية، مستودعات
- **فنادق ومنتجعات**: نظام حجز الفنادق والمنتجعات

### نظام الدلالين
- **لوحة تحكم الدلال**: إدارة كاملة للعقارات والرسائل
- **نظام الاشتراكات**: خطط اشتراك متعددة مع إدارة التجديدات
- **إحصائيات متقدمة**: رسوم بيانية تفاعلية لتتبع الأداء
- **حماية المنشورات**: نظام تجميد وحذف تلقائي للمنشورات المنتهية
- **منع تجاوز الحدود**: حماية ضد تجاوز عدد العقارات المسموح به

### الأمان والحماية
- **حماية شاملة**: CSRF، XSS، SQL injection
- **تتبع الأنشطة**: تسجيل جميع العمليات الحساسة
- **إدارة الصلاحيات**: نظام صلاحيات متقدم
- **تأمين الاشتراكات**: حماية ضد تجاوز وقت الاشتراك

### الميزات التقنية
- **تصميم متجاوب**: واجهة عربية RTL بالكامل مع دعم الجوال
- **SEO محسن**: sitemap.xml و robots.txt و meta tags
- **أمان متقدم**: حماية CSRF، rate limiting، وسياسات أمان محدثة
- **نظام المهام المجدولة**: أوامر إدارة للحذف التلقائي
- **دعم PostgreSQL**: جاهز للاستضافة على Railway

## 📁 هيكل المشروع

```
moq-main/
├── dalal_project/          # إعدادات Django الرئيسية
│   ├── settings.py         # إعدادات المشروع
│   ├── urls.py             # مسارات URL
│   └── wsgi.py             # WSGI configuration
├── properties/             # تطبيق العقارات
│   ├── models.py          # نماذج البيانات
│   ├── views.py           # الوظائف الرئيسية
│   ├── forms.py           # النماذج
│   ├── admin.py           # لوحة التحكم
│   ├── management/        # أوامر الإدارة
│   │   └── commands/      # أوامر الحذف التلقائي
│   └── templates/         # قوالب HTML
├── static/                # الملفات الثابتة (CSS, JS)
├── templates/             # القوالب الإضافية
├── media/                 # الصور والملفات المرفوعة
├── logs/                  # سجلات النظام
├── requirements.txt       # المكتبات المطلوبة
├── Procfile              # تكوين Heroku/Railway
├── runtime.txt           # إصدار Python
├── .env.example          # مثال متغيرات البيئة
├── railway.toml          # تكوين Railway
├── docker-compose.yml    # تكوين Docker
└── manage.py             # أوامر Django
```

## 🚀 التشغيل المحلي

### المتطلبات:
- Python 3.10+
- Django 5.0+
- virtualenv
- Git

### خطوات التشغيل:

1. **إنشاء البيئة الافتراضية:**
```bash
python -m venv venv
```

2. **تفعيل البيئة الافتراضية:**
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. **تثبيت المتطلبات:**
```bash
pip install -r requirements.txt
```

4. **إعداد قاعدة البيانات:**
```bash
python manage.py migrate
```

5. **إنشاء مستخدم مسؤول:**
```bash
python manage.py createsuperuser
```

6. **تشغيل الخادم:**
```bash
python manage.py runserver
```

7. **فتح المتصفح:**
```
http://localhost:8000
```

## 🔐 بيانات الدخول

- **لوحة التحكم**: `/admin/`
- **اسم المستخدم الافتراضي**: admin
- **كلمة المرور الافتراضية**: admin123

## 🗄️ قاعدة البيانات

يدعم المشروع نوعين من قواعد البيانات:

1. **SQLite** (الافتراضي للتنمية):
```env
# يستخدم تلقائياً في وضع التطوير
DEBUG=True
```

2. **PostgreSQL** (للإنتاج على Railway):
```env
# Railway يضيف DATABASE_URL تلقائياً عند إضافة خدمة PostgreSQL
# أو يمكنك تحديده يدوياً:
DATABASE_URL=postgres://user:password@host:5432/dbname
```

### إعدادات قاعدة البيانات في Railway:
- سيقوم Railway تلقائياً بإضافة `DATABASE_URL` عند إنشاء خدمة PostgreSQL
- المشروع يدعم الاتصال التلقائي بقاعدة بيانات PostgreSQL
- يمكن استخدام SQLite كخيار احتياطي بتعيين `ALLOW_SQLITE_FALLBACK=True`

## 🌐 النشر على Railway

### خطوات النشر:

1. **ربط المستودع على Railway عبر GitHub:**
   - افتح موقع Railway: https://railway.app
   - سجل الدخول باستخدام GitHub
   - اضغط على "New Project"
   - اختر "Deploy from GitHub repo"
   - حدد مستودع `mmuuqq`

2. **إضافة خدمة PostgreSQL:**
   - في مشروع Railway، اضغط على "New Service"
   - اختر "Database"
   - اختر "PostgreSQL"
   - سيتم إضافة `DATABASE_URL` تلقائياً

3. **إعدادات متغيرات البيئة:**
   - اذهب إلى إعدادات المشروع في Railway
   - أضف المتغيرات التالية:
     ```
     SECRET_KEY=your-secure-secret-key-here
     DEBUG=False
     ALLOWED_HOSTS=*
     CSRF_TRUSTED_ORIGINS=https://*
     ```
   - Railway سيقوم تلقائياً بإضافة `DATABASE_URL`

4. **النشر التلقائي:**
   - سيقوم Railway ببناء ونشر المشروع تلقائياً عند كل دفع إلى GitHub
   - يمكنك مراقبة حالة النشر في لوحة تحكم Railway

### ملفات النشر المهمة:
- `railway.toml` - تكوين Railway الرئيسي
- `Procfile` - أمر بدء التشغيل
- `requirements.txt` - المكتبات المطلوبة
- `runtime.txt` - إصدار Python (3.12)
- `.env.example` - مثال متغيرات البيئة

## 📊 أنواع العقارات

- قطعة أرض
- بيت
- بناية
- شقة
- محل تجاري
- مستودع

## 🔄 حالات العقارات

- جاهز
- قيد الإنشاء
- مباع
- للإيجار

## 🛠️ التقنيات المستخدمة

### Backend
- **Django 5.0+**: إطار العمل الرئيسي
- **Python 3.12**: لغة البرمجة
- **PostgreSQL**: قاعدة البيانات (الإنتاج على Railway)
- **SQLite**: قاعدة البيانات (التنمية)
- **Gunicorn**: خادم WSGI للإنتاج
- **WhiteNoise**: تقديم الملفات الثابتة

### Frontend
- **HTML5/CSS3/JavaScript**: الواجهة الأمامية
- **Chart.js**: الرسوم البيانية التفاعلية
- **Leaflet**: الخرائط التفاعلية
- **Bootstrap**: إطار العمل CSS

### الأمان والصلاحيات
- **python-social-auth**: المصادقة الاجتماعية (Google, Facebook)
- **django-cors-headers**: دعم CORS
- **django-filter**: فلترة متقدمة
- **Django REST Framework**: API REST

### المهام المجدولة
- **auto_freeze_expired**: تجميد المنشورات المنتهية
- **cleanup_expired_properties**: حذف المنشورات المجمدة

## 🎨 المميزات التصميمية

- دعم كامل للغة العربية (RTL)
- تصميم متجاوب يعمل على جميع الأجهزة
- الوضع الليلي
- رسوم متحركة سلسة
- شريط تنقل سفلي للجوال
- أزرار واتساب للتواصل

## 🔧 أوامر Django المفيدة

```bash
# تشغيل الخادم
python manage.py runserver

# إنشاء migrations جديدة
python manage.py makemigrations

# تطبيق migrations
python manage.py migrate

# جمع الملفات الثابتة
python manage.py collectstatic

# إنشاء مستخدم مسؤول
python manage.py createsuperuser

# فحص المشروع
python manage.py check

# تجميد المنشورات المنتهية
python manage.py auto_freeze_expired

# حذف المنشورات المجمدة (وضع التجربة)
python manage.py cleanup_expired_properties --dry-run

# حذف المنشورات المجمدة (وضع فعلي)
python manage.py cleanup_expired_properties --days=7
```

## 🔒 الأمان

### حماية شاملة
- حماية CSRF مفعلة
- حماية XSS ضد الهجمات
- حماية SQL injection
- Rate limiting للنماذج
- تأمين الكوكيز
- SSL Redirect في الإنتاج
- HSTS Headers
- Content Security Headers

### حماية الاشتراكات
- منع تجاوز عدد العقارات
- نظام تجميد المنشورات المنتهية
- حذف تلقائي للمنشورات المجمدة
- تتبع IP و User Agent
- تسجيل جميع العمليات الحساسة

## 📱 التواصل

- نظام مراسلة مدمج
- عرض أرقام الهاتف
- دعم واتساب

## 🔧 استكشاف الأخطاء

### مشاكل شائعة:

1. **مشاكل البيئة الافتراضية:**
```bash
# إعادة إنشاء البيئة
deactivate
rm -rf venv
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

2. **مشاكل قاعدة البيانات:**
```bash
# حذف وإعادة إنشاء قاعدة البيانات
rm db.sqlite3
python manage.py migrate
```

3. **مشاكل الملفات الثابتة:**
```bash
# إعادة جمع الملفات الثابتة
python manage.py collectstatic --noinput --clear
```

4. **مشاكل الاشتراكات:**
```bash
# تجميد المنشورات المنتهية يدوياً
python manage.py auto_freeze_expired

# حذف المنشورات المجمدة
python manage.py cleanup_expired_properties --dry-run
```

## 📚 ملفات إضافية

- `DEPLOYMENT.md` - دليل النشر التفصيلي
- `DEPLOYMENT_GUIDE.md` - دليل النشر على Railway
- `INSTALLATION_GUIDE.md` - دليل التثبيت
- `QUICKSTART.md` - بدء سريع
- `RAILWAY_DOMAIN_SETUP.md` - إعداد النطاق المخصص
- `ROUTES_API.md` - وثائق API
- `SCHEDULED_TASKS_SETUP.md` - إعداد المهام المجدولة
- `SETUP.md` - إعداد المشروع

## 📄 الترخيص

جميع الحقوق محفوظة © 2026 دلال