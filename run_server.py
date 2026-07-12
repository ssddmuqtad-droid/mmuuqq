#!/usr/bin/env python
"""Railway production entrypoint: migrate, collectstatic, then gunicorn."""
import os
import sys

# Force disable WebSockets to use Gunicorn instead of Daphne
os.environ['USE_WEBSOCKETS'] = 'false'

# Set up Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dalal_project.settings')

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def run_django_command(command_name, *args, allow_fail=False):
    """Run Django management command directly without subprocess."""
    print(f">>> python manage.py {command_name} {' '.join(args)}", flush=True)
    try:
        from django.core.management import call_command
        call_command(command_name, *args)
    except Exception as e:
        if allow_fail:
            print(f"Warning: command failed (non-fatal): {e}. Continuing.", flush=True)
        else:
            raise


def main():
    port = os.getenv('PORT', '8080')
    print(f"=== Dalal Platform Startup (port {port}) ===", flush=True)

    # Run Django management commands directly
    run_django_command('migrate', '--noinput')
    run_django_command('collectstatic', '--noinput')
    run_django_command('setup_site', allow_fail=True)

    workers = os.getenv('GUNICORN_WORKERS', '2')
    log_level = os.getenv('GUNICORN_LOG_LEVEL', 'info')
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
        ],
    )


if __name__ == '__main__':
    main()
