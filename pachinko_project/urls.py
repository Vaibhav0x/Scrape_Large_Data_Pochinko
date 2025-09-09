from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('scraper/', include('scraper.urls')),
    path('', lambda request: redirect('scraper:dashboard')),  # Optional redirect

]
