from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import logging
import base64
import numpy as np

# Импортируем утилиты для работы с FaceNet
from .facenet_utils import process_base64_image, compare_faces, FACENET_THRESHOLD, recognize_face

logger = logging.getLogger(__name__)

def test_facenet(request):
    """
    Тестовая страница для проверки работы модели FaceNet
    """
    return render(request, 'face_recognition/test_facenet_fixed.html')

@csrf_exempt
def test_compare_faces(request):
    """
    Тестовый API для сравнения двух лиц
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Метод не поддерживается'})
    
    # Получаем данные изображений из запроса
    try:
        data = json.loads(request.body)
        face1_data = data.get('face1_data')
        face2_data = data.get('face2_data')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Неверный формат JSON'})
    
    if not face1_data or not face2_data:
        return JsonResponse({'success': False, 'message': 'Данные изображений не предоставлены'})
    
    # Обрабатываем изображения
    face1_embedding, error1 = process_base64_image(face1_data)
    if error1:
        return JsonResponse({'success': False, 'message': f'Ошибка обработки первого изображения: {error1}'})
    
    face2_embedding, error2 = process_base64_image(face2_data)
    if error2:
        return JsonResponse({'success': False, 'message': f'Ошибка обработки второго изображения: {error2}'})
    
    # Сравниваем лица
    similarity = compare_faces(face1_embedding, face2_embedding)
    
    # Формируем ответ
    return JsonResponse({
        'success': True,
        'similarity': float(similarity),
        'is_same_person': similarity >= FACENET_THRESHOLD,
        'threshold': FACENET_THRESHOLD
    })

@csrf_exempt
def test_recognize_face(request):
    """
    Тестовый API для распознавания лица
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Метод не поддерживается'})
    
    # Получаем данные изображения из запроса
    # Пробуем получить данные из разных источников
    face_data = request.POST.get('face_data')
    
    # Если данных нет в POST, пробуем получить их из тела запроса
    if not face_data and request.body:
        try:
            # Пробуем парсить тело запроса как JSON
            body_data = json.loads(request.body)
            face_data = body_data.get('face_data')
            print(f"Получены данные из JSON тела запроса")
        except json.JSONDecodeError:
            print(f"Не удалось парсить тело запроса как JSON")
            pass
    
    if not face_data:
        print("Данные изображения не предоставлены")
        return JsonResponse({'success': False, 'message': 'Данные изображения не предоставлены'})
    
    # Добавляем отладочную информацию о пользователях с зарегистрированными лицами
    from accounts.models import User
    users_with_faces = User.objects.exclude(face_id_data__isnull=True).exclude(face_id_data="")
    print(f"Найдено пользователей с зарегистрированными лицами: {users_with_faces.count()}")
    
    # Выводим информацию о каждом пользователе с зарегистрированным лицом
    for user in users_with_faces:
        print(f"\tПользователь: {user.username}, Тип: {user.user_type}, Длина данных лица: {len(user.face_id_data)}")
    
    # Проверяем формат данных лица у первого пользователя
    if users_with_faces.exists():
        first_user = users_with_faces.first()
        print(f"\tПроверка формата данных лица для {first_user.username}:")
        print(f"\tНачало данных: {first_user.face_id_data[:100]}...")
        
        # Проверяем декодирование эмбеддинга
        from .facenet_utils import decode_face_data
        embedding = decode_face_data(first_user.face_id_data)
        if embedding is not None:
            print(f"\tУспешно декодирован эмбеддинг длиной {len(embedding)}, первые 5 значений: {embedding[:5]}")
        else:
            print("\tОшибка при декодировании эмбеддинга!")
    
    # Проверяем текущий порог распознавания
    from .facenet_utils import FACENET_THRESHOLD
    print(f"\tТекущий порог распознавания: {FACENET_THRESHOLD}")
    
    # Распознаем лицо с возвратом всех сходств
    try:
        # Вызываем функцию распознавания лица с параметром return_all_scores=True
        success, user, error, confidence, all_similarities = recognize_face(face_data, request, return_all_scores=True)
        
        # Создаем список всех пользователей с их сходством
        user_scores = []
        if all_similarities:
            for user_data, score in all_similarities:
                user_scores.append({
                    'username': user_data.username,
                    'user_type': user_data.user_type,
                    'confidence': round(float(score) * 100, 2)  # Преобразуем в проценты и округляем
                })
            
            # Сортируем по убыванию сходства
            user_scores.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Формируем ответ
        if success and user:
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
                'confidence': confidence,
                'confidence_percent': round(confidence * 100, 2),
                'user_scores': user_scores,
                'threshold': FACENET_THRESHOLD,
                'threshold_percent': round(FACENET_THRESHOLD * 100, 2)
            })
        else:
            return JsonResponse({
                'success': False, 
                'message': error or 'Лицо не распознано',
                'user_scores': user_scores,
                'threshold': FACENET_THRESHOLD,
                'threshold_percent': round(FACENET_THRESHOLD * 100, 2)
            })
    except Exception as e:
        print(f"Ошибка при вызове recognize_face: {str(e)}")
        return JsonResponse({'success': False, 'message': f"Произошла ошибка при распознавании лица: {str(e)}"})
