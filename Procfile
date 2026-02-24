web: gunicorn waterworks.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --worker-class gthread --timeout 300 --keep-alive 5 --preload --log-file -
