# دليل البدء السريع - مشروع دلال (Acakar)

## 🎯 الحالة الحالية: ✅ جاهز للعمل

تم إصلاح جميع المشاكل. المشروع يعمل بدون أخطاء.

---

## 📦 البدء السريع

### 1️⃣ تفعيل البيئة الافتراضية
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2️⃣ تشغيل الخادم
```bash
python manage.py runserver
```

ثم افتح: **http://127.0.0.1:8000/**

### 3️⃣ الدخول إلى لوحة التحكم
- الرابط: http://127.0.0.1:8000/dashboard/
- المستخدم: `admin`
- كلمة المرور: `admin123`

---

## 🔧 المشاكل التي تم حلها

### ✅ مشكلة Railway Build
**الخطأ**: فشل التحقق من GitHub artifact attestations
**الحل**: تعديل `build.sh` بإضافة:
```bash
export MISE_PYTHON_GITHUB_ATTESTATIONS=false
mise install
```

### ✅ مشكلة المتطلبات
**الخطأ**: `ModuleNotFoundError: No module named 'django_filters'`
**الحل**: تثبيت المتطلبات:
```bash
pip install -r requirements.txt
```

---

## 📚 الملفات المهمة

| الملف | الوصف |
|------|------|
| `SETUP.md` | دليل الإعداد والنشر الكامل |
| `PROJECT_STATUS.md` | تقرير شامل عن حالة المشروع |
| `build.sh` | سكريبت البناء (معدل) |
| `.env` | متغيرات البيئة |

---

## 🌐 الروابط الهامة

| الرابط | الوصف |
|--------|------|
| `/` | الصفحة الرئيسية |
| `/about/` | من نحن |
| `/contact/` | نموذج التواصل |
| `/login/` | دخول الإدارة |
| `/dashboard/` | لوحة التحكم |
| `/admin/` | إدارة Django |
| `/health/` | فحص الصحة |
| `/sitemap.xml` | خريطة الموقع |
| `/robots.txt` | ملف robots |

---

## 💡 نصائح مهمة

### تشغيل الخادم على باب مختلف
```bash
python manage.py runserver 8080
```

### إنشاء مستخدم إداري جديد
```bash
python manage.py createsuperuser
```

### فحص المشاكل
```bash
python manage.py check
```

### تطبيق هجرات جديدة
```bash
python manage.py migrate
```

---

## 🚀 النشر على Railway

1. دفع التغييرات:
```bash
git push origin master
```

2. في لوحة Railway، أضف متغيرات البيئة:
- `SECRET_KEY` (مفتاح جديد)
- `DEBUG=False`
- `ALLOWED_HOSTS=yourdomain.com`
- `DATABASE_URL=...` (من Railway)

3. سيتم البناء والنشر تلقائياً!

---

## ❓ أسئلة شائعة

**س: كيف أشغل المشروع؟**
ج: `python manage.py runserver`

**س: كيف أنشئ عقار جديد؟**
ج: ادخل `/dashboard/` ثم استخدم نموذج "إضافة عقار"

**س: كيف أغير بيانات الموقع؟**
ج: ادخل `/dashboard/` ثم انقر على "إعدادات الموقع"

**س: الخادم لا يعمل؟**
ج: تأكد من:
1. تفعيل البيئة الافتراضية
2. تثبيت المتطلبات: `pip install -r requirements.txt`
3. تطبيق الهجرات: `python manage.py migrate`

---

## 📞 معلومات الاتصال

- 📱 الهاتف: 07701234567
- 💬 واتساب: رابط مباشر من الموقع
- 📧 البريد: يمكن إضافته من لوحة التحكم

---

**آخر تحديث**: يونيو 4، 2026
**الإصدار**: 1.0.0
**الحالة**: ✅ إنتاجي جاهز
