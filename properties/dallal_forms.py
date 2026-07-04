"""نماذج إدارة نظام الدلال"""

from django import forms
from .models import DallalGlobalSettings, BasicDallalSettings, PremiumDallalSettings, DallalSubscription


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
