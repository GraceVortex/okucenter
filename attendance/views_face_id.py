import json
import logging
import base64
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.conf import settings
from django.db.models import Q

import json
import logging
import base64
import os
import numpy as np
from datetime import datetime, timedelta

from accounts.models import Student
from classes.models import ClassSchedule
from attendance.models import Attendance
from face_recognition_app.models import FaceAttendance
from face_recognition_app.facenet_utils import recognize_face

# Настройка логирования
logger = logging.getLogger(__name__)

# Порог уверенности для распознавания лица (80%)
FACE_RECOGNITION_THRESHOLD = 0.8

@login_required
def face_id(request):
    """View для страницы Face ID"""
    # Проверяем права доступа
    if not (request.user.is_admin or request.user.is_reception):
        return redirect('accounts:login')
    
    # Получаем последние отметки посещаемости
    attendance_logs = FaceAttendance.objects.select_related('attendance__student', 'attendance__class_obj').order_by('-timestamp')[:10]
    
    context = {
        'attendance_logs': attendance_logs
    }
    
    return render(request, 'attendance/face_id.html', context)

@login_required
def face_id_new(request):
    """View для новой страницы Face ID"""
    # Проверяем права доступа
    if not (request.user.is_admin or request.user.is_reception):
        return redirect('accounts:login')
    
    # Получаем последние отметки посещаемости
    attendance_logs = FaceAttendance.objects.select_related('attendance__student', 'attendance__class_obj').order_by('-timestamp')[:10]
    
    context = {
        'attendance_logs': attendance_logs
    }
    
    return render(request, 'attendance/face_id_new.html', context)

@login_required
@csrf_exempt
def api_recognize_face(request):
    """
    API для распознавания лица и получения информации о студенте.
    """
    logger.info("[API] Запрос на распознавание лица")
    
    if not (request.user.is_admin or request.user.is_reception):
        logger.warning("[API] Попытка доступа без необходимых прав")
        return JsonResponse({'success': False, 'message': 'Недостаточно прав'})
    
    if request.method != 'POST':
        logger.warning("[API] Неподдерживаемый метод запроса")
        return JsonResponse({'success': False, 'message': 'Метод не поддерживается'})
    
    try:
        # Получаем данные из запроса
        logger.info("[API] Парсим данные запроса")
        data = json.loads(request.body)
        face_data = data.get('face_data')
        
        if not face_data:
            logger.warning("[API] Данные изображения не предоставлены")
            return JsonResponse({'success': False, 'message': 'Данные изображения не предоставлены'})
        
        # Распознаем лицо с порогом уверенности
        logger.info(f"[API] Вызываем функцию recognize_face с порогом {FACE_RECOGNITION_THRESHOLD}")
        success, user, error, confidence = recognize_face(face_data, request, threshold=FACE_RECOGNITION_THRESHOLD)
        
        if user:
            logger.info(f"[API] Результат распознавания: success={success}, user={user.username}, error={error}, confidence={confidence:.4f}")
        else:
            logger.warning(f"[API] Результат распознавания: success={success}, user=None, error={error}, confidence={confidence:.4f if confidence else 'None'}")
        
        if error:
            logger.warning(f"[API] Ошибка при распознавании лица: {error}")
            return JsonResponse({'success': False, 'message': error})
        
        if not user:
            logger.warning("[API] Лицо не распознано или уверенность ниже порога")
            return JsonResponse({'success': False, 'message': 'Лицо не распознано или уверенность распознавания слишком низкая'})
        
        # Проверяем, является ли пользователь студентом
        if not hasattr(user, 'student_profile'):
            logger.warning(f"Пользователь {user.username} не является студентом")
            return JsonResponse({
                'success': False, 
                'message': 'Распознанный пользователь не является студентом'
            })
        
        student = user.student_profile
        logger.info(f"[API] Распознан студент: {student.full_name}, ID: {student.id}")
        
        # Получаем текущую дату и время
        now = timezone.now()
        today = now.date()
        current_time = now.time()
        logger.info(f"[API] Текущая дата: {today}, день недели: {today.weekday()}, время: {current_time}")
        
        # Получаем занятия студента на сегодня
        try:
            enrollments = student.enrollments.filter(is_active=True)
            class_ids = [enrollment.class_obj_id for enrollment in enrollments]
            logger.info(f"[API] Найдено {len(class_ids)} активных записей на курсы: {class_ids}")
        except Exception as e:
            logger.error(f"[API] Ошибка при получении записей на курсы: {e}")
            class_ids = []
        
        # Получаем расписание занятий на сегодня
        schedules = ClassSchedule.objects.filter(
            class_obj_id__in=class_ids,
            day_of_week=today.weekday()
        ).select_related('class_obj')
        
        # Показываем все занятия на сегодня, независимо от времени их окончания
        logger.info(f"[API] Найдено {schedules.count()} занятий на сегодня")
        
        # Получаем существующие записи о посещаемости на сегодня
        existing_attendance = Attendance.objects.filter(
            student=student,
            date=today
        ).values_list('class_obj_id', 'status')
        
        # Создаем словарь существующих записей о посещаемости
        attendance_dict = {class_id: status for class_id, status in existing_attendance}
        
        # Формируем список занятий для отображения
        classes = []
        for schedule in schedules:
            class_obj = schedule.class_obj
            status = attendance_dict.get(class_obj.id, None)
            
            # Форматируем время начала и окончания
            start_time = schedule.start_time.strftime('%H:%M')
            end_time = schedule.end_time.strftime('%H:%M')
            
            class_info = {
                'id': class_obj.id,
                'name': class_obj.name,
                'schedule_id': schedule.id,
                'time': f"{start_time} - {end_time}",
                'status': status,
                'marked': status is not None
            }
            classes.append(class_info)
        
        # Формируем ответ
        response_data = {
            'success': True,
            'student': {
                'id': student.id,
                'name': student.full_name,
                'photo_url': student.photo.url if student.photo else None,
            },
            'confidence': confidence,
            'classes': classes,
            'has_classes': len(classes) > 0,
            'face_data': face_data
        }
        
        # Дополнительное логирование
        logger.info(f"[API] Отправляем ответ: {response_data}")
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"[API] Ошибка при распознавании лица: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Ошибка при распознавании лица: {str(e)}'})

@login_required
@csrf_exempt
def api_mark_attendance(request):
    """
    API для отметки посещаемости по распознанному лицу.
    """
    logger.info("[API] Запрос на отметку посещаемости")
    
    if not (request.user.is_admin or request.user.is_reception):
        logger.warning("[API] Попытка доступа без необходимых прав")
        return JsonResponse({'success': False, 'message': 'Недостаточно прав'})
    
    if request.method != 'POST':
        logger.warning("[API] Неподдерживаемый метод запроса")
        return JsonResponse({'success': False, 'message': 'Метод не поддерживается'})
    
    try:
        # Получаем данные из запроса
        data = json.loads(request.body)
        student_id = data.get('student_id')
        class_id = data.get('class_id')
        status = data.get('status')
        face_data = data.get('face_data')
        
        logger.info(f"[API] Данные запроса: student_id={student_id}, class_id={class_id}, status={status}")
        
        # Проверяем наличие необходимых данных
        if not all([student_id, class_id, status]):
            logger.warning("[API] Отсутствуют необходимые данные")
            return JsonResponse({'success': False, 'message': 'Отсутствуют необходимые данные'})
        
        # Проверяем статус
        if status not in ['present', 'absent']:
            logger.warning(f"[API] Некорректный статус: {status}")
            return JsonResponse({'success': False, 'message': 'Некорректный статус'})
        
        # Получаем студента
        try:
            student = Student.objects.get(id=student_id)
            logger.info(f"[API] Найден студент: {student.full_name}")
        except Student.DoesNotExist:
            logger.warning(f"[API] Студент с ID {student_id} не найден")
            return JsonResponse({'success': False, 'message': 'Студент не найден'})
        
        # Получаем текущую дату
        today = timezone.now().date()
        
        # Проверяем, существует ли уже запись о посещаемости
        attendance, created = Attendance.objects.update_or_create(
            student=student,
            class_obj_id=class_id,
            date=today,
            defaults={'status': status, 'marked_by': request.user}
        )
        
        logger.info(f"[API] Запись о посещаемости {'создана' if created else 'обновлена'}: {attendance.id}")
        
        # Сохраняем данные о распознавании лица
        if face_data:
            try:
                face_attendance = FaceAttendance.objects.create(
                    attendance=attendance,
                    face_data=face_data,
                    confidence=0.9,  # Значение по умолчанию
                    created_by=request.user
                )
                logger.info(f"[API] Сохранены данные о распознавании лица: {face_attendance.id}")
            except Exception as e:
                logger.error(f"[API] Ошибка при сохранении данных о распознавании лица: {str(e)}")
        
        # Формируем ответ
        response_data = {
            'success': True,
            'message': 'Посещаемость успешно отмечена',
            'attendance': {
                'id': attendance.id,
                'student_name': student.full_name,
                'class_name': attendance.class_obj.name,
                'date': today.strftime('%d.%m.%Y'),
                'status': status
            }
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"[API] Ошибка при отметке посещаемости: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Ошибка при отметке посещаемости: {str(e)}'})
