FROM python:3.13-slim

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

# Run migrations and start the server
CMD ["sh", "-c", "python manage.py migrate && daphne -b 0.0.0.0 -p ${PORT:-8000} bot_iqoption.asgi:application"]
