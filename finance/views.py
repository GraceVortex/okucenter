from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, F, Q, Case, When, IntegerField
from datetime import datetime, timedelta
from .models import Transaction, TeacherSalary
from .forms import TransactionForm, TransactionFilterForm, DepositForm
from accounts.models import Student, User, Teacher
from classes.models import Class
from attendance.models import Attendance

# Create your views here.

@login_required
def transaction_list(request):
    """Отображает список транзакций для текущего пользователя."""
    
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
        start_date = today.replace(year=today.year - 1)
        end_date = today
    else:
        # По умолчанию - текущий месяц
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    
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
        parent_students = request.user.parent_profile.students.all()
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
        teacher_salaries = TeacherSalary.objects.filter(
            is_paid=True,
            paid_date__range=[start_date, end_date]
        ).select_related('teacher')
    else:
        teacher_salaries = TeacherSalary.objects.none()
    
    # 1. Общий баланс (сумма всех текущих балансов учеников)
    total_student_balance = Student.objects.aggregate(total=Sum('balance'))['total'] or 0
    total_student_balance = round(total_student_balance, 2)
    
    # 2. Доходы от уроков (сколько денег снялось на уроки)
    lesson_income = Transaction.objects.filter(
        transaction_type='payment',
        date__range=[start_date, end_date]
    ).aggregate(total=Sum('amount'))['total'] or 0
    lesson_income = round(lesson_income, 2)
    
    # 3. Выплаты учителям
    teacher_payments = TeacherSalary.objects.filter(
        is_paid=True,
        paid_date__range=[start_date, end_date]
    ).aggregate(total=Sum('amount'))['total'] or 0
    teacher_payments = round(teacher_payments, 2)
    
    # 4. Предконечный доход (доходы от уроков - выплаты учителям)
    pre_final_income = lesson_income - teacher_payments
    pre_final_income = round(pre_final_income, 2)
    
    context = {
        'transactions': transactions,
        'teacher_salaries': teacher_salaries,
        'form': form,
        'students': students,
        'classes': classes,
        'total_amount': round(total_amount, 2),
        'selected_student': selected_student,
        'selected_class': selected_class,
        'transaction_type': transaction_type,
        'start_date': start_date,
        'end_date': end_date,
        'period': period,
        # Сводная финансовая информация
        'total_student_balance': total_student_balance,
        'lesson_income': lesson_income,
        'teacher_payments': teacher_payments,
        'pre_final_income': pre_final_income
    }
    
    return render(request, 'finance/transaction_list.html', context)

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
    
    # Ученики не могут видеть баланс
    if request.user.is_student:
        return HttpResponseForbidden("У вас нет доступа к этой странице.")
    
    # Определяем, чей баланс показывать
    if student_id:
        # Проверка доступа
        if request.user.is_admin or request.user.is_reception or request.user.is_teacher:
            student = get_object_or_404(Student, id=student_id)
        elif request.user.is_parent:
            # Проверяем, является ли запрашиваемый студент ребенком этого родителя
            student = get_object_or_404(Student, id=student_id, parent=request.user.parent_profile)
        else:
            return HttpResponseForbidden("У вас нет доступа к этой странице.")
    else:
        # Если student_id не указан, показываем баланс для родителя
        if request.user.is_parent and request.user.parent_profile.students.exists():
            # Для родителя показываем первого ребенка (можно улучшить)
            student = request.user.parent_profile.students.first()
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
    
    context = {
        'student': student,
        'transactions': transactions,
        'balance': student.balance,
        'total_deposits': round(total_deposits, 2),
        'total_payments': round(total_payments, 2),
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
        is_paid=True,
        paid_date__isnull=False
    ).order_by('-paid_date')
    
    # Определяем период для отображения
    start_date = None
    end_date = None
    
    if paid_salaries.exists():
        # Если есть выплаченные зарплаты, берем последнюю как конечную дату
        end_date = paid_salaries.first().paid_date
        
        # Если есть более одной выплаты, берем предпоследнюю как начальную дату
        if paid_salaries.count() > 1:
            start_date = paid_salaries[1].paid_date
    
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
        'is_paid': salary.is_paid,
        'paid_date': salary.paid_date,
        'lessons_count': salary.lessons_count,
        'period_start': start_date,
        'period_end': end_date
    }
    
    # Получаем список всех месяцев с зарплатами для навигации
    salary_months = TeacherSalary.objects.filter(teacher=teacher).values_list('month', flat=True).distinct().order_by('-month')
    
    # Добавляем текущий месяц, если его нет в списке
    if first_day not in salary_months:
        salary_months = list(salary_months)
        salary_months.append(first_day)
        salary_months.sort(reverse=True)
    
    # Формируем контекст для шаблона
    total_paid = salary.amount if salary.is_paid else 0
    context = {
        'teacher': teacher,
        'salary_data': salary_data,
        'current_month': first_day,
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
        if attendances_count > 0 or salary.amount > 0:
            salary_info = {
                'id': salary.id,
                'month': salary.month,
                'amount': salary.amount,
                'is_paid': salary.is_paid,
                'paid_date': salary.paid_date,
                'lessons_count': lessons_count
            }
            
            if salary.is_paid:
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
    first_day = datetime(year, month, 1).date()
    
    # Определяем последний день месяца
    if month == 12:
        last_day = datetime(year + 1, 1, 1).date()
    else:
        last_day = datetime(year, month + 1, 1).date()
    
    # Получаем всех учителей
    teachers = Teacher.objects.all()
    
    # Собираем данные о зарплатах учителей
    teachers_data = []
    total_salary = 0
    
    for teacher in teachers:
        # Получаем или создаем запись о зарплате
        salary, created = TeacherSalary.get_or_create_salary(teacher, first_day)
        
        # Получаем количество проведенных занятий
        attendances_count = Attendance.objects.filter(
            class_schedule__class_obj__teacher=teacher,
            date__gte=first_day,
            date__lt=last_day,
            reception_confirmed=True
        ).count()
        
        # Добавляем данные учителя
        if attendances_count > 0 or salary.amount > 0:
            teachers_data.append({
                'teacher': teacher,
                'amount': round(salary.amount, 2),
                'is_paid': salary.is_paid,
                'paid_date': salary.paid_date,
                'attendances_count': attendances_count
            })
            
            total_salary += salary.amount
    
    # Сортируем учителей по сумме зарплаты (от большей к меньшей)
    teachers_data.sort(key=lambda x: x['amount'], reverse=True)
    
    # Формируем контекст для шаблона
    total_paid = sum([teacher['amount'] for teacher in teachers_data if teacher['is_paid']])
    context = {
        'teachers_data': teachers_data,
        'total_salary': round(total_salary, 2),
        'current_month': first_day,
        'is_current_month': first_day.month == current_date.month and first_day.year == current_date.year,
        'amount_to_pay': round(total_salary - total_paid, 2),
    }
    
    return render(request, 'finance/admin_salary_summary.html', context)

@login_required
def mark_salary_paid(request, teacher_id, year, month):
    """Отмечает зарплату учителя как выплаченную."""
    
    if not request.user.is_admin and not request.user.is_reception:
        return HttpResponseForbidden("Эта операция доступна только администраторам и ресепшн.")
    
    from .models import TeacherSalary
    from accounts.models import Teacher
    from attendance.models import Attendance
    
    teacher = get_object_or_404(Teacher, id=teacher_id)
    first_day = datetime(int(year), int(month), 1).date()
    
    # Определяем последний день месяца
    if int(month) == 12:
        last_day = datetime(int(year) + 1, 1, 1).date()
    else:
        last_day = datetime(int(year), int(month) + 1, 1).date()
    
    # Получаем количество занятий для этого периода
    lessons_count = Attendance.objects.filter(
        class_schedule__class_obj__teacher=teacher,
        date__gte=first_day,
        date__lt=last_day,
        reception_confirmed=True
    ).count()
    
    # Получаем или создаем запись о зарплате
    salary, created = TeacherSalary.get_or_create_salary(teacher, first_day)
    
    # Обновляем данные
    salary.amount = salary.amount
    salary.lessons_count = lessons_count
    salary.is_paid = True
    salary.paid_date = timezone.now().date()
    salary.save()
    
    messages.success(request, f"Зарплата {teacher.full_name} за {first_day.strftime('%B %Y')} отмечена как выплаченная.")
    
    # Если это текущий месяц, сбрасываем текущую зарплату
    current_month = TeacherSalary.get_current_month()
    if first_day.month == current_month.month and first_day.year == current_month.year:
        TeacherSalary.reset_current_salary(teacher)
    
    # Возвращаемся на предыдущую страницу
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    else:
        return redirect('finance:admin_salary_summary')
