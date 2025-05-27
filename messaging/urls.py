from django.urls import path
from . import views
from . import whatsapp_views
from . import telegram_views

app_name = 'messaging'

urlpatterns = [
    # Внутренние сообщения
    path('inbox/', views.inbox, name='inbox'),
    path('conversation/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    path('conversation/create/', views.create_conversation, name='create_conversation'),
    path('conversation/<int:conversation_id>/close/', views.close_conversation, name='close_conversation'),
    
    # WhatsApp рассылки
    path('whatsapp/', whatsapp_views.whatsapp_dashboard, name='whatsapp_dashboard'),
    path('whatsapp/create/', whatsapp_views.create_broadcast, name='create_broadcast'),
    path('whatsapp/broadcast/<int:broadcast_id>/', whatsapp_views.broadcast_detail, name='broadcast_detail'),
    path('whatsapp/broadcast/<int:broadcast_id>/send/', whatsapp_views.send_broadcast, name='send_broadcast'),
    path('whatsapp/broadcast/<int:broadcast_id>/cancel/', whatsapp_views.cancel_broadcast, name='cancel_broadcast'),
    path('whatsapp/broadcast/<int:broadcast_id>/delete/', whatsapp_views.delete_broadcast, name='delete_broadcast'),
    
    # API для WhatsApp рассылок
    path('api/get-recipients/', whatsapp_views.api_get_recipients, name='api_get_recipients'),
    path('api/get-schedules/', whatsapp_views.api_get_schedules, name='api_get_schedules'),
    
    # Выбор типа рассылки
    path('choice/', telegram_views.messaging_choice, name='messaging_choice'),
    
    # Telegram рассылки
    path('telegram/', telegram_views.telegram_dashboard, name='telegram_dashboard'),
    path('telegram/create/', telegram_views.create_telegram_broadcast, name='create_telegram_broadcast'),
    path('telegram/broadcast/<int:broadcast_id>/', telegram_views.telegram_broadcast_detail, name='telegram_broadcast_detail'),
    path('telegram/broadcast/<int:broadcast_id>/send/', telegram_views.send_telegram_broadcast, name='send_telegram_broadcast'),
    path('telegram/broadcast/<int:broadcast_id>/cancel/', telegram_views.cancel_telegram_broadcast, name='cancel_telegram_broadcast'),
    path('telegram/broadcast/<int:broadcast_id>/delete/', telegram_views.delete_telegram_broadcast, name='delete_telegram_broadcast'),
    
    # Управление пользователями Telegram
    path('telegram/users/', telegram_views.telegram_users, name='telegram_users'),
    path('telegram/users/<int:user_id>/toggle/', telegram_views.toggle_telegram_user, name='toggle_telegram_user'),
    path('telegram/users/<int:user_id>/link/', telegram_views.link_telegram_user, name='link_telegram_user'),
    
    # API для Telegram рассылок
    path('api/telegram/get-recipients/', telegram_views.api_get_telegram_recipients, name='api_get_telegram_recipients'),
    path('api/telegram/get-schedules/', telegram_views.api_get_telegram_schedules, name='api_get_telegram_schedules'),
]
