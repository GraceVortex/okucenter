from django.urls import path
from . import views
from . import parent_views
from .healthcheck import healthcheck

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('schedule/', views.schedule_view, name='schedule'),
    path('schedule/<int:schedule_id>/', views.schedule_detail_view, name='schedule_detail'),
    path('statistics/', views.student_statistics, name='statistics'),
    path('statistics/<int:student_id>/', views.student_statistics, name='statistics'),
    path('parent/', parent_views.parent_home, name='parent_home'),
    path('health/', healthcheck, name='healthcheck'),
    path('change-language/', views.change_language, name='change_language'),
]
