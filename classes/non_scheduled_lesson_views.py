from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db.models import Q
from django.utils import timezone
from django.core.paginator import Paginator

from accounts.models import Student, Teacher
from .non_scheduled_lesson_models import NonScheduledLesson, NonScheduledLessonAttendance
from finance.models import Transaction

@login_required
def non_scheduled_lesson_list(request):
    """
    Отображает список всех уроков не по расписанию.
    Для ресепшениста показывает все уроки, для учителя - только его уроки.
    """
    if not (request.user.is_reception or request.user.is_teacher):
        return HttpResponseForbidden("У вас нет доступа к этой странице")
    
    # Фильтрация по типу урока
    lesson_type = request.GET.get('type', 'all')
    trial_status = request.GET.get('trial_status', 'all')
    
    # Базовый запрос
    lessons = NonScheduledLesson.objects.all()
    
    # Фильтрация для учителя
    if request.user.is_teacher:
        teacher = get_object_or_404(Teacher, user=request.user)
        lessons = lessons.filter(teacher=teacher)
    
    # Фильтрация по типу урока
    if lesson_type != 'all':
        lessons = lessons.filter(lesson_type=lesson_type)
    
    # Фильтрация по статусу пробного урока
    if trial_status != 'all' and lesson_type == 'trial':
        lessons = lessons.filter(trial_status=trial_status)
    
    # Поиск
    search_query = request.GET.get('search', '')
    if search_query:
        lessons = lessons.filter(
            Q(name__icontains=search_query) | 
            Q(teacher__user__first_name__icontains=search_query) |
            Q(teacher__user__last_name__icontains=search_query) |
            Q(students__full_name__icontains=search_query)
        ).distinct()
    
    # Сортировка
    lessons = lessons.order_by('-date', '-time')
    
    # Пагинация
    paginator = Paginator(lessons, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'lesson_type': lesson_type,
        'trial_status': trial_status,
        'search_query': search_query,
    }
    
    return render(request, 'classes/non_scheduled_lesson_list.html', context)

@login_required
def create_non_scheduled_lesson(request):
    """
    Создает новый урок не по расписанию.
    """
    if not request.user.is_reception:
        return HttpResponseForbidden("Только ресепшенист может создавать уроки не по расписанию")
    
    if request.method == 'POST':
        # Отладочный вывод всех данных формы
        print("POST data:", dict(request.POST))
        
        # Получаем данные из формы
        name = request.POST.get('name')
        teacher_id = request.POST.get('teacher')
        student_ids = request.POST.getlist('students')
        
        # Отладочный вывод списка учеников
        print("Student IDs:", student_ids)
        print("Student IDs type:", type(student_ids))
        print("Student IDs length:", len(student_ids))
        
        # Проверяем, что выбран хотя бы один ученик
        if not student_ids:
            messages.error(request, "Необходимо выбрать хотя бы одного ученика")
            teachers = Teacher.objects.all()
            students = Student.objects.all()
            return render(request, 'classes/create_non_scheduled_lesson.html', {
                'teachers': teachers,
                'students': students,
                'form_data': request.POST,  # Возвращаем введенные данные
            })
        
        date = request.POST.get('date')
        time = request.POST.get('time')
        duration = request.POST.get('duration')
        lesson_type = request.POST.get('lesson_type')
        price_per_student = request.POST.get('price_per_student')
        teacher_payment = request.POST.get('teacher_payment')
        notes = request.POST.get('notes')
        
        # Создаем урок
        try:
            teacher = Teacher.objects.get(id=teacher_id)
            
            lesson = NonScheduledLesson(
                name=name,
                teacher=teacher,
                date=date,
                time=time,
                duration=duration,
                lesson_type=lesson_type,
                price_per_student=price_per_student,
                teacher_payment=teacher_payment,
                notes=notes
            )
            lesson.save()
            
            # Добавляем учеников
            # Преобразуем все ID в целые числа, чтобы избежать проблем с типами данных
            student_ids_int = [int(sid) for sid in student_ids if sid.isdigit()]
            print("Converted student IDs:", student_ids_int)
            
            students = Student.objects.filter(id__in=student_ids_int)
            print("Found students:", students.count())
            
            # Проверяем, что ученики были найдены
            if not students.exists():
                messages.error(request, "Не удалось найти выбранных учеников в базе данных")
                lesson.delete()  # Удаляем созданный урок, так как не удалось добавить учеников
                teachers = Teacher.objects.all()
                students = Student.objects.all()
                return render(request, 'classes/create_non_scheduled_lesson.html', {
                    'teachers': teachers,
                    'students': students,
                    'form_data': request.POST,  # Возвращаем введенные данные
                })
            
            # Добавляем учеников к уроку
            lesson.students.set(students)
            print("Students added to lesson:", lesson.students.count())
            
            # Если урок обычный (не пробный), сразу снимаем оплату с учеников
            if lesson_type == 'regular':
                for student in students:
                    student.balance -= float(price_per_student)
                    student.save()
                    
                    # Создаем транзакцию
                    Transaction.objects.create(
                        student=student,
                        amount=float(price_per_student),
                        description=f"Оплата за урок не по расписанию: {name} ({date})",
                        transaction_type='payment',
                        date=date
                    )
            
            messages.success(request, f"Урок успешно создан с {students.count()} учениками")
            return redirect('classes:non_scheduled_lesson_list')
            
        except Exception as e:
            messages.error(request, f"Ошибка при создании урока: {str(e)}")
            import traceback
            print("Exception traceback:", traceback.format_exc())
    
    # Получаем список учителей и учеников для формы
    teachers = Teacher.objects.all()
    students = Student.objects.all()
    
    context = {
        'teachers': teachers,
        'students': students,
    }
    
    return render(request, 'classes/create_non_scheduled_lesson.html', context)

@login_required
def non_scheduled_lesson_detail(request, lesson_id):
    """
    Отображает детали урока не по расписанию.
    """
    if not (request.user.is_reception or request.user.is_teacher):
        return HttpResponseForbidden("У вас нет доступа к этой странице")
    
    lesson = get_object_or_404(NonScheduledLesson, id=lesson_id)
    
    # Проверка доступа для учителя
    if request.user.is_teacher:
        teacher = get_object_or_404(Teacher, user=request.user)
        if lesson.teacher != teacher:
            return HttpResponseForbidden("Вы не можете просматривать чужие уроки")
    
    # Получаем данные о посещаемости
    attendances = NonScheduledLessonAttendance.objects.filter(lesson=lesson)
    
    context = {
        'lesson': lesson,
        'attendances': attendances,
    }
    
    return render(request, 'classes/non_scheduled_lesson_detail.html', context)

@login_required
def update_trial_lesson_status(request, lesson_id):
    """
    Обновляет статус пробного урока (продолжил/не продолжил).
    """
    if not request.user.is_reception:
        return HttpResponseForbidden("Только ресепшенист может обновлять статус пробных уроков")
    
    lesson = get_object_or_404(NonScheduledLesson, id=lesson_id)
    
    if lesson.lesson_type != 'trial':
        messages.error(request, "Этот урок не является пробным")
        return redirect('classes:non_scheduled_lesson_detail', lesson_id=lesson_id)
    
    if request.method == 'POST':
        status = request.POST.get('trial_status')
        
        if status not in ['continued', 'discontinued']:
            messages.error(request, "Некорректный статус")
            return redirect('classes:non_scheduled_lesson_detail', lesson_id=lesson_id)
        
        lesson.trial_status = status
        lesson.save()
        
        # Если ученик продолжил обучение, снимаем оплату
        if status == 'continued':
            for student in lesson.students.all():
                student.balance -= lesson.price_per_student
                student.save()
                
                # Создаем транзакцию
                Transaction.objects.create(
                    student=student,
                    amount=float(lesson.price_per_student),
                    description=f"Оплата за пробный урок (продолжил обучение): {lesson.name} ({lesson.date})",
                    transaction_type='payment',
                    date=lesson.date
                )
        
        messages.success(request, "Статус пробного урока успешно обновлен")
    
    return redirect('classes:non_scheduled_lesson_detail', lesson_id=lesson_id)

@login_required
def mark_attendance(request, lesson_id):
    """
    Отмечает посещаемость для урока не по расписанию.
    """
    if not (request.user.is_reception or request.user.is_teacher):
        return HttpResponseForbidden("У вас нет доступа к этой странице")
    
    lesson = get_object_or_404(NonScheduledLesson, id=lesson_id)
    
    # Проверка доступа для учителя
    if request.user.is_teacher:
        teacher = get_object_or_404(Teacher, user=request.user)
        if lesson.teacher != teacher:
            return HttpResponseForbidden("Вы не можете отмечать посещаемость на чужих уроках")
    
    if request.method == 'POST':
        for student in lesson.students.all():
            is_present = request.POST.get(f'attendance_{student.id}') == 'present'
            
            # Проверяем, существует ли уже запись о посещаемости
            attendance, created = NonScheduledLessonAttendance.objects.get_or_create(
                lesson=lesson,
                student=student,
                defaults={
                    'is_present': is_present,
                    'marked_by': request.user.get_full_name() or request.user.username
                }
            )
            
            # Если запись уже существует, обновляем её
            if not created:
                attendance.is_present = is_present
                attendance.marked_by = request.user.get_full_name() or request.user.username
                attendance.marked_at = timezone.now()
                attendance.save()
        
        # Отмечаем урок как проведенный
        lesson.is_completed = True
        lesson.save()
        
        # Создаем финансовые транзакции для обычных уроков
        if lesson.lesson_type == 'regular':
            for student in lesson.students.all():
                # Проверяем, присутствовал ли ученик на уроке
                attendance = NonScheduledLessonAttendance.objects.filter(lesson=lesson, student=student).first()
                if attendance and attendance.is_present:
                    # Проверяем, существует ли уже транзакция за этот урок
                    existing_transaction = Transaction.objects.filter(
                        student=student,
                        description__contains=f"{lesson.name} ({lesson.date})",
                        transaction_type='payment',
                        date=lesson.date
                    ).exists()
                    
                    # Если транзакции еще нет, создаем ее
                    if not existing_transaction:
                        # Обновляем баланс ученика
                        # Преобразуем все значения к типу Decimal для избежания ошибок типизации
                        from decimal import Decimal
                        student.balance -= lesson.price_per_student  # price_per_student уже является Decimal
                        student.save()
                        
                        # Создаем транзакцию
                        Transaction.objects.create(
                            student=student,
                            amount=lesson.price_per_student,  # Используем Decimal напрямую
                            description=f"Оплата за урок не по расписанию: {lesson.name} ({lesson.date})",
                            transaction_type='payment',
                            date=lesson.date
                        )
        
        messages.success(request, "Посещаемость успешно отмечена")
    
    return redirect('classes:non_scheduled_lesson_detail', lesson_id=lesson_id)
