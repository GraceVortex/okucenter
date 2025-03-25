#!/usr/bin/env python
"""
Скрипт для подготовки проекта к деплою на Railway.
"""
import os
import subprocess
import sys

def run_command(command):
    """Выполняет команду и выводит результат."""
    print(f"Выполнение: {command}")
    try:
        result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
        print(f"Успешно: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Ошибка: {e.stderr}")
        return False

def main():
    """Основная функция для подготовки проекта к деплою на Railway."""
    print("Подготовка проекта к деплою на Railway...")
    
    # Проверка наличия необходимых файлов
    required_files = ["Procfile", "runtime.txt", "railway.json", "requirements.txt"]
    for file in required_files:
        if not os.path.exists(file):
            print(f"Ошибка: Файл {file} не найден!")
            return False
    
    # Сбор статических файлов
    print("Сбор статических файлов...")
    if not run_command("python manage.py collectstatic --noinput"):
        print("Ошибка при сборе статических файлов!")
        return False
    
    # Проверка миграций
    print("Проверка миграций...")
    if not run_command("python manage.py makemigrations"):
        print("Ошибка при создании миграций!")
        return False
    
    if not run_command("python manage.py migrate --check"):
        print("Предупреждение: Есть непримененные миграции. Рекомендуется применить их перед деплоем.")
    
    # Проверка работоспособности проекта
    print("Проверка работоспособности проекта...")
    if not run_command("python manage.py check --deploy"):
        print("Предупреждение: Проверка деплоя выявила проблемы. Рекомендуется исправить их перед деплоем.")
    
    print("\nПроект готов к деплою на Railway!")
    print("\nДля деплоя на Railway выполните следующие шаги:")
    print("1. Создайте аккаунт на Railway.app (если еще не создали)")
    print("2. Установите Railway CLI: npm i -g @railway/cli")
    print("3. Войдите в аккаунт: railway login")
    print("4. Инициализируйте проект: railway init")
    print("5. Добавьте базу данных PostgreSQL: railway add")
    print("6. Настройте переменные окружения: railway variables set SECRET_KEY=your_secret_key DEBUG=False")
    print("7. Выполните деплой: railway up")
    print("8. Откройте ваше приложение: railway open")
    
    return True

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
