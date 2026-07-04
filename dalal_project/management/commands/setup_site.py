"""
setup_site management command.
Runs automatically on every Railway startup (called from run_server.py).
- Creates admin user muqtada123 / 12345 if not exists
- Creates default SiteSettings if not exists
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Initialize site: create admin user and default settings'

    def handle(self, *args, **options):
        self._create_admin_user()
        self._create_site_settings()

    # ------------------------------------------------------------------
    def _create_admin_user(self):
        username = 'muqtada123'
        password = '12345'
        email = 'muqtada@daluailiraq.com'

        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
            # Make sure the user is still a superuser / staff
            if not user.is_superuser or not user.is_staff:
                user.is_superuser = True
                user.is_staff = True
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.WARNING(
                    f'[setup_site] User "{username}" updated to superuser.'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'[setup_site] User "{username}" already exists — skipping.'
                ))
        else:
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
            )
            self.stdout.write(self.style.SUCCESS(
                f'[setup_site] Superuser "{username}" created successfully.'
            ))

    # ------------------------------------------------------------------
    def _create_site_settings(self):
        try:
            from properties.models import SiteSettings
            if not SiteSettings.objects.exists():
                SiteSettings.objects.create(
                    site_name='دلال',
                    tagline='منصة العقارات العراقية',
                )
                self.stdout.write(self.style.SUCCESS(
                    '[setup_site] Default SiteSettings created.'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    '[setup_site] SiteSettings already exists — skipping.'
                ))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(
                f'[setup_site] Could not create SiteSettings: {exc}'
            ))
