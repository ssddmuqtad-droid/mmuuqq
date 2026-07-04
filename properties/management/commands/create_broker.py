from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from properties.models import Broker


class Command(BaseCommand):
    help = 'Create a broker account'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True, help='Username')
        parser.add_argument('--password', type=str, required=True, help='Password')
        parser.add_argument('--phone', type=str, default='07123456789', help='Phone number')
        parser.add_argument('--governorate', type=str, default='بغداد', help='Governorate')
        parser.add_argument('--office_name', type=str, default='مكتب افتراضي', help='Office name')
        parser.add_argument('--role', type=str, default='main', choices=['main', 'sub', 'admin'], help='Role')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        phone = options['phone']
        governorate = options['governorate']
        office_name = options['office_name']
        role = options['role']

        # Check if user already exists
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
            user.set_password(password)
            user.is_staff = True
            user.save()
            self.stdout.write(self.style.WARNING(f'Updated existing user: {username}'))
        else:
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=username,
                is_staff=True,
            )
            self.stdout.write(self.style.SUCCESS(f'Created new user: {username}'))

        # Create or update broker
        broker, created = Broker.objects.get_or_create(
            user=user,
            defaults={
                'phone': phone,
                'governorate': governorate,
                'office_name': office_name,
                'role': role,
                'is_active': True,
            }
        )

        if not created:
            broker.phone = phone
            broker.governorate = governorate
            broker.office_name = office_name
            broker.role = role
            broker.is_active = True
            broker.save()
            self.stdout.write(self.style.WARNING(f'Updated existing broker for: {username}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Created new broker for: {username}'))

        self.stdout.write(self.style.SUCCESS(f'Broker account ready: {username} / {password}'))
