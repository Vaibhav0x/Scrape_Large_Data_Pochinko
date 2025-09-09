from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
from scraper.tasks import orchestrate_daily_scraping

class Command(BaseCommand):
    help = 'Run daily scraping process'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--date', 
            type=str, 
            help='Target date (YYYY-MM-DD). Defaults to today.'
        )
        parser.add_argument(
            '--stores',
            nargs='+',
            type=int,
            help='Specific store IDs to scrape'
        )
        parser.add_argument(
            '--sync',
            action='store_true',
            help='Run synchronously (without Celery)'
        )
    
    def handle(self, *args, **options):
        target_date = options.get('date')
        store_ids = options.get('stores')
        sync_mode = options.get('sync', False)
        
        if target_date:
            try:
                datetime.strptime(target_date, '%Y-%m-%d')
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('Invalid date format. Use YYYY-MM-DD')
                )
                return
        else:
            target_date = timezone.now().strftime('%Y-%m-%d')
        
        self.stdout.write(f'Starting scraping for {target_date}')
        if store_ids:
            self.stdout.write(f'Targeting stores: {store_ids}')
        
        if sync_mode:
            # Run synchronously for development/testing
            from scraper.scraper_engine import PachinkoScraper
            from scraper.models import ScrapingSession, Store
            
            if not store_ids:
                store_ids = [2564229, 2583253, 2582885, 2582867, 2583824, 2583250]
            
            session = ScrapingSession.objects.create(
                date=datetime.strptime(target_date, '%Y-%m-%d').date(),
                status='running',
                total_stores=len(store_ids)
            )
            
            scraper = PachinkoScraper()
            successful = 0
            failed = 0
            total_records = 0
            
            for store_id in store_ids:
                self.stdout.write(f'Scraping store {store_id}...')
                result = scraper.scrape_store_data(
                    store_id, 
                    datetime.strptime(target_date, '%Y-%m-%d').date(),
                    session
                )
                
                if result['success']:
                    successful += 1
                    total_records += result['records_created']
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Store {store_id}: {result["records_created"]} records')
                    )
                else:
                    failed += 1
                    self.stdout.write(
                        self.style.ERROR(f'✗ Store {store_id}: {result["errors"]}')
                    )
            
            session.successful_stores = successful
            session.failed_stores = failed
            session.total_records = total_records
            session.status = 'completed' if failed == 0 else 'partial'
            session.end_time = timezone.now()
            session.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Scraping completed: {successful} successful, {failed} failed, {total_records} total records'
                )
            )
        else:
            # Run with Celery
            result = orchestrate_daily_scraping.delay(target_date, store_ids)
            self.stdout.write(
                self.style.SUCCESS(f'Scraping task queued with ID: {result.id}')
            )
