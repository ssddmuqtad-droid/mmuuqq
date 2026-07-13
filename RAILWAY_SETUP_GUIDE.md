# دليل إعداد المشروع على Railway

## المشكلة الحالية
من سجلات Railway، المشروع يعمل لكن مع تحذيرات أمنية مهمة:
- ❌ SECRET_KEY غير معين (يستخدم مفتاح افتراضي غير آمن)
- ❌ DATABASE_URL غير معين (يستخدم SQLite بدلاً من PostgreSQL)

## الحلول المطلوبة

### 1. إضافة خدمة PostgreSQL

1. في مشروع Railway، اذهب إلى **Variables** tab
2. اضغط على **New Variable**
3. أضف خدمة PostgreSQL من المتجر:
   - اضغط على **+ New Service**
   - اختر **Database**
   - اختر **PostgreSQL**
   - سيتم إضافة `DATABASE_URL` تلقائياً

### 2. إعداد SECRET_KEY آمن

#### الطريقة الأولى: استخدام Python
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

#### الطريقة الثانية: استخدام موقع على الإنترنت
اذهب إلى: https://djecrety.ir/

#### إضافة SECRET_KEY في Railway:
1. اذهب إلى **Variables** tab
2. اضغط على **New Variable**
3. الاسم: `SECRET_KEY`
4. القيمة: الصق المفتاح الذي أنشأته
5. اضغط **Save**

### 3. متغيرات البيئة المطلوبة

أضف هذه المتغيرات في Railway Variables:

```bash
# Required
SECRET_KEY=your-secure-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-domain.com,.railway.app

# Domain (اختياري)
CUSTOM_DOMAIN=your-domain.com
CSRF_TRUSTED_ORIGINS=https://your-domain.com,https://*.railway.app

# Security
SECURE_SSL_REDIRECT=False  # Railway handles SSL at proxy

# Optional: Redis (للتحسين)
# REDIS_URL=redis://your-redis-url
```

### 4. إعادة النشر

بعد إضافة المتغيرات:
1. Railway سيعيد النشر تلقائياً
2. أو اضغط على **Redeploy** يدوياً

## التحقق من النجاح

بعد إعادة النشر، تحقق من السجلات:
- ✅ لا يوجد تحذير `SECRET_KEY not set`
- ✅ لا يوجد تحذير `DATABASE_URL not set`
- ✅ يجب أن ترى `App listening on port 8080`

## خطوات سريعة

1. **أضف PostgreSQL service** في Railway
2. **أنشئ SECRET_KEY آمن** باستخدام Python
3. **أضف SECRET_KEY** في Variables
4. **أضف ALLOWED_HOSTS** مع نطاقك
5. **انتظر إعادة النشر التلقائية**

## ملاحظات مهمة

- ⚠️ لا تستخدم SQLite في الإنتاج
- ⚠️ لا تستخدم المفتاح الافتراضي في الإنتاج
- ✅ PostgreSQL سيتم إضافة `DATABASE_URL` تلقائياً
- ✅ Railway يعيد النشر تلقائياً عند تغيير المتغيرات
