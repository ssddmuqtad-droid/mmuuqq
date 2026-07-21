"""نماذج إدارة نظام الدلال"""

from django import forms
from .models import DallalGlobalSettings, BasicDallalSettings, PremiumDallalSettings, DallalSubscription, TravelCompany


class DallalGlobalSettingsForm(forms.ModelForm):
    class Meta:
        model = DallalGlobalSettings
        fields = '__all__'
        widgets = {
            'is_dallal_system_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_brokers_per_user': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'max_properties_per_dallal': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'show_dallal_on_homepage': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'dallal_display_order': forms.Select(attrs={'class': 'form-control'}),
            'show_expired_dallal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class BasicDallalSettingsForm(forms.ModelForm):
    class Meta:
        model = BasicDallalSettings
        fields = '__all__'
        widgets = {
            'max_properties': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'duration_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'auto_renewal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'impressions_limit': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'is_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PremiumDallalSettingsForm(forms.ModelForm):
    class Meta:
        model = PremiumDallalSettings
        fields = '__all__'
        widgets = {
            'max_properties': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'duration_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'priority_display': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'impressions_limit': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'is_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'visual_badge': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'highlight_effect': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DallalSubscriptionForm(forms.ModelForm):
    class Meta:
        model = DallalSubscription
        fields = ['broker', 'subscription_type', 'start_date', 'end_date', 'auto_renewal']
        widgets = {
            'broker': forms.Select(attrs={'class': 'form-control'}),
            'subscription_type': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'auto_renewal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TravelCompanyForm(forms.ModelForm):
    """نموذج إنشاء شركة سفر للدلالين"""
    class Meta:
        model = TravelCompany
        fields = [
            'name', 'name_en', 'description', 'description_en',
            'company_type', 'travel_types', 'travel_scope',
            'departure_time', 'price',
            'phone', 'whatsapp', 'email', 'website',
            'address', 'governorate', 'city',
            'latitude', 'longitude',
            'logo', 'cover_image',
            'rating', 'reviews_count',
            'is_verified', 'is_featured', 'is_active',
            'duration_days'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'اسم الشركة بالعربية'}),
            'name_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company Name in English'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'وصف الشركة بالعربية'}),
            'description_en': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Company Description in English'}),
            'company_type': forms.Select(attrs={'class': 'form-control'}),
            'travel_types': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'أنواع السفر المدعومة (JSON format)'}),
            'travel_scope': forms.Select(attrs={'class': 'form-control'}),
            'departure_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0, 'placeholder': 'السعر'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'رقم الهاتف'}),
            'whatsapp': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'رقم الواتساب'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'البريد الإلكتروني'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'الموقع الإلكتروني'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'العنوان'}),
            'governorate': forms.Select(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'المدينة'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0000001', 'placeholder': 'خط العرض'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0000001', 'placeholder': 'خط الطول'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'cover_image': forms.FileInput(attrs={'class': 'form-control'}),
            'rating': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 5, 'step': 0.1}),
            'reviews_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'duration_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 365}),
        }
