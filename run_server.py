#!/usr/bin/env python
"""Railway production entrypoint: migrate, collectstatic, then gunicorn."""
import os
import subprocess
import sys

# Force disable WebSockets to use Gunicorn instead of Daphne
os.environ['USE_WEBSOCKETS'] = 'false'
# Force rebuild - 2026-07-13-12-42

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
    print(f"=== NEW CODE VERSION - 2026-07-13-12-42 ===", flush=True)
    print(f"DEBUG={os.getenv('DEBUG', 'False')}", flush=True)
    print(f"DJANGO_SETTINGS_MODULE={os.getenv('DJANGO_SETTINGS_MODULE')}", flush=True)
    print(f"PYTHONPATH={os.getenv('PYTHONPATH')}", flush=True)
    
    # Check which settings file is being used
    import django.conf
    print(f"Django settings module: {django.conf.settings.SETTINGS_MODULE}", flush=True)
    
    # Check if settings.py file contains properties app
    settings_file = os.path.join(project_root, 'dalal_project', 'settings.py')
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as f:
            settings_content = f.read()
            print(f"Settings.py exists: True", flush=True)
            print(f"Settings.py contains 'properties': {'properties' in settings_content}", flush=True)
            print(f"Settings.py contains 'INSTALLED_APPS': {'INSTALLED_APPS' in settings_content}", flush=True)
    else:
        print(f"Settings.py exists: False", flush=True)

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
        
        # Check if home view can be imported
        try:
            from properties.views import home
            print(f"Home view imported successfully", flush=True)
        except Exception as e:
            print(f"Error importing home view: {e}", flush=True)
    except Exception as e:
        print(f"Error checking INSTALLED_APPS: {e}", flush=True)

    # Delete old database to fix migration issues
    db_path = os.path.join(project_root, 'db.sqlite3')
    if os.path.exists(db_path):
        print(f"Deleting old database at {db_path}...", flush=True)
        os.remove(db_path)
    
    # Run makemigrations first to ensure all migrations are detected
    print("Running makemigrations...", flush=True)
    run([sys.executable, 'manage.py', 'makemigrations', '--noinput'])
    
    print("Running migrate...", flush=True)
    run([sys.executable, 'manage.py', 'migrate', '--noinput'], allow_fail=True)
    
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
    
    # Check if static files were collected
    static_root = os.path.join(project_root, 'staticfiles')
    if os.path.exists(static_root):
        print(f"Static files collected to {static_root}: {len(os.listdir(static_root))} items", flush=True)
    else:
        print(f"WARNING: staticfiles directory not found at {static_root}", flush=True)

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
