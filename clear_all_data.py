"""
Скрипт для очистки базы данных OkuCenter.
Удаляет все записи, кроме информации о пользователях (студентах, учителях и ресепшнистах).
"""

import os
import django
import sys

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')
django.setup()

# Импортируем модели
from django.db import transaction
from django.db.models import Q
from accounts.models import Student, Teacher, Parent, Reception, User
from classes.models import Class, ClassSchedule, Enrollment
from attendance.models import Attendance, Mark, CanceledAttendance, CancellationRequest, StudentCancellationRequest
from finance.models import Transaction, TeacherSalary, BenchmarkSalary

def clear_database():
    """Очищает базу данных, сохраняя только информацию о пользователях."""
    print("Начинаем очистку базы данных...")
    
    try:
        with transaction.atomic():
            # Удаляем все финансовые записи
            print("Удаление финансовых записей...")
            Transaction.objects.all().delete()
            TeacherSalary.objects.all().delete()
            BenchmarkSalary.objects.all().delete()
            print("Финансовые записи удалены.")
            
            # Удаляем все записи посещаемости
            print("Удаление записей посещаемости...")
            Mark.objects.all().delete()
            CanceledAttendance.objects.all().delete()
            CancellationRequest.objects.all().delete()
            StudentCancellationRequest.objects.all().delete()
            Attendance.objects.all().delete()
            print("Записи посещаемости удалены.")
            
            # Удаляем все записи о классах и расписании
            print("Удаление записей о классах и расписании...")
            Enrollment.objects.all().delete()
            ClassSchedule.objects.all().delete()
            Class.objects.all().delete()
            print("Записи о классах и расписании удалены.")
            
            # Сбрасываем балансы студентов на ноль
            print("Сброс балансов студентов...")
            Student.objects.all().update(balance=0)
            print("Балансы студентов сброшены на ноль.")
            
            print("База данных успешно очищена.")
            print("Сохранены только записи о пользователях (студентах, учителях и ресепшнистах).")
    
    except Exception as e:
        print(f"Ошибка при очистке базы данных: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Запускаем очистку базы данных без запроса подтверждения
    print("Внимание: Удаление всех данных, кроме информации о пользователях...")
    clear_database()
