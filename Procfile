web: python config/manage.py migrate && gunicorn config.config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
