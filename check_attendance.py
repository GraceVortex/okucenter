"""
Скрипт для проверки записей посещаемости в базе данных OkuCenter.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')
django.setup()

from attendance.models import Attendance
from accounts.models import Teacher
from classes.models import ClassSchedule

def check_attendance():
    print("Проверка записей посещаемости...")
    
    # Получаем всех учителей
    teachers = Teacher.objects.all()
    
    for teacher in teachers:
        print(f"\nУчитель: {teacher.full_name} (ID: {teacher.id})")
        
        # Получаем все классы учителя
        classes = teacher.classes.all()
        print(f"Количество классов: {classes.count()}")
        
        for class_obj in classes:
            print(f"  Класс: {class_obj.name} (ID: {class_obj.id})")
            
            # Получаем все расписания для класса
            schedules = ClassSchedule.objects.filter(class_obj=class_obj)
            print(f"  Количество расписаний: {schedules.count()}")
            
            for schedule in schedules:
                print(f"    Расписание: ID {schedule.id}, День {schedule.day_of_week}, Время {schedule.start_time}-{schedule.end_time}")
                
                # Получаем все записи посещаемости для этого расписания
                attendances = Attendance.objects.filter(class_schedule=schedule)
                print(f"    Количество записей посещаемости: {attendances.count()}")
                
                for attendance in attendances:
                    print(f"      Посещение: ID {attendance.id}, Дата {attendance.date}, Студент {attendance.student.full_name if attendance.student else 'Нет'}")
                    print(f"        Статус: {attendance.status}, Подтверждено учителем: {attendance.teacher_confirmed}, Подтверждено ресепшн: {attendance.reception_confirmed}")
    
    # Проверяем общее количество записей посещаемости
    total_attendances = Attendance.objects.count()
    print(f"\nОбщее количество записей посещаемости: {total_attendances}")

if __name__ == "__main__":
    check_attendance()
