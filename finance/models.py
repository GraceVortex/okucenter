from django.db import models
from accounts.models import Student, Teacher
from classes.models import Class
from django.utils import timezone
from datetime import datetime
from decimal import Decimal

class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('payment', 'Payment'),
        ('deposit', 'Deposit'),
        ('refund', 'Refund'),
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    description = models.CharField(max_length=255)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    class_obj = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_transactions')
    
    class Meta:
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.transaction_type} - {self.student.full_name} - {self.amount}"

class TeacherSalary(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='salaries')
    month = models.DateField(help_text="Первый день месяца")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    paid_date = models.DateField(null=True, blank=True)
    lessons_count = models.PositiveIntegerField(default=0, help_text="Количество проведенных занятий")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-month']
        unique_together = ('teacher', 'month')
        verbose_name = "Зарплата учителя"
        verbose_name_plural = "Зарплаты учителей"
    
    def __str__(self):
        month_name = self.month.strftime('%B %Y')
        return f"{self.teacher.full_name} - {month_name} - {self.amount}"
    
    @staticmethod
    def get_current_month():
        """Возвращает первый день текущего месяца"""
        today = timezone.now().date()
        return datetime(today.year, today.month, 1).date()
    
    @staticmethod
    def calculate_teacher_salary(teacher, month=None):
        """
        Рассчитывает зарплату учителя за указанный месяц
        на основе проведенных занятий и типа оплаты (процент или фиксированная сумма)
        """
        from attendance.models import Attendance
        
        if month is None:
            month = TeacherSalary.get_current_month()
        
        # Получаем последний день месяца
        if month.month == 12:
            last_day = datetime(month.year + 1, 1, 1).date()
        else:
            last_day = datetime(month.year, month.month + 1, 1).date()
        
        # Получаем подтвержденные посещения для классов учителя за указанный месяц
        attendances = Attendance.objects.filter(
            class_schedule__class_obj__teacher=teacher,
            date__gte=month,
            date__lt=last_day,
            reception_confirmed=True
        )
        
        total_salary = Decimal('0.00')
        class_earnings = {}
        
        # Рассчитываем зарплату по каждому классу
        for attendance in attendances:
            class_obj = attendance.class_schedule.class_obj
            
            # Определяем сумму в зависимости от типа оплаты
            if class_obj.teacher_payment_type == 'percentage':
                price = class_obj.price_per_lesson
                percentage = Decimal(str(class_obj.teacher_percentage)) / Decimal('100')
                amount = price * percentage
            else:  # fixed payment
                amount = class_obj.teacher_fixed_payment
            
            total_salary += amount
            
            # Добавляем в статистику по классам
            if class_obj.id not in class_earnings:
                class_earnings[class_obj.id] = {
                    'class_name': class_obj.name,
                    'amount': 0,
                    'attendances': 0
                }
            
            class_earnings[class_obj.id]['amount'] += amount
            class_earnings[class_obj.id]['attendances'] += 1
        
        return {
            'total': total_salary,
            'class_earnings': class_earnings,
            'attendances_count': attendances.count(),
            'lessons_count': attendances.count()
        }
    
    @staticmethod
    def get_or_create_salary(teacher, month=None):
        """
        Получает или создает запись о зарплате учителя за указанный месяц
        """
        if month is None:
            month = TeacherSalary.get_current_month()
        
        try:
            salary = TeacherSalary.objects.get(teacher=teacher, month=month)
            return salary, False
        except TeacherSalary.DoesNotExist:
            # Рассчитываем зарплату
            salary_data = TeacherSalary.calculate_teacher_salary(teacher, month)
            
            # Создаем новую запись
            salary = TeacherSalary(
                teacher=teacher,
                month=month,
                amount=salary_data['total'],
                lessons_count=salary_data['lessons_count']
            )
            salary.save()
            
            return salary, True
    
    @staticmethod
    def reset_current_salary(teacher):
        """
        Обнуляет зарплату учителя за текущий месяц после выплаты
        """
        current_month = TeacherSalary.get_current_month()
        
        # Получаем зарплату за текущий месяц
        try:
            current_salary = TeacherSalary.objects.get(
                teacher=teacher,
                month=current_month,
                is_paid=False
            )
            
            # Помечаем как выплаченную
            current_salary.is_paid = True
            current_salary.paid_date = timezone.now().date()
            current_salary.save()
            
            return True
        except TeacherSalary.DoesNotExist:
            return False