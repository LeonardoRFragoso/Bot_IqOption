FROM python:3.13-slim

# Force rebuild - v2
WORKDIR /app

# Install system dependencies - including libpq-dev for psycopg2
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip, setuptools and wheel FIRST - this is critical
RUN pip install --upgrade --force-reinstall pip setuptools wheel

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Collect static files (ignore errors)
RUN python manage.py collectstatic --noinput 2>/dev/null || true

# Create startup script inline
RUN echo '#!/bin/sh\n\
PORT="${PORT:-8000}"\n\
echo "Starting with PORT=$PORT"\n\
python manage.py migrate\n\
exec daphne -b 0.0.0.0 -p "$PORT" bot_iqoption.asgi:application' > /app/start.sh && chmod +x /app/start.sh

# Run the startup script
CMD ["/bin/sh", "/app/start.sh"]
