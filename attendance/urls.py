from django.urls import path
from . import views
from . import views_face_id
from . import views_face_attendance_new
from . import views_attendance_log

app_name = 'attendance'

urlpatterns = [
    # URL-маршруты для управления посещаемостью
    path('', views.attendance_list, name='attendance_list'),
    path('list/', views.attendance_list, name='attendance_list_alt'),
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
    
    # URL-маршруты для Face ID
    path('face-id/', views_face_id.face_id, name='face_id'),
    path('face-id-new/', views_face_id.face_id_new, name='face_id_new'),
    path('api/face-id/recognize/', views_face_id.api_recognize_face, name='api_face_id_recognize'),
    path('api/face-id/mark-attendance/', views_face_id.api_mark_attendance, name='api_face_id_mark_attendance'),
    
    # URL-маршруты для улучшенной версии Face ID
    path('quick-face-attendance/', views_face_attendance_new.quick_face_attendance, name='quick_face_attendance'),
    path('quick-face-attendance-new/', views_face_attendance_new.quick_face_attendance_new, name='quick_face_attendance_new'),
    path('api/quick-face/recognize/', views_face_attendance_new.api_recognize_face, name='api_quick_face_recognize'),
    path('api/quick-face/mark-attendance/', views_face_attendance_new.api_mark_attendance, name='api_quick_face_mark_attendance'),
    
    # URL-маршруты для отмены занятий студентами
    path('student/cancel/<int:class_id>/<int:schedule_id>/<str:date>/', views.student_cancel_lesson, name='student_cancel_lesson'),
    path('student/cancellation-requests/', views.student_cancellation_requests, name='student_cancellation_requests'),
    path('parent/cancel/<int:student_id>/<int:class_id>/<int:schedule_id>/<str:date>/', views.parent_cancel_lesson, name='parent_cancel_lesson'),
    path('admin/student-cancellation-requests/', views.admin_student_cancellation_requests, name='admin_student_cancellation_requests'),
    path('admin/process-student-cancellation/<int:request_id>/<str:action>/', views.process_student_cancellation_request, name='process_student_cancellation_request'),
    path('cancel-student-cancellation/<int:request_id>/', views.cancel_student_cancellation_request, name='cancel_student_cancellation_request'),
    
    # URL-маршруты для журнала посещений с Face ID
    path('face-log/', views_attendance_log.attendance_log, name='attendance_log'),
    path('face-log/<int:attendance_id>/', views_attendance_log.attendance_log_detail, name='attendance_log_detail'),
]
