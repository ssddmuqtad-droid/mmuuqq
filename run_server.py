#!/usr/bin/env python
"""Railway production entrypoint: migrate, collectstatic, then gunicorn.

This version reads GUNICORN_WORKERS and GUNICORN_LOG_LEVEL from the environment
so we can lower workers in low-memory environments (default=1).
"""
import os
import subprocess
import sys


def run(cmd):
    print(f">>> {' '.join(cmd)}", flush=True)
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        # If setup_site is missing (custom management command not provided), log and continue.
        if any('setup_site' in str(c) for c in cmd):
            print(f"Warning: command {' '.join(cmd)} failed: {e}. Continuing without setup_site.", flush=True)
        else:
            raise


def main():
    port = os.getenv('PORT', '8080')
    print(f"=== Dalal Platform Startup (port {port}) ===", flush=True)

    run([sys.executable, 'manage.py', 'migrate', '--noinput'])
    # setup_site is optional; if it's not present as a management command, don't fail startup.
    try:
        run([sys.executable, 'manage.py', 'setup_site'])
    except Exception:
        # run() already handles CalledProcessError for setup_site; this is a safety net.
        print('Continuing without running setup_site.', flush=True)
    run([sys.executable, 'manage.py', 'collectstatic', '--noinput'])

    # Read workers and log level from environment so we can tune on the platform
    workers = os.getenv('GUNICORN_WORKERS', '1')
    log_level = os.getenv('GUNICORN_LOG_LEVEL', 'info')
    timeout = os.getenv('GUNICORN_TIMEOUT', '120')

    print(f"Starting gunicorn with workers={workers}, log_level={log_level}, timeout={timeout}", flush=True)

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
        ],
    )


if __name__ == '__main__':
    main()
