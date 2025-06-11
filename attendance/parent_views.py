from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.utils import timezone
from datetime import datetime, timedelta

from accounts.models import Parent, Student
from classes.models import Class, ClassSchedule, Enrollment
from .models import Attendance, StudentCancellationRequest
from .forms import StudentCancellationRequestForm

@login_required
def parent_child_cancel_lessons(request, student_id):
    """
    Представление для страницы отмены занятий ребенка родителем.
    Родитель может отменять занятия только для своих детей с типом PM (parent managed).
    """
    # Проверяем, что пользователь - родитель
    if not request.user.is_parent:
        return HttpResponseForbidden("Только родители могут отменять занятия своих детей.")
    
    # Получаем профиль родителя и студента
    parent = get_object_or_404(Parent, user=request.user)
    student = get_object_or_404(Student, id=student_id)
    
    # Проверяем, что студент - ребенок этого родителя
    if student.parent != parent:
        return HttpResponseForbidden("Вы можете отменять занятия только своих детей.")
    
    # Проверяем, что студент не является самоуправляемым (то есть имеет тип PM - parent managed)
    if student.is_self_managed:
        return HttpResponseForbidden("Вы не можете отменять занятия для самоуправляемых студентов. Студент должен сделать это самостоятельно.")
    
    # Получаем список классов, на которые записан студент
    enrollments = Enrollment.objects.filter(student=student, is_active=True)
    
    # Получаем предстоящие занятия для этих классов
    today = timezone.now().date()
    upcoming_lessons = []
    
    for enrollment in enrollments:
        class_obj = enrollment.class_obj
        schedules = ClassSchedule.objects.filter(class_obj=class_obj)
        
        for schedule in schedules:
            # Вычисляем ближайшие даты для этого расписания
            next_dates = []
            days_ahead = 0
            
            # Получаем следующие 30 дней
            while len(next_dates) < 5 and days_ahead < 30:
                next_day = today + timedelta(days=days_ahead)
                if next_day.weekday() == schedule.day_of_week:
                    next_dates.append(next_day)
                days_ahead += 1
            
            for date in next_dates:
                # Проверяем, есть ли уже посещаемость на эту дату
                attendance_exists = Attendance.objects.filter(
                    student=student,
                    class_obj=class_obj,
                    date=date
                ).exists()
                
                # Проверяем, есть ли уже запрос на отмену
                cancellation_request_exists = StudentCancellationRequest.objects.filter(
                    student=student,
                    class_obj=class_obj,
                    date=date
                ).exists()
                
                # Проверяем, можно ли отменить занятие (не менее чем за 24 часа)
                # Создаем aware datetime с учетом часового пояса
                lesson_datetime = timezone.make_aware(datetime.combine(date, schedule.start_time))
                can_cancel = (lesson_datetime - timezone.now()) > timedelta(hours=24)
                
                if not attendance_exists and not cancellation_request_exists:
                    upcoming_lessons.append({
                        'class': class_obj,
                        'schedule': schedule,
                        'date': date,
                        'can_cancel': can_cancel
                    })
    
    # Сортируем по дате
    upcoming_lessons.sort(key=lambda x: (x['date'], x['schedule'].start_time))
    
    context = {
        'upcoming_lessons': upcoming_lessons,
        'student': student
    }
    
    return render(request, 'attendance/parent_child_cancel_lessons.html', context)

@login_required
def parent_child_cancellation_requests(request, student_id):
    """
    Представление для просмотра списка запросов на отмену занятий ребенка родителем.
    """
    # Проверяем, что пользователь - родитель
    if not request.user.is_parent:
        return HttpResponseForbidden("Только родители могут просматривать запросы на отмену занятий своих детей.")
    
    # Получаем профиль родителя и студента
    parent = get_object_or_404(Parent, user=request.user)
    student = get_object_or_404(Student, id=student_id)
    
    # Проверяем, что студент - ребенок этого родителя
    if student.parent != parent:
        return HttpResponseForbidden("Вы можете просматривать запросы на отмену занятий только своих детей.")
    
    # Получаем запросы на отмену занятий
    cancellation_requests = StudentCancellationRequest.objects.filter(student=student).order_by('-created_at')
    
    context = {
        'cancellation_requests': cancellation_requests,
        'student': student
    }
    
    return render(request, 'attendance/parent_child_cancellation_requests.html', context)
