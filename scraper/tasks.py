from celery import Celery, group
from django.utils import timezone
from django.db import transaction
import logging
import time
from .models import ScrapingSession, Store, DailySlotData, ScrapingError
from .scraper_engine import PachinkoScraper

logger = logging.getLogger('scraper')
app = Celery('pachinko_project')

@app.task(bind=True, max_retries=2)
def scrape_single_store(self, store_id: int, target_date_str: str, session_id: int):
    """Scrape data for a single store"""
    try:
        target_date = timezone.datetime.strptime(target_date_str, '%Y-%m-%d').date()
        session = ScrapingSession.objects.get(id=session_id)
        
        scraper = PachinkoScraper()
        result = scraper.scrape_store_data(store_id, target_date, session)
        
        # Update session statistics
        with transaction.atomic():
            session.refresh_from_db()
            if result['success']:
                session.successful_stores += 1
                session.total_records += result['records_created']
            else:
                session.failed_stores += 1
                session.error_log[str(store_id)] = result['errors']
            session.save()
        
        return result
        
    except Exception as exc:
        logger.error(f"Task failed for store {store_id}: {str(exc)}")
        if self.request.retries < self.max_retries:
            # Exponential backoff
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(countdown=countdown, exc=exc)
        
        # Final failure - log it
        try:
            session = ScrapingSession.objects.get(id=session_id)
            session.failed_stores += 1
            session.error_log[str(store_id)] = [str(exc)]
            session.save()
        except:
            pass
            
        return {'success': False, 'store_id': store_id, 'error': str(exc)}

@app.task
def orchestrate_daily_scraping(target_date_str: str = None, store_ids: list = None):
    """Main task to orchestrate daily scraping"""
    if not target_date_str:
        target_date = timezone.now().date()
        target_date_str = target_date.strftime('%Y-%m-%d')
    else:
        target_date = timezone.datetime.strptime(target_date_str, '%Y-%m-%d').date()
    
    # Get store IDs to scrape
    if not store_ids:
        store_ids = list(Store.objects.filter(is_active=True).values_list('store_id', flat=True))
        if not store_ids:
            # Default store IDs from your examples
            store_ids = [2564229, 2583253, 2582885, 2582867, 2583824, 2583250]
            # Create Store records if they don't exist
            for store_id in store_ids:
                Store.objects.get_or_create(store_id=store_id, defaults={'is_active': True})
    
    # Create scraping session
    session = ScrapingSession.objects.create(
        date=target_date,
        status='running',
        total_stores=len(store_ids)
    )
    
    logger.info(f"Starting scraping session {session.id} for {target_date} with {len(store_ids)} stores")
    
    try:
        # Create group of tasks for parallel execution
        job = group(
            scrape_single_store.s(store_id, target_date_str, session.id) 
            for store_id in store_ids
        )
        
        # Execute tasks
        result = job.apply_async()
        
        # Wait for completion (with timeout)
        results = result.get(timeout=3600)  # 1 hour timeout
        
        # Update final session status
        session.refresh_from_db()
        session.end_time = timezone.now()
        
        if session.failed_stores == 0:
            session.status = 'completed'
        elif session.successful_stores > 0:
            session.status = 'partial'
        else:
            session.status = 'failed'
            
        session.save()
        
        logger.info(f"Scraping session {session.id} completed: {session.successful_stores} successful, {session.failed_stores} failed")
        
        return {
            'session_id': session.id,
            'status': session.status,
            'successful_stores': session.successful_stores,
            'failed_stores': session.failed_stores,
            'total_records': session.total_records
        }
        
    except Exception as e:
        logger.error(f"Scraping orchestration failed: {str(e)}")
        session.status = 'failed'
        session.end_time = timezone.now()
        session.error_log['orchestration_error'] = str(e)
        session.save()
        raise
