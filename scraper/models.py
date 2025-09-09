# scraper/models.py
from django.db import models

# Keep your existing models but update DailySlotData
class DailySlotData(models.Model):
    id = models.BigIntegerField(primary_key=True)  # Use site-provided ID
    date = models.DateField()
    pref_id = models.IntegerField(null=True, blank=True)
    store_id = models.IntegerField(null=True, blank=True)  # Back to IntegerField
    machine_id = models.IntegerField(null=True, blank=True)
    machine_number = models.IntegerField(null=True, blank=True)
    credit_difference = models.IntegerField(null=True, blank=True)
    game_count = models.IntegerField(null=True, blank=True)
    payout_rate = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    rate = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    bb = models.IntegerField(null=True, blank=True)
    rb = models.IntegerField(null=True, blank=True)
    synthesis = models.CharField(max_length=64, null=True, blank=True)
    bb_rate = models.CharField(max_length=64, null=True, blank=True)
    rb_rate = models.CharField(max_length=64, null=True, blank=True)
    data_url = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'daily_slot_data'  # Use your existing table
        managed = False  # Don't let Django manage this table
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['store_id']),
        ]

    def __str__(self):
        return f"ID: {self.id}, Store: {self.store_id}, Date: {self.date}"

# For the other models, let Django manage them
class Store(models.Model):
    store_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=255, blank=True)
    prefecture = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    last_successful_scrape = models.DateTimeField(null=True, blank=True)
    consecutive_failures = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'stores'
    
    def __str__(self):
        return f"Store {self.store_id} - {self.name}"

class ScrapingSession(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partial', 'Partial Success'),
    ]
    
    date = models.DateField()
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_stores = models.IntegerField(default=0)
    successful_stores = models.IntegerField(default=0)
    failed_stores = models.IntegerField(default=0)
    total_records = models.IntegerField(default=0)
    error_log = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'scraping_sessions'
        ordering = ['-date', '-start_time']

class ScrapingError(models.Model):
    session = models.ForeignKey(ScrapingSession, on_delete=models.CASCADE)
    store_id = models.IntegerField()
    error_type = models.CharField(max_length=100)
    error_message = models.TextField()
    url = models.URLField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    retry_count = models.IntegerField(default=0)
    resolved = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'scraping_errors'
