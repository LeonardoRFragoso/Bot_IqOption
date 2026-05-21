#!/bin/sh
set -e

# Get PORT from environment, default to 8000
PORT="${PORT:-8000}"

echo "=== Railway Startup ==="
echo "PORT environment variable: $PORT"

# Run migrations
echo "Running migrations..."
python manage.py migrate

# Start Daphne
echo "Starting Daphne on port $PORT..."
exec daphne -b 0.0.0.0 -p "$PORT" bot_iqoption.asgi:application
