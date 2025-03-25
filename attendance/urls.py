from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    # URL-маршруты для управления посещаемостью
    path('', views.attendance_list, name='attendance_list'),
    path('mark/<int:class_id>/', views.mark_attendance, name='mark_attendance'),
    path('confirm/<int:attendance_id>/', views.confirm_attendance, name='confirm_attendance'),
    path('mark/add/<int:attendance_id>/', views.add_mark, name='add_mark'),
    
    # URL-маршруты для отмены посещений
    path('cancel/<int:attendance_id>/', views.cancel_attendance, name='cancel_attendance'),
    path('canceled/', views.canceled_attendance_list, name='canceled_attendance_list'),
    
    # URL-маршруты для запросов на отмену уроков
    path('request-cancellation/<int:class_id>/', views.request_class_cancellation, name='request_class_cancellation'),
    path('request-cancellation/<int:class_id>/<str:date>/', views.request_class_cancellation, name='request_class_cancellation_date'),
    path('cancellation-requests/', views.cancellation_requests_list, name='cancellation_requests_list'),
    path('approve-cancellation/<int:request_id>/', views.approve_cancellation_request, name='approve_cancellation_request'),
    
    # URL-маршруты для уроков замены
    path('substitute-classes/', views.substitute_classes_list, name='substitute_classes_list'),
    path('mark-substitute/<int:class_id>/<str:date>/', views.mark_substitute_attendance, name='mark_substitute_attendance'),
]
