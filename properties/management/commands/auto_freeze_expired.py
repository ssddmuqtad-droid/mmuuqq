from django.core.management.base import BaseCommand
from django.utils import timezone
from properties.models import Property, Broker


class Command(BaseCommand):
    help = 'Automatically freeze properties when broker subscription expires'

    def handle(self, *args, **options):
        self.stdout.write('Auto-freezing expired properties...')
        
        from django.utils import timezone
        
        # Get all brokers with expired subscriptions
        expired_brokers = []
        for broker in Broker.objects.all():
            if broker.is_subscription_expired():
                expired_brokers.append(broker)
        
        self.stdout.write(f'Found {len(expired_brokers)} brokers with expired subscriptions')
        
        # Freeze all properties for expired brokers
        frozen_count = 0
        for broker in expired_brokers:
            properties = Property.objects.filter(
                owner=broker.user,
                is_frozen=False
            )
            
            for property in properties:
                property.freeze('انتهاء الاشتراك')
                frozen_count += 1
                self.stdout.write(f'  - Frozen: {property.display_title or property.title}')
        
        self.stdout.write(f'Total properties frozen: {frozen_count}')
        self.stdout.write('Auto-freeze complete!')
