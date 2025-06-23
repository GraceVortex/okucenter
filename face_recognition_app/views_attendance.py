import logging
import json
import base64
from datetime import datetime

# Настраиваем логгер
logger = logging.getLogger(__name__)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction

from accounts.models import User, Student, Teacher
from classes.models import Class, ClassSchedule, Enrollment
from attendance.models import Attendance
from .models import FaceRecognitionLog, FaceAttendance
from .facenet_utils import recognize_face, FACENET_THRESHOLD

@login_required
def attendance_page(request):
    """Страница для отметки посещаемости по распознаванию лица"""
    # Проверяем права доступа - только администраторы, учителя и ресепшн могут отмечать посещаемость
    if not (request.user.is_admin or request.user.is_teacher or request.user.is_reception):
        return HttpResponseForbidden("У вас нет прав для отметки посещаемости")
    
    return render(request, 'face_recognition/attendance_new.html')

@login_required
def simple_attendance_page(request):
    """Упрощенная страница для отметки посещаемости по распознаванию лица"""
    # Проверяем права доступа - только администраторы, учителя и ресепшн могут отмечать посещаемость
    if not (request.user.is_admin or request.user.is_teacher or request.user.is_reception):
        return HttpResponseForbidden("У вас нет прав для отметки посещаемости")
    
    return render(request, 'face_recognition/simple_attendance.html')

@login_required
def mark_attendance_page(request):
    """Страница для отметки посещаемости конкретного студента"""
    # Временно отключаем проверку прав доступа для отладки
    # if not (request.user.is_admin or request.user.is_teacher or request.user.is_reception):
    #     return HttpResponseForbidden("У вас нет прав для отметки посещаемости")
    
    # Получаем данные студента
    student_id = request.GET.get('student_id')
    username = request.GET.get('username')
    
    student = None
    classes = []
    
    # Получаем студента по ID или имени пользователя
    if student_id:
        student = Student.objects.filter(id=student_id).first()
    elif username:
        user = User.objects.filter(username=username).first()
        if user:
            student = Student.objects.filter(user=user).first()
    
    # Если студент найден, получаем его занятия на сегодня
    if student:
        # Получаем текущий день недели (0-6, где 0 - понедельник, 6 - воскресенье)
        # Используем weekday() вместо isoweekday() для совместимости с базой данных
        current_weekday = timezone.now().weekday()
        
        # Получаем все записи студента на занятия
        enrollments = Enrollment.objects.filter(
            student=student,
            is_active=True
        )
        
        # Получаем ID всех занятий, на которые записан студент
        class_ids = enrollments.values_list('class_obj_id', flat=True)
        
        # Получаем только расписания занятий на текущий день недели и только для занятий студента
        today_schedules = ClassSchedule.objects.filter(
            day_of_week=current_weekday,
            class_obj_id__in=class_ids
        )
        
        # Добавляем только занятия на сегодня
        for schedule in today_schedules:
            class_obj = schedule.class_obj
            classes.append({
                'id': class_obj.id,
                'subject_name': class_obj.name,  # Исправлено: используем name вместо subject_name
                'start_time': schedule.start_time.strftime('%H:%M'),
                'end_time': schedule.end_time.strftime('%H:%M'),
                'room': schedule.room,
                'day_of_week': schedule.day_of_week,
                'teacher_name': f"{class_obj.teacher.user.first_name} {class_obj.teacher.user.last_name}"
            })
    
    return render(request, 'face_recognition/mark_attendance.html', {
        'student': student,
        'classes': classes
    })

@login_required
def recognize_face_view(request):
    """API для распознавания лица и получения топ-3 совпадений"""
    # Проверяем права доступа
    if not (request.user.is_admin or request.user.is_teacher or request.user.is_reception):
        return JsonResponse({'success': False, 'message': 'У вас нет прав для распознавания лиц'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Метод не поддерживается'})
    
    try:
        # Получаем данные из запроса JSON
        data = json.loads(request.body)
        base64_image = data.get('face_data')
        
        if not base64_image:
            return JsonResponse({'success': False, 'message': 'Изображение не предоставлено'})
        
        # Распознаем лицо с возвратом всех сходств
        success, user, error_message, confidence, all_similarities = recognize_face(
            base64_image, 
            request=request, 
            threshold=0.75,  # Устанавливаем порог 75%
            return_all_scores=True
        )
        
        # Если распознавание успешно
        if success and user:
            # Преобразуем confidence в проценты
            confidence_percent = confidence * 100
            
            # Получаем информацию о пользователе
            user_info = {
                'success': True,
                'user_id': user.id,
                'username': user.username,
                'full_name': f"{user.first_name} {user.last_name}",
                'user_type': 'Студент' if hasattr(user, 'student') else 'Учитель' if hasattr(user, 'teacher') else 'Администратор',
                'confidence': float(confidence),
                'confidence_percent': float(confidence_percent),
                'threshold': float(0.75),
                'threshold_percent': 75.0
            }
            
            # Если пользователь - студент, добавляем ID студента
            if hasattr(user, 'student'):
                user_info['is_student'] = True
                user_info['student_id'] = user.student.id
            else:
                user_info['is_student'] = False
            
            # Подготавливаем список всех сходств для отображения топ-3
            user_scores = []
            
            # Проверяем тип all_similarities - это может быть словарь или список кортежей
            if isinstance(all_similarities, dict):
                # Если это словарь (username -> score)
                for username, sim_score in all_similarities.items():
                    try:
                        # sim_score уже преобразован в стандартный Python float
                        matched_user = User.objects.get(username=username)
                        user_type = 'Студент' if hasattr(matched_user, 'student') else 'Учитель' if hasattr(matched_user, 'teacher') else 'Администратор'
                        
                        user_scores.append({
                            'username': username,
                            'full_name': f"{matched_user.first_name} {matched_user.last_name}",
                            'user_type': user_type,
                            'user_id': matched_user.id,
                            'confidence': sim_score * 100  # Преобразуем в проценты
                        })
                    except User.DoesNotExist:
                        logger.warning(f"Пользователь {username} не найден в базе данных")
            elif isinstance(all_similarities, list):
                # Если это список кортежей (user, score)
                for user_data, sim_score in all_similarities:
                    try:
                        # sim_score уже преобразован в стандартный Python float
                        user_type = 'Студент' if hasattr(user_data, 'student') else 'Учитель' if hasattr(user_data, 'teacher') else 'Администратор'
                        
                        user_scores.append({
                            'username': user_data.username,
                            'full_name': f"{user_data.first_name} {user_data.last_name}",
                            'user_type': user_type,
                            'user_id': user_data.id,
                            'confidence': sim_score * 100  # Преобразуем в проценты
                        })
                    except Exception as e:
                        logger.warning(f"Ошибка при обработке данных пользователя: {e}")
            else:
                logger.error(f"Неизвестный формат all_similarities: {type(all_similarities)}")
                return JsonResponse({'success': False, 'message': 'Ошибка формата данных сходства'})
            
            # Сортируем по убыванию confidence
            user_scores.sort(key=lambda x: x['confidence'], reverse=True)
            
            # Добавляем список сходств в ответ
            user_info['user_scores'] = user_scores
            
            # Записываем лог распознавания
            log_entry = FaceRecognitionLog(
                user=user,
                recognized_by=request.user,
                confidence=confidence,
                image_data=base64_image
            )
            log_entry.save()
            
            # Финальное преобразование всех данных для безопасной JSON сериализации
            user_info = convert_numpy_types(user_info)
            
            return JsonResponse(user_info)
        else:
            # Если распознавание не удалось, но у нас есть список сходств
            if all_similarities:
                # Подготавливаем список всех сходств для отображения топ-3
                user_scores = []
                
                # Проверяем тип all_similarities - это может быть словарь или список кортежей
                if isinstance(all_similarities, dict):
                    # Если это словарь (username -> score)
                    for username, sim_score in all_similarities.items():
                        try:
                            # Явно преобразуем numpy.float32 в стандартный Python float
                            sim_score = float(sim_score)
                            
                            matched_user = User.objects.get(username=username)
                            user_type = 'Студент' if hasattr(matched_user, 'student') else 'Учитель' if hasattr(matched_user, 'teacher') else 'Администратор'
                            
                            user_scores.append({
                                'username': username,
                                'full_name': f"{matched_user.first_name} {matched_user.last_name}",
                                'user_type': user_type,
                                'user_id': matched_user.id,
                                'confidence': float(sim_score * 100)  # Преобразуем в проценты
                            })
                        except User.DoesNotExist:
                            logger.warning(f"Пользователь {username} не найден в базе данных")
                elif isinstance(all_similarities, list):
                    # Если это список кортежей (user, score)
                    for user_data, sim_score in all_similarities:
                        try:
                            # Явно преобразуем numpy.float32 в стандартный Python float
                            sim_score = float(sim_score)
                            
                            user_type = 'Студент' if hasattr(user_data, 'student') else 'Учитель' if hasattr(user_data, 'teacher') else 'Администратор'
                            
                            user_scores.append({
                                'username': user_data.username,
                                'full_name': f"{user_data.first_name} {user_data.last_name}",
                                'user_type': user_type,
                                'user_id': user_data.id,
                                'confidence': float(sim_score * 100)  # Преобразуем в проценты
                            })
                        except Exception as e:
                            logger.warning(f"Ошибка при обработке данных пользователя: {e}")
                else:
                    logger.error(f"Неизвестный формат all_similarities: {type(all_similarities)}")
                    return JsonResponse({'success': False, 'message': 'Ошибка формата данных сходства'})
                
                # Сортируем по убыванию confidence
                user_scores.sort(key=lambda x: x['confidence'], reverse=True)
                
                error_response = {
                    'success': False,
                    'message': error_message or 'Лицо не распознано (ниже порога уверенности)',
                    'threshold': float(0.75),
                    'threshold_percent': 75.0,
                    'user_scores': user_scores
                }
                error_response = convert_numpy_types(error_response)
                return JsonResponse(error_response)
            else:
                error_response = {
                    'success': False,
                    'message': error_message or 'Лицо не распознано'
                }
                error_response = convert_numpy_types(error_response)
                return JsonResponse(error_response)
    
    except Exception as e:
        # В случае ошибки
        logger.error(f"Ошибка при распознавании лица: {e}")
        error_response = {
            'success': False,
            'message': f'Ошибка при распознавании лица: {str(e)}'
        }
        error_response = convert_numpy_types(error_response)
        return JsonResponse(error_response)

@login_required
def mark_attendance_view(request):
    """API для отметки посещаемости по распознанному лицу"""
    # Проверяем права доступа
    # Временно отключаем проверку прав для отладки
    # if not (request.user.is_admin or request.user.is_teacher or request.user.is_reception):
    #     return JsonResponse({'success': False, 'message': 'У вас нет прав для отметки посещаемости'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Метод не поддерживается'})
    
    try:
        # Отладочная информация
        print(f"\n\n[DEBUG] Получен POST-запрос на mark_attendance_view")
        print(f"[DEBUG] Content-Type: {request.content_type}")
        print(f"[DEBUG] POST data: {request.POST}")
        
        # Получаем данные из формы POST или из JSON
        if request.content_type and 'application/json' in request.content_type:
            # Если данные пришли в формате JSON
            data = json.loads(request.body)
            print(f"[DEBUG] JSON data: {data}")
        else:
            # Если данные пришли из формы
            data = request.POST
            print(f"[DEBUG] Form data: {data}")
        
        # Получаем данные студента
        student_id = data.get('student_id')
        username = data.get('username')
        class_id = data.get('class_id')
        
        print(f"[DEBUG] student_id: {student_id}")
        print(f"[DEBUG] username: {username}")
        print(f"[DEBUG] class_id: {class_id}")
        
        # Проверяем наличие необходимых данных
        if not class_id:
            return JsonResponse({'success': False, 'message': 'ID занятия не предоставлено'})
        
        student = None
        
        # Получаем студента по ID или имени пользователя
        if student_id:
            try:
                student = Student.objects.get(id=student_id)
            except Student.DoesNotExist:
                return JsonResponse({'success': False, 'message': f'Студент с ID {student_id} не найден'})
        elif username:
            try:
                user = User.objects.get(username=username)
                if not hasattr(user, 'student'):
                    return JsonResponse({'success': False, 'message': f'Пользователь {username} не является студентом'})
                student = user.student
            except User.DoesNotExist:
                return JsonResponse({'success': False, 'message': f'Пользователь {username} не найден'})
        else:
            return JsonResponse({'success': False, 'message': 'Не предоставлены данные для идентификации студента'})
        
        # Получаем занятие
        try:
            class_obj = Class.objects.get(id=class_id)
        except Class.DoesNotExist:
            return JsonResponse({'success': False, 'message': f'Занятие с ID {class_id} не найдено'})
        
        # Проверяем, что студент записан на это занятие
        if not class_obj.students.filter(id=student.id).exists():
            return JsonResponse({
                'success': False, 
                'message': f'Студент {student.user.first_name} {student.user.last_name} не записан на это занятие'
            })
        
        # Получаем текущую дату
        current_date = timezone.now().date()
        
        # Проверяем, не отмечен ли уже студент на этом занятии сегодня
        existing_attendance = Attendance.objects.filter(
            student=student,
            class_schedule__class_obj=class_obj,
            date=current_date
        ).first()
        
        if existing_attendance:
            return JsonResponse({
                'success': False, 
                'message': f'Студент {student.user.first_name} {student.user.last_name} уже отмечен на этом занятии сегодня'
            })
        
        # Получаем расписание занятия на сегодня
        class_schedule = ClassSchedule.objects.filter(
            class_obj=class_obj,
            day_of_week=current_date.weekday()
        ).first()
        
        if not class_schedule:
            return JsonResponse({
                'success': False, 
                'message': f'Расписание для занятия {class_obj.subject.name} на сегодня не найдено'
            })
        
        # Создаем запись о посещаемости
        with transaction.atomic():
            attendance = Attendance.objects.create(
                student=student,
                class_schedule=class_schedule,
                date=current_date,
                status='present',
                marked_by=request.user
            )
            
            # Создаем запись о посещаемости по распознаванию лица
            face_attendance = FaceAttendance.objects.create(
                attendance=attendance,
                confidence=confidence,
                marked_by=request.user
            )
            
            # Логируем отметку посещаемости
            logger.info(
                f"Отмечено посещение: Студент {student.user.username}, "
                f"Занятие {class_obj.subject.name}, "
                f"Дата {current_date}, "
                f"Отметил {request.user.username}, "
                f"Уверенность {confidence}"
            )
        
        return JsonResponse({
            'success': True, 
            'message': f'Посещение для студента {student.user.first_name} {student.user.last_name} успешно отмечено',
            'attendance_id': attendance.id
        })
    
    except Exception as e:
        logger.error(f"Ошибка при отметке посещаемости: {e}")
        return JsonResponse({'success': False, 'message': f'Произошла ошибка: {str(e)}'})

@login_required
def get_active_classes(request):
    """API для получения списка активных занятий"""
    # Проверяем права доступа
    if not (request.user.is_admin or request.user.is_teacher or request.user.is_reception):
        return JsonResponse({'success': False, 'message': 'У вас нет прав для получения списка занятий'})
    
    try:
        # Получаем student_id из параметров запроса
        student_id = request.GET.get('student_id')
        student_username = request.GET.get('username')
        
        # Получаем текущую дату и время
        current_date = timezone.now().date()
        current_time = timezone.now().time()
        current_weekday = current_date.weekday()
        
        # Получаем расписание занятий на сегодня
        class_schedules = ClassSchedule.objects.filter(
            day_of_week=current_weekday,
            is_active=True
        )
        
        # Если указан student_id или username, фильтруем занятия только для этого студента
        student = None
        if student_id:
            try:
                student = Student.objects.get(id=student_id)
            except Student.DoesNotExist:
                logger.warning(f"Студент с ID {student_id} не найден")
        elif student_username:
            try:
                student = Student.objects.get(user__username=student_username)
            except Student.DoesNotExist:
                logger.warning(f"Студент с именем пользователя {student_username} не найден")
        
        # Фильтруем занятия
        active_classes = []
        for schedule in class_schedules:
            # Получаем информацию о занятии
            class_obj = schedule.class_obj
            
            # Если указан студент, проверяем, что он записан на этот класс
            if student:
                # Проверяем, что студент записан на этот класс
                enrollment_exists = Enrollment.objects.filter(
                    student=student,
                    class_obj=class_obj,
                    is_active=True
                ).exists()
                
                # Если студент не записан на этот класс, пропускаем его
                if not enrollment_exists:
                    continue
            
            active_classes.append({
                'id': class_obj.id,
                'subject_name': class_obj.subject.name,
                'teacher': f"{class_obj.teacher.user.first_name} {class_obj.teacher.user.last_name}",
                'start_time': schedule.start_time.strftime('%H:%M'),
                'end_time': schedule.end_time.strftime('%H:%M'),
                'room': schedule.room
            })
        
        return JsonResponse(active_classes, safe=False)
    
    except Exception as e:
        logger.error(f"Ошибка при получении списка активных занятий: {e}")
        return JsonResponse({'success': False, 'message': f'Произошла ошибка: {str(e)}'})

