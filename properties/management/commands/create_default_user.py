from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from properties.models import Broker


class Command(BaseCommand):
    help = 'Create default superuser if not exists'

    def handle(self, *args, **options):
        username = 'muq'
        password = '12345'
        email = 'muq@muq.com'

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'is_superuser': True,
                'is_staff': True,
                'is_active': True
            }
        )
        
        # Always update password to ensure it's correct
        user.set_password(password)
        user.email = email
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save()
        
        # Ensure broker profile exists
        broker, broker_created = Broker.objects.get_or_create(
            user=user,
            defaults={
                'phone': '07700000000',
                'governorate': 'بغداد',
                'role': 'admin',
                'is_verified': True
            }
        )
        
        # Update broker if it exists
        if not broker_created:
            broker.phone = '07700000000'
            broker.governorate = 'بغداد'
            broker.role = 'admin'
            broker.is_verified = True
            broker.is_active = True
            broker.save()
        
        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'{action} default user: {username}'))
