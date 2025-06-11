from django.urls import path
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import api
from . import parent_views

app_name = 'finance'

# API маршруты
api_urlpatterns = [
    # API для финансовой панели управления
    path('dashboard/', api.FinancialDashboardAPI.as_view(), name='api_financial_dashboard'),
    
    # API для зарплат учителей
    path('teacher-salaries/', api.TeacherSalaryAPI.as_view(), name='api_teacher_salaries'),
    path('teacher-salaries/<int:teacher_id>/<int:year>/<int:month>/', 
         api.TeacherSalaryDetailAPI.as_view(), name='api_teacher_salary_detail'),
    
    # API для транзакций
    path('transactions/', api.TransactionAPI.as_view(), name='api_transactions'),
]

# Стандартные URL-маршруты
urlpatterns = [
    # URL-маршруты для управления финансами
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/add/', views.add_transaction, name='add_transaction'),
    path('student/transactions/', views.student_transactions, name='student_transactions'),
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
    path('teacher/<int:teacher_id>/salary/pay-advance/<int:year>/<int:month>/', views.pay_salary_advance, name='pay_salary_advance'),
    path('teacher/<int:teacher_id>/salary/detail/<int:year>/<int:month>/', views.teacher_salary_detail, name='teacher_salary_detail'),
    
    # URL-маршруты для просмотра доходов от уроков и выплат учителям
    path('lesson-income/', views.lesson_income_transactions, name='lesson_income'),
    path('teacher-payments/', views.teacher_payments_transactions, name='teacher_payments'),
    
    # URL-маршрут для экспорта транзакций в Excel
    path('transactions/export/excel/', views.export_transactions_excel, name='export_transactions_excel'),
    
    # URL-маршрут для просмотра финансовой выписки ребенка родителем
    path('parent/student/<int:student_id>/finance/', parent_views.student_finance_report, name='parent_student_finance'),
    
    # API маршруты
    path('api/', include(api_urlpatterns)),
]
