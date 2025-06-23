from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from .models import InstagramClient, InstagramMessage
from .permissions import admin_or_reception_required


@admin_or_reception_required
def instagram_dashboard(request):
    """Admin dashboard for Instagram bot statistics and monitoring"""
    # Get basic statistics
    total_clients = InstagramClient.objects.count()
    total_messages = InstagramMessage.objects.count()
    
    # Get messages from today
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    messages_today = InstagramMessage.objects.filter(timestamp__gte=today).count()
    
    # Get recent clients with their last messages
    recent_clients = InstagramClient.objects.all().order_by('-updated_at')[:10]
    
    # Enhance client objects with additional information
    for client in recent_clients:
        client.message_count = client.messages.count()
        client.last_message = client.messages.order_by('-timestamp').first()
    
    context = {
        'total_clients': total_clients,
        'total_messages': total_messages,
        'messages_today': messages_today,
        'recent_clients': recent_clients,
        'today': timezone.now(),  # Pass current date for badge display
        'title': 'Instagram Bot Dashboard',
    }
    
    return render(request, 'instagram_bot/dashboard.html', context)
