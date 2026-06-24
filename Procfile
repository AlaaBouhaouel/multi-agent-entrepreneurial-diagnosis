web: python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn LeadIt.wsgi --bind 0.0.0.0:$PORT --timeout 120 --graceful-timeout 30
