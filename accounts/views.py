from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, F
from django.db import IntegrityError
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.utils import timezone
from datetime import datetime, timedelta
import logging
import os
import json
from .models import User, Teacher, Student, Parent, Reception, Marketer
from .forms import TeacherForm, StudentForm, ReceptionForm, ParentForm, MarketerForm
from classes.models import Enrollment, Homework, HomeworkSubmission
from attendance.models import Attendance, ClassSchedule, Mark

def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:home')
        
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            response = redirect('core:home')
            # Установка заголовков для предотвращения кэширования
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            return response
        else:
            messages.error(request, 'Неверное имя пользователя или пароль')
    
    response = render(request, 'accounts/login.html')
    # Установка заголовков для предотвращения кэширования
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

def logout_view(request):
    logout(request)
    response = redirect('core:home')
    # Установка заголовков для предотвращения кэширования
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@login_required
def profile_view(request):
    context = {}
    
    # Если пользователь - студент, получаем его классы
    if request.user.is_student:
        from classes.models import Enrollment, Homework
        from attendance.models import Attendance, Mark
        from classes.models import HomeworkSubmission
        from django.db.models import Count, Q
        
        student = request.user.student_profile
        student_classes = Enrollment.objects.filter(student=student).select_related('class_obj', 'class_obj__teacher')
        context['student_classes'] = student_classes
        
        # Проверяем, является ли студент самоуправляемым
        # Если студент не самоуправляемый (имеет привязанного родителя), то скрываем финансовую информацию
        context['show_financial_info'] = student.is_self_managed
        
        # Статистика посещаемости
        total_attendances = Attendance.objects.filter(student=student).count()
        present_attendances = Attendance.objects.filter(student=student, status='present').count()
        
        attendance_stats = {
            'total_count': total_attendances,
            'present_count': present_attendances,
            'attendance_rate': round((present_attendances / total_attendances) * 100) if total_attendances > 0 else 0
        }
        context['attendance_stats'] = attendance_stats
        
        # Статистика домашних заданий
        # Получаем все домашние задания для классов студента
        class_ids = student_classes.values_list('class_obj_id', flat=True)
        total_homeworks = Homework.objects.filter(class_obj_id__in=class_ids).count()
        completed_homeworks = HomeworkSubmission.objects.filter(student=student).count()
        
        homework_stats = {
            'total': total_homeworks,
            'completed': completed_homeworks,
            'completion_rate': round((completed_homeworks / total_homeworks) * 100) if total_homeworks > 0 else 0
        }
        context['homework_stats'] = homework_stats
        
        # Проверяем, есть ли у студента зарегистрированный родитель
        if student.parent:
            # Для студентов с зарегистрированным родителем показываем более подробную информацию
            context['has_parent'] = True
            
            # Получаем посещаемость
            attendances = Attendance.objects.filter(student=student).select_related('class_schedule', 'class_schedule__class_obj')
            
            # Получаем домашние задания и их оценки
            homework_submissions = HomeworkSubmission.objects.filter(student=student).select_related('homework', 'homework__class_obj')
            
            # Получаем оценки за активность
            activity_marks = Mark.objects.filter(student=student).select_related('class_obj')
            
            # Группируем посещаемость по классам
            attendance_by_class = {}
            for attendance in attendances:
                class_id = str(attendance.class_schedule.class_obj.id)  # Преобразуем ID в строку
                if class_id not in attendance_by_class:
                    attendance_by_class[class_id] = []
                attendance_by_class[class_id].append(attendance)
            
            # Группируем домашние задания по классам
            homework_by_class = {}
            for submission in homework_submissions:
                class_id = str(submission.homework.class_obj.id)  # Преобразуем ID в строку
                if class_id not in homework_by_class:
                    homework_by_class[class_id] = []
                homework_by_class[class_id].append(submission)
            
            # Группируем оценки по классам
            marks_by_class = {}
            for mark in activity_marks:
                class_id = str(mark.class_obj.id)  # Преобразуем ID в строку
                if class_id not in marks_by_class:
                    marks_by_class[class_id] = []
                marks_by_class[class_id].append(mark)
            
            context['attendance_by_class'] = attendance_by_class
            context['homework_by_class'] = homework_by_class
            context['marks_by_class'] = marks_by_class
            context['student'] = student
        else:
            context['has_parent'] = False
    
    # Если пользователь - учитель, получаем его классы
    elif request.user.is_teacher:
        from classes.models import Class
        teacher = request.user.teacher_profile
        teacher_classes = Class.objects.filter(teacher=teacher)
        context['teacher_classes'] = teacher_classes
    
    return render(request, 'accounts/profile.html', context)

@login_required
def edit_profile(request):
    """Редактирование профиля пользователя"""
    # Проверяем, что пользователь является администратором
    if not request.user.is_admin:
        messages.error(request, 'У вас нет доступа к редактированию профиля.')
        return redirect('accounts:profile')
        
    user = request.user
    
    # Определяем тип пользователя и соответствующий профиль
    profile = None
    if user.is_student:
        profile = user.student_profile
    elif user.is_teacher:
        profile = user.teacher_profile
    elif user.is_parent:
        profile = user.parent_profile
    elif user.is_reception:
        profile = user.reception_profile
    
    if request.method == 'POST':
        # Обрабатываем данные формы
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number')
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Обновляем email
        if email and email != user.email:
            user.email = email
        
        # Обновляем номер телефона
        if phone_number and profile and hasattr(profile, 'phone_number'):
            profile.phone_number = phone_number
            profile.save()
        
        # Меняем пароль, если указаны все необходимые поля
        if current_password and new_password and confirm_password:
            # Проверяем текущий пароль
            if user.check_password(current_password):
                # Проверяем, что новые пароли совпадают
                if new_password == confirm_password:
                    user.set_password(new_password)
                    messages.success(request, 'Пароль успешно изменен')
                else:
                    messages.error(request, 'Новые пароли не совпадают')
                    return render(request, 'accounts/edit_profile.html', {'user': user, 'profile': profile})
            else:
                messages.error(request, 'Неверный текущий пароль')
                return render(request, 'accounts/edit_profile.html', {'user': user, 'profile': profile})
        
        # Сохраняем изменения
        user.save()
        
        messages.success(request, 'Профиль успешно обновлен')
        return redirect('accounts:profile')
    
    return render(request, 'accounts/edit_profile.html', {'user': user, 'profile': profile})

@login_required
def teacher_list(request):
    if not request.user.is_admin:
        return redirect('core:home')
    
    teachers = Teacher.objects.all()
    return render(request, 'accounts/teacher_list.html', {'teachers': teachers})

@login_required
def add_teacher(request):
    if not request.user.is_admin:
        return redirect('core:home')
    
    if request.method == 'POST':
        form = TeacherForm(request.POST)
        if form.is_valid():
            teacher = form.save()
            messages.success(request, f'Преподаватель {teacher.full_name} успешно добавлен')
            return redirect('accounts:teacher_list')
    else:
        form = TeacherForm()
    
    return render(request, 'accounts/teacher_form.html', {'form': form, 'title': 'Добавление преподавателя'})

@login_required
def edit_teacher(request, pk):
    if not request.user.is_admin:
        return redirect('core:home')
    
    teacher = get_object_or_404(Teacher, pk=pk)
    
    if request.method == 'POST':
        # Для редактирования не включаем поля пользователя
        form = TeacherForm(request.POST, instance=teacher, initial={
            'username': teacher.user.username,
            'email': teacher.user.email
        })
        
        if form.is_valid():
            # Обновляем только поля преподавателя
            teacher = form.save(commit=False)
            teacher.save()
            
            # Обновляем поля пользователя отдельно
            user = teacher.user
            if user.username != form.cleaned_data['username']:
                user.username = form.cleaned_data['username']
            user.email = form.cleaned_data.get('email', '')
            
            # Обновляем пароль только если он был предоставлен
            if form.cleaned_data.get('password'):
                user.set_password(form.cleaned_data['password'])
            
            user.save()
            
            messages.success(request, f'Данные преподавателя {teacher.full_name} успешно обновлены')
            return redirect('accounts:teacher_list')
    else:
        form = TeacherForm(instance=teacher, initial={
            'username': teacher.user.username,
            'email': teacher.user.email
        })
    
    return render(request, 'accounts/teacher_form.html', {'form': form, 'title': 'Редактирование преподавателя'})

@login_required
def delete_teacher(request, pk):
    """Удаляет преподавателя."""
    # Проверка доступа
    if not request.user.is_admin:
        return HttpResponseForbidden("Только администраторы могут удалять преподавателей.")
    
    teacher = get_object_or_404(Teacher, pk=pk)
    user = teacher.user
    
    if request.method == 'POST':
        # Удаляем пользователя, что также удалит связанного преподавателя
        user.delete()
        messages.success(request, "Преподаватель успешно удален.")
        return redirect('accounts:teacher_list')
    
    return render(request, 'accounts/confirm_delete.html', {
        'object': teacher,
        'title': 'Удаление преподавателя',
        'message': f'Вы уверены, что хотите удалить преподавателя {teacher.full_name}?',
        'cancel_url': 'accounts:teacher_list'
    })

@login_required
def student_list(request):
    """Отображает список студентов."""
    # Проверка доступа
    if not (request.user.is_admin or request.user.is_reception or request.user.is_teacher):
        return HttpResponseForbidden("У вас нет доступа к списку студентов.")
    
    students = Student.objects.all()
    return render(request, 'accounts/student_list.html', {'students': students})

@login_required
def add_student(request):
    """Добавляет нового студента."""
    # Проверка доступа
    if not request.user.is_admin:
        return HttpResponseForbidden("Только администраторы могут добавлять студентов.")
    
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # Проверяем, существует ли пользователь с таким логином
                username = form.cleaned_data.get('username')
                if User.objects.filter(username=username).exists():
                    messages.error(request, "Пользователь с таким логином уже существует.")
                    return render(request, 'accounts/student_form.html', {
                        'form': form,
                        'title': 'Добавление студента',
                        'submit_text': 'Добавить студента'
                    })
                
                student = form.save()
                logger = logging.getLogger(__name__)
                logger.info(f"Добавлен студент: {student.full_name}, фото: {student.face_image}")
                messages.success(request, f"Студент {student.full_name} успешно добавлен.")
                return redirect('accounts:student_list')
            except IntegrityError:
                # Обрабатываем ошибку уникальности имени пользователя
                messages.error(request, "Пользователь с таким логином уже существует.")
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Ошибка при добавлении студента: {str(e)}")
                messages.error(request, "Произошла ошибка при добавлении студента.")
        else:
            # Выводим ошибки валидации в консоль для отладки
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибки валидации формы: {form.errors}")
            # Добавляем сообщение об ошибке
            messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
    else:
        form = StudentForm()
    
    return render(request, 'accounts/student_form.html', {
        'form': form,
        'title': 'Добавление студента',
        'submit_text': 'Добавить студента'
    })

import base64
from io import BytesIO
import logging

# Импортируем функцию для регистрации лица
from face_recognition_app.facenet_utils import register_face

logger = logging.getLogger(__name__)

@login_required
def edit_student(request, pk):
    """Редактирует студента."""
    # Проверка доступа
    if not request.user.is_admin:
        return HttpResponseForbidden("Только администраторы могут редактировать студентов.")
    
    student = get_object_or_404(Student, pk=pk)
    user = student.user
    
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            # Обновляем данные пользователя
            if user.username != form.cleaned_data['username']:
                # Проверяем, что имя пользователя уникально, исключая текущего пользователя
                if User.objects.filter(username=form.cleaned_data['username']).exclude(id=user.id).exists():
                    form.add_error('username', 'Пользователь с таким именем уже существует')
                    return render(request, 'accounts/student_form.html', {
                        'form': form,
                        'title': 'Редактирование студента',
                        'submit_text': 'Сохранить изменения'
                    })
                user.username = form.cleaned_data['username']
            if form.cleaned_data['password']:
                user.set_password(form.cleaned_data['password'])
            user.email = form.cleaned_data.get('email', '')
            user.save()
            
            # Сохраняем данные студента без создания нового пользователя
            student = form.save(commit=False)
            student.user = user  # Используем существующего пользователя
            
            # Если нужно создать нового родителя
            if form.cleaned_data.get('create_parent'):
                # Проверяем, что имя пользователя для родителя уникально
                if User.objects.filter(username=form.cleaned_data['parent_username']).exists():
                    form.add_error('parent_username', 'Пользователь с таким именем уже существует')
                    return render(request, 'accounts/student_form.html', {
                        'form': form,
                        'title': 'Редактирование студента',
                        'submit_text': 'Сохранить изменения'
                    })
                
                try:
                    # Создаем пользователя для родителя
                    parent_user = User.objects.create_user(
                        username=form.cleaned_data['parent_username'],
                        password=form.cleaned_data['parent_password'],
                        email=form.cleaned_data.get('parent_email', ''),
                        user_type='parent'
                    )
                except Exception as e:
                    # Если возникла ошибка при создании пользователя
                    form.add_error('parent_username', f'Ошибка при создании пользователя: {str(e)}')
                    return render(request, 'accounts/student_form.html', {
                        'form': form,
                        'title': 'Редактирование студента',
                        'submit_text': 'Сохранить изменения'
                    })
                
                # Создаем родителя
                parent = Parent(
                    user=parent_user,
                    full_name=form.cleaned_data['parent_full_name'],
                    phone_number=form.cleaned_data['parent_phone_number']
                )
                parent.save()
                
                # Привязываем родителя к студенту
                student.parent = parent
            
            try:
                student.save()
                logger = logging.getLogger(__name__)
                logger.info(f"Изменен студент: {student.full_name}, фото: {student.face_image}")
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Ошибка при сохранении изменений студента: {str(e)}")
                messages.error(request, f"Ошибка при сохранении изменений: {str(e)}")
                return redirect('accounts:student_list')
            
            # Обрабатываем фотографию для FaceID, если она была загружена
            face_image = request.FILES.get('face_image')
            if face_image:
                try:
                    # Проверяем размер и тип файла
                    if face_image.size > 10 * 1024 * 1024:  # 10 МБ
                        messages.error(request, "Файл слишком большой. Максимальный размер - 10 МБ")
                        return redirect('accounts:student_list')
                    
                    # Проверяем тип файла
                    content_type = face_image.content_type.lower()
                    if not content_type.startswith('image/'):
                        messages.error(request, "Загруженный файл не является изображением")
                        return redirect('accounts:student_list')
                    
                    # Импортируем необходимые модули
                    import io
                    import base64
                    from PIL import Image
                    from django.core.files.base import ContentFile
                    from face_recognition_app.facenet_utils import register_face
                    
                    # Открываем изображение напрямую из загруженного файла
                    img = Image.open(face_image)
                    
                    # Преобразуем в RGB, если необходимо
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Уменьшаем размер изображения, если оно слишком большое
                    if max(img.size) > 1000:
                        img.thumbnail((1000, 1000), Image.LANCZOS)
                    
                    # Сохраняем в буфер в формате JPEG с высоким качеством
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG', quality=95)
                    buffer.seek(0)
                    
                    # Конвертируем в base64 для FaceNet
                    base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    base64_image_with_prefix = f"data:image/jpeg;base64,{base64_image}"
                    
                    # Регистрируем лицо пользователя с помощью FaceNet
                    success, message = register_face(user, base64_image_with_prefix)
                    
                    if success:
                        # Сохраняем фотографию в профиле студента
                        student.face_image.save(f"faceid_{user.id}.jpg", ContentFile(buffer.getvalue()), save=True)
                        messages.success(request, "Фотография для FaceID успешно загружена и обработана.")
                    else:
                        messages.error(request, f"Ошибка при обработке фотографии для FaceID: {message}")
                        
                except Exception as e:
                    logger.error(f"Ошибка при обработке фотографии для FaceID: {e}")
                    messages.error(request, f"Произошла ошибка при обработке фотографии: {str(e)}")
            
            messages.success(request, f"Данные студента {student.full_name} успешно обновлены.")
            return redirect('accounts:student_list')
    else:
        form = StudentForm(instance=student, initial={
            'username': user.username,
            'email': user.email,
            'password': ''  # Пустое поле для пароля
        })
    
    return render(request, 'accounts/student_form.html', {
        'form': form,
        'title': 'Редактирование студента',
        'submit_text': 'Сохранить изменения'
    })

@login_required
def delete_student(request, pk):
    """Удаляет студента."""
    # Проверка доступа
    if not request.user.is_admin:
        return HttpResponseForbidden("Только администраторы могут удалять студентов.")
    
    student = get_object_or_404(Student, pk=pk)
    user = student.user
    
    if request.method == 'POST':
        # Удаляем пользователя, что также удалит связанного студента
        user.delete()
        messages.success(request, "Студент успешно удален.")
        return redirect('accounts:student_list')
    
    return render(request, 'accounts/confirm_delete.html', {
        'object': student,
        'title': 'Удаление студента',
        'message': f'Вы уверены, что хотите удалить студента {student.full_name}?',
        'cancel_url': 'accounts:student_list'
    })

@login_required
def parent_list(request):
    """Отображает список родителей."""
    # Проверка доступа
    if not (request.user.is_admin or request.user.is_reception):
        return HttpResponseForbidden("У вас нет доступа к списку родителей.")
    
    parents = Parent.objects.all()
    return render(request, 'accounts/parent_list.html', {'parents': parents})

@login_required
def add_parent(request):
    """Добавляет нового родителя."""
    # Проверка доступа
    if not request.user.is_admin:
        return HttpResponseForbidden("Только администраторы могут добавлять родителей.")
    
    if request.method == 'POST':
        form = ParentForm(request.POST)
        if form.is_valid():
            parent = form.save()
            messages.success(request, f'Родитель {parent.full_name} успешно добавлен!')
            return redirect('accounts:parent_list')
    else:
        form = ParentForm()
    
    return render(request, 'accounts/parent_form.html', {
        'form': form,
        'title': 'Добавление родителя',
        'submit_text': 'Добавить родителя'
    })

@login_required
def parent_detail(request, pk):
    """Отображает детальную информацию о родителе."""
    # Получаем родителя или возвращаем 404, если не найден
    parent = get_object_or_404(Parent, pk=pk)
    
    # Проверка доступа
    if not (request.user.is_admin or request.user.is_reception or 
            (request.user.is_parent and request.user.get_parent_profile() and request.user.get_parent_profile().id == pk)):
        return HttpResponseForbidden("У вас нет доступа к этой странице.")
    
    # Получаем детей родителя
    children = parent.children.all()
    
    # Получаем классы детей
    classes = []
    for child in children:
        child_classes = child.enrollments.all()
        for enrollment in child_classes:
            if enrollment.class_obj not in classes:
                classes.append(enrollment.class_obj)
    
    context = {
        'parent': parent,
        'children': children,
        'classes': classes
    }
    
    return render(request, 'accounts/parent_detail.html', context)

@login_required
def parent_children(request):
    """Отображает список детей для родителя."""
    # Проверка доступа
    if not request.user.is_parent:
        return HttpResponseForbidden("У вас нет доступа к этой странице.")
    
    parent = request.user.get_parent_profile()
    if not parent:
        return HttpResponseForbidden("У вас нет доступа к этой странице.")
    children = parent.children.all()
    
    # Получаем предстоящие занятия для каждого ребенка
    from datetime import datetime, timedelta
    from django.utils import timezone
    from classes.models import ClassSchedule
    from attendance.models import Attendance, StudentCancellationRequest
    
    # Получаем текущую дату и время
    now = timezone.now()
    today = now.date()
    
    # Создаем список для хранения данных о детях и их предстоящих занятиях
    children_with_lessons = []
    
    for child in children:
        # Получаем все классы, на которые записан ребенок
        enrollments = child.enrollments.all()
        
        # Список предстоящих занятий для этого ребенка
        upcoming_lessons = []
        
        for enrollment in enrollments:
            class_obj = enrollment.class_obj
            schedules = ClassSchedule.objects.filter(class_obj=class_obj)
            
            # Получаем предстоящие занятия для этого класса
            for schedule in schedules:
                # Получаем следующие 14 дней
                for i in range(14):
                    check_date = today + timedelta(days=i)
                    # Проверяем, совпадает ли день недели
                    if check_date.weekday() == schedule.day_of_week:
                        # Проверяем, не отменено ли уже это занятие
                        attendance_exists = Attendance.objects.filter(
                            student=child,
                            class_obj=class_obj,
                            date=check_date,
                            is_canceled=True
                        ).exists()
                        
                        # Проверяем, не создан ли уже запрос на отмену
                        cancellation_request_exists = StudentCancellationRequest.objects.filter(
                            student=child,
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
        
        # Добавляем информацию о ребенке и его предстоящих занятиях в список
        children_with_lessons.append({
            'child': child,
            'upcoming_lessons': upcoming_lessons
        })
    
    return render(request, 'accounts/parent_children.html', {
        'children': children,
        'children_with_lessons': children_with_lessons
    })

@login_required
def parent_cancellation_requests(request):
    """Отображает список запросов на отмену занятий для родителя."""
    if not request.user.is_parent:
        return HttpResponseForbidden("Доступ запрещен. Вы не являетесь родителем.")
    
    try:
        parent = Parent.objects.get(user=request.user)
    except Parent.DoesNotExist:
        messages.error(request, "Профиль родителя не найден.")
        return redirect('home')
    
    # Получаем всех детей родителя
    children = Student.objects.filter(parent=parent)
    
    # Получаем запросы на отмену занятий для всех детей родителя
    from attendance.models import StudentCancellationRequest
    cancellation_requests = StudentCancellationRequest.objects.filter(student__in=children).order_by('-created_at')
    
    # Фильтры по статусу
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        cancellation_requests = cancellation_requests.filter(status=status_filter)
    
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
    
    # Фильтр по ребенку
    child_id = request.GET.get('child_id')
    if child_id:
        cancellation_requests = cancellation_requests.filter(student_id=child_id)
    
    # Статистика
    pending_count = StudentCancellationRequest.objects.filter(student__in=children, status='pending').count()
    approved_count = StudentCancellationRequest.objects.filter(student__in=children, status='approved').count()
    rejected_count = StudentCancellationRequest.objects.filter(student__in=children, status='rejected').count()
    
    context = {
        'cancellation_requests': cancellation_requests,
        'children': children,
        'status_filter': status_filter,
        'start_date': start_date,
        'end_date': end_date,
        'child_id': child_id,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count
    }
    
    return render(request, 'accounts/parent_cancellation_requests.html', context)


@login_required
def parent_dashboard(request):
    """Перенаправляет родителя на главную страницу, где теперь отображается панель управления."""
    if not request.user.is_parent:
        return HttpResponseForbidden("Доступ запрещен. Вы не являетесь родителем.")
    
    # Перенаправляем на главную страницу, где теперь отображается панель управления
    return redirect('core:home')

@login_required
def child_detail(request, student_id):
    """Отображает детальную информацию о ребенке для родителя."""
    if not request.user.is_parent:
        return HttpResponseForbidden("Доступ запрещен. Вы не являетесь родителем.")
    
    try:
        parent = Parent.objects.get(user=request.user)
    except Parent.DoesNotExist:
        messages.error(request, "Профиль родителя не найден.")
        return redirect('home')
    
    # Проверяем, является ли студент ребенком этого родителя
    student = get_object_or_404(Student, id=student_id, parent=parent)
    
    # Получаем классы, в которых учится ребенок
    enrollments = Enrollment.objects.filter(student=student).select_related('class_obj', 'class_obj__teacher')
    
    # Получаем посещаемость
    attendances = Attendance.objects.filter(student=student).select_related('class_schedule', 'class_schedule__class_obj')
    
    # Получаем домашние задания и их оценки
    homework_submissions = HomeworkSubmission.objects.filter(student=student).select_related('homework', 'homework__class_obj')
    
    # Получаем оценки за активность
    activity_marks = Mark.objects.filter(student=student).select_related('class_obj')
    
    # Группируем посещаемость по классам
    attendance_by_class = {}
    for attendance in attendances:
        class_id = attendance.class_schedule.class_obj.id
        if class_id not in attendance_by_class:
            attendance_by_class[class_id] = []
        attendance_by_class[class_id].append(attendance)
    
    # Группируем домашние задания по классам
    homework_by_class = {}
    for submission in homework_submissions:
        class_id = submission.homework.class_obj.id
        if class_id not in homework_by_class:
            homework_by_class[class_id] = []
        homework_by_class[class_id].append(submission)
    
    # Группируем оценки по классам
    marks_by_class = {}
    for mark in activity_marks:
        class_id = mark.class_obj.id
        if class_id not in marks_by_class:
            marks_by_class[class_id] = []
        marks_by_class[class_id].append(mark)
    
    return render(request, 'accounts/child_detail.html', {
        'student': student,
        'enrollments': enrollments,
        'attendance_by_class': attendance_by_class,
        'homework_by_class': homework_by_class,
        'marks_by_class': marks_by_class,
        'balance': student.balance
    })

@login_required
def reception_list(request):
    if not request.user.is_admin:
        return redirect('core:home')
    
    receptions = Reception.objects.all()
    return render(request, 'accounts/reception_list.html', {'receptions': receptions})

@login_required
def add_reception(request):
    if not request.user.is_admin:
        return redirect('core:home')
    
    if request.method == 'POST':
        form = ReceptionForm(request.POST)
        if form.is_valid():
            reception = form.save()
            messages.success(request, f'Ресепшенист {reception.full_name} успешно добавлен')
            return redirect('accounts:reception_list')
    else:
        form = ReceptionForm()
    
    return render(request, 'accounts/add_reception.html', {'form': form})

@login_required
def edit_reception(request, pk):
    if not request.user.is_admin:
        return redirect('core:home')
    
    reception = get_object_or_404(Reception, pk=pk)
    
    if request.method == 'POST':
        form = ReceptionForm(request.POST, instance=reception)
        if form.is_valid():
            # Обновляем данные пользователя
            user = reception.user
            if user.username != form.cleaned_data['username']:
                user.username = form.cleaned_data['username']
            if form.cleaned_data['password']:  # Если пароль был изменен
                user.set_password(form.cleaned_data['password'])
            user.email = form.cleaned_data.get('email', '')
            user.save()
            
            # Сохраняем данные ресепшениста
            reception = form.save(commit=False)
            reception.user = user
            reception.save()
            
            messages.success(request, f'Данные ресепшениста {reception.full_name} успешно обновлены')
            return redirect('accounts:reception_list')
    else:
        initial_data = {
            'username': reception.user.username,
            'password': '',  # Пустой пароль, чтобы не показывать текущий
            'email': reception.user.email,
        }
        form = ReceptionForm(instance=reception, initial=initial_data)
    
    return render(request, 'accounts/edit_reception.html', {
        'form': form,
        'reception': reception
    })

@login_required
def delete_reception(request, pk):
    if not request.user.is_admin:
        return redirect('core:home')
    
    reception = get_object_or_404(Reception, pk=pk)
    
    if request.method == 'POST':
        user = reception.user
        reception_name = reception.full_name
        
        # Удаляем ресепшениста и связанного пользователя
        reception.delete()
        user.delete()
        
        messages.success(request, f'Ресепшенист {reception_name} успешно удален')
        return redirect('accounts:reception_list')
    
    return render(request, 'accounts/delete_reception.html', {'reception': reception})

@login_required
def marketer_list(request):
    """Отображает список маркетологов."""
    if not request.user.is_admin:
        return HttpResponseForbidden("У вас нет прав для просмотра этой страницы.")
        
    marketers = Marketer.objects.all().order_by('full_name')
    return render(request, 'accounts/marketer_list.html', {'marketers': marketers})

@login_required
def add_marketer(request):
    """Добавляет нового маркетолога."""
    if not request.user.is_admin:
        return HttpResponseForbidden("У вас нет прав для просмотра этой страницы.")
        
    if request.method == 'POST':
        form = MarketerForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                marketer = form.save()
                messages.success(request, 'Маркетолог успешно добавлен.')
                return redirect('accounts:marketer_list')
            except Exception as e:
                messages.error(request, f'Ошибка при создании маркетолога: {str(e)}')
    else:
        form = MarketerForm()
    
    return render(request, 'accounts/add_marketer.html', {'form': form})

@login_required
def edit_marketer(request, pk):
    """Редактирует маркетолога."""
    if not request.user.is_admin:
        return HttpResponseForbidden("У вас нет прав для просмотра этой страницы.")
        
    marketer = get_object_or_404(Marketer, pk=pk)
    user = marketer.user
    
    if request.method == 'POST':
        # Обновляем данные пользователя
        username = request.POST.get('username')
        email = request.POST.get('email', '')
        password = request.POST.get('password')
        
        # Проверяем, не занято ли имя пользователя
        if username != user.username and User.objects.filter(username=username).exists():
            messages.error(request, 'Это имя пользователя уже занято.')
            form = MarketerForm(instance=marketer)
            return render(request, 'accounts/edit_marketer.html', {'form': form, 'marketer': marketer})
        
        user.username = username
        user.email = email
        if password:  # Если пароль был предоставлен, обновляем его
            user.set_password(password)
        user.save()
        
        # Обновляем данные маркетолога
        form = MarketerForm(request.POST, request.FILES, instance=marketer)
        if form.is_valid():
            try:
                form.save(commit=False)  # Не сохраняем пока, чтобы избежать создания нового пользователя
                marketer.user = user  # Устанавливаем существующего пользователя
                marketer.save()
                
                # Сохраняем обновленные данные
                marketer.save()
                    
                messages.success(request, 'Данные маркетолога успешно обновлены.')
                
                # Если пароль был изменен, обновляем сессию аутентификации
                if password and request.user.id == user.id:
                    update_session_auth_hash(request, user)
                    
                return redirect('accounts:marketer_list')
            except Exception as e:
                messages.error(request, f'Ошибка при обновлении данных: {str(e)}')
    else:
        form = MarketerForm(instance=marketer, initial={
            'username': user.username,
            'email': user.email,
        })
    
    context = {
        'form': form,
        'marketer': marketer
    }
    return render(request, 'accounts/edit_marketer.html', context)

@login_required
def delete_marketer(request, pk):
    """Удаляет маркетолога."""
    if not request.user.is_admin:
        return HttpResponseForbidden("У вас нет прав для просмотра этой страницы.")
        
    marketer = get_object_or_404(Marketer, pk=pk)
    
    if request.method == 'POST':
        user = marketer.user
        # Удаляем пользователя (каскадно удалится и профиль маркетолога)
        try:
            user.delete()
            messages.success(request, 'Маркетолог успешно удален.')
            return redirect('accounts:marketer_list')
        except Exception as e:
            messages.error(request, f'Ошибка при удалении: {str(e)}')
            return redirect('accounts:marketer_list')
    
    context = {
        'marketer': marketer
    }
    return render(request, 'accounts/delete_marketer.html', context)

@login_required
def performance_stats(request):
    """Отображает подробную статистику успеваемости для студента."""
    if not request.user.is_student:
        return redirect('accounts:profile')
    
    try:
        student = request.user.student_profile
    except Exception as e:
        logger.error(f"Ошибка при получении профиля студента: {e}")
        messages.error(request, "Не удалось загрузить профиль студента. Пожалуйста, обратитесь к администратору.")
        return redirect('accounts:profile')
        
    student_classes = Enrollment.objects.filter(student=student).select_related('class_obj')
    
    # Получаем данные о посещаемости
    try:
        attendances = Attendance.objects.filter(student=student)
        total_attendances = attendances.count()
        present_attendances = attendances.filter(status='present').count()
        
        attendance_stats = {
            'total_count': total_attendances,
            'present_count': present_attendances,
            'attendance_rate': round((present_attendances / total_attendances) * 100) if total_attendances > 0 else 0
        }
    except Exception as e:
        logger.error(f"Ошибка при получении данных о посещаемости: {e}")
        attendance_stats = {
            'total_count': 0,
            'present_count': 0,
            'attendance_rate': 0
        }
    
    # Получаем данные о домашних заданиях
    try:
        class_ids = student_classes.values_list('class_obj_id', flat=True)
        total_homeworks = Homework.objects.filter(class_obj_id__in=class_ids).count()
        homework_submissions = HomeworkSubmission.objects.filter(student=student)
        completed_homeworks = homework_submissions.count()
        
        homework_stats = {
            'total': total_homeworks,
            'completed': completed_homeworks,
            'completion_rate': round((completed_homeworks / total_homeworks) * 100) if total_homeworks > 0 else 0
        }
    except Exception as e:
        logger.error(f"Ошибка при получении данных о домашних заданиях: {e}")
        homework_submissions = []
        homework_stats = {
            'total': 0,
            'completed': 0,
            'completion_rate': 0
        }
    
    # Получаем средний балл студента
    try:
        marks = Mark.objects.filter(student=student)
        homework_grades = homework_submissions.exclude(grade__isnull=True)
        
        avg_mark = marks.aggregate(avg=Avg('value'))['avg'] or 0
        avg_homework_grade = homework_grades.aggregate(avg=Avg('grade'))['avg'] or 0
        
        # Вычисляем общий средний балл (оценки за активность и домашние задания)
        total_marks_count = marks.count() + homework_grades.count()
        if total_marks_count > 0:
            average_grade = round((avg_mark * marks.count() + avg_homework_grade * homework_grades.count()) / total_marks_count, 1)
        else:
            average_grade = 0
    except Exception as e:
        logger.error(f"Ошибка при получении данных об оценках: {e}")
        marks = []
        homework_grades = []
        avg_mark = 0
        avg_homework_grade = 0
        average_grade = 0
    
    # Получаем рейтинг студента среди всех студентов
    try:
        all_students = Student.objects.all()
        student_rank = 1  # По умолчанию первое место
        total_students = all_students.count()
    except Exception as e:
        logger.error(f"Ошибка при получении данных о рейтинге студента: {e}")
        student_rank = 1
        total_students = 1
    
    # Данные по предметам
    subjects_data = []
    try:
        for enrollment in student_classes:
            try:
                class_obj = enrollment.class_obj
                class_marks = marks.filter(class_obj=class_obj)
                class_homework = homework_submissions.filter(homework__class_obj=class_obj)
                
                avg_class_mark = class_marks.aggregate(avg=Avg('value'))['avg'] or 0
                avg_class_homework = class_homework.exclude(grade__isnull=True).aggregate(avg=Avg('grade'))['avg'] or 0
                
                total_class_marks = class_marks.count() + class_homework.exclude(grade__isnull=True).count()
                if total_class_marks > 0:
                    class_avg = round((avg_class_mark * class_marks.count() + avg_class_homework * class_homework.exclude(grade__isnull=True).count()) / total_class_marks, 1)
                else:
                    class_avg = 0
                
                subjects_data.append({
                    'name': class_obj.name,
                    'average_grade': class_avg,
                    'performance_percent': min(int(class_avg * 20), 100)  # Преобразуем оценку в процент (5 = 100%)
                })
            except Exception as e:
                logger.error(f"Ошибка при обработке данных для класса {enrollment.class_obj_id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при получении данных о предметах: {e}")
    
    # Сортируем предметы по среднему баллу (по убыванию)
    subjects_data.sort(key=lambda x: x['average_grade'], reverse=True)
    
    # Добавляем демо-данные для графиков
    # Данные по месяцам для графиков
    months = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май']
    
    # Данные для графика динамики оценок
    grades_data = {
        'labels': months,
        'datasets': [{
            'label': 'Средний балл',
            'data': [4.2, 4.5, 4.3, 4.7, 4.8],
        }]
    }
    
    # Данные для графика распределения оценок
    grade_distribution = {
        'labels': ['Отлично (5)', 'Хорошо (4)', 'Удовлетворительно (3)', 'Неудовлетворительно (2)'],
        'data': [65, 25, 8, 2]
    }
    
    # Данные для радарного графика по предметам
    subjects_chart_data = {
        'labels': [subj['name'] for subj in subjects_data[:5]] if subjects_data else ['Математика', 'Физика', 'Английский', 'История', 'Литература'],
        'data': [subj['performance_percent'] for subj in subjects_data[:5]] if subjects_data else [95, 92, 85, 78, 88]
    }
    
    # Данные для графика посещаемости по месяцам
    attendance_chart_data = {
        'labels': months,
        'data': [80, 85, 90, 88, 92]
    }
    
    # Данные для графика выполнения домашних заданий
    homework_completion_data = {
        'labels': [subj['name'] for subj in subjects_data[:5]] if subjects_data else ['Математика', 'Физика', 'Английский', 'История', 'Литература'],
        'on_time': [18, 16, 15, 14, 17],
        'late': [2, 3, 3, 4, 2],
        'not_completed': [0, 1, 2, 2, 1]
    }
    
    # Данные для графика оценок за домашние задания
    homework_grades_data = {
        'labels': [subj['name'] for subj in subjects_data[:5]] if subjects_data else ['Математика', 'Физика', 'Английский', 'История', 'Литература'],
        'data': [4.8, 4.7, 4.2, 3.9, 4.5]
    }
    
    # Преобразуем данные в JSON для безопасного использования в JavaScript
    try:
        grades_data_json = json.dumps(grades_data)
        grade_distribution_json = json.dumps(grade_distribution)
        subjects_chart_data_json = json.dumps(subjects_chart_data)
        attendance_chart_data_json = json.dumps(attendance_chart_data)
        homework_completion_data_json = json.dumps(homework_completion_data)
        homework_grades_data_json = json.dumps(homework_grades_data)
        
        # Отладочный вывод
        logger.debug(f"JSON data prepared successfully")
    except Exception as e:
        logger.error(f"Ошибка при преобразовании данных в JSON: {e}")
        # Устанавливаем значения по умолчанию
        grades_data_json = '{}'
        grade_distribution_json = '{}'
        subjects_chart_data_json = '{}'
        attendance_chart_data_json = '{}'
        homework_completion_data_json = '{}'
        homework_grades_data_json = '{}'
    
    context = {
        'student': student,
        'student_classes': student_classes,
        'attendance_stats': attendance_stats,
        'homework_stats': homework_stats,
        'average_grade': average_grade,
        'student_rank': student_rank,
        'total_students': total_students,
        'subjects_data': subjects_data,
        # Добавляем данные для графиков в формате JSON
        'grades_data_json': grades_data_json,
        'grade_distribution_json': grade_distribution_json,
        'subjects_chart_data_json': subjects_chart_data_json,
        'attendance_chart_data_json': attendance_chart_data_json,
        'homework_completion_data_json': homework_completion_data_json,
        'homework_grades_data_json': homework_grades_data_json,
        # Добавляем данные для таблиц
        'activity_mark': True,
        'class_obj': True,
        'class_obj_id': True,
        'date': True,
        'homework_mark': True,
        'id': True,
        'student': True,
        'student_id': True,
        'substitute_teacher': True,
        'substitute_teacher_id': True,
        'teacher_comment': True
    }
    
    return render(request, 'accounts/performance_stats.html', context)
