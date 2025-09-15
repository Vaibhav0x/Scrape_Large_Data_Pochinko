# Pachinko Scraper - Complete Documentation

A comprehensive Django-based web scraping system for collecting daily pachinko/slot machine data from min-repo.com. This system provides distributed scraping, data management, and a user-friendly interface for analyzing scraped data.

## 📋 Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [Web Interface](#web-interface)
- [Management Commands](#management-commands)
- [Database Schema](#database-schema)
- [Development](#development)
- [Troubleshooting](#troubleshooting)


## 🚀 Features

- **High-volume data collection**: Scrape 400,000+ records per day from 2,000+ stores
- **Distributed processing**: Celery-based parallel scraping with Redis
- **Error handling**: Comprehensive retry logic and error tracking
- **Proxy support**: IP rotation to avoid access restrictions
- **Data visualization**: Interactive dashboard with charts and statistics
- **Advanced filtering**: Search and filter scraped data by multiple criteria
- **Admin interface**: Django admin for database management
- **REST API**: JSON endpoints for custom integrations
- **Responsive design**: Mobile-friendly web interface


## 📦 Installation

### Prerequisites

- Python 3.9+
- Redis (for Celery)
- Django 4.2+
- SQLite (development) / MySQL (production)


### Quick Setup

1. **Clone and setup project:**
```bash
mkdir pachinko_scraper
cd pachinko_scraper
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install django celery redis requests beautifulsoup4 lxml python-decouple django-extensions
```

2. **Create Django project:**
```bash
django-admin startproject pachinko_project .
cd pachinko_project
python manage.py startapp scraper
```

3. **Apply database migrations:**
```bash
python manage.py makemigrations scraper
python manage.py migrate
python manage.py setup_stores  # Initialize store data
python manage.py createsuperuser  # Create admin user
```

4. **Start services (for full functionality):**
```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Celery worker
celery -A pachinko_project worker --loglevel=info

# Terminal 3: Start Django server
python manage.py runserver
```


## ⚙️ Configuration

### Settings Configuration

```python
# pachinko_project/settings.py

# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_TIMEZONE = 'Asia/Tokyo'

# Database (MySQL for production)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'pachinko_db',
        'USER': 'your_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```


## 🖥️ Web Interface

### Main Dashboard

**URL**: `http://localhost:8000/scraper/`

**Features**:

- Real-time statistics (total stores, records, success rates)
- Recent scraping sessions overview
- Quick action buttons
- Interactive charts showing daily collection trends
- System health indicators


### Data Explorer

**URL**: `http://localhost:8000/scraper/data/`

**Features**:

- Advanced filtering by date range, store, machine name
- Paginated data table (50 records per page)
- Statistics summary (total records, average payout rates)
- Export functionality
- Color-coded indicators for performance metrics

**Filters Available**:

- **Date From/To**: Filter records by date range
- **Store**: Select specific store or view all
- **Machine Name**: Text search for machine names
- **Pagination**: Navigate through large datasets


### Scraping Sessions

**URL**: `http://localhost:8000/scraper/sessions/`

**Features**:

- List all scraping sessions with status indicators
- Progress tracking and completion statistics
- Error logs and retry information
- Session filtering by status
- Detailed session analysis


### Session Details

**URL**: `http://localhost:8000/scraper/session/<session_id>/`

**Features**:

- Complete session information
- Error logs and troubleshooting data
- Records collected in the session
- Performance metrics and statistics
- Store-by-store breakdown


### Store Details

**URL**: `http://localhost:8000/scraper/store/<store_id>/`

**Features**:

- Individual store performance analysis
- Historical data trends
- Machine-level statistics
- Recent scraping history
- Store-specific metrics


### Start Scraping Interface

**URL**: `http://localhost:8000/scraper/start-scraping/`

**Features**:

- Manual scraping initiation
- Date selection for target scraping
- Store selection (individual or all stores)
- Real-time task status updates


## 🔗 API Endpoints

### REST API Endpoints

#### 1. Data API

```
GET /scraper/api/data/
```

**Response**: JSON with daily record counts and store performance

```json
{
  "daily_counts": [
    {"day": "2025-09-01", "count": 15234},
    {"day": "2025-09-02", "count": 16789}
  ],
  "store_performance": [
    {
      "store_id": 2564229,
      "name": "Store Sample 1",
      "record_count": 1250,
      "avg_payout": 95.67
    }
  ]
}
```


#### 2. Dashboard Data

```
GET /scraper/
```

**Returns**: HTML dashboard with embedded statistics

#### 3. Data Explorer API

```
GET /scraper/data/?date_from=2025-09-01&store_id=2564229
```

**Parameters**:

- `date_from`: Start date (YYYY-MM-DD)
- `date_to`: End date (YYYY-MM-DD)
- `store_id`: Specific store ID
- `machine_name`: Machine name search
- `page`: Pagination page number


#### 4. Session Management

```
GET /scraper/sessions/
GET /scraper/session/<int:session_id>/
```


## 💼 Management Commands

### Daily Scraping Commands

#### 1. Run Daily Scraping

```bash
# Scrape all stores for today
python manage.py scrape_daily

# Scrape specific stores
python manage.py scrape_daily --stores 2564229 2583253
# failed stores runs automatically using cron job.
# Scrape for specific date
python manage.py scrape_daily --date 2025-09-01


# Run synchronously (without Celery) for testing
python manage.py scrape_daily --sync

python manage.py scrape_daily --sync --date 2025-09-10
```

Retry onto the Failed command if any store failed.
```bash

python manage.py retry_failed_scrapes --sync 

#on specific store Id's

#Retry for specific store
python manage.py retry_failed_scrapes --date 2025-09-10 --sync

# Retry for the specific session
python manage.py retry_failed_scrapes --session 12 --sync

```
DELETE FROM table_name


#### 2. Setup Initial Data

```bash
# Create initial store records
python manage.py setup_stores

# Debug HTML structure for a store
python manage.py debug_html 2564229
```


#### 3. Data Recovery

```bash
# Recover missing data for date range
python manage.py recover_missing_data --start-date 2025-08-01 --end-date 2025-08-31
```


## 🗄️ Database Schema

### Core Models

#### DailySlotData

```python
- id: BigAutoField (Primary Key)
- unique_id: CharField (Site-provided unique identifier)
- date: DateField (Scraping date)
- store: ForeignKey to Store
- machine_number: IntegerField
- machine_name: CharField
- credit_difference: IntegerField
- game_count: IntegerField
- payout_rate: DecimalField (calculated)
- bb: IntegerField (Big Bonus count)
- rb: IntegerField (Regular Bonus count)
- data_url: TextField (Source URL)
- raw_data: JSONField (Original scraped data)
- created_at: DateTimeField
```


#### Store

```python
- store_id: IntegerField (Unique)
- name: CharField
- prefecture: CharField
- is_active: BooleanField
- last_successful_scrape: DateTimeField
- consecutive_failures: IntegerField
```


#### ScrapingSession

```python
- date: DateField
- start_time: DateTimeField
- end_time: DateTimeField
- status: CharField (pending/running/completed/failed/partial)
- total_stores: IntegerField
- successful_stores: IntegerField
- failed_stores: IntegerField
- total_records: IntegerField
- error_log: JSONField
```


## 🛠️ Development

### Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Interface │    │   Django Views  │    │   Database      │
│   (Templates)   │◄──►│   (Views.py)    │◄──►│   (Models)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Celery Tasks  │◄──►│ Scraping Engine │◄──►│   Target Sites  │
│   (Distributed) │    │  (BeautifulSoup)│    │  (min-repo.com) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```


### Key Components

1. **Scraping Engine** (`scraper_engine.py`)
    - Multi-strategy HTML parsing
    - Error handling and retries
    - Proxy rotation support
    - Rate limiting and delays
2. **Celery Tasks** (`tasks.py`)
    - Distributed processing
    - Task orchestration
    - Progress monitoring
    - Error recovery
3. **Django Views** (`views.py`)
    - Web interface controllers
    - API endpoints
    - Data filtering and pagination
    - Statistics calculation
4. **Templates**
    - Bootstrap-based responsive design
    - Interactive charts with Chart.js
    - Advanced filtering interfaces
    - Real-time updates

### Adding New Stores

```python
# Add stores via Django admin or programmatically
from scraper.models import Store

Store.objects.create(
    store_id=1234567,
    name="New Store Name",
    prefecture="Tokyo",
    is_active=True
)
```


### Custom Parsing Logic

Extend the scraping engine for different site structures:

```python
# scraper/scraper_engine.py
def _parse_custom_strategy(self, soup, store, target_date, url):
    """Add your custom parsing logic here"""
    # Implementation for new site formats
    pass
```


## 📊 Performance \& Monitoring

### System Requirements

**Development Environment**:

- 4GB RAM minimum
- 600GB storage (for data retention)
- Redis server
- Python 3.9+

**Production Environment**:

- 8GB+ RAM recommended
- High-speed storage (SSD)
- Load balancer for multiple workers
- Database optimization (MySQL with proper indexing)


### Monitoring Endpoints

- **Health Check**: Monitor scraping session success rates
- **Error Tracking**: ScrapingError model logs all failures
- **Performance Metrics**: Built-in statistics in dashboard
- **Resource Usage**: Celery worker monitoring


## 🔧 Troubleshooting

### Common Issues

#### 1. Template Syntax Errors

**Problem**: `Invalid block tag 'endif'`
**Solution**: Ensure all template tags are on single lines

```html
<!-- Wrong -->
{% if condition
%}content{% endif %}

<!-- Correct -->
{% if condition %}content{% endif %}
```


#### 2. URL Not Found (404)

**Problem**: `/scraper/data/` returns 404
**Solution**: Check URL configuration in `urls.py`

```python
# Ensure scraper URLs are included
path('scraper/', include('scraper.urls')),
```


#### 3. No Data Found

**Problem**: Scraping returns no records
**Solution**: Debug HTML structure

```bash
python manage.py debug_html 2564229
```


#### 4. Celery Connection Issues

**Problem**: Tasks not executing
**Solution**: Verify Redis is running and configured

```bash
redis-server
celery -A pachinko_project worker --loglevel=info
```


### Debug Mode

Enable detailed logging:

```python
# settings.py
LOGGING['loggers']['scraper']['level'] = 'DEBUG'
```


### Data Validation

Check scraped data integrity:

```python
from scraper.models import DailySlotData

# Check for missing data
missing_dates = DailySlotData.objects.values('date').distinct()
# Validate data ranges
invalid_payouts = DailySlotData.objects.filter(payout_rate__gt=200)
```


## 📈 Scaling \& Production

### Production Deployment

1. **Use MySQL/PostgreSQL** instead of SQLite
2. **Configure proxy rotation** for large-scale scraping
3. **Set up monitoring** (Grafana/Prometheus)
4. **Implement caching** (Redis for session data)
5. **Use reverse proxy** (Nginx) for static files

### Performance Optimization

- **Database indexing** on frequently queried fields
- **Celery worker scaling** based on load
- **Connection pooling** for database connections
- **Batch processing** for large datasets


## 📝 License \& Support

This scraping system is designed for educational and research purposes. Ensure compliance with website terms of service and applicable laws regarding web scraping.

For support and contributions, refer to the project documentation and issue tracking system.

***

## Quick Start Summary

```bash
# 1. Setup
python -m venv venv && source venv/bin/activate
pip install django celery redis requests beautifulsoup4

# 2. Initialize
python manage.py migrate
python manage.py setup_stores
python manage.py createsuperuser

# 3. Run (Development)
python manage.py scrape_daily --sync  # Test scraping
python manage.py runserver             # Start web interface

# 4. Access
# Dashboard: http://localhost:8000/scraper/
# Data Explorer: http://localhost:8000/scraper/data/
# Admin: http://localhost:8000/admin/
```

**Your pachinko scraping system is now ready for data collection and analysis!**

