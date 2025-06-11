from django.db import models
from django.utils import timezone
from accounts.models import Student, Teacher, User
from classes.models import Class
from decimal import Decimal
from datetime import datetime, timedelta

# Существующие модели (с улучшениями)

class Transaction(models.Model):
    """
    Модель финансовых транзакций учеников.
    Хранит информацию о платежах, депозитах и возвратах.
    """
    TRANSACTION_TYPES = (
        ('payment', 'Оплата'),
        ('deposit', 'Депозит'),
        ('refund', 'Возврат'),
    )
    
    student = models.ForeignKey(
        Student, 
        on_delete=models.CASCADE, 
        related_name='transactions',
        verbose_name="Ученик",
        db_index=True
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Сумма",
        db_index=True
    )
    date = models.DateField(verbose_name="Дата", db_index=True)
    description = models.CharField(max_length=255, verbose_name="Описание")
    transaction_type = models.CharField(
        max_length=10, 
        choices=TRANSACTION_TYPES,
        verbose_name="Тип транзакции",
        db_index=True
    )
    class_obj = models.ForeignKey(
        Class, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='transactions',
        verbose_name="Класс"
    )
    
    # Новые поля для улучшения связей
    scheduled_lesson = models.ForeignKey(
        'attendance.Attendance',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name="Урок по расписанию"
    )
    
    non_scheduled_lesson = models.ForeignKey(
        'classes.NonScheduledLesson',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name="Урок не по расписанию"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания", db_index=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_transactions',
        verbose_name="Кто создал"
    )
    
    class Meta:
        verbose_name = "Транзакция"
        verbose_name_plural = "Транзакции"
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['student', '-date']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['class_obj']),
            models.Index(fields=['scheduled_lesson']),
            models.Index(fields=['non_scheduled_lesson']),
        ]
    
    def __str__(self):
        return f"{self.student.full_name} - {self.get_transaction_type_display()} - {self.amount} ₸ ({self.date})"


class TeacherSalary(models.Model):
    """
    Модель зарплаты учителя.
    Хранит информацию о зарплате учителя за каждый месяц.
    """
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name='salaries',
        verbose_name="Преподаватель",
        db_index=True
    )
    month = models.DateField(
        help_text="Первый день месяца",
        verbose_name="Месяц",
        db_index=True
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Начислено (общая сумма за месяц)",
        db_index=True,
        default=0
    )

    PAYMENT_STATUS_CHOICES = (
        ('unpaid', 'Не выплачено'),
        ('partially_paid', 'Частично выплачено'),
        ('paid', 'Выплачено полностью')
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='unpaid',
        verbose_name="Статус выплаты",
        db_index=True
    )

    # Общая сумма, выплаченная за этот месяц (включая аванс и основные выплаты)
    paid_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Выплачено за месяц"
    )

    # Информация по авансу
    advance_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Сумма аванса"
    )
    advance_paid_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Дата выплаты аванса"
    )
    advance_confirmed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_advances',
        verbose_name="Аванс подтвержден"
    )

    # Дата окончательного расчета за месяц
    final_payment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Дата окончательной выплаты"
    )
    lessons_count = models.IntegerField(
        default=0,
        verbose_name="Количество занятий"
    )
    payment_confirmed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_final_payments',
        verbose_name="Выплата подтверждена"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
        db_index=True
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления"
    )
    
    class Meta:
        ordering = ['-month', 'teacher']
        unique_together = ('teacher', 'month')
        verbose_name = "Зарплата преподавателя"
        verbose_name_plural = "Зарплаты преподавателей"
        indexes = [
            models.Index(fields=['teacher']),
            models.Index(fields=['-month']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['amount']),
            models.Index(fields=['paid_amount']),
        ]

    def __str__(self):
        month_name = self.month.strftime('%B %Y')
        return f"{self.teacher.full_name} - {month_name} - Начислено: {self.amount}, Выплачено: {self.paid_amount}, Статус: {self.get_payment_status_display()}"


# Новые модели для улучшения финансовой части

class LessonPayment(models.Model):
    """
    Модель для связи между уроками и платежами.
    Позволяет отслеживать, за какие уроки произведена оплата.
    """
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name='lesson_payments',
        verbose_name="Транзакция"
    )
    scheduled_lesson = models.ForeignKey(
        'attendance.Attendance',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name="Урок по расписанию"
    )
    non_scheduled_lesson = models.ForeignKey(
        'classes.NonScheduledLesson',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name="Урок не по расписанию"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Сумма"
    )
    date = models.DateField(
        verbose_name="Дата",
        db_index=True
    )
    
    class Meta:
        verbose_name = "Оплата за урок"
        verbose_name_plural = "Оплаты за уроки"
        indexes = [
            models.Index(fields=['transaction']),
            models.Index(fields=['scheduled_lesson']),
            models.Index(fields=['non_scheduled_lesson']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        lesson_info = self.scheduled_lesson if self.scheduled_lesson else self.non_scheduled_lesson
        return f"Оплата за урок: {lesson_info} - {self.amount} ₸"


class TeacherPayment(models.Model):
    """
    Модель для отслеживания выплат учителям за конкретные уроки.
    """
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name="Преподаватель"
    )
    salary = models.ForeignKey(
        TeacherSalary,
        on_delete=models.CASCADE,
        related_name='lesson_payments',
        verbose_name="Зарплата"
    )
    scheduled_lesson = models.ForeignKey(
        'attendance.Attendance',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='teacher_payments',
        verbose_name="Урок по расписанию"
    )
    non_scheduled_lesson = models.ForeignKey(
        'classes.NonScheduledLesson',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='teacher_payments',
        verbose_name="Урок не по расписанию"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Сумма"
    )
    date = models.DateField(
        verbose_name="Дата урока",
        db_index=True
    )
    payment_date = models.DateField(
        verbose_name="Дата выплаты",
        null=True,
        blank=True
    )
    is_paid = models.BooleanField(
        default=False,
        verbose_name="Выплачено"
    )
    
    class Meta:
        verbose_name = "Выплата учителю"
        verbose_name_plural = "Выплаты учителям"
        indexes = [
            models.Index(fields=['teacher']),
            models.Index(fields=['salary']),
            models.Index(fields=['scheduled_lesson']),
            models.Index(fields=['non_scheduled_lesson']),
            models.Index(fields=['date']),
            models.Index(fields=['is_paid']),
        ]
    
    def __str__(self):
        lesson_info = self.scheduled_lesson if self.scheduled_lesson else self.non_scheduled_lesson
        return f"Выплата учителю {self.teacher.full_name} за урок: {lesson_info} - {self.amount} ₸"


class FinancialStatistics(models.Model):
    """
    Модель для хранения агрегированной финансовой статистики.
    Позволяет быстро получать финансовую информацию без сложных расчетов.
    """
    date = models.DateField(
        verbose_name="Дата",
        db_index=True,
        unique=True
    )
    total_income = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Общий доход"
    )
    lesson_income = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Доход от уроков"
    )
    other_income = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Прочие доходы"
    )
    teacher_payments = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Выплаты учителям"
    )
    refunds = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Возвраты"
    )
    profit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Прибыль"
    )
    scheduled_lessons_count = models.IntegerField(
        default=0,
        verbose_name="Количество уроков по расписанию"
    )
    non_scheduled_lessons_count = models.IntegerField(
        default=0,
        verbose_name="Количество уроков не по расписанию"
    )
    students_count = models.IntegerField(
        default=0,
        verbose_name="Количество активных студентов"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Последнее обновление"
    )
    
    class Meta:
        verbose_name = "Финансовая статистика"
        verbose_name_plural = "Финансовая статистика"
        ordering = ['-date']
        indexes = [
            models.Index(fields=['-date']),
        ]
    
    def __str__(self):
        return f"Финансовая статистика за {self.date.strftime('%d.%m.%Y')}"


class MonthlyFinancialStatistics(models.Model):
    """
    Модель для хранения агрегированной финансовой статистики по месяцам.
    """
    year = models.IntegerField(
        verbose_name="Год",
        db_index=True
    )
    month = models.IntegerField(
        verbose_name="Месяц",
        db_index=True
    )
    total_income = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Общий доход"
    )
    lesson_income = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Доход от уроков"
    )
    other_income = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Прочие доходы"
    )
    teacher_payments = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Выплаты учителям"
    )
    refunds = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Возвраты"
    )
    profit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Прибыль"
    )
    scheduled_lessons_count = models.IntegerField(
        default=0,
        verbose_name="Количество уроков по расписанию"
    )
    non_scheduled_lessons_count = models.IntegerField(
        default=0,
        verbose_name="Количество уроков не по расписанию"
    )
    students_count = models.IntegerField(
        default=0,
        verbose_name="Количество активных студентов"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Последнее обновление"
    )
    
    class Meta:
        verbose_name = "Месячная финансовая статистика"
        verbose_name_plural = "Месячная финансовая статистика"
        ordering = ['-year', '-month']
        unique_together = ('year', 'month')
        indexes = [
            models.Index(fields=['-year', '-month']),
        ]
    
    def __str__(self):
        month_name = datetime(self.year, self.month, 1).strftime('%B')
        return f"Финансовая статистика за {month_name} {self.year}"
