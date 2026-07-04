from django.core.management.base import BaseCommand
from properties.models import Property, Message

class Command(BaseCommand):
    help = 'Load sample data for properties'

    def handle(self, *args, **options):
        # Clear existing data
        Property.objects.all().delete()
        Message.objects.all().delete()

        # Create sample properties
        properties_data = [
            {
                'type': 'house',
                'status': 'ready',
                'location': 'المنصور، بغداد',
                'area': 250,
                'price': 350000000,
                'description': 'بيت حديث البناء في المنصور، قرب سوق السيدية، يحتوي على 4 غرف نوم، صالة كبيرة، حديقة أمامية.',
                'phone': '0770 123 4567',
            },
            {
                'type': 'land',
                'status': 'ready',
                'location': 'الكرادة، بغداد',
                'area': 500,
                'price': 200000000,
                'description': 'قطعة أرض استثمارية في الكرادة، قريبة من الشارع الرئيسي، مناسبة للبناء التجاري.',
                'phone': '0770 123 4567',
            },
            {
                'type': 'building',
                'status': 'under-construction',
                'location': 'الجادرية، بغداد',
                'area': 1200,
                'price': 950000000,
                'description': 'بناية سكنية قيد الإنشاء في الجادرية، 6 طوابق، موقع مميز قرب الجامعة.',
                'phone': '0770 123 4567',
            },
            {
                'type': 'house',
                'status': 'ready',
                'location': 'الدورة، بغداد',
                'area': 180,
                'price': 180000000,
                'description': 'بيت عائلي في الدورة، مجدد بالكامل، 3 غرف، مطبخ جديد، موقف سيارة.',
                'phone': '0770 123 4567',
            },
            {
                'type': 'land',
                'status': 'ready',
                'location': 'الأعظمية، بغداد',
                'area': 300,
                'price': 120000000,
                'description': 'قطعة أرض سكنية في الأعظمية، حي هادئ، خدمات متوفرة.',
                'phone': '0770 123 4567',
            },
            {
                'type': 'building',
                'status': 'ready',
                'location': 'الكرخ، بغداد',
                'area': 800,
                'price': 680000000,
                'description': 'بناية تجارية جاهزة في الكرخ، 4 طوابق، مناسبة للمكاتب أو المحلات.',
                'phone': '0770 123 4567',
            }
        ]

        for prop_data in properties_data:
            Property.objects.create(**prop_data)

        # Create sample messages
        messages_data = [
            {
                'name': 'محمد أحمد',
                'message': 'أهلاً، هل يمكنني الحصول على معلومات أكثر عن البيت في المنصور؟',
                'property': Property.objects.get(location='المنصور، بغداد'),
            },
            {
                'name': 'فاطمة علي',
                'message': 'هل الأرض في الكرادة قريبة من المواصلات العامة؟',
                'property': Property.objects.get(location='الكرادة، بغداد'),
            }
        ]

        for msg_data in messages_data:
            Message.objects.create(**msg_data)

        self.stdout.write(self.style.SUCCESS('Sample data loaded successfully!'))
