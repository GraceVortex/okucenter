#!/usr/bin/env python
"""
Скрипт для проверки готовности проекта к деплою на Railway.
Проверяет наличие всех необходимых файлов и настроек.
"""

import os
import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def check_file_exists(filepath, required=True):
    """Проверяет наличие файла и выводит соответствующее сообщение."""
    exists = os.path.exists(filepath)
    status = "[OK]" if exists else "[FAIL]"
    if required and not exists:
        print(f"{status} {filepath} - Отсутствует (Критично)")
        return False
    elif not required and not exists:
        print(f"{status} {filepath} - отсутствует (некритично)")
        return True
    else:
        print(f"{status} {filepath} - найден")
        return True

def check_settings():
    """Проверяет настройки Django."""
    try:
        import django
        from django.conf import settings
        
        # Настраиваем Django для загрузки настроек
        sys.path.insert(0, str(BASE_DIR))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "okucenter.settings")
        django.setup()
        
        # Проверяем критичные настройки
        checks = {
            "DATABASE_URL поддержка": hasattr(settings, "DATABASES") and "default" in settings.DATABASES,
            "Whitenoise": "whitenoise.middleware.WhiteNoiseMiddleware" in settings.MIDDLEWARE,
            "Static files": hasattr(settings, "STATIC_ROOT") and hasattr(settings, "STATIC_URL"),
            "Allowed hosts": hasattr(settings, "ALLOWED_HOSTS") and settings.ALLOWED_HOSTS,
            "Debug setting": hasattr(settings, "DEBUG"),
            "Secret key": hasattr(settings, "SECRET_KEY") and settings.SECRET_KEY,
        }
        
        all_passed = True
        print("\nПроверка настроек Django:")
        for name, passed in checks.items():
            status = "[OK]" if passed else "[FAIL]"
            if not passed:
                all_passed = False
                print(f"{status} {name} - Проблема")
            else:
                print(f"{status} {name} - OK")
        
        return all_passed
    except Exception as e:
        print(f"Ошибка при проверке настроек Django: {e}")
        return False

def check_railway_json():
    """Проверяет содержимое railway.json."""
    railway_json_path = BASE_DIR / "railway.json"
    if not os.path.exists(railway_json_path):
        print("[FAIL] railway.json отсутствует")
        return False
    
    try:
        with open(railway_json_path, 'r') as f:
            config = json.load(f)
        
        required_keys = ["build", "deploy"]
        missing_keys = [key for key in required_keys if key not in config]
        
        if missing_keys:
            print(f"[FAIL] В railway.json отсутствуют ключи: {', '.join(missing_keys)}")
            return False
        
        if "startCommand" not in config.get("deploy", {}):
            print("[FAIL] В railway.json отсутствует startCommand")
            return False
        
        print("[OK] railway.json настроен правильно")
        return True
    except Exception as e:
        print(f"Ошибка при проверке railway.json: {e}")
        return False

def check_requirements():
    """Проверяет requirements.txt на наличие необходимых пакетов."""
    req_path = BASE_DIR / "requirements.txt"
    if not os.path.exists(req_path):
        print("[FAIL] requirements.txt отсутствует")
        return False
    
    try:
        with open(req_path, 'r') as f:
            requirements = f.read()
        
        required_packages = [
            "django", "gunicorn", "whitenoise", "dj-database-url", 
            "psycopg2-binary", "python-dotenv"
        ]
        
        missing_packages = []
        for package in required_packages:
            if package.lower() not in requirements.lower():
                missing_packages.append(package)
        
        if missing_packages:
            print(f"[FAIL] В requirements.txt отсутствуют пакеты: {', '.join(missing_packages)}")
            return False
        
        print("[OK] requirements.txt содержит все необходимые пакеты")
        return True
    except Exception as e:
        print(f"Ошибка при проверке requirements.txt: {e}")
        return False

def main():
    """Основная функция проверки."""
    print("=== Проверка готовности проекта к деплою на Railway ===\n")
    
    # Проверка наличия необходимых файлов
    print("Проверка наличия необходимых файлов:")
    files_check = True
    files_check &= check_file_exists(BASE_DIR / "Procfile", required=True)
    files_check &= check_file_exists(BASE_DIR / "runtime.txt", required=True)
    files_check &= check_file_exists(BASE_DIR / "railway.json", required=True)
    files_check &= check_file_exists(BASE_DIR / "requirements.txt", required=True)
    files_check &= check_file_exists(BASE_DIR / ".gitignore", required=False)
    
    # Проверка railway.json
    railway_check = check_railway_json()
    
    # Проверка requirements.txt
    requirements_check = check_requirements()
    
    # Проверка настроек Django
    settings_check = check_settings()
    
    # Итоговый результат
    print("\n=== Результаты проверки ===")
    all_passed = files_check and railway_check and requirements_check and settings_check
    
    if all_passed:
        print("\n[Успех] Проект готов к деплою на Railway!")
        print("\nСледующие шаги:")
        print("1. Закоммитьте и отправьте изменения в GitHub:")
        print("   git add .")
        print('   git commit -m "Подготовка к деплою на Railway"')
        print("   git push")
        print("2. Настройте переменные окружения на Railway:")
        print("   - SECRET_KEY: уникальный секретный ключ")
        print("   - DEBUG: False")
        print("   - ALLOWED_HOSTS: .railway.app,ваш-домен.com")
        print("3. Добавьте базу данных PostgreSQL в проект на Railway")
        print("4. После деплоя выполните миграции и создайте суперпользователя")
    else:
        print("\n[Ошибка] Проект НЕ готов к деплою на Railway. Исправьте указанные проблемы.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
