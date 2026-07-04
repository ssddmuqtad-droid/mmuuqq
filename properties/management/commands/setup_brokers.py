from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from properties.models import Broker, SubscriptionPlan


class Command(BaseCommand):
    help = 'Create broker profiles for existing staff/superuser accounts'

    def handle(self, *args, **options):
        User = get_user_model()
        created = 0
        
        # Get or create a default subscription plan
        default_plan, _ = SubscriptionPlan.objects.get_or_create(
            period='unlimited',
            defaults={
                'name': 'غير محدود',
                'ads_limit': 999999,
                'price': 0,
                'color': '#000000',
                'is_active': True,
            }
        )
        
        for user in User.objects.filter(is_staff=True):
            broker, was_created = Broker.objects.get_or_create(
                user=user,
                defaults={
                    'phone': '07700000000',
                    'role': Broker.ROLE_ADMIN if user.is_superuser else Broker.ROLE_MAIN,
                    'subscription_plan': default_plan,
                    'is_verified': True,
                    'office_name': 'المكتب الرئيسي',
                },
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'Created broker profile for {user.username}'))
            else:
                self.stdout.write(f'Broker profile already exists for {user.username}')
        self.stdout.write(self.style.SUCCESS(f'Done. Created {created} broker profile(s).'))
