"""
Представления для распознавания лиц с использованием FaceNet
"""

import logging
import json
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required

# Настраиваем логгер
logger = logging.getLogger(__name__)

@login_required
def facenet_compare(request):
    """Страница для сравнения двух фотографий лиц с использованием FaceNet"""
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
            from .facenet_utils import process_base64_image, compare_faces
            
            # Получаем эмбеддинги лиц из изображений
            benchmark_features, benchmark_error = process_base64_image(benchmark_image)
            
            if benchmark_error:
                return JsonResponse({'success': False, 'message': f'Ошибка обработки эталонного изображения: {benchmark_error}'})
            
            check_features, check_error = process_base64_image(check_image)
            
            if check_error:
                return JsonResponse({'success': False, 'message': f'Ошибка обработки проверочного изображения: {check_error}'})
            
            # Используем функцию compare_faces из facenet_utils для сравнения лиц
            is_match, confidence = compare_faces(benchmark_features, check_features, threshold)
            
            # Логируем результат
            logger.info(f"Результат сравнения лиц с FaceNet: Совпадение={is_match}, Уверенность={confidence:.2f}")
            
            return JsonResponse({
                'success': True,
                'match': is_match,
                'confidence': float(confidence),
                'threshold': float(threshold),
                'model': 'FaceNet'  # Указываем, что использовалась модель FaceNet
            })
                
        except Exception as e:
            logger.error(f"Ошибка при сравнении лиц с FaceNet: {e}")
            return JsonResponse({'success': False, 'message': f'Произошла ошибка: {str(e)}'})
    
    # Для GET-запроса отображаем страницу сравнения
    return render(request, 'face_recognition/simple_face_compare.html')
