from django.urls import path
from . import views
from .healthcheck import healthcheck

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('schedule/', views.schedule_view, name='schedule'),
    path('health/', healthcheck, name='healthcheck'),
]
