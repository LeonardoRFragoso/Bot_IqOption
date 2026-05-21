#!/usr/bin/env python
"""
Startup script for Railway deployment.
Handles PORT environment variable and starts Daphne.
"""
import os
import subprocess
import sys

def main():
    # Get PORT from environment, default to 8000
    port = os.environ.get('PORT', '8000')
    
    print(f"=== Railway Startup ===")
    print(f"PORT from environment: {port}")
    print(f"All env vars with PORT: {[(k,v) for k,v in os.environ.items() if 'PORT' in k.upper()]}")
    
    # Run migrations
    print("Running migrations...")
    subprocess.run([sys.executable, 'manage.py', 'migrate'], check=True)
    
    # Start Daphne
    print(f"Starting Daphne on port {port}...")
    os.execvp('daphne', ['daphne', '-b', '0.0.0.0', '-p', port, 'bot_iqoption.asgi:application'])

if __name__ == '__main__':
    main()
