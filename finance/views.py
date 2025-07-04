from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, F, Q, Case, When, IntegerField
from datetime import datetime, timedelta
from decimal import Decimal
import xlwt
import io
from .models import Transaction, TeacherSalary
from .forms import TransactionForm, TransactionFilterForm, DepositForm
from accounts.models import Student, User, Teacher
from classes.models import Class
from attendance.models import Attendance
from classes.non_scheduled_lesson_models import NonScheduledLesson, NonScheduledLessonAttendance
from dateutil.relativedelta import relativedelta

# Create your views here.

@login_required
def student_transactions(request):
    """Отображает транзакции текущего студента."""
    
    # Проверяем, что пользователь является студентом
    if not request.user.is_authenticated or not hasattr(request.user, 'student_profile'):
        return HttpResponseForbidden("Доступ запрещен")
    
    # Получаем профиль студента
    student = request.user.student_profile
    
    # Проверяем, что студент управляет своим аккаунтом самостоятельно
    if not student.is_self_managed:
        return HttpResponseForbidden("Доступ запрещен. Ваш аккаунт управляется родителем.")
    
    # Получаем период из GET-параметров
    period = request.GET.get('period', 'current_month')
    
    # Определяем даты начала и конца периода
    today = timezone.now().date()
    
    if period == 'current_month':
        start_date = today.replace(day=1)
        end_date = (start_date + relativedelta(months=1) - timedelta(days=1))
    elif period == 'previous_month':
        start_date = (today.replace(day=1) - relativedelta(months=1))
        end_date = (today.replace(day=1) - timedelta(days=1))
    else:
        # По умолчанию - текущий месяц
        period = 'current_month'
        start_date = today.replace(day=1)
        end_date = (start_date + relativedelta(months=1) - timedelta(days=1))
    
    # Получаем транзакции студента за выбранный период
    transactions = Transaction.objects.filter(
        student=student,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('-date')
    
    # Рассчитываем суммы по типам транзакций
    deposits = transactions.filter(transaction_type='deposit').aggregate(Sum('amount'))['amount__sum'] or 0
    payments = transactions.filter(transaction_type='payment').aggregate(Sum('amount'))['amount__sum'] or 0
    refunds = transactions.filter(transaction_type='refund').aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Проверяем, соответствует ли текущий баланс формуле: пополнения - списания + возвраты
    # Получаем все транзакции студента (без фильтрации по дате)
    all_deposits = Transaction.objects.filter(student=student, transaction_type='deposit').aggregate(Sum('amount'))['amount__sum'] or 0
    all_payments = Transaction.objects.filter(student=student, transaction_type='payment').aggregate(Sum('amount'))['amount__sum'] or 0
    all_refunds = Transaction.objects.filter(student=student, transaction_type='refund').aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Рассчитываем ожидаемый баланс по формуле: Депозиты - Платежи + Возвраты
    expected_balance = all_deposits - all_payments + all_refunds
    
    # Проверяем, совпадает ли расчетный баланс с фактическим
    balance_matches = abs(student.balance - expected_balance) < 0.01  # Учитываем возможные ошибки округления
    
    # Локализация названий месяцев
    month_names = {
        1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель', 5: 'Май', 6: 'Июнь',
        7: 'Июль', 8: 'Август', 9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
    }
    
    month_name = month_names.get(start_date.month, '')
    month_year = f"{month_name} {start_date.year}"
    
    context = {
        'transactions': transactions,
        'balance': student.balance,
        'deposits': deposits,
        'payments': payments,
        'refunds': refunds,
        'current_period': period,
        'start_date': start_date,
        'end_date': end_date,
        'month_year': month_year,
        'expected_balance': expected_balance,
        'balance_matches': balance_matches,
        'all_deposits': all_deposits,
        'all_payments': all_payments,
        'all_refunds': all_refunds,
    }
    
    return render(request, 'finance/student_transactions.html', context)

@login_required
def student_balance(request, student_id=None):
    """Отображает баланс и транзакции студента."""
    
    # Получаем текущую дату
    today = timezone.now().date()
    
    # Получаем период из параметров запроса
    period = request.GET.get('period', 'current_month')
    
    # Определяем даты начала и конца в зависимости от выбранного периода
    if period == 'current_month':
        # Текущий месяц
        start_date = today.replace(day=1)
        # Последний день текущего месяца
        if today.month == 12:
            end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    elif period == 'previous_month':
        # Прошлый месяц
        if today.month == 1:
            start_date = today.replace(year=today.year - 1, month=12, day=1)
            end_date = today.replace(day=1) - timedelta(days=1)
        else:
            start_date = today.replace(month=today.month - 1, day=1)
            end_date = today.replace(day=1) - timedelta(days=1)
    elif period == 'last_3_months':
        # Последние 3 месяца
        start_date = (today - timedelta(days=90)).replace(day=1)
        end_date = today
    elif period == 'last_year':
        # Последний год
        start_date = today.replace(year=today.year - 1, day=1)
        end_date = today
    else:
        # По умолчанию - текущий месяц
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    
    # Определяем, какого студента показывать
    if student_id:
        # Если указан ID студента
        if request.user.is_admin or request.user.is_reception:
            # Администраторы и ресепшн могут видеть баланс любого студента
            student = get_object_or_404(Student, id=student_id)
        else:
            # Другие пользователи не могут видеть баланс других студентов
            return HttpResponseForbidden("У вас нет доступа к этой странице.")
    else:
        # Если ID не указан, используем профиль текущего пользователя
        if hasattr(request.user, 'student_profile'):
            student = request.user.student_profile
        else:
            # Если пользователь не является студентом
            return HttpResponseForbidden("У вас нет доступа к этой странице.")
    
    # Получаем транзакции студента
    transactions = Transaction.objects.filter(
        student=student,
        date__range=[start_date, end_date]
    ).order_by('-date', '-created_at')
    
    # Вычисляем сумму депозитов и платежей
    deposits = transactions.filter(transaction_type='deposit').aggregate(total=Sum('amount'))['total'] or 0
    payments = transactions.filter(transaction_type='payment').aggregate(total=Sum('amount'))['total'] or 0
    refunds = transactions.filter(transaction_type='refund').aggregate(total=Sum('amount'))['total'] or 0
    
    # Периоды для фильтрации
    periods = [
        {'value': 'current_month', 'label': 'Текущий месяц'},
        {'value': 'previous_month', 'label': 'Прошлый месяц'},
        {'value': 'last_3_months', 'label': 'За 3 месяца'},
        {'value': 'last_year', 'label': 'За год'}
    ]
    
    context = {
        'student': student,
        'transactions': transactions,
        'balance': student.balance,
        'deposits': deposits,
        'payments': payments,
        'refunds': refunds,
        'periods': periods,
        'current_period': period,
        'start_date': start_date,
        'end_date': end_date
    }
    
    return render(request, 'finance/student_balance.html', context)

@login_required
def transaction_list(request):
    """Отображает список транзакций для текущего пользователя."""
    
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
    
    # Получаем фильтры из формы
    form = TransactionFilterForm(request.GET or None)
    
    # Если форма содержит валидные даты, используем их вместо расчетных
    if form.is_valid():
        if form.cleaned_data.get('start_date'):
            start_date = form.cleaned_data.get('start_date')
        if form.cleaned_data.get('end_date'):
            end_date = form.cleaned_data.get('end_date')
        selected_student = form.cleaned_data.get('student')
        selected_class = form.cleaned_data.get('class_obj')
        transaction_type = form.cleaned_data.get('transaction_type')
    else:
        selected_student = None
        selected_class = None
        transaction_type = None
    
    # Фильтруем данные в зависимости от роли пользователя
    if request.user.is_admin or request.user.is_reception:
        # Администраторы и ресепшн видят все транзакции
        transactions = Transaction.objects.filter(
            date__range=[start_date, end_date]
        ).select_related('student', 'class_obj')
        
        # Получаем всех студентов и классы для формы фильтрации
        students = Student.objects.all()
        classes = Class.objects.all()
        
    elif request.user.is_teacher:
        # Преподаватели видят только транзакции своих классов
        teacher_classes = request.user.teacher_profile.classes.all()
        transactions = Transaction.objects.filter(
            date__range=[start_date, end_date],
            class_obj__in=teacher_classes
        ).select_related('student', 'class_obj')
        
        # Получаем студентов и классы только для этого преподавателя
        students = Student.objects.filter(enrollments__class_obj__in=teacher_classes).distinct()
        classes = teacher_classes
        
    elif request.user.is_student:
        # Студенты видят только свои транзакции
        transactions = Transaction.objects.filter(
            date__range=[start_date, end_date],
            student=request.user.student_profile
        ).select_related('student', 'class_obj')
        
        # Студенты не могут фильтровать по другим студентам
        students = Student.objects.filter(id=request.user.student_profile.id)
        classes = request.user.student_profile.enrollments.all()
        
    elif request.user.is_parent:
        # Родители видят транзакции своих детей
        parent_profile = request.user.get_parent_profile()
        parent_students = parent_profile.children.all() if parent_profile else []
        transactions = Transaction.objects.filter(
            date__range=[start_date, end_date],
            student__in=parent_students
        ).select_related('student', 'class_obj')
        
        # Родители могут фильтровать только по своим детям
        students = parent_students
        classes = Class.objects.filter(enrollments__student__in=parent_students).distinct()
        
    else:
        # Неизвестная роль - показываем пустой список
        transactions = Transaction.objects.none()
        students = Student.objects.none()
        classes = Class.objects.none()
    
    # Применяем дополнительные фильтры
    if selected_student:
        transactions = transactions.filter(student=selected_student)
    
    if selected_class:
        transactions = transactions.filter(class_obj=selected_class)
    
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    
    # Вычисляем общую сумму отфильтрованных транзакций
    total_amount = transactions.aggregate(
        total=Sum(Case(
            When(transaction_type='payment', then=-F('amount')),
            When(transaction_type='deposit', then=F('amount')),
            When(transaction_type='refund', then=F('amount')),
            output_field=IntegerField()
        ))
    )['total'] or 0
    
    # Получаем информацию о выплатах зарплат учителям
    if request.user.is_admin or request.user.is_reception:
        try:
            teacher_salaries = TeacherSalary.objects.filter(
                payment_status='paid',
                final_payment_date__range=[start_date, end_date]
            ).select_related('teacher')
        except Exception as e:
            # В случае ошибки возвращаем пустой QuerySet
            messages.error(request, f"Ошибка при получении зарплат учителей: {str(e)}")
            teacher_salaries = TeacherSalary.objects.none()
    else:
        teacher_salaries = TeacherSalary.objects.none()
    
    # 1. Общий баланс (сумма всех текущих балансов учеников)
    total_student_balance = Student.objects.aggregate(total=Sum('balance'))['total'] or 0
    total_student_balance = round(total_student_balance, 2)
    
    # 2. Доходы от уроков (все списания от учеников минус все возвраты)
    # Получаем все транзакции типа 'payment' за выбранный период
    payment_transactions = Transaction.objects.filter(
        transaction_type='payment',
        date__range=[start_date, end_date]
    )
    
    # Подсчитываем общую сумму платежей
    payments = payment_transactions.aggregate(total=Sum('amount'))['total'] or 0
    
    # Подсчитываем количество транзакций за уроки не по расписанию
    non_scheduled_lesson_payments_count = payment_transactions.filter(
        description__contains='урок не по расписанию'
    ).count()
    
    # Подсчитываем сумму транзакций за уроки не по расписанию
    non_scheduled_lesson_payments = payment_transactions.filter(
        description__contains='урок не по расписанию'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Получаем сумму всех возвратов (положительные значения)
    refunds = Transaction.objects.filter(
        transaction_type='refund',
        date__range=[start_date, end_date]
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Доход от уроков = сумма платежей - возвраты
    # В системе значение amount для транзакций типа 'payment' является положительным
    lesson_income = payments - refunds
    lesson_income = round(lesson_income, 2)
    
    # Добавляем отладочную информацию в контекст
    debug_info = {
        'total_payment_transactions': payment_transactions.count(),
        'non_scheduled_lesson_payments_count': non_scheduled_lesson_payments_count,
        'non_scheduled_lesson_payments_amount': abs(non_scheduled_lesson_payments),
        'start_date': start_date,
        'end_date': end_date
    }
    
    # 3. Выплаты учителям
    # Используем метод calculate_teacher_salary для расчета зарплат учителей
    # Этот метод учитывает как уроки по расписанию, так и уроки не по расписанию
    teacher_payments = Decimal('0.00')
    
    # Получаем всех учителей
    teachers = Teacher.objects.all()
    
    # Для каждого учителя рассчитываем зарплату
    for teacher in teachers:
        # Создаем временные даты для расчета зарплаты за выбранный период
        # Создаем временный объект месяца для начальной даты
        temp_month = start_date.replace(day=1)
        
        # Если период охватывает несколько месяцев, рассчитываем зарплату для каждого месяца
        current_month = temp_month
        while current_month <= end_date:
            # Рассчитываем зарплату за текущий месяц
            salary_data = TeacherSalary.calculate_teacher_salary(teacher, current_month)
            teacher_payments += salary_data['total']
            
            # Переходим к следующему месяцу
            if current_month.month == 12:
                current_month = current_month.replace(year=current_month.year + 1, month=1)
            else:
                current_month = current_month.replace(month=current_month.month + 1)
    
    # Округляем до двух знаков после запятой
    teacher_payments = round(teacher_payments, 2)
    
    # 4. Предконечный доход (доходы от уроков - выплаты учителям)
    pre_final_income = lesson_income - teacher_payments
    pre_final_income = round(pre_final_income, 2)
    
    context = {
        'transactions': transactions,
        'form': form,
        'total_amount': total_amount,
        'start_date': start_date,
        'end_date': end_date,
        'students': students,
        'classes': classes,
        'selected_student': selected_student,
        'selected_class': selected_class,
        'transaction_type': transaction_type,
        'total_student_balance': total_student_balance,
        'lesson_income': lesson_income,
        'teacher_payments': teacher_payments,
        'pre_final_income': pre_final_income,
        # Добавляем информацию о навигации по месяцам
        'current_month': month,
        'current_year': year,
        'current_month_name': current_month_name,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'is_current_month': (month == today.month and year == today.year),
        'teacher_salaries': teacher_salaries,
        'debug_info': debug_info,
    }
    
    return render(request, 'finance/transaction_list.html', context)

@login_required
def lesson_income_transactions(request):
    """
    Отображает транзакции по доходам от уроков (платежи типа 'payment').
    """
    # Проверяем права доступа
    if not request.user.is_authenticated or not (request.user.is_admin or request.user.is_reception):
        return HttpResponseForbidden("У вас нет прав для просмотра этой страницы")
    
    # Получаем месяц и год из GET-параметров
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
    
    # Получаем все транзакции типа 'payment' за выбранный период
    transactions = Transaction.objects.filter(
        transaction_type='payment',
        date__range=[start_date, end_date]
    ).select_related('student', 'class_obj')
    
    # Подсчитываем общую сумму платежей
    total_amount = transactions.aggregate(total=Sum('amount'))['total'] or 0
    
    context = {
        'transactions': transactions,
        'start_date': start_date,
        'end_date': end_date,
        'total_amount': total_amount,
        'title': 'Доходы от уроков',
        'description': 'Все платежи за уроки за выбранный период',
        # Добавляем информацию о навигации по месяцам
        'current_month': month,
        'current_year': year,
        'current_month_name': current_month_name,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'is_current_month': (month == today.month and year == today.year)
    }
    
    return render(request, 'finance/filtered_transactions.html', context)

@login_required
def teacher_payments_transactions(request):
    """
    Отображает информацию о выплатах учителям.
    """
    # Проверяем права доступа
    if not request.user.is_authenticated or not (request.user.is_admin or request.user.is_reception):
        return HttpResponseForbidden("У вас нет прав для просмотра этой страницы")
    
    # Получаем месяц и год из GET-параметров
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
    
    # Получаем информацию о выплатах зарплат учителям
    teacher_salaries = TeacherSalary.objects.filter(
        payment_status='paid',
        final_payment_date__range=[start_date, end_date]
    ).select_related('teacher')
    
    # Получаем всех учителей
    teachers = Teacher.objects.all()
    
    # Рассчитываем зарплату для каждого учителя
    teacher_payments_data = []
    total_payments = Decimal('0.00')
    
    for teacher in teachers:
        teacher_salary_amount = Decimal('0.00')
        
        # 1. Учитываем уроки по расписанию
        # Получаем все посещения для подсчета уникальных занятий
        attendances = Attendance.objects.filter(
            class_schedule__class_obj__teacher=teacher,
            date__range=[start_date, end_date],
            reception_confirmed=True
        ).select_related('class_schedule')
        
        # Считаем уникальные занятия по дате и расписанию
        unique_classes = {}
        for attendance in attendances:
            # Создаем уникальный ключ для каждой комбинации даты, класса и расписания
            key = (attendance.date, attendance.class_schedule.class_obj.id, attendance.class_schedule.id)
            if key not in unique_classes:
                unique_classes[key] = {
                    'date': attendance.date,
                    'class_obj': attendance.class_schedule.class_obj,
                    'class_schedule': attendance.class_schedule
                }
        
        # Рассчитываем сумму зарплаты на основе уникальных занятий по расписанию
        for key, data in unique_classes.items():
            class_obj = data['class_obj']
            
            # Определяем сумму за занятие
            if class_obj.teacher_payment_type == 'percentage':
                price = class_obj.price_per_lesson
                percentage = Decimal(str(class_obj.teacher_percentage)) / Decimal('100')
                amount = price * percentage
            else:  # fixed payment
                amount = class_obj.teacher_fixed_payment
            
            teacher_salary_amount += amount
        
        # 2. Учитываем уроки не по расписанию
        # Получаем все проведенные уроки не по расписанию для этого учителя
        non_scheduled_lessons = NonScheduledLesson.objects.filter(
            teacher=teacher,
            date__range=[start_date, end_date],
            is_completed=True
        )
        
        # Для каждого урока не по расписанию добавляем сумму оплаты учителю
        for lesson in non_scheduled_lessons:
            # Рассчитываем оплату учителю только за присутствующих учеников
            if lesson.lesson_type == 'trial' and lesson.trial_status != 'continued':
                # Если это пробный урок и ученик не продолжил обучение, не учитываем оплату
                continue
                
            # Получаем количество присутствующих учеников
            present_students_count = NonScheduledLessonAttendance.objects.filter(
                lesson=lesson,
                is_present=True
            ).count()
            
            # Если нет присутствующих учеников, не учитываем оплату
            if present_students_count == 0:
                continue
                
            # Если это обычный урок, учитываем оплату только за присутствующих учеников
            total_students_count = lesson.students.count()
            if total_students_count > 0:
                # Рассчитываем оплату учителю пропорционально количеству присутствующих учеников
                teacher_payment_per_student = Decimal(str(lesson.teacher_payment)) / Decimal(str(total_students_count))
                teacher_salary_amount += teacher_payment_per_student * Decimal(str(present_students_count))
        
        # Добавляем данные о зарплате учителя в список
        if teacher_salary_amount > 0:
            teacher_payments_data.append({
                'teacher': teacher,
                'amount': teacher_salary_amount,
                'lessons_count': len(unique_classes) + non_scheduled_lessons.count()
            })
            total_payments += teacher_salary_amount
    
    context = {
        'teacher_payments_data': teacher_payments_data,
        'teacher_salaries': teacher_salaries,
        'start_date': start_date,
        'end_date': end_date,
        'total_payments': total_payments,
        'title': 'Выплаты учителям',
        'description': 'Информация о выплатах учителям за проведенные уроки',
        # Добавляем информацию о навигации по месяцам
        'current_month': month,
        'current_year': year,
        'current_month_name': current_month_name,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'is_current_month': (month == today.month and year == today.year)
    }
    
    return render(request, 'finance/teacher_payments.html', context)

@login_required
def add_transaction(request):
    """Добавляет новую транзакцию."""
    
    # Проверка доступа
    if not (request.user.is_admin or request.user.is_reception):
        return HttpResponseForbidden("Только администраторы и ресепшн могут добавлять транзакции.")
    
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Создаем транзакцию
                new_transaction = form.save(commit=False)
                new_transaction.date = timezone.now().date()
                new_transaction.created_by = request.user
                
                # Обновляем баланс студента
                student = new_transaction.student
                if new_transaction.transaction_type == 'payment':
                    student.balance -= new_transaction.amount
                else:  # deposit или refund
                    student.balance += new_transaction.amount
                
                # Сохраняем изменения
                student.save()
                new_transaction.save()
                
                messages.success(request, f"Транзакция успешно добавлена. Новый баланс студента: {student.balance} ₸")
                return redirect('finance:transaction_list')
    else:
        form = TransactionForm()
    
    return render(request, 'finance/transaction_form.html', {'form': form})

@login_required
def deposit_balance(request, student_id):
    """Пополняет баланс студента."""
    
    # Проверка доступа
    if not (request.user.is_admin or request.user.is_reception):
        return HttpResponseForbidden("Только администраторы и ресепшн могут пополнять баланс студентов.")
    
    student = get_object_or_404(Student, id=student_id)
    
    if request.method == 'POST':
        form = DepositForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Получаем данные из формы
                amount = form.cleaned_data['amount']
                description = form.cleaned_data.get('description') or "Пополнение баланса"
                
                # Создаем транзакцию
                new_transaction = Transaction(
                    student=student,
                    amount=amount,
                    date=timezone.now().date(),
                    description=description,
                    transaction_type='deposit',
                    created_by=request.user
                )
                
                # Обновляем баланс студента
                student.balance += amount
                
                # Сохраняем изменения
                student.save()
                new_transaction.save()
                
                messages.success(request, f"Баланс студента {student.full_name} успешно пополнен на {amount} ₸. Новый баланс: {student.balance} ₸")
                return redirect('accounts:student_list')
    else:
        form = DepositForm()
    
    return render(request, 'finance/deposit_form.html', {
        'form': form,
        'student': student
    })

@login_required
def student_balance(request, student_id=None):
    """Отображает баланс студента и историю транзакций."""
    
    # Проверяем доступ для учеников
    if request.user.is_student:
        # Получаем профиль студента
        student_profile = request.user.student_profile
        
        # Если ученик не самоуправляемый (имеет привязанного родителя), то запрещаем доступ
        if student_profile and not student_profile.is_self_managed:
            return HttpResponseForbidden("У вас нет доступа к финансовой информации. Эта информация доступна только вашему родителю.")
        
        # Если ученик самоуправляемый, то проверяем, что он смотрит свой баланс
        if student_id and student_id != str(student_profile.id):
            return HttpResponseForbidden("Вы можете просматривать только свою финансовую информацию.")
    
    # Определяем, чей баланс показывать
    if student_id:
        # Проверка доступа
        if request.user.is_admin or request.user.is_reception or request.user.is_teacher:
            student = get_object_or_404(Student, id=student_id)
        elif request.user.is_parent:
            # Проверяем, является ли запрашиваемый студент ребенком этого родителя
            parent_profile = request.user.get_parent_profile()
            student = get_object_or_404(Student, id=student_id, parent=parent_profile)
        else:
            return HttpResponseForbidden("У вас нет доступа к этой странице.")
    else:
        # Если student_id не указан, показываем баланс для родителя
        parent_profile = request.user.get_parent_profile()
        if request.user.is_parent and parent_profile and parent_profile.children.exists():
            # Для родителя показываем первого ребенка (можно улучшить)
            student = parent_profile.children.first()
        else:
            return HttpResponseForbidden("У вас нет доступа к этой странице.")
    
    # Получаем параметр фильтра из запроса
    transaction_filter = request.GET.get('filter', 'last_deposit')
    
    # Базовый запрос для транзакций студента
    transactions_query = Transaction.objects.filter(student=student)
    
    # Применяем фильтр
    if transaction_filter == 'deposits':
        transactions = transactions_query.filter(transaction_type='deposit').order_by('-date', '-created_at')
        active_filter = 'deposits'
    elif transaction_filter == 'payments':
        transactions = transactions_query.filter(transaction_type='payment').order_by('-date', '-created_at')
        active_filter = 'payments'
    elif transaction_filter == 'refunds':
        transactions = transactions_query.filter(transaction_type='refund').order_by('-date', '-created_at')
        active_filter = 'refunds'
    elif transaction_filter == 'last_deposit':
        # Находим дату последнего пополнения
        last_deposit = transactions_query.filter(transaction_type='deposit').order_by('-date', '-created_at').first()
        
        if last_deposit:
            # Показываем транзакции с даты последнего пополнения
            transactions = transactions_query.filter(date__gte=last_deposit.date).order_by('-date', '-created_at')
        else:
            # Если пополнений не было, показываем все транзакции
            transactions = transactions_query.order_by('-date', '-created_at')
        
        active_filter = 'last_deposit'
    else:  # 'all' или любой другой
        transactions = transactions_query.order_by('-date', '-created_at')
        active_filter = 'all'
    
    # Рассчитываем финансовую статистику
    total_deposits = Transaction.objects.filter(
        student=student, 
        transaction_type='deposit'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_payments = Transaction.objects.filter(
        student=student, 
        transaction_type='payment'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Добавляем расчет возвратов (рефандов)
    total_refunds = Transaction.objects.filter(
        student=student, 
        transaction_type='refund'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Если выбран фильтр "с последнего пополнения", рассчитываем статистику только для этого периода
    if active_filter == 'last_deposit':
        last_deposit = transactions_query.filter(transaction_type='deposit').order_by('-date', '-created_at').first()
        
        if last_deposit:
            # Статистика с даты последнего пополнения
            period_deposits = Transaction.objects.filter(
                student=student, 
                transaction_type='deposit',
                date__gte=last_deposit.date
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            period_payments = Transaction.objects.filter(
                student=student, 
                transaction_type='payment',
                date__gte=last_deposit.date
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Добавляем информацию о периоде
            period_start = last_deposit.date
            period_end = timezone.now().date()
        else:
            # Если пополнений не было, используем общую статистику
            period_deposits = total_deposits
            period_payments = total_payments
            period_start = None
            period_end = None
    else:
        # Для других фильтров используем общую статистику
        period_deposits = total_deposits
        period_payments = total_payments
        period_start = None
        period_end = None
    
    # Рассчитываем текущий баланс на основе транзакций
    # Баланс = Депозиты - Платежи + Возвраты
    calculated_balance = total_deposits - total_payments + total_refunds
    
    # Проверяем, совпадает ли рассчитанный баланс с балансом в модели
    if abs(calculated_balance - student.balance) > 0.01:  # Допускаем небольшую погрешность из-за округления
        # Если есть расхождение, обновляем баланс в модели
        student.balance = calculated_balance
        student.save(update_fields=['balance'])
        
        # Добавляем сообщение для администраторов
        if request.user.is_admin or request.user.is_reception:
            messages.warning(request, f"Баланс студента был обновлен с {student.balance} на {calculated_balance} тенге на основе транзакций.")
    
    context = {
        'student': student,
        'transactions': transactions,
        'balance': student.balance,  # Теперь это гарантированно совпадает с рассчитанным балансом
        'total_deposits': round(total_deposits, 2),
        'total_payments': round(total_payments, 2),
        'total_refunds': round(total_refunds, 2),  # Добавляем информацию о возвратах
        'period_deposits': round(period_deposits, 2),
        'period_payments': round(period_payments, 2),
        'period_start': period_start,
        'period_end': period_end,
        'active_filter': active_filter,
    }
    
    return render(request, 'finance/student_balance.html', context)

@login_required
def class_finances(request, class_id):
    """Отображает финансовую информацию по классу."""
    
    # Проверка доступа
    if not (request.user.is_admin or request.user.is_reception):
        return HttpResponseForbidden("Только администраторы и ресепшн могут просматривать финансы классов.")
    
    class_obj = get_object_or_404(Class, id=class_id)
    
    # Получаем все транзакции для этого класса
    transactions = Transaction.objects.filter(class_obj=class_obj).order_by('-date')
    
    # Вычисляем общую сумму транзакций
    total_amount = transactions.aggregate(
        total=Sum(Case(
            When(transaction_type='payment', then=F('amount')),
            When(transaction_type='refund', then=-F('amount')),
            output_field=IntegerField()
        ))
    )['total'] or 0
    
    # Группируем транзакции по студентам
    student_transactions = {}
    for transaction in transactions:
        if transaction.student.id not in student_transactions:
            student_transactions[transaction.student.id] = {
                'student': transaction.student,
                'transactions': [],
                'total': 0
            }
        
        student_transactions[transaction.student.id]['transactions'].append(transaction)
        
        # Учитываем тип транзакции при подсчете суммы
        if transaction.transaction_type == 'payment':
            student_transactions[transaction.student.id]['total'] += transaction.amount
        elif transaction.transaction_type == 'refund':
            student_transactions[transaction.student.id]['total'] -= transaction.amount
    
    context = {
        'class': class_obj,
        'transactions': transactions,
        'student_transactions': student_transactions.values(),
        'total_amount': round(total_amount, 2),
    }
    
    return render(request, 'finance/class_finances.html', context)

@login_required
def teacher_salary(request, month=None, year=None):
    """Отображает информацию о зарплате учителя."""
    
    if not request.user.is_teacher and not request.user.is_admin and not request.user.is_reception:
        return HttpResponseForbidden("Эта страница доступна только учителям, администраторам и ресепшн.")
    
    from .models import TeacherSalary
    from accounts.models import Teacher
    from datetime import datetime
    from classes.models import Class
    
    # Определяем учителя
    if request.user.is_teacher:
        teacher = get_object_or_404(Teacher, user=request.user)
    else:
        # Для админа и ресепшн - получаем ID учителя из параметров запроса
        teacher_id = request.GET.get('teacher_id')
        if teacher_id:
            teacher = get_object_or_404(Teacher, id=teacher_id)
        else:
            # Если ID не указан, перенаправляем на список учителей
            messages.info(request, "Пожалуйста, выберите учителя для просмотра зарплаты.")
            return redirect('accounts:teacher_list')
    
    # Определяем месяц и год для отображения
    current_date = timezone.now().date()
    
    if month is None:
        month = current_date.month
    else:
        month = int(month)
    
    if year is None:
        year = current_date.year
    else:
        year = int(year)
    
    # Создаем дату первого дня месяца
    first_day = datetime(year, month, 1).date()
    
    # Получаем все выплаченные зарплаты учителя, отсортированные по дате выплаты
    paid_salaries = TeacherSalary.objects.filter(
        teacher=teacher,
        payment_status='paid',
        final_payment_date__isnull=False
    ).order_by('-final_payment_date')
    
    # Определяем период для отображения
    start_date = None
    end_date = None
    
    if paid_salaries.exists():
        # Если есть выплаченные зарплаты, берем последнюю как конечную дату
        end_date = paid_salaries.first().final_payment_date
        
        # Если есть более одной выплаты, берем предпоследнюю как начальную дату
        if paid_salaries.count() > 1:
            start_date = paid_salaries[1].final_payment_date
    
    # Если нет предыдущих выплат, используем дату создания первого класса учителя
    if start_date is None:
        first_class = Class.objects.filter(teacher=teacher).order_by('created_at').first()
        if first_class:
            start_date = first_class.created_at.date()
        else:
            # Если нет классов, используем первый день текущего месяца
            start_date = first_day
    
    # Если нет конечной даты (нет выплат), используем текущую дату
    if end_date is None:
        end_date = current_date
    
    # Получаем или создаем запись о зарплате
    salary, created = TeacherSalary.get_or_create_salary(teacher, first_day)
    
    # Получаем подтвержденные посещения для классов учителя за указанный период
    from attendance.models import Attendance
    
    attendances = Attendance.objects.filter(
        class_schedule__class_obj__teacher=teacher,
        date__gte=start_date,
        date__lte=end_date,
        reception_confirmed=True
    ).select_related('class_schedule__class_obj')
    
    # Формируем данные о зарплате
    salary_data = {
        'total': salary.amount,
        'is_paid': salary.payment_status == 'paid',
        'payment_status': salary.payment_status,  # Добавляем поле payment_status
        'paid_date': salary.final_payment_date,
        'lessons_count': salary.lessons_count,
        'period_start': start_date,
        'period_end': end_date,
        'advance_amount': salary.advance_amount,
        'advance_paid_date': salary.advance_paid_date,
        'paid_amount': salary.paid_amount,
        'remaining_amount': salary.remaining_amount
    }
    
    # Получаем список всех месяцев с зарплатами для навигации
    salary_months = TeacherSalary.objects.filter(teacher=teacher).values_list('month', flat=True).distinct().order_by('-month')
    
    # Добавляем текущий месяц, если его нет в списке
    if first_day not in salary_months:
        salary_months = list(salary_months)
        salary_months.append(first_day)
        salary_months.sort(reverse=True)
    
    # Получаем список активных классов учителя за период
    active_classes = Class.objects.filter(
        teacher=teacher,
        attendances__date__gte=start_date,
        attendances__date__lte=end_date,
        attendances__reception_confirmed=True
    ).distinct()

    # Формируем контекст для шаблона
    total_paid = salary.amount if salary.payment_status == 'paid' else 0
    context = {
        'teacher': teacher,
        'salary_data': salary_data,
        'current_month': first_day,
        'classes': active_classes,
        'salary_months': salary_months,
        'attendances_count': attendances.count(),
        'is_current_month': first_day.month == current_date.month and first_day.year == current_date.year,
        'amount_to_pay': round(salary.amount - total_paid, 2),
        'period_start': start_date,
        'period_end': end_date
    }
    
    return render(request, 'finance/teacher_salary.html', context)

@login_required
def teacher_salary_overall(request):
    """Отображает общую информацию о зарплате учителя за все время."""
    
    if not request.user.is_teacher and not request.user.is_admin and not request.user.is_reception:
        return HttpResponseForbidden("Эта страница доступна только учителям, администраторам и ресепшн.")
    
    from .models import TeacherSalary
    from accounts.models import Teacher
    from attendance.models import Attendance
    
    # Определяем учителя
    if request.user.is_teacher:
        teacher = get_object_or_404(Teacher, user=request.user)
    else:
        # Для админа и ресепшн - получаем ID учителя из параметров запроса
        teacher_id = request.GET.get('teacher_id')
        if teacher_id:
            teacher = get_object_or_404(Teacher, id=teacher_id)
        else:
            # Если ID не указан, перенаправляем на список учителей
            messages.info(request, "Пожалуйста, выберите учителя для просмотра зарплаты.")
            return redirect('accounts:teacher_list')
    
    # Получаем все зарплаты учителя
    salaries = TeacherSalary.objects.filter(teacher=teacher).order_by('-month')
    
    # Разделяем на выплаченные и невыплаченные
    paid_salaries = []
    unpaid_salaries = []
    
    for salary in salaries:
        # Получаем количество занятий для этого периода
        month_start = salary.month
        if month_start.month == 12:
            month_end = datetime(month_start.year + 1, 1, 1).date()
        else:
            month_end = datetime(month_start.year, month_start.month + 1, 1).date()
        
        lessons_count = Attendance.objects.filter(
            class_schedule__class_obj__teacher=teacher,
            date__gte=month_start,
            date__lt=month_end,
            reception_confirmed=True
        ).count()
        
        # Добавляем данные учителя
        if lessons_count > 0 or salary.amount > 0:
            salary_info = {
                'id': salary.id,
                'month': salary.month,
                'amount': salary.amount,
                'is_paid': salary.payment_status == 'paid',  # Для обратной совместимости
                'paid_date': salary.final_payment_date,  # Для обратной совместимости
                'lessons_count': lessons_count,
                'advance_amount': salary.advance_amount,
                'advance_paid_date': salary.advance_paid_date,
                'paid_amount': salary.paid_amount,
                'payment_status': salary.payment_status,
                'remaining_amount': salary.remaining_amount
            }
            
            if salary.payment_status == 'paid':
                paid_salaries.append(salary_info)
            else:
                unpaid_salaries.append(salary_info)
    
    # Получаем общую статистику
    total_paid = sum(salary['amount'] for salary in paid_salaries)
    total_unpaid = sum(salary['amount'] for salary in unpaid_salaries)
    total_amount = total_paid + total_unpaid
    
    # Получаем общее количество проведенных занятий
    attendances_count = Attendance.objects.filter(
        class_schedule__class_obj__teacher=teacher,
        reception_confirmed=True
    ).count()
    
    # Формируем контекст для шаблона
    context = {
        'teacher': teacher,
        'paid_salaries': paid_salaries,
        'unpaid_salaries': unpaid_salaries,
        'total_paid': total_paid,
        'amount_to_pay': total_unpaid,
        'total_amount': total_amount,
        'attendances_count': attendances_count
    }
    
    return render(request, 'finance/teacher_salary_overall.html', context)

@login_required
def admin_salary_summary(request):
    """Отображает сводную информацию о зарплатах всех учителей для администратора."""
    
    if not request.user.is_admin and not request.user.is_reception:
        return HttpResponseForbidden("Эта страница доступна только администраторам и ресепшн.")
    
    from .models import TeacherSalary
    from accounts.models import Teacher
    from attendance.models import Attendance
    
    # Определяем месяц и год для отображения
    current_date = timezone.now().date()
    month = int(request.GET.get('month', current_date.month))
    year = int(request.GET.get('year', current_date.year))
    
    # Создаем дату первого дня месяца
    first_day = datetime(year=year, month=month, day=1).date()
    
    # Определяем последний день месяца
    if month == 12:
        last_day = datetime(year=year + 1, month=1, day=1).date()
    else:
        last_day = datetime(year=year, month=month + 1, day=1).date()
    
    # Получаем всех учителей
    teachers = Teacher.objects.all()
    
    # Собираем данные о зарплатах учителей
    teachers_data = []
    total_salary = 0
    
    for teacher in teachers:
        # Получаем или создаем запись о зарплате
        salary, created = TeacherSalary.get_or_create_salary(teacher, first_day)
        
        # Используем метод calculate_teacher_salary для получения полной информации о зарплате
        # Этот метод учитывает как уроки по расписанию, так и уроки не по расписанию
        salary_data = TeacherSalary.calculate_teacher_salary(teacher, first_day)
        recalculated_salary_amount = salary_data['total']
        attendances_count = salary_data['lessons_count']
        
        # Обновляем запись о зарплате, если рассчитанная сумма отличается от сохраненной
        if abs(recalculated_salary_amount - salary.amount) > 0.01:  # Допускаем небольшую погрешность из-за округления
            salary.amount = recalculated_salary_amount
            salary.lessons_count = attendances_count
            salary.save(update_fields=['amount', 'lessons_count'])
        
        # Добавляем данные учителя
        if attendances_count > 0 or recalculated_salary_amount > 0:
            # Используем пересчитанную сумму
            # Получаем выплаченную сумму (аванс или полная выплата)
            # Если paid_amount существует и больше 0, используем его, иначе используем advance_amount
            paid_amount = salary.paid_amount if hasattr(salary, 'paid_amount') and salary.paid_amount and salary.paid_amount > 0 else salary.advance_amount
            
            # Рассчитываем реальный остаток к выплате
            real_balance = recalculated_salary_amount - paid_amount
            if real_balance < 0.01:  # Если остаток меньше погрешности, считаем его нулевым
                real_balance = Decimal('0.00')
            
            # Получаем статус оплаты
            payment_status = salary.payment_status
            
            # Проверяем и корректируем статус оплаты на основе фактических данных
            if abs(paid_amount - recalculated_salary_amount) < 0.01:  # Если выплачено полностью
                payment_status = 'paid'
            elif paid_amount > 0:  # Если выплачено частично
                payment_status = 'partially_paid'
            else:  # Если не выплачено
                payment_status = 'unpaid'
            
            # Если статус изменился, обновляем его в базе данных
            if payment_status != salary.payment_status:
                salary.payment_status = payment_status
                salary.save(update_fields=['payment_status'])
            
            teachers_data.append({
                'teacher': teacher,
                'amount': round(recalculated_salary_amount, 2),
                'is_paid': payment_status == 'paid',  # Для обратной совместимости
                'paid_date': getattr(salary, 'final_payment_date', None),
                'advance_amount': salary.advance_amount,
                'advance_date': getattr(salary, 'advance_paid_date', None),
                'paid_amount': paid_amount,  # Добавляем выплаченную сумму
                'balance': real_balance,  # Используем рассчитанный остаток
                'payment_status': payment_status,  # Добавляем статус оплаты
                'attendances_count': attendances_count
            })
        
        total_salary += recalculated_salary_amount
    
    # Сортируем учителей по сумме зарплаты (от большей к меньшей)
    teachers_data.sort(key=lambda x: x['amount'], reverse=True)
    
    # Формируем контекст для шаблона
    total_advances = sum(teacher_data['advance_amount'] for teacher_data in teachers_data)
    
    # Рассчитываем сумму к выплате (учитывая авансы)
    amount_to_pay = sum(teacher_data['balance'] for teacher_data in teachers_data 
                      if teacher_data['payment_status'] != 'paid')
    
    # Общая сумма зарплат
    total_salary = sum(teacher_data['amount'] for teacher_data in teachers_data)
    
    # Фактически выплачено (авансы + полные выплаты)
    total_paid = sum(teacher_data['paid_amount'] for teacher_data in teachers_data)
    
    # Проверяем, является ли текущий месяц выбранным
    is_current_month = (first_day.month == current_date.month and first_day.year == current_date.year)
    
    context = {
        'teachers_data': teachers_data,
        'total_salary': round(total_salary, 2),
        'total_advances': round(total_advances, 2),
        'total_paid': round(total_paid, 2),
        'current_month': first_day,
        'is_current_month': is_current_month,
        'amount_to_pay': round(amount_to_pay, 2),
    }
    
    return render(request, 'finance/admin_salary_summary.html', context)

@login_required
def mark_salary_paid(request, teacher_id, year, month):
    """
    Отмечает зарплату учителя как выплаченную.
    Учитывает как уроки по расписанию, так и уроки не по расписанию.
    """
    if not request.user.is_admin and not request.user.is_reception:
        messages.error(request, "У вас нет прав для выполнения этого действия")
        return redirect('finance:teacher_salary_overall')
    
    try:
        teacher = Teacher.objects.get(id=teacher_id)
    except Teacher.DoesNotExist:
        messages.error(request, "Преподаватель не найден")
        return redirect('finance:teacher_salary_overall')
    
    # Получаем первый день месяца
    first_day = datetime(year=int(year), month=int(month), day=1).date()
    
    # Проверяем, есть ли уже запись о зарплате
    try:
        salary = TeacherSalary.objects.get(
            teacher=teacher,
            month=first_day
        )
        if salary.payment_status == 'paid':
            messages.info(request, f"Зарплата {teacher.full_name} за {first_day.strftime('%B %Y')} уже отмечена как выплаченная")
            return redirect('finance:teacher_salary', year=year, month=month)
    except TeacherSalary.DoesNotExist:
        # Если записи нет, создаем новую
        salary = TeacherSalary(teacher=teacher, month=first_day, amount=0, lessons_count=0)
    
    # Используем обновленный метод расчета зарплаты, который учитывает уроки не по расписанию
    salary_data = TeacherSalary.calculate_teacher_salary(teacher, first_day)
    
    # Обновляем данные о зарплате
    salary.amount = salary_data['total']
    salary.lessons_count = salary_data['lessons_count']
    salary.payment_status = 'paid'  # Обновляем статус оплаты на "оплачено полностью"
    salary.final_payment_date = datetime.now().date()
    salary.payment_confirmed_by = request.user
    salary.paid_amount = salary_data['total']  # Устанавливаем выплаченную сумму равной общей сумме
    salary.save()
    
    # В данной реализации мы не создаем транзакцию, так как модель Transaction предназначена только для студентов
    # Вместо этого мы просто обновляем запись о зарплате, что уже сделано выше
    
    messages.success(request, f"Зарплата {teacher.full_name} за {first_day.strftime('%B %Y')} отмечена как выплаченная")
    
    # Определяем, откуда был сделан запрос
    referer = request.META.get('HTTP_REFERER', '')
    if 'teacher_salary_overall' in referer:
        return redirect('finance:teacher_salary_overall')
    elif 'admin_salary_summary' in referer:
        return redirect('finance:admin_salary_summary', year=year, month=month)
    else:
        return redirect('finance:teacher_salary', year=year, month=month)


@login_required
def pay_salary_advance(request, teacher_id, year, month):
    """
    Выплачивает аванс учителю.
    """
    if not request.user.is_admin and not request.user.is_reception:
        messages.error(request, "У вас нет прав для выполнения этого действия")
        return redirect('finance:teacher_salary_overall')
    
    if request.method != 'POST':
        messages.error(request, "Неверный метод запроса")
        return redirect('finance:teacher_salary')
    
    try:
        teacher = Teacher.objects.get(id=teacher_id)
        first_day = datetime(year=int(year), month=int(month), day=1).date()
        
        # Получаем или создаем запись о зарплате
        try:
            salary = TeacherSalary.objects.get(teacher=teacher, month=first_day)
            if salary.payment_status == 'paid':
                messages.error(request, f"Зарплата {teacher.full_name} за {first_day.strftime('%B %Y')} уже выплачена полностью")
                return redirect('finance:teacher_salary')
        except TeacherSalary.DoesNotExist:
            # Если записи нет, создаем новую используя метод calculate_teacher_salary
            # Этот метод учитывает как уроки по расписанию, так и уроки не по расписанию
            salary_data = TeacherSalary.calculate_teacher_salary(teacher, first_day)
            
            salary = TeacherSalary(
                teacher=teacher, 
                month=first_day, 
                amount=salary_data['total'], 
                lessons_count=salary_data['lessons_count']
            )
        
        # Получаем сумму аванса из формы
        try:
            advance_amount = Decimal(request.POST.get('advance_amount', 0))
            if advance_amount <= 0:
                messages.error(request, "Сумма аванса должна быть положительным числом")
                return redirect('finance:teacher_salary')
        except (ValueError, InvalidOperation):
            messages.error(request, "Неверный формат суммы аванса")
            return redirect('finance:teacher_salary')
        
        # Обновляем данные о зарплате
        salary.advance_amount = advance_amount
        salary.advance_paid_date = datetime.now().date()  # Используем новое поле для даты аванса
        salary.advance_confirmed_by = request.user
        
        # Устанавливаем выплаченную сумму равной авансу
        # Это поле используется для отображения фактически выплаченной суммы в сводке зарплат
        salary.paid_amount = advance_amount
        
        # Проверяем, равен ли аванс полной сумме зарплаты
        if abs(advance_amount - salary.amount) < 0.01:  # Если аванс равен полной сумме (с учетом погрешности)
            salary.payment_status = 'paid'  # Оплачено полностью
            salary.final_payment_date = datetime.now().date()  # Устанавливаем дату полной выплаты
            salary.payment_confirmed_by = request.user
        elif advance_amount > 0:
            salary.payment_status = 'partially_paid'  # Оплачено частично
        
        salary.save()
        
        # Создаем транзакцию для аванса
        # Поскольку в модели Transaction нет поля teacher, мы не можем создать транзакцию для учителя
        # Вместо этого мы просто обновляем запись о зарплате
        
        messages.success(request, f"Аванс {teacher.full_name} за {first_day.strftime('%B %Y')} в размере {advance_amount} ₸ выплачен")
        
        # Перенаправляем на соответствующую страницу
        if request.user.is_teacher and request.user.teacher.id == teacher_id:
            return redirect('finance:teacher_salary')
        else:
            return redirect('finance:admin_salary_summary')
            
    except Teacher.DoesNotExist:
        messages.error(request, "Преподаватель не найден")
        return redirect('finance:admin_salary_summary')
    except Exception as e:
        messages.error(request, f"Произошла ошибка: {str(e)}")
        if request.user.is_teacher and request.user.teacher.id == teacher_id:
            return redirect('finance:teacher_salary')
        else:
            return redirect('finance:admin_salary_summary')
    



@login_required
def teacher_salary_detail(request, teacher_id, year, month):
    """Отображает детальную информацию о зарплате учителя за указанный месяц."""
    
    if not request.user.is_admin and not request.user.is_reception:
        return HttpResponseForbidden("Эта страница доступна только администраторам и ресепшн.")
    
    from .models import TeacherSalary
    from accounts.models import Teacher
    from attendance.models import Attendance
    from classes.models import ClassSchedule, Class
    from django.db.models import Count, Sum, F
    from django.utils import timezone
    
    teacher = get_object_or_404(Teacher, id=teacher_id)
    first_day = datetime(int(year), int(month), 1).date()
    
    # Определяем последний день месяца
    if int(month) == 12:
        last_day = datetime(int(year) + 1, 1, 1).date()
    else:
        last_day = datetime(int(year), int(month) + 1, 1).date()
    
    # Получаем или создаем запись о зарплате
    salary, created = TeacherSalary.get_or_create_salary(teacher, first_day)
    
    # Пересчитываем зарплату на основе фактических посещений
    # Используем обновленный метод, который учитывает уроки не по расписанию
    recalculated_salary = TeacherSalary.calculate_teacher_salary(teacher, first_day)
    
    # Получаем все посещения со статусом 'present' для классов учителя за указанный месяц
    attendances = Attendance.objects.filter(
        class_schedule__class_obj__teacher=teacher,
        date__gte=first_day,
        date__lt=last_day,
        status='present'
    ).select_related('class_schedule', 'class_schedule__class_obj')
    
    # Получаем все посещения для уроков не по расписанию
    from classes.models import NonScheduledLesson, NonScheduledLessonAttendance
    non_scheduled_attendances = NonScheduledLessonAttendance.objects.filter(
        lesson__teacher=teacher,
        lesson__date__gte=first_day,
        lesson__date__lt=last_day,
        is_present=True
    ).select_related('lesson', 'student')
    
    # Используем рассчитанную зарплату для получения детальной информации
    salary_details = recalculated_salary
    
    # Группируем посещения по датам и классам
    # Сначала группируем посещения по уникальным комбинациям даты, класса и расписания
    unique_classes = {}
    for attendance in attendances:
        # Создаем уникальный ключ для каждой комбинации даты, класса и расписания
        key = (attendance.date, attendance.class_schedule.class_obj.id, attendance.class_schedule.id)
        if key not in unique_classes:
            unique_classes[key] = {
                'date': attendance.date,
                'class_obj': attendance.class_schedule.class_obj,
                'class_schedule': attendance.class_schedule,
                'is_scheduled': True
            }
    
    # Добавляем уроки не по расписанию
    # Группируем по уникальным урокам не по расписанию
    non_scheduled_lessons = {}
    for attendance in non_scheduled_attendances:
        lesson = attendance.lesson
        key = (lesson.date, f'non_scheduled_{lesson.id}')
        
        if key not in non_scheduled_lessons:
            non_scheduled_lessons[key] = {
                'date': lesson.date,
                'lesson': lesson,
                'students': [],
                'is_scheduled': False
            }
        
        # Добавляем студента в список присутствующих
        non_scheduled_lessons[key]['students'].append(attendance.student)
    
    # Добавляем уроки не по расписанию в общий список
    for key, data in non_scheduled_lessons.items():
        lesson = data['lesson']
        unique_key = (data['date'], f'non_scheduled_{lesson.id}', lesson.id)
        
        if unique_key not in unique_classes:
            unique_classes[unique_key] = {
                'date': data['date'],
                'non_scheduled_lesson': lesson,
                'students_count': len(data['students']),
                'is_scheduled': False
            }
    
    # Теперь группируем по датам
    attendance_by_date = {}
    for key, data in unique_classes.items():
        date_str = data['date'].strftime('%Y-%m-%d')
        
        if date_str not in attendance_by_date:
            attendance_by_date[date_str] = {
                'date': data['date'],
                'day_of_week': data['date'].strftime('%A'),  # День недели
                'classes': [],
                'total_amount': Decimal('0')
            }
        
        # Обрабатываем уроки по расписанию
        if data.get('is_scheduled', True):
            class_obj = data['class_obj']
            class_schedule = data['class_schedule']
            
            # Определяем сумму за занятие используя вспомогательный метод
            amount = TeacherSalary.calculate_lesson_payment(class_obj)
            
            # Добавляем информацию о классе
            attendance_by_date[date_str]['classes'].append({
                'class_name': class_obj.name,
                'time': f"{class_schedule.start_time.strftime('%H:%M')} - {class_schedule.end_time.strftime('%H:%M')}",
                'amount': amount,
                'is_scheduled': True
            })
            
            # Увеличиваем общую сумму за день
            attendance_by_date[date_str]['total_amount'] += amount
        
        # Обрабатываем уроки не по расписанию
        else:
            lesson = data['non_scheduled_lesson']
            students_count = data['students_count']
            
            # Определяем сумму за урок не по расписанию
            # Сумма зависит от количества присутствующих студентов
            amount = lesson.teacher_payment
            
            # Добавляем информацию о уроке не по расписанию
            # Используем поле name вместо subject, и поле time вместо start_time/end_time
            end_time = (timezone.datetime.combine(timezone.datetime.today(), lesson.time) + 
                       timezone.timedelta(minutes=lesson.duration)).time()
            
            attendance_by_date[date_str]['classes'].append({
                'class_name': f"{lesson.name} (Вне расписания)",
                'time': f"{lesson.time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}",
                'amount': amount,
                'students_count': students_count,
                'is_scheduled': False
            })
            
            # Увеличиваем общую сумму за день
            attendance_by_date[date_str]['total_amount'] += amount
    
    # Сортируем дни по дате
    attendance_days = sorted(attendance_by_date.values(), key=lambda x: x['date'])
    
    # Получаем классы учителя
    teacher_classes = Class.objects.filter(teacher=teacher)
    
    # Статистика по классам из рассчитанной зарплаты
    class_stats = []
    for class_id, data in salary_details.get('class_earnings', {}).items():
        # Проверяем, является ли class_id строкой, начинающейся с 'non_scheduled_lesson_'
        if isinstance(class_id, str) and class_id.startswith('non_scheduled_lesson_'):
            # Это урок не по расписанию, добавляем его в статистику
            class_stats.append({
                'class_name': data.get('name', 'Урок вне расписания'),
                'attendances_count': data.get('lessons_conducted', 0),
                'amount_per_lesson': data.get('amount_earned', Decimal('0')) / data.get('lessons_conducted', 1) if data.get('lessons_conducted', 0) > 0 else Decimal('0'),
                'total_amount': data.get('amount_earned', Decimal('0')),
                'is_scheduled': False
            })
        else:
            # Пытаемся преобразовать class_id в целое число
            try:
                class_id_int = int(class_id)
                class_obj = next((c for c in teacher_classes if c.id == class_id_int), None)
                if class_obj:
                    class_stats.append({
                        'class_name': data.get('name', class_obj.name),
                        'attendances_count': data.get('lessons_conducted', 0),
                        'amount_per_lesson': TeacherSalary.calculate_lesson_payment(class_obj),
                        'total_amount': data.get('amount_earned', Decimal('0')),
                        'is_scheduled': True
                    })
            except (ValueError, TypeError):
                # Если не удалось преобразовать в целое число, пропускаем этот класс
                pass
    
    # Используем общую сумму из рассчитанной зарплаты
    total_amount = salary_details.get('total', Decimal('0'))
    
    # Проверяем, совпадает ли рассчитанная сумма с суммой в модели
    if abs(total_amount - salary.amount) > 0.01:  # Допускаем небольшую погрешность из-за округления
        # Если есть расхождение, обновляем сумму в модели
        salary.amount = total_amount
        salary.lessons_count = salary_details.get('lessons_count', attendances.count())
        salary.save(update_fields=['amount', 'lessons_count'])
        
        # Добавляем сообщение для администраторов
        if request.user.is_admin or request.user.is_reception:
            messages.info(request, f"Зарплата учителя была обновлена на основе фактических посещений.")
    
    context = {
        'teacher': teacher,
        'salary': salary,
        'attendance_days': attendance_days,
        'class_stats': class_stats,
        'current_month': first_day,
        'total_days': len(attendance_days),
        'total_lessons': salary_details.get('lessons_count', attendances.count()),
        'total_amount': total_amount  # Используем сумму, рассчитанную на основе фактических посещений
    }
    
    return render(request, 'finance/teacher_salary_detail.html', context)

@login_required
def export_transactions_excel(request):
    """Экспортирует транзакции в Excel файл."""
    
    # Получаем параметры фильтрации из запроса
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    student_id = request.GET.get('student')
    class_id = request.GET.get('class_obj')
    transaction_type = request.GET.get('transaction_type')
    period = request.GET.get('period')
    
    # Получаем текущую дату
    today = timezone.now().date()
    
    # Определяем даты начала и конца в зависимости от выбранного периода
    if not start_date and period:
        if period == 'current_month':
            # Текущий месяц
            start_date = today.replace(day=1)
            # Последний день текущего месяца
            if today.month == 12:
                end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        elif period == 'previous_month':
            # Прошлый месяц
            if today.month == 1:
                start_date = today.replace(year=today.year - 1, month=12, day=1)
                end_date = today.replace(day=1) - timedelta(days=1)
            else:
                start_date = today.replace(month=today.month - 1, day=1)
                end_date = today.replace(day=1) - timedelta(days=1)
        elif period == 'last_3_months':
            # Последние 3 месяца
            start_date = (today - timedelta(days=90)).replace(day=1)
            end_date = today
        elif period == 'last_year':
            # Последний год
            start_date = today.replace(year=today.year - 1)
            end_date = today
        else:
            # По умолчанию - текущий месяц
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    else:
        # Если даты указаны в запросе, преобразуем их из строк в объекты datetime
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError:
                start_date = today.replace(day=1)
        else:
            start_date = today.replace(day=1)
        
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                end_date = today
        else:
            end_date = today
    
    # Формируем имя файла с датой и временем для уникальности
    current_time = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f"transactions_{start_date}_to_{end_date}_{current_time}"
    
    # Создаем HTTP-ответ с правильным типом содержимого для Excel
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = f'attachment; filename="{filename}.xls"'
    
    # Фильтруем транзакции в зависимости от роли пользователя
    if request.user.is_admin or request.user.is_reception:
        # Администраторы и ресепшн видят все транзакции
        transactions = Transaction.objects.filter(
            date__range=[start_date, end_date]
        ).select_related('student', 'class_obj')
    elif request.user.is_teacher:
        # Учителя видят только транзакции своих студентов
        teacher = Teacher.objects.get(user=request.user)
        transactions = Transaction.objects.filter(
            date__range=[start_date, end_date],
            student__in=Student.objects.filter(classes__teacher=teacher).distinct()
        ).select_related('student', 'class_obj')
    else:
        # Студенты видят только свои транзакции
        student = Student.objects.get(user=request.user)
        transactions = Transaction.objects.filter(
            date__range=[start_date, end_date],
            student=student
        ).select_related('student', 'class_obj')
    
    # Применяем дополнительные фильтры
    if student_id:
        transactions = transactions.filter(student_id=student_id)
    
    if class_id:
        transactions = transactions.filter(class_obj_id=class_id)
    
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    
    # Сортируем транзакции по дате (сначала новые)
    transactions = transactions.order_by('-date')
    
    # Создаем новую книгу Excel
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('Транзакции')
    
    # Настраиваем ширину столбцов
    ws.col(0).width = 256 * 15  # Дата
    ws.col(1).width = 256 * 30  # Студент
    ws.col(2).width = 256 * 15  # Сумма
    ws.col(3).width = 256 * 15  # Тип
    ws.col(4).width = 256 * 20  # Класс
    ws.col(5).width = 256 * 50  # Описание
    
    # Стили для заголовков
    header_style = xlwt.XFStyle()
    header_style.font.bold = True
    header_style.pattern.pattern = xlwt.Pattern.SOLID_PATTERN
    header_style.pattern.pattern_fore_colour = xlwt.Style.colour_map['light_blue']
    header_style.alignment.horz = xlwt.Alignment.HORZ_CENTER
    header_style.borders.left = xlwt.Borders.THIN
    header_style.borders.right = xlwt.Borders.THIN
    header_style.borders.top = xlwt.Borders.THIN
    header_style.borders.bottom = xlwt.Borders.THIN
    
    # Стиль для данных
    data_style = xlwt.XFStyle()
    data_style.borders.left = xlwt.Borders.THIN
    data_style.borders.right = xlwt.Borders.THIN
    data_style.borders.top = xlwt.Borders.THIN
    data_style.borders.bottom = xlwt.Borders.THIN
    
    # Стиль для денежных значений
    money_style = xlwt.XFStyle()
    money_style.borders.left = xlwt.Borders.THIN
    money_style.borders.right = xlwt.Borders.THIN
    money_style.borders.top = xlwt.Borders.THIN
    money_style.borders.bottom = xlwt.Borders.THIN
    money_style.alignment.horz = xlwt.Alignment.HORZ_RIGHT
    
    # Стиль для оплат (отрицательные значения)
    payment_style = xlwt.XFStyle()
    payment_style.borders.left = xlwt.Borders.THIN
    payment_style.borders.right = xlwt.Borders.THIN
    payment_style.borders.top = xlwt.Borders.THIN
    payment_style.borders.bottom = xlwt.Borders.THIN
    payment_style.alignment.horz = xlwt.Alignment.HORZ_RIGHT
    payment_style.font.colour_index = xlwt.Style.colour_map['red']
    
    # Стиль для пополнений (положительные значения)
    deposit_style = xlwt.XFStyle()
    deposit_style.borders.left = xlwt.Borders.THIN
    deposit_style.borders.right = xlwt.Borders.THIN
    deposit_style.borders.top = xlwt.Borders.THIN
    deposit_style.borders.bottom = xlwt.Borders.THIN
    deposit_style.alignment.horz = xlwt.Alignment.HORZ_RIGHT
    deposit_style.font.colour_index = xlwt.Style.colour_map['green']
    
    # Стиль для итоговой информации
    summary_style = xlwt.XFStyle()
    summary_style.font.bold = True
    summary_style.pattern.pattern = xlwt.Pattern.SOLID_PATTERN
    summary_style.pattern.pattern_fore_colour = xlwt.Style.colour_map['light_yellow']
    
    # Стиль для заголовка отчета
    title_style = xlwt.XFStyle()
    title_style.font.bold = True
    title_style.font.height = 400  # Увеличенный размер шрифта
    title_style.alignment.horz = xlwt.Alignment.HORZ_CENTER
    
    # Добавляем заголовок отчета
    ws.write_merge(0, 0, 0, 5, f"Отчет по транзакциям за период {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}", title_style)
    
    # Добавляем информацию о пользователе и дате формирования отчета
    ws.write_merge(1, 1, 0, 5, f"Сформировано: {timezone.now().strftime('%d.%m.%Y %H:%M:%S')} пользователем {request.user.get_full_name() or request.user.username}", data_style)
    
    # Пропускаем строку для разделения заголовка и данных
    row_num = 3
    
    # Заголовки столбцов
    columns = ['Дата', 'Студент', 'Сумма', 'Тип', 'Класс', 'Описание']
    
    # Записываем заголовки столбцов
    for col_num, column_title in enumerate(columns):
        ws.write(row_num, col_num, column_title, header_style)
    
    # Записываем данные
    row_num += 1
    for transaction in transactions:
        # Форматируем дату
        date_str = transaction.date.strftime('%d.%m.%Y')
        
        # Определяем тип транзакции на русском
        if transaction.transaction_type == 'payment':
            type_str = 'Оплата'
            amount_style = payment_style
            amount_str = f"-{transaction.amount} ₸"
        elif transaction.transaction_type == 'deposit':
            type_str = 'Пополнение'
            amount_style = deposit_style
            amount_str = f"{transaction.amount} ₸"
        elif transaction.transaction_type == 'refund':
            type_str = 'Возврат'
            amount_style = deposit_style
            amount_str = f"{transaction.amount} ₸"
        else:
            type_str = transaction.transaction_type
            amount_style = money_style
            amount_str = f"{transaction.amount} ₸"
        
        # Записываем данные в ячейки с соответствующими стилями
        ws.write(row_num, 0, date_str, data_style)
        ws.write(row_num, 1, transaction.student.full_name if transaction.student else '', data_style)
        ws.write(row_num, 2, amount_str, amount_style)
        ws.write(row_num, 3, type_str, data_style)
        ws.write(row_num, 4, transaction.class_obj.name if transaction.class_obj else '', data_style)
        ws.write(row_num, 5, transaction.description, data_style)
        
        row_num += 1
    
    # Добавляем сводную информацию
    row_num += 2  # Пропускаем строку для разделения данных и сводной информации
    
    # Заголовок сводной информации
    ws.write_merge(row_num, row_num, 0, 5, "Сводная финансовая информация", title_style)
    row_num += 1
    
    # Вычисляем общую сумму отфильтрованных транзакций
    total_amount = transactions.aggregate(
        total=Sum(Case(
            When(transaction_type='payment', then=-F('amount')),
            When(transaction_type='deposit', then=F('amount')),
            When(transaction_type='refund', then=F('amount')),
            output_field=IntegerField()
        ))
    )['total'] or 0
    
    # Доходы от уроков (сколько денег снялось на уроки)
    lesson_income = Transaction.objects.filter(
        transaction_type='payment',
        date__range=[start_date, end_date]
    )
    
    # Применяем те же фильтры, что и к основным транзакциям
    if student_id:
        lesson_income = lesson_income.filter(student_id=student_id)
    
    if class_id:
        lesson_income = lesson_income.filter(class_obj_id=class_id)
    
    lesson_income = lesson_income.aggregate(total=Sum('amount'))['total'] or 0
    lesson_income = round(lesson_income, 2)
    
    # Выплаты учителям
    teacher_payments = TeacherSalary.objects.filter(
        payment_status='paid',
        final_payment_date__range=[start_date, end_date]
    ).aggregate(total=Sum('amount'))['total'] or 0
    teacher_payments = round(teacher_payments, 2)
    
    # Предконечный доход (доходы от уроков - выплаты учителям)
    pre_final_income = lesson_income - teacher_payments
    pre_final_income = round(pre_final_income, 2)
    
    # Общий баланс учеников
    if student_id:
        total_student_balance = Student.objects.filter(id=student_id).aggregate(total=Sum('balance'))['total'] or 0
    else:
        total_student_balance = Student.objects.aggregate(total=Sum('balance'))['total'] or 0
    
    # Записываем сводную информацию с красивым форматированием
    summary_items = [
        ('Общий баланс учеников:', f"{total_student_balance} ₸"),
        ('Доходы от уроков:', f"{lesson_income} ₸"),
        ('Выплаты учителям:', f"{teacher_payments} ₸"),
        ('Предконечный доход:', f"{pre_final_income} ₸")
    ]
    
    for item in summary_items:
        ws.write(row_num, 0, item[0], summary_style)
        ws.write(row_num, 1, item[1], summary_style)
        row_num += 1
    
    # Добавляем информацию о фильтрах
    row_num += 2
    ws.write(row_num, 0, "Примененные фильтры:", data_style)
    row_num += 1
    
    filters_info = []
    if student_id:
        student = Student.objects.filter(id=student_id).first()
        if student:
            filters_info.append(f"Студент: {student.full_name}")
    
    if class_id:
        class_obj = Class.objects.filter(id=class_id).first()
        if class_obj:
            filters_info.append(f"Класс: {class_obj.name}")
    
    if transaction_type:
        type_mapping = {
            'payment': 'Оплата',
            'deposit': 'Пополнение',
            'refund': 'Возврат'
        }
        filters_info.append(f"Тип транзакции: {type_mapping.get(transaction_type, transaction_type)}")
    
    if not filters_info:
        filters_info.append("Без дополнительных фильтров")
    
    for info in filters_info:
        ws.write(row_num, 0, info, data_style)
        row_num += 1
    
    # Сохраняем Excel файл
    try:
        wb.save(response)
        return response
    except Exception as e:
        # В случае ошибки при сохранении файла, возвращаем сообщение об ошибке
        messages.error(request, f"Ошибка при экспорте данных: {str(e)}")
        return redirect('finance:transaction_list')
