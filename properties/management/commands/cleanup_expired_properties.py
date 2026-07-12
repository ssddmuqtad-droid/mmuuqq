from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from properties.models import Property, Broker


class Command(BaseCommand):
    help = 'Delete expired and frozen properties automatically'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help='Run in dry-run mode without actually deleting',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Delete properties that have been expired for this many days (default: 7)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        days_threshold = options.get('days', 7)
        
        self.stdout.write(f'{"=" * 60}')
        self.stdout.write(f'Cleanup Expired Properties Command')
        self.stdout.write(f'{"=" * 60}')
        self.stdout.write(f'Mode: {"DRY RUN" if dry_run else "LIVE"}')
        self.stdout.write(f'Days threshold: {days_threshold} days')
        self.stdout.write(f'{"=" * 60}')
        
        from django.utils import timezone
        threshold_date = timezone.now() - timedelta(days=days_threshold)
        
        # Find expired properties
        expired_properties = Property.objects.filter(
            expiry_date__lt=threshold_date,
            is_frozen=False
        )
        
        self.stdout.write(f'\nFound {expired_properties.count()} expired properties')
        
        # Freeze expired properties
        frozen_count = 0
        for property in expired_properties:
            try:
                broker = Broker.objects.filter(user=property.owner).first()
                if broker and broker.is_subscription_expired():
                    if not dry_run:
                        property.freeze('انتهاء الاشتراك')
                    frozen_count += 1
                    self.stdout.write(f'  - Frozen: {property.display_title or property.title}')
            except Exception as e:
                self.stdout.write(f'  - Error freezing {property.id}: {str(e)}')
        
        self.stdout.write(f'\nFrozen {frozen_count} properties')
        
        # Find properties that have been frozen for more than threshold days
        properties_to_delete = Property.objects.filter(
            frozen_at__lt=threshold_date,
            is_frozen=True
        )
        
        self.stdout.write(f'\nFound {properties_to_delete.count()} properties to delete (frozen for > {days_threshold} days)')
        
        # Delete properties
        deleted_count = 0
        for property in properties_to_delete:
            if not dry_run:
                property.delete()
            deleted_count += 1
            self.stdout.write(f'  - Deleted: {property.display_title or property.title}')
        
        self.stdout.write(f'\nDeleted {deleted_count} properties')
        
        # Summary
        self.stdout.write(f'\n{"=" * 60}')
        self.stdout.write(f'SUMMARY:')
        self.stdout.write(f'  - Expired properties found: {expired_properties.count()}')
        self.stdout.write(f'  - Properties frozen: {frozen_count}')
        self.stdout.write(f'  - Properties deleted: {deleted_count}')
        self.stdout.write(f'{"=" * 60}')
        
        if dry_run:
            self.stdout.write('\nDRY RUN COMPLETE - No changes were made')
        else:
            self.stdout.write('\nCLEANUP COMPLETE')
