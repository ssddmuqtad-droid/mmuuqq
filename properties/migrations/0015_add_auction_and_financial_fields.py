# Generated migration manually to fix deployment issues

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0014_buildingrequest_buildingdetails_budget_blueprint_and_more'),
    ]

    operations = [
        # Add missing Auction fields
        migrations.AddField(
            model_name='auction',
            name='auction_type',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('home', 'بيع منزل'),
                    ('land', 'بيع أرض'),
                    ('shop', 'بيع محل تجاري'),
                    ('building', 'بيع عمارة'),
                    ('investment', 'استثماري'),
                ],
                default='home',
                verbose_name='نوع المزاد'
            ),
        ),
        migrations.AddField(
            model_name='auction',
            name='reserve_price',
            field=models.DecimalField(
                max_digits=15,
                decimal_places=0,
                null=True,
                blank=True,
                verbose_name='السعر الاحتياطي'
            ),
        ),
        migrations.AddField(
            model_name='auction',
            name='auto_extend_minutes',
            field=models.IntegerField(
                default=5,
                verbose_name='دقائق التمديد التلقائي'
            ),
        ),
        migrations.AddField(
            model_name='auction',
            name='access_code',
            field=models.CharField(
                max_length=20,
                null=True,
                blank=True,
                verbose_name='كود الدخول'
            ),
        ),
        migrations.AddField(
            model_name='auction',
            name='is_closed',
            field=models.BooleanField(
                default=False,
                verbose_name='مزاد مغلق'
            ),
        ),
        migrations.AddField(
            model_name='auction',
            name='is_featured',
            field=models.BooleanField(
                default=False,
                verbose_name='مزاد مميز'
            ),
        ),
        
        # Create FinancialTransaction model
        migrations.CreateModel(
            name='FinancialTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_type', models.CharField(
                    max_length=20,
                    choices=[
                        ('sale', 'بيع عقار'),
                        ('commission', 'عمولة'),
                        ('refund', 'استرجاع'),
                    ],
                    verbose_name='نوع المعاملة'
                )),
                ('status', models.CharField(
                    max_length=20,
                    choices=[
                        ('pending', 'قيد الانتظار'),
                        ('completed', 'مكتمل'),
                        ('cancelled', 'ملغي'),
                    ],
                    default='pending',
                    verbose_name='الحالة'
                )),
                ('sale_price', models.DecimalField(
                    max_digits=15,
                    decimal_places=0,
                    null=True,
                    blank=True,
                    verbose_name='سعر البيع'
                )),
                ('commission_type', models.CharField(
                    max_length=20,
                    choices=[
                        ('percentage', 'نسبة مئوية'),
                        ('fixed', 'مبلغ ثابت'),
                    ],
                    default='percentage',
                    verbose_name='نوع العمولة'
                )),
                ('commission_rate', models.DecimalField(
                    max_digits=5,
                    decimal_places=2,
                    null=True,
                    blank=True,
                    verbose_name='نسبة العمولة (%)'
                )),
                ('commission_amount', models.DecimalField(
                    max_digits=15,
                    decimal_places=0,
                    null=True,
                    blank=True,
                    verbose_name='مبلغ العمولة'
                )),
                ('owner_name', models.CharField(
                    max_length=200,
                    verbose_name='اسم صاحب العقار'
                )),
                ('owner_amount', models.DecimalField(
                    max_digits=15,
                    decimal_places=0,
                    verbose_name='المبلغ المستحق لصاحب العقار'
                )),
                ('additional_fees', models.DecimalField(
                    max_digits=15,
                    decimal_places=0,
                    default=0,
                    verbose_name='رسوم إضافية'
                )),
                ('platform_commission_rate', models.DecimalField(
                    max_digits=5,
                    decimal_places=2,
                    default=0,
                    verbose_name='نسبة المنصة (%)'
                )),
                ('platform_commission_amount', models.DecimalField(
                    max_digits=15,
                    decimal_places=0,
                    default=0,
                    verbose_name='مبلغ عمولة المنصة'
                )),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ المعاملة')),
                ('completed_at', models.DateTimeField(
                    null=True,
                    blank=True,
                    verbose_name='تاريخ الإتمام'
                )),
                ('property', models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name='financial_transactions',
                    to='properties.property',
                    null=True,
                    blank=True
                )),
                ('user', models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name='financial_transactions',
                    to='auth.user'
                )),
            ],
            options={
                'verbose_name': 'معاملة مالية',
                'verbose_name_plural': 'المعاملات المالية',
                'ordering': ['-created_at'],
            },
        ),
        
        # Create Expense model
        migrations.CreateModel(
            name='Expense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(
                    max_length=20,
                    choices=[
                        ('rent', 'إيجار المكتب'),
                        ('salary', 'رواتب الموظفين'),
                        ('marketing', 'إعلانات وتسويق'),
                        ('fuel', 'وقود وتنقل'),
                        ('internet', 'إنترنت واتصالات'),
                        ('utilities', 'مرافق'),
                        ('other', 'مصاريف أخرى'),
                    ],
                    verbose_name='فئة المصروف'
                )),
                ('title', models.CharField(max_length=200, verbose_name='العنوان')),
                ('amount', models.DecimalField(max_digits=15, decimal_places=0, verbose_name='المبلغ')),
                ('date', models.DateField(verbose_name='التاريخ')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('receipt_image', models.ImageField(
                    null=True,
                    blank=True,
                    upload_to='property_images/%Y/%m/',
                    verbose_name='صورة الإيصال'
                )),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإدخال')),
                ('user', models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name='expenses',
                    to='auth.user'
                )),
            ],
            options={
                'verbose_name': 'مصروف',
                'verbose_name_plural': 'المصاريف',
                'ordering': ['-date'],
            },
        ),
        
        # Create Payment model
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payment_type', models.CharField(
                    max_length=20,
                    choices=[
                        ('full', 'دفعة كاملة'),
                        ('partial', 'دفعة جزئية'),
                        ('advance', 'سلفة'),
                    ],
                    verbose_name='نوع الدفعة'
                )),
                ('amount', models.DecimalField(max_digits=15, decimal_places=0, verbose_name='المبلغ')),
                ('status', models.CharField(
                    max_length=20,
                    choices=[
                        ('pending', 'قيد الانتظار'),
                        ('completed', 'مكتمل'),
                        ('cancelled', 'ملغي'),
                    ],
                    default='pending',
                    verbose_name='الحالة'
                )),
                ('payment_date', models.DateField(
                    null=True,
                    blank=True,
                    verbose_name='تاريخ الدفع'
                )),
                ('payment_method', models.CharField(
                    max_length=100,
                    blank=True,
                    verbose_name='طريقة الدفع'
                )),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإدخال')),
                ('financial_transaction', models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name='payments',
                    to='properties.financialtransaction'
                )),
                ('user', models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name='payments',
                    to='auth.user'
                )),
            ],
            options={
                'verbose_name': 'دفعة',
                'verbose_name_plural': 'المدفوعات',
                'ordering': ['-created_at'],
            },
        ),
        
        # Create OfficeWallet model
        migrations.CreateModel(
            name='OfficeWallet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('current_balance', models.DecimalField(
                    max_digits=15,
                    decimal_places=0,
                    default=0,
                    verbose_name='الرصيد الحالي'
                )),
                ('pending_commissions', models.DecimalField(
                    max_digits=15,
                    decimal_places=0,
                    default=0,
                    verbose_name='الأرباح المعلقة'
                )),
                ('received_commissions', models.DecimalField(
                    max_digits=15,
                    decimal_places=0,
                    default=0,
                    verbose_name='الأرباح المستلمة'
                )),
                ('withdrawn_amount', models.DecimalField(
                    max_digits=15,
                    decimal_places=0,
                    default=0,
                    verbose_name='الأرباح المسحوبة'
                )),
                ('user', models.OneToOneField(
                    on_delete=models.deletion.CASCADE,
                    related_name='wallet',
                    to='auth.user'
                )),
            ],
            options={
                'verbose_name': 'محفظة مالية',
                'verbose_name_plural': 'المحافظ المالية',
            },
        ),
        
        # Create WalletTransaction model
        migrations.CreateModel(
            name='WalletTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_type', models.CharField(
                    max_length=20,
                    choices=[
                        ('commission', 'عمولة'),
                        ('withdrawal', 'سحب'),
                        ('deposit', 'إيداع'),
                        ('adjustment', 'تعديل'),
                    ],
                    verbose_name='نوع المعاملة'
                )),
                ('amount', models.DecimalField(max_digits=15, decimal_places=0, verbose_name='المبلغ')),
                ('balance_before', models.DecimalField(
                    max_digits=15,
                    decimal_places=0,
                    verbose_name='الرصيد قبل'
                )),
                ('balance_after', models.DecimalField(
                    max_digits=15,
                    decimal_places=0,
                    verbose_name='الرصيد بعد'
                )),
                ('description', models.TextField(verbose_name='الوصف')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='التاريخ')),
                ('related_transaction', models.ForeignKey(
                    null=True,
                    blank=True,
                    on_delete=models.deletion.SET_NULL,
                    related_name='wallet_transactions',
                    to='properties.financialtransaction'
                )),
                ('wallet', models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name='transactions',
                    to='properties.officewallet'
                )),
            ],
            options={
                'verbose_name': 'معاملة محفظة',
                'verbose_name_plural': 'معاملات المحفظة',
                'ordering': ['-created_at'],
            },
        ),
    ]
