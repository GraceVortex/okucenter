from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    # URL-маршруты для управления финансами
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/add/', views.add_transaction, name='add_transaction'),
    path('student/balance/', views.student_balance, name='my_balance'),
    path('student/<int:student_id>/balance/', views.student_balance, name='student_balance'),
    path('class/<int:class_id>/finances/', views.class_finances, name='class_finances'),
    path('student/<int:student_id>/deposit/', views.deposit_balance, name='deposit_balance'),
    
    # URL-маршруты для управления зарплатами учителей
    path('teacher/salary/', views.teacher_salary, name='teacher_salary'),
    path('teacher/salary/<int:year>/<int:month>/', views.teacher_salary, name='teacher_salary'),
    path('teacher/salary/overall/', views.teacher_salary_overall, name='teacher_salary_overall'),
    path('admin/salaries/', views.admin_salary_summary, name='admin_salary_summary'),
    path('admin/salaries/<int:year>/<int:month>/', views.admin_salary_summary, name='admin_salary_summary'),
    path('teacher/<int:teacher_id>/salary/mark-paid/<int:year>/<int:month>/', views.mark_salary_paid, name='mark_salary_paid'),
]
