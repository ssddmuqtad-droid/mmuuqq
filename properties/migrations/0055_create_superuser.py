from django.db import migrations
from django.contrib.auth.models import User


def create_superuser(apps, schema_editor):
    """Create superuser if it doesn't exist"""
    if not User.objects.filter(username='muqtada123').exists():
        User.objects.create_superuser(
            username='muqtada123',
            email='muqtada123@example.com',
            password='12345'
        )


def reverse_create_superuser(apps, schema_editor):
    """Reverse migration - delete the superuser"""
    User.objects.filter(username='muqtada123').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('properties', '0054_conversation_chatsettings_chatmessage_and_more'),
    ]

    operations = [
        migrations.RunPython(create_superuser, reverse_create_superuser),
    ]
