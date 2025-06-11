from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404, JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta

from accounts.models import Parent, Student
from classes.models import Enrollment, ClassSchedule, Homework, HomeworkSubmission, Class, ClassworkFile
from attendance.models import CancellationRequest, StudentCancellationRequest, Mark, Attendance

@login_required
def parent_child_lessons(request, student_id):
    """
    Отображает список классов и предстоящих уроков ребенка для родителя.
    """
    # Проверяем, что пользователь является родителем
    if not request.user.is_parent:
        return HttpResponseForbidden("Эта страница доступна только родителям.")
    
    # Получаем родителя и студента
    parent = get_object_or_404(Parent, user=request.user)
    student = get_object_or_404(Student, id=student_id)
    
    # Проверяем, что студент является ребенком этого родителя
    if student.parent != parent:
        return HttpResponseForbidden("Вы не являетесь родителем этого студента.")
    
    # Получаем все активные записи студента на классы
    enrollments = Enrollment.objects.filter(student=student, is_active=True)
    
    # Создаем список данных о классах
    classes_data = []
    today = timezone.now().date()
    
    for enrollment in enrollments:
        class_obj = enrollment.class_obj
        
        # Получаем все расписания для этого класса
        schedules = ClassSchedule.objects.filter(class_obj=class_obj)
        
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
            from attendance.models import CancellationRequest
            is_cancelled = CancellationRequest.objects.filter(
                class_obj=class_obj,
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
        
        # Получаем невыполненные домашние задания для этого класса
        # Получаем все домашние задания для класса
        all_homeworks = Homework.objects.filter(
            class_obj=class_obj,
            due_date__gte=today
        ).order_by('due_date')
        
        # Получаем выполненные домашние задания студента
        submitted_homework_ids = HomeworkSubmission.objects.filter(
            student=student,
            homework__class_obj=class_obj
        ).values_list('homework_id', flat=True)
        
        # Фильтруем только невыполненные задания
        pending_homeworks = [hw for hw in all_homeworks if hw.id not in submitted_homework_ids]
        
        # Получаем файлы класса, добавленные после даты зачисления студента
        try:
            # Проверяем, что модель ClassworkFile имеет необходимые поля
            class_files = ClassworkFile.objects.filter(
                class_obj=class_obj
            )
            
            # Проверяем, есть ли поле date в модели
            if hasattr(ClassworkFile, 'date'):
                class_files = class_files.filter(date__gte=enrollment.enrollment_date)
                
            class_files = class_files.order_by('-id')  # Сортируем по id вместо даты, если даты нет
        except Exception as e:
            # Если что-то пошло не так, используем пустой список
            class_files = []
        
        # Получаем информацию о платежах для этого класса
        # Проверяем, есть ли модель Payment в проекте
        try:
            # Пытаемся импортировать модель Payment
            from django.apps import apps
            if apps.is_installed('payments'):
                Payment = apps.get_model('payments', 'Payment')
                payments = Payment.objects.filter(
                    student=student,
                    class_obj=class_obj
                ).order_by('-date')
            else:
                payments = []
        except (ImportError, LookupError):
            # Если модуль не найден или модель не существует, используем пустой список
            payments = []
        
        # Добавляем данные о классе в список
        classes_data.append({
            'class': class_obj,
            'next_lesson': next_lesson,
            'pending_homeworks': pending_homeworks,  # Передаем весь список, а в шаблоне ограничим
            'class_files': class_files,
            'payments': payments,
            'enrollment': enrollment
        })
    
    # Сортируем классы по ближайшему уроку
    classes_data.sort(key=lambda x: x['next_lesson']['days_until'] if x['next_lesson'] else float('inf'))
    
    context = {
        'student': student,
        'classes_data': classes_data,
        'today': today
    }
    
    return render(request, 'classes/parent_child_lessons.html', context)

@login_required
def parent_child_homework(request, student_id):
    """
    Отображает домашние задания ребенка для родителя.
    """
    # Проверяем, что пользователь является родителем
    if not request.user.is_parent:
        return HttpResponseForbidden("Эта страница доступна только родителям.")
    
    # Получаем родителя и студента
    parent = get_object_or_404(Parent, user=request.user)
    student = get_object_or_404(Student, id=student_id)
    
    # Проверяем, что студент является ребенком этого родителя
    if student.parent != parent:
        return HttpResponseForbidden("Вы не являетесь родителем этого студента.")
    
    # Получаем все активные записи студента на классы
    enrollments = Enrollment.objects.filter(student=student, is_active=True)
    
    # Текущая дата
    current_date = timezone.now().date()
    
    # Создаем список данных о классах и домашних заданиях
    classes_data = []
    
    for enrollment in enrollments:
        class_obj = enrollment.class_obj
        
        # Получаем все домашние задания для этого класса
        homeworks = Homework.objects.filter(class_obj=class_obj).order_by('-due_date')
        
        # Создаем список элементов домашних заданий
        homework_items = []
        
        for homework in homeworks:
            # Проверяем, есть ли отправленное домашнее задание
            try:
                submission = HomeworkSubmission.objects.get(homework=homework, student=student)
            except HomeworkSubmission.DoesNotExist:
                submission = None
            
            homework_items.append({
                'homework': homework,
                'submission': submission
            })
        
        # Добавляем данные о классе в список
        if homework_items:  # Добавляем только классы с домашними заданиями
            classes_data.append({
                'class': class_obj,
                'homework_items': homework_items
            })
    
    context = {
        'student': student,
        'classes_data': classes_data,
        'current_date': current_date
    }
    
    return render(request, 'classes/parent_child_homework.html', context)

@login_required
def parent_child_schedule(request, student_id):
    """
    Отображает расписание занятий ребенка для родителя.
    """
    # Проверяем, что пользователь является родителем
    if not request.user.is_parent:
        return HttpResponseForbidden("Эта страница доступна только родителям.")
    
    # Получаем родителя и студента
    parent = get_object_or_404(Parent, user=request.user)
    student = get_object_or_404(Student, id=student_id)
    
    # Проверяем, что студент является ребенком этого родителя
    if student.parent != parent:
        return HttpResponseForbidden("Вы не являетесь родителем этого студента.")
    
    # Получаем все активные записи студента на классы
    enrollments = Enrollment.objects.filter(student=student, is_active=True)
    class_ids = [enrollment.class_obj.id for enrollment in enrollments]
    
    # Получаем все расписания для этих классов
    schedules = ClassSchedule.objects.filter(class_obj_id__in=class_ids)
    
    # Получаем параметры для навигации по неделям
    week_offset = int(request.GET.get('week_offset', 0))
    
    # Получаем текущую дату
    today = timezone.now().date()
    
    # Находим начало текущей недели (понедельник)
    start_of_week = today - timedelta(days=today.weekday())
    
    # Применяем смещение недели
    start_of_week = start_of_week + timedelta(weeks=week_offset)
    
    # Создаем список дней недели
    weekdays = []
    for i in range(7):
        date = start_of_week + timedelta(days=i)
        
        # Получаем уроки на этот день
        day_schedules = schedules.filter(day_of_week=i)
        lessons = []
        
        for schedule in day_schedules:
            # Проверяем, не отменен ли урок
            is_cancelled = False
            from attendance.models import CancellationRequest
            cancellation = CancellationRequest.objects.filter(
                class_obj=schedule.class_obj,
                date=date,
                status='approved'
            ).exists()
            
            if cancellation:
                is_cancelled = True
            
            lessons.append({
                'schedule_id': schedule.id,
                'class_name': schedule.class_obj.name,
                'teacher': schedule.class_obj.teacher.full_name,
                'room': schedule.room,
                'start_time': schedule.start_time,
                'end_time': schedule.end_time,
                'is_cancelled': is_cancelled
            })
        
        # Сортируем уроки по времени начала
        lessons.sort(key=lambda x: x['start_time'])
        
        weekdays.append({
            'date': date,
            'lessons': lessons
        })
    
    context = {
        'student': student,
        'weekdays': weekdays,
        'today': today,
        'week_offset': week_offset,
        'prev_week': week_offset - 1,
        'next_week': week_offset + 1
    }
    
    return render(request, 'classes/parent_child_schedule.html', context)

@login_required
def parent_child_past_lessons(request, student_id):
    """
    Отображает прошедшие уроки ребенка для родителя.
    """
    # Проверяем, что пользователь является родителем
    if not request.user.is_parent:
        return HttpResponseForbidden("Эта страница доступна только родителям.")
    
    # Получаем родителя и студента
    parent = get_object_or_404(Parent, user=request.user)
    student = get_object_or_404(Student, id=student_id)
    
    # Проверяем, что студент является ребенком этого родителя
    if student.parent != parent:
        return HttpResponseForbidden("Вы не являетесь родителем этого студента.")
    
    # Получаем параметры фильтрации
    class_filter = request.GET.get('class_filter')
    status_filter = request.GET.get('status_filter')
    
    # Получаем текущую дату
    today = timezone.now().date()
    
    # Получаем все активные записи студента на классы
    enrollments = Enrollment.objects.filter(student=student, is_active=True)
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
def parent_child_lesson_detail(request, student_id, schedule_id):
    """
    Отображает детальную информацию о конкретном уроке ребенка для родителя.
    """
    # Проверяем, что пользователь является родителем
    if not request.user.is_parent:
        return HttpResponseForbidden("Эта страница доступна только родителям.")
    
    # Получаем родителя и студента
    parent = get_object_or_404(Parent, user=request.user)
    student = get_object_or_404(Student, id=student_id)
    
    # Проверяем, что студент является ребенком этого родителя
    if student.parent != parent:
        return HttpResponseForbidden("Вы не являетесь родителем этого студента.")
    
    # Получаем объект расписания
    schedule = get_object_or_404(ClassSchedule, id=schedule_id)
    class_obj = schedule.class_obj
    
    # Проверяем, что студент записан на этот класс
    enrollment = get_object_or_404(Enrollment, student=student, class_obj=class_obj)
    
    # Вместо рендеринга собственного шаблона, перенаправляем на существующий schedule_detail_view
    # который уже обрабатывает доступ родителей
    from django.shortcuts import redirect
    from django.urls import reverse
    
    # Перенаправляем на страницу деталей расписания
    url = reverse('core:schedule_detail', args=[schedule.id])
    return redirect(url)


@login_required
def parent_class_detail(request, class_id, student_id):
    """
    Отображает детальную информацию о классе для родителя.
    """
    # Проверяем, что пользователь является родителем
    if not request.user.is_parent:
        return HttpResponseForbidden("Эта страница доступна только родителям.")
    
    # Получаем родителя и студента
    parent = get_object_or_404(Parent, user=request.user)
    student = get_object_or_404(Student, id=student_id)
    class_obj = get_object_or_404(Class, id=class_id)
    
    # Проверяем, что студент является ребенком этого родителя
    if student.parent != parent:
        return HttpResponseForbidden("Вы не являетесь родителем этого студента.")
    
    # Проверяем, что студент записан на этот класс
    enrollment = get_object_or_404(Enrollment, student=student, class_obj=class_obj)
    
    # Получаем расписание класса
    schedules = ClassSchedule.objects.filter(class_obj=class_obj).order_by('day_of_week', 'start_time')
    
    # Получаем файлы класса, добавленные после даты зачисления студента
    try:
        class_files = ClassworkFile.objects.filter(
            class_obj=class_obj
        )
        
        # Проверяем, есть ли поле date в модели
        if hasattr(ClassworkFile, 'date'):
            class_files = class_files.filter(date__gte=enrollment.enrollment_date)
            
        class_files = class_files.order_by('-id')
    except Exception:
        class_files = []
    
    # Получаем информацию о платежах
    try:
        from django.apps import apps
        if apps.is_installed('payments'):
            Payment = apps.get_model('payments', 'Payment')
            payments = Payment.objects.filter(
                student=student,
                class_obj=class_obj
            ).order_by('-date')
        else:
            payments = []
    except (ImportError, LookupError):
        payments = []
    
    # Создаем контекст для шаблона
    context = {
        'student': student,
        'class': class_obj,
        'schedules': schedules,
        'class_files': class_files,
        'payments': payments,
        'enrollment': enrollment,
    }
    
    return render(request, 'classes/parent_class_detail.html', context)
