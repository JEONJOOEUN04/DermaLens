FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    pkg-config \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app/config

CMD gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
