#!/usr/bin/env python3
"""
Setup script for Pachinko Scraper development environment
"""
import os
import subprocess
import sys

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"\n🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"Error: {e.stderr}")
        return None

def main():
    print("🚀 Setting up Pachinko Scraper development environment...")
    
    # Create and activate virtual environment
    if not os.path.exists('venv'):
        run_command('python -m venv venv', 'Creating virtual environment')
    
    # Install requirements
    requirements = [
        'django>=4.2',
        'celery>=5.2',
        'redis>=4.0',
        'requests>=2.28',
        'beautifulsoup4>=4.11',
        'lxml>=4.9',
        'python-decouple>=3.6',
        'django-extensions>=3.2',
    ]
    
    pip_install = f"pip install {' '.join(requirements)}"
    run_command(pip_install, 'Installing Python packages')
    
    # Django setup
    run_command('python manage.py makemigrations', 'Creating migrations')
    run_command('python manage.py migrate', 'Running migrations')
    run_command('python manage.py setup_stores', 'Setting up initial stores')
    
    print("\n🎉 Setup completed!")
    print("\nNext steps:")
    print("1. Install and start Redis: redis-server")
    print("2. Start Celery worker: celery -A pachinko_project worker --loglevel=info")
    print("3. Start Django server: python manage.py runserver")
    print("4. Test scraping: python manage.py scrape_daily --sync")

if __name__ == '__main__':
    main()
