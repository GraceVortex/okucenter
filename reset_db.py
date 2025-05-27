import os
import django
import sys

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')
django.setup()

# Импортируем необходимые модели
from django.contrib.auth import get_user_model
from django.db.models import Q
from accounts.models import Student, Teacher, Parent, Reception
from classes.models import Class, ClassSchedule, Enrollment, Homework, HomeworkSubmission
from attendance.models import Attendance, Mark, CanceledAttendance, CancellationRequest, StudentCancellationRequest
from finance.models import Transaction, TeacherSalary

User = get_user_model()

def reset_database():
    print("Начинаем очистку базы данных...")
    
    # Сохраняем ID администратора
    admin_users = User.objects.filter(user_type='admin')
    admin_ids = list(admin_users.values_list('id', flat=True))
    
    if not admin_ids:
        print("Не найдено ни одного администратора! Операция отменена.")
        return
    
    print(f"Найдено {len(admin_ids)} администраторов. Их данные будут сохранены.")
    
    # Удаляем все финансовые транзакции
    print("Удаление финансовых транзакций...")
    Transaction.objects.all().delete()
    
    # Удаляем зарплаты учителей
    print("Удаление зарплат учителей...")
    TeacherSalary.objects.all().delete()
    
    # Удаляем записи о посещаемости и связанные данные
    print("Удаление записей о посещаемости...")
    CanceledAttendance.objects.all().delete()
    StudentCancellationRequest.objects.all().delete()
    CancellationRequest.objects.all().delete()
    Mark.objects.all().delete()
    Attendance.objects.all().delete()
    
    # Удаляем домашние задания и их выполнение
    print("Удаление домашних заданий...")
    HomeworkSubmission.objects.all().delete()
    Homework.objects.all().delete()
    
    # Удаляем записи о зачислении
    print("Удаление записей о зачислении...")
    Enrollment.objects.all().delete()
    
    # Удаляем расписания и классы
    print("Удаление расписаний и классов...")
    ClassSchedule.objects.all().delete()
    Class.objects.all().delete()
    
    # Удаляем всех пользователей, кроме администраторов
    print("Удаление пользователей (кроме администраторов)...")
    
    # Сначала удаляем профили
    Reception.objects.filter(~Q(user__id__in=admin_ids)).delete()
    Parent.objects.all().delete()
    Teacher.objects.all().delete()
    Student.objects.all().delete()
    
    # Затем удаляем пользователей
    User.objects.filter(~Q(id__in=admin_ids)).delete()
    
    print("База данных успешно очищена. Сохранены только администраторы.")

if __name__ == "__main__":
    # Автоматически запускаем очистку без запроса подтверждения
    print("ВНИМАНИЕ: Эта операция удалит ВСЕ данные из базы данных, кроме администраторов!")
    print("Выполняем очистку...")
    reset_database()
