#!/usr/bin/env python
"""
Скрипт для проверки данных лица в базе данных и диагностики проблем с распознаванием.
"""

import os
import sys
import django
import logging
import argparse

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Настраиваем Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')
django.setup()

from face_recognition_app.facenet_utils import check_face_data, process_base64_image
from accounts.models import User

def main():
    parser = argparse.ArgumentParser(description='Проверка данных лица в базе данных')
    parser.add_argument('--username', help='Имя пользователя для проверки (опционально)')
    parser.add_argument('--verbose', action='store_true', help='Подробный вывод')
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("Используемый алгоритм распознавания лиц: FaceNet")
    
    # Проверяем данные лица
    success, results = check_face_data(args.username)
    
    if not success:
        print(f"Ошибка: {results}")
        return
    
    print(f"Найдено пользователей с данными лица: {len(results)}")
    
    # Выводим результаты проверки
    for result in results:
        status_icon = "✅" if result['status'] == 'ok' else "⚠️" if result['status'] == 'warning' else "❌"
        print(f"{status_icon} {result['username']}: {result['message']}")
    
    # Проверяем, есть ли проблемные записи
    problem_users = [r for r in results if r['status'] != 'ok']
    if problem_users:
        print("\nОбнаружены проблемы с данными лица следующих пользователей:")
        for user in problem_users:
            print(f"- {user['username']}: {user['message']}")
        
        print("\nВозможные решения:")
        print("1. Перерегистрируйте лица этих пользователей")
        print("2. Убедитесь, что используется FaceNet для распознавания лиц")
    else:
        print("\nВсе данные лиц корректны.")
    
    # Если указан конкретный пользователь, выводим дополнительную информацию
    if args.username and results:
        user = User.objects.filter(username=args.username).first()
        if user and user.face_id_data:
            print(f"\nДополнительная информация о пользователе {user.username}:")
            print(f"Имя: {user.first_name} {user.last_name}")
            print(f"Email: {user.email}")
            print(f"Активен: {'Да' if user.is_active else 'Нет'}")
            print(f"Размер данных лица: {len(user.face_id_data)} байт")

if __name__ == "__main__":
    main()
