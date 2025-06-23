from django.urls import path
from .views import instagram_webhook
from .admin_views import instagram_dashboard
from .permissions import admin_or_reception_required

app_name = 'instagram_bot'

urlpatterns = [
    # Single webhook endpoint that handles both GET (verification) and POST (messages)
    path('webhook/', instagram_webhook, name='instagram_webhook'),
    
    # Dashboard URL for admin interface - accessible by admins and receptionists
    path('dashboard/', admin_or_reception_required(instagram_dashboard), name='instagram_bot_dashboard'),
]
