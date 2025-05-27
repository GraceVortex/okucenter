from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from classes.models import Class, ClassSchedule, Homework, HomeworkSubmission, Enrollment
from accounts.models import Student, Teacher, Parent
from attendance.models import Attendance, CancellationRequest, Mark
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
            
            # Посещаемость, ожидающая подтверждения
            context['pending_attendances'] = Attendance.objects.filter(
                teacher_confirmed=True,
                reception_confirmed=False
            ).count()
            
            # Финансовая статистика
            today = timezone.now().date()
            first_day_of_month = today.replace(day=1)
            
            # Доход от уроков (платежи)
            lesson_income = Transaction.objects.filter(
                transaction_type='payment',
                date__gte=first_day_of_month,
                date__lte=today
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            # Выплаты учителям за текущий месяц - используем тот же метод, что и на странице зарплат
            teacher_payments = Decimal('0.00')
            
            # Получаем всех учителей
            teachers = Teacher.objects.all()
            
            # Для каждого учителя рассчитываем зарплату на основе фактических посещений
            for teacher in teachers:
                # Получаем все посещения для подсчета уникальных занятий
                attendances = Attendance.objects.filter(
                    class_schedule__class_obj__teacher=teacher,
                    date__gte=first_day_of_month,
                    date__lte=today,
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
                
                # Рассчитываем сумму зарплаты на основе уникальных занятий
                for key, data in unique_classes.items():
                    class_obj = data['class_obj']
                    
                    # Определяем сумму за занятие
                    if class_obj.teacher_payment_type == 'percentage':
                        price = class_obj.price_per_lesson
                        percentage = Decimal(str(class_obj.teacher_percentage)) / Decimal('100')
                        amount = price * percentage
                    else:  # fixed payment
                        amount = class_obj.teacher_fixed_payment
                    
                    teacher_payments += amount
            
            # Предконечный доход = доход от уроков - выплаты учителям
            net_income = lesson_income - teacher_payments
            
            # Общий баланс учеников (сумма всех нынешних балансов)
            total_balance = Student.objects.aggregate(total=Sum('balance'))['total'] or Decimal('0')
            
            # Добавляем финансовую статистику в контекст
            context['admin_data']['monthly_income'] = net_income
            context['admin_data']['total_balance'] = total_balance
            
            # Статистика посещаемости
            # Посещаемость за сегодня - считаем уникальные занятия
            today_attendances = Attendance.objects.filter(
                date=today,
                reception_confirmed=True
            ).select_related('class_schedule')
            
            # Считаем уникальные занятия по дате и расписанию
            unique_today_classes = set()
            for attendance in today_attendances:
                unique_today_classes.add((attendance.date, attendance.class_schedule.id))
            
            today_attendance = len(unique_today_classes)
            
            # Ожидающие подтверждения ресепшн
            pending_attendances_data = Attendance.objects.filter(
                teacher_confirmed=True,
                reception_confirmed=False,
                status='present'  # Добавляем проверку статуса посещаемости
            ).select_related('class_schedule')
            
            # Считаем уникальные занятия, ожидающие подтверждения
            unique_pending_classes = set()
            for attendance in pending_attendances_data:
                unique_pending_classes.add((attendance.date, attendance.class_schedule.id))
            
            pending_attendances = len(unique_pending_classes)
            
            # Добавляем статистику посещаемости в контекст
            context['admin_data']['today_attendance'] = today_attendance
            context['pending_attendances'] = pending_attendances
            
            # Добавляем статистику запросов на отмену уроков от учителей
            pending_cancellations = CancellationRequest.objects.filter(status='pending').count()
            context['pending_cancellations'] = pending_cancellations
            
            # Добавляем статистику запросов на отмену уроков от студентов
            from attendance.models import StudentCancellationRequest
            pending_student_cancellations = StudentCancellationRequest.objects.filter(status='pending').count()
            context['pending_student_cancellations'] = pending_student_cancellations
            
        elif user.is_reception:
            context['pending_attendances'] = Attendance.objects.filter(
                teacher_confirmed=True, 
                reception_confirmed=False,
                status='present'  # Добавляем проверку статуса посещаемости
            ).count()
            
            # Добавляем статистику запросов на отмену уроков от учителей
            pending_cancellations = CancellationRequest.objects.filter(status='pending').count()
            context['pending_cancellations'] = pending_cancellations
            
            # Добавляем статистику запросов на отмену уроков от студентов
            from attendance.models import StudentCancellationRequest
            pending_student_cancellations = StudentCancellationRequest.objects.filter(status='pending').count()
            context['pending_student_cancellations'] = pending_student_cancellations
        elif user.is_teacher:
            teacher = user.teacher_profile
            context['teacher_classes'] = teacher.classes.all()
            
            # Добавляем информацию о запросах на отмену уроков
            today = timezone.now().date()
            current_time = timezone.now().time()
            current_weekday = today.weekday()
            
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
            
            # Получаем все классы учителя
            teacher_classes = teacher.classes.all()
            class_ids = teacher_classes.values_list('id', flat=True)
            
            # Получаем все расписания для классов учителя
            schedules = ClassSchedule.objects.filter(class_obj_id__in=class_ids).select_related('class_obj')
            
            # Находим ближайший урок
            next_class = None
            days_until_next_class = 7  # Максимум неделя
            
            # Проверяем сначала уроки сегодня, которые еще не прошли
            todays_schedules = schedules.filter(day_of_week=current_weekday)
            for schedule in todays_schedules:
                if schedule.start_time > current_time:  # Урок еще не начался
                    next_class = schedule
                    days_until_next_class = 0
                    break
            
            # Если сегодня больше нет уроков, ищем на ближайшие дни
            if next_class is None:
                for days_ahead in range(1, 8):  # Проверяем следующие 7 дней
                    next_day = (current_weekday + days_ahead) % 7  # Циклически переходим к следующему дню недели
                    day_schedules = schedules.filter(day_of_week=next_day)
                    
                    if day_schedules.exists():
                        # Берем самый ранний урок в этот день
                        next_class = day_schedules.order_by('start_time').first()
                        days_until_next_class = days_ahead
                        break
            
            # Если нашли ближайший урок, добавляем информацию в контекст
            if next_class:
                # Получаем название дня недели
                day_names = dict(ClassSchedule.DAY_CHOICES)
                day_name = day_names[next_class.day_of_week]
                
                # Форматируем время начала и окончания
                start_time = next_class.start_time.strftime('%H:%M')
                end_time = next_class.end_time.strftime('%H:%M')
                
                # Вычисляем дату следующего урока
                if days_until_next_class == 0:
                    next_class_date = today
                else:
                    next_class_date = today + timedelta(days=days_until_next_class)
                
                # Получаем количество студентов в классе
                student_count = Enrollment.objects.filter(class_obj=next_class.class_obj, is_active=True).count()
                
                context['next_class'] = {
                    'class_name': next_class.class_obj.name,
                    'class_id': next_class.class_obj.id,
                    'schedule_id': next_class.id,
                    'day_name': day_name,
                    'date': next_class_date,
                    'start_time': start_time,
                    'end_time': end_time,
                    'room': next_class.room,
                    'days_until': days_until_next_class,
                    'student_count': student_count
                }
            
            # Получаем непроверенные домашние задания для классов учителя
            unchecked_homework = HomeworkSubmission.objects.filter(
                homework__class_obj__in=teacher_classes,
                completion_status__isnull=True  # Не проверенные задания не имеют статуса выполнения
            ).select_related('homework', 'student', 'homework__class_obj').order_by('submission_date')
            
            # Получаем общее количество непроверенных заданий
            unchecked_homework_count = unchecked_homework.count()
            context['unchecked_homework_count'] = unchecked_homework_count
            
            # Если есть непроверенные задания, добавляем информацию о них
            if unchecked_homework_count > 0:
                # Группируем домашние задания по классам
                homework_by_class = {}
                for submission in unchecked_homework[:5]:  # Берем первые 5 заданий для отображения
                    class_id = submission.homework.class_obj.id
                    if class_id not in homework_by_class:
                        homework_by_class[class_id] = []
                    
                    # Проверяем, прошел ли дедлайн
                    deadline_passed = False
                    if submission.homework.due_date:
                        deadline_passed = submission.homework.due_date < today
                    
                    homework_by_class[class_id].append({
                        'submission': submission,
                        'homework': submission.homework,
                        'student': submission.student,
                        'class': submission.homework.class_obj,
                        'submitted_at': submission.submission_date,
                        'deadline_passed': deadline_passed
                    })
                
                context['homework_by_class'] = homework_by_class
        elif user.is_student:
            student = user.student_profile
            context['student_classes'] = student.enrollments.all()
            
            # Проверяем, является ли студент самоуправляемым
            # Если студент не самоуправляемый (имеет привязанного родителя), то скрываем финансовую информацию
            context['show_financial_info'] = student.is_self_managed
            
            # Добавляем статистику посещаемости для студента
            attendance_stats = Attendance.objects.filter(student=student)
            context['student_attendance'] = {
                'total': attendance_stats.count(),
                'present': attendance_stats.filter(status='present').count(),
                'absent': attendance_stats.filter(status='absent').count(),
                'excused': attendance_stats.filter(status='excused').count()
            }
            
            # Находим ближайший урок для студента
            today = timezone.now().date()
            current_time = timezone.now().time()
            current_weekday = today.weekday()
            
            # Получаем все активные зачисления студента
            active_enrollments = student.enrollments.filter(is_active=True)
            class_ids = active_enrollments.values_list('class_obj_id', flat=True)
            
            # Находим ближайшее домашнее задание с дедлайном
            # Получаем все домашние задания для классов студента
            homework_assignments = Homework.objects.filter(class_obj_id__in=class_ids)
            
            # Получаем все выполненные домашние задания студента
            submitted_homework_ids = HomeworkSubmission.objects.filter(
                student=student
            ).values_list('homework_id', flat=True)
            
            # Находим невыполненные домашние задания с ближайшим дедлайном
            pending_homework = homework_assignments.exclude(
                id__in=submitted_homework_ids
            ).order_by('due_date')  # Сортируем по дедлайну (самые ранние сначала)
            
            # Добавляем информацию о ближайшем домашнем задании в контекст
            if pending_homework.exists():
                next_homework = pending_homework.first()
                days_until_deadline = (next_homework.due_date - today).days
                
                # Проверяем, прошел ли дедлайн
                deadline_passed = days_until_deadline < 0
                
                context['next_homework'] = {
                    'title': next_homework.title,
                    'class_name': next_homework.class_obj.name,
                    'due_date': next_homework.due_date,
                    'days_until': days_until_deadline,
                    'description': next_homework.description,
                    'homework_id': next_homework.id,
                    'deadline_passed': deadline_passed
                }
            else:
                # Если все домашние задания выполнены
                context['all_homework_completed'] = True
            
            # Получаем расписания для классов, в которых зачислен студент
            schedules = ClassSchedule.objects.filter(class_obj_id__in=class_ids).select_related('class_obj')
            
            # Находим ближайший урок
            next_class = None
            days_until_next_class = 7  # Максимум неделя
            
            # Проверяем сначала уроки сегодня, которые еще не прошли
            todays_schedules = schedules.filter(day_of_week=current_weekday)
            for schedule in todays_schedules:
                if schedule.start_time > current_time:  # Урок еще не начался
                    next_class = schedule
                    days_until_next_class = 0
                    break
            
            # Если сегодня больше нет уроков, ищем на ближайшие дни
            if next_class is None:
                for days_ahead in range(1, 8):  # Проверяем следующие 7 дней
                    next_day = (current_weekday + days_ahead) % 7  # Циклически переходим к следующему дню недели
                    day_schedules = schedules.filter(day_of_week=next_day)
                    
                    if day_schedules.exists():
                        # Берем самый ранний урок в этот день
                        next_class = day_schedules.order_by('start_time').first()
                        days_until_next_class = days_ahead
                        break
            
            # Если нашли ближайший урок, добавляем информацию в контекст
            if next_class:
                # Получаем название дня недели
                day_names = dict(ClassSchedule.DAY_CHOICES)
                day_name = day_names[next_class.day_of_week]
                
                # Форматируем время начала и окончания
                start_time = next_class.start_time.strftime('%H:%M')
                end_time = next_class.end_time.strftime('%H:%M')
                
                # Вычисляем дату следующего урока
                if days_until_next_class == 0:
                    next_class_date = today
                else:
                    next_class_date = today + timedelta(days=days_until_next_class)
                
                context['next_class'] = {
                    'class_name': next_class.class_obj.name,
                    'teacher': next_class.class_obj.teacher.full_name,
                    'day_name': day_name,
                    'date': next_class_date,
                    'start_time': start_time,
                    'end_time': end_time,
                    'room': next_class.room,
                    'days_until': days_until_next_class
                }
        elif user.is_parent:
            # Get parent profile
            parent = user.parent_profile
            
            # Get all children of the parent
            children = parent.children.all()
            
            # Get cancellation requests count
            from attendance.models import StudentCancellationRequest
            pending_cancellations = StudentCancellationRequest.objects.filter(
                student__in=children, 
                status='pending'
            ).count()
            
            # Prepare data for each child similar to parent_dashboard view
            children_data = []
            for child in children:
                # Get child's balance
                balance = child.balance
                
                # Get child's enrollments and classes
                enrollments = Enrollment.objects.filter(student=child, is_active=True).select_related('class_obj', 'class_obj__teacher')
                classes = [enrollment.class_obj for enrollment in enrollments]
                class_ids = [enrollment.class_obj.id for enrollment in enrollments]
                
                # Get attendance records
                attendances = Attendance.objects.filter(student=child).select_related('class_schedule', 'class_schedule__class_obj')
                
                # Get homework submissions
                homework_submissions = HomeworkSubmission.objects.filter(student=child).select_related('homework')
                
                # Get grades
                marks = Mark.objects.filter(student=child).select_related('class_obj')
                
                # Get pending cancellation requests for this child
                child_pending_cancellations = StudentCancellationRequest.objects.filter(student=child, status='pending').count()
                
                # Prepare child data dictionary
                child_data = {
                    'student': child,
                    'balance': balance,
                    'enrollments': enrollments,
                    'classes': classes,
                    'attendances': attendances,
                    'homework_submissions': homework_submissions,
                    'marks': marks,
                    'pending_cancellations': child_pending_cancellations
                }
                
                # Get next class information
                if class_ids:
                    # Get current time and weekday
                    current_time = timezone.localtime().time()
                    current_weekday = timezone.localtime().weekday() + 1  # Django uses 1-7 for weekdays
                    today = timezone.localdate()
                    
                    # Get schedules for classes the child is enrolled in
                    schedules = ClassSchedule.objects.filter(class_obj_id__in=class_ids).select_related('class_obj', 'class_obj__teacher')
                    
                    # Find the next class
                    next_class = None
                    days_until_next_class = 7  # Maximum one week
                    next_class_date = None
                    
                    # Check for classes today that haven't started yet
                    todays_schedules = schedules.filter(day_of_week=current_weekday)
                    for schedule in todays_schedules:
                        if schedule.start_time > current_time:  # Class hasn't started yet
                            next_class = schedule
                            days_until_next_class = 0
                            next_class_date = today
                            break
                    
                    # If no classes today, look for the next few days
                    if next_class is None:
                        for days_ahead in range(1, 8):  # Check the next 7 days
                            next_date = today + timedelta(days=days_ahead)
                            next_weekday = next_date.weekday() + 1  # Convert to 1-7 format
                            
                            day_schedules = schedules.filter(day_of_week=next_weekday)
                            if day_schedules.exists():
                                # Get the earliest class of the day
                                next_class = day_schedules.order_by('start_time').first()
                                days_until_next_class = days_ahead
                                next_class_date = next_date
                                break
                    
                    # If we found a next class, add it to the context
                    if next_class:
                        # Get day name in Russian
                        day_names = {
                            1: 'Понедельник', 2: 'Вторник', 3: 'Среда', 4: 'Четверг',
                            5: 'Пятница', 6: 'Суббота', 7: 'Воскресенье'
                        }
                        day_name = day_names.get(next_class.day_of_week, '')
                        
                        # Format times
                        start_time = next_class.start_time.strftime('%H:%M')
                        end_time = next_class.end_time.strftime('%H:%M')
                        
                        child_data['next_class'] = {
                            'class_name': next_class.class_obj.name,
                            'teacher': next_class.class_obj.teacher.full_name,
                            'day_name': day_name,
                            'date': next_class_date,
                            'start_time': start_time,
                            'end_time': end_time,
                            'room': next_class.room,
                            'days_until': days_until_next_class
                        }
                
                # Get homework information
                if class_ids:
                    # Get all homework assignments for the child's classes
                    homework_assignments = Homework.objects.filter(class_obj_id__in=class_ids)
                    
                    # Get IDs of homework that has been submitted
                    submitted_homework_ids = HomeworkSubmission.objects.filter(
                        student=child
                    ).values_list('homework_id', flat=True)
                    
                    # Find pending homework with the nearest deadline
                    pending_homework = homework_assignments.exclude(
                        id__in=submitted_homework_ids
                    ).order_by('due_date')  # Sort by deadline (earliest first)
                    
                    # Add information about the next homework to the context
                    if pending_homework.exists():
                        next_homework = pending_homework.first()
                        days_until_deadline = (next_homework.due_date - today).days
                        
                        # Check if the deadline has passed
                        deadline_passed = days_until_deadline < 0
                        
                        child_data['next_homework'] = {
                            'title': next_homework.title,
                            'class_name': next_homework.class_obj.name,
                            'due_date': next_homework.due_date,
                            'days_until': days_until_deadline,
                            'description': next_homework.description,
                            'homework_id': next_homework.id,
                            'deadline_passed': deadline_passed
                        }
                    else:
                        # If all homework is completed
                        child_data['all_homework_completed'] = True
                
                children_data.append(child_data)
            
            context['children'] = children
            context['children_data'] = children_data
            context['pending_cancellations'] = pending_cancellations
            context['parent'] = parent
    
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
            # Студенты видят только свои классы и только после даты зачисления
            student = request.user.student_profile
            enrollments = student.enrollments.filter(is_active=True)
            
            # Создаем словарь с датами зачисления для каждого класса
            enrollment_dates = {enrollment.class_obj.id: enrollment.enrollment_date for enrollment in enrollments}
            
            # Получаем ID классов, в которые зачислен студент
            class_ids = list(enrollment_dates.keys())
            
            # Получаем расписание для этих классов
            schedules = ClassSchedule.objects.filter(class_obj__id__in=class_ids).select_related('class_obj', 'class_obj__teacher')
            
            # Сохраняем даты зачисления в контексте для использования в шаблоне
            request.enrollment_dates = enrollment_dates
        elif request.user.is_parent:
            # Родители видят классы своих детей только после даты зачисления
            parent = request.user.get_parent_profile()
            children = parent.students.all()
            
            # Получаем все записи о зачислении для детей родителя
            enrollments = []
            enrollment_dates = {}
            
            for child in children:
                child_enrollments = child.enrollments.filter(is_active=True)
                for enrollment in child_enrollments:
                    enrollments.append(enrollment)
                    # Сохраняем дату зачисления для каждого класса
                    enrollment_dates[enrollment.class_obj.id] = enrollment.enrollment_date
            
            # Получаем ID классов, в которые зачислены дети
            class_ids = list(enrollment_dates.keys())
            
            # Получаем расписание для этих классов
            schedules = ClassSchedule.objects.filter(class_obj__id__in=class_ids).select_related('class_obj', 'class_obj__teacher')
            
            # Сохраняем даты зачисления в контексте для использования в шаблоне
            request.enrollment_dates = enrollment_dates
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
    
    # Добавляем информацию о датах зачисления в контекст
    enrollment_dates = getattr(request, 'enrollment_dates', {})
    
    context = {
        'days': days,
        'rooms': rooms,
        'time_slots': time_slots,
        'schedule_data': schedule_data,
        'enrollment_dates': enrollment_dates,
    }
    
    return render(request, 'core/schedule.html', context)


def schedule_detail_view(request, schedule_id):
    """
    Представление для отображения деталей занятия, включая материалы и оценки.
    """
    from django.shortcuts import get_object_or_404
    from classes.models import ClassSchedule, LessonMaterial, StudentLessonGrade, Enrollment
    from django.utils import timezone
    from datetime import datetime
    
    # Получаем расписание по ID
    schedule = get_object_or_404(ClassSchedule, id=schedule_id)
    
    # Проверяем права доступа
    if request.user.is_authenticated:
        if request.user.is_admin or request.user.is_reception or request.user.is_teacher:
            # Администраторы, ресепшн и учителя имеют доступ ко всем занятиям
            pass
        elif request.user.is_student:
            # Студенты видят только свои классы и только после даты зачисления
            student = request.user.student_profile
            enrollments = student.enrollments.filter(is_active=True, class_obj=schedule.class_obj)
            
            if not enrollments.exists():
                # Если студент не зачислен в этот класс, перенаправляем на страницу расписания
                from django.shortcuts import redirect
                return redirect('core:schedule')
            
            # Проверяем, что студент был зачислен до даты занятия
            enrollment = enrollments.first()
            
            # Преобразуем даты для корректного сравнения
            current_date = timezone.now().date()
            enrollment_date = enrollment.enrollment_date
            if hasattr(enrollment_date, 'date'):
                enrollment_date = enrollment_date.date()
                
            if enrollment_date > current_date:
                # Если студент был зачислен после текущей даты, перенаправляем на страницу расписания
                from django.shortcuts import redirect
                return redirect('core:schedule')
        elif request.user.is_parent:
            # Родители видят только классы своих детей и только после даты зачисления
            from accounts.models import Parent, Student
            
            # Проверяем, есть ли у родителя дети, зачисленные в этот класс
            try:
                parent = Parent.objects.get(user=request.user)
                students = Student.objects.filter(parent=parent)
                enrollments = Enrollment.objects.filter(student__in=students, class_obj=schedule.class_obj, is_active=True)
                
                if not enrollments.exists():
                    # Если ни один из детей не зачислен в этот класс
                    from django.shortcuts import redirect
                    return redirect('core:home')
                
                # Проверяем, что хотя бы один ребенок был зачислен до даты занятия
                valid_enrollment = False
                for enrollment in enrollments:
                    enrollment_date = enrollment.enrollment_date
                    if hasattr(enrollment_date, 'date'):
                        enrollment_date = enrollment_date.date()
                    
                    current_date = timezone.now().date()
                    if enrollment_date <= current_date:
                        valid_enrollment = True
                        break
                
                if not valid_enrollment:
                    # Если ни один ребенок не был зачислен до текущей даты
                    from django.shortcuts import redirect
                    return redirect('core:home')
                    
            except Parent.DoesNotExist:
                from django.shortcuts import redirect
                return redirect('core:home')
        else:
            # Остальные пользователи не имеют доступа
            from django.shortcuts import redirect
            return redirect('core:schedule')
    else:
        # Неавторизованные пользователи не имеют доступа
        from django.shortcuts import redirect
        return redirect('accounts:login')
    
    # Получаем дату из URL или используем текущую дату
    lesson_date = request.GET.get('date', None)
    if lesson_date:
        try:
            # Преобразуем строку даты в объект date
            lesson_date = datetime.strptime(lesson_date, '%Y-%m-%d').date()
        except ValueError:
            # Если формат даты неверный, используем текущую дату
            lesson_date = timezone.now().date()
    else:
        # Если дата не указана, используем текущую дату
        lesson_date = timezone.now().date()
    
    # Получаем материалы для занятия
    materials = LessonMaterial.objects.filter(schedule=schedule).order_by('-created_at')
    
    # Также получаем существующие материалы занятий для конкретной даты
    try:
        classwork_files = schedule.materials.filter(
            material_type='lesson_specific',
            date=lesson_date
        ).order_by('-date')
        materials = list(materials) + list(classwork_files)
    except Exception as e:
        # Если возникла ошибка, просто используем только новые материалы
        print(f"Error retrieving classwork files: {e}")
    
    # Если пользователь - студент, получаем его оценки
    student_grades = None
    if request.user.is_student:
        student = request.user.student_profile
        student_grades = StudentLessonGrade.objects.filter(
            student=student,
            schedule=schedule
        ).order_by('-date')
    
    context = {
        'schedule': schedule,
        'materials': materials,
        'student_grades': student_grades,
    }
    
    return render(request, 'core/schedule_detail.html', context)


def student_schedule(request):
    """
    Отображает расписание занятий студента в формате календаря, похожем на расписание учителя.
    Также доступно родителям для просмотра расписания своих детей.
    """
    from django.contrib.auth.decorators import login_required
    from django.http import HttpResponseForbidden
    from django.shortcuts import get_object_or_404, redirect
    from accounts.models import Student, Parent
    from classes.models import ClassSchedule, Class
    from classes.models_lesson import StudentLessonGrade
    from datetime import datetime, timedelta, date
    import calendar
    from django.utils import timezone
    from django.db.models import Min
    from django.contrib import messages
    
    @login_required
    def view_func(request):
        student_id = request.GET.get('student_id')
        
        # Если пользователь - родитель, проверяем доступ к ученику
        if request.user.is_parent:
            if not student_id:
                # Если не указан ID ученика, перенаправляем на домашнюю страницу
                messages.error(request, "Выберите ученика для просмотра его расписания.")
                return redirect('core:home')
            
            try:
                # Проверяем, что родитель имеет доступ к этому ученику
                parent = Parent.objects.get(user=request.user)
                student = get_object_or_404(Student, id=student_id, parent=parent)
            except (Parent.DoesNotExist, Student.DoesNotExist):
                messages.error(request, "У вас нет доступа к этому ученику.")
                return redirect('core:home')
        elif request.user.is_student:
            # Если пользователь - студент, получаем его профиль
            student = get_object_or_404(Student, user=request.user)
        else:
            # Другие пользователи не имеют доступа
            return HttpResponseForbidden("Эта страница доступна только студентам и их родителям.")
        
        # Получаем все классы студента
        enrollments = student.enrollments.filter(is_active=True)
        class_ids = [enrollment.class_obj.id for enrollment in enrollments]
        enrollment_dates = {enrollment.class_obj.id: enrollment.enrollment_date for enrollment in enrollments}
        
        # Получаем все расписания для этих классов
        schedules = ClassSchedule.objects.filter(class_obj__id__in=class_ids).select_related('class_obj')
        
        # Получаем оценки студента за уроки
        lesson_grades = StudentLessonGrade.objects.filter(student=student)
        # Создаем словарь для быстрого доступа к оценкам по классу и дате
        grades_dict = {}
        for grade in lesson_grades:
            # Ключ - ID класса и дата урока
            key = (grade.lesson.class_obj.id, grade.lesson.date)
            grades_dict[key] = grade.grade
        
        # Получаем текущую дату и смещение недели
        today = timezone.localdate()
        week_offset = int(request.GET.get('week_offset', 0))
        
        # Вычисляем начало и конец недели
        start_of_week = today + timedelta(days=-today.weekday(), weeks=week_offset)
        end_of_week = start_of_week + timedelta(days=6)
        
        # Смещения для навигации
        prev_week_offset = week_offset - 1
        next_week_offset = week_offset + 1
        
        # Создаем календарь на неделю
        calendar_days = []
        current_date = start_of_week
        
        while current_date <= end_of_week:
            day_schedules = []
            
            # Для каждого расписания проверяем, есть ли занятие в этот день
            for schedule in schedules:
                # Проверяем, совпадает ли день недели
                if schedule.day_of_week == current_date.weekday():
                    # Проверяем, что дата зачисления раньше текущей даты
                    enrollment_date = enrollment_dates.get(schedule.class_obj.id)
                    # Убедимся, что оба объекта являются date
                    current_date_as_date = current_date
                    if hasattr(current_date, 'date'):
                        current_date_as_date = current_date.date()
                        
                    enrollment_date_as_date = enrollment_date
                    if hasattr(enrollment_date, 'date'):
                        enrollment_date_as_date = enrollment_date.date()
                        
                    if enrollment_date and enrollment_date_as_date <= current_date_as_date:
                        # Проверяем, есть ли оценка за этот урок
                        grade = grades_dict.get((schedule.class_obj.id, current_date))
                        day_schedules.append({
                            'schedule': schedule,
                            'enrollment_date': enrollment_date,
                            'grade': grade
                        })
            
            calendar_days.append({
                'date': current_date,
                'schedules': day_schedules
            })
            
            current_date += timedelta(days=1)
        
        context = {
            'today': today,
            'calendar_days': calendar_days,
            'start_of_week': start_of_week,
            'end_of_week': end_of_week,
            'prev_week_offset': prev_week_offset,
            'next_week_offset': next_week_offset,
            'enrollment_dates': enrollment_dates,
        }
        
        return render(request, 'core/student_schedule.html', context)
    
    return view_func(request)


def student_statistics(request, student_id=None):
    """
    Отображает подробную статистику успеваемости студента.
    Включает статистику по домашним заданиям, посещаемости и оценкам.
    """
    from django.contrib.auth.decorators import login_required
    from django.http import HttpResponseForbidden
    from django.shortcuts import get_object_or_404, redirect, render
    from accounts.models import Student
    from classes.models import HomeworkSubmission, Homework
    from classes.models_lesson import StudentLessonGrade
    from attendance.models import Attendance
    from django.db.models import Count, Avg, F, ExpressionWrapper, fields, Q, Case, When, Value, IntegerField
    from django.utils import timezone
    from datetime import timedelta
    import math
    
    # Определяем функцию render_student_statistics вне декоратора login_required
    def render_student_statistics(request, student):
        # 1. Процент выполненных домашних заданий
        # Получаем все домашние задания для классов студента
        enrollments = student.enrollments.filter(is_active=True)
        class_ids = [enrollment.class_obj.id for enrollment in enrollments]
        
        # Получаем все домашние задания для этих классов
        homework_assignments = Homework.objects.filter(class_obj__id__in=class_ids)
        
        # Получаем все выполненные домашние задания студента
        homework_submissions = HomeworkSubmission.objects.filter(student=student)
        
        # Рассчитываем процент выполненных заданий
        total_homework = homework_assignments.count()
        completed_homework = homework_submissions.count()
        
        homework_completion_rate = 0
        if total_homework > 0:
            homework_completion_rate = round((completed_homework / total_homework) * 100)
        
        # 2. Насколько вовремя сдаются домашние задания
        on_time_submissions = 0
        late_submissions = 0
        
        for submission in homework_submissions:
            if submission.submission_date.date() <= submission.homework.due_date:
                on_time_submissions += 1
            else:
                late_submissions += 1
        
        on_time_rate = 0
        if completed_homework > 0:
            on_time_rate = round((on_time_submissions / completed_homework) * 100)
        
        # 3. Процент посещаемости
        attendance_stats = Attendance.objects.filter(student=student)
        total_attendance = attendance_stats.count()
        present_attendance = attendance_stats.filter(status='present').count()
        
        attendance_rate = 0
        if total_attendance > 0:
            attendance_rate = round((present_attendance / total_attendance) * 100)
        
        # 4. Процент оценок за урок
        lesson_grades = StudentLessonGrade.objects.filter(student=student)
        total_lesson_grades = lesson_grades.count()
        
        # Распределение оценок за урок
        excellent_lesson_grades = lesson_grades.filter(grade__gte=90).count()
        good_lesson_grades = lesson_grades.filter(grade__gte=75, grade__lt=90).count()
        average_lesson_grades = lesson_grades.filter(grade__gte=60, grade__lt=75).count()
        poor_lesson_grades = lesson_grades.filter(grade__lt=60).count()
        
        lesson_grade_distribution = {
            'excellent': round((excellent_lesson_grades / total_lesson_grades) * 100) if total_lesson_grades > 0 else 0,
            'good': round((good_lesson_grades / total_lesson_grades) * 100) if total_lesson_grades > 0 else 0,
            'average': round((average_lesson_grades / total_lesson_grades) * 100) if total_lesson_grades > 0 else 0,
            'poor': round((poor_lesson_grades / total_lesson_grades) * 100) if total_lesson_grades > 0 else 0
        }
        
        # 5. Процент оценок за домашние задания
        graded_homework = homework_submissions.exclude(grade=None)
        total_homework_grades = graded_homework.count()
        
        # Распределение оценок за домашние задания
        excellent_homework_grades = graded_homework.filter(grade__gte=90).count()
        good_homework_grades = graded_homework.filter(grade__gte=75, grade__lt=90).count()
        average_homework_grades = graded_homework.filter(grade__gte=60, grade__lt=75).count()
        poor_homework_grades = graded_homework.filter(grade__lt=60).count()
        
        homework_grade_distribution = {
            'excellent': round((excellent_homework_grades / total_homework_grades) * 100) if total_homework_grades > 0 else 0,
            'good': round((good_homework_grades / total_homework_grades) * 100) if total_homework_grades > 0 else 0,
            'average': round((average_homework_grades / total_homework_grades) * 100) if total_homework_grades > 0 else 0,
            'poor': round((poor_homework_grades / total_homework_grades) * 100) if total_homework_grades > 0 else 0
        }
        
        # Дополнительная статистика для графиков
        # Посещаемость по месяцам
        from datetime import datetime
        import calendar
        
        # Получаем последние 6 месяцев
        current_date = timezone.now().date()
        monthly_attendance = {}
        
        # Используем правильные названия месяцев на русском
        month_names_ru = {
            1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель', 5: 'Май', 6: 'Июнь',
            7: 'Июль', 8: 'Август', 9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
        }
        
        # Получаем данные за последние 6 месяцев
        for i in range(5, -1, -1):  # От 5 до 0 (последние 6 месяцев в обратном порядке)
            # Вычисляем месяц и год
            month = current_date.month - i
            year = current_date.year
            
            # Корректируем месяц и год, если месяц отрицательный
            while month <= 0:
                month += 12
                year -= 1
            
            # Первый день месяца
            month_start = datetime(year, month, 1).date()
            
            # Последний день месяца
            if month == 12:
                month_end = datetime(year + 1, 1, 1).date()
            else:
                month_end = datetime(year, month + 1, 1).date()
            
            # Получаем название месяца на русском
            month_name = month_names_ru[month]
            
            # Считаем статистику посещаемости
            month_total = attendance_stats.filter(date__gte=month_start, date__lt=month_end).count()
            month_present = attendance_stats.filter(date__gte=month_start, date__lt=month_end, status='present').count()
            
            if month_total > 0:
                monthly_attendance[month_name] = round((month_present / month_total) * 100)
            else:
                monthly_attendance[month_name] = 0
        
        context = {
            'student': student,
            'homework_completion_rate': homework_completion_rate,
            'on_time_rate': on_time_rate,
            'attendance_rate': attendance_rate,
            'lesson_grade_distribution': lesson_grade_distribution,
            'homework_grade_distribution': homework_grade_distribution,
            'monthly_attendance': monthly_attendance,
            'total_homework': total_homework,
            'completed_homework': completed_homework,
            'on_time_submissions': on_time_submissions,
            'late_submissions': late_submissions,
            'total_attendance': total_attendance,
            'present_attendance': present_attendance,
            'total_lesson_grades': total_lesson_grades,
            'total_homework_grades': total_homework_grades
        }
        
        return render(request, 'core/student_statistics.html', context)
    
    @login_required
    def view_func(request):
        # Проверка прав доступа
        if not request.user.is_student and not request.user.is_parent:
            return HttpResponseForbidden("Эта страница доступна только студентам и родителям.")
        
        # Получаем student_id из URL или GET-параметра
        local_student_id = student_id
        if local_student_id is None:
            local_student_id = request.GET.get('student_id')
        
        # Если это студент и не указан ID, используем его профиль
        if request.user.is_student and not local_student_id:
            student = request.user.student_profile
            return render_student_statistics(request, student)
        
        # Если указан ID студента
        if local_student_id:
            try:
                student = Student.objects.get(id=local_student_id)
                return render_student_statistics(request, student)
            except Student.DoesNotExist:
                pass
        
        # Если это родитель и не указан ID студента или студент не найден
        if request.user.is_parent:
            parent = request.user.get_parent_profile()
            children = parent.children.all()
            
            if children.count() == 1:
                # Если только один ребенок, сразу показываем его статистику
                student = children.first()
                return render_student_statistics(request, student)
            
            # Если несколько детей, показываем список для выбора
            return render(request, 'core/parent_children_list.html', {'children': children})
        
        # Если не студент и не родитель, возвращаем ошибку доступа
        return HttpResponseForbidden("Эта страница доступна только студентам и родителям.")
    
    def render_student_statistics(request, student):
        # 1. Процент выполненных домашних заданий
        # Получаем все домашние задания для классов студента
        enrollments = student.enrollments.filter(is_active=True)
        class_ids = [enrollment.class_obj.id for enrollment in enrollments]
        
        # Получаем все домашние задания для этих классов
        homework_assignments = Homework.objects.filter(class_obj__id__in=class_ids)
        
        # Получаем все выполненные домашние задания студента
        homework_submissions = HomeworkSubmission.objects.filter(student=student)
        
        # Рассчитываем процент выполненных заданий
        total_homework = homework_assignments.count()
        completed_homework = homework_submissions.count()
        
        homework_completion_rate = 0
        if total_homework > 0:
            homework_completion_rate = round((completed_homework / total_homework) * 100)
        
        # 2. Насколько вовремя сдаются домашние задания
        on_time_submissions = 0
        late_submissions = 0
        
        for submission in homework_submissions:
            if submission.submission_date.date() <= submission.homework.due_date:
                on_time_submissions += 1
            else:
                late_submissions += 1
        
        on_time_rate = 0
        if completed_homework > 0:
            on_time_rate = round((on_time_submissions / completed_homework) * 100)
        
        # 3. Процент посещаемости
        attendance_stats = Attendance.objects.filter(student=student)
        total_attendance = attendance_stats.count()
        present_attendance = attendance_stats.filter(status='present').count()
        
        attendance_rate = 0
        if total_attendance > 0:
            attendance_rate = round((present_attendance / total_attendance) * 100)
        
        # 4. Процент оценок за урок
        lesson_grades = StudentLessonGrade.objects.filter(student=student)
        total_lesson_grades = lesson_grades.count()
        
        # Распределение оценок за урок
        excellent_lesson_grades = lesson_grades.filter(grade__gte=90).count()
        good_lesson_grades = lesson_grades.filter(grade__gte=75, grade__lt=90).count()
        average_lesson_grades = lesson_grades.filter(grade__gte=60, grade__lt=75).count()
        poor_lesson_grades = lesson_grades.filter(grade__lt=60).count()
        
        # 5. Процент оценок за домашние задания
        homework_grades = homework_submissions.exclude(grade=None)
        total_homework_grades = homework_grades.count()
        
        # Распределение оценок за домашние задания
        excellent_homework_grades = homework_grades.filter(grade__gte=90).count()
        good_homework_grades = homework_grades.filter(grade__gte=75, grade__lt=90).count()
        average_homework_grades = homework_grades.filter(grade__gte=60, grade__lt=75).count()
        poor_homework_grades = homework_grades.filter(grade__lt=60).count()
        
        # Средние оценки
        avg_lesson_grade = lesson_grades.aggregate(Avg('grade'))['grade__avg'] or 0
        avg_homework_grade = homework_grades.aggregate(Avg('grade'))['grade__avg'] or 0
        
        # Формируем контекст для шаблона
        context = {
            'student': student,
            'homework_completion_rate': homework_completion_rate,
            'on_time_rate': on_time_rate,
            'attendance_rate': attendance_rate,
            'avg_lesson_grade': round(avg_lesson_grade, 1),
            'avg_homework_grade': round(avg_homework_grade, 1),
            'excellent_lesson_grades': excellent_lesson_grades,
            'good_lesson_grades': good_lesson_grades,
            'average_lesson_grades': average_lesson_grades,
            'poor_lesson_grades': poor_lesson_grades,
            'excellent_homework_grades': excellent_homework_grades,
            'good_homework_grades': good_homework_grades,
            'average_homework_grades': average_homework_grades,
            'poor_homework_grades': poor_homework_grades,
            'total_homework': total_homework,
            'completed_homework': completed_homework,
            'on_time_submissions': on_time_submissions,
            'late_submissions': late_submissions,
            'total_attendance': total_attendance,
            'present_attendance': present_attendance,
            'total_lesson_grades': total_lesson_grades,
            'total_homework_grades': total_homework_grades
        }
        
        return render(request, 'core/student_statistics.html', context)
        
        lesson_grade_distribution = {
            'excellent': round((excellent_lesson_grades / total_lesson_grades) * 100) if total_lesson_grades > 0 else 0,
            'good': round((good_lesson_grades / total_lesson_grades) * 100) if total_lesson_grades > 0 else 0,
            'average': round((average_lesson_grades / total_lesson_grades) * 100) if total_lesson_grades > 0 else 0,
            'poor': round((poor_lesson_grades / total_lesson_grades) * 100) if total_lesson_grades > 0 else 0
        }
        
        # 5. Процент оценок за домашние задания
        graded_homework = homework_submissions.exclude(grade=None)
        total_homework_grades = graded_homework.count()
        
        # Распределение оценок за домашние задания
        excellent_homework_grades = graded_homework.filter(grade__gte=90).count()
        good_homework_grades = graded_homework.filter(grade__gte=75, grade__lt=90).count()
        average_homework_grades = graded_homework.filter(grade__gte=60, grade__lt=75).count()
        poor_homework_grades = graded_homework.filter(grade__lt=60).count()
        
        homework_grade_distribution = {
            'excellent': round((excellent_homework_grades / total_homework_grades) * 100) if total_homework_grades > 0 else 0,
            'good': round((good_homework_grades / total_homework_grades) * 100) if total_homework_grades > 0 else 0,
            'average': round((average_homework_grades / total_homework_grades) * 100) if total_homework_grades > 0 else 0,
            'poor': round((poor_homework_grades / total_homework_grades) * 100) if total_homework_grades > 0 else 0
        }
        
        # Дополнительная статистика для графиков
        # Посещаемость по месяцам
        from datetime import datetime
        import calendar
        
        # Получаем последние 6 месяцев
        current_date = timezone.now().date()
        monthly_attendance = {}
        
        # Используем правильные названия месяцев на русском
        month_names_ru = {
            1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель', 5: 'Май', 6: 'Июнь',
            7: 'Июль', 8: 'Август', 9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
        }
        
        # Получаем данные за последние 6 месяцев
        for i in range(5, -1, -1):  # От 5 до 0 (последние 6 месяцев в обратном порядке)
            # Вычисляем месяц и год
            month = current_date.month - i
            year = current_date.year
            
            # Корректируем месяц и год, если месяц отрицательный
            while month <= 0:
                month += 12
                year -= 1
            
            # Первый день месяца
            month_start = datetime(year, month, 1).date()
            
            # Последний день месяца
            if month == 12:
                month_end = datetime(year + 1, 1, 1).date()
            else:
                month_end = datetime(year, month + 1, 1).date()
            
            # Получаем название месяца на русском
            month_name = month_names_ru[month]
            
            # Считаем статистику посещаемости
            month_total = attendance_stats.filter(date__gte=month_start, date__lt=month_end).count()
            month_present = attendance_stats.filter(date__gte=month_start, date__lt=month_end, status='present').count()
            
            if month_total > 0:
                monthly_attendance[month_name] = round((month_present / month_total) * 100)
            else:
                monthly_attendance[month_name] = 0
        
        context = {
            'student': student,
            'homework_completion_rate': homework_completion_rate,
            'on_time_rate': on_time_rate,
            'attendance_rate': attendance_rate,
            'lesson_grade_distribution': lesson_grade_distribution,
            'homework_grade_distribution': homework_grade_distribution,
            'monthly_attendance': monthly_attendance,
            'total_homework': total_homework,
            'completed_homework': completed_homework,
            'on_time_submissions': on_time_submissions,
            'late_submissions': late_submissions,
            'total_attendance': total_attendance,
            'present_attendance': present_attendance,
            'total_lesson_grades': total_lesson_grades,
            'total_homework_grades': total_homework_grades
        }
        
        return render(request, 'core/student_statistics.html', context)
    
    return view_func(request)
