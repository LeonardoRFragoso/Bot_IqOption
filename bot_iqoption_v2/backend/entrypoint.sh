#!/bin/bash
set -e

# Use PORT from environment or default to 8000
PORT=${PORT:-8000}

echo "Starting migrations..."
python manage.py migrate

echo "Starting Daphne on port $PORT..."
exec daphne -b 0.0.0.0 -p $PORT bot_iqoption.asgi:application
