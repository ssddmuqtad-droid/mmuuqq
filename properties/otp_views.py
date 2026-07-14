"""
نظام التحقق برقم OTP (One-Time Password)
للتسجيل واستعادة كلمة المرور
"""

from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import timedelta
import json
import logging

logger = logging.getLogger(__name__)


def send_otp_view(request):
    """إرسال رمز OTP إلى رقم الهاتف"""
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        purpose = request.POST.get('purpose', 'registration')
        
        if not phone:
            return JsonResponse({'success': False, 'error': 'رقم الهاتف مطلوب'})
        
        # التحقق من صيغة رقم الهاتف
        if not phone.startswith('07') or len(phone) != 11:
            return JsonResponse({'success': False, 'error': 'رقم الهاتف غير صحيح'})
        
        from .models import OTPVerification
        
        try:
            # توليد رمز OTP جديد
            otp = OTPVerification.generate_otp(phone, purpose)
            
            # محاكاة إرسال SMS (في الإنتاج، استخدم خدمة SMS حقيقية)
            # هنا سنعرض الرمز للمطور للاختبار
            logger.info(f"OTP Code for {phone}: {otp.code}")
            
            # في الإنتاج، استخدم خدمة SMS مثل:
            # send_sms(phone, f"رمز التحقق الخاص بـ دلال هو: {otp.code}")
            
            return JsonResponse({
                'success': True,
                'message': 'تم إرسال رمز التحقق بنجاح',
                'expires_in': 600  # 10 دقائق بالثواني
            })
            
        except Exception as e:
            logger.error(f"Error sending OTP: {str(e)}")
            return JsonResponse({'success': False, 'error': 'حدث خطأ أثناء إرسال رمز التحقق'})
    
    return JsonResponse({'success': False, 'error': 'طريقة الطلب غير صحيحة'})


@require_POST
def verify_otp_view(request):
    """التحقق من رمز OTP"""
    phone = request.POST.get('phone', '').strip()
    code = request.POST.get('code', '').strip()
    purpose = request.POST.get('purpose', 'registration')
    
    if not phone or not code:
        return JsonResponse({'success': False, 'error': 'رقم الهاتف ورمز التحقق مطلوبان'})
    
    from .models import OTPVerification
    
    try:
        # البحث عن آخر رمز OTP غير مستخدم
        otp = OTPVerification.objects.filter(
            phone=phone,
            purpose=purpose,
            is_verified=False
        ).order_by('-created_at').first()
        
        if not otp:
            return JsonResponse({'success': False, 'error': 'رمز التحقق غير موجود'})
        
        # التحقق من الرمز
        if otp.verify(code):
            return JsonResponse({
                'success': True,
                'message': 'تم التحقق بنجاح'
            })
        else:
            if otp.attempts >= 3:
                return JsonResponse({'success': False, 'error': 'تم تجاوز الحد الأقصى من المحاولات'})
            remaining_attempts = 3 - otp.attempts
            return JsonResponse({
                'success': False,
                'error': f'رمز التحقق غير صحيح. المحاولات المتبقية: {remaining_attempts}'
            })
            
    except Exception as e:
        logger.error(f"Error verifying OTP: {str(e)}")
        return JsonResponse({'success': False, 'error': 'حدث خطأ أثناء التحقق'})


def otp_verification_page(request):
    """صفحة إدخال رمز OTP"""
    phone = request.GET.get('phone', '')
    purpose = request.GET.get('purpose', 'registration')
    
    context = {
        'phone': phone,
        'purpose': purpose,
        'purpose_display': {
            'registration': 'تسجيل حساب جديد',
            'password_reset': 'استعادة كلمة المرور',
            'phone_verification': 'التحقق من رقم الهاتف'
        }.get(purpose, 'التحقق')
    }
    
    return render(request, 'properties/otp_verification.html', context)


def resend_otp_view(request):
    """إعادة إرسال رمز OTP"""
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        purpose = request.POST.get('purpose', 'registration')
        
        if not phone:
            return JsonResponse({'success': False, 'error': 'رقم الهاتف مطلوب'})
        
        from .models import OTPVerification
        
        try:
            # التحقق من عدم وجود رمز حديث (منع إعادة الإرسال المتكرر)
            recent_otp = OTPVerification.objects.filter(
                phone=phone,
                purpose=purpose,
                is_verified=False,
                created_at__gte=timezone.now() - timedelta(minutes=1)
            ).first()
            
            if recent_otp:
                return JsonResponse({
                    'success': False,
                    'error': 'يمكنك طلب رمز جديد بعد دقيقة واحدة'
                })
            
            # توليد رمز جديد
            otp = OTPVerification.generate_otp(phone, purpose)
            
            logger.info(f"Resent OTP Code for {phone}: {otp.code}")
            
            return JsonResponse({
                'success': True,
                'message': 'تم إرسال رمز التحقق الجديد بنجاح'
            })
            
        except Exception as e:
            logger.error(f"Error resending OTP: {str(e)}")
            return JsonResponse({'success': False, 'error': 'حدث خطأ أثناء إعادة الإرسال'})
    
    return JsonResponse({'success': False, 'error': 'طريقة الطلب غير صحيحة'})
