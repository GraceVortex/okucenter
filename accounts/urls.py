from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Маршруты для аутентификации
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    
    # Маршруты для администраторов
    path('admin/reception/', views.reception_list, name='reception_list'),
    path('admin/reception/add/', views.add_reception, name='add_reception'),
    path('admin/reception/<int:pk>/edit/', views.edit_reception, name='edit_reception'),
    path('admin/reception/<int:pk>/delete/', views.delete_reception, name='delete_reception'),
    
    path('admin/teachers/', views.teacher_list, name='teacher_list'),
    path('admin/teachers/add/', views.add_teacher, name='add_teacher'),
    path('admin/teachers/<int:pk>/edit/', views.edit_teacher, name='edit_teacher'),
    path('admin/teachers/<int:pk>/delete/', views.delete_teacher, name='delete_teacher'),
    
    path('admin/students/', views.student_list, name='student_list'),
    path('admin/students/add/', views.add_student, name='add_student'),
    path('admin/students/<int:pk>/edit/', views.edit_student, name='edit_student'),
    path('admin/students/<int:pk>/delete/', views.delete_student, name='delete_student'),
    
    path('admin/parents/', views.parent_list, name='parent_list'),
    path('parents/<int:pk>/', views.parent_detail, name='parent_detail'),
    
    # Маршруты для родителей
    path('parent/dashboard/', views.parent_dashboard, name='parent_dashboard'),
    path('parent/child/<int:student_id>/', views.child_detail, name='child_detail'),
    path('parent/children/', views.parent_children, name='parent_children'),
]
