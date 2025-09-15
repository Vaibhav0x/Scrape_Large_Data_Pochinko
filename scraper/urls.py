from django.urls import path
from . import views

app_name = 'scraper'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('data/', views.data_explorer, name='data_explorer'),
    path('sessions/', views.scraping_sessions, name='sessions'),
    # path('sessions/', views.scraping_sessions, name='scraping_sessions'),
    path('session/<int:session_id>/', views.session_detail, name='session_detail'),
    path('store/<int:store_id>/', views.store_detail, name='store_detail'),
    path('start-scraping/', views.start_scraping, name='start_scraping'),
    path('api/data/', views.api_data, name='api_data'),
    path("home/", views.home, name="scraper-home"),
    path("scrape-daily/", lambda req: views.run_command(req, "scrape-daily"), name="scrape-daily"),
    path("retry-failed/", lambda req: views.run_command(req, "retry-failed"), name="retry-failed"),
]
