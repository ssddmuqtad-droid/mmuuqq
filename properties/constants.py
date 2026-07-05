"""Iraq real estate platform constants."""

# Iraq governorates with codes (19 governorates)
IRAQ_GOVERNORATES = [
    ('BAG', 'بغداد'),
    ('BAS', 'البصرة'),
    ('NIN', 'نينوى'),
    ('ERB', 'أربيل'),
    ('NAJ', 'النجف'),
    ('KAR', 'كربلاء'),
    ('BAB', 'بابل'),
    ('DHI', 'ذي قار'),
    ('DIA', 'ديالى'),
    ('KIR', 'كركوك'),
    ('ANB', 'الأنبار'),
    ('WAS', 'واسط'),
    ('MUT', 'ميسان'),
    ('MUTH', 'المثنى'),
    ('QAD', 'القادسية (الديوانية)'),
    ('SAL', 'صلاح الدين'),
    ('DUH', 'دهوك'),
    ('SUL', 'السليمانية'),
    ('HAL', 'حلبجة'),
    ('KIRKUK', 'كركوك'),
]

# Property categories (main classification)
PROPERTY_CATEGORIES = [
    ('residential', 'سكني'),
    ('commercial', 'تجاري'),
    ('investment', 'استثماري'),
    ('tourism', 'سياحي'),
    ('land', 'أراضي'),
]

# Property types by category
PROPERTY_TYPES = {
    'residential': [
        ('house', 'بيت'),
        ('apartment', 'شقة'),
        ('villa', 'فيلا'),
        ('duplex', 'دوبلكس'),
        ('residential_complex', 'مجمع سكني'),
    ],
    'commercial': [
        ('shop', 'محل'),
        ('office', 'مكتب'),
        ('mall', 'مول / مركز تجاري'),
        ('car_showroom', 'معرض سيارات'),
        ('warehouse', 'مخزن'),
    ],
    'investment': [
        ('residential_building', 'بناية سكنية'),
        ('commercial_building', 'عمارة تجارية'),
        ('investment_land', 'أرض للاستثمار'),
        ('apartment_complex', 'مجمع شقق'),
        ('small_hotel', 'فندق صغير'),
    ],
    'tourism': [
        ('chalet', 'شاليه'),
        ('resort', 'منتجع'),
        ('hotel', 'فندق'),
        ('hotel_apartment', 'شقق فندقية'),
        ('tourism_house', 'بيت سياحي'),
    ],
    'land': [
        ('residential_land', 'أرض سكنية'),
        ('agricultural_land', 'أرض زراعية'),
        ('commercial_land', 'أرض تجارية'),
        ('investment_land', 'أرض استثمارية'),
    ],
}

# Transaction types
TRANSACTION_TYPES = [
    ('sale', 'بيع'),
    ('rent_monthly', 'إيجار شهري'),
    ('rent_yearly', 'إيجار سنوي'),
    ('rent_daily', 'إيجار يومي'),
    ('investment_rent', 'شراء للإيجار'),
    ('investment_develop', 'تطوير وبيع'),
    ('investment_partnership', 'شراكة استثمارية'),
]

# Status choices (simplified for filtering)
STATUS_CHOICES = [
    ('sale', 'بيع'),
    ('rent', 'إيجار'),
    ('investment', 'استثمار'),
]

# Subscription plans
SUBSCRIPTION_PERIODS = [
    ('daily', 'يومي'),
    ('monthly', 'شهري'),
    ('yearly', 'سنوي'),
    ('5_years', '5 سنوات'),
]

SUBSCRIPTION_PLANS = [
    # Daily plans
    {
        'period': 'daily',
        'ads_limit': 100,
        'name': 'الاشتراك اليومي',
        'color': 'green',
        'price': 0,  # Will be set dynamically
    },
    # Monthly plans
    {
        'period': 'monthly',
        'ads_limit': 100,
        'name': 'الاشتراك الشهري - 100 إعلان',
        'color': 'blue',
        'price': 0,
    },
    {
        'period': 'monthly',
        'ads_limit': 500,
        'name': 'الاشتراك الشهري - 500 إعلان',
        'color': 'blue',
        'price': 0,
    },
    {
        'period': 'monthly',
        'ads_limit': 1000,
        'name': 'الاشتراك الشهري - 1000 إعلان',
        'color': 'blue',
        'price': 0,
    },
    # Yearly plans
    {
        'period': 'yearly',
        'ads_limit': 100,
        'name': 'الاشتراك السنوي - 100 إعلان',
        'color': 'purple',
        'price': 0,
    },
    {
        'period': 'yearly',
        'ads_limit': 500,
        'name': 'الاشتراك السنوي - 500 إعلان',
        'color': 'purple',
        'price': 0,
    },
    {
        'period': 'yearly',
        'ads_limit': 1000,
        'name': 'الاشتراك السنوي - 1000 إعلان',
        'color': 'purple',
        'price': 0,
    },
    {
        'period': 'yearly',
        'ads_limit': 2500,
        'name': 'الاشتراك السنوي - 2500 إعلان',
        'color': 'purple',
        'price': 0,
    },
    {
        'period': 'yearly',
        'ads_limit': 5000,
        'name': 'الاشتراك السنوي - 5000 إعلان',
        'color': 'purple',
        'price': 0,
    },
    # 5 years plans
    {
        'period': '5_years',
        'ads_limit': 100,
        'name': 'اشتراك 5 سنوات - 100 إعلان',
        'color': 'orange',
        'price': 0,
    },
    {
        'period': '5_years',
        'ads_limit': 500,
        'name': 'اشتراك 5 سنوات - 500 إعلان',
        'color': 'orange',
        'price': 0,
    },
    {
        'period': '5_years',
        'ads_limit': 1000,
        'name': 'اشتراك 5 سنوات - 1000 إعلان',
        'color': 'orange',
        'price': 0,
    },
    {
        'period': '5_years',
        'ads_limit': 2500,
        'name': 'اشتراك 5 سنوات - 2500 إعلان',
        'color': 'orange',
        'price': 0,
    },
    {
        'period': '5_years',
        'ads_limit': 5000,
        'name': 'اشتراك 5 سنوات - 5000 إعلان',
        'color': 'orange',
        'price': 0,
    },
]

# Cities for each governorate
GOVERNORATE_CITIES = {
    'BAG': ['بغداد', 'الكرادة', 'المنصور', 'الشعب', 'السيدية', 'الاعظمية'],
    'BAS': ['البصرة', 'الفاو', 'القرنة', 'الزبير', 'أبو الخصيب'],
    'NIN': ['الموصل', 'تلعفر', 'سنجار', 'الحمدانية', 'الشيخان'],
    'BAB': ['بابل', 'الحلة', 'المشخاب', 'المدائن', 'القاسم'],
    'DHI': ['الناصرية', 'الرفاعي', 'الشطرة', 'سوق الشيوخ', 'الغراف'],
    'SUL': ['السليمانية', 'حلبجة', 'چوارتة', 'دوكان', 'سردشت'],
    'ERB': ['أربيل', 'خانقين', 'شقلاوة', 'سوران', 'مخمور'],
    'KIR': ['كركوك', 'داقوق', 'تازة', 'تلكيف', 'الحمزة'],
    'NAJ': ['النجف', 'الكوفة', 'الخمس', 'المنصورية', 'الحر'],
    'KAR': ['كربلاء', 'العيون', 'الحنينية', 'النخيب', 'عين التمر'],
    'WAS': ['الكوت', 'النعمانية', 'الزبداني', 'الحي', 'بدرة'],
    'MUT': ['العمارة', 'المجر الكبير', 'قضاء علي الغربي', 'الميمونة', 'الكحلاء'],
    'QAD': ['الديوانية', 'الحمزة', 'الشامية', 'عفك', 'بني سعد'],
    'ANB': ['الرمادي', 'الفلوجة', 'حديثة', 'القائم', 'الرطبة'],
    'SAL': ['تكريت', 'سامراء', 'البلد', 'الدور', 'شرقاط'],
    'THQ': ['كركوك', 'توز خورماتو', 'داقوق', 'الشيرقات', 'آمرلي'],
    'MUTH': ['السماوة', 'الرفاعي', 'الغربي', 'الشامية', 'المجد'],
}

# Common districts in Nasiriyah (user can add custom districts)
COMMON_NASIRIYAH_DISTRICTS = [
    'الشموخ',
    'سومر',
    'الإسكان الصناعي',
    'أور',
    'الجامعة',
    'العسكري',
    'الحجرة',
    'السيدية',
    'العامرية',
    'الجنينة',
    'المشراق',
    'الصناعية',
    'المعلمين',
    'الاطباء',
    'الاداريين',
]

SORT_CHOICES = [
    ('newest', 'الأحدث'),
    ('oldest', 'الأقدم'),
    ('price_asc', 'السعر: من الأقل'),
    ('price_desc', 'السعر: من الأعلى'),
    ('area_asc', 'المساحة: من الأصغر'),
    ('area_desc', 'المساحة: من الأكبر'),
    ('views', 'الأكثر مشاهدة'),
    ('rating', 'الأعلى تقييماً'),
    ('popular', 'الأكثر طلباً'),
    ('nearest', 'الأقرب إليك'),
]

# Nasiriyah city center coordinates for map
NASIRIYAH_CENTER = {
    'lat': 31.0564,
    'lng': 46.2545,
    'zoom': 13
}

# SEO keywords for Nasiriyah
SEO_KEYWORDS = [
    'بيوت للبيع في الناصرية',
    'شقق للبيع في الناصرية',
    'أراضي للبيع في الناصرية',
    'عقارات ذي قار',
    'إيجار منازل الناصرية',
    'محلات تجارية الناصرية',
    'عقارات الناصرية',
    'سوق العقارات الناصرية',
]
