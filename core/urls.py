from django.urls import path
from . import views
from .healthcheck import healthcheck

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('schedule/', views.student_schedule, name='schedule'),
    path('schedule/<int:schedule_id>/', views.schedule_detail_view, name='schedule_detail'),
    path('statistics/', views.student_statistics, name='statistics'),
    path('statistics/<int:student_id>/', views.student_statistics, name='statistics'),
    path('health/', healthcheck, name='healthcheck'),
]
