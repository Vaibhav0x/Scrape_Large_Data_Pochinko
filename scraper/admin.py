from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import DailySlotData, ScrapingSession, Store, ScrapingError
import json

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ['store_id', 'name', 'prefecture', 'is_active', 'last_successful_scrape', 'consecutive_failures']
    list_filter = ['is_active', 'prefecture', 'consecutive_failures']
    search_fields = ['store_id', 'name', 'prefecture']
    readonly_fields = ['last_successful_scrape', 'consecutive_failures']
    
    def get_queryset(self, request):
        return super().get_queryset(request)

@admin.register(ScrapingSession)
class ScrapingSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'date', 'status', 'progress_bar', 'total_records', 'duration']
    list_filter = ['status', 'date']
    readonly_fields = ['start_time', 'end_time', 'error_log_display']
    
    def progress_bar(self, obj):
        if obj.total_stores == 0:
            return "0%"
        percentage = (obj.successful_stores / obj.total_stores) * 100
        color = 'green' if percentage == 100 else 'orange' if percentage > 50 else 'red'
        return format_html(
            '<div style="width: 100px; background-color: #ddd;">'
            '<div style="width: {}%; background-color: {}; height: 20px; text-align: center; color: white;">{:.1f}%</div>'
            '</div>',
            percentage, color, percentage
        )
    progress_bar.short_description = 'Progress'
    
    def duration(self, obj):
        if obj.end_time and obj.start_time:
            duration = obj.end_time - obj.start_time
            return f"{duration.total_seconds():.0f} seconds"
        return "Running..." if obj.status == 'running' else "N/A"
    
    def error_log_display(self, obj):
        if obj.error_log:
            return format_html('<pre>{}</pre>', json.dumps(obj.error_log, indent=2))
        return "No errors"
    error_log_display.short_description = 'Error Log'

@admin.register(DailySlotData)
class DailySlotDataAdmin(admin.ModelAdmin):
    # Only use fields that exist in your model
    list_display = [
        'id', 'date', 'store_id', 'machine_number', 'credit_difference', 
        'game_count', 'payout_rate', 'bb', 'rb'
    ]
    # Use direct fields only, not relationships
    list_filter = ['date', 'store_id']
    # Search only on existing fields
    search_fields = ['store_id', 'machine_number']
    # Only include actual model fields
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'date'
    list_per_page = 50
    
    # Optional: Add a method to display store information
    def store_info(self, obj):
        try:
            store = Store.objects.get(store_id=obj.store_id)
            return f"{store.name} ({obj.store_id})"
        except Store.DoesNotExist:
            return f"Store {obj.store_id}"
    store_info.short_description = 'Store Info'
    
    # Optional: Add machine name method if needed
    def machine_name_display(self, obj):
        # You can add logic here to display machine names
        # based on machine_id or other fields
        return f"Machine {obj.machine_number}" if obj.machine_number else "Unknown"
    machine_name_display.short_description = 'Machine Name'

@admin.register(ScrapingError)
class ScrapingErrorAdmin(admin.ModelAdmin):
    list_display = ['session', 'store_id', 'error_type', 'timestamp', 'retry_count', 'resolved']
    list_filter = ['error_type', 'resolved', 'timestamp']
    search_fields = ['store_id', 'error_message']
    readonly_fields = ['timestamp']
