from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.db.models import Q

from .models import Attendance
from face_recognition_app.models import FaceAttendance
from accounts.models import Student, Parent

@login_required
def attendance_log(request):
    """
    Представление для просмотра журнала посещений с фотографиями, сделанными через Face ID.
    Родители видят посещения своих детей, студенты - свои посещения, учителя и администраторы - всех.
    """
    user = request.user
    
    # Определяем, какие посещения показывать в зависимости от типа пользователя
    if user.is_admin or user.is_reception or user.is_teacher:
        # Администраторы, рецепшн и учителя видят все посещения с Face ID
        attendances = Attendance.objects.filter(
            face_id_confirmed=True
        ).select_related('student', 'class_obj', 'class_schedule').order_by('-date')
    elif user.is_parent:
        # Родители видят посещения своих детей
        try:
            parent = user.parent_profile
            children = Student.objects.filter(parent=parent)
            attendances = Attendance.objects.filter(
                student__in=children,
                face_id_confirmed=True
            ).select_related('student', 'class_obj', 'class_schedule').order_by('-date')
        except:
            return HttpResponseForbidden("У вас нет прав для просмотра этой страницы")
    elif user.is_student:
        # Студенты видят свои посещения
        try:
            student = user.student_profile
            attendances = Attendance.objects.filter(
                student=student,
                face_id_confirmed=True
            ).select_related('student', 'class_obj', 'class_schedule').order_by('-date')
        except:
            return HttpResponseForbidden("У вас нет прав для просмотра этой страницы")
    else:
        return HttpResponseForbidden("У вас нет прав для просмотра этой страницы")
    
    # Получаем связанные FaceAttendance записи с фотографиями
    attendance_logs = []
    for attendance in attendances:
        try:
            face_attendance = FaceAttendance.objects.get(attendance=attendance)
            attendance_logs.append({
                'attendance': attendance,
                'face_attendance': face_attendance,
                'has_image': bool(face_attendance.image),
                'image_url': face_attendance.image.url if face_attendance.image else None,
                'confidence': face_attendance.confidence,
                'date': attendance.date,
                'class_name': attendance.class_obj.name,
                'time': f"{attendance.class_schedule.start_time.strftime('%H:%M')} - {attendance.class_schedule.end_time.strftime('%H:%M')}",
                'room': attendance.class_schedule.room,
                'student_name': attendance.student.full_name
            })
        except FaceAttendance.DoesNotExist:
            # Пропускаем записи без FaceAttendance
            pass
    
    context = {
        'attendance_logs': attendance_logs,
        'user_type': user.user_type
    }
    
    return render(request, 'attendance/attendance_log_new.html', context)

@login_required
def attendance_log_detail(request, attendance_id):
    """
    Представление для просмотра деталей конкретной записи посещаемости.
    """
    user = request.user
    
    # Получаем запись посещаемости
    attendance = get_object_or_404(Attendance, id=attendance_id, face_id_confirmed=True)
    
    # Проверяем права доступа
    if user.is_admin or user.is_reception or user.is_teacher:
        # Администраторы, рецепшн и учителя могут видеть любую запись
        pass
    elif user.is_parent:
        # Родители могут видеть только записи своих детей
        try:
            parent = user.parent_profile
            if attendance.student.parent != parent:
                return HttpResponseForbidden("У вас нет прав для просмотра этой записи")
        except:
            return HttpResponseForbidden("У вас нет прав для просмотра этой записи")
    elif user.is_student:
        # Студенты могут видеть только свои записи
        try:
            student = user.student_profile
            if attendance.student != student:
                return HttpResponseForbidden("У вас нет прав для просмотра этой записи")
        except:
            return HttpResponseForbidden("У вас нет прав для просмотра этой записи")
    else:
        return HttpResponseForbidden("У вас нет прав для просмотра этой записи")
    
    # Получаем связанную FaceAttendance запись
    try:
        face_attendance = FaceAttendance.objects.get(attendance=attendance)
        has_image = bool(face_attendance.image)
        image_url = face_attendance.image.url if face_attendance.image else None
        confidence = face_attendance.confidence
    except FaceAttendance.DoesNotExist:
        face_attendance = None
        has_image = False
        image_url = None
        confidence = 0
    
    context = {
        'attendance': attendance,
        'face_attendance': face_attendance,
        'has_image': has_image,
        'image_url': image_url,
        'confidence': confidence,
        'user_type': user.user_type
    }
    
    return render(request, 'attendance/attendance_log_detail_new.html', context)
