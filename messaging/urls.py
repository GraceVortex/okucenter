from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    path('inbox/', views.inbox, name='inbox'),
    path('conversation/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    path('conversation/create/', views.create_conversation, name='create_conversation'),
    path('conversation/<int:conversation_id>/close/', views.close_conversation, name='close_conversation'),
]
