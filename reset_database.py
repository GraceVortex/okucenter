from django.db import transaction
from django.contrib.auth.models import User
from accounts.models import Student, Teacher, Parent, Reception
from finance.models import Transaction
from attendance.models import Attendance
from classes.models import Class, Enrollment

@transaction.atomic
def reset_database():
    """Удаляет все данные из базы данных, кроме суперпользователя."""
    # Сохраняем информацию о суперпользователе
    superusers = User.objects.filter(is_superuser=True)
    superuser_usernames = list(superusers.values_list('username', flat=True))
    
    print(f"Найдено суперпользователей: {superusers.count()}")
    print(f"Имена суперпользователей: {', '.join(superuser_usernames)}")
    
    # Удаляем данные о посещаемости
    attendance_count = Attendance.objects.count()
    Attendance.objects.all().delete()
    print(f"Удалено записей о посещаемости: {attendance_count}")
    
    # Удаляем транзакции
    transaction_count = Transaction.objects.count()
    Transaction.objects.all().delete()
    print(f"Удалено транзакций: {transaction_count}")
    
    # Удаляем записи о зачислении
    enrollment_count = Enrollment.objects.count()
    Enrollment.objects.all().delete()
    print(f"Удалено записей о зачислении: {enrollment_count}")
    
    # Удаляем классы
    class_count = Class.objects.count()
    Class.objects.all().delete()
    print(f"Удалено классов: {class_count}")
    
    # Удаляем студентов
    student_count = Student.objects.count()
    Student.objects.all().delete()
    print(f"Удалено студентов: {student_count}")
    
    # Удаляем преподавателей
    teacher_count = Teacher.objects.count()
    Teacher.objects.all().delete()
    print(f"Удалено преподавателей: {teacher_count}")
    
    # Удаляем родителей
    parent_count = Parent.objects.count()
    Parent.objects.all().delete()
    print(f"Удалено родителей: {parent_count}")
    
    # Удаляем администраторов рецепции
    reception_count = Reception.objects.count()
    Reception.objects.all().delete()
    print(f"Удалено администраторов рецепции: {reception_count}")
    
    # Удаляем пользователей, кроме суперпользователей
    user_count = User.objects.exclude(is_superuser=True).count()
    User.objects.exclude(is_superuser=True).delete()
    print(f"Удалено пользователей: {user_count}")
    
    print("\nБаза данных успешно очищена. Сохранены только суперпользователи.")

if __name__ == "__main__":
    reset_database()
