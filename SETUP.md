# دليل إعداد مشروع دلال (Dalal) للعقارات

## المتطلبات الأساسية
- Python 3.12+ أو 3.13+
- pip أو virtualenv
- SQLite (قاعدة البيانات الافتراضية للتطوير)

## الخطوة 1: إعداد البيئة الافتراضية

### Windows
```bash
# إنشاء بيئة افتراضية
python -m venv venv

# تفعيل البيئة الافتراضية
venv\Scripts\activate
```

### Linux/Mac
```bash
python3 -m venv venv
source venv/bin/activate
```

## الخطوة 2: تثبيت المتطلبات

```bash
pip install -r requirements.txt
```

### المتطلبات الرئيسية:
- Django >= 5.0
- python-dotenv
- Pillow (معالجة الصور)
- gunicorn (خادم الإنتاج)
- django-cors-headers
- django-filter

## الخطوة 3: تكوين البيئة

### نسخ ملف البيئة
```bash
cp .env.example .env
```

### تحرير ملف `.env`
```env
# Django
SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=True  # غيره إلى False في الإنتاج
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_ENGINE=sqlite  # أو postgresql أو mysql
```

## الخطوة 4: تشغيل الهجرات

```bash
python manage.py migrate
```

## الخطوة 5: إنشاء مستخدم المسؤول

```bash
python manage.py createsuperuser
```

اتبع التعليمات على الشاشة لإنشاء حساب إداري.

## الخطوة 6: تشغيل خادم التطوير

```bash
python manage.py runserver
```

سيكون التطبيق متاحاً على: **http://127.0.0.1:8000/**

### الروابط الهامة:
- **الصفحة الرئيسية**: http://127.0.0.1:8000/
- **لوحة التحكم**: http://127.0.0.1:8000/dashboard/ (يتطلب تسجيل الدخول)
- **إدارة Django**: http://127.0.0.1:8000/admin/

## بنية المشروع

```
acakar/
├── dalal_project/           # إعدادات المشروع الرئيسية
│   ├── settings.py          # الإعدادات الرئيسية
│   ├── urls.py              # المسارات الرئيسية
│   ├── wsgi.py              # تكوين WSGI
│   └── asgi.py              # تكوين ASGI
├── properties/              # تطبيق إدارة العقارات
│   ├── models.py            # نماذج قاعدة البيانات
│   ├── views.py             # المناظر/الدوال
│   ├── forms.py             # نماذج HTML
│   ├── urls.py              # مسارات التطبيق
│   ├── admin.py             # إدارة Django
│   ├── utils.py             # دوال مساعدة
│   └── migrations/          # هجرات قاعدة البيانات
├── templates/               # قوالب HTML
├── static/                  # ملفات ثابتة (CSS، JavaScript)
├── manage.py                # أداة إدارة Django
├── requirements.txt         # المتطلبات
├── .env.example             # نموذج متغيرات البيئة
└── build.sh                 # سكريبت البناء
```

## أوامر Django المهمة

```bash
# فحص الأخطاء
python manage.py check

# تطبيق الهجرات
python manage.py migrate

# إنشاء هجرة جديدة
python manage.py makemigrations

# تجميع الملفات الثابتة
python manage.py collectstatic

# فتح قشرة Python
python manage.py shell

# تشغيل الاختبارات
python manage.py test
```

## إعدادات قاعدة البيانات

### SQLite (التطوير - الافتراضي)
```env
DB_ENGINE=sqlite
```

### PostgreSQL (الإنتاج)
```env
DB_ENGINE=postgresql
DATABASE_URL=postgres://user:password@localhost:5432/dalal
# أو
DB_NAME=dalal
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432
```

### MySQL
```env
DB_ENGINE=mysql
DB_NAME=dalal_db
DB_USER=root
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=3306
```

## النشر على Railway

### الملفات المطلوبة:
- `railway.toml` - تكوين Railway
- `Procfile` - تحديد أوامر البدء
- `build.sh` - سكريبت البناء
- `.railwayignore` - الملفات المراد تجاهلها

### خطوات النشر:
1. دفع التغييرات إلى GitHub
2. ربط مستودع على Railway
3. إضافة متغيرات البيئة الإنتاجية
4. سيتم البناء والنشر تلقائياً

## المشاكل الشائعة والحلول

### مشكلة: `ModuleNotFoundError: No module named 'django_filters'`
**الحل**: `pip install -r requirements.txt`

### مشكلة: `ImproperlyConfigured: SECRET_KEY`
**الحل**: أضف `SECRET_KEY` في ملف `.env`

### مشكلة: خطأ في قاعدة البيانات
**الحل**: 
```bash
python manage.py migrate --run-syncdb
```

### مشكلة: فشل Collectstatic
**الحل**:
```bash
python manage.py collectstatic --noinput --clear
```

## ميزات التطبيق

### للزوار:
- 🔍 بحث متقدم عن العقارات
- 📁 عرض تفاصيل العقار مع الصور
- 💬 نموذج اتصال
- 📍 خريطة موقع العقار
- 🌐 دعم اللغة العربية الكامل

### للمسؤول:
- 📊 لوحة تحكم شاملة
- ➕ إضافة/تعديل/حذف العقارات
- 🖼️ إدارة معرض الصور
- 📧 إدارة الرسائل الواردة
- ⚙️ تحديث إعدادات الموقع

## الأمان

✅ حماية CSRF
✅ رؤوس أمان HTTP
✅ معدل تحديد IP للدخول والرسائل
✅ خوارزميات تجزئة كلمات المرور
✅ SSL/HTTPS في الإنتاج
✅ إعدادات SameSite Cookies

## الدعم والتطوير

للمساهمة أو الإبلاغ عن المشاكل:
1. انسخ المشروع
2. أنشئ فرعاً جديداً
3. أجرِ التغييرات
4. قدّم طلب دمج

---

**آخر تحديث**: يونيو 2026
**الإصدار**: 1.0.0
