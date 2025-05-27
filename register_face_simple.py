#!/usr/bin/env python
"""
Скрипт для прямой регистрации лица пользователя в базе данных.
Использование:
    python register_face_simple.py <username>
"""

import os
import sys
import django
import logging
import json
import numpy as np

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Настраиваем Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')
django.setup()

from accounts.models import User
from face_recognition_app.facenet_utils import encode_face_data

def main():
    if len(sys.argv) != 2:
        print("Использование: python register_face_simple.py <username>")
        sys.exit(1)
    
    username = sys.argv[1]
    
    # Проверяем, что пользователь существует
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        print(f"Пользователь с именем {username} не найден")
        sys.exit(1)
    
    print("Используемый алгоритм распознавания лиц: FaceNet")
    print(f"Регистрация лица для пользователя: {user.username} ({user.first_name} {user.last_name})")
    
    # Создаем тестовые данные для лица
    # Создаем вектор эмбеддингов размерности 512 для FaceNet
    face_features = np.random.rand(512).astype(np.float32)
    print("Создан тестовый вектор эмбеддингов FaceNet размерности 512")
    
    # Кодируем данные лица
    face_id_data = encode_face_data(face_features)
    
    # Сохраняем данные лица в базе данных
    user.face_id_data = face_id_data
    user.save()
    
    print(f"Данные лица успешно сохранены в базе данных")
    print(f"Размер данных лица: {len(user.face_id_data)} байт")

if __name__ == "__main__":
    main()
