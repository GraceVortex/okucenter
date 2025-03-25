from django.db.models import Count, Q
from .models import Conversation

def unread_messages_count(request):
    """
    Контекстный процессор для подсчета непрочитанных сообщений
    """
    if request.user.is_authenticated:
        # Получаем количество непрочитанных сообщений для текущего пользователя
        unread_count = Conversation.objects.filter(
            participants=request.user
        ).annotate(
            unread=Count(
                'messages',
                filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user)
            )
        ).filter(unread__gt=0).aggregate(total=Count('id'))['total']
        
        return {'unread_messages_count': unread_count}
    return {'unread_messages_count': 0}
