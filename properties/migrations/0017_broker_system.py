# Broker system: Office, Broker, BrokerJoinRequest, Property/Message fields

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0016_merge_20260619_2259'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Office',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='اسم المكتب')),
                ('address', models.CharField(blank=True, max_length=300, verbose_name='العنوان')),
                ('phone', models.CharField(blank=True, max_length=30, verbose_name='الهاتف')),
                ('governorate', models.CharField(blank=True, max_length=100, verbose_name='المحافظة')),
                ('is_active', models.BooleanField(default=True, verbose_name='نشط')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_offices', to=settings.AUTH_USER_MODEL, verbose_name='المالك')),
            ],
            options={
                'verbose_name': 'مكتب عقاري',
                'verbose_name_plural': 'المكاتب العقارية',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Broker',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone', models.CharField(max_length=20, verbose_name='الهاتف')),
                ('office_name', models.CharField(blank=True, max_length=200, verbose_name='اسم المكتب')),
                ('governorate', models.CharField(blank=True, max_length=100, verbose_name='المحافظة')),
                ('role', models.CharField(choices=[('admin', 'مدير النظام'), ('main', 'دلال رئيسي'), ('sub', 'دلال فرعي')], default='sub', max_length=10, verbose_name='الدور')),
                ('is_verified', models.BooleanField(default=False, verbose_name='دلال موثق')),
                ('is_active', models.BooleanField(default=True, verbose_name='نشط')),
                ('subscription_type', models.CharField(choices=[('free', 'مجاني'), ('silver', 'فضي'), ('gold', 'ذهبي'), ('diamond', 'ماسي')], default='free', max_length=10, verbose_name='نوع الاشتراك')),
                ('id_card_image', models.ImageField(blank=True, null=True, upload_to='broker_ids/', verbose_name='صورة الهوية')),
                ('bio', models.TextField(blank=True, verbose_name='نبذة')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('office', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='brokers', to='properties.office', verbose_name='المكتب العقاري')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sub_brokers', to='properties.broker', verbose_name='الدلال الرئيسي')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='broker_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'دلال',
                'verbose_name_plural': 'الدلالين',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='BrokerJoinRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='الاسم')),
                ('phone', models.CharField(max_length=20, verbose_name='الهاتف')),
                ('governorate', models.CharField(max_length=100, verbose_name='المحافظة')),
                ('office_name', models.CharField(max_length=200, verbose_name='المكتب العقاري')),
                ('id_card_image', models.ImageField(upload_to='broker_requests/', verbose_name='صورة الهوية')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='البريد الإلكتروني')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات المتقدم')),
                ('status', models.CharField(choices=[('pending', 'قيد المراجعة'), ('approved', 'مقبول'), ('rejected', 'مرفوض')], default='pending', max_length=10, verbose_name='الحالة')),
                ('review_notes', models.TextField(blank=True, verbose_name='ملاحظات المراجعة')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='join_request', to=settings.AUTH_USER_MODEL, verbose_name='الحساب المُنشأ')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_join_requests', to=settings.AUTH_USER_MODEL, verbose_name='راجع بواسطة')),
            ],
            options={
                'verbose_name': 'طلب انضمام دلال',
                'verbose_name_plural': 'طلبات انضمام الدلالين',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='property',
            name='owner',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_properties', to=settings.AUTH_USER_MODEL, verbose_name='صاحب الإعلان'),
        ),
        migrations.AddField(
            model_name='property',
            name='broker',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='properties', to='properties.broker', verbose_name='الدلال'),
        ),
        migrations.AddField(
            model_name='property',
            name='office',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='properties', to='properties.office', verbose_name='المكتب العقاري'),
        ),
        migrations.AddField(
            model_name='message',
            name='broker',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inquiries', to='properties.broker', verbose_name='الدلال'),
        ),
        migrations.AddField(
            model_name='message',
            name='reply',
            field=models.TextField(blank=True, verbose_name='الرد'),
        ),
        migrations.AddField(
            model_name='message',
            name='replied_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='تاريخ الرد'),
        ),
        migrations.AddField(
            model_name='message',
            name='replied_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='message_replies', to=settings.AUTH_USER_MODEL, verbose_name='رد بواسطة'),
        ),
        migrations.AddField(
            model_name='message',
            name='is_archived',
            field=models.BooleanField(default=False, verbose_name='مؤرشف'),
        ),
    ]
