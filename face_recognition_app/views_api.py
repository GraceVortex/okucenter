import logging
import json
import base64
from io import BytesIO
from PIL import Image
import numpy as np
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from accounts.models import Student, Teacher
from classes.models import Class, ClassSchedule
from attendance.models import Attendance
from .models import FaceAttendance
from .facenet_utils import process_base64_image, recognize_face

# Настраиваем логгер
logger = logging.getLogger(__name__)

@login_required
def api_recognize_attendance(request):
    """API для распознавания лиц и отметки посещаемости"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается'})
    
    # Проверяем права доступа
    if not (request.user.is_admin or request.user.is_reception or request.user.is_teacher):
        return JsonResponse({'success': False, 'error': 'У вас нет прав для отметки посещаемости'})
    
    try:
        # Получаем данные из запроса
        image_data = request.POST.get('image_data')
        mark_attendance = request.POST.get('mark_attendance', 'false').lower() == 'true'
        class_id = request.POST.get('class_id')
        
        if not image_data:
            return JsonResponse({'success': False, 'error': 'Не указаны обязательные параметры'})
        
        # Обрабатываем изображение
        try:
            # Проверяем формат изображения
            if not image_data.startswith('data:image'):
                image_data = 'data:image/jpeg;base64,' + image_data
                
            logger.info(f"Получено изображение для распознавания, длина: {len(image_data)}")
        except Exception as e:
            logger.error(f"Ошибка при обработке изображения: {e}")
            return JsonResponse({'success': False, 'error': f'Ошибка при обработке изображения: {str(e)}'})
        
        # Получаем текущую дату
        today = timezone.now().date()
        
        # Распознаем лицо
        try:
            # Добавляем дополнительное логирование
            logger.info(f"[API] Начинаем распознавание лица с изображения длиной {len(image_data)} символов")
            
            # Вызываем функцию распознавания лица с высоким порогом уверенности
            # Используем значение по умолчанию из модуля facenet_utils (0.88 или 88%)
            success, user, message, confidence = recognize_face(image_data, request)
            
            logger.info(f"[API] Результат распознавания: success={success}, user={user.username if user else None}, message={message}, confidence={confidence:.4f} ({confidence*100:.1f}%)")
            
            # Если распознавание успешно, получаем студента
            student_id = None
            if success and user and hasattr(user, 'student_profile'):
                student_id = user.student_profile.id
                logger.info(f"Найден студент с ID: {student_id}")
            
            if not student_id:
                # Добавляем более подробную информацию об ошибке
                error_message = f'Лицо не распознано. Убедитесь, что студент зарегистрирован в системе. Детали: {message}'
                logger.warning(f'Ошибка распознавания: {error_message}')
                return JsonResponse({'success': False, 'error': error_message})
            
            # Получаем студента
            try:
                student = Student.objects.get(id=student_id)
                logger.info(f'Успешно распознан студент: {student.user.get_full_name()} (ID: {student_id})')
            except Student.DoesNotExist:
                logger.error(f'Студент с ID {student_id} не найден в базе данных')
                return JsonResponse({'success': False, 'error': 'Студент не найден в базе данных.'})
                
            # Получаем все активные зачисления студента
            active_enrollments = student.enrollments.filter(is_active=True)
            
            # Получаем все классы студента
            student_classes = [enrollment.class_obj for enrollment in active_enrollments]
            
            # Получаем расписание на сегодня для этого студента
            today_schedules = ClassSchedule.objects.filter(
                class_obj__in=student_classes,
                day_of_week=today.weekday()
            ).select_related('class_obj')
            
            # Форматируем расписание для отображения
            schedule_data = []
            for schedule in today_schedules:
                schedule_data.append({
                    'id': schedule.id,
                    'class_id': schedule.class_obj.id,
                    'class_name': schedule.class_obj.name,
                    'start_time': schedule.start_time.strftime('%H:%M'),
                    'end_time': schedule.end_time.strftime('%H:%M'),
                    'teacher': schedule.class_obj.teacher.user.get_full_name() if hasattr(schedule.class_obj, 'teacher') else 'Не назначен',
                    'room': schedule.room or 'Не указан'
                })
            
            # Если указан конкретный класс и нужно отметить посещаемость
            if class_id and mark_attendance:
                try:
                    class_obj = Class.objects.get(id=class_id)
                    
                    # Проверяем, что студент принадлежит к выбранному классу
                    if not student.enrollments.filter(class_obj_id=class_obj.id, is_active=True).exists():
                        return JsonResponse({
                            'success': True, 
                            'student_id': student.id,
                            'student_name': student.user.get_full_name(),
                            'confidence': float(confidence),
                            'today_schedules': schedule_data,
                            'attendance_marked': False,
                            'attendance_error': f'Студент не принадлежит к классу {class_obj.name}'
                        })
                    
                    # Получаем расписание для этого класса на сегодня
                    try:
                        class_schedule = ClassSchedule.objects.filter(
                            class_obj=class_obj,
                            day_of_week=today.weekday()
                        ).first()
                        
                        if not class_schedule:
                            return JsonResponse({
                                'success': False,
                                'error': f'Расписание для класса {class_obj.name} на сегодня не найдено'
                            })
                        
                        # Создаем или обновляем запись о посещаемости
                        with transaction.atomic():
                            attendance, created = Attendance.objects.get_or_create(
                                student=student,
                                class_obj=class_obj,
                                date=today,
                                defaults={
                                    'status': 'present',
                                    'class_schedule': class_schedule  # Добавляем обязательное поле class_schedule
                                }
                            )
                            
                            if not created:
                                attendance.status = 'present'
                                if not attendance.class_schedule:
                                    attendance.class_schedule = class_schedule
                                # Автоматически подтверждаем посещаемость через Face ID
                                attendance.face_id_confirmed = True
                                attendance.teacher_confirmed = True  # Автоматически подтверждаем посещаемость учителем
                                attendance.reception_confirmed = True  # Автоматически подтверждаем посещаемость рецепшеном
                                attendance.save()
                    except Exception as e:
                        logger.error(f"[API] Ошибка при создании записи посещаемости: {e}")
                        return JsonResponse({
                            'success': False,
                            'error': f'Ошибка при создании записи посещаемости: {str(e)}'
                        })
                        
                        # Создаем запись о распознавании лица
                        face_attendance, created = FaceAttendance.objects.get_or_create(
                            attendance=attendance,
                            defaults={
                                'confidence': confidence
                            }
                        )
                        
                        # Сохраняем изображение, использованное для распознавания
                        try:
                            if image_data and ('base64,' in image_data):
                                # Извлекаем данные base64 без префикса
                                image_data_base64 = image_data.split('base64,')[1]
                                image_bytes = base64.b64decode(image_data_base64)
                                
                                # Сохраняем изображение в модели FaceAttendance
                                from django.core.files.base import ContentFile
                                import uuid
                                
                                filename = f"face_attendance_{uuid.uuid4()}.jpg"
                                face_attendance.image.save(filename, ContentFile(image_bytes), save=True)
                                logger.info(f"[API] Изображение сохранено для посещаемости ID: {attendance.id}")
                                
                                # Отправляем фотографию родителю или ученику
                                # Эту функцию можно реализовать через асинхронную задачу
                                # Для простоты пока просто логируем
                                student = attendance.student
                                if student and student.parent:
                                    logger.info(f"[API] Необходимо отправить фото родителю: {student.parent.user.username}")
                                else:
                                    logger.info(f"[API] Необходимо отправить фото ученику: {student.user.username}")
                        except Exception as e:
                            logger.error(f"[API] Ошибка при сохранении изображения: {e}")
                    
                    return JsonResponse({
                        'success': True,
                        'student_id': student.id,
                        'student_name': student.user.get_full_name(),
                        'confidence': float(confidence),
                        'today_schedules': schedule_data,
                        'attendance_marked': True,
                        'attendance_id': attendance.id,
                        'class_name': class_obj.name
                    })
                    
                except Class.DoesNotExist:
                    return JsonResponse({
                        'success': True,
                        'student_id': student.id,
                        'student_name': student.user.get_full_name(),
                        'confidence': float(confidence),
                        'today_schedules': schedule_data,
                        'attendance_marked': False,
                        'attendance_error': 'Указанный класс не найден'
                    })
            
            # Если не нужно отмечать посещаемость, просто возвращаем информацию о студенте и его расписании
            return JsonResponse({
                'success': True,
                'student_id': student.id,
                'student_name': student.user.get_full_name(),
                'confidence': float(confidence),
                'today_schedules': schedule_data,
                'attendance_marked': False
            })
            
        except Exception as e:
            logger.error(f"Ошибка при распознавании лица: {e}")
            return JsonResponse({'success': False, 'error': f'Ошибка при распознавании лица: {str(e)}'})
    
    except Exception as e:
        logger.error(f"Общая ошибка: {e}")
        return JsonResponse({'success': False, 'error': f'Произошла ошибка: {str(e)}'})
