from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from .models import Class, ClassSchedule, Enrollment, Homework, HomeworkSubmission
from accounts.models import Teacher, Student, Parent
from .forms import ClassForm, ClassScheduleForm, HomeworkForm, HomeworkSubmissionForm, AddStudentForm, HomeworkGradeForm
from datetime import datetime, timedelta
import os
from django.utils import timezone
from attendance.models import Attendance, Mark

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
    
    # Проверка доступа - ограничиваем доступ только для администраторов, ресепшена и учителей
    if not (request.user.is_admin or request.user.is_reception or 
            (request.user.is_teacher and class_obj.teacher.user == request.user)):
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
                    schedule = ClassSchedule(
                        class_obj=class_obj,
                        day_of_week=int(day),
                        start_time=start_time,
                        end_time=end_time,
                        room=room
                    )
                    schedule.save()
                    schedules_created += 1
            
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
        form = HomeworkForm(request.POST, request.FILES)
        if form.is_valid():
            homework = form.save(commit=False)
            homework.class_obj = class_obj
            homework.save()
            messages.success(request, "Домашнее задание успешно добавлено.")
            return redirect('classes:class_detail', class_id=class_obj.id)
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
    """Удаляет студента из класса."""
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    class_obj = enrollment.class_obj
    student = enrollment.student
    
    # Проверка доступа
    if not (request.user.is_admin or request.user.is_reception):
        return HttpResponseForbidden("Только администраторы и ресепшн могут удалять студентов из класса.")
    
    if request.method == 'POST':
        # Удаляем запись о зачислении
        enrollment.delete()
        
        messages.success(request, f"Студент {student.full_name} успешно удален из класса.")
        return redirect('classes:class_detail', class_id=class_obj.id)
    
    return render(request, 'classes/confirm_delete.html', {
        'object': enrollment,
        'title': 'Удаление студента из класса',
        'message': f'Вы уверены, что хотите удалить студента {student.full_name} из класса {class_obj.name}?',
        'cancel_url': 'classes:class_detail',
        'cancel_id': class_obj.id
    })

@login_required
def student_classes(request):
    """Отображает список классов студента с дополнительной информацией."""
    if not request.user.is_student:
        return HttpResponseForbidden("Эта страница доступна только студентам.")
    
    student = get_object_or_404(Student, user=request.user)
    enrollments = Enrollment.objects.filter(student=student)
    classes = Class.objects.filter(enrollments__in=enrollments).order_by('name')
    
    # Получаем дополнительную информацию для каждого класса
    classes_with_info = []
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
    
    return render(request, 'classes/student_classes.html', {
        'classes_with_info': classes_with_info,
        'student': student
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
    
    return render(request, 'classes/all_student_homework.html', {
        'student': student,
        'homework_data': homework_data
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
def teacher_schedule(request):
    """Отображает расписание занятий учителя с возможностью запросить отмену урока."""
    if not request.user.is_teacher:
        return HttpResponseForbidden("Эта страница доступна только учителям.")
    
    teacher = get_object_or_404(Teacher, user=request.user)
    
    # Получаем все классы учителя
    classes = Class.objects.filter(teacher=teacher)
    
    # Получаем расписание для всех классов
    schedules = ClassSchedule.objects.filter(class_obj__in=classes).select_related('class_obj')
    
    # Получаем текущую дату и начало недели (понедельник)
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    
    # Создаем календарь на 2 недели (текущую и следующую)
    calendar_days = []
    for i in range(14):
        day = start_of_week + timedelta(days=i)
        day_schedules = []
        
        for schedule in schedules:
            if schedule.day_of_week == day.weekday():
                # Проверяем, есть ли запрос на отмену для этого урока и даты
                from attendance.models import CancellationRequest
                cancellation_request = CancellationRequest.objects.filter(
                    teacher=teacher,
                    class_obj=schedule.class_obj,
                    date=day,
                ).first()
                
                day_schedules.append({
                    'schedule': schedule,
                    'cancellation_request': cancellation_request
                })
        
        calendar_days.append({
            'date': day,
            'schedules': sorted(day_schedules, key=lambda x: x['schedule'].start_time)
        })
    
    # Получаем запросы на отмену уроков
    from attendance.models import CancellationRequest
    pending_requests = CancellationRequest.objects.filter(
        teacher=teacher,
        status='pending'
    ).count()
    
    # Получаем уроки замены
    from attendance.models import Attendance
    substitute_classes = Attendance.objects.filter(
        substitute_teacher=teacher,
        is_canceled=True,
        date__gte=today
    ).values('class_obj', 'date').distinct().count()
    
    context = {
        'calendar_days': calendar_days,
        'today': today,
        'pending_requests': pending_requests,
        'substitute_classes': substitute_classes
    }
    
    return render(request, 'classes/teacher_schedule.html', context)

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
    # Простой тест для проверки работы URL
    from django.http import HttpResponse
    return HttpResponse(f"Тестовая страница домашних заданий для студента {student_id}")
