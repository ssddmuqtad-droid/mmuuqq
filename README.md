# دلال - منصة العقارات العراقية

منصة عقارات عراقية متكاملة مبنية على Django لإدارة وعرض العقارات (أراضي، بيوت، بنايات، شقق) مع نظام فلترة متقدم ولوحة تحكم شاملة.

## 🏠 المميزات

- **نظام عقارات كامل**: إدارة كاملة للعقارات مع معلومات تفصيلية وصور
- **فلترة متقدمة**: بحث وفلترة حسب النوع، الحالة، السعر، الموقع، والمزيد
- **لوحة تحكم الدلال**: إدارة كاملة للعقارات والرسائل
- **نظام المفضلة والمقارنة**: حفظ العقارات المفضلة ومقارنة بينها
- **خرائط تفاعلية**: دعم خرائط Leaflet لعرض المواقع
- **تصميم متجاوب**: واجهة عربية RTL بالكامل مع دعم الجوال
- **SEO محسن**: sitemap.xml و robots.txt و meta tags
- **أمان متقدم**: حماية CSRF، rate limiting، وسياسات أمان محدثة

## 📁 هيكل المشروع

```
acakar/
├── dalal_project/          # إعدادات Django الرئيسية
├── properties/             # تطبيق العقارات
│   ├── models.py          # نماذج البيانات
│   ├── views.py           # الوظائف الرئيسية
│   ├── forms.py           # النماذج
│   └── templates/         # قوالب HTML
├── static/                # الملفات الثابتة (CSS, JS)
├── templates/             # القوالب الإضافية
├── media/                 # الصور والملفات المرفوعة
├── logs/                  # سجلات النظام
├── requirements.txt       # المكتبات المطلوبة
├── railway.toml          # تكوين Railway
├── Procfile              # تكوين Heroku/Railway
└── manage.py             # أوامر Django
```

## 🚀 التشغيل المحلي

### المتطلبات:
- Python 3.10+
- Django 5.0+
- virtualenv

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

## �️ قاعدة البيانات

يدعم المشروع ثلاثة أنواع من قواعد البيانات:

1. **SQLite** (الافتراضي للتنمية):
```env
DB_ENGINE=sqlite
```

2. **MySQL** (للإنتاج على Railway):
```env
DB_ENGINE=mysql
DATABASE_URL=mysql://user:password@host:3306/dbname
```

3. **MySQL** (اختياري):
```env
DB_ENGINE=mysql
DB_NAME=dalal_db
DB_USER=root
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=3306
```

## 🌐 النشر على Railway عبر GitHub

### خطوات النشر:

1. **ربط المستودع على Railway عبر GitHub:**
   - افتح موقع Railway: https://railway.app
   - سجل الدخول باستخدام GitHub
   - اضغط على "New Project"
   - اختر "Deploy from GitHub repo"
   - حدد مستودع `acakar`

2. **إعدادات البناء التلقائية:**
   - سيقوم Railway تلقائياً بكشف مشروع Django
   - سيستخدم ملف `railway.toml` للتكوين
   - سيتم بناء المشروع تلقائياً

3. **إضافة متغيرات البيئة في Railway:**
   - اذهب إلى إعدادات المشروع في Railway
   - أضف المتغيرات التالية:
     ```
     SECRET_KEY=your-secure-secret-key-here
     DEBUG=False
     ALLOWED_HOSTS=*
     CSRF_TRUSTED_ORIGINS=https://*
     DB_ENGINE=mysql
     ```
   - Railway سيقوم تلقائياً بإضافة `DATABASE_URL` عند إنشاء قاعدة بيانات MySQL

4. **النشر التلقائي:**
   - سيقوم Railway ببناء ونشر المشروع تلقائياً عند كل دفع إلى GitHub
   - يمكنك مراقبة حالة النشر في لوحة تحكم Railway

### ملفات النشر المهمة:
- `railway.toml` - تكوين Railway الرئيسي
- `Procfile` - أمر بدء التشغيل
- `requirements.txt` - المكتبات المطلوبة
- `runtime.txt` - إصدار Python (3.10)

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

- **Django 5.0+**: إطار العمل الرئيسي
- **Python 3.10+**: لغة البرمجة
- **MySQL**: قاعدة البيانات (الإنتاج على Railway)
- **SQLite**: قاعدة البيانات (التنمية)
- **WhiteNoise**: تقديم الملفات الثابتة
- **Gunicorn**: خادم WSGI
- **Leaflet**: الخرائط التفاعلية
- **HTML5/CSS3/JavaScript**: الواجهة الأمامية

## 🎨 المميزات التصميمية

- دعم كامل للغة العربية (RTL)
- تصميم متجاوب يعمل على جميع الأجهزة
- الوضع الليلي
- رسوم متحركة سلسة
- شريط تنقل سفلي للجوال
- أزرار واتساب للتواصل

## � أوامر Django المفيدة

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

# استيراد بيانات تجريبية
python manage.py load_sample_data
```

## � الأمان

- حماية CSRF مفعلة
- Rate limiting للنماذج
- تأمين الكوكيز
- SSL Redirect في الإنتاج
- HSTS Headers
- Content Security Headers

## 📱 التواصل

- نظام مراسلة مدمج
- عرض أرقام الهاتف
- دعم واتساب

## � استكشاف الأخطاء

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

## 📄 الترخيص

جميع الحقوق محفوظة © 2026 دلال