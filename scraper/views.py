from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse,StreamingHttpResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Avg, Max, Min, Q
from django.core.paginator import Paginator
from datetime import datetime, timedelta,date
from .models import ScrapingSession, Store, DailySlotData, ScrapingError
from .tasks import orchestrate_daily_scraping
import subprocess


def home(request):
    """Render dashboard with today's date pre-filled"""
    return render(request, "scraper/home.html", {"today": date.today().isoformat()})


import sys
import subprocess
from datetime import date
from django.http import StreamingHttpResponse

def run_command(request, command_name):
    """
    Run management command and stream logs to browser
    Example: /scraper/scrape-daily/?date=2025-09-10
    """
    target_date = request.GET.get("date", date.today().isoformat())
    python_exe = sys.executable  # this points to your venv's Python

    # Choose command
    if command_name == "scrape-daily":
        cmd = [python_exe, "manage.py", "scrape_daily", "--sync", "--date", target_date]
    elif command_name == "retry-failed":
        cmd = [python_exe, "manage.py", "retry_failed", "--sync", "--date", target_date]
    else:
        return StreamingHttpResponse(f"Unknown command: {command_name}")

    # Generator for streaming output
    def stream():
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        for line in process.stdout:
            yield line
        process.wait()

    return StreamingHttpResponse(stream(), content_type="text/plain")

def dashboard(request):
    """Enhanced dashboard with statistics"""
    # Basic stats
    total_stores = Store.objects.filter(is_active=True).count()
    total_records = DailySlotData.objects.count()
    recent_sessions = ScrapingSession.objects.all()[:5]
    
    # Recent data stats
    last_week = timezone.now().date() - timedelta(days=7)
    recent_records = DailySlotData.objects.filter(date__gte=last_week).count()
    
    # Success rate
    completed_sessions = ScrapingSession.objects.filter(status='completed').count()
    total_sessions = ScrapingSession.objects.count()
    success_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
    
    # Average records per session
    avg_records = ScrapingSession.objects.aggregate(avg_records=Avg('total_records'))['avg_records'] or 0
    
    # Error count
    unresolved_errors = ScrapingError.objects.filter(resolved=False).count()
    
    context = {
        'total_stores': total_stores,
        'total_records': total_records,
        'recent_records': recent_records, 
        'recent_sessions': recent_sessions,
        'success_rate': round(success_rate, 1),
        'avg_records': round(avg_records, 0),
        'unresolved_errors': unresolved_errors,
    }
    return render(request, 'scraper/dashboard.html', context)

def data_explorer(request):
    """Data exploration interface"""
    print("DEBUG: data_explorer view called")  # Add this line
    
    # Get filter parameters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    store_id = request.GET.get('store_id')
    machine_name = request.GET.get('machine_name')
    
    print(f"DEBUG: Filters - date_from: {date_from}, date_to: {date_to}, store_id: {store_id}")  # Add this
    
    # Base queryset
    queryset = DailySlotData.objects.select_related('store', 'scraping_session')
    print(f"DEBUG: Base queryset count: {queryset.count()}")  # Add this
    
    # Apply filters
    if date_from:
        queryset = queryset.filter(date__gte=date_from)
    if date_to:
        queryset = queryset.filter(date__lte=date_to)
    if store_id:
        queryset = queryset.filter(store__store_id=store_id)
    if machine_name:
        queryset = queryset.filter(machine_name__icontains=machine_name)
    
    # Order by most recent
    queryset = queryset.order_by('-date', '-created_at')
    
    # Pagination
    paginator = Paginator(queryset, 50)  # 50 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get available stores for filter dropdown
    stores = Store.objects.filter(is_active=True).order_by('store_id')
    print(f"DEBUG: Available stores count: {stores.count()}")  # Add this
    
    # Statistics for current filter
    stats = queryset.aggregate(
        total_records=Count('id'),
        avg_payout=Avg('payout_rate'),
        max_credits=Max('credit_difference'),
        min_credits=Min('credit_difference'),
        total_games=Count('game_count')
    )
    print(f"DEBUG: Stats: {stats}")  # Add this
    
    context = {
        'page_obj': page_obj,
        'stores': stores,
        'stats': stats,
        'filters': {
            'date_from': date_from,
            'date_to': date_to,
            'store_id': store_id,
            'machine_name': machine_name,
        }
    }
    
    print("DEBUG: About to render template")  # Add this
    return render(request, 'scraper/data_explorer.html', context)

def store_detail(request, store_id):
    """Detailed view of a specific store"""
    store = get_object_or_404(Store, store_id=store_id)
    
    # Get recent data for this store
    recent_data = DailySlotData.objects.filter(store=store).order_by('-date')[:100]
    
    # Get statistics
    stats = DailySlotData.objects.filter(store=store).aggregate(
        total_records=Count('id'),
        avg_payout=Avg('payout_rate'),
        avg_games=Avg('game_count'),
        total_bb=Count('bb'),
        total_rb=Count('rb')
    )
    
    # Get recent sessions for this store
    recent_sessions = ScrapingSession.objects.filter(
        dailyslotdata__store=store
    ).distinct().order_by('-date')[:10]
    
    context = {
        'store': store,
        'recent_data': recent_data,
        'stats': stats,
        'recent_sessions': recent_sessions,
    }
    return render(request, 'scraper/store_detail.html', context)

def scraping_sessions(request):
    """Enhanced scraping sessions view"""
    sessions = ScrapingSession.objects.all().order_by('-date', '-start_time')
    
    # Filter by status if requested
    status_filter = request.GET.get('status')
    if status_filter:
        sessions = sessions.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(sessions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
    }
    return render(request, 'scraper/sessions.html', context)

def session_detail(request, session_id):
    """Enhanced session detail view"""
    session = get_object_or_404(ScrapingSession, id=session_id)
    
    # Get errors for this session
    errors = ScrapingError.objects.filter(session=session).order_by('-timestamp')
    
    # Get records for this session
    records = DailySlotData.objects.filter(scraping_session=session).select_related('store')
    
    # Pagination for records
    paginator = Paginator(records, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    stats = records.aggregate(
        total_records=Count('id'),
        unique_stores=Count('store', distinct=True),
        avg_payout=Avg('payout_rate'),
        total_games=Count('game_count')
    )
    
    context = {
        'session': session,
        'errors': errors,
        'page_obj': page_obj,
        'stats': stats,
    }
    return render(request, 'scraper/session_detail.html', context)

def api_data(request):
    """API endpoint for JavaScript charts"""
    # Daily record counts for the last 30 days
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    
    daily_counts = DailySlotData.objects.filter(
        date__gte=thirty_days_ago
    ).extra(
        select={'day': 'DATE(date)'}
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    # Store performance
    store_performance = Store.objects.annotate(
        record_count=Count('dailyslotdata'),
        avg_payout=Avg('dailyslotdata__payout_rate')
    ).filter(record_count__gt=0)[:10]
    
    data = {
        'daily_counts': list(daily_counts),
        'store_performance': [
            {
                'store_id': store.store_id,
                'name': store.name or f'Store {store.store_id}',
                'record_count': store.record_count,
                'avg_payout': float(store.avg_payout) if store.avg_payout else 0
            }
            for store in store_performance
        ]
    }
    
    return JsonResponse(data)

def start_scraping(request):
    """Enhanced start scraping interface"""
    if request.method == 'POST':
        target_date = request.POST.get('date', timezone.now().strftime('%Y-%m-%d'))
        selected_stores = request.POST.getlist('stores')
        
        # Convert store IDs to integers
        if selected_stores:
            try:
                store_ids = [int(store_id) for store_id in selected_stores]
            except ValueError:
                messages.error(request, 'Invalid store IDs provided')
                return render(request, 'scraper/start_scraping.html')
        else:
            store_ids = None
        
        # Start the task
        result = orchestrate_daily_scraping.delay(target_date, store_ids)
        
        messages.success(request, f'Scraping task started with ID: {result.id}')
        return render(request, 'scraper/start_scraping.html', {'task_id': result.id})
    
    # GET request - show form
    stores = Store.objects.filter(is_active=True).order_by('store_id')
    context = {
        'stores': stores,
        'default_date': timezone.now().strftime('%Y-%m-%d'),
    }
    return render(request, 'scraper/start_scraping.html', context)
