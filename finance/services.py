from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, F, Q
from django.db import transaction
from datetime import datetime, timedelta
from decimal import Decimal

from accounts.models import Student, Teacher
from attendance.models import Attendance
from classes.models import Class, ClassSchedule
from classes.non_scheduled_lesson_models import NonScheduledLesson, NonScheduledLessonAttendance
from finance.models import Transaction, TeacherSalary


class FinancialService:
    """
    Сервисный класс для работы с финансовыми данными.
    Предоставляет методы для создания транзакций, расчета зарплат и получения статистики.
    """
    
    @staticmethod
    def create_student_payment(student, amount, description, transaction_type='payment', 
                               class_obj=None, scheduled_lesson=None, non_scheduled_lesson=None, 
                               created_by=None):
        """
        Создает транзакцию оплаты для студента и обновляет его баланс.
        Также создает связь с уроком, если указан.
        """
        with transaction.atomic():
            # Обновляем баланс студента
            if transaction_type == 'payment' or transaction_type == 'deposit':
                student.balance += amount
            elif transaction_type == 'refund':
                student.balance -= amount
            student.save()
            
            # Создаем транзакцию
            new_transaction = Transaction.objects.create(
                student=student,
                amount=amount,
                date=timezone.now().date(),
                description=description,
                transaction_type=transaction_type,
                class_obj=class_obj,
                scheduled_lesson=scheduled_lesson,
                non_scheduled_lesson=non_scheduled_lesson,
                created_by=created_by
            )
            
            return new_transaction
    
    @staticmethod
    def calculate_teacher_salary(teacher, month=None):
        """
        Рассчитывает зарплату учителя за указанный месяц.
        Учитывает как уроки по расписанию, так и уроки не по расписанию.
        Создает записи о выплатах за каждый урок.
        """
        if month is None:
            month = timezone.now().date().replace(day=1)
        
        # Определяем период
        first_day = month
        if month.month == 12:
            next_month = datetime(month.year + 1, 1, 1).date()
        else:
            next_month = datetime(month.year, month.month + 1, 1).date()
        
        with transaction.atomic():
            # Получаем или создаем запись о зарплате
            salary, created = TeacherSalary.objects.get_or_create(
                teacher=teacher,
                month=first_day,
                defaults={'amount': Decimal('0.00')}
            )
            
            # Очищаем существующие записи о выплатах за уроки
            TeacherPayment.objects.filter(salary=salary).delete()
            
            total_amount = Decimal('0.00')
            lessons_count = 0
            
            # 1. Обрабатываем уроки по расписанию
            attendances = Attendance.objects.filter(
                class_schedule__class_obj__teacher=teacher,
                date__range=[first_day, next_month - timedelta(days=1)],
                status='present'
            ).select_related('class_schedule__class_obj')
            
            # Группируем по уникальным урокам
            unique_lessons = {}
            for att in attendances:
                key = (att.date, att.class_schedule_id)
                if key not in unique_lessons:
                    unique_lessons[key] = {
                        'date': att.date,
                        'class_obj': att.class_schedule.class_obj,
                        'attendance': att
                    }
            
            # Рассчитываем оплату за каждый урок по расписанию
            for key, data in unique_lessons.items():
                class_obj = data['class_obj']
                date = data['date']
                attendance = data['attendance']
                
                # Определяем сумму за занятие
                if class_obj.teacher_payment_type == 'percentage':
                    # Получаем количество студентов на уроке
                    students_count = Attendance.objects.filter(
                        class_schedule=attendance.class_schedule,
                        date=date,
                        status='present'
                    ).count()
                    
                    # Рассчитываем сумму
                    total_lesson_price = class_obj.price_per_lesson * Decimal(str(students_count))
                    percentage = Decimal(str(class_obj.teacher_percentage)) / Decimal('100')
                    amount = total_lesson_price * percentage
                else:  # fixed payment
                    amount = class_obj.teacher_fixed_payment
                
                # Создаем запись о выплате за урок
                TeacherPayment.objects.create(
                    teacher=teacher,
                    salary=salary,
                    scheduled_lesson=attendance,
                    amount=amount,
                    date=date
                )
                
                total_amount += amount
                lessons_count += 1
            
            # 2. Обрабатываем уроки не по расписанию
            non_scheduled_lessons = NonScheduledLesson.objects.filter(
                teacher=teacher,
                date__range=[first_day, next_month - timedelta(days=1)],
                is_completed=True
            )
            
            for lesson in non_scheduled_lessons:
                # Получаем количество присутствовавших студентов
                present_students = NonScheduledLessonAttendance.objects.filter(
                    lesson=lesson,
                    is_present=True
                ).count()
                
                if present_students > 0:
                    # Создаем запись о выплате за урок не по расписанию
                    TeacherPayment.objects.create(
                        teacher=teacher,
                        salary=salary,
                        non_scheduled_lesson=lesson,
                        amount=lesson.teacher_payment,
                        date=lesson.date
                    )
                    
                    total_amount += lesson.teacher_payment
                    lessons_count += 1
            
            # Обновляем данные о зарплате
            salary.amount = total_amount
            salary.lessons_count = lessons_count
            salary.save()
            
            return salary
    
    @staticmethod
    def mark_salary_paid(teacher, month, paid_by=None):
        """
        Отмечает зарплату учителя как выплаченную.
        """
        with transaction.atomic():
            # Пересчитываем зарплату, чтобы убедиться, что данные актуальны
            salary = FinancialService.calculate_teacher_salary(teacher, month)
            
            # Отмечаем зарплату как выплаченную
            salary.payment_status = 'paid'
            salary.final_payment_date = timezone.now().date()
            salary.payment_confirmed_by = paid_by
            salary.paid_amount = salary.amount
            salary.save()
            
            return salary
    

    

    
    @staticmethod
    def get_financial_dashboard(period='current_month'):
        """
        Возвращает данные для финансовой панели управления.
        """
        today = timezone.now().date()
        
        # Определяем период
        if period == 'current_month':
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = datetime(today.year + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(today.year, today.month + 1, 1).date() - timedelta(days=1)
            period_str = f"{start_date.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')}"
        elif period == 'previous_month':
            if today.month == 1:
                start_date = datetime(today.year - 1, 12, 1).date()
                end_date = datetime(today.year, 1, 1).date() - timedelta(days=1)
            else:
                start_date = datetime(today.year, today.month - 1, 1).date()
                end_date = today.replace(day=1) - timedelta(days=1)
            period_str = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
        elif period == 'last_3_months':
            start_date = (today - timedelta(days=90))
            end_date = today
            period_str = f"{start_date.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')}"
        elif period == 'year':
            start_date = datetime(today.year, 1, 1).date()
            end_date = today
            period_str = f"01.01.{today.year} - {today.strftime('%d.%m.%Y')}"
        else:
            # По умолчанию - текущий месяц
            start_date = today.replace(day=1)
            end_date = today
            period_str = f"{start_date.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')}"
        
        # Получаем транзакции за период
        transactions = Transaction.objects.filter(date__range=[start_date, end_date])
        
        # Рассчитываем суммы
        total_income = transactions.filter(
            transaction_type__in=['payment', 'deposit']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        lesson_income = transactions.filter(
            transaction_type='payment',
            scheduled_lesson__isnull=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        lesson_income += transactions.filter(
            transaction_type='payment',
            non_scheduled_lesson__isnull=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        other_income = total_income - lesson_income
        
        refunds = transactions.filter(
            transaction_type='refund'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Получаем зарплаты учителей за период
        teacher_payments = TeacherSalary.objects.filter(
            month__range=[start_date, end_date],
            payment_status='paid'
        ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0.00')
        
        # Количество уроков
        scheduled_lessons_count = Attendance.objects.filter(
            date__range=[start_date, end_date],
            status='present'
        ).values('class_schedule', 'date').distinct().count()
        
        non_scheduled_lessons_count = NonScheduledLesson.objects.filter(
            date__range=[start_date, end_date],
            is_completed=True
        ).count()
        
        # Количество активных студентов
        students_count = Student.objects.filter(
            is_active=True
        ).count()
        
        # Рассчитываем прибыль
        profit = total_income - teacher_payments - refunds
        
        return {
            'period': period_str,
            'total_income': total_income,
            'lesson_income': lesson_income,
            'other_income': other_income,
            'teacher_payments': teacher_payments,
            'refunds': refunds,
            'profit': profit,
            'scheduled_lessons_count': scheduled_lessons_count,
            'non_scheduled_lessons_count': non_scheduled_lessons_count,
            'students_count': students_count
        }
    
    @staticmethod
    def get_teacher_earnings(teacher, year=None, month=None):
        """
        Возвращает данные о заработке учителя за указанный месяц.
        """
        if year is None or month is None:
            today = timezone.now().date()
            year = today.year
            month = today.month
        
        # Определяем период
        first_day = datetime(year, month, 1).date()
        
        # Получаем или создаем запись о зарплате
        salary = FinancialService.calculate_teacher_salary(teacher, first_day)
        
        # Получаем детальную информацию о выплатах за уроки
        lesson_payments = TeacherPayment.objects.filter(salary=salary)
        
        # Группируем выплаты по дням
        days_data = {}
        for payment in lesson_payments:
            date_str = payment.date.strftime('%Y-%m-%d')
            
            if date_str not in days_data:
                days_data[date_str] = {
                    'date': payment.date,
                    'day_of_week': payment.date.strftime('%A'),
                    'classes': [],
                    'total_amount': Decimal('0.00')
                }
            
            # Добавляем информацию о классе/уроке
            if payment.scheduled_lesson:
                class_obj = payment.scheduled_lesson.class_schedule.class_obj
                days_data[date_str]['classes'].append({
                    'class_name': class_obj.name,
                    'time': f"{payment.scheduled_lesson.class_schedule.start_time.strftime('%H:%M')} - {payment.scheduled_lesson.class_schedule.end_time.strftime('%H:%M')}",
                    'amount': payment.amount,
                    'is_scheduled': True
                })
            elif payment.non_scheduled_lesson:
                lesson = payment.non_scheduled_lesson
                # Рассчитываем время окончания
                end_time = (datetime.combine(datetime.today(), lesson.time) + 
                           timedelta(minutes=lesson.duration)).time()
                
                days_data[date_str]['classes'].append({
                    'class_name': f"{lesson.name} (Вне расписания)",
                    'time': f"{lesson.time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}",
                    'amount': payment.amount,
                    'students_count': NonScheduledLessonAttendance.objects.filter(
                        lesson=lesson,
                        is_present=True
                    ).count(),
                    'is_scheduled': False
                })
            
            # Увеличиваем общую сумму за день
            days_data[date_str]['total_amount'] += payment.amount
        
        # Сортируем дни по дате
        attendance_days = sorted(days_data.values(), key=lambda x: x['date'])
        
        # Группируем выплаты по классам
        class_stats = {}
        for payment in lesson_payments:
            if payment.scheduled_lesson:
                class_obj = payment.scheduled_lesson.class_schedule.class_obj
                class_id = f"class_{class_obj.id}"
                
                if class_id not in class_stats:
                    class_stats[class_id] = {
                        'name': class_obj.name,
                        'lessons_conducted': 0,
                        'amount_per_lesson': TeacherSalary.calculate_lesson_payment(class_obj),
                        'total_amount': Decimal('0.00'),
                        'is_scheduled': True
                    }
                
                class_stats[class_id]['lessons_conducted'] += 1
                class_stats[class_id]['total_amount'] += payment.amount
                
            elif payment.non_scheduled_lesson:
                lesson = payment.non_scheduled_lesson
                class_id = f"non_scheduled_{lesson.id}"
                
                if class_id not in class_stats:
                    class_stats[class_id] = {
                        'name': f"{lesson.name} (Вне расписания)",
                        'lessons_conducted': 0,
                        'amount_per_lesson': lesson.teacher_payment,
                        'total_amount': Decimal('0.00'),
                        'is_scheduled': False
                    }
                
                class_stats[class_id]['lessons_conducted'] += 1
                class_stats[class_id]['total_amount'] += payment.amount
        
        # Преобразуем в список
        class_stats_list = list(class_stats.values())
        
        return {
            'teacher': teacher,
            'salary': salary,
            'attendance_days': attendance_days,
            'class_stats': class_stats_list,
            'current_month': first_day,
            'total_days': len(attendance_days),
            'total_lessons': salary.lessons_count,
            'total_amount': salary.amount
        }
    
    @staticmethod
    def get_student_financial_summary(student, period=None):
        """
        Возвращает финансовую сводку по студенту за указанный период.
        """
        # Определяем период
        today = timezone.now().date()
        
        if period == 'current_month':
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = datetime(today.year + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(today.year, today.month + 1, 1).date() - timedelta(days=1)
        elif period == 'previous_month':
            if today.month == 1:
                start_date = datetime(today.year - 1, 12, 1).date()
                end_date = datetime(today.year, 1, 1).date() - timedelta(days=1)
            else:
                start_date = datetime(today.year, today.month - 1, 1).date()
                end_date = today.replace(day=1) - timedelta(days=1)
        elif period == 'last_3_months':
            start_date = (today - timedelta(days=90)).replace(day=1)
            end_date = today
        elif period == 'year':
            start_date = datetime(today.year, 1, 1).date()
            end_date = today
        else:  # all time
            start_date = None
            end_date = None
        
        # Получаем транзакции студента
        transactions = Transaction.objects.filter(student=student)
        
        if start_date:
            transactions = transactions.filter(date__gte=start_date)
        if end_date:
            transactions = transactions.filter(date__lte=end_date)
        
        # Группируем транзакции по типам
        payments = transactions.filter(transaction_type='payment')
        deposits = transactions.filter(transaction_type='deposit')
        refunds = transactions.filter(transaction_type='refund')
        
        # Рассчитываем суммы
        total_payments = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_deposits = deposits.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_refunds = refunds.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Получаем информацию о посещенных уроках
        scheduled_lessons = Attendance.objects.filter(
            student=student,
            status='present'
        )
        
        non_scheduled_lessons = NonScheduledLessonAttendance.objects.filter(
            student=student,
            is_present=True
        )
        
        if start_date:
            scheduled_lessons = scheduled_lessons.filter(date__gte=start_date)
            non_scheduled_lessons = non_scheduled_lessons.filter(lesson__date__gte=start_date)
        if end_date:
            scheduled_lessons = scheduled_lessons.filter(date__lte=end_date)
            non_scheduled_lessons = non_scheduled_lessons.filter(lesson__date__lte=end_date)
        
        # Считаем количество уроков
        scheduled_lessons_count = scheduled_lessons.count()
        non_scheduled_lessons_count = non_scheduled_lessons.count()
        total_lessons_count = scheduled_lessons_count + non_scheduled_lessons_count
        
        # Рассчитываем среднюю стоимость урока
        avg_lesson_cost = Decimal('0.00')
        if total_lessons_count > 0 and total_payments > 0:
            avg_lesson_cost = total_payments / total_lessons_count
        
        return {
            'student': student,
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'name': period or 'all_time'
            },
            'balance': student.balance,
            'total_payments': total_payments,
            'total_deposits': total_deposits,
            'total_refunds': total_refunds,
            'scheduled_lessons_count': scheduled_lessons_count,
            'non_scheduled_lessons_count': non_scheduled_lessons_count,
            'total_lessons_count': total_lessons_count,
            'avg_lesson_cost': avg_lesson_cost
        }
    
    @staticmethod
    def get_class_financial_summary(class_obj, period=None):
        """
        Возвращает финансовую сводку по классу за указанный период.
        """
        # Определяем период
        today = timezone.now().date()
        
        if period == 'current_month':
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = datetime(today.year + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(today.year, today.month + 1, 1).date() - timedelta(days=1)
        elif period == 'previous_month':
            if today.month == 1:
                start_date = datetime(today.year - 1, 12, 1).date()
                end_date = datetime(today.year, 1, 1).date() - timedelta(days=1)
            else:
                start_date = datetime(today.year, today.month - 1, 1).date()
                end_date = today.replace(day=1) - timedelta(days=1)
        elif period == 'last_3_months':
            start_date = (today - timedelta(days=90)).replace(day=1)
            end_date = today
        elif period == 'year':
            start_date = datetime(today.year, 1, 1).date()
            end_date = today
        else:  # all time
            start_date = None
            end_date = None
        
        # Получаем транзакции класса
        transactions = Transaction.objects.filter(class_obj=class_obj)
        
        if start_date:
            transactions = transactions.filter(date__gte=start_date)
        if end_date:
            transactions = transactions.filter(date__lte=end_date)
        
        # Рассчитываем доход от класса
        total_income = transactions.filter(
            transaction_type='payment'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Получаем информацию о проведенных уроках
        attendances = Attendance.objects.filter(
            class_schedule__class_obj=class_obj,
            status='present'
        )
        
        if start_date:
            attendances = attendances.filter(date__gte=start_date)
        if end_date:
            attendances = attendances.filter(date__lte=end_date)
        
        # Группируем по уникальным урокам
        unique_lessons = attendances.values('date', 'class_schedule').distinct()
        lessons_count = unique_lessons.count()
        
        # Рассчитываем выплаты учителю
        teacher_payments = TeacherPayment.objects.filter(
            scheduled_lesson__class_schedule__class_obj=class_obj
        )
        
        if start_date:
            teacher_payments = teacher_payments.filter(date__gte=start_date)
        if end_date:
            teacher_payments = teacher_payments.filter(date__lte=end_date)
        
        total_teacher_payments = teacher_payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Рассчитываем прибыль
        profit = total_income - total_teacher_payments
        
        # Рассчитываем среднюю прибыль с урока
        avg_profit_per_lesson = Decimal('0.00')
        if lessons_count > 0 and profit > 0:
            avg_profit_per_lesson = profit / lessons_count
        
        # Получаем количество студентов в классе
        students_count = class_obj.students.filter(is_active=True).count()
        
        return {
            'class': class_obj,
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'name': period or 'all_time'
            },
            'total_income': total_income,
            'total_teacher_payments': total_teacher_payments,
            'profit': profit,
            'lessons_count': lessons_count,
            'students_count': students_count,
            'avg_profit_per_lesson': avg_profit_per_lesson
        }
    
    @staticmethod
    def get_transaction_statistics(period=None):
        """
        Возвращает статистику по транзакциям за указанный период.
        """
        # Определяем период
        today = timezone.now().date()
        
        if period == 'current_month':
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = datetime(today.year + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(today.year, today.month + 1, 1).date() - timedelta(days=1)
        elif period == 'previous_month':
            if today.month == 1:
                start_date = datetime(today.year - 1, 12, 1).date()
                end_date = datetime(today.year, 1, 1).date() - timedelta(days=1)
            else:
                start_date = datetime(today.year, today.month - 1, 1).date()
                end_date = today.replace(day=1) - timedelta(days=1)
        elif period == 'last_3_months':
            start_date = (today - timedelta(days=90)).replace(day=1)
            end_date = today
        elif period == 'year':
            start_date = datetime(today.year, 1, 1).date()
            end_date = today
        else:  # all time
            start_date = None
            end_date = None
        
        # Получаем транзакции
        transactions = Transaction.objects.all()
        
        if start_date:
            transactions = transactions.filter(date__gte=start_date)
        if end_date:
            transactions = transactions.filter(date__lte=end_date)
        
        # Группируем транзакции по типам
        payments = transactions.filter(transaction_type='payment')
        deposits = transactions.filter(transaction_type='deposit')
        refunds = transactions.filter(transaction_type='refund')
        
        # Рассчитываем суммы
        total_payments = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_deposits = deposits.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_refunds = refunds.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Группируем платежи по классам
        class_payments = payments.filter(class_obj__isnull=False).values('class_obj').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')
        
        # Получаем информацию о классах
        class_stats = []
        for cp in class_payments:
            try:
                class_obj = Class.objects.get(id=cp['class_obj'])
                class_stats.append({
                    'class_id': class_obj.id,
                    'class_name': class_obj.name,
                    'total_payments': cp['total'],
                    'transactions_count': cp['count']
                })
            except Class.DoesNotExist:
                pass
        
        # Группируем платежи по студентам
        student_payments = payments.values('student').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')[:10]  # Топ-10 студентов
        
        # Получаем информацию о студентах
        student_stats = []
        for sp in student_payments:
            try:
                student = Student.objects.get(id=sp['student'])
                student_stats.append({
                    'student_id': student.id,
                    'student_name': student.full_name,
                    'total_payments': sp['total'],
                    'transactions_count': sp['count']
                })
            except Student.DoesNotExist:
                pass
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'name': period or 'all_time'
            },
            'total_payments': total_payments,
            'total_deposits': total_deposits,
            'total_refunds': total_refunds,
            'total_income': total_payments + total_deposits,
            'transactions_count': transactions.count(),
            'class_stats': class_stats,
            'student_stats': student_stats
        }
