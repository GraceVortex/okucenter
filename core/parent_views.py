from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.utils import timezone
from datetime import timedelta

from accounts.models import Parent, Student
from classes.models import Enrollment, ClassSchedule, Homework, HomeworkSubmission
from attendance.models import CancellationRequest, StudentCancellationRequest

@login_required
def parent_home(request):
    """
    Главная страница для родителей, показывающая информацию о детях.
    """
    if not request.user.is_parent:
        return redirect('core:home')
    
    # Получаем родителя и его детей
    parent = get_object_or_404(Parent, user=request.user)
    children = Student.objects.filter(parent=parent)
    
    children_data = []
    pending_cancellations = 0
    
    for student in children:
        # Данные о ближайшем уроке
        next_class = None
        today = timezone.now().date()
        
        # Получаем все классы, в которых учится студент
        enrollments = Enrollment.objects.filter(student=student, is_active=True)
        class_ids = enrollments.values_list('class_obj_id', flat=True)
        
        # Получаем все расписания для этих классов
        schedules = ClassSchedule.objects.filter(class_obj_id__in=class_ids)
        
        # Находим ближайший урок
        next_lesson = None
        min_days_until = float('inf')
        
        for schedule in schedules:
            # Находим ближайшую дату для этого расписания
            next_date = today
            days_to_add = (schedule.day_of_week - today.weekday()) % 7
            
            if days_to_add == 0 and timezone.now().time() > schedule.start_time:
                days_to_add = 7  # Если сегодняшний урок уже прошел, берем следующую неделю
                
            next_date = today + timedelta(days=days_to_add)
            
            # Проверяем, не отменен ли урок
            is_cancelled = CancellationRequest.objects.filter(
                class_obj=schedule.class_obj,
                date=next_date,
                status='approved'
            ).exists()
            
            if not is_cancelled and days_to_add < min_days_until:
                min_days_until = days_to_add
                next_lesson = {
                    'schedule': schedule,
                    'date': next_date,
                    'days_until': days_to_add
                }
        
        if next_lesson:
            day_names = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
            next_class = {
                'class_name': next_lesson['schedule'].class_obj.name,
                'teacher': next_lesson['schedule'].class_obj.teacher.full_name,
                'room': next_lesson['schedule'].room,
                'start_time': next_lesson['schedule'].start_time.strftime('%H:%M'),
                'end_time': next_lesson['schedule'].end_time.strftime('%H:%M'),
                'date': next_lesson['date'],
                'day_name': day_names[next_lesson['date'].weekday()],
                'days_until': next_lesson['days_until']
            }
        
        # Данные о ближайшем домашнем задании
        next_homework = None
        
        # Получаем все невыполненные домашние задания для классов студента
        homeworks = Homework.objects.filter(
            class_obj_id__in=class_ids,
            due_date__gte=today
        ).order_by('due_date')
        
        # Исключаем уже выполненные задания
        for homework in homeworks:
            submission_exists = HomeworkSubmission.objects.filter(
                homework=homework,
                student=student
            ).exists()
            
            if not submission_exists:
                days_until = (homework.due_date - today).days
                deadline_passed = homework.due_date < today
                
                next_homework = {
                    'title': homework.title,
                    'class_name': homework.class_obj.name,
                    'due_date': homework.due_date,
                    'days_until': days_until,
                    'deadline_passed': deadline_passed
                }
                break
        
        # Получаем количество запросов на отмену
        student_cancellations = StudentCancellationRequest.objects.filter(
            student=student, 
            status='pending'
        ).count()
        
        pending_cancellations += student_cancellations
        
        # Расчет информации о балансе
        balance_info = {}
        balance_info['amount'] = student.balance
        
        # Получаем среднюю стоимость занятий для этого студента
        total_price = 0
        lesson_count = 0
        
        for enrollment in enrollments:
            total_price += enrollment.class_obj.price_per_lesson
            lesson_count += 1
        
        # Если у студента есть занятия, рассчитываем среднюю стоимость и прогноз
        if lesson_count > 0:
            avg_price_per_lesson = total_price / lesson_count
            
            # Рассчитываем, на сколько занятий хватит денег
            if avg_price_per_lesson > 0:
                lessons_left = student.balance / avg_price_per_lesson
                balance_info['lessons_left'] = int(lessons_left)
                
                # Рассчитываем примерную дату, когда закончатся деньги
                # Предполагаем, что в среднем студент посещает 2 занятия в неделю
                if lessons_left > 0:
                    weeks_left = lessons_left / 2  # 2 занятия в неделю
                    days_left = int(weeks_left * 7)
                    balance_info['days_left'] = days_left
                    balance_info['date_until'] = today + timedelta(days=days_left)
                else:
                    # Если баланс отрицательный, рассчитываем, с какого числа он в минусе
                    # Предполагаем, что в среднем студент тратит деньги на 2 занятия в неделю
                    negative_lessons = abs(lessons_left)
                    weeks_ago = negative_lessons / 2
                    days_ago = int(weeks_ago * 7)
                    balance_info['days_ago'] = days_ago
                    balance_info['date_since'] = today - timedelta(days=days_ago)
            else:
                balance_info['lessons_left'] = 0
        else:
            balance_info['lessons_left'] = 0
        
        children_data.append({
            'student': student,
            'next_class': next_class,
            'next_homework': next_homework,
            'pending_cancellations': student_cancellations,
            'balance_info': balance_info
        })
    
    context = {
        'children_data': children_data,
        'pending_cancellations': pending_cancellations
    }
    
    return render(request, 'core/parent_home.html', context)
