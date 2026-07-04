# 🚀 دليل النشر - منصة دلال العقارية

دليل شامل لنشر منصة دلال العقارية على Railway.

## 📋 المتطلبات

- حساب على Railway
- مستودع GitHub
- ملفات البيئة (Environment Variables)

## 🔧 إعداد البيئة

### Backend (Django)

1. **إنشاء ملف `.env` في مجلد `acakar/`:**
```bash
cd acakar
cp .env.example .env
```

2. **تحديث المتغيرات في `.env`:**
```env
SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=False
ALLOWED_HOSTS=your-app.railway.app
CSRF_TRUSTED_ORIGINS=https://your-app.railway.app
DB_ENGINE=postgresql
CORS_ALLOWED_ORIGINS=https://your-frontend-app.railway.app
```

### Frontend (Next.js)

1. **إنشاء ملف `.env.local` في مجلد `luxury-frontend/`:**
```bash
cd luxury-frontend
cp .env.example .env.local
```

2. **تحديث المتغيرات في `.env.local`:**
```env
NEXT_PUBLIC_API_URL=https://your-backend-app.railway.app
NODE_ENV=production
```

## 🚀 النشر على Railway

### 1. نشر Backend (Django)

1. **اتصل بمستودع GitHub على Railway:**
   - افتح https://railway.app
   - سجل الدخول باستخدام GitHub
   - اضغط "New Project"
   - اختر "Deploy from GitHub repo"
   - حدد المستودع

2. **إعدادات البناء:**
   - سيقوم Railway تلقائياً بكشف مشروع Django
   - سيستخدم ملف `railway.toml` للتكوين

3. **إضافة متغيرات البيئة في Railway:**
   ```
   SECRET_KEY=your-secure-secret-key
   DEBUG=False
   ALLOWED_HOSTS=your-app.railway.app
   CSRF_TRUSTED_ORIGINS=https://your-app.railway.app
   DB_ENGINE=postgresql
   CORS_ALLOWED_ORIGINS=https://your-frontend-app.railway.app
   ```

4. **قاعدة البيانات:**
   - Railway سيقوم تلقائياً بإنشاء قاعدة بيانات PostgreSQL
   - سيضيف متغير `DATABASE_URL` تلقائياً

5. **تشغيل الهجرة:**
   - افتح Railway Console
   - شغل: `python manage.py migrate`

### 2. نشر Frontend (Next.js)

1. **إنشاء خدمة جديدة:**
   - في مشروع Railway نفسه
   - اضغط "New Service"
   - اختر "Deploy from GitHub repo"
   - حدد المستودع نفسه

2. **إعدادات البناء:**
   - اضبط "Root Directory" إلى `luxury-frontend`
   - سيستخدم ملف `luxury-frontend/railway.toml`

3. **إضافة متغيرات البيئة:**
   ```
   NEXT_PUBLIC_API_URL=https://your-backend-app.railway.app
   NODE_ENV=production
   ```

## 🧪 الاختبار

### اختبار Backend
```bash
# Health check
curl https://your-backend-app.railway.app/api/health/

# API endpoints
curl https://your-backend-app.railway.app/api/properties/
```

### اختبار Frontend
- افتح https://your-frontend-app.railway.app
- تأكد من أن الصفحة تعمل
- تحقق من أن API يعمل

## 🔐 الأمان

### قائمة التحقق الأمنية
- [ ] تغيير SECRET_KEY
- [ ] تفعيل HTTPS (Railway تلقائي)
- [ ] إعداد CORS بشكل صحيح
- [ ] تفعيل DEBUG=False
- [ ] مراجعة ALLOWED_HOSTS
- [ ] إعداد نسخ احتياطية لقاعدة البيانات

## 📊 المراقبة

### Railway Dashboard
- عرض السجلات (Logs)
- مراقبة استخدام الموارد
- إعداد التنبيهات

### Health Checks
- Backend: `/api/health/`
- Frontend: `/`

## 🐛 استكشاف الأخطاء

### المشاكل الشائعة

**Frontend لا يتصل بـ Backend:**
- تحقق من NEXT_PUBLIC_API_URL
- تأكد من إعدادات CORS في Django
- تأكد من أن Backend يعمل

**Django static files لا تعمل:**
- شغل `python manage.py collectstatic`
- تحقق من STATIC_URL و STATIC_ROOT
- تأكد من Whitenoise middleware

**فشل البناء:**
- تحقق من إصدار Node.js
- تأكد من تثبيت جميع المكتبات
- راجع سجلات البناء في Railway

## 📝 ملاحظات مهمة

### للبيانات الموجودة
- العقارات القديمة قد لا تحتوي على district/street
- قد تحتاج لتحديثها يدوياً
- يمكنك استخدام Django shell أو لوحة الإدارة

### للإدارة
- تم تحديث لوحة الإدارة لتعكس الحقول الجديدة
- يمكن إضافة/تعديل الحقول بسهولة
- البحث والفلترة يعملان بالأحياء

### للـ API
- جميع الـ endpoints محدثة
- backward compatibility محفوظة
- الوثائق محدثة

## 🎯 الخطوات التالية

### للتحسينات الإضافية
- إضافة قائمة الأحياء الأكثر شعبية ديناميكياً
- إضافة إحصائيات خاصة بكل حي
- تحسينات على الخريطة تفاعلية للناصرية
- إضافة مدونات وأخبار محلية

## 📞 الدعم

إذا واجهت أي مشاكل:
- راجع سجلات Railway
- تحقق من متغيرات البيئة
- تأكد من أن جميع الملفات مرفوعة إلى GitHub

---

**تم إصلاح جميع الأخطاء وجاهز للنشر! 🎉**
