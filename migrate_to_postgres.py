"""
Скрипт для миграции данных из SQLite в MySQL
"""

import os
import sys
import subprocess
import json
import time
from pathlib import Path

# Устанавливаем переменную окружения для Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')

def create_backup():
    """Создает резервную копию данных из SQLite"""
    print("Создание резервной копии данных из SQLite...")
    
    try:
        # Создаем директорию для бэкапов, если она не существует
        backup_dir = Path('backups')
        backup_dir.mkdir(exist_ok=True)
        
        # Имя файла бэкапа с временной меткой
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup_file = backup_dir / f"sqlite_backup_{timestamp}.json"
        
        # Запускаем команду dumpdata для создания бэкапа
        result = subprocess.run(
            [sys.executable, 'manage.py', 'dumpdata', '--exclude', 'contenttypes', '--exclude', 'auth.permission', '--indent', '2'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Ошибка при создании бэкапа: {result.stderr}")
            return None
        
        # Записываем данные в файл
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(result.stdout)
        
        print(f"Бэкап успешно создан: {backup_file}")
        return backup_file
    
    except Exception as e:
        print(f"Ошибка при создании бэкапа: {e}")
        return None

def setup_mysql():
    """Настраивает MySQL базу данных"""
    print("Настройка MySQL базы данных...")
    
    try:
        # Запускаем миграции для MySQL
        migrate_result = subprocess.run(
            [sys.executable, 'manage.py', 'migrate'],
            capture_output=True,
            text=True
        )
        
        if migrate_result.returncode != 0:
            print(f"Ошибка при выполнении миграций: {migrate_result.stderr}")
            return False
        
        print("Миграции успешно выполнены")
        return True
    
    except Exception as e:
        print(f"Ошибка при настройке MySQL: {e}")
        return False

def restore_data(backup_file):
    """Восстанавливает данные из бэкапа в MySQL"""
    print(f"Восстановление данных из бэкапа {backup_file}...")
    
    try:
        # Загружаем данные из бэкапа
        result = subprocess.run(
            [sys.executable, 'manage.py', 'loaddata', backup_file],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Ошибка при восстановлении данных: {result.stderr}")
            return False
        
        print("Данные успешно восстановлены")
        return True
    
    except Exception as e:
        print(f"Ошибка при восстановлении данных: {e}")
        return False

def main():
    """Основная функция для миграции данных"""
    print("Начинаем миграцию данных из SQLite в MySQL...")
    
    # Шаг 1: Создание бэкапа данных из SQLite
    backup_file = create_backup()
    if not backup_file:
        print("Не удалось создать бэкап. Миграция прервана.")
        return
    
    # Шаг 2: Настройка MySQL и выполнение миграций
    if not setup_mysql():
        print("Не удалось настроить MySQL. Миграция прервана.")
        return
    
    # Шаг 3: Восстановление данных в MySQL
    if not restore_data(backup_file):
        print("Не удалось восстановить данные. Миграция прервана.")
        return
    
    print("Миграция данных из SQLite в MySQL успешно завершена!")

if __name__ == "__main__":
    main()
