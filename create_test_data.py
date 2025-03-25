import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Teacher, Student, Parent
from classes.models import Class, ClassSchedule
from datetime import date

User = get_user_model()

def create_test_data():
    # Проверяем, есть ли уже данные в базе
    if User.objects.filter(username='teacher1').exists():
        print("Тестовые данные уже существуют.")
        return

    # Создаем учителей
    teacher_user1 = User.objects.create_user(
        username='teacher1',
        password='password123',
        first_name='Иван',
        last_name='Петров',
        email='teacher1@example.com',
        user_type='teacher'
    )
    
    teacher_user2 = User.objects.create_user(
        username='teacher2',
        password='password123',
        first_name='Мария',
        last_name='Иванова',
        email='teacher2@example.com',
        user_type='teacher'
    )
    
    # Создаем профили учителей
    teacher1 = Teacher.objects.create(
        user=teacher_user1,
        full_name=f"{teacher_user1.first_name} {teacher_user1.last_name}",
        birth_date=date(1985, 5, 15),
        google_docs_link='https://docs.google.com/document/d/1234567890'
    )
    
    teacher2 = Teacher.objects.create(
        user=teacher_user2,
        full_name=f"{teacher_user2.first_name} {teacher_user2.last_name}",
        birth_date=date(1990, 3, 20),
        google_docs_link='https://docs.google.com/document/d/0987654321'
    )
    
    # Создаем студентов
    student_user1 = User.objects.create_user(
        username='student1',
        password='password123',
        first_name='Алексей',
        last_name='Смирнов',
        email='student1@example.com',
        user_type='student'
    )
    
    student_user2 = User.objects.create_user(
        username='student2',
        password='password123',
        first_name='Екатерина',
        last_name='Козлова',
        email='student2@example.com',
        user_type='student'
    )
    
    # Создаем профили студентов
    student1 = Student.objects.create(
        user=student_user1,
        full_name=f"{student_user1.first_name} {student_user1.last_name}",
        birth_date=date(2005, 8, 10),
        school='Школа №1',
        graduation_year=2023,
        school_start_year=2012,
        phone_number='+77001234567',
        balance=10000
    )
    
    student2 = Student.objects.create(
        user=student_user2,
        full_name=f"{student_user2.first_name} {student_user2.last_name}",
        birth_date=date(2006, 4, 25),
        school='Школа №2',
        graduation_year=2024,
        school_start_year=2013,
        phone_number='+77007654321',
        balance=15000
    )
    
    # Создаем родителей
    parent_user1 = User.objects.create_user(
        username='parent1',
        password='password123',
        first_name='Сергей',
        last_name='Смирнов',
        email='parent1@example.com',
        user_type='parent'
    )
    
    # Создаем профиль родителя
    parent1 = Parent.objects.create(
        user=parent_user1,
        phone_number='+77011234567'
    )
    
    # Связываем родителя со студентом
    parent1.students.add(student1)
    
    # Создаем классы
    class1 = Class.objects.create(
        name='Математика',
        description='Курс по алгебре и геометрии',
        teacher=teacher1,
        price_per_lesson=2000
    )
    
    class2 = Class.objects.create(
        name='Физика',
        description='Курс по основам физики',
        teacher=teacher2,
        price_per_lesson=2500
    )
    
    class3 = Class.objects.create(
        name='Английский язык',
        description='Курс английского языка для начинающих',
        teacher=teacher1,
        price_per_lesson=1800
    )
    
    # Создаем расписание занятий
    ClassSchedule.objects.create(
        class_obj=class1,
        day_of_week=0,  # Понедельник
        start_time='14:00',
        end_time='15:30',
        room=1
    )
    
    ClassSchedule.objects.create(
        class_obj=class2,
        day_of_week=1,  # Вторник
        start_time='16:00',
        end_time='17:30',
        room=2
    )
    
    ClassSchedule.objects.create(
        class_obj=class3,
        day_of_week=2,  # Среда
        start_time='15:00',
        end_time='16:30',
        room=3
    )
    
    ClassSchedule.objects.create(
        class_obj=class1,
        day_of_week=3,  # Четверг
        start_time='14:00',
        end_time='15:30',
        room=1
    )
    
    ClassSchedule.objects.create(
        class_obj=class2,
        day_of_week=4,  # Пятница
        start_time='16:00',
        end_time='17:30',
        room=2
    )
    
    # Записываем студентов на занятия
    class1.enroll_student(student1)
    class2.enroll_student(student1)
    class3.enroll_student(student2)
    
    print("Тестовые данные успешно созданы.")

if __name__ == '__main__':
    create_test_data()
