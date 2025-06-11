from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Sum, Q
from accounts.models import Student
from finance.models import Transaction
from classes.models import Class, Enrollment

@login_required
def student_finance_report(request, student_id):
    """Отображает финансовую выписку для ребенка родителя."""
    
    # Проверяем, что пользователь является родителем
    if not request.user.is_parent:
        return redirect('core:home')
    
    # Получаем профиль родителя
    parent = request.user.get_parent_profile()
    if not parent:
        return redirect('core:home')
    
    # Проверяем, что студент принадлежит родителю
    student = get_object_or_404(Student, id=student_id, parent=parent)
    
    # Получаем текущую дату
    today = timezone.now().date()
    
    # Получаем месяц и год из параметров URL или используем текущий месяц
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))
    
    # Создаем дату для первого дня выбранного месяца
    start_date = datetime(year, month, 1).date()
    
    # Вычисляем последний день месяца
    if month == 12:
        end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
    
    # Вычисляем предыдущий месяц
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year
    
    # Вычисляем следующий месяц
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
        
    # Получаем название месяца на русском
    month_names = {
        1: 'Январь',
        2: 'Февраль',
        3: 'Март',
        4: 'Апрель',
        5: 'Май',
        6: 'Июнь',
        7: 'Июль',
        8: 'Август',
        9: 'Сентябрь',
        10: 'Октябрь',
        11: 'Ноябрь',
        12: 'Декабрь'
    }
    current_month_name = month_names[month]
    
    # Получаем все транзакции студента за выбранный период
    transactions = Transaction.objects.filter(
        student=student,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('-date')
    
    # Рассчитываем общую сумму транзакций за период
    total_amount = transactions.aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Получаем классы, которые посещает студент через модель Enrollment
    # Получаем ID классов, в которые зачислен студент
    class_ids = Enrollment.objects.filter(student=student, is_active=True).values_list('class_obj_id', flat=True)
    # Получаем сами классы по ID
    classes = Class.objects.filter(id__in=class_ids)
    
    context = {
        'student': student,
        'transactions': transactions,
        'total_amount': total_amount,
        'start_date': start_date,
        'end_date': end_date,
        'classes': classes,
        # Добавляем информацию о навигации по месяцам
        'current_month': month,
        'current_year': year,
        'current_month_name': current_month_name,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'is_current_month': (month == today.month and year == today.year),
    }
    
    return render(request, 'finance/parent_student_finance.html', context)
