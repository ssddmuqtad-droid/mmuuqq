# إعداد المهام المجدولة للحماية التلقائية

## نظرة عامة
يحتوي النظام على أوامر إدارة Django للتشغيل التلقائي لحماية المنشورات وإدارتها.

## الأوامر المتاحة

### 1. auto_freeze_expired
تجميد جميع المنشورات تلقائياً عند انتهاء اشتراك الدلال.

```bash
python manage.py auto_freeze_expired
```

### 2. cleanup_expired_properties
حذف المنشورات المنتهية والمجمدة بعد فترة زمنية محددة.

```bash
# تشغيل عادي (حذف المنشورات المجمدة لأكثر من 7 أيام)
python manage.py cleanup_expired_properties

# تشغيل بفترة زمنية مخصصة (30 يوم)
python manage.py cleanup_expired_properties --days=30

# تشغيل في وضع التجربة (بدون حذف فعلي)
python manage.py cleanup_expired_properties --dry-run
```

## إعداد المهام المجدولة

### على Windows (Task Scheduler)

#### 1. إعداد auto_freeze_expired (يومياً)

1. افتح Task Scheduler
2. أنشئ مهمة جديدة
3. الاسم: `Auto Freeze Expired Properties`
4. التشغيل: يومياً في الساعة 00:00
5. الإجراء:
   - البرنامج: `python`
   - الوسائط: `manage.py auto_freeze_expired`
   - المجلد: `c:\Users\muqtada\OneDrive\Desktop\moq-main`

#### 2. إعداد cleanup_expired_properties (أسبوعياً)

1. افتح Task Scheduler
2. أنشئ مهمة جديدة
3. الاسم: `Cleanup Expired Properties`
4. التشغيل: أسبوعياً يوم الأحد في الساعة 02:00
5. الإجراء:
   - البرنامج: `python`
   - الوسائط: `manage.py cleanup_expired_properties --days=7`
   - المجلد: `c:\Users\muqtada\OneDrive\Desktop\moq-main`

### على Linux (CRON)

#### 1. إضافة إلى crontab

```bash
crontab -e
```

#### 2. إضافة المهام التالية:

```bash
# تجميد المنشورات يومياً في الساعة 00:00
0 0 * * * cd /path/to/moq-main && python manage.py auto_freeze_expired

# حذف المنشورات المنتهية أسبوعياً يوم الأحد في الساعة 02:00
0 2 * * 0 cd /path/to/moq-main && python manage.py cleanup_expired_properties --days=7
```

## اختبار الأوامر

### اختبار auto_freeze_expired

```bash
python manage.py auto_freeze_expired
```

### اختبار cleanup_expired_properties في وضع التجربة

```bash
python manage.py cleanup_expired_properties --dry-run
```

## الملاحظات

- تأكد من تشغيل الخادم قبل تشغيل الأوامر
- يمكن تعديل فترة الحذف حسب الحاجة
- يُنصح باختبار الأوامر في وضع التجربة أولاً
