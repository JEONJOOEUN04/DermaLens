FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app/config

CMD gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
