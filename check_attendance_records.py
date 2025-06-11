"""
Скрипт для проверки записей посещаемости в базе данных OkuCenter.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')
django.setup()

from attendance.models import Attendance
from classes.models import Class, ClassSchedule
from accounts.models import Student, Teacher

def check_attendance_records():
    """Проверяет записи посещаемости в базе данных."""
    print("Проверка записей посещаемости...")
    
    # Общее количество записей
    total_records = Attendance.objects.count()
    print(f"Общее количество записей посещаемости: {total_records}")
    
    # Записи, ожидающие подтверждения ресепшн
    pending_records = Attendance.objects.filter(
        teacher_confirmed=True,
        reception_confirmed=False
    ).count()
    print(f"Записи, ожидающие подтверждения ресепшн: {pending_records}")
    
    # Записи, ожидающие подтверждения ресепшн со статусом "present"
    pending_present_records = Attendance.objects.filter(
        teacher_confirmed=True,
        reception_confirmed=False,
        status='present'
    ).count()
    print(f"Записи со статусом 'present', ожидающие подтверждения ресепшн: {pending_present_records}")
    
    # Выводим детали всех записей
    print("\nДетали всех записей посещаемости:")
    for attendance in Attendance.objects.all():
        print(f"ID: {attendance.id}")
        print(f"  Дата: {attendance.date}")
        print(f"  Студент: {attendance.student.full_name if attendance.student else 'Нет'}")
        print(f"  Класс: {attendance.class_obj.name if attendance.class_obj else 'Нет'}")
        print(f"  Статус: {attendance.status}")
        print(f"  Подтверждено учителем: {attendance.teacher_confirmed}")
        print(f"  Подтверждено ресепшн: {attendance.reception_confirmed}")
        print("---")

if __name__ == "__main__":
    check_attendance_records()
