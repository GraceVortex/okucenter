"""
Скрипт для сбора статических файлов
"""

import os
import subprocess
import sys

def collect_static():
    """Собирает статические файлы для продакшена"""
    try:
        # Устанавливаем переменную окружения для Django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')
        
        # Запускаем команду collectstatic с флагом --noinput
        result = subprocess.run(
            [sys.executable, 'manage.py', 'collectstatic', '--noinput'],
            capture_output=True,
            text=True
        )
        
        # Выводим результат
        print(result.stdout)
        
        if result.returncode != 0:
            print(f"Ошибка: {result.stderr}")
            return False
        
        return True
    
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        return False

if __name__ == "__main__":
    print("Начинаем сбор статических файлов...")
    success = collect_static()
    
    if success:
        print("Статические файлы успешно собраны!")
    else:
        print("Не удалось собрать статические файлы.")
