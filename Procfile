web: sh -c 'python manage.py migrate --noinput && gunicorn dalal_project.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile - --error-logfile - --forwarded-allow-ips *'
