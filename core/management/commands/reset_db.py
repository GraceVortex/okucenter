from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import User, Student, Teacher, Parent, Reception
from finance.models import Transaction
from attendance.models import Attendance
from classes.models import Class, Enrollment

class Command(BaseCommand):
    help = 'Resets the database, keeping only superusers'

    @transaction.atomic
    def handle(self, *args, **options):
        # Сохраняем информацию о суперпользователе
        superusers = User.objects.filter(is_superuser=True)
        superuser_usernames = list(superusers.values_list('username', flat=True))
        
        self.stdout.write(self.style.SUCCESS(f"Found superusers: {superusers.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Superuser usernames: {', '.join(superuser_usernames)}"))
        
        # Удаляем данные о посещаемости
        attendance_count = Attendance.objects.count()
        Attendance.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted attendance records: {attendance_count}"))
        
        # Удаляем транзакции
        transaction_count = Transaction.objects.count()
        Transaction.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted transactions: {transaction_count}"))
        
        # Удаляем записи о зачислении
        enrollment_count = Enrollment.objects.count()
        Enrollment.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted enrollments: {enrollment_count}"))
        
        # Удаляем классы
        class_count = Class.objects.count()
        Class.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted classes: {class_count}"))
        
        # Удаляем студентов
        student_count = Student.objects.count()
        Student.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted students: {student_count}"))
        
        # Удаляем преподавателей
        teacher_count = Teacher.objects.count()
        Teacher.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted teachers: {teacher_count}"))
        
        # Удаляем родителей
        parent_count = Parent.objects.count()
        Parent.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted parents: {parent_count}"))
        
        # Удаляем администраторов рецепции
        reception_count = Reception.objects.count()
        Reception.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted reception admins: {reception_count}"))
        
        # Удаляем пользователей, кроме суперпользователей
        user_count = User.objects.exclude(is_superuser=True).count()
        User.objects.exclude(is_superuser=True).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted users: {user_count}"))
        
        self.stdout.write(self.style.SUCCESS("\nDatabase successfully reset. Only superusers preserved."))
