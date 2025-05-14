from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from .models import Class, ClassSchedule, Enrollment, Homework, HomeworkSubmission, ClassworkFile
from accounts.models import Teacher, Student, Parent
from .forms import ClassForm, ClassScheduleForm, HomeworkForm, HomeworkSubmissionForm, AddStudentForm, HomeworkGradeForm, ClassworkFileForm
from datetime import datetime, timedelta, date as datetime_date
import os
import logging
from django.utils import timezone
from attendance.models import Attendance, Mark
from django.core.exceptions import ValidationError

# Create your views here.

@login_required
def class_list(request):
    """Отображает список всех классов."""
    if request.user.is_admin or request.user.is_reception:
        # Администраторы и ресепшн видят все классы
        classes = Class.objects.all().order_by('name')
    elif request.user.is_teacher:
        # Учителя видят только свои классы
        teacher = get_object_or_404(Teacher, user=request.user)
        classes = Class.objects.filter(teacher=teacher).order_by('name')
    elif request.user.is_student:
        # Студенты видят классы, на которые они записаны
        student = get_object_or_404(Student, user=request.user)
        enrollments = Enrollment.objects.filter(student=student)
        classes = Class.objects.filter(enrollments__in=enrollments).order_by('name')
    else:
        # Родители видят классы своих детей
        classes = Class.objects.filter(
            enrollments__student__parent__user=request.user
        ).distinct().order_by('name')
    
    return render(request, 'classes/class_list.html', {'classes': classes})

@login_required
def teacher_classes(request):
    """Отображает список классов учителя с дополнительной информацией."""
    if not request.user.is_teacher:
        return HttpResponseForbidden("Эта страница доступна только учителям.")
    
    teacher = get_object_or_404(Teacher, user=request.user)
    classes = Class.objects.filter(teacher=teacher).order_by('name')
    
    # Получаем дополнительную информацию для каждого класса
    classes_with_info = []
    for class_obj in classes:
        # Количество студентов в классе
        student_count = Enrollment.objects.filter(class_obj=class_obj).count()
        
        # Ближайшее занятие
        upcoming_schedule = ClassSchedule.objects.filter(
            class_obj=class_obj,
            day_of_week__gte=datetime.now().weekday()
        ).order_by('day_of_week', 'start_time').first()
        
        if not upcoming_schedule:
            # Если нет занятий на этой неделе, ищем на следующей
            upcoming_schedule = ClassSchedule.objects.filter(
                class_obj=class_obj
            ).order_by('day_of_week', 'start_time').first()
        
        # Количество непроверенных домашних заданий
        unchecked_homework_count = HomeworkSubmission.objects.filter(
            homework__class_obj=class_obj,
            completion_status__isnull=True  # Не проверенные задания не имеют статуса выполнения
        ).count()
        
        classes_with_info.append({
            'class': class_obj,
            'student_count': student_count,
            'upcoming_schedule': upcoming_schedule,
            'unchecked_homework': unchecked_homework_count
        })
    
    return render(request, 'classes/teacher_classes.html', {
        'classes_with_info': classes_with_info,
        'teacher': teacher
    })

@login_required
def class_detail(request, class_id):
    """Отображает детальную информацию о классе."""
    class_obj = get_object_or_404(Class, id=class_id)
    
    # Проверка доступа
    has_access = False
    
    # Администраторы, ресепшен и учителя этого класса имеют доступ
    if (request.user.is_admin or request.user.is_reception or 
        (request.user.is_teacher and class_obj.teacher.user == request.user)):
        has_access = True
    
    # Студенты имеют доступ только к своим классам
    if request.user.is_student:
        student = Student.objects.get(user=request.user)
        if Enrollment.objects.filter(student=student, class_obj=class_obj).exists():
            has_access = True
    
    if not has_access:
        return HttpResponseForbidden("У вас нет доступа к этой странице.")
    
    schedules = ClassSchedule.objects.filter(class_obj=class_obj).order_by('day_of_week', 'start_time')
    enrollments = Enrollment.objects.filter(class_obj=class_obj).select_related('student')
    homeworks = Homework.objects.filter(class_obj=class_obj).order_by('-date')
    
    # Расчет статистики класса
    from attendance.models import Attendance
    
    # Количество проведенных занятий
    total_lessons = Attendance.objects.filter(
        class_obj=class_obj, 
        teacher_confirmed=True
    ).values('date').distinct().count()
    
    # Средняя посещаемость
    total_attendances = Attendance.objects.filter(
        class_obj=class_obj, 
        teacher_confirmed=True
    ).count()
    
    present_attendances = Attendance.objects.filter(
        class_obj=class_obj, 
        teacher_confirmed=True,
        status='present'
    ).count()
    
    avg_attendance = 0
    if total_attendances > 0:
        avg_attendance = round((present_attendances / total_attendances) * 100)
    
    # Количество выполненных домашних заданий
    completed_homeworks = HomeworkSubmission.objects.filter(
        homework__class_obj=class_obj
    ).count()
    
    class_stats = {
        'total_lessons': total_lessons,
        'avg_attendance': avg_attendance,
        'completed_homeworks': completed_homeworks
    }
    
    context = {
        'class': class_obj,
        'schedules': schedules,
        'enrollments': enrollments,
        'homeworks': homeworks,
        'class_stats': class_stats,
    }
    
    # Если пользователь - студент, добавляем его домашние задания
    if request.user.is_student:
        student = Student.objects.get(user=request.user)
        submissions = HomeworkSubmission.objects.filter(
            student=student,
            homework__class_obj=class_obj
        ).select_related('homework')
        context['submissions'] = submissions
    
    # Если пользователь - учитель этого класса или администратор, добавляем все отправленные домашние задания
    if request.user.is_admin or (request.user.is_teacher and class_obj.teacher.user == request.user):
        # Получаем все домашние задания с отправленными заданиями
        homeworks_with_submissions = []
        for homework in homeworks:
            submissions = HomeworkSubmission.objects.filter(
                homework=homework
            ).select_related('student')
            
            if submissions.exists():
                homeworks_with_submissions.append({
                    'homework': homework,
                    'submissions': submissions,
                    'count': submissions.count()
                })
            else:
                homeworks_with_submissions.append({
                    'homework': homework,
                    'submissions': [],
                    'count': 0
                })
        
        context['homeworks_with_submissions'] = homeworks_with_submissions
    
    return render(request, 'classes/class_detail.html', context)

@login_required
def create_class(request):
    """Создает новый класс."""
    if not (request.user.is_admin or request.user.is_reception):
        return HttpResponseForbidden("У вас нет прав для создания классов.")
    
    if request.method == 'POST':
        form = ClassForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Класс успешно создан.")
            return redirect('classes:class_list')
    else:
        form = ClassForm()
    
    return render(request, 'classes/class_form.html', {'form': form, 'title': 'Создать класс'})

@login_required
def update_class(request, class_id):
    """Обновляет информацию о классе."""
    class_obj = get_object_or_404(Class, id=class_id)
    
    if not (request.user.is_admin or request.user.is_reception or 
            (request.user.is_teacher and class_obj.teacher.user == request.user)):
        return HttpResponseForbidden("У вас нет прав для редактирования этого класса.")
    
    if request.method == 'POST':
        form = ClassForm(request.POST, instance=class_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Информация о классе успешно обновлена.")
            return redirect('classes:class_detail', class_id=class_obj.id)
    else:
        form = ClassForm(instance=class_obj)
    
    return render(request, 'classes/class_form.html', {'form': form, 'title': 'Редактировать класс'})

@login_required
def delete_class(request, class_id):
    """Удаляет класс."""
    class_obj = get_object_or_404(Class, id=class_id)
    
    if not (request.user.is_admin or request.user.is_reception):
        return HttpResponseForbidden("У вас нет прав для удаления классов.")
    
    if request.method == 'POST':
        class_obj.delete()
        messages.success(request, "Класс успешно удален.")
        return redirect('classes:class_list')
    
    return render(request, 'classes/class_confirm_delete.html', {'class': class_obj})

@login_required
def add_schedule(request, class_id):
    """Добавляет расписание для класса."""
    class_obj = get_object_or_404(Class, id=class_id)
    
    if not (request.user.is_admin or request.user.is_reception or 
            (request.user.is_teacher and class_obj.teacher.user == request.user)):
        return HttpResponseForbidden("У вас нет прав для добавления расписания.")
    
    if request.method == 'POST':
        form = ClassScheduleForm(request.POST)
        if form.is_valid():
            # Получаем выбранные дни недели и временной интервал
            days_of_week = form.cleaned_data['days_of_week']
            time_slot = form.cleaned_data['time_slot']
            room = form.cleaned_data['room']
            
            # Разбиваем временной интервал на время начала и окончания
            start_time = time_slot
            
            # Вычисляем время окончания (начало + 1.5 часа)
            start_time_obj = datetime.strptime(start_time, '%H:%M:%S')
            end_time_obj = start_time_obj + timedelta(hours=1, minutes=30)
            end_time = end_time_obj.strftime('%H:%M:%S')
            
            # Создаем расписание для каждого выбранного дня недели
            schedules_created = 0
            for day in days_of_week:
                # Проверяем, не существует ли уже такое расписание
                existing_schedule = ClassSchedule.objects.filter(
                    class_obj=class_obj,
                    day_of_week=int(day),
                    start_time=start_time,
                    end_time=end_time,
                    room=room
                ).exists()
                
                if not existing_schedule:
                    # Создаем объект без вызова валидации
                    schedule = ClassSchedule()
                    schedule.class_obj = class_obj
                    schedule.day_of_week = int(day)
                    schedule.start_time = start_time
                    schedule.end_time = end_time
                    schedule.room = room
                    # Теперь сохраняем объект
                    try:
                        schedule.save()
                        schedules_created += 1
                    except Exception as e:
                        messages.error(request, f"Ошибка при сохранении расписания: {str(e)}")
            
            if schedules_created > 0:
                messages.success(request, f"Расписание успешно добавлено для {schedules_created} дней недели.")
            else:
                messages.warning(request, "Расписание с такими параметрами уже существует.")
            
            return redirect('classes:class_detail', class_id=class_obj.id)
    else:
        form = ClassScheduleForm()
    
    return render(request, 'classes/schedule_form.html', {
        'form': form, 
        'class': class_obj,
        'title': 'Добавить расписание'
    })

@login_required
def update_schedule(request, schedule_id):
    """Обновляет расписание занятий."""
    schedule = get_object_or_404(ClassSchedule, id=schedule_id)
    class_obj = schedule.class_obj
    
    if not (request.user.is_admin or request.user.is_reception or 
            (request.user.is_teacher and class_obj.teacher.user == request.user)):
        return HttpResponseForbidden("У вас нет прав для изменения расписания.")
    
    # Находим соответствующий временной интервал
    start_time_str = schedule.start_time.strftime('%H:%M:%S')
    
    # Определяем начальные значения для формы
    initial_data = {
        'room': schedule.room,
    }
    
    # Находим соответствующий временной слот
    for value, _ in ClassScheduleForm.TIME_SLOTS:
        if value == start_time_str:
            initial_data['time_slot'] = value
            break
    
    if request.method == 'POST':
        form = ClassScheduleForm(request.POST)
        if form.is_valid():
            # Получаем данные из формы
            time_slot = form.cleaned_data['time_slot']
            room = form.cleaned_data['room']
            
            # Вычисляем время окончания (начало + 1.5 часа)
            start_time_obj = datetime.strptime(time_slot, '%H:%M:%S')
            end_time_obj = start_time_obj + timedelta(hours=1, minutes=30)
            end_time = end_time_obj.strftime('%H:%M:%S')
            
            # Обновляем расписание
            schedule.start_time = time_slot
            schedule.end_time = end_time
            schedule.room = room
            schedule.save()
            
            messages.success(request, "Расписание успешно обновлено.")
            return redirect('classes:class_detail', class_id=class_obj.id)
    else:
        form = ClassScheduleForm(initial=initial_data)
    
    return render(request, 'classes/schedule_form.html', {
        'form': form,
        'class': class_obj,
        'title': 'Изменить расписание',
        'is_update': True,
        'schedule': schedule
    })

@login_required
def delete_schedule(request, schedule_id):
    """Удаляет расписание занятий."""
    schedule = get_object_or_404(ClassSchedule, id=schedule_id)
    class_obj = schedule.class_obj
    
    if not (request.user.is_admin or request.user.is_reception or 
            (request.user.is_teacher and class_obj.teacher.user == request.user)):
        return HttpResponseForbidden("У вас нет прав для удаления расписания.")
    
    if request.method == 'POST':
        schedule.delete()
        messages.success(request, "Расписание успешно удалено.")
        return redirect('classes:class_detail', class_id=class_obj.id)
    
    return render(request, 'classes/confirm_delete.html', {
        'object': f"расписание на {schedule.get_day_of_week_display()} ({schedule.start_time.strftime('%H:%M')} - {schedule.end_time.strftime('%H:%M')})",
        'back_url': 'classes:class_detail',
        'back_id': class_obj.id
    })

@login_required
def add_homework(request, class_id):
    """Добавляет домашнее задание для класса."""
    class_obj = get_object_or_404(Class, id=class_id)
    
    if not (request.user.is_admin or 
            (request.user.is_teacher and class_obj.teacher.user == request.user)):
        return HttpResponseForbidden("У вас нет прав для добавления домашнего задания.")
    
    if request.method == 'POST':
        print(f"POST data: {request.POST}")
        form = HomeworkForm(request.POST, request.FILES)
        print(f"Form data before validation: {form.data}")
        if form.is_valid():
            print("Form is valid")
            homework = form.save(commit=False)
            homework.class_obj = class_obj
            print(f"Homework object before save: {homework.__dict__}")
            try:
                homework.save()
                messages.success(request, "Домашнее задание успешно добавлено.")
                return redirect('classes:class_detail', class_id=class_obj.id)
            except Exception as e:
                print(f"Error saving homework: {str(e)}")
                messages.error(request, f"Ошибка при сохранении домашнего задания: {str(e)}")
        else:
            print(f"Form is invalid. Errors: {form.errors}")
            # Добавляем сообщение об ошибках формы
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Ошибка в поле {field}: {error}")
    else:
        form = HomeworkForm()
    
    return render(request, 'classes/homework_form.html', {
        'form': form, 
        'class': class_obj,
        'title': 'Добавить домашнее задание'
    })

@login_required
def submit_homework(request, homework_id):
    """Отправляет выполненное домашнее задание."""
    homework = get_object_or_404(Homework, id=homework_id)
    class_obj = homework.class_obj
    
    # Проверка доступа
    if not request.user.is_student:
        return HttpResponseForbidden("Только студенты могут отправлять домашние задания.")
    
    student = get_object_or_404(Student, user=request.user)
    
    # Проверка, что студент записан на этот класс
    if not Enrollment.objects.filter(student=student, class_obj=class_obj).exists():
        return HttpResponseForbidden("Вы не записаны на этот класс.")
    
    # Проверка, не отправлял ли студент уже домашнее задание
    if HomeworkSubmission.objects.filter(homework=homework, student=student).exists():
        messages.warning(request, "Вы уже отправили домашнее задание.")
        return redirect('classes:class_detail', class_id=class_obj.id)
    
    if request.method == 'POST':
        form = HomeworkSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.homework = homework
            submission.student = student
            submission.save()
            messages.success(request, "Домашнее задание успешно отправлено.")
            return redirect('classes:all_student_homework')
    else:
        form = HomeworkSubmissionForm()
    
    return render(request, 'classes/submit_homework.html', {
        'form': form,
        'homework': homework,
        'class': class_obj
    })

@login_required
def update_homework(request, homework_id):
    """Обновляет домашнее задание."""
    homework = get_object_or_404(Homework, id=homework_id)
    class_obj = homework.class_obj
    
    if not (request.user.is_admin or 
            (request.user.is_teacher and class_obj.teacher.user == request.user)):
        return HttpResponseForbidden("У вас нет прав для редактирования домашнего задания.")
    
    if request.method == 'POST':
        form = HomeworkForm(request.POST, request.FILES, instance=homework)
        if form.is_valid():
            form.save()
            messages.success(request, "Домашнее задание успешно обновлено.")
            return redirect('classes:class_detail', class_id=class_obj.id)
    else:
        form = HomeworkForm(instance=homework)
    
    return render(request, 'classes/homework_form.html', {
        'form': form, 
        'class': class_obj,
        'title': 'Редактировать домашнее задание',
        'is_update': True,
        'homework': homework
    })

@login_required
def delete_homework(request, homework_id):
    """Удаляет домашнее задание."""
    homework = get_object_or_404(Homework, id=homework_id)
    class_obj = homework.class_obj
    
    if not (request.user.is_admin or 
            (request.user.is_teacher and class_obj.teacher.user == request.user)):
        return HttpResponseForbidden("У вас нет прав для удаления домашнего задания.")
    
    if request.method == 'POST':
        homework.delete()
        messages.success(request, "Домашнее задание успешно удалено.")
        return redirect('classes:class_detail', class_id=class_obj.id)
    
    return render(request, 'classes/confirm_delete.html', {
        'object': f"домашнее задание от {homework.date.strftime('%d.%m.%Y')}",
        'back_url': 'classes:class_detail',
        'back_id': class_obj.id
    })

@login_required
def add_student(request, class_id):
    """Добавляет студентов в класс."""
    class_obj = get_object_or_404(Class, id=class_id)
    
    # Проверка доступа
    if not (request.user.is_admin or request.user.is_reception):
        return HttpResponseForbidden("Только администраторы и ресепшн могут добавлять студентов в класс.")
    
    # Получаем список студентов, которые уже записаны на этот класс
    enrolled_students = Student.objects.filter(enrollments__class_obj=class_obj)
    
    # Получаем список студентов, которые еще не записаны на этот класс
    available_students = Student.objects.exclude(id__in=enrolled_students.values_list('id', flat=True))
    
    if request.method == 'POST':
        form = AddStudentForm(request.POST)
        form.fields['students'].queryset = available_students
        
        if form.is_valid():
            selected_students = form.cleaned_data['students']
            
            for student in selected_students:
                # Создаем запись о зачислении
                enrollment = Enrollment(
                    student=student,
                    class_obj=class_obj
                )
                enrollment.save()
            
            messages.success(request, f"{len(selected_students)} студентов успешно добавлены в класс.")
            return redirect('classes:class_detail', class_id=class_obj.id)
    else:
        form = AddStudentForm()
        form.fields['students'].queryset = available_students
    
    return render(request, 'classes/add_student.html', {
        'form': form,
        'class': class_obj,
        'available_students': available_students
    })

@login_required
def remove_student(request, enrollment_id):
    """Деактивирует студента в классе и сохраняет дату отчисления."""
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    class_obj = enrollment.class_obj
    student = enrollment.student
    
    # Проверка доступа
    if not (request.user.is_admin or request.user.is_reception):
        return HttpResponseForbidden("Только администраторы и ресепшн могут отчислять студентов из класса.")
    
    if request.method == 'POST':
        # Вместо удаления деактивируем запись и устанавливаем дату отчисления
        enrollment.is_active = False
        enrollment.deactivation_date = timezone.now()
        enrollment.save()
        
        messages.success(request, f"Студент {student.full_name} успешно отчислен из класса.")
        return redirect('classes:class_detail', class_id=class_obj.id)
    
    return render(request, 'classes/confirm_delete.html', {
        'object': enrollment,
        'title': 'Отчисление студента из класса',
        'message': f'Вы уверены, что хотите отчислить студента {student.full_name} из класса {class_obj.name}?',
        'cancel_url': 'classes:class_detail',
        'cancel_id': class_obj.id
    })

@login_required
def student_classes(request):
    """Отображает список классов студента с дополнительной информацией и предстоящими занятиями."""
    if not request.user.is_student:
        return HttpResponseForbidden("Эта страница доступна только студентам.")
    
    student = get_object_or_404(Student, user=request.user)
    enrollments = Enrollment.objects.filter(student=student)
    classes = Class.objects.filter(enrollments__in=enrollments).order_by('name')
    
    # Получаем текущую дату и время
    now = timezone.now()
    today = now.date()
    
    # Получаем дополнительную информацию для каждого класса
    classes_with_info = []
    upcoming_lessons = []
    
    for class_obj in classes:
        # Расписание занятий
        schedules = ClassSchedule.objects.filter(class_obj=class_obj)
        
        # Домашние задания
        homeworks = Homework.objects.filter(class_obj=class_obj)
        
        # Добавляем информацию в список
        classes_with_info.append({
            'class': class_obj,
            'schedules': schedules,
            'homeworks': homeworks,
        })
        
        # Получаем предстоящие занятия для этого класса
        for schedule in schedules:
            # Получаем следующие 14 дней
            for i in range(14):
                check_date = today + timedelta(days=i)
                # Проверяем, совпадает ли день недели
                if check_date.weekday() == schedule.day_of_week:
                    # Проверяем, не отменено ли уже это занятие
                    attendance_exists = Attendance.objects.filter(
                        student=student,
                        class_obj=class_obj,
                        date=check_date,
                        is_canceled=True
                    ).exists()
                    
                    # Проверяем, не создан ли уже запрос на отмену
                    from attendance.models import StudentCancellationRequest
                    cancellation_request_exists = StudentCancellationRequest.objects.filter(
                        student=student,
                        class_obj=class_obj,
                        date=check_date
                    ).exists()
                    
                    # Если занятие не отменено и запрос не создан, добавляем его в список
                    if not attendance_exists and not cancellation_request_exists:
                        # Проверяем, можно ли отменить занятие (более 24 часов до начала)
                        lesson_datetime = datetime.combine(
                            check_date, 
                            schedule.start_time,
                            tzinfo=timezone.get_current_timezone()
                        )
                        can_cancel = lesson_datetime - now > timedelta(hours=24)
                        
                        upcoming_lessons.append({
                            'class': class_obj,
                            'schedule': schedule,
                            'date': check_date,
                            'can_cancel': can_cancel,
                            'datetime': lesson_datetime
                        })
    
    # Сортируем предстоящие занятия по дате и времени
    upcoming_lessons.sort(key=lambda x: x['datetime'])
    
    return render(request, 'classes/student_classes.html', {
        'classes_with_info': classes_with_info,
        'student': student,
        'upcoming_lessons': upcoming_lessons,
        'is_self_managed': student.is_self_managed
    })

@login_required
def grade_homework(request, submission_id):
    """Оценивает отправленное домашнее задание."""
    submission = get_object_or_404(HomeworkSubmission, id=submission_id)
    homework = submission.homework
    class_obj = homework.class_obj
    
    # Проверка доступа
    if not (request.user.is_admin or 
            (request.user.is_teacher and class_obj.teacher.user == request.user)):
        return HttpResponseForbidden("У вас нет прав для оценки домашних заданий.")
    
    if request.method == 'POST':
        form = HomeworkGradeForm(request.POST, instance=submission)
        if form.is_valid():
            form.save()
            messages.success(request, "Оценка успешно сохранена.")
            return redirect('classes:class_detail', class_id=class_obj.id)
    else:
        form = HomeworkGradeForm(instance=submission)
    
    return render(request, 'classes/grade_homework.html', {
        'form': form,
        'submission': submission,
        'homework': homework,
        'class': class_obj,
        'student': submission.student
    })

@login_required
def grade_homework_submission(request, submission_id):
    """Оценивает отправленное домашнее задание."""
    if request.method != 'POST' or not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'message': 'Неверный запрос'})
    
    # Проверка, что пользователь является учителем
    if not request.user.is_teacher:
        return JsonResponse({'success': False, 'message': 'У вас нет прав для выполнения этого действия'})
    
    teacher = get_object_or_404(Teacher, user=request.user)
    submission = get_object_or_404(HomeworkSubmission, id=submission_id)
    
    # Проверка, что учитель имеет право оценивать это задание
    if submission.homework.class_obj.teacher != teacher:
        return JsonResponse({'success': False, 'message': 'У вас нет прав для оценки этого задания'})
    
    # Получаем данные из формы
    completion_status = request.POST.get('completion_status')
    teacher_comment = request.POST.get('teacher_comment', '')
    
    # Проверка валидности статуса выполнения
    valid_statuses = ['completed', 'partially_completed', 'not_completed']
    if completion_status not in valid_statuses:
        return JsonResponse({'success': False, 'message': 'Неверный статус выполнения'})
    
    # Обновляем запись о выполнении домашнего задания
    submission.completion_status = completion_status
    submission.teacher_comment = teacher_comment
    submission.checked_at = timezone.now()
    submission.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Домашнее задание успешно оценено'
    })

@login_required
def student_homework(request, class_id, student_id):
    """Отображает все домашние задания и отправленные работы конкретного студента в классе."""
    class_obj = get_object_or_404(Class, id=class_id)
    student = get_object_or_404(Student, id=student_id)
    
    # Проверка доступа
    if not (request.user.is_admin or 
            (request.user.is_teacher and class_obj.teacher.user == request.user) or
            (request.user.is_student and request.user.id == student.user.id) or
            (request.user.is_parent and student.parent and student.parent.user == request.user)):
        return HttpResponseForbidden("У вас нет прав для просмотра этой страницы.")
    
    # Проверка, что студент зачислен в этот класс
    if not Enrollment.objects.filter(student=student, class_obj=class_obj).exists():
        messages.error(request, "Студент не зачислен в этот класс.")
        if request.user.is_student:
            return redirect('classes:student_classes')
        else:
            return redirect('classes:class_detail', class_id=class_obj.id)
    
    # Получаем все домашние задания для класса
    homeworks = Homework.objects.filter(class_obj=class_obj).order_by('-date')
    
    # Получаем все отправленные задания этого студента
    submissions = HomeworkSubmission.objects.filter(
        homework__class_obj=class_obj,
        student=student
    ).select_related('homework')
    
    # Создаем словарь для быстрого доступа к отправленным заданиям по id домашнего задания
    submission_dict = {sub.homework.id: sub for sub in submissions}
    
    # Подготавливаем данные для отображения
    homework_data = []
    for hw in homeworks:
        submission = submission_dict.get(hw.id)
        homework_data.append({
            'homework': hw,
            'submission': submission
        })
    
    return render(request, 'classes/student_homework.html', {
        'class': class_obj,
        'student': student,
        'homework_data': homework_data
    })

@login_required
def all_student_homework(request):
    """Отображает все домашние задания и отправленные работы студента по всем классам."""
    
    # Проверка, что пользователь является студентом
    if not request.user.is_student:
        return HttpResponseForbidden("Эта страница доступна только студентам.")
    
    student = get_object_or_404(Student, user=request.user)
    
    # Получаем все классы, на которые записан студент
    enrollments = Enrollment.objects.filter(student=student)
    classes = Class.objects.filter(enrollments__in=enrollments)
    
    # Получаем все домашние задания для этих классов
    homeworks = Homework.objects.filter(class_obj__in=classes).order_by('-date')
    
    # Получаем все отправленные задания этого студента
    submissions = HomeworkSubmission.objects.filter(
        student=student
    ).select_related('homework')
    
    # Создаем словарь для быстрого доступа к отправленным заданиям по id домашнего задания
    submission_dict = {sub.homework.id: sub for sub in submissions}
    
    # Подготавливаем данные для отображения
    homework_data = []
    for hw in homeworks:
        submission = submission_dict.get(hw.id)
        homework_data.append({
            'homework': hw,
            'submission': submission,
            'class': hw.class_obj
        })
    
    # Группируем домашние задания по классам
    homework_by_class = {}
    for item in homework_data:
        class_id = item['class'].id
        if class_id not in homework_by_class:
            homework_by_class[class_id] = {
                'class': item['class'],
                'homework_items': []
            }
        homework_by_class[class_id]['homework_items'].append(item)
    
    # Преобразуем словарь в список для удобства использования в шаблоне
    classes_with_homework = list(homework_by_class.values())
    
    # Получаем идентификатор класса из GET-параметра, если он есть
    selected_class_id = request.GET.get('class_id')
    
    return render(request, 'classes/all_student_homework.html', {
        'student': student,
        'homework_data': homework_data,
        'classes_with_homework': classes_with_homework,
        'selected_class_id': selected_class_id
    })

@login_required
def unchecked_student_homework(request):
    """Отображает все непроверенные домашние задания студента."""
    
    # Проверка, что пользователь является студентом
    if not request.user.is_student:
        return HttpResponseForbidden("Эта страница доступна только студентам.")
    
    student = get_object_or_404(Student, user=request.user)
    
    # Получаем все отправленные задания этого студента, которые еще не проверены (не имеют оценки)
    submissions = HomeworkSubmission.objects.filter(
        student=student,
        completion_status__isnull=True  # Не проверенные задания не имеют статуса выполнения
    ).select_related('homework', 'homework__class_obj')
    
    # Подготавливаем данные для отображения
    homework_data = []
    for submission in submissions:
        homework_data.append({
            'homework': submission.homework,
            'submission': submission,
            'class': submission.homework.class_obj,
            'submitted_at': submission.submission_date
        })
    
    # Сортируем по дате отправки (сначала новые)
    homework_data = sorted(homework_data, key=lambda x: x['submitted_at'], reverse=True)
    
    return render(request, 'classes/unchecked_student_homework.html', {
        'student': student,
        'homework_data': homework_data
    })

@login_required
def unchecked_teacher_homework(request):
    """Отображает все непроверенные домашние задания для учителя."""
    
    # Проверка, что пользователь является учителем
    if not request.user.is_teacher:
        return HttpResponseForbidden("Эта страница доступна только учителям.")
    
    teacher = get_object_or_404(Teacher, user=request.user)
    
    # Получаем классы этого учителя
    teacher_classes = Class.objects.filter(teacher=teacher)
    
    # Получаем все домашние задания для этих классов
    homeworks = Homework.objects.filter(class_obj__in=teacher_classes)
    
    # Получаем все отправленные задания для этих домашних заданий, которые еще не проверены
    submissions = HomeworkSubmission.objects.filter(
        homework__in=homeworks,
        completion_status__isnull=True  # Не проверенные задания не имеют статуса выполнения
    ).select_related('homework', 'homework__class_obj', 'student')
    
    # Подготавливаем данные для отображения
    homework_data = []
    for submission in submissions:
        homework_data.append({
            'homework': submission.homework,
            'submission': submission,
            'class': submission.homework.class_obj,
            'student': submission.student,
            'submitted_at': submission.submission_date
        })
    
    # Сортируем по дате отправки (сначала старые)
    homework_data = sorted(homework_data, key=lambda x: x['submitted_at'])
    
    return render(request, 'classes/unchecked_teacher_homework.html', {
        'teacher': teacher,
        'homework_data': homework_data
    })

@login_required
def unchecked_class_homework(request, class_id):
    """Отображает все непроверенные домашние задания для конкретного класса."""
    
    # Проверка, что пользователь является учителем
    if not request.user.is_teacher:
        return HttpResponseForbidden("Эта страница доступна только учителям.")
    
    teacher = get_object_or_404(Teacher, user=request.user)
    class_obj = get_object_or_404(Class, id=class_id, teacher=teacher)
    
    # Получаем все домашние задания для этого класса
    homeworks = Homework.objects.filter(class_obj=class_obj)
    
    # Получаем все отправленные задания для этих домашних заданий, которые еще не проверены
    submissions = HomeworkSubmission.objects.filter(
        homework__in=homeworks,
        completion_status__isnull=True  # Не проверенные задания не имеют статуса выполнения
    ).select_related('homework', 'student')
    
    # Подготавливаем данные для отображения
    homework_data = []
    for submission in submissions:
        homework_data.append({
            'homework': submission.homework,
            'submission': submission,
            'student': submission.student,
            'submitted_at': submission.submission_date
        })
    
    # Сортируем по дате отправки (сначала старые)
    homework_data = sorted(homework_data, key=lambda x: x['submitted_at'])
    
    return render(request, 'classes/unchecked_class_homework.html', {
        'teacher': teacher,
        'class': class_obj,
        'homework_data': homework_data
    })

@login_required
def submit_homework_ajax(request, homework_id):
    """Отправляет выполненное домашнее задание через AJAX."""
    if request.method != 'POST' or not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'message': 'Неверный запрос'})
    
    homework = get_object_or_404(Homework, id=homework_id)
    class_obj = homework.class_obj
    
    # Проверка доступа
    if not request.user.is_student:
        return JsonResponse({'success': False, 'message': 'Только студенты могут отправлять домашние задания'})
    
    student = get_object_or_404(Student, user=request.user)
    
    # Проверка, что студент записан на этот класс
    if not Enrollment.objects.filter(student=student, class_obj=class_obj).exists():
        return JsonResponse({'success': False, 'message': 'Вы не записаны на этот класс'})
    
    # Проверка, не отправлял ли студент уже домашнее задание
    if HomeworkSubmission.objects.filter(homework=homework, student=student).exists():
        return JsonResponse({'success': False, 'message': 'Вы уже отправили домашнее задание'})
    
    try:
        # Получаем файл и комментарий из запроса
        homework_file = request.FILES.get('file')
        comment = request.POST.get('comment', '')
        
        if not homework_file:
            return JsonResponse({'success': False, 'message': 'Файл не загружен'})
        
        # Создаем новую запись о выполненном задании
        submission = HomeworkSubmission(
            homework=homework,
            student=student,
            file=homework_file
        )
        submission.save()
        
        # Сохраняем комментарий студента в поле teacher_comment временно
        # (позже учитель заменит его своим комментарием)
        if comment:
            submission.teacher_comment = f"Комментарий студента: {comment}"
            submission.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Домашнее задание успешно отправлено'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка при отправке: {str(e)}'})

@login_required
def cancel_homework_submission(request, submission_id):
    """Отменяет отправку домашнего задания."""
    if request.method != 'POST' or not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'message': 'Неверный запрос'})
    
    # Получаем объект отправленного задания
    submission = get_object_or_404(HomeworkSubmission, id=submission_id)
    
    # Проверка доступа
    if not request.user.is_student:
        return JsonResponse({'success': False, 'message': 'Только студенты могут отменять отправку заданий'})
    
    student = get_object_or_404(Student, user=request.user)
    
    # Проверка, что это задание принадлежит текущему студенту
    if submission.student != student:
        return JsonResponse({'success': False, 'message': 'У вас нет прав для отмены этого задания'})
    
    # Проверка, что задание еще не оценено учителем
    if submission.completion_status:
        return JsonResponse({'success': False, 'message': 'Нельзя отменить отправку задания, которое уже оценено учителем'})
    
    try:
        # Сохраняем путь к файлу, чтобы удалить его после удаления записи
        file_path = submission.file.path if submission.file else None
        
        # Удаляем запись об отправленном задании
        submission.delete()
        
        # Удаляем файл, если он существует
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        
        return JsonResponse({
            'success': True, 
            'message': 'Отправка домашнего задания отменена. Теперь вы можете отправить его заново.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка при отмене отправки: {str(e)}'})

@login_required
def teacher_today_schedule(request):
    """Отображает расписание занятий учителя на сегодня и домашние задания, которые нужно проверить."""
    if not request.user.is_teacher:
        return HttpResponseForbidden("Эта страница доступна только учителям.")
    
    teacher = get_object_or_404(Teacher, user=request.user)
    today = timezone.now().date()
    today_weekday = today.weekday()
    
    # Получаем все классы учителя
    classes = Class.objects.filter(teacher=teacher)
    
    # Получаем расписание для всех классов на сегодня
    today_schedules = ClassSchedule.objects.filter(
        class_obj__in=classes,
        day_of_week=today_weekday
    ).select_related('class_obj').order_by('start_time')
    
    # Получаем непроверенные домашние задания для классов учителя
    unchecked_homework = HomeworkSubmission.objects.filter(
        homework__class_obj__in=classes,
        completion_status__isnull=True  # Не проверенные задания не имеют статуса выполнения
    ).select_related('homework', 'student', 'homework__class_obj').order_by('submission_date')
    
    # Группируем домашние задания по классам
    homework_by_class = {}
    for submission in unchecked_homework:
        class_id = submission.homework.class_obj.id
        if class_id not in homework_by_class:
            homework_by_class[class_id] = []
        
        homework_by_class[class_id].append({
            'submission': submission,
            'homework': submission.homework,
            'student': submission.student,
            'class': submission.homework.class_obj,
            'submitted_at': submission.submission_date
        })
    
    # Подготавливаем данные для шаблона
    schedule_data = []
    for schedule in today_schedules:
        class_id = schedule.class_obj.id
        schedule_data.append({
            'schedule': schedule,
            'class': schedule.class_obj,
            'homework': homework_by_class.get(class_id, [])
        })
    
    # Общее количество непроверенных заданий
    total_unchecked = unchecked_homework.count()
    
    context = {
        'today': today,
        'schedule_data': schedule_data,
        'total_unchecked': total_unchecked,
        'teacher': teacher
    }
    
    return render(request, 'classes/teacher_today_schedule.html', context)

@login_required
def teacher_schedule(request):
    """Отображает расписание занятий учителя с возможностью запросить отмену урока."""
    if not request.user.is_teacher:
        return HttpResponseForbidden("Эта страница доступна только учителям.")
    
    teacher = get_object_or_404(Teacher, user=request.user)
    
    # Получаем все классы учителя
    classes = Class.objects.filter(teacher=teacher)
    
    # Получаем расписание для всех классов
    schedules = ClassSchedule.objects.filter(class_obj__in=classes).select_related('class_obj')
    
    # Получаем даты зачисления студентов для каждого класса
    enrollment_dates = {}
    for class_obj in classes:
        # Получаем все активные зачисления для класса
        enrollments = Enrollment.objects.filter(class_obj=class_obj, is_active=True)
        
        # Сохраняем информацию о студентах и датах их зачисления
        enrollment_dates[class_obj.id] = {
            'students': [],
            'earliest_date': None
        }
        
        for enrollment in enrollments:
            enrollment_dates[class_obj.id]['students'].append({
                'student_id': enrollment.student.id,
                'student_name': enrollment.student.full_name,
                'enrollment_date': enrollment.enrollment_date
            })
            
            # Определяем самую раннюю дату зачисления для класса
            if enrollment_dates[class_obj.id]['earliest_date'] is None or enrollment.enrollment_date < enrollment_dates[class_obj.id]['earliest_date']:
                enrollment_dates[class_obj.id]['earliest_date'] = enrollment.enrollment_date
    
    # Создаем словарь для хранения классов без расписания
    classes_without_schedule = {cls.id: cls for cls in classes}
    
    # Удаляем из словаря классы, для которых уже есть расписание
    for schedule in schedules:
        if schedule.class_obj.id in classes_without_schedule:
            del classes_without_schedule[schedule.class_obj.id]
    
    # Получаем текущую дату и начало недели (понедельник)
    today = timezone.now().date()
    
    # Получаем номер недели из GET-параметра или используем текущую неделю
    week_offset = int(request.GET.get('week_offset', 0))
    
    # Начало текущей недели (понедельник)
    current_week_start = today - timedelta(days=today.weekday())
    
    # Начало недели с учетом смещения
    start_of_week = current_week_start + timedelta(weeks=week_offset)
    
    # Создаем календарь на 2 недели (текущую и следующую)
    calendar_days = []
    for i in range(14):
        day = start_of_week + timedelta(days=i)
        day_schedules = []
        substitute_schedules = []
        
        for schedule in schedules:
            if schedule.day_of_week == day.weekday():
                # Проверяем, есть ли запрос на отмену для этого урока и даты
                from attendance.models import CancellationRequest
                cancellation_request = CancellationRequest.objects.filter(
                    teacher=teacher,
                    class_obj=schedule.class_obj,
                    date=day,
                ).first()
                
                # Проверяем, есть ли студенты в классе на эту дату
                class_id = schedule.class_obj.id
                has_students = False
                earliest_enrollment = None
                
                if class_id in enrollment_dates and enrollment_dates[class_id]['earliest_date']:
                    earliest_enrollment = enrollment_dates[class_id]['earliest_date']
                    # Проверяем, что дата урока не раньше самой ранней даты зачисления
                    has_students = day.date() >= earliest_enrollment.date()
                
                day_schedules.append({
                    'schedule': schedule,
                    'cancellation_request': cancellation_request,
                    'has_students': has_students,
                    'earliest_enrollment': earliest_enrollment
                })
        
        # Добавляем уроки замены для этого дня
        for key, substitute_class in substitute_classes_by_date.items():
            substitute_date, _, _ = key
            if substitute_date == day.date():
                substitute_schedules.append({
                    'class_obj': substitute_class['class_obj'],
                    'schedule': substitute_class['class_schedule'],
                    'is_substitute': True
                })
        
        calendar_days.append({
            'date': day,
            'schedules': sorted(day_schedules, key=lambda x: x['schedule'].start_time),
            'substitute_schedules': sorted(substitute_schedules, key=lambda x: x['schedule'].start_time)
        })
    
    # Получаем запросы на отмену уроков
    from attendance.models import CancellationRequest
    pending_requests = CancellationRequest.objects.filter(
        teacher=teacher,
        status='pending'
    ).count()
    
    # Получаем уроки замены
    from attendance.models import Attendance
    
    # Получаем количество уроков замены для отображения в счетчике
    substitute_classes_count = Attendance.objects.filter(
        substitute_teacher=teacher,
        is_canceled=True,
        date__gte=today
    ).values('class_obj', 'date').distinct().count()
    
    # Получаем уроки замены для отображения в расписании
    substitute_attendances = Attendance.objects.filter(
        substitute_teacher=teacher,
        is_canceled=True,
        date__range=[start_of_week, start_of_week + timedelta(days=13)]
    ).select_related('class_obj', 'class_schedule').order_by('date', 'class_schedule__start_time')
    
    # Группируем уроки замены по дате и классу
    substitute_classes_by_date = {}
    for attendance in substitute_attendances:
        key = (attendance.date, attendance.class_obj.id, attendance.class_schedule.id)
        if key not in substitute_classes_by_date:
            substitute_classes_by_date[key] = {
                'date': attendance.date,
                'class_obj': attendance.class_obj,
                'class_schedule': attendance.class_schedule,
                'attendances': []
            }
        substitute_classes_by_date[key]['attendances'].append(attendance)
    
    context = {
        'calendar_days': calendar_days,
        'today': today,
        'pending_requests': pending_requests,
        'substitute_classes_count': substitute_classes_count,
        'classes_without_schedule': list(classes_without_schedule.values()),
        'week_offset': week_offset,
        'prev_week_offset': week_offset - 1,
        'next_week_offset': week_offset + 1,
        'start_of_week': start_of_week,
        'end_of_week': start_of_week + timedelta(days=13),  # Конец двухнедельного периода
        'enrollment_dates': enrollment_dates
    }
    
    return render(request, 'classes/teacher_schedule.html', context)


@login_required
def lesson_detail(request, class_id, schedule_id, date):
    """Отображает детальную информацию о конкретном уроке в конкретную дату."""
    # Импортируем все необходимые модели и модули
    from datetime import datetime
    from django.http import HttpResponseForbidden, HttpResponseBadRequest
    from django.shortcuts import get_object_or_404
    from accounts.models import Teacher
    from classes.models import Class, ClassSchedule, Enrollment
    from attendance.models import Attendance, CancellationRequest
    
    # Проверяем, что пользователь является учителем
    if not hasattr(request.user, 'is_teacher') or not request.user.is_teacher:
        return HttpResponseForbidden("Эта страница доступна только учителям.")
        
    # Получаем класс и расписание
    class_obj = get_object_or_404(Class, id=class_id)
    schedule = get_object_or_404(ClassSchedule, id=schedule_id, class_obj=class_obj)
    
    # Преобразуем строку даты в объект даты
    try:
        lesson_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Неверный формат даты.")
        return redirect('classes:teacher_schedule')
    
    # Проверяем, что пользователь имеет доступ к этому уроку
    if request.user.is_teacher:
        teacher = get_object_or_404(Teacher, user=request.user)
        if class_obj.teacher != teacher:
            return HttpResponseForbidden("У вас нет доступа к этому уроку.")
    elif request.user.is_student:
        student = get_object_or_404(Student, user=request.user)
        enrollment = Enrollment.objects.filter(student=student, class_obj=class_obj, is_active=True).first()
        if not enrollment:
            return HttpResponseForbidden("Вы не записаны на этот класс.")
        # Проверяем, что дата урока не раньше даты зачисления студента
        if enrollment.enrollment_date > lesson_date:
            return HttpResponseForbidden("У вас нет доступа к урокам, которые были до вашего зачисления.")
    elif not (request.user.is_admin or request.user.is_reception):
        return HttpResponseForbidden("У вас нет доступа к этому уроку.")
    
    # Получаем информацию о посещаемости для этого урока
    attendances = Attendance.objects.filter(class_obj=class_obj, date=lesson_date)
    
    # Получаем домашнее задание для этого урока
    try:
        homework = Homework.objects.get(class_obj=class_obj, date=lesson_date)
    except Homework.DoesNotExist:
        homework = None
    
    # Получаем отправленные домашние задания для этого урока
    homework_submissions = []
    if homework:
        homework_submissions = HomeworkSubmission.objects.filter(homework=homework)
    
    # Получаем оценки для этого урока
    marks = Mark.objects.filter(class_obj=class_obj, date=lesson_date)
    
    # Получаем материалы для этого урока
    lesson_materials = ClassworkFile.objects.filter(
        class_obj=class_obj,
        schedule=schedule,
        material_type='lesson_specific',
        date=lesson_date
    )
    
    # Получаем список студентов, записанных на этот класс
    enrollments = Enrollment.objects.filter(class_obj=class_obj, is_active=True)
    
    # Если пользователь - студент, проверяем только его
    if request.user.is_student:
        students = [student]
    else:
        # Для учителей, администраторов и ресепшн показываем всех студентов
        students = [enrollment.student for enrollment in enrollments]
    
    # Создаем словарь для быстрого доступа к посещаемости и оценкам
    attendance_dict = {attendance.student_id: attendance for attendance in attendances}
    mark_dict = {mark.student_id: mark for mark in marks}
    
    # Создаем список студентов с информацией о посещаемости и оценках
    students_info = []
    for student in students:
        # Проверяем, что дата урока не раньше даты зачисления студента
        student_enrollment = next((e for e in enrollments if e.student_id == student.id), None)
        if student_enrollment and student_enrollment.enrollment_date <= lesson_date:
            attendance = attendance_dict.get(student.id)
            mark = mark_dict.get(student.id)
            
            # Проверяем, отправил ли студент домашнее задание
            submission = None
            if homework:
                try:
                    submission = HomeworkSubmission.objects.get(homework=homework, student=student)
                except HomeworkSubmission.DoesNotExist:
                    pass
            
            students_info.append({
                'student': student,
                'attendance': attendance,
                'mark': mark,
                'submission': submission
            })
    
    context = {
        'class': class_obj,
        'schedule': schedule,
        'date': lesson_date,
        'students_info': students_info,
        'homework': homework,
        'homework_submissions': homework_submissions,
        'lesson_materials': lesson_materials,
        'is_teacher': request.user.is_teacher,
        'is_student': request.user.is_student,
        'is_admin': request.user.is_admin,
        'is_reception': request.user.is_reception
    }
    
    return render(request, 'classes/lesson_detail.html', context)

@login_required
def parent_child_lessons(request, student_id):
    user = request.user
    
    if not hasattr(user, 'parent'):
        return redirect('core:home')
    
    parent = user.parent
    
    try:
        student = Student.objects.get(pk=student_id)
    except Student.DoesNotExist:
        return redirect('core:home')
    
    # Проверяем, что родитель имеет доступ к этому студенту
    if student not in parent.students.all():
        return redirect('core:home')
    
    enrollments = Enrollment.objects.filter(student=student).select_related('class_obj')
    classes_data = []
    
    for enrollment in enrollments:
        class_obj = enrollment.class_obj
        
        # Получаем данные о посещаемости
        attendances = Attendance.objects.filter(
            student=student,
            class_obj=class_obj
        ).order_by('-date')
        
        attendance_data = []
        
        for attendance in attendances:
            # Получаем оценки для этого посещения
            try:
                mark = Mark.objects.get(
                    student=student,
                    class_obj=class_obj,
                    date=attendance.date
                )
            except Mark.DoesNotExist:
                mark = None
            
            # Получаем домашнее задание для этого урока
            try:
                homework = Homework.objects.get(
                    class_obj=class_obj,
                    date=attendance.date
                )
            except Homework.DoesNotExist:
                homework = None
            
            # Получаем загруженные студентом файлы
            student_files = []
            if homework:
                student_files = HomeworkSubmission.objects.filter(
                    homework=homework,
                    student=student
                )
            
            attendance_data.append({
                'attendance': attendance,
                'mark': mark,
                'homework': homework,
                'student_files': student_files
            })
        
        classes_data.append({
            'class': class_obj,
            'attendance_data': attendance_data
        })
    
    context = {
        'student': student,
        'classes_data': classes_data
    }
    
    return render(request, 'classes/parent_child_lessons.html', context)

@login_required
def parent_child_homework(request, student_id):
    # Implement this view
    pass

@login_required
def class_lesson_calendar(request, class_id):
    """
    Отображает календарь уроков класса для выбора урока при загрузке материала.
    """
    class_obj = get_object_or_404(Class, id=class_id)
    
    # Проверяем права доступа
    if request.user.is_teacher:
        teacher = get_object_or_404(Teacher, user=request.user)
        if class_obj.teacher != teacher:
            return HttpResponseForbidden("Вы не являетесь преподавателем этого класса.")
    elif not request.user.is_admin:
        return HttpResponseForbidden("Только преподаватели и администраторы могут загружать материалы.")
    
    # Получаем расписание для этого класса
    schedules = ClassSchedule.objects.filter(class_obj=class_obj)
    
    # Получаем текущую дату
    today = timezone.now().date()
    
    # Определяем начальную и конечную даты для календаря (4 недели назад и 8 недель вперед)
    start_date = today - timedelta(days=28)
    end_date = today + timedelta(days=56)
    
    # Создаем список дат для календаря
    calendar_dates = []
    current_date = start_date
    
    while current_date <= end_date:
        # Для каждой даты проверяем, есть ли в этот день занятия по расписанию
        day_of_week = current_date.weekday()
        day_schedules = schedules.filter(day_of_week=day_of_week)
        
        if day_schedules.exists():
            # Для каждого расписания на этот день создаем запись в календаре
            for schedule in day_schedules:
                # Проверяем, есть ли уже материалы для этого урока
                existing_materials = ClassworkFile.objects.filter(
                    class_obj=class_obj,
                    schedule=schedule,
                    date=current_date,
                    material_type='lesson_specific'
                ).count()
                
                calendar_dates.append({
                    'date': current_date,
                    'schedule': schedule,
                    'day_name': schedule.get_day_of_week_display(),
                    'time': f"{schedule.start_time.strftime('%H:%M')} - {schedule.end_time.strftime('%H:%M')}",
                    'has_materials': existing_materials > 0,
                    'is_past': current_date < today,
                    'is_today': current_date == today
                })
        
        current_date += timedelta(days=1)
    
    # Группируем даты по месяцам для удобного отображения
    calendar_by_month = {}
    for item in calendar_dates:
        month_key = item['date'].strftime('%Y-%m')
        month_name = item['date'].strftime('%B %Y')
        
        if month_key not in calendar_by_month:
            calendar_by_month[month_key] = {
                'name': month_name,
                'dates': []
            }
        
        calendar_by_month[month_key]['dates'].append(item)
    
    # Сортируем месяцы по дате
    sorted_months = sorted(calendar_by_month.items(), key=lambda x: x[0])
    
    return render(request, 'classes/class_lesson_calendar.html', {
        'class': class_obj,
        'calendar_months': [month_data for _, month_data in sorted_months],
        'today': today
    })

@login_required
def upload_classwork_file(request, class_id, schedule_id=None, date=None):
    """
    Загружает материал для класса (общий или привязанный к конкретному уроку).
    Доступно только для учителей класса и администраторов.
    """
    class_obj = get_object_or_404(Class, id=class_id)
    
    # Проверяем права доступа
    if request.user.is_teacher:
        teacher = get_object_or_404(Teacher, user=request.user)
        if class_obj.teacher != teacher:
            return HttpResponseForbidden("Вы не являетесь преподавателем этого класса.")
    elif not request.user.is_admin:
        return HttpResponseForbidden("Только преподаватели и администраторы могут загружать материалы.")
    
    # Обрабатываем параметры для материала к конкретному уроку
    selected_schedule = None
    lesson_date = None
    initial_data = {}
    
    if schedule_id:
        try:
            selected_schedule = ClassSchedule.objects.get(id=schedule_id, class_obj=class_obj)
            initial_data['schedule'] = selected_schedule
            initial_data['material_type'] = 'lesson_specific'
        except ClassSchedule.DoesNotExist:
            messages.error(request, "Указанное расписание не найдено.")
    
    if date:
        try:
            lesson_date = datetime.strptime(date, '%Y-%m-%d').date()
            initial_data['date'] = lesson_date
        except ValueError:
            messages.error(request, "Неверный формат даты.")
            lesson_date = datetime.now().date()
    else:
        lesson_date = datetime.now().date()
        initial_data['date'] = lesson_date
    
    if request.method == 'POST':
        form = ClassworkFileForm(request.POST, request.FILES, class_obj=class_obj)
        if form.is_valid():
            classwork_file = form.save(commit=False)
            classwork_file.class_obj = class_obj
            classwork_file.date = form.cleaned_data.get('date', lesson_date)
            
            try:
                classwork_file.save()
                messages.success(request, "Материал успешно загружен.")
                return redirect('classes:class_materials', class_id=class_id)
            except ValidationError as e:
                for field, errors in e.message_dict.items():
                    for error in errors:
                        form.add_error(field, error)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Ошибка при загрузке материала: {str(e)}")
                messages.error(request, f"Произошла ошибка при загрузке материала: {str(e)}")
    else:
        form = ClassworkFileForm(class_obj=class_obj, initial=initial_data)
    
    # Получаем расписание для этого класса
    schedules = ClassSchedule.objects.filter(class_obj=class_obj)
    
    # Добавляем информацию о выбранном уроке
    lesson_info = None
    if selected_schedule and lesson_date:
        lesson_info = {
            'date': lesson_date,
            'day_name': selected_schedule.get_day_of_week_display(),
            'time': f"{selected_schedule.start_time.strftime('%H:%M')} - {selected_schedule.end_time.strftime('%H:%M')}",
            'room': selected_schedule.room
        }
    
    return render(request, 'classes/upload_classwork_file.html', {
        'form': form,
        'class': class_obj,
        'schedules': schedules,
        'lesson_info': lesson_info,
        'from_calendar': schedule_id is not None and date is not None
    })

@login_required
def class_materials(request, class_id):
    """
    Отображает список всех материалов для класса.
    Для студентов показывает только общие материалы и материалы к урокам после даты их зачисления.
    """
    class_obj = get_object_or_404(Class, id=class_id)
    
    # Проверяем права доступа
    if request.user.is_teacher:
        teacher = get_object_or_404(Teacher, user=request.user)
        if class_obj.teacher != teacher:
            return HttpResponseForbidden("Вы не являетесь преподавателем этого класса.")
    elif request.user.is_student:
        student = get_object_or_404(Student, user=request.user)
        enrollment = Enrollment.objects.filter(student=student, class_obj=class_obj, is_active=True).first()
        if not enrollment:
            return HttpResponseForbidden("Вы не записаны на этот класс.")
    elif not (request.user.is_admin or request.user.is_reception):
        return HttpResponseForbidden("У вас нет доступа к материалам этого класса.")
    
    # Получаем тип материалов для фильтрации
    material_type = request.GET.get('type', 'all')
    
    # Базовый запрос для материалов
    materials_query = ClassworkFile.objects.filter(class_obj=class_obj)
    
    # Фильтруем по типу материала, если указан
    if material_type == 'general':
        materials_query = materials_query.filter(material_type='general')
    elif material_type == 'lesson_specific':
        materials_query = materials_query.filter(material_type='lesson_specific')
    
    # Для студентов фильтруем материалы по дате зачисления
    if request.user.is_student:
        enrollment_date = enrollment.enrollment_date
        # Общие материалы доступны всем
        general_materials = materials_query.filter(material_type='general')
        # Материалы к конкретным урокам доступны только после даты зачисления
        lesson_materials = materials_query.filter(
            material_type='lesson_specific',
            date__gte=enrollment_date
        )
        # Объединяем результаты
        materials = general_materials | lesson_materials
    else:
        # Для учителей, администраторов и ресепшн показываем все материалы
        materials = materials_query
    
    # Сортируем по дате (сначала новые)
    materials = materials.order_by('-date')
    
    return render(request, 'classes/class_materials.html', {
        'class': class_obj,
        'materials': materials,
        'material_type': material_type,
        'is_teacher': request.user.is_teacher,
        'is_admin': request.user.is_admin
    })

@login_required
def delete_classwork_file(request, file_id):
    """
    Удаляет материал занятия.
    Доступно только для учителей класса и администраторов.
    """
    classwork_file = get_object_or_404(ClassworkFile, id=file_id)
    class_obj = classwork_file.class_obj
    
    # Проверяем права доступа
    if request.user.is_teacher:
        teacher = get_object_or_404(Teacher, user=request.user)
        if class_obj.teacher != teacher:
            return HttpResponseForbidden("Вы не являетесь преподавателем этого класса.")
    elif not request.user.is_admin:
        return HttpResponseForbidden("Только преподаватели и администраторы могут удалять материалы.")
    
    if request.method == 'POST':
        # Удаляем файл
        try:
            # Удаляем физический файл, если он существует
            if classwork_file.file and os.path.isfile(classwork_file.file.path):
                os.remove(classwork_file.file.path)
            # Удаляем запись из базы данных
            classwork_file.delete()
            messages.success(request, "Материал успешно удален.")
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка при удалении материала: {str(e)}")
            messages.error(request, f"Произошла ошибка при удалении материала: {str(e)}")
        
        return redirect('classes:class_materials', class_id=class_obj.id)
    
    return render(request, 'classes/confirm_delete.html', {
        'object': classwork_file,
        'title': 'Удаление материала',
        'message': f'Вы уверены, что хотите удалить материал "{classwork_file.title}"?',
        'cancel_url': 'classes:class_materials',
        'cancel_url_args': [class_obj.id]
    })

@login_required
def parent_child_past_lessons(request, student_id):
    """Отображает список прошедших уроков ребенка для родителя с комментариями, оценками и материалами.
    Родители всегда видят комментарии и оценки своих детей.
    Показываются только те уроки, которые были после регистрации ребенка в класс.
    """
    if not request.user.is_parent:
        return HttpResponseForbidden("Эта страница доступна только родителям.")
    
    parent = get_object_or_404(Parent, user=request.user)
    student = get_object_or_404(Student, id=student_id, parent=parent)
    
    # Получаем текущую дату
    today = timezone.now().date()
    
    # Получаем все записи ребенка на классы
    enrollments = Enrollment.objects.filter(student=student)
    
    # Фильтры
    class_filter = request.GET.get('class_id')
    status_filter = request.GET.get('status')
    
    # Получаем все классы ребенка для фильтра
    student_classes = Class.objects.filter(enrollments__in=enrollments).distinct()
    
    # Создаем список для хранения данных о прошедших уроках
    past_lessons = []
    
    # Перебираем все записи на классы
    for enrollment in enrollments:
        class_obj = enrollment.class_obj
        
        # Если выбран конкретный класс для фильтрации
        if class_filter and int(class_filter) != class_obj.id:
            continue
        
        # Получаем дату зачисления в класс
        enrollment_date = enrollment.enrollment_date
        
        # Получаем все посещения для этого класса
        attendances = Attendance.objects.filter(
            student=student,
            class_obj=class_obj,
            date__lt=today,  # Только прошедшие уроки
            date__gte=enrollment_date  # Только уроки после зачисления
        ).order_by('-date')
        
        # Фильтруем по статусу, если указан
        if status_filter:
            attendances = attendances.filter(status=status_filter)
        
        # Получаем расписание для этого класса
        schedules = ClassSchedule.objects.filter(class_obj=class_obj)
        
        # Создаем словарь для быстрого доступа к расписанию по дню недели
        schedule_dict = {}
        for schedule in schedules:
            schedule_dict[schedule.day_of_week] = schedule
        
        # Перебираем все посещения
        for attendance in attendances:
            # Получаем день недели для этой даты
            day_of_week = attendance.date.weekday()
            
            # Получаем расписание для этого дня
            schedule = schedule_dict.get(day_of_week)
            
            # Получаем оценки и комментарии для этого урока
            try:
                mark = Mark.objects.get(
                    student=student,
                    class_obj=class_obj,
                    date=attendance.date
                )
            except Mark.DoesNotExist:
                mark = None
            
            # Получаем материалы для этого урока
            from classes.models import ClassworkFile
            classwork_files = ClassworkFile.objects.filter(
                class_obj=class_obj,
                date=attendance.date
            )
            
            # Получаем домашнее задание для этого урока
            try:
                homework = Homework.objects.get(
                    class_obj=class_obj,
                    date=attendance.date
                )
            except Homework.DoesNotExist:
                homework = None
            
            # Добавляем информацию в список
            past_lessons.append({
                'class': class_obj,
                'date': attendance.date,
                'schedule': schedule,
                'attendance': attendance,
                'mark': mark,
                'classwork_files': classwork_files,
                'homework': homework,
                'is_self_managed': student.is_self_managed
            })
    
    # Сортируем по дате (сначала самые недавние)
    past_lessons.sort(key=lambda x: x['date'], reverse=True)
    
    context = {
        'student': student,
        'past_lessons': past_lessons,
        'student_classes': student_classes,
        'class_filter': class_filter,
        'status_filter': status_filter,
        'is_self_managed': student.is_self_managed
    }
    
    return render(request, 'classes/parent_child_past_lessons.html', context)


@login_required
def student_schedule(request):
    """Отображает расписание занятий студента с возможностью навигации по неделям.
    Синим цветом отмечаются уроки, на которые хватает баланса студента.
    Красным цветом отмечаются уроки, на которые не хватает баланса.
    Учитывается, что у студента может быть несколько классов.
    """
    if not request.user.is_student:
        return HttpResponseForbidden("Эта страница доступна только студентам.")
    
    student = get_object_or_404(Student, user=request.user)
    
    # Получаем все записи ученика на классы
    enrollments = Enrollment.objects.filter(student=student, is_active=True)
    
    # Получаем все классы ученика
    classes = Class.objects.filter(enrollments__in=enrollments).distinct()
    
    # Получаем расписание для всех классов
    # Берем только первое расписание для каждого класса и дня недели
    # Создаем словарь для хранения уникальных расписаний по классу и дню недели
    unique_schedules = {}
    all_schedules = ClassSchedule.objects.filter(class_obj__in=classes).select_related('class_obj')
    
    for schedule in all_schedules:
        key = (schedule.class_obj.id, schedule.day_of_week)
        if key not in unique_schedules:
            unique_schedules[key] = schedule
    
    # Преобразуем словарь в список
    schedules = list(unique_schedules.values())
    
    # Получаем текущую дату и начало недели (понедельник)
    today = timezone.now().date()
    
    # Получаем номер недели из GET-параметра или используем текущую неделю
    week_offset = int(request.GET.get('week_offset', 0))
    
    # Начало текущей недели (понедельник)
    current_week_start = today - timedelta(days=today.weekday())
    
    # Начало недели с учетом смещения
    start_of_week = current_week_start + timedelta(weeks=week_offset)
    
    # Получаем даты зачисления ученика в каждый класс
    enrollment_dates = {}
    for enrollment in enrollments:
        # Преобразуем дату зачисления в объект datetime для корректного сравнения
        enrollment_date = enrollment.enrollment_date
        if isinstance(enrollment_date, datetime_date) and not isinstance(enrollment_date, datetime):
            # Если это объект date, но не datetime, преобразуем его в datetime
            enrollment_date = datetime.combine(enrollment_date, datetime.min.time())
            # Добавляем часовой пояс, чтобы избежать ошибки сравнения offset-naive и offset-aware
            enrollment_date = timezone.make_naive(timezone.make_aware(enrollment_date))
        enrollment_dates[enrollment.class_obj.id] = enrollment_date
    
    # Создаем календарь на неделю
    calendar_days = []
    
    # Получаем все посещения студента за неделю
    from django.db.models import Max
    
    # Получаем даты начала и конца недели
    week_start = start_of_week
    week_end = start_of_week + timedelta(days=6)
    
    # Получаем последние ID посещений для каждого класса и даты за неделю
    latest_attendance_subquery = Attendance.objects.filter(
        student=student,
        date__range=[week_start, week_end]
    ).values('class_obj', 'date').annotate(latest_id=Max('id')).values('latest_id')
    
    # Получаем только последние записи о посещении
    week_attendances = Attendance.objects.filter(
        id__in=latest_attendance_subquery
    ).select_related('class_obj')
    
    # Создаем словарь посещений по классу и дате
    attendance_by_class_and_date = {}
    for attendance in week_attendances:
        key = (attendance.class_obj.id, attendance.date)
        attendance_by_class_and_date[key] = attendance
    
    # Получаем все запросы на отмену за неделю
    from attendance.models import StudentCancellationRequest
    
    latest_cancellation_subquery = StudentCancellationRequest.objects.filter(
        student=student,
        date__range=[week_start, week_end]
    ).values('class_obj', 'date').annotate(latest_id=Max('id')).values('latest_id')
    
    week_cancellations = StudentCancellationRequest.objects.filter(
        id__in=latest_cancellation_subquery
    ).select_related('class_obj')
    
    # Создаем словарь запросов на отмену по классу и дате
    cancellation_by_class_and_date = {}
    for cancellation in week_cancellations:
        key = (cancellation.class_obj.id, cancellation.date)
        cancellation_by_class_and_date[key] = cancellation
        
    # Создаем календарь на неделю
    for i in range(7):
        day = start_of_week + timedelta(days=i)
        day_schedules = []
        
        # Получаем все оценки и материалы для этого дня
        marks_by_class = {}
        try:
            marks = Mark.objects.filter(
                student=student,
                date=day
            ).select_related('class_obj')
            for mark in marks:
                marks_by_class[mark.class_obj.id] = mark
        except Mark.DoesNotExist:
            pass
        
        # Получаем материалы для этого дня
        from classes.models import ClassworkFile
        classwork_files_by_class = {}
        classwork_files = ClassworkFile.objects.filter(
            class_obj__in=classes,
            date=day
        ).select_related('class_obj')
        for file in classwork_files:
            if file.class_obj.id not in classwork_files_by_class:
                classwork_files_by_class[file.class_obj.id] = []
            classwork_files_by_class[file.class_obj.id].append(file)
        
        # Получаем домашние задания для этого дня
        homework_by_class = {}
        homeworks = Homework.objects.filter(
            class_obj__in=classes,
            date=day
        ).select_related('class_obj')
        for hw in homeworks:
            homework_by_class[hw.class_obj.id] = hw
        
        # Список классов, которые уже добавлены в расписание на этот день
        processed_classes = set()
        
        # Сначала добавляем уроки с посещениями
        for class_id, date in attendance_by_class_and_date.keys():
            if date == day and class_id not in processed_classes:
                # Получаем посещение
                attendance = attendance_by_class_and_date.get((class_id, date))
                
                # Получаем расписание для этого класса
                class_schedule = None
                for schedule in schedules:
                    if schedule.class_obj.id == class_id:
                        class_schedule = schedule
                        break
                
                if class_schedule:
                    # Получаем запрос на отмену
                    cancellation_request = cancellation_by_class_and_date.get((class_id, date))
                    
                    # Проверяем, хватает ли баланса на урок
                    class_price = class_schedule.class_obj.price_per_lesson
                    has_enough_balance = student.balance >= class_price
                    
                    # Получаем оценку
                    mark = marks_by_class.get(class_id)
                    
                    # Получаем материалы
                    classwork_files = classwork_files_by_class.get(class_id, [])
                    
                    # Получаем домашнее задание
                    homework = homework_by_class.get(class_id)
                    
                    day_schedules.append({
                        'schedule': class_schedule,
                        'attendance': attendance,
                        'cancellation_request': cancellation_request,
                        'has_enough_balance': has_enough_balance,
                        'class_price': class_price,
                        'mark': mark,
                        'classwork_files': classwork_files,
                        'homework': homework,
                        'is_past': day < today,
                        'is_today': day == today
                    })
                    
                    # Отмечаем класс как обработанный
                    processed_classes.add(class_id)
        
        # Затем добавляем уроки по расписанию
        # Затем добавляем уроки по расписанию, которые еще не были добавлены
        for schedule in schedules:
            # Проверяем, что класс еще не был добавлен и день недели совпадает
            if schedule.class_obj.id not in processed_classes and schedule.day_of_week == day.weekday():
                # Проверяем, что дата урока не раньше даты зачисления
                if schedule.class_obj.id in enrollment_dates:
                    enrollment_date = enrollment_dates[schedule.class_obj.id]
                    # Преобразуем day в datetime для корректного сравнения
                    current_day_datetime = day
                    if isinstance(day, datetime_date) and not isinstance(day, datetime):
                        # Если это объект date, но не datetime, преобразуем его в datetime
                        current_day_datetime = datetime.combine(day, datetime.min.time())
                    # Обрабатываем часовой пояс
                    if timezone.is_aware(current_day_datetime):
                        current_day_datetime = timezone.make_naive(current_day_datetime)
                    elif not timezone.is_aware(enrollment_date):
                        # Если enrollment_date без часового пояса, то ничего не делаем
                        pass
                    else:
                        # Если enrollment_date с часовым поясом, добавляем часовой пояс к current_day_datetime
                        current_day_datetime = timezone.make_aware(current_day_datetime)
                    
                    # Пропускаем уроки до даты зачисления
                    if current_day_datetime < enrollment_date:
                        continue
                    
                    # Получаем запрос на отмену
                    cancellation_request = cancellation_by_class_and_date.get((schedule.class_obj.id, day))
                    
                    # Проверяем, хватает ли баланса на урок
                    class_price = schedule.class_obj.price_per_lesson
                    has_enough_balance = student.balance >= class_price
                    
                    # Получаем оценку
                    mark = marks_by_class.get(schedule.class_obj.id)
                    
                    # Получаем материалы
                    classwork_files = classwork_files_by_class.get(schedule.class_obj.id, [])
                    
                    # Получаем домашнее задание
                    homework = homework_by_class.get(schedule.class_obj.id)
                    
                    # Получаем посещение (должно быть None, так как мы уже обработали все посещения)
                    attendance = attendance_by_class_and_date.get((schedule.class_obj.id, day))
                    
                    day_schedules.append({
                        'schedule': schedule,
                        'attendance': attendance,
                        'cancellation_request': cancellation_request,
                        'has_enough_balance': has_enough_balance,
                        'class_price': class_price,
                        'mark': mark,
                        'classwork_files': classwork_files,
                        'homework': homework,
                        'is_past': day < today,
                        'is_today': day == today
                    })
                    
                    # Отмечаем класс как обработанный
                    processed_classes.add(schedule.class_obj.id)
        
        calendar_days.append({
            'date': day,
            'is_today': day == today,
            'is_weekend': day.weekday() >= 5,  # 5 и 6 - это суббота и воскресенье
            'schedules': sorted(day_schedules, key=lambda x: x['schedule'].start_time)
        })
    
    context = {
        'calendar_days': calendar_days,
        'today': today,
        'student': student,
        'is_self_managed': student.is_self_managed,
        'week_offset': week_offset,
        'prev_week_offset': week_offset - 1,
        'next_week_offset': week_offset + 1,
        'start_of_week': start_of_week,
        'end_of_week': start_of_week + timedelta(days=6)  # Конец недельного периода
    }
    
    return render(request, 'classes/student_schedule.html', context)


# Представление для отображения уроков и оценок ребенка для родителя
@login_required
def parent_child_lessons(request, student_id):
    # Проверяем, что пользователь - родитель
    if not request.user.is_parent:
        messages.error(request, 'У вас нет доступа к этой странице.')
        return redirect('core:home')
    
    # Проверяем, что студент принадлежит этому родителю
    try:
        parent = Parent.objects.get(user=request.user)
        student = Student.objects.get(id=student_id, parent=parent)
    except (Parent.DoesNotExist, Student.DoesNotExist):
        messages.error(request, 'Студент не найден или не принадлежит вам.')
        return redirect('accounts:parent_dashboard')
    
    # Получаем все классы студента
    enrollments = Enrollment.objects.filter(student=student)
    classes = [enrollment.class_obj for enrollment in enrollments]
    
    # Получаем все посещения и оценки студента
    attendances = Attendance.objects.filter(student=student).order_by('-date')
    activity_marks = Mark.objects.filter(student=student).order_by('-date')
    
    # Создаем словарь оценок по датам и классам
    marks_dict = {}
    for mark in activity_marks:
        key = (mark.date, mark.class_obj.id)
        marks_dict[key] = mark
    
    # Формируем данные для шаблона
    classes_data = []
    
    for class_obj in classes:
        # Фильтруем посещения для этого класса
        class_attendances = [a for a in attendances if a.class_obj.id == class_obj.id]
        
        # Создаем список данных о посещениях и оценках
        attendance_data = []
        
        for attendance in class_attendances:
            # Получаем оценку для этого посещения, если она есть
            key = (attendance.date, class_obj.id)
            mark = marks_dict.get(key, None)
            
            # Формируем данные об оценке
            mark_data = {
                'activity_mark': mark.activity_mark if mark else None,
                'teacher_comment': mark.teacher_comment if mark else None
            }
            
            # Добавляем данные о посещении и оценке
            attendance_data.append({
                'attendance': attendance,
                'mark': mark_data
            })
        
        # Добавляем данные о классе
        classes_data.append({
            'class': class_obj,
            'attendance_data': attendance_data
        })
    
    context = {
        'student': student,
        'classes_data': classes_data
    }
    
    return render(request, 'classes/parent_child_lessons.html', context)


# Представление для отображения прошлых занятий ребенка для родителя
@login_required
def parent_child_past_lessons(request, student_id):
    # Проверяем, что пользователь - родитель
    if not request.user.is_parent:
        messages.error(request, 'У вас нет доступа к этой странице.')
        return redirect('core:home')
    
    # Проверяем, что студент принадлежит этому родителю
    try:
        parent = Parent.objects.get(user=request.user)
        student = Student.objects.get(id=student_id, parent=parent)
    except (Parent.DoesNotExist, Student.DoesNotExist):
        messages.error(request, 'Студент не найден или не принадлежит вам.')
        return redirect('accounts:parent_dashboard')
    
    # Получаем все посещения студента, отсортированные по дате (последние сначала)
    attendances = Attendance.objects.filter(student=student).order_by('-date')
    
    context = {
        'student': student,
        'attendances': attendances,
    }
    
    return render(request, 'classes/parent_child_past_lessons.html', context)


# Представление для отображения домашних заданий ребенка для родителя
@login_required
def parent_child_homework(request, student_id):
    # Проверяем, что пользователь - родитель
    if not request.user.is_parent:
        messages.error(request, 'У вас нет доступа к этой странице.')
        return redirect('core:home')
    
    # Проверяем, что студент принадлежит этому родителю
    try:
        parent = Parent.objects.get(user=request.user)
        student = Student.objects.get(id=student_id, parent=parent)
    except (Parent.DoesNotExist, Student.DoesNotExist):
        messages.error(request, 'Студент не найден или не принадлежит вам.')
        return redirect('accounts:parent_dashboard')
    
    # Получаем все сдачи домашних заданий студента
    submissions = HomeworkSubmission.objects.filter(student=student).order_by('-submission_date')
    
    # Группируем сдачи по классам
    submissions_by_class = {}
    for submission in submissions:
        class_id = submission.homework.class_obj.id
        if class_id not in submissions_by_class:
            submissions_by_class[class_id] = []
        submissions_by_class[class_id].append(submission)
    
    context = {
        'student': student,
        'submissions_by_class': submissions_by_class,
    }
    
    return render(request, 'classes/parent_child_homework.html', context)


def student_past_lessons(request):
    """Отображает список прошедших уроков студента с комментариями, оценками и материалами.
    Самоуправляемые ученики видят комментарии и оценки, несамоуправляемые - только материалы.
    Ученики видят только те уроки, которые были после их регистрации в класс.
    """
    if not request.user.is_student:
        return HttpResponseForbidden("Эта страница доступна только студентам.")
    
    student = get_object_or_404(Student, user=request.user)
    
    # Получаем текущую дату
    today = timezone.now().date()
    
    # Получаем все записи ученика на классы
    enrollments = Enrollment.objects.filter(student=student)
    
    # Фильтры
    class_filter = request.GET.get('class_id')
    status_filter = request.GET.get('status')
    
    # Получаем все классы ученика для фильтра
    student_classes = Class.objects.filter(enrollments__in=enrollments).distinct()
    
    # Создаем список для хранения данных о прошедших уроках
    past_lessons = []
    
    # Перебираем все записи на классы
    for enrollment in enrollments:
        class_obj = enrollment.class_obj
        
        # Если выбран конкретный класс для фильтрации
        if class_filter and int(class_filter) != class_obj.id:
            continue
        
        # Получаем дату зачисления в класс
        enrollment_date = enrollment.enrollment_date
        
        # Получаем все посещения для этого класса
        attendances = Attendance.objects.filter(
            student=student,
            class_obj=class_obj,
            date__lt=today,  # Только прошедшие уроки
            date__gte=enrollment_date  # Только уроки после зачисления
        ).order_by('-date')
        
        # Фильтруем по статусу, если указан
        if status_filter:
            attendances = attendances.filter(status=status_filter)
        
        # Получаем расписание для этого класса
        schedules = ClassSchedule.objects.filter(class_obj=class_obj)
        
        # Создаем словарь для быстрого доступа к расписанию по дню недели
        schedule_dict = {}
        for schedule in schedules:
            schedule_dict[schedule.day_of_week] = schedule
        
        # Перебираем все посещения
        for attendance in attendances:
            # Получаем день недели для этой даты
            day_of_week = attendance.date.weekday()
            
            # Получаем расписание для этого дня
            schedule = schedule_dict.get(day_of_week)
            
            # Получаем оценки и комментарии для этого урока
            try:
                mark = Mark.objects.get(
                    student=student,
                    class_obj=class_obj,
                    date=attendance.date
                )
            except Mark.DoesNotExist:
                mark = None
            
            # Получаем материалы для этого урока
            from classes.models import ClassworkFile
            classwork_files = ClassworkFile.objects.filter(
                class_obj=class_obj,
                date=attendance.date
            )
            
            # Получаем домашнее задание для этого урока
            try:
                homework = Homework.objects.get(
                    class_obj=class_obj,
                    date=attendance.date
                )
            except Homework.DoesNotExist:
                homework = None
            
            # Добавляем информацию в список
            past_lessons.append({
                'class': class_obj,
                'date': attendance.date,
                'schedule': schedule,
                'attendance': attendance,
                'mark': mark,
                'classwork_files': classwork_files,
                'homework': homework,
                'is_self_managed': student.is_self_managed
            })
    
    # Сортируем по дате (сначала самые недавние)
    past_lessons.sort(key=lambda x: x['date'], reverse=True)
    
    context = {
        'student': student,
        'past_lessons': past_lessons,
        'student_classes': student_classes,
        'class_filter': class_filter,
        'status_filter': status_filter,
        'is_self_managed': student.is_self_managed
    }
    
    return render(request, 'classes/student_past_lessons.html', context)

