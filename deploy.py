"""
Скрипт для подготовки и развертывания проекта на Hostinger
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def generate_secret_key():
    """Генерирует новый секретный ключ для Django"""
    import random
    import string
    
    chars = string.ascii_letters + string.digits + '!@#$%^&*(-_=+)'
    return ''.join(random.choice(chars) for _ in range(50))

def update_env_file():
    """Обновляет файл .env с правильными настройками"""
    print("Обновление файла .env...")
    
    try:
        # Проверяем существование файла .env
        env_path = Path('.env')
        if not env_path.exists():
            print("Файл .env не найден. Создаем новый файл.")
            
            # Создаем новый файл .env
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(f"""# Настройки Django
SECRET_KEY={generate_secret_key()}
DEBUG=False
ALLOWED_HOSTS=aqylgym.com,www.aqylgym.com

# Настройки базы данных MySQL
DB_ENGINE=django.db.backends.mysql
DB_NAME=u24689283_load_okucenter
DB_USER=u24689283_dulat_orynbek
DB_PASSWORD=input_your_password_here
DB_HOST=localhost
DB_PORT=3306

# Настройки электронной почты (если используются)
EMAIL_HOST=smtp.your-email-provider.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@example.com
EMAIL_HOST_PASSWORD=your_email_password
EMAIL_USE_TLS=True
""")
            print("Файл .env создан. Пожалуйста, обновите пароль базы данных и другие настройки.")
        else:
            print("Файл .env уже существует. Проверьте настройки вручную.")
        
        return True
    
    except Exception as e:
        print(f"Ошибка при обновлении файла .env: {e}")
        return False

def install_dependencies():
    """Устанавливает необходимые зависимости"""
    print("Установка зависимостей...")
    
    try:
        # Проверяем существование файла requirements.txt
        req_path = Path('requirements.txt')
        if not req_path.exists():
            print("Файл requirements.txt не найден.")
            return False
        
        # Устанавливаем зависимости
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Ошибка при установке зависимостей: {result.stderr}")
            return False
        
        print("Зависимости успешно установлены")
        return True
    
    except Exception as e:
        print(f"Ошибка при установке зависимостей: {e}")
        return False

def collect_static_files():
    """Собирает статические файлы"""
    print("Сбор статических файлов...")
    
    try:
        # Проверяем существование директории для статических файлов
        static_dir = Path('staticfiles')
        if not static_dir.exists():
            static_dir.mkdir(exist_ok=True)
        
        # Запускаем сбор статических файлов
        result = subprocess.run(
            [sys.executable, 'manage.py', 'collectstatic', '--noinput'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Ошибка при сборе статических файлов: {result.stderr}")
            return False
        
        print("Статические файлы успешно собраны")
        return True
    
    except Exception as e:
        print(f"Ошибка при сборе статических файлов: {e}")
        return False

def run_migrations():
    """Выполняет миграции базы данных"""
    print("Выполнение миграций базы данных...")
    
    try:
        # Запускаем миграции
        result = subprocess.run(
            [sys.executable, 'manage.py', 'migrate'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Ошибка при выполнении миграций: {result.stderr}")
            return False
        
        print("Миграции успешно выполнены")
        return True
    
    except Exception as e:
        print(f"Ошибка при выполнении миграций: {e}")
        return False

def create_backup_directory():
    """Создает директорию для резервных копий"""
    print("Создание директории для резервных копий...")
    
    try:
        backup_dir = Path('backups')
        backup_dir.mkdir(exist_ok=True)
        
        print("Директория для резервных копий создана")
        return True
    
    except Exception as e:
        print(f"Ошибка при создании директории для резервных копий: {e}")
        return False

def create_logs_directory():
    """Создает директорию для логов"""
    print("Создание директории для логов...")
    
    try:
        logs_dir = Path('logs')
        logs_dir.mkdir(exist_ok=True)
        
        print("Директория для логов создана")
        return True
    
    except Exception as e:
        print(f"Ошибка при создании директории для логов: {e}")
        return False

def main():
    """Основная функция для подготовки проекта к развертыванию"""
    print("Начинаем подготовку проекта к развертыванию на Hostinger...")
    
    # Шаг 1: Обновление файла .env
    if not update_env_file():
        print("Не удалось обновить файл .env. Подготовка прервана.")
        return
    
    # Шаг 2: Установка зависимостей
    if not install_dependencies():
        print("Не удалось установить зависимости. Подготовка прервана.")
        return
    
    # Шаг 3: Создание директории для логов
    if not create_logs_directory():
        print("Не удалось создать директорию для логов. Подготовка прервана.")
        return
    
    # Шаг 4: Создание директории для резервных копий
    if not create_backup_directory():
        print("Не удалось создать директорию для резервных копий. Подготовка прервана.")
        return
    
    # Шаг 5: Выполнение миграций
    if not run_migrations():
        print("Не удалось выполнить миграции. Подготовка прервана.")
        return
    
    # Шаг 6: Сбор статических файлов
    if not collect_static_files():
        print("Не удалось собрать статические файлы. Подготовка прервана.")
        return
    
    print("\nПроект успешно подготовлен к развертыванию на Hostinger!")
    print("\nСледующие шаги:")
    print("1. Загрузите файлы проекта на сервер Hostinger через FTP или Git")
    print("2. Настройте виртуальное окружение на сервере")
    print("3. Установите зависимости на сервере: pip install -r requirements.txt")
    print("4. Настройте Gunicorn и Nginx согласно инструкции в DEPLOYMENT.md")
    print("5. Запустите приложение: gunicorn -c gunicorn_config.py okucenter.wsgi:application")

if __name__ == "__main__":
    main()
