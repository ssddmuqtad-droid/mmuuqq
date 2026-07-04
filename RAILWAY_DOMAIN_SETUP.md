# إعداد الدومين المخصص daluailiraq.com على Railway

## الخطوة 1: إضافة الدومين في Railway

1. سجل الدخول إلى حسابك على [Railway](https://railway.app)
2. انتقل إلى مشروعك (muq-main)
3. اذهب إلى **Settings** > **Domains**
4. انقر على **Add Domain**
5. أدخل الدومين: `daluailiraq.com`
6. كرر الخطوة لإضافة `www.daluailiraq.com`

## الخطوة 2: تحديث سجلات DNS

سيعطيك Railway سجلات DNS لإضافتها. ستكون مشابهة لما يلي:

### للدومين الرئيسي (daluailiraq.com):
```
Type: CNAME
Name: @
Value: [Railway-provided-CNAME]
TTL: 300
```

### للدومين الفرعي (www.daluailiraq.com):
```
Type: CNAME
Name: www
Value: [Railway-provided-CNAME]
TTL: 300
```

### أضف هذه السجلات في مزود خدمة الدومين الخاص بك (مثل GoDaddy, Namecheap, إلخ)

## الخطوة 3: إعداد متغيرات البيئة في Railway

أضف المتغيرات التالية في **Settings** > **Variables**:

```
CUSTOM_DOMAIN=daluailiraq.com
ALLOWED_HOSTS=daluailiraq.com,www.daluailiraq.com,.railway.app
CSRF_TRUSTED_ORIGINS=https://daluailiraq.com,https://www.daluailiraq.com,https://muq.up.railway.app
```

## الخطوة 4: إعادة نشر المشروع

بعد إضافة الدومين وتحديث متغيرات البيئة:

1. انتقل إلى **Deployments**
2. انقر على **Redeploy**
3. انتظر حتى يكتمل النشر

## الخطوة 5: التحقق من SSL

سيقوم Railway تلقائياً بإعداد شهادة SSL/TLS للدومين المخصص. قد يستغرق هذا بضع دقائق.

للتحقق من SSL:
1. انتقل إلى **Settings** > **Domains**
2. تأكد من أن حالة SSL هي "Active"

## الخطوة 6: الاختبار

بعد اكتمال النشر، اختبر الدومين:

1. افتح المتصفح واذهب إلى: `https://daluailiraq.com`
2. اختبر أيضاً: `https://www.daluailiraq.com`
3. تأكد من أن الموقع يعمل بشكل صحيح
4. تحقق من شهادة SSL (قفل الأمان في المتصفح)

## استكشاف الأخطاء

### إذا لم يعمل الدومين:
1. تحقق من سجلات DNS (استخدم `nslookup` أو `dig`)
2. تأكد من أن سجلات DNS قد نشرت (قد يستغرق 24-48 ساعة)
3. تحقق من متغيرات البيئة في Railway
4. راجع سجلات النشر في Railway

### إذا لم يعمل SSL:
1. انتظر بضع دقائق إضافية (Railway يقوم تلقائياً بإعداد SSL)
2. تأكد من أن سجلات DNS صحيحة
3. تحقق من أن الدومين يشير إلى Railway بشكل صحيح

## الإعدادات الحالية في المشروع

ملف `dalal_project/settings.py` يحتوي بالفعل على:
- دعم الدومين المخصص عبر متغير البيئة `CUSTOM_DOMAIN`
- إضافة الدومين تلقائياً إلى `ALLOWED_HOSTS`
- إضافة الدومين تلقائياً إلى `CSRF_TRUSTED_ORIGINS`
- دعم الدومين الفرعي `www.`

لا حاجة لتعديل ملفات المشروع - فقط اتبع الخطوات أعلاه في Railway.
