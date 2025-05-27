import logging
import os

# Настраиваем логгер
logger = logging.getLogger(__name__)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from django.conf import settings
import json

from accounts.models import User, Student, Teacher
from classes.models import Class, ClassSchedule
from attendance.models import Attendance
from .models import FaceRecognitionLog, FaceAttendance
from .forms import FaceRegistrationForm, FaceAttendanceForm
import base64
from io import BytesIO
from PIL import Image
import numpy as np
# Импортируем функции из нового модуля facenet_utils вместо старого utils
# Импортируем все необходимые функции из facenet_utils
from .facenet_utils import register_face, recognize_face, process_base64_image, compare_faces, FACENET_THRESHOLD
logger.info("Используем улучшенное распознавание лиц с FaceNet")

@login_required
def face_registration(request):
    """Страница для регистрации лица пользователя"""
    # Проверяем права доступа - только администраторы могут регистрировать лица
    if not request.user.is_admin and not request.user.is_reception:
        return HttpResponseForbidden("У вас нет прав для регистрации лиц пользователей")
    
    form = FaceRegistrationForm(request.POST or None)
    
    if request.method == 'POST' and form.is_valid():
        user = form.cleaned_data.get('user')
        face_data = form.cleaned_data.get('face_data')
        
        if user and face_data:
            success, message = register_face(user, face_data)
            
            if success:
                messages.success(request, message)
                return redirect('face_recognition:face_registration')
            else:
                messages.error(request, message)
    
    # Получаем пользователей, у которых уже зарегистрированы лица
    users_with_faces = User.objects.exclude(face_id_data__isnull=True).exclude(face_id_data="")
    
    context = {
        'form': form,
        'users_with_faces': users_with_faces
    }
    
    return render(request, 'face_recognition/face_registration.html', context)

@login_required
def face_attendance(request):
    """Страница для отметки посещаемости через распознавание лиц"""
    # Проверяем права доступа
    if not (request.user.is_admin or request.user.is_reception or request.user.is_teacher):
        return HttpResponseForbidden("У вас нет прав для отметки посещаемости")
    
    # Получаем текущую дату
    today = timezone.now().date()
    
    # В простом варианте не будем создавать файлы, чтобы избежать ошибок с правами доступа
    
    context = {
        'today': today
    }
    
    return render(request, 'face_recognition/face_attendance.html', context)

@login_required
def api_recognize_face(request):
    """API для распознавания лица"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Метод не поддерживается'})
    
    # Получаем данные изображения из запроса
    face_data = request.POST.get('face_data')
    
    if not face_data:
        return JsonResponse({'success': False, 'message': 'Данные изображения не предоставлены'})
    
    # Распознаем лицо
    try:
        # Добавляем логирование для отладки
        logger.info(f"Начинаем распознавание лица в api_recognize_face. Длина данных: {len(face_data)}")
        
        # Вызываем функцию распознавания лица
        success, user, error, confidence = recognize_face(face_data, request)
        
        # Логируем результат
        logger.info(f"Результат распознавания: success={success}, user={user.username if user else None}, error={error}, confidence={confidence}")
    except Exception as e:
        logger.error(f"Ошибка при вызове recognize_face: {str(e)}")
        return JsonResponse({'success': False, 'message': f"Произошла ошибка при распознавании лица: {str(e)}"})    
    
    if error:
        logger.warning(f"Ошибка распознавания: {error}")
        return JsonResponse({'success': False, 'message': error})
    
    if user:
        # Проверяем, является ли пользователь студентом
        is_student = hasattr(user, 'student_profile')
        student_id = user.student_profile.id if is_student else None
        
        return JsonResponse({
            'success': True,
            'user_id': user.id,
            'username': user.username,
            'full_name': user.get_full_name(),
            'user_type': user.user_type,
            'is_student': is_student,
            'student_id': student_id,
            'confidence': confidence
        })
    else:
        return JsonResponse({'success': False, 'message': 'Лицо не распознано'})

@login_required
def api_mark_attendance(request):
    """API для отметки посещаемости через распознавание лиц"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Метод не поддерживается'})
    
    # Получаем данные из запроса
    student_id = request.POST.get('student_id')
    class_id = request.POST.get('class_id')
    face_data = request.POST.get('face_data')
    date_str = request.POST.get('date')
    teacher_id = request.POST.get('teacher_id')
    
    if not all([student_id, class_id, face_data]):
        return JsonResponse({'success': False, 'message': 'Не все данные предоставлены'})
    
    try:
        student = Student.objects.get(id=student_id)
        class_obj = Class.objects.get(id=class_id)
        
        # Определяем дату
        if date_str:
            try:
                date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'success': False, 'message': 'Неверный формат даты'})
        else:
            date = timezone.now().date()
        
        # Если указан учитель, проверяем, что он ведет этот класс
        if teacher_id and request.user.is_reception:
            try:
                teacher = Teacher.objects.get(id=teacher_id)
                # Если учитель не соответствует классу, проверяем
                if class_obj.teacher.id != teacher.id:
                    return JsonResponse({'success': False, 'message': 'Выбранный учитель не ведет этот класс'})
            except Teacher.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Учитель не найден'})
        
        # Отмечаем посещаемость с использованием обновленной функции
        with transaction.atomic():
            success, message = mark_attendance_by_face(student, class_obj, face_data, request, date)
            
            if success:
                return JsonResponse({'success': True, 'message': message})
            else:
                return JsonResponse({'success': False, 'message': message})
    
    except (Student.DoesNotExist, Class.DoesNotExist) as e:
        return JsonResponse({'success': False, 'message': f'Объект не найден: {str(e)}'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка: {str(e)}'})

@login_required
def face_recognition_logs(request):
    """Страница для просмотра логов распознавания лиц"""
    # Проверяем права доступа - только администраторы могут просматривать логи
    if not request.user.is_admin:
        return HttpResponseForbidden("У вас нет прав для просмотра логов распознавания лиц")
    
    # Получаем логи распознавания лиц
    logs = FaceRecognitionLog.objects.all().select_related('user')
    
    context = {
        'logs': logs
    }
    
    return render(request, 'face_recognition/logs.html', context)

@login_required
def face_attendance_list(request):
    """Страница для просмотра отметок посещаемости через распознавание лиц"""
    # Проверяем права доступа
    if not (request.user.is_admin or request.user.is_reception or request.user.is_teacher):
        return HttpResponseForbidden("У вас нет прав для просмотра отметок посещаемости")
    
    # Получаем отметки посещаемости через распознавание лиц
    if request.user.is_admin or request.user.is_reception:
        face_attendances = FaceAttendance.objects.all().select_related('attendance__student', 'attendance__class_obj')
    elif request.user.is_teacher:
        teacher = get_object_or_404(Teacher, user=request.user)
        face_attendances = FaceAttendance.objects.filter(
            attendance__class_obj__teacher=teacher
        ).select_related('attendance__student', 'attendance__class_obj')
    
    context = {
        'face_attendances': face_attendances
    }
    
    return render(request, 'face_recognition/face_attendance_list.html', context)

@login_required
def api_get_class_dates(request):
    """API для получения доступных дат для класса на основе расписания"""
    class_id = request.GET.get('class_id')
    
    if not class_id:
        return JsonResponse({'success': False, 'message': 'Не указан ID класса'})
    
    try:
        class_obj = Class.objects.get(id=class_id)
        
        # Получаем расписание для класса
        schedules = ClassSchedule.objects.filter(class_obj=class_obj)
        
        if not schedules.exists():
            return JsonResponse({'success': False, 'message': 'Для этого класса нет расписания'})
        
        # Получаем текущую дату
        today = timezone.now().date()
        
        # Создаем список дат на ближайшие 30 дней на основе расписания
        dates = []
        
        # Словарь для преобразования номера дня недели в строковое представление
        day_map = {
            0: 'monday',
            1: 'tuesday',
            2: 'wednesday',
            3: 'thursday',
            4: 'friday',
            5: 'saturday',
            6: 'sunday',
        }
        
        # Получаем дни недели, в которые проходят занятия
        class_days = [schedule.day_of_week for schedule in schedules]
        
        # Генерируем даты на ближайшие 30 дней
        for i in range(30):
            date = today + timezone.timedelta(days=i)
            # Проверяем, соответствует ли день недели расписанию
            if date.weekday() in class_days:
                # Добавляем дату в список
                dates.append({
                    'date': date.isoformat(),
                    'formatted_date': date.strftime('%d.%m.%Y'),
                    'day_of_week': day_map[date.weekday()],
                    'schedules': [
                        {
                            'id': schedule.id,
                            'start_time': schedule.start_time.strftime('%H:%M'),
                            'end_time': schedule.end_time.strftime('%H:%M'),
                            'room': schedule.room
                        }
                        for schedule in schedules if schedule.day_of_week == date.weekday()
                    ]
                })
        
        return JsonResponse({
            'success': True,
            'dates': dates
        })
    
    except Class.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Класс не найден'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка: {str(e)}'})


@login_required
def test_recognition(request):
    """Страница для тестирования распознавания лиц с расширенной отладочной информацией"""
    # Проверяем права доступа - только администраторы и ресепшн могут тестировать распознавание
    if not request.user.is_admin and not request.user.is_reception:
        return HttpResponseForbidden("У вас нет прав для тестирования распознавания лиц")
    
    if request.method == 'POST':
        try:
            # Получаем данные из запроса JSON
            data = json.loads(request.body)
            face_data = data.get('face_data')
            threshold = float(data.get('threshold', 0.7))  # Получаем пользовательский порог уверенности
            
            if not face_data:
                return JsonResponse({'success': False, 'message': 'Данные изображения не предоставлены'})
            
            # Временно изменяем порог уверенности для этого запроса
            from .utils import FACE_RECOGNITION_THRESHOLD
            original_threshold = FACE_RECOGNITION_THRESHOLD
            
            # Устанавливаем пользовательский порог
            import face_recognition_app.utils
            face_recognition_app.utils.FACE_RECOGNITION_THRESHOLD = threshold
            
            # Распознаем лицо
            success, user, error, confidence = recognize_face(face_data, request)
            
            # Возвращаем оригинальный порог
            face_recognition_app.utils.FACE_RECOGNITION_THRESHOLD = original_threshold
            
            if error:
                return JsonResponse({'success': False, 'message': error})
            
            if user:
                # Получаем дополнительную информацию о пользователе
                user_info = {
                    'id': user.id,
                    'username': user.username,
                    'full_name': user.get_full_name() if hasattr(user, 'get_full_name') else user.username,
                    'face_image': user.face_image.url if hasattr(user, 'face_image') and user.face_image else None
                }
                
                # Если пользователь - студент, добавляем дополнительную информацию
                if hasattr(user, 'student_profile'):
                    student = user.student_profile
                    user_info.update({
                        'is_student': True,
                        'student_id': student.id,
                        'current_grade': student.current_grade,
                        'school': student.school
                    })
                
                # Получаем последние логи распознавания для этого пользователя
                recent_logs = FaceRecognitionLog.objects.filter(user=user).order_by('-created_at')[:5]
                logs_info = [{
                    'timestamp': log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'success': log.success,
                    'confidence': log.confidence
                } for log in recent_logs]
                
                # Отладочная информация
                debug_info = {
                    'threshold_used': threshold,
                    'confidence_achieved': confidence,
                    'recognition_logs': logs_info,
                    'recognition_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                return JsonResponse({
                    'success': True,
                    'user': user_info,
                    'confidence': confidence,
                    'debug_info': debug_info
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Лицо не распознано',
                    'debug_info': {
                        'threshold_used': threshold,
                        'recognition_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                })
                
        except Exception as e:
            logger.error(f"Ошибка при тестировании распознавания лица: {e}")
            return JsonResponse({'success': False, 'message': f'Произошла ошибка: {str(e)}'})
    
    # Для GET-запроса отображаем страницу тестирования
    return render(request, 'face_recognition/test_recognition.html')


@login_required
def face_compare(request):
    """Страница для простого сравнения двух фотографий лиц"""
    # Проверяем права доступа - только администраторы и ресепшн могут сравнивать лица
    if not request.user.is_admin and not request.user.is_reception:
        return HttpResponseForbidden("У вас нет прав для сравнения лиц")
    
    if request.method == 'POST':
        try:
            # Получаем данные из запроса JSON
            data = json.loads(request.body)
            benchmark_image = data.get('benchmark_image')
            check_image = data.get('check_image')
            threshold = float(data.get('threshold', 0.7))  # Получаем пользовательский порог уверенности
            
            if not benchmark_image:
                return JsonResponse({'success': False, 'message': 'Эталонное изображение не предоставлено'})
            
            if not check_image:
                return JsonResponse({'success': False, 'message': 'Изображение для проверки не предоставлено'})
            
            # Обрабатываем оба изображения с помощью FaceNet
            benchmark_embedding, benchmark_error = process_base64_image(benchmark_image)
            
            if benchmark_embedding is None:
                return JsonResponse({'success': False, 'message': f'Ошибка обработки эталонного изображения: {benchmark_error}'})
            
            check_embedding, check_error = process_base64_image(check_image)
            
            if check_embedding is None:
                return JsonResponse({'success': False, 'message': f'Ошибка обработки проверочного изображения: {check_error}'})
            
            # Сравниваем изображения, используя FaceNet
            import numpy as np
            
            # Используем FaceNet для сравнения лиц
            # Вычисляем косинусное сходство между эмбеддингами
            is_match, similarity = compare_faces(benchmark_embedding, check_embedding, threshold)
            
            # Вычисляем процент сходства
            similarity_percent = similarity * 100
            
            # Определяем, является ли сходство достаточным для совпадения
            is_match = similarity >= threshold
            
            # Результаты сравнения уже готовы из FaceNet
            confidence = similarity
            
            # Логируем результаты сравнения
            logger.info(f"Сравнение лиц: сходство {similarity:.4f} ({similarity_percent:.2f}%), порог {threshold}, совпадение: {is_match}")
            
            return JsonResponse({
                'success': True,
                'match': is_match,
                'confidence': float(similarity),
                'threshold': float(threshold),
                'facenet_similarity': float(similarity)
            })
                
        except Exception as e:
            logger.error(f"Ошибка при сравнении лиц: {e}")
            return JsonResponse({'success': False, 'message': f'Произошла ошибка: {str(e)}'})
    
    # Для GET-запроса отображаем страницу сравнения
    return render(request, 'face_recognition/face_compare.html')


@login_required
def simple_face_compare(request):
    """Упрощенная страница для сравнения двух фотографий лиц"""
    # Проверяем права доступа - только администраторы и ресепшн могут сравнивать лица
    if not request.user.is_admin and not request.user.is_reception:
        return HttpResponseForbidden("У вас нет прав для сравнения лиц")
    
    if request.method == 'POST':
        try:
            # Получаем данные из запроса JSON
            data = json.loads(request.body)
            benchmark_image = data.get('benchmark_image')
            check_image = data.get('check_image')
            threshold = float(data.get('threshold', 0.7))  # Получаем пользовательский порог уверенности
            
            if not benchmark_image:
                return JsonResponse({'success': False, 'message': 'Эталонное изображение не предоставлено'})
            
            if not check_image:
                return JsonResponse({'success': False, 'message': 'Изображение для проверки не предоставлено'})
            
            # Обрабатываем оба изображения с помощью FaceNet
            benchmark_embedding, benchmark_error = process_base64_image(benchmark_image)
            
            if benchmark_embedding is None:
                return JsonResponse({'success': False, 'message': f'Ошибка обработки эталонного изображения: {benchmark_error}'})
            
            check_embedding, check_error = process_base64_image(check_image)
            
            if check_embedding is None:
                return JsonResponse({'success': False, 'message': f'Ошибка обработки проверочного изображения: {check_error}'})
            
            # Сравниваем изображения, используя FaceNet
            import numpy as np
            
            # Используем FaceNet для сравнения лиц
            # Вычисляем косинусное сходство между эмбеддингами
            is_match, similarity = compare_faces(benchmark_embedding, check_embedding, threshold)
            
            # Вычисляем процент сходства
            similarity_percent = similarity * 100
            
            # Определяем, является ли сходство достаточным для совпадения
            is_match = similarity >= threshold
            
            # Результаты сравнения уже готовы из FaceNet
            confidence = similarity
            
            # Логируем результаты сравнения
            logger.info(f"Сравнение лиц: сходство {similarity:.4f} ({similarity_percent:.2f}%), порог {threshold}, совпадение: {is_match}")
            
            return JsonResponse({
                'success': True,
                'match': is_match,
                'confidence': float(similarity),
                'threshold': float(threshold),
                'facenet_similarity': float(similarity)
            })
                
        except Exception as e:
            logger.error(f"Ошибка при сравнении лиц: {e}")
            return JsonResponse({'success': False, 'message': f'Произошла ошибка: {str(e)}'})
    
    # Для GET-запроса отображаем страницу сравнения
    return render(request, 'face_recognition/simple_face_compare.html')

@login_required
def test_face_recognition(request):
    """Тестовая страница для проверки алгоритма распознавания лиц"""
    # Проверяем права доступа - только администраторы и ресепшн могут тестировать распознавание лиц
    if not request.user.is_admin and not request.user.is_reception:
        return HttpResponseForbidden("У вас нет прав для тестирования распознавания лиц")
    
    # Результаты сравнения
    comparison_results = None
    debug_info = None
    
    if request.method == 'POST':
        try:
            # Получаем данные из запроса
            data = json.loads(request.body)
            reference_image = data.get('reference_image')
            test_image = data.get('test_image')
            
            if not reference_image or not test_image:
                return JsonResponse({'success': False, 'message': 'Оба изображения должны быть предоставлены'})
            
            # Обрабатываем изображения и получаем эмбеддинги лиц
            reference_embedding, reference_error = process_base64_image(reference_image)
            test_embedding, test_error = process_base64_image(test_image)
            
            # Проверяем наличие ошибок
            if reference_embedding is None:
                return JsonResponse({'success': False, 'message': f'Ошибка при обработке эталонного изображения: {reference_error}'})
            
            if test_embedding is None:
                return JsonResponse({'success': False, 'message': f'Ошибка при обработке тестового изображения: {test_error}'})
            
            # Сравниваем лица с разными порогами уверенности
            thresholds = [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
            results = []
            
            # Получаем результаты сравнения с текущим порогом
            is_match, similarity = compare_faces(reference_embedding, test_embedding, FACENET_THRESHOLD)
            
            # Добавляем результаты для разных порогов
            for threshold in thresholds:
                match_at_threshold = similarity >= threshold
                results.append({
                    'threshold': threshold,
                    'is_match': match_at_threshold,
                    'similarity': similarity,
                    'percentage': round(similarity * 100, 2)
                })
            
            # Создаем объект с результатами
            comparison_results = {
                'current_threshold': FACENET_THRESHOLD,
                'current_threshold_result': is_match,
                'similarity': similarity,
                'percentage': round(similarity * 100, 2),
                'results': results
            }
            
            # Добавляем отладочную информацию
            debug_info = {
                'reference_embedding_shape': reference_embedding.shape if reference_embedding is not None else None,
                'test_embedding_shape': test_embedding.shape if test_embedding is not None else None,
            }
            
            return JsonResponse({
                'success': True, 
                'comparison_results': comparison_results,
                'debug_info': debug_info
            })
                
        except Exception as e:
            logger.error(f"Ошибка при тестировании распознавания лиц: {e}")
            return JsonResponse({'success': False, 'message': f'Произошла ошибка: {str(e)}'})
    
    # Для GET-запроса отображаем тестовую страницу
    return render(request, 'face_recognition/test_face_recognition.html', {
        'current_threshold': FACENET_THRESHOLD,
        'current_threshold_percent': int(FACENET_THRESHOLD * 100)
    })
