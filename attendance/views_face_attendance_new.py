"""
Модуль для быстрой отметки посещаемости с использованием распознавания лиц.
Использует FaceNet для более точного распознавания лиц.
"""

import json
import base64
import logging
from datetime import datetime, timedelta

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from django.contrib import messages
from django.conf import settings

from accounts.models import User, Student
from classes.models import Class, ClassSchedule
from .models import Attendance
from face_recognition_app.models import FaceAttendance

# Настраиваем логгер
logger = logging.getLogger(__name__)

# Импортируем функции из модуля facenet_utils
from face_recognition_app.facenet_utils import recognize_face, process_base64_image, compare_faces, FACENET_THRESHOLD
logger.info("Используем FaceNet для быстрой отметки посещаемости")

# Порог уверенности для распознавания лиц (65%)
FACE_RECOGNITION_THRESHOLD = 0.65

@login_required
def quick_face_attendance(request):
    """
    Страница для быстрой отметки посещаемости по лицу.
    Использует улучшенный алгоритм FaceNet для распознавания лиц.
    """
    # Проверяем, что пользователь имеет права для отметки посещаемости
    if not (request.user.is_admin or request.user.is_reception):
        messages.error(request, "У вас нет прав для отметки посещаемости")
        return redirect('core:home')
    
    # Получаем последние записи о посещаемости через распознавание лиц
    attendance_logs = FaceAttendance.objects.select_related(
        'attendance', 'attendance__student', 'attendance__class_obj'
    ).order_by('-timestamp')[:10]
    
    # Получаем сегодняшнюю дату
    today = timezone.now().date()
    
    # Получаем список активных классов на сегодня
    today_classes = ClassSchedule.objects.filter(
        day_of_week=today.weekday()
    ).select_related('class_obj')
    
    context = {
        'attendance_logs': attendance_logs,
        'today_classes': today_classes,
        'today': today,
        'use_facenet': True
    }
    
    return render(request, 'attendance/quick_face_attendance_new.html', context)

@login_required
def quick_face_attendance_new(request):
    """
    Страница быстрой отметки посещаемости с помощью распознавания лица.
    Использует FaceNet для более точного распознавания.
    """
    if not (request.user.is_admin or request.user.is_reception):
        return redirect('accounts:login')
    
    return render(request, 'attendance/quick_face_attendance_new.html')

@login_required
@csrf_exempt
def api_recognize_face(request):
    """
    API для распознавания лица и получения информации о студенте.
    Использует FaceNet для более точного распознавания.
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
        
        # Если занятия не найдены, добавляем тестовые данные для отладки
        if not classes and hasattr(settings, 'DEBUG') and settings.DEBUG:
            logger.warning("[API] Занятия не найдены, добавляем тестовые данные для отладки")
            classes = [
                {
                    'id': 1001,
                    'name': 'Математика (тест)',
                    'schedule_id': 1001,
                    'time': '09:00 - 10:30',
                    'status': None,
                    'marked': False
                },
                {
                    'id': 1002,
                    'name': 'Физика (тест)',
                    'schedule_id': 1002,
                    'time': '11:00 - 12:30',
                    'status': None,
                    'marked': False
                }
            ]
        
        # Получаем URL фотографии студента, если она есть
        photo_url = None
        if hasattr(student, 'face_image') and student.face_image:
            try:
                photo_url = student.face_image.url
            except Exception as e:
                logger.error(f"[API] Ошибка при получении URL фотографии студента: {e}")
        elif hasattr(student, 'photo') and student.photo:
            try:
                photo_url = student.photo.url
            except Exception as e:
                logger.error(f"[API] Ошибка при получении URL фотографии студента: {e}")
        
        # Формируем ответ
        response_data = {
            'success': True,
            'student': {
                'id': student.id,
                'full_name': student.full_name,
                'photo_url': photo_url,
                'confidence': float(confidence) if confidence is not None else 0.8
            },
            'classes': classes
        }
        
        return JsonResponse(response_data)
    
    except json.JSONDecodeError:
        logger.error("[API] Ошибка декодирования JSON")
        return JsonResponse({
            'success': False,
            'message': "Неверный формат данных запроса"
        })
    except Exception as e:
        logger.error(f"[API] Ошибка при распознавании лица: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f"Произошла ошибка при распознавании лица: {str(e)}"
        })

@login_required
@csrf_exempt
def api_mark_attendance(request):
    """
    API для отметки посещаемости по результатам распознавания лица.
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
        logger.info("[API] Парсим данные запроса")
        data = json.loads(request.body)
        student_id = data.get('student_id')
        face_data = data.get('face_data')
        attendance_data = data.get('attendance_data', [])
        
        logger.info(f"[API] Полученные данные: student_id={student_id}, attendance_data={attendance_data}")
        
        if not student_id:
            logger.warning("[API] ID студента не предоставлен")
            return JsonResponse({'success': False, 'message': 'ID студента не предоставлен'})
        
        if not attendance_data:
            logger.warning("[API] Данные о посещаемости не предоставлены")
            return JsonResponse({'success': False, 'message': 'Данные о посещаемости не предоставлены'})
        
        # Получаем студента
        try:
            student = Student.objects.get(id=student_id)
            logger.info(f"[API] Найден студент: {student.full_name}, ID: {student.id}")
        except Student.DoesNotExist:
            logger.warning(f"[API] Студент с ID {student_id} не найден")
            return JsonResponse({'success': False, 'message': 'Студент не найден'})
        
        # Получаем текущую дату
        today = timezone.now().date()
        logger.info(f"[API] Текущая дата: {today}")
        
        # Список для хранения логов отметок
        attendance_logs = []
        
        # Отмечаем посещаемость для каждого класса
        with transaction.atomic():
            for item in attendance_data:
                class_id = item.get('class_id')
                schedule_id = item.get('schedule_id')
                status = item.get('status', 'absent')  # По умолчанию отсутствовал
                
                if not class_id or not schedule_id:
                    logger.warning(f"[API] Пропускаем запись без class_id или schedule_id: {item}")
                    continue
                
                logger.info(f"[API] Обрабатываем запись: class_id={class_id}, schedule_id={schedule_id}, status={status}")
                
                # Получаем класс и расписание
                try:
                    class_obj = Class.objects.get(id=class_id)
                    schedule = ClassSchedule.objects.get(id=schedule_id)
                    logger.info(f"[API] Найден класс: {class_obj.name} и расписание ID: {schedule.id}")
                except (Class.DoesNotExist, ClassSchedule.DoesNotExist) as e:
                    logger.warning(f"[API] Не найден класс или расписание: {e}")
                    continue
                
                # Создаем или обновляем запись о посещаемости
                try:
                    attendance, created = Attendance.objects.update_or_create(
                        student=student,
                        class_obj=class_obj,
                        date=today,
                        defaults={
                            'class_schedule': schedule,
                            'status': status,
                            'reception_confirmed': True,
                            'reception_confirmed_by': request.user
                        }
                    )
                    logger.info(f"[API] {'Создана' if created else 'Обновлена'} запись о посещаемости ID: {attendance.id}")
                except Exception as e:
                    logger.error(f"[API] Ошибка при создании/обновлении записи о посещаемости: {e}")
                    continue
                
                # Получаем уверенность из распознавания лица
                confidence = 0.85  # Значение по умолчанию
                if face_data:
                    try:
                        # Обрабатываем изображение
                        face_features, error = process_base64_image(face_data)
                        if not error and face_features is not None:
                            # Если у студента есть зарегистрированное лицо, сравниваем с ним
                            if hasattr(student, 'user') and hasattr(student.user, 'face_id_data') and student.user.face_id_data:
                                from face_recognition_app.facenet_utils import decode_face_data
                                stored_features = decode_face_data(student.user.face_id_data)
                                if stored_features is not None:
                                    # Сравниваем лица
                                    _, confidence = compare_faces(stored_features, face_features)
                                    logger.info(f"[API] Уверенность распознавания: {confidence:.4f}")
                    except Exception as e:
                        logger.error(f"[API] Ошибка при обработке изображения лица: {e}")
                
                # Создаем запись о посещаемости через распознавание лица
                try:
                    face_attendance = FaceAttendance.objects.create(
                        attendance=attendance,
                        confidence=confidence,
                        created_by=request.user
                    )
                    logger.info(f"[API] Создана запись о распознавании лица ID: {face_attendance.id}")
                except Exception as e:
                    logger.error(f"[API] Ошибка при создании записи о распознавании лица: {e}")
                    continue
                
                # Если есть изображение, сохраняем его
                if face_data:
                    try:
                        # Удаляем префикс data:image/jpeg;base64, если он есть
                        if ',' in face_data:
                            face_data = face_data.split(',')[1]
                        
                        # Декодируем base64 в байты
                        image_data = base64.b64decode(face_data)
                        
                        # Сохраняем изображение, если есть такая функция
                        if hasattr(face_attendance, 'save_image'):
                            face_attendance.save_image(image_data)
                            logger.info(f"[API] Сохранено изображение для записи о распознавании лица ID: {face_attendance.id}")
                    except Exception as e:
                        logger.error(f"[API] Ошибка при сохранении изображения: {e}")
                
                # Добавляем запись в список логов
                attendance_logs.append({
                    'time': timezone.now().strftime('%H:%M'),
                    'student_name': student.full_name,
                    'class_name': class_obj.name,
                    'status': attendance.status
                })
                
                # Снимаем деньги с баланса студента, если это необходимо и статус "присутствовал"
                if status == 'present' and hasattr(class_obj, 'price_per_lesson') and class_obj.price_per_lesson > 0:
                    try:
                        # Снимаем деньги с баланса студента (разрешаем минусовой баланс)
                        student.balance -= class_obj.price_per_lesson
                        student.save()
                        logger.info(f"[API] Снято {class_obj.price_per_lesson} с баланса студента. Новый баланс: {student.balance}")
                        
                        # Создаем запись о финансовой операции (если есть соответствующая модель)
                        try:
                            from django.conf import settings
                            if 'finance' in settings.INSTALLED_APPS:
                                from finance.models import Transaction
                                transaction = Transaction.objects.create(
                                    student=student,
                                    amount=-class_obj.price_per_lesson,
                                    description=f"Оплата за занятие {class_obj.name} от {today}",
                                    transaction_type='class_payment'
                                )
                                logger.info(f"[API] Создана финансовая транзакция ID: {transaction.id}")
                        except Exception as e:
                            logger.error(f"[API] Ошибка при создании финансовой транзакции: {e}")
                    except Exception as e:
                        logger.error(f"[API] Ошибка при снятии денег с баланса: {e}")
        
        logger.info("[API] Получаем обновленные логи посещаемости")
        # Получаем обновленные логи посещаемости
        try:
            updated_logs = FaceAttendance.objects.select_related(
                'attendance', 'attendance__student', 'attendance__class_obj'
            ).order_by('-timestamp')[:10]
            
            # Форматируем логи для ответа
            formatted_logs = []
            for log in updated_logs:
                try:
                    formatted_logs.append({
                        'time': log.timestamp.strftime('%H:%M'),
                        'student_name': log.attendance.student.full_name,
                        'class_name': log.attendance.class_obj.name,
                        'status': log.attendance.status
                    })
                except Exception as e:
                    logger.error(f"[API] Ошибка при форматировании лога: {e}")
        except Exception as e:
            logger.error(f"[API] Ошибка при получении обновленных логов: {e}")
            formatted_logs = attendance_logs
        
        logger.info("[API] Посещаемость успешно отмечена")
        return JsonResponse({
            'success': True,
            'message': 'Посещаемость успешно отмечена',
            'attendance_logs': formatted_logs
        })
    
    except json.JSONDecodeError:
        logger.error("[API] Ошибка декодирования JSON")
        return JsonResponse({
            'success': False,
            'message': "Неверный формат данных запроса"
        })
    except Exception as e:
        logger.error(f"[API] Ошибка при отметке посещаемости: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Произошла ошибка при отметке посещаемости: {str(e)}'
        })
