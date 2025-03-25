"""
Скрипт для генерации SQL-скрипта для создания структуры базы данных MySQL
"""

import os
import sys
import subprocess
from pathlib import Path

def get_app_names():
    """Получает список всех приложений Django в проекте"""
    # Список стандартных приложений Django
    django_apps = ['auth', 'contenttypes', 'sessions', 'admin', 'messages']
    
    # Список ваших приложений
    custom_apps = ['accounts', 'attendance', 'classes', 'core', 'finance', 'messaging']
    
    return django_apps + custom_apps

def generate_sql_for_app(app_name):
    """Генерирует SQL для миграций приложения"""
    try:
        # Получаем список миграций для приложения
        result = subprocess.run(
            [sys.executable, 'manage.py', 'showmigrations', app_name],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Ошибка при получении миграций для {app_name}: {result.stderr}")
            return ""
        
        # Парсим вывод, чтобы получить имена миграций
        migrations = []
        for line in result.stdout.split('\n'):
            if '[X]' in line or '[ ]' in line:
                migration_name = line.strip().split(' ')[-1]
                migrations.append(migration_name)
        
        # Генерируем SQL для каждой миграции
        sql_statements = []
        for migration in migrations:
            result = subprocess.run(
                [sys.executable, 'manage.py', 'sqlmigrate', app_name, migration],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"Ошибка при генерации SQL для {app_name}.{migration}: {result.stderr}")
                continue
            
            sql_statements.append(f"-- Migration: {app_name}.{migration}")
            sql_statements.append(result.stdout)
        
        return "\n".join(sql_statements)
    
    except Exception as e:
        print(f"Ошибка при генерации SQL для {app_name}: {e}")
        return ""

def main():
    """Основная функция для генерации SQL-скрипта"""
    print("Начинаем генерацию SQL-скрипта для MySQL...")
    
    # Получаем список приложений
    apps = get_app_names()
    
    # Генерируем SQL для каждого приложения
    all_sql = []
    for app in apps:
        print(f"Генерация SQL для приложения {app}...")
        sql = generate_sql_for_app(app)
        if sql:
            all_sql.append(sql)
    
    # Записываем SQL в файл
    output_file = Path('mysql_structure.sql')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("-- SQL-скрипт для создания структуры базы данных MySQL\n\n")
        f.write("\n\n".join(all_sql))
    
    print(f"SQL-скрипт успешно сгенерирован и сохранен в {output_file}")
    print("Теперь вы можете импортировать этот файл в phpMyAdmin")

if __name__ == "__main__":
    main()
