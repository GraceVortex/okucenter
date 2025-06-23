from django.urls import path
from django.shortcuts import render
from . import views
from . import views_student_face
from . import views_api
from . import views_test
# Импортируем представления для FaceNet
from .views_facenet import facenet_compare
# Импортируем представления для отметки посещаемости
from . import views_attendance

app_name = 'face_recognition_app'

urlpatterns = [
    # Основные функции распознавания лиц
    path('register/', views.face_registration, name='face_registration'),
    path('attendance/', views.face_attendance, name='face_attendance'),
    path('logs/', views.face_recognition_logs, name='logs'),
    path('attendance-list/', views.face_attendance_list, name='face_attendance_list'),
    path('register-face/', views.register_face, name='register_face'),
    path('simple-face-compare/', views.simple_face_compare, name='simple_face_compare'),
    
    # Отладочные URL-маршруты
    path('debug-face-recognition/', views.simple_face_compare, name='debug_face_recognition'),
    
    # Тестовая страница для проверки алгоритма распознавания лиц
    path('test/', views.test_face_recognition, name='test_face_recognition'),
    
    # URL-маршруты для регистрации лица ученика
    path('register-student-face/', views_student_face.register_student_face, name='register_student_face'),
    path('api/register-student-face/', views_student_face.api_register_student_face, name='api_register_student_face'),
    
    # URL-маршруты для отметки посещаемости по распознаванию лица
    path('attendance-page/', views_attendance.attendance_page, name='attendance_page'),
    path('simple-attendance/', views_attendance.simple_attendance_page, name='simple_attendance_page'),
    path('mark-attendance-page/', views_attendance.mark_attendance_page, name='mark_attendance_page'),
    path('recognize/', views_attendance.recognize_face_view, name='recognize_face'),
    path('mark-attendance/', views_attendance.mark_attendance_view, name='mark_attendance'),
    path('api/active-classes/', views_attendance.get_active_classes, name='get_active_classes'),
    
    # Сравнение лиц с использованием FaceNet
    path('compare/', facenet_compare, name='face_compare'),
    
    # API для распознавания лиц
    path('api/recognize-attendance/', views_api.api_recognize_attendance, name='api_recognize_attendance'),
    path('api/recognize/', views.api_recognize_face, name='api_recognize_face'),
    path('api/mark-attendance/', views.api_mark_attendance, name='api_mark_attendance'),
    path('api/get-class-dates/', views.api_get_class_dates, name='api_get_class_dates'),
    
    # Тестовые страницы для отладки FaceNet
    path('test-facenet/', views_test.test_facenet, name='test_facenet'),
    # Тестовая страница для распознавания лиц без аутентификации
    path('test-recognize/', views_test.test_recognize_face, name='test_facenet_recognize'),
    # Тестовая страница для проверки API
    path('test-api/', lambda request: render(request, 'face_recognition/test_api.html'), name='test_api'),
    path('api/test-compare/', views_test.test_compare_faces, name='test_compare_faces'),
    path('api/test-recognize/', views_test.test_recognize_face, name='test_recognize_face'),
]
