from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Attendance, Mark, CanceledAttendance, CancellationRequest
from .forms import (
    AttendanceForm, MarkForm, AttendanceFilterForm, CancelAttendanceForm,
    CancellationRequestForm, ApproveCancellationForm
)
from classes.models import Class, ClassSchedule, Enrollment
from accounts.models import Student, Teacher
from finance.models import Transaction

# Create your views here.

@login_required
def attendance_list(request):
    """Отображает список посещаемости для текущего пользователя."""
    
    # Запрещаем доступ студентам к странице посещаемости
    if request.user.is_student:
        return HttpResponseForbidden("У вас нет доступа к этой странице.")
    
    # Получаем текущую дату
    today = timezone.now().date()
    
    # Получаем фильтры из формы
    form = AttendanceFilterForm(request.GET or None)
    
    # Начальные значения для фильтров
    start_date = today - timedelta(days=7)
    end_date = today
    selected_class = None
    
    if form.is_valid():
        start_date = form.cleaned_data.get('start_date') or start_date
        end_date = form.cleaned_data.get('end_date') or end_date
        selected_class = form.cleaned_data.get('class_obj')
    
    # Фильтруем данные в зависимости от роли пользователя
    if request.user.is_admin or request.user.is_reception:
        # Администраторы и ресепшн видят все записи о посещаемости
        attendances = Attendance.objects.filter(
            date__range=[start_date, end_date]
        ).select_related('student', 'class_obj', 'class_schedule')
        
        if selected_class:
            attendances = attendances.filter(class_obj=selected_class)
            
        # Получаем все классы для формы фильтрации
        classes = Class.objects.all()
        
    elif request.user.is_teacher:
        # Учителя видят посещаемость только своих классов
        teacher = get_object_or_404(Teacher, user=request.user)
        
        attendances = Attendance.objects.filter(
            class_obj__teacher=teacher,
            date__range=[start_date, end_date]
        ).select_related('student', 'class_obj', 'class_schedule')
        
        if selected_class:
            attendances = attendances.filter(class_obj=selected_class)
            
        # Получаем классы этого учителя для формы фильтрации
        classes = Class.objects.filter(teacher=teacher)
    else:
        # Родители видят посещаемость своих детей
        attendances = Attendance.objects.filter(
            student__parent__user=request.user,
            date__range=[start_date, end_date]
        ).select_related('student', 'class_obj', 'class_schedule')
        
        if selected_class:
            attendances = attendances.filter(class_obj=selected_class)
            
        # Получаем классы детей родителя
        classes = Class.objects.filter(
            enrollments__student__parent__user=request.user
        ).distinct()
    
    # Обновляем форму с доступными классами
    form.fields['class_obj'].queryset = classes
    
    # Для каждого посещения проверяем, есть ли соответствующая транзакция
    attendance_data = []
    for attendance in attendances:
        transaction_exists = Transaction.objects.filter(
            student=attendance.student,
            class_obj=attendance.class_obj,
            date=attendance.date,
            transaction_type='payment'
        ).exists()
        
        attendance_data.append({
            'attendance': attendance,
            'transaction_exists': transaction_exists
        })
    
    context = {
        'attendance_data': attendance_data,
        'form': form,
        'start_date': start_date,
        'end_date': end_date,
        'selected_class': selected_class
    }
    
    return render(request, 'attendance/attendance_list.html', context)

@login_required
def mark_attendance(request, class_id):
    """Отмечает посещаемость для класса."""
    
    class_obj = get_object_or_404(Class, id=class_id)
    
    # Проверяем права доступа
    if not (request.user.is_admin or request.user.is_reception or 
            (request.user.is_teacher and class_obj.teacher.user == request.user)):
        return HttpResponseForbidden("У вас нет прав для отметки посещаемости.")
    
    # Получаем всех студентов, записанных на этот класс
    enrollments = Enrollment.objects.filter(class_obj=class_obj).select_related('student')
    students = [enrollment.student for enrollment in enrollments]
    
    # Получаем расписания для этого класса
    schedules = ClassSchedule.objects.filter(class_obj=class_obj)
    
    # Получаем текущую дату
    today = timezone.now().date()
    
    if request.method == 'POST':
        # Обрабатываем форму отметки посещаемости
        for student in students:
            schedule_id = request.POST.get(f'schedule_{student.id}')
            status = request.POST.get(f'status_{student.id}')
            
            if schedule_id and status:
                schedule = get_object_or_404(ClassSchedule, id=schedule_id)
                
                # Проверяем, существует ли уже запись о посещаемости
                attendance, created = Attendance.objects.get_or_create(
                    student=student,
                    class_obj=class_obj,
                    date=today,
                    defaults={
                        'class_schedule': schedule,
                        'status': status,
                        'teacher_confirmed': request.user.is_teacher,
                        'reception_confirmed': request.user.is_reception or request.user.is_admin
                    }
                )
                
                # Если запись уже существует, обновляем её
                if not created:
                    attendance.class_schedule = schedule
                    attendance.status = status
                    
                    if request.user.is_teacher:
                        attendance.teacher_confirmed = True
                    
                    if request.user.is_reception or request.user.is_admin:
                        attendance.reception_confirmed = True
                    
                    attendance.save()
                
                # Если и учитель, и ресепшн подтвердили посещение, и статус "present",
                # то списываем деньги со счета студента
                if (attendance.teacher_confirmed and attendance.reception_confirmed and 
                    attendance.status == 'present'):
                    
                    with transaction.atomic():
                        # Проверяем, не была ли уже списана оплата за это занятие
                        transaction_exists = Transaction.objects.filter(
                            student=student,
                            class_obj=class_obj,
                            date=today,
                            transaction_type='payment'
                        ).exists()
                        
                        if not transaction_exists:
                            # Списываем деньги со счета студента
                            student.balance -= class_obj.price_per_lesson
                            student.save()
                            
                            # Создаем запись о транзакции
                            Transaction.objects.create(
                                student=student,
                                class_obj=class_obj,
                                amount=class_obj.price_per_lesson,
                                date=today,
                                transaction_type='payment',
                                description=f'Оплата за занятие {class_obj.name} от {today}'
                            )
        
        messages.success(request, "Посещаемость успешно отмечена.")
        return redirect('attendance:attendance_list')
    
    # Проверяем, есть ли уже записи о посещаемости на сегодня
    existing_attendances = Attendance.objects.filter(
        class_obj=class_obj,
        date=today
    ).select_related('student')
    
    # Создаем словарь для хранения существующих записей
    attendance_dict = {
        f"{attendance.student.id}": {
            'schedule': attendance.class_schedule,
            'status': attendance.status
        } for attendance in existing_attendances
    }
    
    context = {
        'class': class_obj,
        'students': students,
        'schedules': schedules,
        'today': today,
        'attendance_dict': attendance_dict,
    }
    
    return render(request, 'attendance/mark_attendance.html', context)

@login_required
def confirm_attendance(request, attendance_id):
    """Подтверждает посещаемость (для ресепшн)."""
    
    attendance = get_object_or_404(Attendance, id=attendance_id)
    
    # Проверяем права доступа
    if not (request.user.is_admin or request.user.is_reception):
        return HttpResponseForbidden("У вас нет прав для подтверждения посещаемости.")
    
    # Подтверждаем посещаемость
    attendance.reception_confirmed = True
    attendance.save()
    
    # Если и учитель, и ресепшн подтвердили посещение, и статус "present",
    # то списываем деньги со счета студента
    if (attendance.teacher_confirmed and attendance.reception_confirmed and 
        attendance.status == 'present'):
        
        try:
            with transaction.atomic():
                # Проверяем, не была ли уже списана оплата за это занятие
                transaction_exists = Transaction.objects.filter(
                    student=attendance.student,
                    class_obj=attendance.class_obj,
                    date=attendance.date,
                    transaction_type='payment'
                ).exists()
                
                if not transaction_exists:
                    # Получаем стоимость занятия
                    lesson_price = attendance.class_obj.price_per_lesson
                    
                    # Списываем деньги со счета студента
                    attendance.student.balance -= lesson_price
                    attendance.student.save()
                    
                    # Создаем запись о транзакции
                    Transaction.objects.create(
                        student=attendance.student,
                        class_obj=attendance.class_obj,
                        amount=lesson_price,
                        date=attendance.date,
                        transaction_type='payment',
                        description=f'Оплата за занятие {attendance.class_obj.name} от {attendance.date.strftime("%d.%m.%Y")}',
                        created_by=request.user
                    )
                    
                    messages.success(
                        request, 
                        f"Посещаемость подтверждена. Со счета студента {attendance.student.full_name} "
                        f"списано {lesson_price} тг за занятие {attendance.class_obj.name}."
                    )
                else:
                    messages.info(request, "Посещаемость подтверждена. Оплата за это занятие уже была списана ранее.")
        except Exception as e:
            messages.error(
                request, 
                f"Ошибка при обработке финансовой операции: {str(e)}. "
                f"Посещаемость подтверждена, но оплата не списана."
            )
    else:
        messages.success(request, "Посещаемость успешно подтверждена.")
    
    # Возвращаемся на предыдущую страницу
    return redirect(request.META.get('HTTP_REFERER', 'attendance:attendance_list'))

@login_required
def add_mark(request, attendance_id):
    """Добавляет оценку и комментарий к посещению."""
    
    attendance = get_object_or_404(Attendance, id=attendance_id)
    
    # Проверяем права доступа
    if not (request.user.is_admin or 
            (request.user.is_teacher and attendance.class_obj.teacher.user == request.user)):
        return HttpResponseForbidden("У вас нет прав для добавления оценок.")
    
    # Проверяем, существует ли уже оценка для этого посещения
    mark, created = Mark.objects.get_or_create(
        student=attendance.student,
        class_obj=attendance.class_obj,
        date=attendance.date
    )
    
    if request.method == 'POST':
        form = MarkForm(request.POST, instance=mark)
        if form.is_valid():
            form.save()
            messages.success(request, "Оценка успешно добавлена.")
            return redirect('attendance:attendance_list')
    else:
        form = MarkForm(instance=mark)
    
    context = {
        'form': form,
        'attendance': attendance,
    }
    
    return render(request, 'attendance/add_mark.html', context)

@login_required
def cancel_attendance(request, attendance_id):
    """Отменяет подтвержденное посещение и возвращает деньги на счет студента."""
    
    # Проверка прав доступа
    if not (request.user.is_reception or request.user.is_admin):
        return HttpResponseForbidden("У вас нет прав для отмены посещений.")
    
    # Получаем объект посещения
    attendance = get_object_or_404(Attendance, id=attendance_id)
    
    # Проверяем, что посещение было подтверждено ресепшеном
    if not attendance.reception_confirmed:
        messages.error(request, "Невозможно отменить неподтвержденное посещение.")
        return redirect('attendance:attendance_list')
    
    if request.method == 'POST':
        form = CancelAttendanceForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            
            try:
                with transaction.atomic():
                    # Проверяем, была ли списана оплата за это занятие
                    payment_transaction = Transaction.objects.filter(
                        student=attendance.student,
                        class_obj=attendance.class_obj,
                        date=attendance.date,
                        transaction_type='payment'
                    ).first()
                    
                    if payment_transaction:
                        # Получаем сумму, которую нужно вернуть
                        refund_amount = payment_transaction.amount
                        
                        # Возвращаем деньги на счет студента
                        attendance.student.balance += refund_amount
                        attendance.student.save()
                        
                        # Создаем запись о возврате средств
                        Transaction.objects.create(
                            student=attendance.student,
                            class_obj=attendance.class_obj,
                            amount=refund_amount,
                            date=timezone.now().date(),
                            transaction_type='deposit',  # Используем deposit вместо refund
                            description=f'Возврат средств за отмененное занятие {attendance.class_obj.name} от {attendance.date.strftime("%d.%m.%Y")}',
                            created_by=request.user
                        )
                    
                    # Отменяем подтверждение посещения
                    attendance.reception_confirmed = False
                    attendance.save()
                    
                    # Создаем запись в журнале отмененных посещений
                    CanceledAttendance.objects.create(
                        attendance=attendance,
                        canceled_by=request.user,
                        reason=reason
                    )
                    
                    if payment_transaction:
                        messages.success(
                            request, 
                            f"Посещение отменено. На счет студента {attendance.student.full_name} "
                            f"возвращено {refund_amount} тг за занятие {attendance.class_obj.name}."
                        )
                    else:
                        messages.success(request, "Посещение отменено. Финансовые операции не требовались.")
                    
                    return redirect('attendance:attendance_list')
                    
            except Exception as e:
                messages.error(
                    request, 
                    f"Ошибка при отмене посещения: {str(e)}. "
                    f"Пожалуйста, попробуйте еще раз или обратитесь к администратору."
                )
    else:
        form = CancelAttendanceForm()
    
    context = {
        'form': form,
        'attendance': attendance
    }
    
    return render(request, 'attendance/cancel_attendance.html', context)

@login_required
def canceled_attendance_list(request):
    """Отображает журнал отмененных посещений."""
    
    # Проверка прав доступа
    if not (request.user.is_reception or request.user.is_admin):
        return HttpResponseForbidden("У вас нет прав для просмотра журнала отмененных посещений.")
    
    # Получаем параметры фильтрации
    form = AttendanceFilterForm(request.GET or None)
    
    # Начальные значения для фильтров
    today = timezone.now().date()
    start_date = today - timedelta(days=30)
    end_date = today
    selected_class = None
    
    if form.is_valid():
        start_date = form.cleaned_data.get('start_date') or start_date
        end_date = form.cleaned_data.get('end_date') or end_date
        selected_class = form.cleaned_data.get('class_obj')
    
    # Получаем список отмененных посещений
    canceled_attendances = CanceledAttendance.objects.filter(
        canceled_at__date__range=[start_date, end_date]
    ).select_related('attendance', 'attendance__student', 'attendance__class_obj', 'canceled_by')
    
    # Применяем дополнительные фильтры
    if selected_class:
        canceled_attendances = canceled_attendances.filter(attendance__class_obj=selected_class)
    
    context = {
        'canceled_attendances': canceled_attendances,
        'form': form,
        'start_date': start_date,
        'end_date': end_date,
        'selected_class': selected_class
    }
    
    return render(request, 'attendance/canceled_attendance_list.html', context)

@login_required
def request_class_cancellation(request, class_id, date=None):
    """
    Позволяет учителю запросить отмену урока.
    """
    if not request.user.is_teacher:
        return HttpResponseForbidden("Только учителя могут запрашивать отмену уроков.")
    
    # Получаем класс
    class_obj = get_object_or_404(Class, id=class_id)
    teacher = get_object_or_404(Teacher, user=request.user)
    
    # Проверяем, что учитель ведет этот класс
    if class_obj.teacher != teacher:
        return HttpResponseForbidden("Вы не можете отменить урок, который не ведете.")
    
    # Если дата не указана, используем текущую
    if date is None:
        date = timezone.now().date()
    else:
        date = datetime.strptime(date, '%Y-%m-%d').date()
    
    # Проверяем, есть ли уже запрос на отмену для этого класса и даты
    existing_request = CancellationRequest.objects.filter(
        class_obj=class_obj,
        date=date,
        status='pending'
    ).first()
    
    if existing_request:
        messages.warning(request, "Запрос на отмену этого урока уже существует и ожидает рассмотрения.")
        return redirect('classes:teacher_schedule')
    
    # Получаем расписание класса на указанную дату
    day_of_week = date.weekday()
    class_schedule = ClassSchedule.objects.filter(
        class_obj=class_obj,
        day_of_week=day_of_week
    ).first()
    
    if not class_schedule:
        messages.error(request, f"Для класса {class_obj.name} нет расписания на {date.strftime('%d.%m.%Y')}.")
        return redirect('classes:teacher_schedule')
    
    if request.method == 'POST':
        form = CancellationRequestForm(request.POST)
        if form.is_valid():
            cancellation_request = form.save(commit=False)
            cancellation_request.teacher = teacher
            cancellation_request.class_obj = class_obj
            cancellation_request.class_schedule = class_schedule
            cancellation_request.date = date
            cancellation_request.needs_substitute = form.cleaned_data.get('needs_substitute')
            
            if form.cleaned_data.get('needs_substitute'):
                cancellation_request.substitute_teacher = form.cleaned_data.get('substitute_teacher')
            
            cancellation_request.save()
            
            messages.success(request, "Запрос на отмену урока успешно отправлен и ожидает подтверждения.")
            return redirect('classes:teacher_schedule')
    else:
        form = CancellationRequestForm()
    
    # Получаем всех учителей, кроме текущего, для выбора заменяющего
    other_teachers = Teacher.objects.exclude(id=teacher.id)
    
    context = {
        'form': form,
        'class_obj': class_obj,
        'date': date,
        'class_schedule': class_schedule,
        'other_teachers': other_teachers
    }
    
    return render(request, 'attendance/request_cancellation.html', context)

@login_required
def cancellation_requests_list(request):
    """
    Отображает список запросов на отмену уроков.
    """
    if request.user.is_teacher:
        # Учителя видят только свои запросы
        teacher = get_object_or_404(Teacher, user=request.user)
        cancellation_requests = CancellationRequest.objects.filter(teacher=teacher)
        
        # Также показываем запросы, где учитель указан как заменяющий
        substitute_requests = CancellationRequest.objects.filter(
            substitute_teacher=teacher,
            status='approved'
        )
        
        context = {
            'cancellation_requests': cancellation_requests,
            'substitute_requests': substitute_requests,
            'is_teacher': True
        }
    elif request.user.is_admin or request.user.is_reception:
        # Админы и ресепшн видят все запросы
        cancellation_requests = CancellationRequest.objects.all()
        
        context = {
            'cancellation_requests': cancellation_requests,
            'is_teacher': False
        }
    else:
        return HttpResponseForbidden("У вас нет доступа к этой странице.")
    
    return render(request, 'attendance/cancellation_requests_list.html', context)

@login_required
def approve_cancellation_request(request, request_id):
    """
    Позволяет администратору или ресепшн подтвердить или отклонить запрос на отмену урока.
    """
    if not request.user.is_admin and not request.user.is_reception:
        return HttpResponseForbidden("Только администраторы и ресепшн могут подтверждать отмену уроков.")
    
    cancellation_request = get_object_or_404(CancellationRequest, id=request_id, status='pending')
    
    if request.method == 'POST':
        form = ApproveCancellationForm(request.POST)
        if form.is_valid():
            approve = form.cleaned_data.get('approve')
            substitute_teacher = form.cleaned_data.get('substitute_teacher')
            
            if approve:
                # Подтверждаем отмену
                with transaction.atomic():
                    # Обновляем статус запроса
                    cancellation_request.status = 'approved'
                    cancellation_request.approved_by = request.user
                    
                    # Если был выбран заменяющий учитель, обновляем запрос
                    if substitute_teacher:
                        cancellation_request.needs_substitute = True
                        cancellation_request.substitute_teacher = substitute_teacher
                    
                    cancellation_request.save()
                    
                    # Получаем всех студентов, записанных на этот класс
                    enrollments = Enrollment.objects.filter(class_obj=cancellation_request.class_obj)
                    
                    # Для каждого студента создаем или обновляем запись о посещаемости
                    for enrollment in enrollments:
                        attendance, created = Attendance.objects.get_or_create(
                            student=enrollment.student,
                            class_obj=cancellation_request.class_obj,
                            date=cancellation_request.date,
                            defaults={
                                'class_schedule': cancellation_request.class_schedule,
                                'status': 'canceled',
                                'is_canceled': True,
                                'teacher_confirmed': True,
                                'reception_confirmed': True
                            }
                        )
                        
                        if not created:
                            attendance.status = 'canceled'
                            attendance.is_canceled = True
                            attendance.teacher_confirmed = True
                            attendance.reception_confirmed = True
                            attendance.save()
                        
                        # Если был выбран заменяющий учитель, обновляем запись
                        if substitute_teacher:
                            attendance.substitute_teacher = substitute_teacher
                            attendance.save()
                
                messages.success(request, "Запрос на отмену урока успешно подтвержден.")
            else:
                # Отклоняем запрос
                cancellation_request.status = 'rejected'
                cancellation_request.save()
                messages.info(request, "Запрос на отмену урока отклонен.")
            
            return redirect('attendance:cancellation_requests_list')
    else:
        form = ApproveCancellationForm()
    
    # Получаем всех учителей, кроме учителя, запросившего отмену
    other_teachers = Teacher.objects.exclude(id=cancellation_request.teacher.id)
    
    context = {
        'form': form,
        'cancellation_request': cancellation_request,
        'other_teachers': other_teachers
    }
    
    return render(request, 'attendance/approve_cancellation.html', context)

@login_required
def substitute_classes_list(request):
    """
    Отображает список уроков, где учитель является заменяющим.
    """
    if not request.user.is_teacher:
        return HttpResponseForbidden("Только учителя могут просматривать уроки замены.")
    
    teacher = get_object_or_404(Teacher, user=request.user)
    
    # Получаем все записи о посещаемости, где учитель указан как заменяющий
    substitute_attendances = Attendance.objects.filter(
        substitute_teacher=teacher,
        is_canceled=True
    ).select_related('class_obj', 'student', 'class_schedule').order_by('date')
    
    # Группируем по дате и классу
    substitute_classes = {}
    for attendance in substitute_attendances:
        key = (attendance.date, attendance.class_obj.id)
        if key not in substitute_classes:
            substitute_classes[key] = {
                'date': attendance.date,
                'class_obj': attendance.class_obj,
                'class_schedule': attendance.class_schedule,
                'attendances': []
            }
        substitute_classes[key]['attendances'].append(attendance)
    
    context = {
        'substitute_classes': substitute_classes.values()
    }
    
    return render(request, 'attendance/substitute_classes_list.html', context)

@login_required
def mark_substitute_attendance(request, class_id, date):
    """
    Позволяет заменяющему учителю отмечать посещаемость и ставить оценки.
    """
    if not request.user.is_teacher:
        return HttpResponseForbidden("Только учителя могут отмечать посещаемость.")
    
    teacher = get_object_or_404(Teacher, user=request.user)
    class_obj = get_object_or_404(Class, id=class_id)
    date_obj = datetime.strptime(date, '%Y-%m-%d').date()
    
    # Проверяем, что учитель является заменяющим для этого класса и даты
    attendances = Attendance.objects.filter(
        class_obj=class_obj,
        date=date_obj,
        substitute_teacher=teacher,
        is_canceled=True
    ).select_related('student')
    
    if not attendances.exists():
        return HttpResponseForbidden("Вы не являетесь заменяющим учителем для этого урока.")
    
    if request.method == 'POST':
        # Обрабатываем форму
        for attendance in attendances:
            status_key = f'status_{attendance.id}'
            homework_key = f'homework_{attendance.id}'
            activity_key = f'activity_{attendance.id}'
            comment_key = f'comment_{attendance.id}'
            
            if status_key in request.POST:
                attendance.status = request.POST[status_key]
                attendance.teacher_confirmed = True
                attendance.reception_confirmed = False  # Сбрасываем флаг подтверждения ресепшеном
                attendance.save()
            
            # Создаем или обновляем оценку
            mark, created = Mark.objects.get_or_create(
                student=attendance.student,
                class_obj=class_obj,
                date=date_obj,
                defaults={
                    'substitute_teacher': teacher
                }
            )
            
            if homework_key in request.POST:
                mark.homework_mark = request.POST[homework_key]
            
            if activity_key in request.POST:
                mark.activity_mark = request.POST[activity_key]
            
            if comment_key in request.POST:
                mark.teacher_comment = request.POST[comment_key]
            
            mark.substitute_teacher = teacher
            mark.save()
        
        messages.success(request, "Посещаемость и оценки успешно обновлены.")
        return redirect('attendance:substitute_classes_list')
    
    # Получаем оценки для студентов
    marks = {}
    for attendance in attendances:
        try:
            mark = Mark.objects.get(
                student=attendance.student,
                class_obj=class_obj,
                date=date_obj
            )
            marks[attendance.student.id] = mark
        except Mark.DoesNotExist:
            marks[attendance.student.id] = None
    
    context = {
        'class_obj': class_obj,
        'date': date_obj,
        'attendances': attendances,
        'marks': marks
    }
    
    return render(request, 'attendance/mark_substitute_attendance.html', context)
