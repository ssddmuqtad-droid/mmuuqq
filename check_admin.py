import os
import sys
import django

# Add the project directory to Python path
sys.path.insert(0, r'c:\Users\zbxhh\OneDrive\Desktop\acakar11\acakar')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dalal_project.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
admin_user = User.objects.filter(username='admin').first()

print('Admin user exists:', admin_user is not None)
if admin_user:
    print('Admin user:', admin_user)
    print('Is superuser:', admin_user.is_superuser)
    print('Is active:', admin_user.is_active)
    print('Is staff:', admin_user.is_staff)
    
    # Reset password to admin123
    admin_user.set_password('admin123')
    admin_user.save()
    print('Password reset to admin123 successfully')
else:
    print('Creating admin user...')
    admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Admin user created successfully')
