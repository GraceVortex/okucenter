from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from accounts.models import User
import json
import logging
from .facenet_utils import register_face, process_base64_image

logger = logging.getLogger(__name__)

@login_required
def register_student_face(request):
    """
    Страница для регистрации лица ученика.
    """
    # Проверяем, что пользователь имеет права для регистрации лиц
    if not (request.user.is_admin or request.user.is_reception or request.user.is_superuser):
        return redirect('core:home')
    
    # Получаем список всех пользователей с ролью студента
    students = User.objects.filter(is_student=True).order_by('last_name', 'first_name')
    
    context = {
        'students': students,
        'use_facenet': True
    }
    
    return render(request, 'face_recognition/register_student_face.html', context)

@login_required
@csrf_exempt
def api_register_student_face(request):
    """
    API для регистрации лица ученика.
    """
    # Проверяем, что пользователь имеет права для регистрации лиц
    if not (request.user.is_admin or request.user.is_reception or request.user.is_superuser):
        return JsonResponse({
            'success': False,
            'message': 'У вас нет прав для регистрации лиц'
        })
    
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Метод не поддерживается'
        })
    
    try:
        # Получаем данные из запроса
        data = json.loads(request.body)
        user_id = data.get('user_id')
        face_data = data.get('face_data')
        
        if not user_id:
            return JsonResponse({
                'success': False,
                'message': 'Не указан ID пользователя'
            })
        
        if not face_data:
            return JsonResponse({
                'success': False,
                'message': 'Данные изображения не предоставлены'
            })
        
        # Получаем пользователя по ID
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Пользователь не найден'
            })
        
        # Проверяем, что пользователь является учеником
        if not hasattr(user, 'student_profile'):
            return JsonResponse({
                'success': False,
                'message': 'Выбранный пользователь не является учеником'
            })
        
        # Регистрируем лицо
        success, message = register_face(user, face_data)
        
        # Логируем результат
        if success:
            logger.info(f"Лицо ученика {user.username} успешно зарегистрировано")
        else:
            logger.error(f"Ошибка при регистрации лица ученика {user.username}: {message}")
        
        return JsonResponse({
            'success': success,
            'message': message
        })
    
    except Exception as e:
        logger.error(f"Ошибка при регистрации лица ученика: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Произошла ошибка: {str(e)}'
        })
