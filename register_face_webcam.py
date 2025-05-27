#!/usr/bin/env python
"""
Скрипт для регистрации лица пользователя с использованием веб-камеры.
Использование:
    python register_face_webcam.py <username>
"""

import os
import sys
import django
import base64
import logging
import cv2
import time
import numpy as np
from io import BytesIO
from PIL import Image

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
    if len(sys.argv) != 2:
        print("Использование: python register_face_webcam.py <username>")
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
    print("Инициализация камеры...")
    
    # Инициализируем камеру
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Ошибка: Не удалось получить доступ к камере")
        sys.exit(1)
    
    # Загружаем каскад Хаара для обнаружения лиц
    cascade_path = os.path.join(cv2.__path__[0], 'data', 'haarcascade_frontalface_default.xml')
    face_cascade = cv2.CascadeClassifier(cascade_path)
    
    if face_cascade.empty():
        print(f"Ошибка: Не удалось загрузить каскад Хаара из {cascade_path}")
        sys.exit(1)
    
    print("Камера инициализирована. Нажмите ПРОБЕЛ, чтобы сделать снимок, или ESC для выхода.")
    
    while True:
        # Захватываем кадр с камеры
        ret, frame = cap.read()
        if not ret:
            print("Ошибка: Не удалось получить кадр с камеры")
            break
        
        # Конвертируем в оттенки серого для обнаружения лиц
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Обнаруживаем лица
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        
        # Рисуем прямоугольник вокруг лица
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
        
        # Отображаем кадр
        cv2.imshow('Регистрация лица', frame)
        
        # Обрабатываем нажатия клавиш
        key = cv2.waitKey(1)
        if key == 27:  # ESC
            print("Отмена регистрации")
            break
        elif key == 32:  # ПРОБЕЛ
            if len(faces) == 0:
                print("Лицо не обнаружено. Пожалуйста, убедитесь, что ваше лицо видно на камере.")
                continue
            elif len(faces) > 1:
                print("Обнаружено более одного лица. Пожалуйста, убедитесь, что на камере видно только ваше лицо.")
                continue
            
            print("Снимок сделан. Обработка изображения...")
            
            # Конвертируем изображение в формат base64
            _, buffer = cv2.imencode('.jpg', frame)
            base64_image = base64.b64encode(buffer).decode('utf-8')
            
            # Регистрируем лицо
            success, message = register_face(user, base64_image)
            
            if success:
                print(f"Лицо успешно зарегистрировано: {message}")
                print(f"Размер данных лица: {len(user.face_id_data)} байт")
                break
            else:
                print(f"Ошибка при регистрации лица: {message}")
                print("Пожалуйста, попробуйте еще раз или нажмите ESC для выхода.")
    
    # Освобождаем ресурсы
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
