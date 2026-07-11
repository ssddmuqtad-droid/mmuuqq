from django import forms
from django.contrib.auth.models import User

from .constants import IRAQ_GOVERNORATES
from .models import Broker, BrokerJoinRequest, Message, Office


def _fc(placeholder=''):
    attrs = {'class': 'form-control'}
    if placeholder:
        attrs['placeholder'] = placeholder
    return attrs


class BrokerJoinForm(forms.ModelForm):
    class Meta:
        model = BrokerJoinRequest
        fields = ['name', 'phone', 'governorate', 'office_name', 'id_card_image', 'email', 'notes']
        widgets = {
            'name': forms.TextInput(attrs=_fc('الاسم الكامل')),
            'phone': forms.TextInput(attrs=_fc('07XXXXXXXXX')),
            'governorate': forms.Select(attrs={'class': 'form-control'}),
            'office_name': forms.TextInput(attrs=_fc('اسم المكتب العقاري')),
            'email': forms.EmailInput(attrs=_fc('example@email.com')),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'ملاحظات إضافية (اختياري)'}),
            'id_card_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['governorate'].widget = forms.Select(
            choices=[('', 'اختر المحافظة')] + list(IRAQ_GOVERNORATES),
            attrs={'class': 'form-control'}
        )
        self.fields['id_card_image'].required = True


class BrokerCreateForm(forms.Form):
    username = forms.CharField(label='اسم المستخدم', widget=forms.TextInput(attrs=_fc('username')))
    password = forms.CharField(label='كلمة المرور', widget=forms.PasswordInput(attrs=_fc('********')))
    first_name = forms.CharField(label='الاسم', widget=forms.TextInput(attrs=_fc('الاسم الكامل')))
    phone = forms.CharField(label='الهاتف', widget=forms.TextInput(attrs=_fc('07XXXXXXXXX')))
    governorate = forms.ChoiceField(label='المحافظة', required=False, choices=[('', 'اختر المحافظة')] + list(IRAQ_GOVERNORATES))
    office_name = forms.CharField(label='المكتب', required=False, widget=forms.TextInput(attrs=_fc('المكتب العقاري')))
    role = forms.ChoiceField(
        label='الدور',
        choices=[(Broker.ROLE_SUB, 'دلال فرعي')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    def __init__(self, *args, creator=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.creator = creator
        if creator and hasattr(creator, 'broker_profile'):
            bp = creator.broker_profile
            if bp.role == Broker.ROLE_ADMIN:
                self.fields['role'].choices = Broker.ROLE_CHOICES
            elif bp.role == Broker.ROLE_MAIN:
                self.fields['role'].choices = [(Broker.ROLE_SUB, 'دلال فرعي')]

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('اسم المستخدم موجود مسبقاً')
        return username


class BrokerEditForm(forms.ModelForm):
    first_name = forms.CharField(label='الاسم', required=False, widget=forms.TextInput(attrs=_fc('الاسم')))

    class Meta:
        model = Broker
        fields = [
            'phone', 'office_name', 'governorate', 'role',
            'is_verified', 'is_active', 'is_suspended', 'bio',
            'profile_image', 'cover_image',
            # Sub-broker specific fields
            'commission_rate', 'commission_type', 'fixed_commission',
            'target_sales', 'performance_rating',
            'can_add_properties', 'can_edit_properties', 'can_delete_properties',
        ]
        widgets = {
            'phone': forms.TextInput(attrs=_fc('07XXXXXXXXX')),
            'office_name': forms.TextInput(attrs=_fc('المكتب')),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'profile_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'cover_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'commission_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'commission_type': forms.Select(attrs={'class': 'form-control'}),
            'fixed_commission': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'target_sales': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'performance_rating': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '5'}),
        }

    def __init__(self, *args, editor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.editor = editor
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
        # Change governorate to ChoiceField
        self.fields['governorate'] = forms.ChoiceField(
            label='المحافظة',
            required=False,
            choices=[('', 'اختر المحافظة')] + list(IRAQ_GOVERNORATES),
            widget=forms.Select(attrs={'class': 'form-control'})
        )
        # Add subscription info display
        if self.instance and self.instance.subscription_plan:
            self.fields['subscription_plan'].help_text = f'الحد الأقصى: {self.instance.subscription_plan.ads_limit} إعلان'
        if editor and hasattr(editor, 'broker_profile'):
            bp = editor.broker_profile
            if bp.role == Broker.ROLE_MAIN:
                self.fields.pop('role', None)
                self.fields.pop('is_verified', None)
                self.fields.pop('subscription_plan', None)
                # Keep sub-broker fields for main broker to manage
            elif bp.role == Broker.ROLE_SUB:
                # Sub-brokers can only edit limited fields
                allowed_fields = ['bio', 'target_sales']
                for field_name in list(self.fields.keys()):
                    if field_name not in allowed_fields and field_name != 'first_name':
                        self.fields.pop(field_name, None)

    def save(self, commit=True):
        broker = super().save(commit=False)
        if commit:
            broker.save()
            first_name = self.cleaned_data.get('first_name', '')
            if first_name and broker.user:
                broker.user.first_name = first_name
                broker.user.save(update_fields=['first_name'])
        return broker


class OfficeForm(forms.ModelForm):
    governorate = forms.ChoiceField(label='المحافظة', required=False, choices=[('', 'اختر المحافظة')] + list(IRAQ_GOVERNORATES))

    class Meta:
        model = Office
        fields = ['name', 'address', 'phone', 'governorate']
        widgets = {
            'name': forms.TextInput(attrs=_fc('اسم المكتب')),
            'address': forms.TextInput(attrs=_fc('العنوان')),
            'phone': forms.TextInput(attrs=_fc('الهاتف')),
        }


class MessageReplyForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'اكتب ردك...'}),
        }
