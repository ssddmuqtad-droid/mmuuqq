#!/usr/bin/env python
"""Railway production entrypoint: migrate, collectstatic, then gunicorn."""
import os
import subprocess
import sys

# Force disable WebSockets to use Gunicorn instead of Daphne
os.environ['USE_WEBSOCKETS'] = 'false'

# Set up Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dalal_project.settings')

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def run(cmd, allow_fail=False):
    """Run command with proper PYTHONPATH."""
    print(f">>> {' '.join(str(c) for c in cmd)}", flush=True)
    env = os.environ.copy()
    env['PYTHONPATH'] = project_root
    try:
        subprocess.run(cmd, check=True, env=env, cwd=project_root)
    except subprocess.CalledProcessError as e:
        if allow_fail:
            print(f"Warning: command failed (non-fatal): {e}. Continuing.", flush=True)
        else:
            raise


def main():
    port = os.getenv('PORT', '8080')
    print(f"=== Dalal Platform Startup (port {port}) ===", flush=True)
    print(f"DEBUG={os.getenv('DEBUG', 'False')}", flush=True)
    print(f"DJANGO_SETTINGS_MODULE={os.getenv('DJANGO_SETTINGS_MODULE')}", flush=True)
    print(f"PYTHONPATH={os.getenv('PYTHONPATH')}", flush=True)

    # Check if properties app is in INSTALLED_APPS
    try:
        import django
        django.setup()
        from django.conf import settings
        print(f"INSTALLED_APPS: {settings.INSTALLED_APPS}", flush=True)
        print(f"Properties in INSTALLED_APPS: {'properties' in settings.INSTALLED_APPS}", flush=True)
        
        # Check if properties.urls can be imported
        try:
            from properties import urls as properties_urls
            print(f"Properties URLs loaded successfully: {len(properties_urls.urlpatterns)} patterns", flush=True)
        except Exception as e:
            print(f"Error loading properties URLs: {e}", flush=True)
    except Exception as e:
        print(f"Error checking INSTALLED_APPS: {e}", flush=True)

    # Run makemigrations first to ensure all migrations are detected
    print("Running makemigrations...", flush=True)
    run([sys.executable, 'manage.py', 'makemigrations', '--noinput'])
    
    print("Running migrate...", flush=True)
    run([sys.executable, 'manage.py', 'migrate', '--noinput'])
    
    # Check if properties migrations were applied
    try:
        from django.core.management import call_command
        from io import StringIO
        output = StringIO()
        call_command('showmigrations', 'properties', verbosity=0, stdout=output)
        print(f"Properties migrations status: {output.getvalue()[:200]}", flush=True)
    except Exception as e:
        print(f"Error checking migrations: {e}", flush=True)
    
    print("Running collectstatic...", flush=True)
    run([sys.executable, 'manage.py', 'collectstatic', '--noinput'])

    workers = os.getenv('GUNICORN_WORKERS', '2')
    log_level = os.getenv('GUNICORN_LOG_LEVEL', 'debug')
    timeout = os.getenv('GUNICORN_TIMEOUT', '120')

    print(f"Starting gunicorn workers={workers}, log_level={log_level}, timeout={timeout}", flush=True)

    os.execvp(
        'gunicorn',
        [
            'gunicorn',
            'dalal_project.wsgi:application',
            '--bind', f'0.0.0.0:{port}',
            '--workers', workers,
            '--timeout', timeout,
            '--log-level', log_level,
            '--access-logfile', '-',
            '--error-logfile', '-',
            '--forwarded-allow-ips', '*',
            '--capture-output',
        ],
    )


if __name__ == '__main__':
    main()
