#!/usr/bin/env python
"""Railway production entrypoint: migrate, collectstatic, then gunicorn."""
import os
import subprocess
import sys


def run(cmd):
    print(f">>> {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True)


def main():
    port = os.getenv('PORT', '8080')
    print(f"=== Dalal Platform Startup (port {port}) ===", flush=True)

    run([sys.executable, 'manage.py', 'migrate', '--noinput'])
    run([sys.executable, 'manage.py', 'setup_site'])
    run([sys.executable, 'manage.py', 'collectstatic', '--noinput'])

    os.execvp(
        'gunicorn',
        [
            'gunicorn',
            'dalal_project.wsgi:application',
            '--bind', f'0.0.0.0:{port}',
            '--workers', '2',
            '--timeout', '120',
            '--access-logfile', '-',
            '--error-logfile', '-',
        ],
    )


if __name__ == '__main__':
    main()
