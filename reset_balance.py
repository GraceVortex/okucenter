"""
Скрипт для сброса баланса всех студентов в OkuCenter.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')
django.setup()

from accounts.models import Student
from decimal import Decimal

def reset_student_balances():
    print("Начинаем сброс баланса студентов...")
    
    # Получаем всех студентов
    students = Student.objects.all()
    
    print(f"\nТекущие балансы студентов:")
    for student in students:
        print(f"{student.full_name}: {student.balance} KZT")
    
    # Сбрасываем баланс всех студентов
    students.update(balance=Decimal('0.00'))
    
    print(f"\nБалансы студентов после сброса:")
    for student in Student.objects.all():
        print(f"{student.full_name}: {student.balance} KZT")
    
    print("\nСброс баланса студентов завершен!")

if __name__ == "__main__":
    reset_student_balances()
