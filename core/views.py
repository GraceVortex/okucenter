from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from classes.models import Class, ClassSchedule
from accounts.models import Student, Teacher
from attendance.models import Attendance, CancellationRequest
from finance.models import Transaction, TeacherSalary
from django.db.models import Count, Q, Sum
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

User = get_user_model()

def home(request):
    context = {}
    
    if request.user.is_authenticated:
        user = request.user
        context['user_type'] = user.user_type
        
        if user.is_admin:
            # Базовая статистика
            context['admin_data'] = {
                'total_students': Student.objects.count(),
                'total_teachers': Teacher.objects.count(),
                'total_classes': Class.objects.count(),
            }
            
            # Финансовая статистика
            today = timezone.now().date()
            first_day_of_month = today.replace(day=1)
            
            # Доход от уроков (платежи)
            lesson_income = Transaction.objects.filter(
                transaction_type='payment',
                date__gte=first_day_of_month,
                date__lte=today
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            # Выплаты учителям за текущий месяц
            teacher_payments = TeacherSalary.objects.filter(
                month=first_day_of_month,
                is_paid=True
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            # Предконечный доход = доход от уроков - выплаты учителям
            net_income = lesson_income - teacher_payments
            
            # Общий баланс учеников (сумма всех нынешних балансов)
            total_balance = Student.objects.aggregate(total=Sum('balance'))['total'] or Decimal('0')
            
            # Добавляем финансовую статистику в контекст
            context['admin_data']['monthly_income'] = net_income
            context['admin_data']['total_balance'] = total_balance
            
            # Статистика посещаемости
            # Посещаемость за сегодня
            today_attendance = Attendance.objects.filter(
                date=today,
                reception_confirmed=True
            ).count()
            
            # Ожидающие подтверждения ресепшн
            pending_attendances = Attendance.objects.filter(
                teacher_confirmed=True,
                reception_confirmed=False
            ).count()
            
            # Добавляем статистику посещаемости в контекст
            context['admin_data']['today_attendance'] = today_attendance
            context['pending_attendances'] = pending_attendances
            
            # Добавляем статистику запросов на отмену уроков
            pending_cancellations = CancellationRequest.objects.filter(status='pending').count()
            context['pending_cancellations'] = pending_cancellations
            
        elif user.is_reception:
            context['pending_attendances'] = Attendance.objects.filter(
                teacher_confirmed=True, 
                reception_confirmed=False
            ).count()
            
            # Добавляем статистику запросов на отмену уроков
            pending_cancellations = CancellationRequest.objects.filter(status='pending').count()
            context['pending_cancellations'] = pending_cancellations
        elif user.is_teacher:
            teacher = user.teacher_profile
            context['teacher_classes'] = teacher.classes.all()
            
            # Добавляем информацию о запросах на отмену уроков
            today = timezone.now().date()
            pending_cancellations = CancellationRequest.objects.filter(
                teacher=teacher,
                status='pending'
            ).count()
            context['pending_cancellations'] = pending_cancellations
            
            # Добавляем информацию о уроках замены
            substitute_classes = Attendance.objects.filter(
                substitute_teacher=teacher,
                is_canceled=True,
                date__gte=today
            ).values('class_obj', 'date').distinct().count()
            context['substitute_classes'] = substitute_classes
        elif user.is_student:
            student = user.student_profile
            context['student_classes'] = student.enrollments.all()
            
            # Добавляем статистику посещаемости для студента
            attendance_stats = Attendance.objects.filter(student=student)
            context['student_attendance'] = {
                'total': attendance_stats.count(),
                'present': attendance_stats.filter(status='present').count(),
                'absent': attendance_stats.filter(status='absent').count(),
                'excused': attendance_stats.filter(status='excused').count()
            }
        elif user.is_parent:
            parent = user.parent_profile
            context['children'] = parent.children.all()
    
    return render(request, 'core/home.html', context)

def schedule_view(request):
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    rooms = [f'Room {i}' for i in range(1, 9)]
    time_slots = [
        '8:00 - 9:30',
        '9:30 - 11:00',
        '11:00 - 12:30',
        '14:30 - 16:00',
        '16:00 - 17:30',
        '17:30 - 19:00'
    ]
    
    # Словарь для сопоставления временных слотов с диапазонами времени
    time_ranges = {
        '8:00 - 9:30': ('08:00:00', '09:30:00'),
        '9:30 - 11:00': ('09:30:00', '11:00:00'),
        '11:00 - 12:30': ('11:00:00', '12:30:00'),
        '14:30 - 16:00': ('14:30:00', '16:00:00'),
        '16:00 - 17:30': ('16:00:00', '17:30:00'),
        '17:30 - 19:00': ('17:30:00', '19:00:00')
    }
    
    # Фильтруем расписание в зависимости от роли пользователя
    if request.user.is_authenticated:
        if request.user.is_admin or request.user.is_reception or request.user.is_teacher:
            # Администраторы, ресепшн и учителя видят все расписание
            schedules = ClassSchedule.objects.all().select_related('class_obj', 'class_obj__teacher')
        elif request.user.is_student:
            # Студенты видят только свои классы
            student = request.user.student_profile
            enrollments = student.enrollments.all()
            class_ids = [enrollment.class_obj.id for enrollment in enrollments]
            schedules = ClassSchedule.objects.filter(class_obj__id__in=class_ids).select_related('class_obj', 'class_obj__teacher')
        elif request.user.is_parent:
            # Родители видят классы своих детей
            parent = request.user.parent_profile
            children = parent.students.all()
            
            # Получаем все записи о зачислении для детей родителя
            enrollments = []
            for child in children:
                enrollments.extend(child.enrollments.all())
            
            class_ids = [enrollment.class_obj.id for enrollment in enrollments]
            schedules = ClassSchedule.objects.filter(class_obj__id__in=class_ids).select_related('class_obj', 'class_obj__teacher')
        else:
            # Неавторизованные пользователи не видят расписание
            schedules = ClassSchedule.objects.none()
    else:
        # Неавторизованные пользователи не видят расписание
        schedules = ClassSchedule.objects.none()
    
    schedule_data = {}
    for day_idx, day in enumerate(days):
        schedule_data[day] = {}
        for time_slot in time_slots:
            schedule_data[day][time_slot] = {}
            start_time, end_time = time_ranges[time_slot]
            
            for room_idx, room in enumerate(rooms, 1):
                # Фильтруем занятия по дню, комнате и точному временному слоту
                # Используем точное сравнение start_time вместо диапазона
                schedule_data[day][time_slot][room] = schedules.filter(
                    day_of_week=day_idx,
                    room=room_idx,
                    start_time=start_time
                )
    
    context = {
        'days': days,
        'rooms': rooms,
        'time_slots': time_slots,
        'schedule_data': schedule_data,
    }
    
    return render(request, 'core/schedule.html', context)
