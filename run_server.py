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

    run([sys.executable, 'manage.py', 'migrate', '--noinput'])
    run([sys.executable, 'manage.py', 'collectstatic', '--noinput'])
    run([sys.executable, 'manage.py', 'setup_site'], allow_fail=True)

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
