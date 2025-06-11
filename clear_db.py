"""
Скрипт для очистки базы данных OkuCenter.
Удаляет все записи, кроме данных о студентах, учителях и ресепшенистах.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')
django.setup()

from django.db import connection
from django.contrib.auth.models import Group, Permission
from accounts.models import User, Student, Teacher, Parent, Reception
from finance.models import Transaction, TeacherSalary, BenchmarkSalary
from classes.models import Class, ClassSchedule, Enrollment
from attendance.models import Attendance
from classes.non_scheduled_lesson_models import NonScheduledLesson, NonScheduledLessonAttendance

def clear_database():
    print("Начинаем очистку базы данных...")
    
    # Сохраняем количество записей до удаления
    print("\nКоличество записей до удаления:")
    print(f"Транзакции: {Transaction.objects.count()}")
    print(f"Зарплаты учителей: {TeacherSalary.objects.count()}")
    print(f"Эталонные зарплаты: {BenchmarkSalary.objects.count()}")
    print(f"Классы: {Class.objects.count()}")
    print(f"Расписания: {ClassSchedule.objects.count()}")
    print(f"Записи на курсы: {Enrollment.objects.count()}")
    print(f"Посещения: {Attendance.objects.count()}")
    print(f"Уроки не по расписанию: {NonScheduledLesson.objects.count()}")
    print(f"Посещения уроков не по расписанию: {NonScheduledLessonAttendance.objects.count()}")
    
    # Сохраняем количество пользователей до удаления
    students_count = Student.objects.count()
    teachers_count = Teacher.objects.count()
    parents_count = Parent.objects.count()
    reception_count = Reception.objects.count()
    users_count = User.objects.count()
    
    print(f"\nПользователи до удаления:")
    print(f"Студенты: {students_count}")
    print(f"Учителя: {teachers_count}")
    print(f"Родители: {parents_count}")
    print(f"Ресепшенисты: {reception_count}")
    print(f"Всего пользователей: {users_count}")
    
    # Удаляем все финансовые записи
    print("\nУдаляем финансовые записи...")
    Transaction.objects.all().delete()
    TeacherSalary.objects.all().delete()
    BenchmarkSalary.objects.all().delete()
    
    # Удаляем все записи о классах и уроках
    print("Удаляем записи о классах и уроках...")
    NonScheduledLessonAttendance.objects.all().delete()
    NonScheduledLesson.objects.all().delete()
    Attendance.objects.all().delete()
    Enrollment.objects.all().delete()
    ClassSchedule.objects.all().delete()
    Class.objects.all().delete()
    
    # Проверяем, что данные о пользователях сохранены
    print("\nПроверяем сохранность данных о пользователях...")
    print(f"Студенты: {Student.objects.count()} (было {students_count})")
    print(f"Учителя: {Teacher.objects.count()} (было {teachers_count})")
    print(f"Родители: {Parent.objects.count()} (было {parents_count})")
    print(f"Ресепшенисты: {Reception.objects.count()} (было {reception_count})")
    print(f"Всего пользователей: {User.objects.count()} (было {users_count})")
    
    # Проверяем, что все остальные данные удалены
    print("\nПроверяем удаление остальных данных:")
    print(f"Транзакции: {Transaction.objects.count()}")
    print(f"Зарплаты учителей: {TeacherSalary.objects.count()}")
    print(f"Эталонные зарплаты: {BenchmarkSalary.objects.count()}")
    print(f"Классы: {Class.objects.count()}")
    print(f"Расписания: {ClassSchedule.objects.count()}")
    print(f"Записи на курсы: {Enrollment.objects.count()}")
    print(f"Посещения: {Attendance.objects.count()}")
    print(f"Уроки не по расписанию: {NonScheduledLesson.objects.count()}")
    print(f"Посещения уроков не по расписанию: {NonScheduledLessonAttendance.objects.count()}")
    
    print("\nОчистка базы данных завершена!")

if __name__ == "__main__":
    clear_database()
