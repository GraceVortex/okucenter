from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse
from .models import User, Teacher, Student, Parent, Reception
from .forms import TeacherForm, StudentForm, ReceptionForm
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
    return render(request, 'accounts/profile.html')

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
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save()
            messages.success(request, f"Студент {student.full_name} успешно добавлен.")
            return redirect('accounts:student_list')
    else:
        form = StudentForm()
    
    return render(request, 'accounts/student_form.html', {
        'form': form,
        'title': 'Добавление студента',
        'submit_text': 'Добавить студента'
    })

@login_required
def edit_student(request, pk):
    """Редактирует студента."""
    # Проверка доступа
    if not request.user.is_admin:
        return HttpResponseForbidden("Только администраторы могут редактировать студентов.")
    
    student = get_object_or_404(Student, pk=pk)
    user = student.user
    
    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            # Обновляем данные пользователя
            if user.username != form.cleaned_data['username']:
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
                # Создаем пользователя для родителя
                parent_user = User.objects.create_user(
                    username=form.cleaned_data['parent_username'],
                    password=form.cleaned_data['parent_password'],
                    email=form.cleaned_data.get('parent_email', ''),
                    user_type='parent'
                )
                
                # Создаем родителя
                parent = Parent(
                    user=parent_user,
                    full_name=form.cleaned_data['parent_full_name'],
                    phone_number=form.cleaned_data['parent_phone_number']
                )
                parent.save()
                
                # Привязываем родителя к студенту
                student.parent = parent
            
            student.save()
            
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
def parent_detail(request, pk):
    """Отображает детальную информацию о родителе."""
    # Получаем родителя или возвращаем 404, если не найден
    parent = get_object_or_404(Parent, pk=pk)
    
    # Проверка доступа
    if not (request.user.is_admin or request.user.is_reception or 
            (request.user.is_parent and request.user.parent_profile.id == pk)):
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
    
    parent = request.user.parent_profile
    children = parent.children.all()
    
    return render(request, 'accounts/parent_children.html', {'children': children})

@login_required
def parent_dashboard(request):
    """Отображает панель управления для родителя с информацией о его детях."""
    if not request.user.is_parent:
        return HttpResponseForbidden("Доступ запрещен. Вы не являетесь родителем.")
    
    try:
        parent = Parent.objects.get(user=request.user)
    except Parent.DoesNotExist:
        messages.error(request, "Профиль родителя не найден.")
        return redirect('home')
    
    # Получаем всех детей родителя
    children = Student.objects.filter(parent=parent)
    
    children_data = []
    for child in children:
        # Получаем классы, в которых учится ребенок
        enrollments = Enrollment.objects.filter(student=child).select_related('class_obj', 'class_obj__teacher')
        
        # Получаем посещаемость
        attendances = Attendance.objects.filter(student=child).select_related('class_schedule', 'class_schedule__class_obj')
        
        # Получаем домашние задания
        homework_submissions = HomeworkSubmission.objects.filter(student=child).select_related('homework')
        
        # Получаем оценки
        marks = Mark.objects.filter(student=child).select_related('class_obj')
        
        children_data.append({
            'student': child,
            'enrollments': enrollments,
            'attendances': attendances,
            'homework_submissions': homework_submissions,
            'marks': marks,
            'balance': child.balance
        })
    
    return render(request, 'accounts/parent_dashboard.html', {
        'parent': parent,
        'children_data': children_data
    })

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
