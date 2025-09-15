from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
from scraper.models import ScrapingError, ScrapingSession
from scraper.scraper_engine import PachinkoScraper


class Command(BaseCommand):
    help = "Retry scraping for stores that failed previously"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            help="Target date (YYYY-MM-DD). Defaults to today.",
        )
        parser.add_argument(
            "--session",
            type=int,
            help="Specific session ID to retry. If not provided, will use latest session.",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run synchronously (without Celery).",
        )

    def handle(self, *args, **options):
        target_date = options.get("date")
        session_id = options.get("session")
        sync_mode = options.get("sync", False)

        # --- Pick date ---
        if target_date:
            try:
                target_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                self.stdout.write(self.style.ERROR("Invalid date format. Use YYYY-MM-DD"))
                return
        else:
            target_date = timezone.now().date()

        # --- Pick session ---
        if session_id:
            try:
                session = ScrapingSession.objects.get(id=session_id)
            except ScrapingSession.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"No session found with ID {session_id}"))
                return
        else:
            session = ScrapingSession.objects.filter(date=target_date).order_by("-start_time").first()
            if not session:
                self.stdout.write(self.style.ERROR(f"No scraping session found for {target_date}"))
                return

        # --- Collect failed store IDs ---
        failed_stores = ScrapingError.objects.filter(session=session).values_list("store_id", flat=True).distinct()
        if not failed_stores:
            self.stdout.write(self.style.WARNING("No failed stores to retry."))
            return

        self.stdout.write(f"Retrying {len(failed_stores)} failed stores for session {session.id} ({target_date})")

        if sync_mode:
            scraper = PachinkoScraper()
            successful = 0
            failed = 0
            retried_records = 0

            for store_id in failed_stores:
                self.stdout.write(f"Retrying store {store_id}...")
                result = scraper.scrape_store_data(store_id, target_date, session)

                if result["success"]:
                    successful += 1
                    retried_records += result["records_created"]
                    self.stdout.write(self.style.SUCCESS(f"Store {store_id}: {result['records_created']} records"))
                else:
                    failed += 1
                    self.stdout.write(self.style.ERROR(f"Store {store_id}: {result['errors']}"))

            session.successful_stores += successful
            session.failed_stores = failed  # reset to current failures
            session.total_records += retried_records
            session.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Retry completed: {successful} successful, {failed} failed, {retried_records} new records"
                )
            )
        else:
            # Celery version (queue retry tasks)
            from scraper.tasks import orchestrate_daily_scraping

            task = orchestrate_daily_scraping.delay(str(target_date), list(failed_stores))
            self.stdout.write(self.style.SUCCESS(f"Retry task queued with ID: {task.id}"))
