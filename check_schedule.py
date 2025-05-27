import os
import sys
import django
from django.utils import timezone

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')
django.setup()

# Импортируем модели после настройки Django
from accounts.models import Student
from classes.models import ClassSchedule, Class
from attendance.models import Attendance

# Получаем текущую дату и день недели
today = timezone.now().date()
day_of_week = today.weekday()

print(f"Сегодня: {today}, день недели: {day_of_week}")

# Находим студента Dulat
students = Student.objects.filter(full_name__icontains='Dulat')
if not students.exists():
    print("Студент с именем Dulat не найден")
    sys.exit(1)

# Выводим информацию о каждом найденном студенте
for student in students:
    print(f"\nСтудент: {student.full_name} (ID: {student.id})")
    
    # Получаем активные записи на курсы
    enrollments = student.enrollments.filter(is_active=True)
    if not enrollments.exists():
        print("У студента нет активных записей на курсы")
        continue
    
    print(f"Активные записи на курсы: {enrollments.count()}")
    
    # Получаем ID классов, на которые записан студент
    class_ids = [enrollment.class_obj_id for enrollment in enrollments]
    print(f"ID классов: {class_ids}")
    
    # Получаем расписание занятий на сегодня
    schedules = ClassSchedule.objects.filter(
        class_obj_id__in=class_ids,
        day_of_week=day_of_week
    ).select_related('class_obj')
    
    if not schedules.exists():
        print(f"У студента нет занятий на сегодня (день недели: {day_of_week})")
        
        # Проверяем, есть ли занятия в другие дни недели
        other_schedules = ClassSchedule.objects.filter(
            class_obj_id__in=class_ids
        ).select_related('class_obj')
        
        if other_schedules.exists():
            print("Занятия в другие дни недели:")
            for schedule in other_schedules:
                day_name = dict(ClassSchedule.DAY_CHOICES)[schedule.day_of_week]
                print(f"  - {schedule.class_obj.name}: {day_name}, {schedule.start_time.strftime('%H:%M')} - {schedule.end_time.strftime('%H:%M')}")
        else:
            print("У студента нет занятий ни в один день недели")
        
        continue
    
    print(f"Занятия на сегодня: {schedules.count()}")
    
    # Выводим информацию о каждом занятии
    for schedule in schedules:
        class_obj = schedule.class_obj
        start_time = schedule.start_time.strftime('%H:%M')
        end_time = schedule.end_time.strftime('%H:%M')
        
        # Проверяем, отмечен ли студент на этом занятии сегодня
        attendance = Attendance.objects.filter(
            student=student,
            class_obj=class_obj,
            date=today
        ).first()
        
        status = attendance.status if attendance else "не отмечен"
        
        print(f"  - {class_obj.name}: {start_time} - {end_time}, статус: {status}")
