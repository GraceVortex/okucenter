from django.urls import path
from . import views
from . import views_student_face
from . import views_api
# Импортируем представления для FaceNet
from .views_facenet import facenet_compare

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
    
    # Сравнение лиц с использованием FaceNet
    path('compare/', facenet_compare, name='face_compare'),
    
    # API для распознавания лиц
    path('api/recognize-attendance/', views_api.api_recognize_attendance, name='api_recognize_attendance'),
    path('api/recognize/', views.api_recognize_face, name='api_recognize_face'),
    path('api/mark-attendance/', views.api_mark_attendance, name='api_mark_attendance'),
    path('api/get-class-dates/', views.api_get_class_dates, name='api_get_class_dates'),
]
