from django import forms
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.contrib.auth.models import User

from .constants import COMMON_NASIRIYAH_DISTRICTS, IRAQ_GOVERNORATES
from .models import Property, Message, SiteSettings, PropertyImage, PropertyVideo, PropertyNote, VirtualTour360, Auction, Bid, BuildingRequest, LandInfo, BuildingDetails, Budget, Blueprint, Quote, ProjectTracking, DeliveryMilestone, ContractorRating, ContractorBid, FinancialTransaction, Expense, Payment, Report, Profit, SubscriptionPlan, UserSettings, BlockedUser, SavedSearch, OfficePresence, PresenceNotification, BrokerSubscription, BrokerNotificationSettings, AutoBid, AuctionRating, AuctionLiveStream, AuctionAdvertisement, Hotel, Resort, PaymentMethod, PropertyPayment, PropertyNotification, SubscriptionRequest, BrokerChannel, ChannelRating, ChannelReview, ChannelReviewReply, ChannelMilestone, OutsideProperty, PropertyHotel, PropertyResort, PropertyDocument, PropertyMediaStats, WhatsAppMessage, TelegramMessage, AppointmentBooking, PropertyInquiry, LiveStream, LiveStreamComment, UserProfile, ServiceProvider, ServiceAdvertisement, HotelPage, HotelPost, HotelRoom, HotelOffer, HotelBooking, ServiceProviderCategory, ServiceProviderPage, ServiceProviderWork, ServiceProviderService, ServiceProviderGallery, ServiceProviderVideo, ServiceProvider360, ServiceProviderFollower, ServiceProviderRating, ServiceProviderContact, ServiceProviderQuote, FreelanceJob, FreelanceJobImage, FreelanceJobVideo


def _fc(placeholder=''):
    attrs = {'class': 'form-control'}
    if placeholder:
        attrs['placeholder'] = placeholder
    return attrs


class PropertySearchForm(forms.Form):
    q = forms.CharField(required=False, label='بحث', widget=forms.TextInput(attrs=_fc('ابحث عن عقار، فندق، منتجع...')))
    governorate = forms.ChoiceField(required=False, label='المحافظة', choices=[('', 'كل المحافظات')] + list(IRAQ_GOVERNORATES))
    district = forms.CharField(required=False, label='الحي/المنطقة', widget=forms.TextInput(attrs=_fc('الحي/المنطقة')))
    city = forms.CharField(required=False, label='المدينة', widget=forms.TextInput(attrs=_fc('المدينة')))
    country = forms.CharField(required=False, label='الدولة', widget=forms.TextInput(attrs=_fc('الدولة')))
    street = forms.CharField(required=False, label='الشارع', widget=forms.TextInput(attrs=_fc('الشارع')))
    type = forms.ChoiceField(required=False, label='نوع العقار', choices=[('', 'كل الأنواع')])
    status = forms.ChoiceField(required=False, label='الحالة', choices=[('', 'كل الحالات')])
    price_min = forms.IntegerField(required=False, label='السعر من', validators=[MinValueValidator(0)])
    price_max = forms.IntegerField(required=False, label='السعر إلى', validators=[MinValueValidator(0)])
    currency = forms.ChoiceField(required=False, label='العملة', choices=[('', 'كل العملات'), ('IQD', 'دينار عراقي'), ('USD', 'دولار أمريكي')])
    area_min = forms.IntegerField(required=False, label='المساحة من', validators=[MinValueValidator(0)])
    area_max = forms.IntegerField(required=False, label='المساحة إلى', validators=[MinValueValidator(0)])
    bedrooms = forms.IntegerField(required=False, label='الغرف', validators=[MinValueValidator(0)])
    bathrooms = forms.IntegerField(required=False, label='الحمامات', validators=[MinValueValidator(0)])
    floors = forms.IntegerField(required=False, label='الطوابق', validators=[MinValueValidator(0)])
    year_built = forms.IntegerField(required=False, label='سنة البناء', validators=[MinValueValidator(0)])
    property_condition = forms.ChoiceField(required=False, label='حالة العقار', choices=[('', 'كل الحالات'), ('new', 'جديد'), ('used', 'مستعمل'), ('under_construction', 'قيد البناء')])
    category = forms.ChoiceField(required=False, label='القسم', choices=[
        ('', 'كل الأقسام'),
        ('property_iraq', 'عقار داخل العراق'),
        ('property_outside', 'عقار خارج العراق'),
        ('hotel', 'فندق'),
        ('resort', 'منتجع'),
        ('service', 'خدمات'),
        ('building_request', 'طلبات البناء'),
        ('auction', 'مزادات'),
        ('job', 'فرص العمل')
    ])
    featured_only = forms.BooleanField(required=False, label='المميزة فقط')
    verified_only = forms.BooleanField(required=False, label='الموثقة فقط')
    new_only = forms.BooleanField(required=False, label='الجديدة فقط')
    broker_name = forms.CharField(required=False, label='اسم الدلال', widget=forms.TextInput(attrs=_fc('اسم الدلال')))
    rating_min = forms.IntegerField(required=False, label='التقييم الأدنى', validators=[MinValueValidator(0)])
    sort = forms.ChoiceField(required=False, label='ترتيب')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['type'].choices = [('', 'كل الأنواع')] + list(Property.PROPERTY_TYPES)
        # Update status choices for new payment system
        self.fields['status'].choices = [
            ('', 'كل الحالات'),
            (Property.STATUS_PUBLISHED, 'منشور'),
            (Property.STATUS_DRAFT, 'مسودة'),
            (Property.STATUS_PAID, 'تم الدفع'),
            (Property.STATUS_PENDING_APPROVAL, 'بانتظار الموافقة'),
            (Property.STATUS_EXPIRED, 'منتهي'),
        ]
        from .constants import SORT_CHOICES
        self.fields['sort'].choices = SORT_CHOICES
        for name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            'title', 'type', 'status', 'category',
            # Property Purpose and Condition
            'purpose', 'property_condition', 'ownership_status',
            # Property ID and Owner
            'property_number', 'owner_name',
            # Price
            'price', 'negotiable', 'currency', 'original_price',
            # Additional Price Details
            'price_per_meter', 'down_payment', 'installments', 'annual_maintenance_fee',
            # Location - Iraq
            'governorate', 'city', 'district', 'subdistrict', 'nahiyah', 'region', 'street', 'landmark', 'location',
            # Location - Outside Iraq
            'country', 'city_outside', 'area_outside', 'postal_code', 'taxes', 'registration_fees', 'foreign_ownership_laws',
            # GPS
            'latitude', 'longitude', 'nearest_landmark', 'distance_to_city_center', 'distance_to_airport',
            # Area and Building
            'total_area', 'building_area', 'area',
            # Building Details
            'facade', 'direction', 'year_built', 'building_condition', 'total_floors', 'floor_number',
            'property_age', 'last_renovation',
            # Additional Building Details
            'floor_type', 'roof_type', 'wall_type', 'finish_condition', 'last_maintenance',
            # Room Details
            'bedrooms', 'living_rooms', 'dining_rooms', 'bathrooms', 'kitchens', 'balconies',
            # Parking
            'parking', 'parking_spaces', 'parking_type',
            # Amenities
            'furnished', 'has_pool', 'has_garden', 'has_elevator', 'has_generator',
            'has_national_electricity', 'has_water', 'has_internet', 'has_sewerage',
            'has_heating', 'has_cooling', 'has_solar_power',
            # Security
            'has_security_system', 'has_cctv', 'has_alarm',
            # Hotel/Resort specific
            'hotel_stars', 'hotel_rating', 'hotel_rooms', 'hotel_suites', 'hotel_family_rooms',
            'has_restaurant', 'has_cafe', 'has_swimming_pool', 'has_gym', 'has_spa',
            'has_conference_hall', 'has_wifi', 'has_parking', 'has_room_service',
            'has_laundry', 'has_airport_shuttle',
            'resort_capacity', 'resort_activities', 'booking_available', 'booking_url',
            'min_booking_duration', 'max_booking_duration',
            # Virtual Tour and Media
            'virtual_tour_url', 'vr_tour_url', 'ar_available',
            # Live Streaming
            'live_stream_enabled', 'live_stream_url', 'live_stream_scheduled', 'live_stream_status',
            # AI Features
            'ai_generated_description', 'ai_suggested_price', 'ai_keywords', 'ai_image_enhanced',
            # Additional fees
            'maintenance_fee', 'hoa_fee',
            # Accessibility
            'wheelchair_accessible', 'has_ramp', 'has_elevator_accessibility',
            # Green features
            'energy_efficient', 'has_green_building_cert', 'has_smart_home',
            'has_double_glazing', 'has_insulation',
            # View
            'view_type',
            # Description
            'description', 'phone',
            # Publication
            'publication_type', 'publication_days', 'duration_days', 'is_featured', 'is_promoted',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'location': forms.TextInput(attrs={'placeholder': 'الحي، الشارع، أقرب معلم', 'class': 'form-control'}),
            'foreign_ownership_laws': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'resort_activities': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'ai_keywords': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'كلمات مفتاحية مفصولة بفاصلة'}),
            'district': forms.TextInput(attrs={'placeholder': 'مثال: حي الشموخ', 'class': 'form-control'}),
            'street': forms.TextInput(attrs={'placeholder': 'مثال: شارع 40', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'publication_type': forms.Select(attrs={'class': 'form-control'}),
            'publication_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'duration_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 365}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add detailed property type choices with categories
        type_choices = [
            ('', 'اختر نوع العقار'),
            # --- عقارات داخل العراق ---
            ('inside_iraq_header', '🏠 عقارات داخل العراق'),
            ('apartment', 'شقة'),
            ('house', 'منزل'),
            ('villa', 'فيلا'),
            ('duplex', 'دوبلكس'),
            ('residential_complex', 'مجمع سكني'),
            ('shop', 'محل تجاري'),
            ('office', 'مكتب'),
            ('mall', 'مول / مركز تجاري'),
            ('car_showroom', 'معرض سيارات'),
            ('warehouse', 'مخزن'),
            ('residential_building', 'بناية سكنية'),
            ('commercial_building', 'عمارة تجارية'),
            ('investment_land', 'أرض للاستثمار'),
            ('apartment_complex', 'مجمع شقق'),
            ('residential_land', 'أرض سكنية'),
            ('agricultural_land', 'أرض زراعية'),
            ('commercial_land', 'أرض تجارية'),
            # --- عقارات خارج العراق ---
            ('outside_iraq_header', '🌍 عقارات خارج العراق'),
            ('outside_apartment', 'شقة خارج العراق'),
            ('outside_villa', 'فيلا خارج العراق'),
            ('outside_palace', 'قصر خارج العراق'),
            ('outside_house', 'منزل خارج العراق'),
            ('outside_land', 'أرض خارج العراق'),
            ('outside_commercial', 'عقار تجاري خارج العراق'),
            # --- فنادق ---
            ('hotels_header', '🏨 فنادق'),
            ('hotel', 'فندق'),
            ('small_hotel', 'فندق صغير'),
            ('hotel_apartment', 'شقق فندقية'),
            # --- منتجعات وأماكن سياحية ---
            ('tourism_header', '🏖️ منتجعات وأماكن سياحية'),
            ('resort', 'منتجع'),
            ('chalet', 'شاليه'),
            ('tourism_house', 'بيت سياحي'),
        ]
        
        self.fields['type'].choices = type_choices
        self.fields['type'].widget.attrs['class'] = 'form-control property-type-select'
        
        # Update status choices for new payment system
        self.fields['status'].choices = [
            (Property.STATUS_DRAFT, 'مسودة'),
            (Property.STATUS_PAID, 'تم الدفع'),
            (Property.STATUS_PENDING_APPROVAL, 'بانتظار الموافقة'),
            (Property.STATUS_PUBLISHED, 'منشور'),
            (Property.STATUS_REJECTED, 'مرفوض'),
            (Property.STATUS_EXPIRED, 'منتهي'),
        ]
        # Set default status to draft
        if 'status' in self.fields:
            self.fields['status'].initial = Property.STATUS_DRAFT
        
        # Publication type choices
        if 'publication_type' in self.fields:
            self.fields['publication_type'].choices = [
                ('normal', 'نشر عادي'),
                ('featured', 'نشر مميز'),
            ]
            self.fields['publication_type'].initial = 'normal'
            self.fields['publication_type'].required = False
        if 'publication_days' in self.fields:
            self.fields['publication_days'].required = False

    def clean_type(self):
        property_type = self.cleaned_data.get('type')
        # Prevent selecting header options
        header_options = ['inside_iraq_header', 'outside_iraq_header', 'hotels_header', 'tourism_header']
        if property_type in header_options:
            raise forms.ValidationError('يرجى اختيار نوع عقار محدد')
        return property_type


class OutsidePropertyForm(forms.ModelForm):
    """Form for properties outside Iraq"""
    class Meta:
        model = OutsideProperty
        fields = [
            'state_province', 'local_currency', 'taxes', 'registration_fees',
            'foreign_ownership_laws', 'hoa_fees', 'property_tax'
        ]
        widgets = {
            'foreign_ownership_laws': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'taxes': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'registration_fees': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'hoa_fees': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'property_tax': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class PropertyHotelForm(forms.ModelForm):
    """Form for hotel properties"""
    class Meta:
        model = PropertyHotel
        fields = [
            'hotel_name', 'star_rating', 'classification', 'total_rooms',
            'suites', 'family_rooms', 'price_per_night', 'currency',
            'has_restaurant', 'has_cafe', 'has_pool', 'has_gym', 'has_spa',
            'has_conference_hall', 'direct_booking', 'booking_url'
        ]
        widgets = {
            'price_per_night': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'booking_url': forms.URLInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class PropertyResortForm(forms.ModelForm):
    """Form for resort properties"""
    class Meta:
        model = PropertyResort
        fields = [
            'resort_type', 'resort_name', 'max_guests', 'min_guests',
            'price_per_night', 'price_per_week', 'currency',
            'min_booking_duration', 'max_booking_duration',
            'has_wifi', 'has_kitchen', 'has_bbq', 'has_playground', 'has_parking',
            'activities'
        ]
        widgets = {
            'activities': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'price_per_night': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'price_per_week': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class PropertyImageForm(forms.ModelForm):
    """Form for property images"""
    class Meta:
        model = PropertyImage
        fields = ['image', 'caption', 'sort_order', 'is_primary', 'image_type']
        widgets = {
            'caption': forms.TextInput(attrs={'class': 'form-control'}),
            'sort_order': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class PropertyVideoForm(forms.ModelForm):
    """Form for property videos"""
    class Meta:
        model = PropertyVideo
        fields = ['video', 'caption', 'sort_order', 'video_type', 'duration']
        widgets = {
            'caption': forms.TextInput(attrs={'class': 'form-control'}),
            'sort_order': forms.NumberInput(attrs={'class': 'form-control'}),
            'duration': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class VirtualTour360Form(forms.ModelForm):
    """Form for 360 virtual tours"""
    class Meta:
        model = VirtualTour360
        fields = ['title', 'tour_type', 'image', 'tour_file', 'external_url', 'external_service', 'description', 'order', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'external_url': forms.URLInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class PropertyDocumentForm(forms.ModelForm):
    """Form for property documents"""
    class Meta:
        model = PropertyDocument
        fields = ['document_type', 'title', 'file', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class AppointmentBookingForm(forms.ModelForm):
    """Form for appointment bookings"""
    class Meta:
        model = AppointmentBooking
        fields = ['client_name', 'client_phone', 'client_email', 'appointment_date', 'notes']
        widgets = {
            'appointment_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class PropertyInquiryForm(forms.ModelForm):
    """Form for property inquiries"""
    class Meta:
        model = PropertyInquiry
        fields = ['inquiry_type', 'name', 'email', 'phone', 'subject', 'message', 'preferred_contact_method']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content', 'message_type']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4, 'placeholder': 'اكتب رسالتك...', 'class': 'form-control'}),
            'message_type': forms.Select(attrs={'class': 'form-control'}),
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
                  'access_type', 'access_code', 'is_closed', 'is_featured', 'terms', 'duration_days']
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
            'access_type': forms.Select(attrs={'class': 'form-control'}),
            'access_code': forms.TextInput(attrs={'placeholder': 'كود الدخول (اختياري)', 'class': 'form-control'}),
            'terms': forms.Textarea(attrs={'rows': 6, 'placeholder': 'شروط المزاد...', 'class': 'form-control'}),
            'duration_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 365}),
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
                  'expected_completion_date', 'priority', 'description', 'requirements', 
                  'is_public', 'is_featured', 'duration_days']
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
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'duration_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 365}),
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


class ServiceProviderForm(forms.ModelForm):
    class Meta:
        model = ServiceProvider
        fields = ['business_name', 'service_type', 'description', 'phone', 'whatsapp', 'email', 
                  'address', 'governorate', 'years_experience', 'team_size', 'working_hours',
                  'min_price', 'max_price', 'price_unit', 'licenses', 'logo', 'cover_image']
        widgets = {
            'business_name': forms.TextInput(attrs={'placeholder': 'اسم العمل/الشركة', 'class': 'form-control'}),
            'service_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'وصف الخدمات', 'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'placeholder': 'رقم الهاتف', 'class': 'form-control'}),
            'whatsapp': forms.TextInput(attrs={'placeholder': 'واتساب', 'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'placeholder': 'البريد الإلكتروني', 'class': 'form-control'}),
            'address': forms.TextInput(attrs={'placeholder': 'العنوان', 'class': 'form-control'}),
            'governorate': forms.Select(attrs={'class': 'form-control'}),
            'years_experience': forms.NumberInput(attrs={'placeholder': 'سنوات الخبرة', 'class': 'form-control'}),
            'team_size': forms.NumberInput(attrs={'placeholder': 'حجم الفريق', 'class': 'form-control'}),
            'working_hours': forms.TextInput(attrs={'placeholder': 'ساعات العمل', 'class': 'form-control'}),
            'min_price': forms.NumberInput(attrs={'placeholder': 'أقل سعر', 'class': 'form-control'}),
            'max_price': forms.NumberInput(attrs={'placeholder': 'أعلى سعر', 'class': 'form-control'}),
            'price_unit': forms.TextInput(attrs={'placeholder': 'وحدة السعر', 'class': 'form-control'}),
            'licenses': forms.Textarea(attrs={'rows': 3, 'placeholder': 'التراخيص والشهادات', 'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'cover_image': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class ServiceAdvertisementForm(forms.ModelForm):
    class Meta:
        model = ServiceAdvertisement
        fields = ['title', 'description', 'service_type', 'project_type', 'location', 'governorate',
                  'price', 'price_description', 'completion_time', 'includes', 'requirements', 
                  'cover_image', 'is_featured']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'عنوان الإعلان', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'وصف الإعلان', 'class': 'form-control'}),
            'service_type': forms.Select(attrs={'class': 'form-control'}),
            'project_type': forms.TextInput(attrs={'placeholder': 'نوع المشروع', 'class': 'form-control'}),
            'location': forms.TextInput(attrs={'placeholder': 'الموقع', 'class': 'form-control'}),
            'governorate': forms.Select(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'placeholder': 'السعر', 'class': 'form-control'}),
            'price_description': forms.TextInput(attrs={'placeholder': 'وصف السعر', 'class': 'form-control'}),
            'completion_time': forms.TextInput(attrs={'placeholder': 'وقت الإنجاز', 'class': 'form-control'}),
            'includes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'ما يشمله العرض', 'class': 'form-control'}),
            'requirements': forms.Textarea(attrs={'rows': 3, 'placeholder': 'المتطلبات', 'class': 'form-control'}),
            'cover_image': forms.FileInput(attrs={'class': 'form-control'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
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


class UserProfileImageForm(forms.ModelForm):
    """Form for user profile images"""
    
    class Meta:
        model = UserProfile
        fields = ['profile_image', 'cover_image']
        widgets = {
            'profile_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'cover_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
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
        choices=Resort.RESORT_TYPE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='نوع المنتجع'
    )
    price_range = forms.MultipleChoiceField(
        choices=[
            ('0-50000', 'أقل من 50,000'),
            ('50000-100000', '50,000 - 100,000'),
            ('100000-200000', '100,000 - 200,000'),
            ('200000-500000', '200,000 - 500,000'),
            ('500000+', 'أكثر من 500,000'),
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='السعر'
    )
    governorate = forms.ChoiceField(
        choices=[
            ('', 'كل المحافظات'),
            ('بغداد', 'بغداد'),
            ('البصرة', 'البصرة'),
            ('نينوى', 'نينوى'),
            ('أربيل', 'أربيل'),
            ('النجف', 'النجف'),
            ('كربلاء', 'كربلاء'),
            ('السليمانية', 'السليمانية'),
            ('ديالى', 'ديالى'),
            ('بابل', 'بابل'),
            ('واسط', 'واسط'),
            ('ميسان', 'ميسان'),
            ('ذي قار', 'ذي قار'),
            ('المثنى', 'المثنى'),
            ('القادسية', 'القادسية'),
            ('كركوك', 'كركوك'),
            ('صلاح الدين', 'صلاح الدين'),
            ('الأنبار', 'الأنبار'),
            ('دهوك', 'دهوك'),
            ('حلبجة', 'حلبجة'),
        ],
        required=False,
        label='المحافظة'
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
    rating = forms.ChoiceField(
        choices=[
            ('', 'كل التقييمات'),
            ('5', '5 نجوم'),
            ('4', '4 نجوم'),
            ('3', '3 نجوم'),
            ('2', 'نجمتان'),
            ('1', 'نجمة'),
        ],
        required=False,
        label='التقييم'
    )


# ==================== Payment System Forms ====================

class PropertyPublicationForm(forms.Form):
    """Form for choosing publication type and duration"""
    
    PUBLICATION_TYPE_CHOICES = [
        ('normal', 'نشر عادي'),
        ('featured', 'نشر مميز'),
    ]
    
    DURATION_CHOICES = [
        (1, 'يوم واحد'),
        (7, '7 أيام'),
        (15, '15 يوم'),
        (30, '30 يوم'),
        (60, '60 يوم'),
        (90, '90 يوم'),
        (180, '6 أشهر'),
        (365, 'سنة'),
        (1825, '5 سنوات'),
    ]
    
    publication_type = forms.ChoiceField(
        choices=PUBLICATION_TYPE_CHOICES,
        label='نوع النشر',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    publication_days = forms.ChoiceField(
        choices=DURATION_CHOICES,
        label='مدة النشر',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, daily_price=50.00, featured_price=0.00, **kwargs):
        super().__init__(*args, **kwargs)
        self.daily_price = daily_price
        self.featured_price = featured_price
    
    def calculate_total(self):
        """Calculate total cost"""
        cleaned_data = self.cleaned_data
        days = int(cleaned_data.get('publication_days', 1))
        pub_type = cleaned_data.get('publication_type', 'normal')
        
        base_amount = days * self.daily_price
        if pub_type == 'featured':
            base_amount += self.featured_price
        
        return base_amount


class PropertyPaymentForm(forms.ModelForm):
    """Form for property payment"""
    
    class Meta:
        model = PropertyPayment
        fields = ['payment_method', 'payment_proof']
        widgets = {
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'payment_proof': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*,.pdf'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter active payment methods
        self.fields['payment_method'].queryset = PaymentMethod.objects.filter(is_active=True)
        self.fields['payment_method'].label = 'طريقة الدفع'
        self.fields['payment_proof'].label = 'إيصال الدفع (اختياري)'


class PaymentMethodForm(forms.ModelForm):
    """Form for admin to manage payment methods"""
    
    class Meta:
        model = PaymentMethod
        fields = ['name', 'is_active', 'icon', 'description']
        widgets = {
            'name': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'اسم الأيقونة (مثال: 💳)'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].label = 'طريقة الدفع'
        self.fields['is_active'].label = 'نشط'
        self.fields['icon'].label = 'أيقونة'
        self.fields['description'].label = 'الوصف'


class SubscriptionRequestForm(forms.ModelForm):
    """Form for brokers to request subscription via chat"""
    
    class Meta:
        model = SubscriptionRequest
        fields = ['custom_plan_name', 'custom_price', 'custom_duration', 'custom_properties_limit', 'message']
        widgets = {
            'custom_plan_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'اسم الباقة المطلوبة'}),
            'custom_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'السعر المطلوب'}),
            'custom_duration': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'مثال: شهر، 3 أشهر، سنة'}),
            'custom_properties_limit': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'عدد العقارات المطلوب'}),
            'message': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'رسالة إضافية للإدارة'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['custom_plan_name'].label = 'اسم الباقة'
        self.fields['custom_price'].label = 'السعر (د.ع)'
        self.fields['custom_duration'].label = 'المدة'
        self.fields['custom_properties_limit'].label = 'عدد العقارات'
        self.fields['message'].label = 'رسالة للإدارة'


class ChannelRatingForm(forms.ModelForm):
    """نموذج تقييم القنوات"""
    
    class Meta:
        model = ChannelRating
        fields = [
            'rating', 'content_quality_rating', 'response_speed_rating',
            'trust_rating', 'variety_rating', 'review'
        ]
        widgets = {
            'rating': forms.Select(attrs={'class': 'form-control'}),
            'content_quality_rating': forms.Select(attrs={'class': 'form-control'}),
            'response_speed_rating': forms.Select(attrs={'class': 'form-control'}),
            'trust_rating': forms.Select(attrs={'class': 'form-control'}),
            'variety_rating': forms.Select(attrs={'class': 'form-control'}),
            'review': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'اكتب مراجعتك...'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # إضافة خيارات التقييم 1-5
        rating_choices = [(i, f'{i} ⭐') for i in range(1, 6)]
        for field in ['rating', 'content_quality_rating', 'response_speed_rating', 'trust_rating', 'variety_rating']:
            self.fields[field].choices = rating_choices
            self.fields[field].required = False
        
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class ChannelReviewForm(forms.ModelForm):
    """نموذج مراجعة القنوات"""
    
    class Meta:
        model = ChannelReview
        fields = ['title', 'content', 'overall_rating', 'would_recommend']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'عنوان المراجعة'}),
            'content': forms.Textarea(attrs={'rows': 6, 'class': 'form-control', 'placeholder': 'اكتب تجربتك مع هذه القناة...'}),
            'overall_rating': forms.Select(attrs={'class': 'form-control'}),
            'would_recommend': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    # Add channel_id field separately (not in model)
    channel_id = forms.IntegerField(widget=forms.HiddenInput())
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['overall_rating'].choices = [(i, f'{i} ⭐') for i in range(1, 6)]
        
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class ChannelReviewReplyForm(forms.ModelForm):
    """نموذج الرد على مراجعة القناة"""
    
    class Meta:
        model = ChannelReviewReply
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'اكتب ردك...'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class ChannelMilestoneForm(forms.ModelForm):
    """نموذج إنجازات القنوات"""
    
    class Meta:
        model = ChannelMilestone
        fields = ['milestone_type', 'target_value']
        widgets = {
            'milestone_type': forms.Select(attrs={'class': 'form-control'}),
            'target_value': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class ChannelSearchForm(forms.Form):
    """نموذج البحث في القنوات"""


class LiveStreamForm(forms.ModelForm):
    """نموذج البث المباشر"""
    
    class Meta:
        model = LiveStream
        fields = [
            'property', 'broker', 'title', 'description', 'stream_url', 'stream_key',
            'platform', 'scheduled_start', 'scheduled_end', 'notify_subscribers', 'thumbnail'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'scheduled_start': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'scheduled_end': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class LiveStreamCommentForm(forms.ModelForm):
    """نموذج تعليق البث المباشر"""
    
    class Meta:
        model = LiveStreamComment
        fields = ['author_name', 'author_phone', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'اكتب تعليقك...'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class PropertyDocumentForm(forms.ModelForm):
    """نموذج مستندات العقار"""
    
    class Meta:
        model = PropertyDocument
        fields = ['document_type', 'title', 'file', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class PropertyVideoForm(forms.ModelForm):
    """نموذج فيديوهات العقار"""
    
    class Meta:
        model = PropertyVideo
        fields = ['video', 'caption', 'sort_order', 'video_type', 'duration']
        widgets = {
            'caption': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'عنوان الفيديو'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class ChannelSearchForm(forms.Form):
    """نموذج البحث في القنوات"""
    search_query = forms.CharField(required=False, label='بحث', widget=forms.TextInput(attrs={'placeholder': 'ابحث عن قناة...'}))
    governorate = forms.ChoiceField(required=False, label='المحافظة', choices=[('', 'كل المحافظات')])
    min_rating = forms.IntegerField(required=False, label='التقييم الأدنى', min_value=1, max_value=5)
    min_followers = forms.IntegerField(required=False, label='الحد الأدنى للمتابعين', min_value=0)
    is_verified = forms.BooleanField(required=False, label='الموثقة فقط')
    sort_by = forms.ChoiceField(required=False, label='ترتيب حسب', choices=[
        ('', 'الافتراضي'),
        ('followers', 'عدد المتابعين'),
        ('rating', 'التقييم'),
        ('properties', 'عدد العقارات'),
        ('views', 'عدد المشاهدات'),
        ('newest', 'الأحدث'),
    ])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # إضافة خيارات المحافظات
        from .constants import IRAQ_GOVERNORATES
        self.fields['governorate'].choices = [('', 'كل المحافظات')] + list(IRAQ_GOVERNORATES)
        
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


# ==================== Dynamic Category Forms ====================

class PropertyInsideIraqForm(forms.ModelForm):
    """نموذج عقارات داخل العراق"""
    
    # Media fields for handling uploads (handled separately in view)
    cover_image = forms.ImageField(required=False, label='صورة الغلاف')
    personal_image = forms.ImageField(required=False, label='صورة شخصية')
    property_video = forms.FileField(required=False, label='فيديو العقار')
    
    class Meta:
        model = Property
        fields = [
            'title', 'type', 'status',
            # Property Purpose and Condition
            'purpose', 'property_condition', 'ownership_status',
            # Property ID and Owner
            'property_number', 'owner_name',
            # Price
            'price', 'negotiable', 'currency',
            # Additional Price Details
            'price_per_meter', 'down_payment', 'installments', 'annual_maintenance_fee',
            # Location - Iraq
            'governorate', 'city', 'district', 'subdistrict', 'nahiyah', 'region', 'street', 'landmark', 'location',
            # GPS
            'latitude', 'longitude', 'nearest_landmark',
            # Area and Building
            'total_area', 'building_area', 'area',
            # Building Details
            'facade', 'direction', 'year_built', 'building_condition', 'total_floors', 'floor_number',
            # Additional Building Details
            'floor_type', 'roof_type', 'wall_type', 'finish_condition', 'last_maintenance',
            # Room Details
            'bedrooms', 'living_rooms', 'dining_rooms', 'bathrooms', 'kitchens', 'balconies',
            # Parking
            'parking', 'parking_spaces', 'parking_type',
            # Amenities
            'furnished', 'has_pool', 'has_garden', 'has_elevator', 'has_generator',
            'has_national_electricity', 'has_water', 'has_internet', 'has_solar_power',
            # Security
            'has_security_system', 'has_cctv', 'has_alarm',
            # Description
            'description', 'phone',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'location': forms.TextInput(attrs={'placeholder': 'الحي، الشارع، أقرب معلم', 'class': 'form-control'}),
            'district': forms.TextInput(attrs={'placeholder': 'مثال: حي الشموخ', 'class': 'form-control'}),
            'street': forms.TextInput(attrs={'placeholder': 'مثال: شارع 40', 'class': 'form-control'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Property type choices for inside Iraq
        type_choices = [
            ('', 'اختر نوع العقار'),
            ('apartment', 'شقة'),
            ('house', 'منزل'),
            ('villa', 'فيلا'),
            ('duplex', 'دوبلكس'),
            ('residential_complex', 'مجمع سكني'),
            ('shop', 'محل تجاري'),
            ('office', 'مكتب'),
            ('mall', 'مول / مركز تجاري'),
            ('warehouse', 'مخزن'),
            ('residential_building', 'بناية سكنية'),
            ('commercial_building', 'عمارة تجارية'),
            ('residential_land', 'أرض سكنية'),
            ('agricultural_land', 'أرض زراعية'),
            ('commercial_land', 'أرض تجارية'),
        ]
        self.fields['type'].choices = type_choices
        
        # Status choices
        self.fields['status'].choices = [
            (Property.STATUS_DRAFT, 'مسودة'),
            (Property.STATUS_PUBLISHED, 'منشور'),
        ]
        self.fields['status'].initial = Property.STATUS_DRAFT
        
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned = super().clean()
        governorate = (cleaned.get('governorate') or '').strip()
        city = (cleaned.get('city') or '').strip()
        district = (cleaned.get('district') or '').strip()
        location = (cleaned.get('location') or '').strip()
        area_sqm = cleaned.get('area')

        if not governorate:
            self.add_error('governorate', 'المحافظة مطلوبة')
        if not city:
            self.add_error('city', 'المدينة مطلوبة')
        if not district:
            self.add_error('district', 'الحي مطلوب')
        if not location:
            # Compose a usable address from available parts
            parts = [p for p in [governorate, city, cleaned.get('region'), district, cleaned.get('street')] if p]
            if parts:
                cleaned['location'] = '، '.join(parts)
            else:
                self.add_error('location', 'العنوان التفصيلي مطلوب')
        if area_sqm is None or area_sqm <= 0:
            self.add_error('area', 'المساحة يجب أن تكون أكبر من صفر')
        return cleaned


class PropertyOutsideIraqForm(forms.ModelForm):
    """نموذج عقارات خارج العراق"""
    
    # Media fields for handling uploads (handled separately in view)
    cover_image = forms.ImageField(required=False, label='صورة الغلاف')
    personal_image = forms.ImageField(required=False, label='صورة شخصية')
    property_video = forms.FileField(required=False, label='فيديو العقار')
    
    class Meta:
        model = Property
        fields = [
            'title', 'type', 'status',
            # Property Purpose and Condition
            'purpose', 'property_condition', 'ownership_status',
            # Property ID and Owner
            'property_number', 'owner_name',
            # Price
            'price', 'negotiable', 'currency', 'original_price',
            # Additional Price Details
            'price_per_meter', 'down_payment', 'installments', 'annual_maintenance_fee',
            # Location - Outside Iraq
            'country', 'city_outside', 'area_outside', 'postal_code', 'taxes', 'registration_fees', 'foreign_ownership_laws',
            # GPS
            'latitude', 'longitude', 'nearest_landmark',
            # Area and Building
            'total_area', 'building_area', 'area',
            # Building Details
            'facade', 'direction', 'year_built', 'building_condition', 'total_floors', 'floor_number',
            # Additional Building Details
            'floor_type', 'roof_type', 'wall_type', 'finish_condition', 'last_maintenance',
            # Room Details
            'bedrooms', 'living_rooms', 'dining_rooms', 'bathrooms', 'kitchens', 'balconies',
            # Additional
            'maintenance_fee', 'hoa_fee',
            # Investment info
            'description', 'phone',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'foreign_ownership_laws': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Property type choices for outside Iraq
        type_choices = [
            ('', 'اختر نوع العقار'),
            ('outside_apartment', 'شقة خارج العراق'),
            ('outside_villa', 'فيلا خارج العراق'),
            ('outside_palace', 'قصر خارج العراق'),
            ('outside_house', 'منزل خارج العراق'),
            ('outside_land', 'أرض خارج العراق'),
            ('outside_commercial', 'عقار تجاري خارج العراق'),
        ]
        self.fields['type'].choices = type_choices
        
        # Status choices
        self.fields['status'].choices = [
            (Property.STATUS_DRAFT, 'مسودة'),
            (Property.STATUS_PUBLISHED, 'منشور'),
        ]
        self.fields['status'].initial = Property.STATUS_DRAFT
        
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class PropertyHotelForm(forms.ModelForm):
    """نموذج فنادق"""
    
    # Media fields for handling uploads (handled separately in view)
    cover_image = forms.ImageField(required=False, label='صورة الغلاف')
    personal_image = forms.ImageField(required=False, label='صورة شخصية')
    property_video = forms.FileField(required=False, label='فيديو العقار')
    
    class Meta:
        model = PropertyHotel
        fields = [
            'hotel_name', 'star_rating', 'classification', 'total_rooms',
            'suites', 'family_rooms', 'price_per_night', 'currency',
            'has_restaurant', 'has_cafe', 'has_pool', 'has_gym', 'has_spa',
            'has_conference_hall', 'direct_booking', 'booking_url',
        ]
        widgets = {
            'booking_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'رابط الحجز'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Star rating choices
        STAR_RATING_CHOICES = [(i, f'{i} نجوم') for i in range(1, 6)]
        self.fields['star_rating'].choices = STAR_RATING_CHOICES
        
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class PropertyResortForm(forms.ModelForm):
    """نموذج منتجعات"""
    
    # Media fields for handling uploads (handled separately in view)
    cover_image = forms.ImageField(required=False, label='صورة الغلاف')
    personal_image = forms.ImageField(required=False, label='صورة شخصية')
    property_video = forms.FileField(required=False, label='فيديو العقار')
    
    class Meta:
        model = PropertyResort
        fields = [
            'resort_name', 'resort_type', 'max_guests', 'min_guests', 'max_rooms',
            # Location
            'governorate', 'city', 'district', 'address', 'latitude', 'longitude',
            # Pricing
            'price_per_night', 'price_per_week', 'price_per_month', 'currency',
            # Booking
            'min_booking_duration', 'max_booking_duration', 'check_in_time', 'check_out_time',
            # Services
            'has_wifi', 'has_kitchen', 'has_bbq', 'has_playground', 'has_parking',
            'has_pool', 'has_gym', 'has_spa', 'has_restaurant', 'has_ac', 'has_heating',
            'has_security', 'has_laundry', 'has_room_service', 'has_concierge',
            # Activities
            'activities',
            # Description
            'description', 'rules',
            # Contact
            'phone', 'whatsapp', 'email', 'website',
            # Status
            'is_active', 'featured',
        ]
        widgets = {
            'activities': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'الأنشطة المتاحة'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'وصف المنتجع'}),
            'rules': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'القواعد والشروط'}),
            'address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'العنوان التفصيلي'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'check_in_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'check_out_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Resort type choices - use the actual RESORT_TYPES from the model
        self.fields['resort_type'].choices = PropertyResort.RESORT_TYPES
        
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class DynamicPropertyForm(forms.Form):
    """نموذج ديناميكي لاختيار الفئة"""
    
    CATEGORY_CHOICES = [
        ('', 'اختر فئة العقار'),
        ('inside_iraq', '🏠 عقارات داخل العراق'),
        ('outside_iraq', '🌍 عقارات خارج العراق'),
        ('hotel', '🏨 فنادق'),
        ('resort', '🏖️ منتجعات وأماكن سياحية'),
    ]
    
    category = forms.ChoiceField(
        choices=CATEGORY_CHOICES,
        label='فئة العقار',
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'category-select'})
    )


# ==================== Forms لنظام الفنادق والمنتجعات الجديد ====================

class HotelPageForm(forms.ModelForm):
    """نموذج إنشاء/تعديل صفحة الفندق"""
    
    class Meta:
        model = HotelPage
        fields = [
            'page_type', 'name', 'description', 'cover_image', 'logo',
            'governorate', 'city', 'district', 'address', 'latitude', 'longitude',
            'phone', 'whatsapp', 'email', 'website', 'working_hours', 'working_days',
            'meta_title', 'meta_description', 'keywords'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class HotelPostForm(forms.ModelForm):
    """نموذج إنشاء/تعديل منشور الفندق"""
    
    class Meta:
        model = HotelPost
        fields = [
            'post_type', 'title', 'content', 'images', 'video_url', 'tour_360_url',
            'price', 'currency', 'discount_percentage', 'valid_from', 'valid_until'
        ]
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'images': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'أدخل روابط الصور JSON'}),
            'valid_from': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'valid_until': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class HotelRoomForm(forms.ModelForm):
    """نموذج إنشاء/تعديل غرفة الفندق"""
    
    class Meta:
        model = HotelRoom
        fields = [
            'room_type', 'room_number', 'title', 'description',
            'max_adults', 'max_children', 'max_guests',
            'price_per_night', 'currency', 'amenities',
            'images', 'video_url', 'tour_360_url',
            'area', 'floor'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'amenities': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'أدخل المرافق JSON'}),
            'images': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'أدخل روابط الصور JSON'}),
            'price_per_night': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'area': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class HotelOfferForm(forms.ModelForm):
    """نموذج إنشاء/تعديل عرض الفندق"""
    
    class Meta:
        model = HotelOffer
        fields = [
            'offer_type', 'title', 'description',
            'original_price', 'discounted_price', 'discount_percentage', 'currency',
            'valid_from', 'valid_until', 'images', 'terms_and_conditions'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'terms_and_conditions': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'images': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'أدخل روابط الصور JSON'}),
            'original_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discounted_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'valid_from': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'valid_until': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class HotelBookingForm(forms.ModelForm):
    """نموذج حجز الفندق"""
    
    class Meta:
        model = HotelBooking
        fields = [
            'room', 'offer', 'check_in', 'check_out', 'guests',
            'special_requests'
        ]
        widgets = {
            'check_in': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'check_out': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'special_requests': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


# ==================== Service Provider Forms ====================

class ServiceProviderPageForm(forms.ModelForm):
    """Form for creating/editing service provider page"""
    
    class Meta:
        model = ServiceProviderPage
        fields = [
            'page_type', 'name', 'description', 'profile_image', 'cover_image', 'logo',
            'category', 'sub_categories', 'years_of_experience', 'projects_count', 'clients_count',
            'governorate', 'city', 'working_areas', 'latitude', 'longitude',
            'phone', 'whatsapp', 'telegram', 'facebook', 'instagram', 'website',
            'working_hours', 'availability', 'meta_title', 'meta_description', 'meta_keywords'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'working_areas': forms.Textarea(attrs={'rows': 3}),
            'sub_categories': forms.CheckboxSelectMultiple(),
            'meta_description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs and not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-control'


class ServiceProviderWorkForm(forms.ModelForm):
    """Form for creating/editing service provider work"""
    
    class Meta:
        model = ServiceProviderWork
        fields = [
            'title', 'description', 'location', 'execution_date', 'duration',
            'estimated_price', 'before_image', 'after_image', 'is_featured', 'status'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'execution_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class ServiceProviderServiceForm(forms.ModelForm):
    """Form for creating/editing service provider service"""
    
    class Meta:
        model = ServiceProviderService
        fields = ['name', 'description', 'price', 'price_unit', 'is_active', 'order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class ServiceProviderGalleryForm(forms.ModelForm):
    """Form for adding images to service provider gallery"""
    
    class Meta:
        model = ServiceProviderGallery
        fields = ['image', 'caption', 'is_primary', 'order']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class ServiceProviderVideoForm(forms.ModelForm):
    """Form for adding videos to service provider"""
    
    class Meta:
        model = ServiceProviderVideo
        fields = ['title', 'video_url', 'thumbnail', 'description', 'is_primary', 'order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class ServiceProvider360Form(forms.ModelForm):
    """Form for adding 360 tours to service provider"""
    
    class Meta:
        model = ServiceProvider360
        fields = ['title', 'tour_url', 'thumbnail', 'description', 'is_primary', 'order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class ServiceProviderRatingForm(forms.ModelForm):
    """Form for rating service provider"""
    
    class Meta:
        model = ServiceProviderRating
        fields = ['rating', 'review']
        widgets = {
            'review': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class ServiceProviderContactForm(forms.ModelForm):
    """Form for contacting service provider"""
    
    class Meta:
        model = ServiceProviderContact
        fields = ['contact_type', 'name', 'email', 'phone', 'message']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class ServiceProviderQuoteForm(forms.ModelForm):
    """Form for requesting quote from service provider"""
    
    class Meta:
        model = ServiceProviderQuote
        fields = [
            'project_title', 'project_description', 'location', 'budget',
            'name', 'email', 'phone'
        ]
        widgets = {
            'project_description': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class FreelanceJobForm(forms.ModelForm):
    """Form for creating freelance job postings for employers"""
    
    class Meta:
        model = FreelanceJob
        fields = [
            'job_title', 'job_description', 'employer_type', 'industry_type',
            'required_experience', 'required_specialization', 'required_skills', 'required_education',
            'salary', 'payment_method', 'start_date', 'work_type',
            'governorate', 'city', 'address',
            'work_days', 'work_hours',
            'tools_equipment_provided', 'certificates_required',
            'employer_name', 'employer_description', 'website',
            'phone', 'whatsapp', 'email',
            'duration_days',
            'is_featured', 'is_urgent',
        ]
        widgets = {
            'job_title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'المسمى الوظيفي (مثل: كهربائي، سباك، مبرمج...)'}),
            'job_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'وصف الوظيفة والمهام'}),
            'employer_type': forms.Select(attrs={'class': 'form-control'}),
            'industry_type': forms.Select(attrs={'class': 'form-control'}),
            'required_experience': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'required_specialization': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'التخصص المطلوب'}),
            'required_skills': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'المهارات المطلوبة'}),
            'required_education': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'المؤهل المطلوب'}),
            'salary': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'الراتب المقدم'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'work_type': forms.Select(attrs={'class': 'form-control'}),
            'governorate': forms.Select(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'المدينة'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'العنوان التفصيلي'}),
            'work_days': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'أيام العمل'}),
            'work_hours': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ساعات العمل'}),
            'tools_equipment_provided': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'الأدوات والمعدات المتوفرة'}),
            'certificates_required': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'الشهادات المطلوبة'}),
            'employer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'اسم صاحب العمل/الشركة'}),
            'employer_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'نبذة عن صاحب العمل'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'رقم الهاتف'}),
            'whatsapp': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'واتساب'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'البريد الإلكتروني'}),
            'duration_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 365, 'placeholder': 'عدد الأيام'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_urgent': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add governorate choices
        self.fields['governorate'].choices = [('', 'اختر المحافظة')] + list(IRAQ_GOVERNORATES)
        
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class FreelanceJobImageForm(forms.ModelForm):
    """Form for uploading freelance job images"""
    
    class Meta:
        model = FreelanceJobImage
        fields = ['image', 'caption', 'order']
        widgets = {
            'caption': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'التعليق'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class FreelanceJobVideoForm(forms.ModelForm):
    """Form for uploading freelance job videos"""
    
    class Meta:
        model = FreelanceJobVideo
        fields = ['video', 'thumbnail', 'caption', 'order']
        widgets = {
            'caption': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'التعليق'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'