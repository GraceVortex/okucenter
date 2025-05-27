from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q
from .models import Attendance, Mark, CanceledAttendance, CancellationRequest, StudentCancellationRequest
from .forms import (
    AttendanceForm, MarkForm, AttendanceFilterForm, CancelAttendanceForm,
    CancellationRequestForm, ApproveCancellationForm, StudentCancellationRequestForm
)
from classes.models import Class, ClassSchedule, Enrollment
from accounts.models import Student, Teacher
from finance.models import Transaction

# Create your views here.

def check_teacher_availability(teacher, date, class_schedule):
    """
    Проверяет, свободен ли учитель в указанное время.
    
    Args:
        teacher (Teacher): Учитель для проверки
        date (date): Дата урока
        class_schedule (ClassSchedule): Расписание класса
    
    Returns:
        tuple: (is_available, conflicting_classes)
            - is_available (bool): True если учитель свободен, иначе False
            - conflicting_classes (list): Список конфликтующих классов, если есть
    """
    day_of_week = date.weekday()
    
    # Проверяем, нет ли у учителя других уроков в это время
    conflicting_schedules = ClassSchedule.objects.filter(
        class_obj__teacher=teacher,
        day_of_week=day_of_week,
        start_time=class_schedule.start_time
    ).select_related('class_obj')
    
    conflicting_classes = []
    for schedule in conflicting_schedules:
        conflicting_classes.append({
            'class_obj': schedule.class_obj,
            'schedule': schedule
        })
    
    # Проверяем, нет ли у учителя уроков замены в это время
    substitute_attendances = Attendance.objects.filter(
        substitute_teacher=teacher,
        date=date,
        is_canceled=True,
        class_schedule__start_time=class_schedule.start_time
    ).select_related('class_obj', 'class_schedule')
    
    for attendance in substitute_attendances:
        conflicting_classes.append({
            'class_obj': attendance.class_obj,
            'schedule': attendance.class_schedule,
            'is_substitute': True
        })
    
    return (len(conflicting_classes) == 0, conflicting_classes)

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
    
    # Получаем текущую дату и время
    now = timezone.now()
    today = now.date()
    
    # Проверяем, передана ли дата в URL
    date_str = request.GET.get('date')
    specific_date = None
    specific_schedule = None
    schedule_id = request.GET.get('schedule_id')
    
    # Устанавливаем дату посещения по умолчанию
    attendance_date = today
    
    if date_str:
        try:
            specific_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            attendance_date = specific_date
            
            # Находим расписание для этого дня недели
            day_of_week = specific_date.weekday()
            
            # Если передан ID расписания, используем его
            if schedule_id:
                try:
                    specific_schedule = ClassSchedule.objects.get(id=schedule_id, class_obj=class_obj)
                except ClassSchedule.DoesNotExist:
                    specific_schedule = schedules.filter(day_of_week=day_of_week).first()
            else:
                specific_schedule = schedules.filter(day_of_week=day_of_week).first()
            
            if specific_schedule:
                # Проверяем, не прошло ли более 24 часов с начала урока
                lesson_datetime = datetime.combine(
                    specific_date, 
                    specific_schedule.start_time, 
                    tzinfo=timezone.get_current_timezone()
                )
                time_difference = (now - lesson_datetime).total_seconds() / 3600
                
                # Отключаем проверку на 24 часа для учителей
                if request.user.is_teacher:
                    pass  # Учителя могут отмечать посещаемость в любое время
                elif time_difference < 0 or time_difference > 24:
                    messages.error(request, "Отметить посещаемость можно только в течение 24 часов после начала урока.")
                    return redirect('classes:class_detail', class_id=class_id)
            else:
                messages.error(request, f"В этот день ({specific_date.strftime('%d.%m.%Y')}) нет занятий для данного класса.")
                return redirect('classes:class_detail', class_id=class_id)
        except ValueError:
            messages.error(request, "Неверный формат даты.")
            return redirect('classes:class_detail', class_id=class_id)
    
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
                    date=specific_date or today,
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
                
                # Если и учитель, и ресепшн подтвердили посещение, и статус "present" или "absent",
                # то списываем деньги со счета студента
                # Списываем деньги как при присутствии, так и при пропуске без уважительной причины
                if (attendance.teacher_confirmed and attendance.reception_confirmed and 
                    (attendance.status == 'present' or attendance.status == 'absent')):
                    
                    with transaction.atomic():
                        # Проверяем, не была ли уже списана оплата за это занятие
                        transaction_exists = Transaction.objects.filter(
                            student=student,
                            class_obj=class_obj,
                            date=specific_date or today,
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
                                date=attendance_date,
                                transaction_type='payment',
                                description=f'Оплата за занятие {class_obj.name} от {attendance_date.strftime("%d.%m.%Y")}'
                            )
        
        messages.success(request, "Посещаемость успешно отмечена.")
        
        # Проверяем, откуда пришел пользователь
        from_teacher_today = request.POST.get('from_teacher_today')
        if from_teacher_today:
            return redirect('classes:teacher_today_schedule')
        else:
            return redirect('attendance:attendance_list')
    
    # Проверяем, есть ли уже записи о посещаемости на указанную дату
    # Обновляем дату посещения, если указана конкретная дата
    if specific_date:
        attendance_date = specific_date
        
    # Получаем существующие записи о посещаемости для этого класса и даты
    existing_attendances = Attendance.objects.filter(
        class_obj=class_obj,
        date=attendance_date
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
        'schedules': schedules if not specific_schedule else None,
        'specific_schedule': specific_schedule,
        'today': attendance_date,
        'attendance_dict': attendance_dict,
        'from_teacher_today': request.GET.get('from_teacher_today', False),
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
    
    # Если и учитель, и ресепшн подтвердили посещение, и статус "present" или "absent",
    # то списываем деньги со счета студента
    # Списываем деньги как при присутствии, так и при пропуске без уважительной причины
    if (attendance.teacher_confirmed and attendance.reception_confirmed and 
        (attendance.status == 'present' or attendance.status == 'absent')):
        
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
                        
                        # Создаем запись о возврате средств
                        # Для возврата используем тип 'refund' и отрицательную сумму
                        Transaction.objects.create(
                            student=attendance.student,
                            class_obj=attendance.class_obj,
                            amount=-refund_amount,  # Отрицательная сумма для возврата
                            date=timezone.now().date(),
                            transaction_type='refund',  # Правильный тип для возврата
                            description=f'Возврат средств за отмененное занятие {attendance.class_obj.name} от {attendance.date.strftime("%d.%m.%Y")}',
                            created_by=request.user
                        )
                        
                        # Обновляем баланс студента
                        # Баланс обновится автоматически при создании транзакции типа 'refund'
                        attendance.student.refresh_from_db()
                    
                    # Отменяем подтверждение посещения и меняем статус на "отсутствует"
                    attendance.reception_confirmed = False
                    attendance.status = 'absent'  # Меняем статус на "отсутствует"
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
            
            # Проверяем доступность заменяющего учителя, если он указан
            if form.cleaned_data.get('needs_substitute'):
                substitute_teacher = form.cleaned_data.get('substitute_teacher')
                cancellation_request.substitute_teacher = substitute_teacher
                
                # Проверяем, свободен ли заменяющий учитель в это время
                is_available, conflicting_classes = check_teacher_availability(
                    substitute_teacher, date, class_schedule
                )
                
                if not is_available:
                    # Показываем предупреждение, но не блокируем создание запроса
                    conflict_messages = []
                    for conflict in conflicting_classes:
                        if conflict.get('is_substitute'):
                            conflict_messages.append(
                                f"Урок замены: {conflict['class_obj'].name} ({conflict['schedule'].get_start_time_display()}-{conflict['schedule'].get_end_time_display()})"
                            )
                        else:
                            conflict_messages.append(
                                f"Основной урок: {conflict['class_obj'].name} ({conflict['schedule'].get_start_time_display()}-{conflict['schedule'].get_end_time_display()})"
                            )
                    
                    conflict_text = "\n- ".join(conflict_messages)
                    messages.warning(
                        request, 
                        f"Внимание! У заменяющего учителя {substitute_teacher.full_name} есть конфликты в расписании на {date.strftime('%d.%m.%Y')}:\n- {conflict_text}\n\nЗапрос на замену всё равно создан."
                    )
            
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
            
            # Проверяем доступность заменяющего учителя, если он указан
            if substitute_teacher:
                is_available, conflicting_classes = check_teacher_availability(
                    substitute_teacher, cancellation_request.date, cancellation_request.class_schedule
                )
                
                if not is_available:
                    # Показываем предупреждение, но не блокируем подтверждение
                    conflict_messages = []
                    for conflict in conflicting_classes:
                        if conflict.get('is_substitute'):
                            conflict_messages.append(
                                f"Урок замены: {conflict['class_obj'].name} ({conflict['schedule'].get_start_time_display()}-{conflict['schedule'].get_end_time_display()})"
                            )
                        else:
                            conflict_messages.append(
                                f"Основной урок: {conflict['class_obj'].name} ({conflict['schedule'].get_start_time_display()}-{conflict['schedule'].get_end_time_display()})"
                            )
                    
                    conflict_text = "\n- ".join(conflict_messages)
                    messages.warning(
                        request, 
                        f"Внимание! У заменяющего учителя {substitute_teacher.full_name} есть конфликты в расписании на {cancellation_request.date.strftime('%d.%m.%Y')}:\n- {conflict_text}\n\nЗапрос на замену всё равно будет подтвержден."
                    )
            
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


@login_required
def student_cancel_lesson(request, class_id, schedule_id, date):
    """
    Представление для создания запроса на отмену занятия студентом.
    Студент может отменить занятие только если он самоуправляемый и до занятия осталось более 24 часов.
    """
    # Проверяем, что пользователь - студент
    if not request.user.is_student:
        return HttpResponseForbidden("Только студенты могут отменять свои занятия.")
    
    # Получаем профиль студента
    student = request.user.student_profile
    
    # Проверяем, является ли студент самоуправляемым
    if not student.is_self_managed:
        return HttpResponseForbidden("Только самоуправляемые студенты могут отменять свои занятия. Обратитесь к родителю.")
    
    # Получаем класс и расписание
    class_obj = get_object_or_404(Class, id=class_id)
    class_schedule = get_object_or_404(ClassSchedule, id=schedule_id, class_obj=class_obj)
    
    # Преобразуем дату из строки в объект date
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Неверный формат даты.")
        return redirect('classes:student_classes')
    
    # Проверяем, что студент записан на этот класс
    if not Enrollment.objects.filter(student=student, class_obj=class_obj).exists():
        return HttpResponseForbidden("Вы не записаны на этот класс.")
    
    # Проверяем, что дата в будущем
    if date_obj < timezone.now().date():
        messages.error(request, "Нельзя отменить занятие на прошедшую дату.")
        return redirect('classes:student_classes')
    
    # Создаем форму
    if request.method == 'POST':
        form = StudentCancellationRequestForm(
            request.POST,
            student=student,
            class_obj=class_obj,
            class_schedule=class_schedule,
            date=date_obj,
            user=request.user
        )
        
        if form.is_valid():
            try:
                # Создаем запрос на отмену
                cancellation_request = form.save()
                
                # Создаем или обновляем запись о посещаемости
                attendance, created = Attendance.objects.get_or_create(
                    student=student,
                    class_obj=class_obj,
                    date=date_obj,
                    defaults={
                        'class_schedule': class_schedule,
                        'status': 'excused',  # Устанавливаем статус "уважительная причина"
                        'teacher_confirmed': False,
                        'reception_confirmed': False
                    }
                )
                
                # Связываем запрос на отмену с записью о посещаемости
                cancellation_request.attendance = attendance
                cancellation_request.save()
                
                messages.success(request, "Запрос на отмену занятия успешно создан и ожидает подтверждения.")
                return redirect('attendance:student_cancellation_requests')
            
            except Exception as e:
                messages.error(request, f"Произошла ошибка при создании запроса: {str(e)}")
    else:
        form = StudentCancellationRequestForm(
            student=student,
            class_obj=class_obj,
            class_schedule=class_schedule,
            date=date_obj,
            user=request.user
        )
    
    # Получаем информацию о занятии для отображения
    lesson_info = {
        'class_name': class_obj.name,
        'teacher_name': class_obj.teacher.full_name,
        'date': date_obj,
        'time': f"{class_schedule.start_time.strftime('%H:%M')} - {class_schedule.end_time.strftime('%H:%M')}",
        'room': class_schedule.room
    }
    
    context = {
        'form': form,
        'lesson_info': lesson_info,
        'class_obj': class_obj,
        'class_schedule': class_schedule,
        'date': date_obj
    }
    
    return render(request, 'attendance/student_cancel_lesson.html', context)


@login_required
def student_cancellation_requests(request):
    """
    Представление для просмотра списка запросов на отмену занятий студентом.
    """
    # Проверяем, что пользователь - студент
    if not request.user.is_student:
        return HttpResponseForbidden("Только студенты могут просматривать свои запросы на отмену занятий.")
    
    # Получаем профиль студента
    student = request.user.student_profile
    
    # Получаем запросы на отмену занятий
    cancellation_requests = StudentCancellationRequest.objects.filter(student=student).order_by('-created_at')
    
    context = {
        'cancellation_requests': cancellation_requests
    }
    
    return render(request, 'attendance/student_cancellation_requests.html', context)


@login_required
def parent_cancel_lesson(request, student_id, class_id, schedule_id, date):
    """
    Представление для создания запроса на отмену занятия родителем.
    Родитель может отменить занятие только для своих детей и до занятия должно оставаться более 24 часов.
    """
    # Проверяем, что пользователь - родитель
    if not request.user.is_parent:
        return HttpResponseForbidden("Только родители могут отменять занятия своих детей.")
    
    # Получаем профиль родителя
    parent = request.user.parent_profile
    
    # Получаем студента
    student = get_object_or_404(Student, id=student_id)
    
    # Проверяем, что студент - ребенок этого родителя
    if student.parent != parent:
        return HttpResponseForbidden("Вы можете отменять занятия только своих детей.")
    
    # Получаем класс и расписание
    class_obj = get_object_or_404(Class, id=class_id)
    class_schedule = get_object_or_404(ClassSchedule, id=schedule_id, class_obj=class_obj)
    
    # Преобразуем дату из строки в объект date
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Неверный формат даты.")
        return redirect('accounts:parent_children')
    
    # Проверяем, что студент записан на этот класс
    if not Enrollment.objects.filter(student=student, class_obj=class_obj).exists():
        return HttpResponseForbidden("Ваш ребенок не записан на этот класс.")
    
    # Проверяем, что дата в будущем
    if date_obj < timezone.now().date():
        messages.error(request, "Нельзя отменить занятие на прошедшую дату.")
        return redirect('accounts:parent_children')
    
    # Создаем форму
    if request.method == 'POST':
        form = StudentCancellationRequestForm(
            request.POST,
            student=student,
            class_obj=class_obj,
            class_schedule=class_schedule,
            date=date_obj,
            user=request.user
        )
        
        if form.is_valid():
            try:
                # Создаем запрос на отмену
                cancellation_request = form.save()
                
                # Создаем или обновляем запись о посещаемости
                attendance, created = Attendance.objects.get_or_create(
                    student=student,
                    class_obj=class_obj,
                    date=date_obj,
                    defaults={
                        'class_schedule': class_schedule,
                        'status': 'excused',  # Устанавливаем статус "уважительная причина"
                        'teacher_confirmed': False,
                        'reception_confirmed': False
                    }
                )
                
                # Связываем запрос на отмену с записью о посещаемости
                cancellation_request.attendance = attendance
                cancellation_request.save()
                
                messages.success(request, "Запрос на отмену занятия успешно создан и ожидает подтверждения.")
                return redirect('accounts:parent_children')
            
            except Exception as e:
                messages.error(request, f"Произошла ошибка при создании запроса: {str(e)}")
    else:
        form = StudentCancellationRequestForm(
            student=student,
            class_obj=class_obj,
            class_schedule=class_schedule,
            date=date_obj,
            user=request.user
        )
    
    # Получаем информацию о занятии для отображения
    lesson_info = {
        'student_name': student.full_name,
        'class_name': class_obj.name,
        'teacher_name': class_obj.teacher.full_name,
        'date': date_obj,
        'time': f"{class_schedule.start_time.strftime('%H:%M')} - {class_schedule.end_time.strftime('%H:%M')}",
        'room': class_schedule.room
    }
    
    context = {
        'form': form,
        'lesson_info': lesson_info,
        'student': student,
        'class_obj': class_obj,
        'class_schedule': class_schedule,
        'date': date_obj
    }
    
    return render(request, 'attendance/parent_cancel_lesson.html', context)


@login_required
def cancel_student_cancellation_request(request, request_id):
    """
    Отмена запроса на отмену занятия студентом или родителем.
    Запрос можно отменить в любом статусе (ожидающий, подтвержденный, отклоненный).
    """
    try:
        cancellation_request = StudentCancellationRequest.objects.get(id=request_id)
    except StudentCancellationRequest.DoesNotExist:
        messages.error(request, "Запрос на отмену занятия не найден.")
        if request.user.is_student:
            return redirect('attendance:student_cancellation_requests')
        elif request.user.is_parent:
            return redirect('accounts:parent_cancellation_requests')
        else:
            return redirect('home')
    
    # Проверяем права доступа
    if request.user.is_student:
        # Студент может отменить только свои запросы
        if cancellation_request.student.user != request.user:
            return HttpResponseForbidden("Вы можете отменить только свои запросы на отмену занятий.")
    elif request.user.is_parent:
        # Родитель может отменить запросы своих детей
        try:
            parent = Parent.objects.get(user=request.user)
            if cancellation_request.student.parent != parent:
                return HttpResponseForbidden("Вы можете отменить только запросы на отмену занятий ваших детей.")
        except Parent.DoesNotExist:
            return HttpResponseForbidden("Профиль родителя не найден.")
    else:
        # Администраторы и ресепшнисты также могут отменять запросы
        if not (request.user.is_admin or request.user.is_reception):
            return HttpResponseForbidden("У вас нет прав для отмены запросов на отмену занятий.")
    
    # Используем транзакцию для обеспечения целостности данных
    with transaction.atomic():
        # Сохраняем информацию о запросе перед удалением
        student = cancellation_request.student
        class_obj = cancellation_request.class_obj
        class_schedule = cancellation_request.class_schedule
        date = cancellation_request.date
        old_status = cancellation_request.get_status_display()
        attendance = cancellation_request.attendance
        
        # Удаляем запрос на отмену
        cancellation_request.delete()
    
    messages.success(request, f"Запрос на отмену занятия успешно отменен. Предыдущий статус: {old_status}")
    
    # Перенаправляем пользователя в зависимости от его роли
    if request.user.is_student:
        return redirect('attendance:student_cancellation_requests')
    elif request.user.is_parent:
        return redirect('accounts:parent_cancellation_requests')
    elif request.user.is_admin or request.user.is_reception:
        return redirect('attendance:admin_student_cancellation_requests')
    else:
        return redirect('home')

@login_required
def admin_student_cancellation_requests(request):
    """
    Представление для просмотра и обработки запросов на отмену занятий администратором/ресепшнистом.
    """
    # Проверяем, что пользователь - администратор или ресепшн
    if not (request.user.is_admin or request.user.is_reception):
        return HttpResponseForbidden("Только администраторы и ресепшн могут просматривать запросы на отмену занятий.")
    
    # Получаем запросы на отмену занятий
    # По умолчанию показываем только ожидающие обработки запросы
    status_filter = request.GET.get('status', 'pending')
    
    if status_filter == 'all':
        cancellation_requests = StudentCancellationRequest.objects.all().order_by('-created_at')
    else:
        cancellation_requests = StudentCancellationRequest.objects.filter(status=status_filter).order_by('-created_at')
    
    # Фильтры по дате
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            cancellation_requests = cancellation_requests.filter(date__gte=start_date)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            cancellation_requests = cancellation_requests.filter(date__lte=end_date)
        except ValueError:
            pass
    
    # Фильтр по студенту
    student_id = request.GET.get('student_id')
    if student_id:
        cancellation_requests = cancellation_requests.filter(student_id=student_id)
    
    # Фильтр по классу
    class_id = request.GET.get('class_id')
    if class_id:
        cancellation_requests = cancellation_requests.filter(class_obj_id=class_id)
    
    # Статистика
    pending_count = StudentCancellationRequest.objects.filter(status='pending').count()
    approved_count = StudentCancellationRequest.objects.filter(status='approved').count()
    rejected_count = StudentCancellationRequest.objects.filter(status='rejected').count()
    
    # Получаем список студентов и классов для фильтров
    students = Student.objects.all()
    classes = Class.objects.all()
    
    context = {
        'cancellation_requests': cancellation_requests,
        'status_filter': status_filter,
        'start_date': start_date,
        'end_date': end_date,
        'student_id': student_id,
        'class_id': class_id,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'students': students,
        'classes': classes
    }
    
    return render(request, 'attendance/admin_student_cancellation_requests.html', context)


@login_required
def process_student_cancellation_request(request, request_id, action):
    """
    Представление для обработки запроса на отмену занятия администратором/ресепшнистом.
    """
    # Проверяем, что пользователь - администратор или ресепшн
    if not (request.user.is_admin or request.user.is_reception):
        return HttpResponseForbidden("Только администраторы и ресепшн могут обрабатывать запросы на отмену занятий.")
    
    # Получаем запрос на отмену
    cancellation_request = get_object_or_404(StudentCancellationRequest, id=request_id)
    
    # Проверяем, что запрос еще не обработан
    if cancellation_request.status != 'pending':
        messages.error(request, "Этот запрос уже обработан.")
        return redirect('attendance:admin_student_cancellation_requests')
    
    # Обрабатываем запрос
    if action == 'approve':
        with transaction.atomic():
            # Обновляем статус запроса
            cancellation_request.status = 'approved'
            cancellation_request.processed_by = request.user
            cancellation_request.save()
            
            # Обновляем запись о посещаемости
            if cancellation_request.attendance:
                attendance = cancellation_request.attendance
                attendance.status = 'excused'  # Устанавливаем статус "уважительная причина"
                attendance.teacher_confirmed = True
                attendance.reception_confirmed = True
                attendance.reception_confirmed_by = request.user
                attendance.save()
                
                # Проверяем, была ли уже списана оплата за это занятие
                payment_transaction = Transaction.objects.filter(
                    student=attendance.student,
                    class_obj=attendance.class_obj,
                    date=attendance.date,
                    transaction_type='payment'
                ).first()
                
                # Если оплата была списана, возвращаем средства
                if payment_transaction:
                    refund_amount = payment_transaction.amount
                    
                    # Создаем запись о возврате средств
                    Transaction.objects.create(
                        student=attendance.student,
                        class_obj=attendance.class_obj,
                        amount=-refund_amount,  # Отрицательная сумма для возврата
                        date=timezone.now().date(),
                        transaction_type='refund',
                        description=f'Возврат средств за отмененное занятие {attendance.class_obj.name} от {attendance.date.strftime("%d.%m.%Y")} (запрос одобрен)',
                        created_by=request.user
                    )
                    
                    # Обновляем баланс студента
                    attendance.student.refresh_from_db()
                    
                    messages.success(request, f"Запрос на отмену занятия успешно подтвержден. На счет студента {attendance.student.full_name} возвращено {refund_amount} тг.")
                else:
                    messages.success(request, "Запрос на отмену занятия успешно подтвержден. Деньги за занятие не будут списаны.")
            else:
                # Создаем запись о посещаемости, если она не существует
                attendance = Attendance.objects.create(
                    student=cancellation_request.student,
                    class_obj=cancellation_request.class_obj,
                    class_schedule=cancellation_request.class_schedule,
                    date=cancellation_request.date,
                    status='excused',  # Устанавливаем статус "уважительная причина"
                    teacher_confirmed=True,
                    reception_confirmed=True,
                    reception_confirmed_by=request.user
                )
                cancellation_request.attendance = attendance
                cancellation_request.save()
                
                messages.success(request, "Запрос на отмену занятия успешно подтвержден. Деньги за занятие не будут списаны.")
    
    elif action == 'reject':
        with transaction.atomic():
            # Обновляем статус запроса
            cancellation_request.status = 'rejected'
            cancellation_request.processed_by = request.user
            cancellation_request.save()
            
            # Обновляем запись о посещаемости
            if cancellation_request.attendance:
                attendance = cancellation_request.attendance
                attendance.status = 'absent'  # Устанавливаем статус "отсутствует"
                attendance.teacher_confirmed = True
                attendance.reception_confirmed = True
                attendance.reception_confirmed_by = request.user
                attendance.save()
                
                # Проверяем, была ли уже списана оплата за это занятие
                payment_transaction = Transaction.objects.filter(
                    student=attendance.student,
                    class_obj=attendance.class_obj,
                    date=attendance.date,
                    transaction_type='payment'
                ).first()
                
                # Если оплата еще не была списана, списываем средства
                if not payment_transaction and attendance.class_obj.price_per_lesson > 0:
                    # Получаем стоимость занятия
                    lesson_price = attendance.class_obj.price_per_lesson
                    
                    # Проверяем, достаточно ли средств на балансе
                    if attendance.student.balance >= lesson_price:
                        # Создаем запись об оплате
                        Transaction.objects.create(
                            student=attendance.student,
                            class_obj=attendance.class_obj,
                            amount=lesson_price,
                            date=attendance.date,
                            transaction_type='payment',
                            description=f'Оплата за занятие {attendance.class_obj.name} от {attendance.date.strftime("%d.%m.%Y")} (запрос на отмену отклонен)',
                            created_by=request.user
                        )
                        
                        # Обновляем баланс студента
                        attendance.student.refresh_from_db()
                        
                        messages.success(request, f"Запрос на отмену занятия отклонен. Со счета студента {attendance.student.full_name} списано {lesson_price} тг.")
                    else:
                        messages.warning(request, f"Запрос на отмену занятия отклонен. Недостаточно средств на балансе студента {attendance.student.full_name} для оплаты занятия.")
                else:
                    messages.success(request, "Запрос на отмену занятия отклонен.")
            else:
                # Создаем запись о посещаемости, если она не существует
                attendance = Attendance.objects.create(
                    student=cancellation_request.student,
                    class_obj=cancellation_request.class_obj,
                    class_schedule=cancellation_request.class_schedule,
                    date=cancellation_request.date,
                    status='absent',  # Устанавливаем статус "отсутствует"
                    teacher_confirmed=True,
                    reception_confirmed=True,
                    reception_confirmed_by=request.user
                )
                cancellation_request.attendance = attendance
                cancellation_request.save()
                
                # Списываем оплату за занятие
                if attendance.class_obj.price_per_lesson > 0:
                    lesson_price = attendance.class_obj.price_per_lesson
                    
                    # Проверяем, достаточно ли средств на балансе
                    if attendance.student.balance >= lesson_price:
                        # Создаем запись об оплате
                        Transaction.objects.create(
                            student=attendance.student,
                            class_obj=attendance.class_obj,
                            amount=lesson_price,
                            date=attendance.date,
                            transaction_type='payment',
                            description=f'Оплата за занятие {attendance.class_obj.name} от {attendance.date.strftime("%d.%m.%Y")} (запрос на отмену отклонен)',
                            created_by=request.user
                        )
                        
                        # Обновляем баланс студента
                        attendance.student.refresh_from_db()
                        
                        messages.success(request, f"Запрос на отмену занятия отклонен. Со счета студента {attendance.student.full_name} списано {lesson_price} тг.")
                    else:
                        messages.warning(request, f"Запрос на отмену занятия отклонен. Недостаточно средств на балансе студента {attendance.student.full_name} для оплаты занятия.")
                else:
                    messages.success(request, "Запрос на отмену занятия отклонен.")
    
    return redirect('attendance:admin_student_cancellation_requests')
