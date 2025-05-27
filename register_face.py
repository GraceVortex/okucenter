#!/usr/bin/env python
"""
Скрипт для регистрации лица пользователя напрямую из файла изображения.
Использование:
    python register_face.py <username> <путь_к_изображению>
"""

import os
import sys
import django
import base64
import logging

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Настраиваем Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')
django.setup()

from accounts.models import User
from face_recognition_app.facenet_utils import register_face

def main():
    if len(sys.argv) != 3:
        print("Использование: python register_face.py <username> <путь_к_изображению>")
        sys.exit(1)
    
    username = sys.argv[1]
    image_path = sys.argv[2]
    
    # Проверяем, что пользователь существует
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        print(f"Пользователь с именем {username} не найден")
        sys.exit(1)
    
    # Проверяем, что файл изображения существует
    if not os.path.exists(image_path):
        print(f"Файл {image_path} не найден")
        sys.exit(1)
    
    # Читаем изображение и конвертируем в base64
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
        base64_image = base64.b64encode(image_data).decode('utf-8')
    except Exception as e:
        print(f"Ошибка при чтении изображения: {e}")
        sys.exit(1)
    
    print("Используемый алгоритм распознавания лиц: FaceNet")
    print(f"Регистрация лица для пользователя: {user.username} ({user.first_name} {user.last_name})")
    
    # Регистрируем лицо
    success, message = register_face(user, base64_image)
    
    if success:
        print(f"Лицо успешно зарегистрировано: {message}")
        print(f"Размер данных лица: {len(user.face_id_data)} байт")
    else:
        print(f"Ошибка при регистрации лица: {message}")

if __name__ == "__main__":
    main()
