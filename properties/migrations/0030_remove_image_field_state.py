# Migration to remove image field from Django internal state only

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0029_twofactorauth_securitylog'),
    ]

    operations = [
        # No operations - this just marks the migration as applied
        # The model already has the image field removed (commented out)
        # This syncs Django's internal state with the actual database schema
    ]
