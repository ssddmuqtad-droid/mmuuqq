from django import forms
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.contrib.auth.models import User

from .constants import COMMON_NASIRIYAH_DISTRICTS, IRAQ_GOVERNORATES
from .models import Property, Message, SiteSettings, PropertyImage, PropertyNote, VirtualTour360, Auction, Bid, BuildingRequest, LandInfo, BuildingDetails, Budget, Blueprint, Quote, ProjectTracking, DeliveryMilestone, ContractorRating, ContractorBid, FinancialTransaction, Expense, Payment, Report, Profit, SubscriptionPlan, UserSettings, BlockedUser, SavedSearch, OfficePresence, PresenceNotification, BrokerSubscription, BrokerNotificationSettings, AutoBid, AuctionRating, AuctionLiveStream, AuctionAdvertisement, Hotel, Resort


def _fc(placeholder=''):
    attrs = {'class': 'form-control'}
    if placeholder:
        attrs['placeholder'] = placeholder
    return attrs


class PropertySearchForm(forms.Form):
    q = forms.CharField(required=False, label='بحث', widget=forms.TextInput(attrs=_fc('ابحث عن عقار...')))
    governorate = forms.ChoiceField(required=False, label='المحافظة', choices=[('', 'كل المحافظات')] + list(IRAQ_GOVERNORATES))
    district = forms.CharField(required=False, label='الحي', widget=forms.TextInput(attrs=_fc('الحي')))
    street = forms.CharField(required=False, label='الشارع', widget=forms.TextInput(attrs=_fc('الشارع')))
    type = forms.ChoiceField(required=False, label='نوع العقار', choices=[('', 'كل الأنواع')])
    status = forms.ChoiceField(required=False, label='الحالة', choices=[('', 'كل الحالات')])
    price_min = forms.IntegerField(required=False, label='السعر من', validators=[MinValueValidator(0)])
    price_max = forms.IntegerField(required=False, label='السعر إلى', validators=[MinValueValidator(0)])
    area_min = forms.IntegerField(required=False, label='المساحة من', validators=[MinValueValidator(0)])
    area_max = forms.IntegerField(required=False, label='المساحة إلى', validators=[MinValueValidator(0)])
    bedrooms = forms.IntegerField(required=False, label='الغرف', validators=[MinValueValidator(0)])
    owner_name = forms.CharField(required=False, label='اسم دلال العقار', widget=forms.TextInput(attrs=_fc('اسم دلال العقار')))
    sort = forms.ChoiceField(required=False, label='ترتيب')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['type'].choices = [('', 'كل الأنواع')] + list(Property.PROPERTY_TYPES)
        self.fields['status'].choices = [('', 'كل الحالات')] + list(Property.STATUS_CHOICES)
        from .constants import SORT_CHOICES
        self.fields['sort'].choices = SORT_CHOICES
        for name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            'title', 'type', 'status', 'district', 'street', 'location',
            'area', 'price', 'description', 'phone', 'bedrooms', 'bathrooms', 'floors',
            'year_built', 'parking', 'furnished', 'latitude', 'longitude',
            'is_featured', 'is_promoted', 'view_commission_rate',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'location': forms.TextInput(attrs={'placeholder': 'الحي، الشارع، أقرب معلم', 'class': 'form-control'}),
            'district': forms.TextInput(attrs={'placeholder': 'مثال: حي الشموخ', 'class': 'form-control'}),
            'street': forms.TextInput(attrs={'placeholder': 'مثال: شارع 40', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'view_commission_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add detailed property type choices
        self.fields['type'].choices = [
            ('', 'اختر نوع العقار'),
            # سكني
            ('apartment', 'شقة'),
            ('house', 'منزل'),
            ('villa', 'فيلا'),
            ('duplex', 'دوبلكس'),
            ('residential_complex', 'مجمع سكني'),
            # تجاري
            ('shop', 'محل تجاري'),
            ('office', 'مكتب'),
            ('mall', 'مول / مركز تجاري'),
            ('car_showroom', 'معرض سيارات'),
            ('warehouse', 'مخزن'),
            # استثماري
            ('residential_building', 'بناية سكنية'),
            ('commercial_building', 'عمارة تجارية'),
            ('investment_land', 'أرض للاستثمار'),
            ('apartment_complex', 'مجمع شقق'),
            ('small_hotel', 'فندق صغير'),
            # سياحي
            ('chalet', 'شاليه'),
            ('resort', 'منتجع'),
            ('hotel', 'فندق'),
            ('hotel_apartment', 'شقق فندقية'),
            ('tourism_house', 'بيت سياحي'),
            # أراضي
            ('residential_land', 'أرض سكنية'),
            ('agricultural_land', 'أرض زراعية'),
            ('commercial_land', 'أرض تجارية'),
            ('investment_land', 'أرض استثمارية'),
        ]
        # Simplify status choices to only two options
        self.fields['status'].choices = [
            ('ready', 'كامل'),
            ('under-construction', 'قيد البناء'),
            ('rent', 'إيجار'),
        ]
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            # Check file size (5MB limit)
            if image.size > 5 * 1024 * 1024:
                raise ValidationError('حجم الصورة يجب أن يكون أقل من 5MB')
            
            # Check file type using magic bytes
            import imghdr
            image.seek(0)
            file_type = imghdr.what(image)
            if file_type not in ['jpeg', 'png', 'gif', 'webp']:
                raise ValidationError('نوع الملف غير مدعوم. يرجى رفع صورة بصيغة JPEG, PNG, GIF, أو WebP')
            
            # Check for malicious content
            image.seek(0)
            header = image.read(8)
            if b'<script' in header.lower() or b'<?php' in header.lower():
                raise ValidationError('الملف يحتوي على محتوى غير آمن')
            
            image.seek(0)
        return image


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['name', 'email', 'phone', 'message']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 4, 'placeholder': 'اكتب رسالتك...', 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'placeholder': 'الاسم الكامل', 'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'placeholder': 'example@email.com', 'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'placeholder': '07XXXXXXXXX', 'class': 'form-control'}),
        }


class UserMessageForm(forms.Form):
    """Form for sending messages from users to brokers."""
    recipient = forms.ModelChoiceField(
        queryset=None,
        label='الدلال',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    message = forms.CharField(
        label='الرسالة',
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'اكتب رسالتك هنا...', 'class': 'form-control'})
    )
    property = forms.ModelChoiceField(
        queryset=Property.objects.none(),
        required=False,
        label='العقار (اختياري)',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        from .models import Broker
        self.fields['recipient'].queryset = Broker.objects.filter(is_active=True).exclude(user=user).select_related('user')
        
        # If user has saved properties, add them to property choices
        if user and user.is_authenticated:
            from .models import Property
            self.fields['property'].queryset = Property.objects.filter(status='active')


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            'site_name', 'tagline', 'broker_phone', 'broker_email', 'broker_address',
            'whatsapp', 'mission', 'seo_description',
            'facebook_url', 'instagram_url',
        ]
        widgets = {
            'mission': forms.Textarea(attrs={'rows': 4}),
            'seo_description': forms.Textarea(attrs={'rows': 2}),
        }


class PropertyNoteForm(forms.ModelForm):
    class Meta:
        model = PropertyNote
        fields = ['property', 'title', 'content', 'priority', 'is_completed']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'عنوان الملاحظة', 'class': 'form-control'}),
            'content': forms.Textarea(attrs={'rows': 4, 'placeholder': 'تفاصيل الملاحظة...', 'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, **kwargs)
            for field in self.fields.values():
                if 'class' not in field.widget.attrs:
                    field.widget.attrs['class'] = 'form-control'
        except Exception as e:
            # PropertyNote model doesn't exist yet
            raise Exception(f'PropertyNote model not available: {str(e)}')


class VirtualTour360Form(forms.ModelForm):
    class Meta:
        model = VirtualTour360
        fields = [
            'title', 'tour_type', 'image', 'tour_file', 'external_url',
            'external_service', 'description', 'order', 'is_active',
            'auto_rotate', 'auto_rotate_speed', 'enable_zoom', 'min_zoom',
            'max_zoom', 'enable_fullscreen', 'enable_vr',
            'initial_view_pitch', 'initial_view_yaw', 'start_in_autoplay',
            'autoplay_duration'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'عنوان الجولة'}),
            'tour_type': forms.Select(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'tour_file': forms.FileInput(attrs={'class': 'form-control'}),
            'external_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'external_service': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_rotate': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_rotate_speed': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
            'enable_zoom': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'min_zoom': forms.NumberInput(attrs={'class': 'form-control', 'step': 0.1, 'min': 0.1, 'max': 5}),
            'max_zoom': forms.NumberInput(attrs={'class': 'form-control', 'step': 0.1, 'min': 0.1, 'max': 10}),
            'enable_fullscreen': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_vr': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'initial_view_pitch': forms.NumberInput(attrs={'class': 'form-control', 'step': 1, 'min': -90, 'max': 90}),
            'initial_view_yaw': forms.NumberInput(attrs={'class': 'form-control', 'step': 1, 'min': 0, 'max': 360}),
            'start_in_autoplay': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'autoplay_duration': forms.NumberInput(attrs={'class': 'form-control', 'min': 5, 'max': 60}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class AuctionForm(forms.ModelForm):
    class Meta:
        model = Auction
        fields = ['property', 'auction_type', 'title', 'description', 'starting_price', 'minimum_increment',
                  'reserve_price', 'start_date', 'end_date', 'auto_extend_minutes', 'deposit_amount',
                  'access_code', 'is_closed', 'is_featured', 'terms']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'عنوان المزاد', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'وصف المزاد...', 'class': 'form-control'}),
            'starting_price': forms.NumberInput(attrs={'placeholder': 'سعر البداية', 'class': 'form-control'}),
            'minimum_increment': forms.NumberInput(attrs={'placeholder': 'أقل زيادة', 'class': 'form-control'}),
            'reserve_price': forms.NumberInput(attrs={'placeholder': 'السعر الاحتياطي (اختياري)', 'class': 'form-control'}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'auto_extend_minutes': forms.NumberInput(attrs={'placeholder': 'دقائق التمديد التلقائي', 'class': 'form-control'}),
            'deposit_amount': forms.NumberInput(attrs={'placeholder': 'مبلغ التأمين', 'class': 'form-control'}),
            'access_code': forms.TextInput(attrs={'placeholder': 'كود الدخول (اختياري)', 'class': 'form-control'}),
            'terms': forms.Textarea(attrs={'rows': 6, 'placeholder': 'شروط المزاد...', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class BidForm(forms.ModelForm):
    class Meta:
        model = Bid
        fields = ['amount']
        widgets = {
            'amount': forms.NumberInput(attrs={'placeholder': 'المبلغ', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class BuildingRequestForm(forms.ModelForm):
    class Meta:
        model = BuildingRequest
        fields = ['full_name', 'phone', 'email', 'governorate', 'city', 'district', 'address', 
                  'project_type', 'estimated_area', 'estimated_budget', 'expected_start_date', 
                  'expected_completion_date', 'priority', 'description', 'requirements']
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'الاسم الكامل', 'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'placeholder': 'رقم الهاتف', 'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'placeholder': 'البريد الإلكتروني', 'class': 'form-control'}),
            'governorate': forms.Select(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'placeholder': 'المدينة', 'class': 'form-control'}),
            'district': forms.TextInput(attrs={'placeholder': 'المنطقة', 'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 2, 'placeholder': 'العنوان التفصيلي', 'class': 'form-control'}),
            'project_type': forms.TextInput(attrs={'placeholder': 'نوع المشروع', 'class': 'form-control'}),
            'estimated_area': forms.NumberInput(attrs={'placeholder': 'المساحة المقدرة (م²)', 'class': 'form-control'}),
            'estimated_budget': forms.NumberInput(attrs={'placeholder': 'الميزانية المقدرة', 'class': 'form-control'}),
            'expected_start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'expected_completion_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'وصف المشروع', 'class': 'form-control'}),
            'requirements': forms.Textarea(attrs={'rows': 3, 'placeholder': 'المتطلبات الخاصة', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class LandInfoForm(forms.ModelForm):
    class Meta:
        model = LandInfo
        fields = ['plot_location', 'area', 'width', 'length', 'land_type', 'deed_image']
        widgets = {
            'plot_location': forms.TextInput(attrs={'placeholder': 'موقع القطعة', 'class': 'form-control'}),
            'area': forms.NumberInput(attrs={'placeholder': 'مساحة الأرض (متر مربع)', 'class': 'form-control'}),
            'width': forms.NumberInput(attrs={'placeholder': 'العرض (متر)', 'class': 'form-control'}),
            'length': forms.NumberInput(attrs={'placeholder': 'الطول (متر)', 'class': 'form-control'}),
            'land_type': forms.Select(attrs={'class': 'form-control'}),
            'deed_image': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class BuildingDetailsForm(forms.ModelForm):
    class Meta:
        model = BuildingDetails
        fields = ['floors', 'rooms', 'bathrooms', 'has_garage', 'has_garden', 'has_elevator', 'architectural_style']
        widgets = {
            'floors': forms.NumberInput(attrs={'placeholder': 'عدد الطوابق', 'class': 'form-control'}),
            'rooms': forms.NumberInput(attrs={'placeholder': 'عدد الغرف', 'class': 'form-control'}),
            'bathrooms': forms.NumberInput(attrs={'placeholder': 'عدد الحمامات', 'class': 'form-control'}),
            'has_garage': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'has_garden': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'has_elevator': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'architectural_style': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['estimated_budget', 'finishing_level']
        widgets = {
            'estimated_budget': forms.NumberInput(attrs={'placeholder': 'الميزانية التقريبية', 'class': 'form-control'}),
            'finishing_level': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class QuoteForm(forms.ModelForm):
    class Meta:
        model = Quote
        fields = ['quote_type', 'provider_name', 'price', 'duration_days', 'description']
        widgets = {
            'quote_type': forms.Select(attrs={'class': 'form-control'}),
            'provider_name': forms.TextInput(attrs={'placeholder': 'اسم المزود', 'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'placeholder': 'السعر', 'class': 'form-control'}),
            'duration_days': forms.NumberInput(attrs={'placeholder': 'مدة التنفيذ (أيام)', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'الوصف', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class ContractorBidForm(forms.ModelForm):
    class Meta:
        model = ContractorBid
        fields = ['contractor_name', 'bid_amount', 'bid_description']
        widgets = {
            'contractor_name': forms.TextInput(attrs={'placeholder': 'اسم المقاول', 'class': 'form-control'}),
            'bid_amount': forms.NumberInput(attrs={'placeholder': 'مبلغ المزايدة', 'class': 'form-control'}),
            'bid_description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'وصف العرض', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class ContractorRatingForm(forms.ModelForm):
    class Meta:
        model = ContractorRating
        fields = ['contractor_name', 'rating', 'review']
        widgets = {
            'contractor_name': forms.TextInput(attrs={'placeholder': 'اسم المقاول', 'class': 'form-control'}),
            'rating': forms.NumberInput(attrs={'placeholder': 'التقييم (1-5)', 'class': 'form-control'}),
            'review': forms.Textarea(attrs={'rows': 5, 'placeholder': 'التقييم المفصل', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class FinancialTransactionForm(forms.ModelForm):
    class Meta:
        model = FinancialTransaction
        fields = ['property', 'transaction_type', 'sale_price', 'commission_type', 
                  'commission_rate', 'commission_amount', 'owner_name', 'additional_fees',
                  'platform_commission_rate', 'notes']
        widgets = {
            'property': forms.Select(attrs={'class': 'form-control', 'required': False}),
            'transaction_type': forms.Select(attrs={'class': 'form-control'}),
            'sale_price': forms.NumberInput(attrs={'placeholder': 'سعر البيع', 'class': 'form-control', 'required': False}),
            'commission_type': forms.Select(attrs={'class': 'form-control'}),
            'commission_rate': forms.NumberInput(attrs={'placeholder': 'نسبة العمولة %', 'class': 'form-control', 'required': False}),
            'commission_amount': forms.NumberInput(attrs={'placeholder': 'مبلغ العمولة', 'class': 'form-control', 'required': False}),
            'owner_name': forms.TextInput(attrs={'placeholder': 'اسم صاحب العقار', 'class': 'form-control', 'required': False}),
            'additional_fees': forms.NumberInput(attrs={'placeholder': 'رسوم إضافية', 'class': 'form-control', 'required': False}),
            'platform_commission_rate': forms.NumberInput(attrs={'placeholder': 'نسبة المنصة %', 'class': 'form-control', 'required': False}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'ملاحظات', 'class': 'form-control', 'required': False}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name not in ['transaction_type', 'commission_type']:
                field.required = False
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['category', 'title', 'amount', 'date', 'notes', 'receipt_image']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'placeholder': 'العنوان', 'class': 'form-control', 'required': False}),
            'amount': forms.NumberInput(attrs={'placeholder': 'المبلغ', 'class': 'form-control', 'required': False}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'required': False}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'ملاحظات', 'class': 'form-control', 'required': False}),
            'receipt_image': forms.FileInput(attrs={'class': 'form-control', 'required': False}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'category':
                field.required = False
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['payment_type', 'amount', 'payment_date', 'payment_method', 'notes']
        widgets = {
            'payment_type': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'placeholder': 'المبلغ', 'class': 'form-control'}),
            'payment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'payment_method': forms.TextInput(attrs={'placeholder': 'طريقة الدفع', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'ملاحظات', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class ProfitForm(forms.ModelForm):
    class Meta:
        model = Profit
        fields = ['profit_type', 'amount', 'property', 'client_name', 'client_phone', 'notes', 'date']
        widgets = {
            'profit_type': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'placeholder': 'مبلغ الربح', 'class': 'form-control'}),
            'property': forms.Select(attrs={'class': 'form-control'}),
            'client_name': forms.TextInput(attrs={'placeholder': 'اسم العميل', 'class': 'form-control'}),
            'client_phone': forms.TextInput(attrs={'placeholder': 'رقم العميل', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'ملاحظات', 'class': 'form-control'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # Filter properties to show only user's properties
        if user:
            from .models import Property
            self.fields['property'].queryset = Property.objects.filter(
                Q(owner=user) | Q(broker__user=user)
            ).distinct()
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class SubscriptionPlanForm(forms.ModelForm):
    class Meta:
        model = SubscriptionPlan
        fields = ['period', 'name', 'ads_limit', 'price', 'color', 'is_active']
        widgets = {
            'period': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'placeholder': 'اسم الخطة', 'class': 'form-control'}),
            'ads_limit': forms.NumberInput(attrs={'placeholder': 'عدد العقارات', 'class': 'form-control', 'min': '1'}),
            'price': forms.NumberInput(attrs={'placeholder': 'السعر', 'class': 'form-control', 'step': '0.01'}),
            'color': forms.TextInput(attrs={'placeholder': '#000000', 'class': 'form-control', 'type': 'color'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'



class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['report_type', 'reason', 'description', 'priority']
        widgets = {
            'report_type': forms.Select(attrs={'class': 'form-control'}),
            'reason': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'وصف المشكلة بالتفصيل...'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Update reason choices based on report type
        if 'report_type' in self.data:
            report_type = self.data['report_type']
            self.fields['reason'].choices = self._get_reason_choices(report_type)
        elif self.instance and self.instance.report_type:
            self.fields['reason'].choices = self._get_reason_choices(self.instance.report_type)
        else:
            self.fields['reason'].choices = Report.USER_REASON_CHOICES

    def _get_reason_choices(self, report_type):
        if report_type == Report.TYPE_USER:
            return Report.USER_REASON_CHOICES
        elif report_type == Report.TYPE_OFFICE:
            return Report.OFFICE_REASON_CHOICES
        elif report_type == Report.TYPE_COMMENT:
            return Report.COMMENT_REASON_CHOICES
        elif report_type == Report.TYPE_TECHNICAL:
            return Report.TECHNICAL_REASON_CHOICES
        return Report.USER_REASON_CHOICES


# User Settings Forms

class UserProfileForm(forms.ModelForm):
    """Form for user profile settings"""
    
    class Meta:
        model = UserSettings
        fields = ['phone', 'birth_date', 'gender', 'governorate', 'city', 'address', 'bio']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'رقم الهاتف'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'governorate': forms.Select(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'المدينة'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'العنوان الكامل'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'نبذة قصيرة عنك'}),
        }


class UserBasicInfoForm(forms.ModelForm):
    """Form for basic user info (User model)"""
    
    first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'الاسم الأول'}))
    last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'اسم العائلة'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'البريد الإلكتروني'}))
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


class UserSecurityForm(forms.Form):
    """Form for security settings"""
    
    current_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'كلمة المرور الحالية'}), required=False)
    new_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'كلمة المرور الجديدة'}), required=False)
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'تأكيد كلمة المرور'}), required=False)
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        current_password = cleaned_data.get('current_password')
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password or confirm_password:
            if not current_password:
                raise ValidationError('يرجى إدخال كلمة المرور الحالية')
            
            if not self.user.check_password(current_password):
                raise ValidationError('كلمة المرور الحالية غير صحيحة')
            
            if new_password != confirm_password:
                raise ValidationError('كلمات المرور غير متطابقة')
            
            if len(new_password) < 8:
                raise ValidationError('كلمة المرور يجب أن تكون 8 أحرف على الأقل')
        
        return cleaned_data


class UserNotificationForm(forms.ModelForm):
    """Form for notification settings"""
    
    class Meta:
        model = UserSettings
        fields = ['notification_new_properties', 'notification_messages', 'notification_offers', 
                  'notification_matching', 'email_notifications', 'app_notifications']
        widgets = {
            'notification_new_properties': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notification_messages': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notification_offers': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notification_matching': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'app_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class UserPrivacyForm(forms.ModelForm):
    """Form for privacy settings"""
    
    class Meta:
        model = UserSettings
        fields = ['show_phone', 'show_email', 'who_can_message']
        widgets = {
            'show_phone': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_email': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'who_can_message': forms.Select(attrs={'class': 'form-control'}),
        }


class UserPreferencesForm(forms.ModelForm):
    """Form for user preferences"""
    
    class Meta:
        model = UserSettings
        fields = ['dark_mode', 'language', 'currency', 'property_view_mode', 'properties_per_page']
        widgets = {
            'dark_mode': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'language': forms.Select(attrs={'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'property_view_mode': forms.Select(attrs={'class': 'form-control'}),
            'properties_per_page': forms.Select(attrs={'class': 'form-control'}),
        }


class BlockUserForm(forms.Form):
    """Form to block a user"""
    
    blocked_user = forms.ModelChoiceField(queryset=User.objects.all(), widget=forms.Select(attrs={'class': 'form-control'}), label='المستخدم')
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'سبب الحظر (اختياري)'}), label='السبب')
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclude current user and already blocked users
        blocked_ids = BlockedUser.objects.filter(blocker=user).values_list('blocked_id', flat=True)
        self.fields['blocked_user'].queryset = User.objects.exclude(id=user.id).exclude(id__in=blocked_ids)


class SavedSearchForm(forms.ModelForm):
    """Form to save a search"""
    
    class Meta:
        model = SavedSearch
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'اسم البحث المحفوظ'}),
        }


# Office Presence Forms

class OfficePresenceForm(forms.ModelForm):
    """Form for office presence status"""
    
    class Meta:
        model = OfficePresence
        fields = ['status', 'expected_return', 'absence_reason', 'auto_update_enabled', 'work_start', 'work_end', 'work_days']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'expected_return': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'absence_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'سبب الغياب (اختياري)'}),
            'auto_update_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'work_start': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'work_end': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'work_days': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add work days choices
        self.fields['work_days'].choices = [
            (0, 'الأحد'),
            (1, 'الاثنين'),
            (2, 'الثلاثاء'),
            (3, 'الأربعاء'),
            (4, 'الخميس'),
            (5, 'الجمعة'),
            (6, 'السبت'),
        ]


class QuickStatusForm(forms.Form):
    """Quick status update form"""
    
    status = forms.ChoiceField(choices=OfficePresence.STATUS_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    expected_return = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}))
    absence_reason = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))


class PresenceNotificationForm(forms.ModelForm):
    """Form to subscribe to presence notifications"""
    
    class Meta:
        model = PresenceNotification
        fields = []
        # No fields needed, just creates the subscription


# Broker Subscription Forms

class BrokerNotificationSettingsForm(forms.ModelForm):
    """Form for broker notification settings"""
    
    class Meta:
        model = BrokerNotificationSettings
        fields = ['notification_type', 'in_app_notifications', 'browser_notifications', 'email_notifications']
        widgets = {
            'notification_type': forms.Select(attrs={'class': 'form-control'}),
            'in_app_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'browser_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# Auction Advanced Features Forms

class AutoBidForm(forms.ModelForm):
    """Form for automatic bidding"""
    
    class Meta:
        model = AutoBid
        fields = ['max_amount', 'is_active']
        widgets = {
            'max_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'الحد الأقصى للمزايدة',
                'min': 0
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'max_amount': 'الحد الأقصى للمزايدة',
            'is_active': 'تفعيل المزايدة الآلية',
        }


class AuctionRatingForm(forms.ModelForm):
    """Form for rating auction participants"""
    
    class Meta:
        model = AuctionRating
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(attrs={'class': 'form-control'}),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'اكتب تعليقك هنا...'
            }),
        }
        labels = {
            'rating': 'التقييم',
            'comment': 'التعليق',
        }


class AuctionLiveStreamForm(forms.ModelForm):
    """Form for auction live streaming"""
    
    class Meta:
        model = AuctionLiveStream
        fields = ['stream_url', 'stream_key', 'platform', 'chat_enabled', 'recording_enabled']
        widgets = {
            'stream_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://youtube.com/watch?v=...'
            }),
            'stream_key': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'مفتاح البث (اختياري)'
            }),
            'platform': forms.Select(attrs={'class': 'form-control'}),
            'chat_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'recording_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'stream_url': 'رابط البث',
            'stream_key': 'مفتاح البث',
            'platform': 'المنصة',
            'chat_enabled': 'تفعيل الشات',
            'recording_enabled': 'تفعيل التسجيل',
        }


class AuctionAdvertisementForm(forms.ModelForm):
    """Form for auction advertisements"""
    
    class Meta:
        model = AuctionAdvertisement
        fields = ['platform', 'title', 'description', 'image_url', 'budget', 'start_date', 'end_date']
        widgets = {
            'platform': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'عنوان الإعلان'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'وصف الإعلان'}),
            'image_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'رابط الصورة'}),
            'budget': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'الميزانية'}),
            'start_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }
        labels = {
            'platform': 'المنصة',
            'title': 'عنوان الإعلان',
            'description': 'وصف الإعلان',
            'image_url': 'رابط الصورة',
            'budget': 'الميزانية',
            'start_date': 'تاريخ البدء',
            'end_date': 'تاريخ الانتهاء',
        }


class HotelSearchForm(forms.Form):
    """Form for searching hotels"""
    star_rating = forms.MultipleChoiceField(
        choices=Hotel.STAR_RATINGS,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='التصنيف'
    )
    price_range = forms.MultipleChoiceField(
        choices=Hotel.PRICE_RANGES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='السعر'
    )
    room_types = forms.MultipleChoiceField(
        choices=Hotel.ROOM_TYPES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='نوع الغرفة'
    )
    meal_plan = forms.ChoiceField(
        choices=[('', 'الكل')] + Hotel.MEAL_PLANS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='خطة الوجبات'
    )
    services = forms.MultipleChoiceField(
        choices=[
            ('wifi', 'واي فاي مجاني'),
            ('ac', 'تكييف'),
            ('parking', 'موقف سيارات'),
            ('pool', 'مسبح'),
            ('gym', 'نادي رياضي'),
            ('spa', 'سبا'),
            ('laundry', 'غسيل ملابس'),
            ('room_service', 'خدمة غرف 24 ساعة'),
            ('airport_transfer', 'نقل من وإلى المطار'),
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='الخدمات'
    )
    suitable_for = forms.MultipleChoiceField(
        choices=Hotel.SUITABLE_FOR,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='مناسب لـ'
    )
    governorate = forms.ChoiceField(
        choices=[('', 'كل المحافظات')] + IRAQ_GOVERNORATES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='المحافظة'
    )


class ResortSearchForm(forms.Form):
    """Form for searching resorts"""
    resort_type = forms.MultipleChoiceField(
        choices=Resort.RESORT_TYPES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='نوع المنتجع'
    )
    price_range = forms.MultipleChoiceField(
        choices=Hotel.PRICE_RANGES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='السعر'
    )
    accommodation_types = forms.MultipleChoiceField(
        choices=Resort.ACCOMMODATION_TYPES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='الإقامة'
    )
    facilities = forms.MultipleChoiceField(
        choices=[
            ('private_beach', 'شاطئ خاص'),
            ('pools', 'مسابح داخلية وخارجية'),
            ('water_park', 'ألعاب مائية'),
            ('spa', 'سبا وعلاج طبيعي'),
            ('gym', 'نادي رياضي'),
            ('sports', 'ملاعب رياضية'),
            ('restaurants', 'مطاعم وكافيهات'),
            ('event_halls', 'قاعات مناسبات'),
            ('kids_area', 'منطقة ألعاب أطفال'),
            ('boat_trips', 'رحلات بحرية'),
            ('bbq', 'جلسات خارجية وشواء'),
            ('parking', 'موقوف سيارات'),
            ('wifi', 'واي فاي مجاني'),
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='المرافق'
    )
    suitable_for = forms.MultipleChoiceField(
        choices=Resort.SUITABLE_FOR,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='مناسب لـ'
    )
    governorate = forms.ChoiceField(
        choices=[('', 'كل المحافظات')] + IRAQ_GOVERNORATES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='المحافظة'
    )