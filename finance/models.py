from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from accounts.models import Student, Teacher
from classes.models import Class
from datetime import datetime
from decimal import Decimal

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
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания", db_index=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления", null=True, blank=True)
    created_by = models.ForeignKey(
        'accounts.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_transactions',
        verbose_name="Создано пользователем"
    )
    
    class Meta:
        ordering = ['-date']
        verbose_name = "Транзакция"
        verbose_name_plural = "Транзакции"
        indexes = [
            models.Index(fields=['student']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['-date']),
            models.Index(fields=['amount']),
        ]
    
    def clean(self):
        """Валидация на уровне модели"""
        if self.amount <= 0 and self.transaction_type != 'refund':
            raise ValidationError({
                'amount': "Сумма должна быть положительной для типа транзакции '{}'.".format(
                    self.get_transaction_type_display())
            })
        if self.amount >= 0 and self.transaction_type == 'refund':
            raise ValidationError({
                'amount': "Сумма должна быть отрицательной для типа транзакции 'Возврат'."
            })
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.student.full_name} - {self.amount}"

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
        default=0 # Добавим default=0 для консистентности
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
    advance_paid_date = models.DateField( # Переименовал advance_date для единообразия
        null=True,
        blank=True,
        verbose_name="Дата выплаты аванса"
    )
    advance_confirmed_by = models.ForeignKey(
        'accounts.User',
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
    # Кто подтвердил окончательную выплату или последнюю частичную выплату, приведшую к статусу 'paid'
    payment_confirmed_by = models.ForeignKey( # Переименовал confirmed_by
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_final_payments', # Изменил related_name
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

    @property
    def remaining_amount(self):
        """Оставшаяся к выплате сумма за месяц."""
        return self.amount - self.paid_amount

    def update_payment_status(self):
        """Обновляет статус выплаты на основе выплаченной суммы."""
        if self.paid_amount == 0:
            self.payment_status = 'unpaid'
        elif self.paid_amount > 0 and self.paid_amount < self.amount:
            self.payment_status = 'partially_paid'
        elif self.paid_amount >= self.amount: # >= на случай переплат, хотя их быть не должно по логике
            self.payment_status = 'paid'
            if not self.final_payment_date: # Устанавливаем дату, если это полный расчет
                 self.final_payment_date = timezone.now().date()

    def save(self, *args, **kwargs):
        self.update_payment_status()
        # Если общая сумма начислений равна 0, то статус должен быть 'unpaid',
        # если только paid_amount тоже не 0 (например, ошибочная выплата при нулевом начислении)
        if self.amount == 0 and self.paid_amount == 0:
            self.payment_status = 'unpaid'
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-month', 'teacher'] # Добавил сортировку по учителю для консистентности
        unique_together = ('teacher', 'month')
        verbose_name = "Зарплата преподавателя"
        verbose_name_plural = "Зарплаты преподавателей"
        indexes = [
            models.Index(fields=['teacher']),
            models.Index(fields=['-month']),
            models.Index(fields=['payment_status']), # Обновленный индекс
            models.Index(fields=['amount']),
            models.Index(fields=['paid_amount']), # Добавил индекс
        ]

    def __str__(self):
        month_name = self.month.strftime('%B %Y')
        return f"{self.teacher.full_name} - {month_name} - Начислено: {self.amount}, Выплачено: {self.paid_amount}, Статус: {self.get_payment_status_display()}"

    @staticmethod
    def get_current_month():
        """Возвращает первый день текущего месяца"""
        today = timezone.now().date()
        return datetime(year=today.year, month=today.month, day=1).date()

    @staticmethod
    def calculate_lesson_payment(class_obj):
        """
        Вспомогательный метод для расчета суммы оплаты за одно занятие
        в зависимости от типа оплаты учителя (процент или фиксированная сумма)
        """
        from decimal import Decimal
        
        base_amount = Decimal('0.00')
        if class_obj.teacher_payment_type == 'percentage':
            price = class_obj.price_per_lesson or Decimal('0.00')
            percentage = Decimal(str(class_obj.teacher_percentage or 0)) / Decimal('100')
            base_amount = price * percentage
        else:  # fixed payment или любой другой тип
            base_amount = class_obj.teacher_fixed_payment or Decimal('0.00')
            
        return base_amount

    @staticmethod
    def calculate_teacher_salary(teacher, month=None):
        """
        Рассчитывает зарплату учителя за указанный месяц
        на основе проведенных занятий и типа оплаты (процент или фиксированная сумма)
        """
        from attendance.models import Attendance
        from classes.models import ClassSchedule # Убедимся, что импорт здесь
        from django.db.models import Count, Sum, F, ExpressionWrapper, DecimalField, Case, When
        
        if month is None:
            month = TeacherSalary.get_current_month()
        
        first_day_of_month = month
        if month.month == 12:
            last_day_of_month = datetime(month.year + 1, 1, 1).date() - timedelta(days=1)
        else:
            last_day_of_month = datetime(month.year, month.month + 1, 1).date() - timedelta(days=1)
            
        # Получаем подтвержденные посещения для классов учителя за указанный месяц
        # Учитываем только те посещения, где учитель указан в Class.teacher
        attendances = Attendance.objects.filter(
            class_schedule__class_obj__teacher=teacher,
            date__range=[first_day_of_month, last_day_of_month],
            status='present' # Только за присутствие
            # Не требуем подтверждения рецепшеном, так как это может привести к неправильному расчету
            # если посещение отмечено, но не подтверждено рецепшеном
        ).select_related('class_schedule__class_obj')

        total_salary = Decimal('0.00')
        class_earnings = {} # Для детальной информации по каждому классу
        
        # Группируем посещения по ClassSchedule, чтобы правильно считать уникальные уроки
        # Это важно, если одно ClassSchedule может иметь несколько записей Attendance (например, разные студенты)
        # но урок для учителя считается один раз.
        
        # Сначала соберем уникальные проведенные уроки (дата + расписание)
        unique_lessons = set()
        for att in attendances:
            unique_lessons.add((att.date, att.class_schedule_id))

        lessons_count = len(unique_lessons)
        
        # Теперь рассчитаем зарплату на основе этих уникальных уроков
        # Для этого нам нужно снова пройтись по посещениям или получить данные о ClassSchedule
        
        # Оптимизированный подход: агрегируем напрямую из Attendance, если возможно,
        # или получаем детали ClassSchedule для каждого уникального урока.

        # Пройдемся по уникальным урокам и рассчитаем зарплату
        for lesson_date, schedule_id in unique_lessons:
            # Получаем объект ClassSchedule и связанный Class
            try:
                schedule = ClassSchedule.objects.select_related('class_obj').get(id=schedule_id)
                class_obj = schedule.class_obj
            except ClassSchedule.DoesNotExist:
                continue # Пропускаем, если расписание не найдено (маловероятно)

            class_id = class_obj.id
            if class_id not in class_earnings:
                class_earnings[class_id] = {
                    'name': class_obj.name,
                    'lessons_conducted': 0, # Количество проведенных уроков по этому курсу
                    'amount_earned': Decimal('0.00') # Заработано по этому курсу
                }

            # Используем вспомогательный метод для расчета суммы за занятие
            base_amount_for_lesson = TeacherSalary.calculate_lesson_payment(class_obj)
            
            class_earnings[class_id]['lessons_conducted'] += 1
            class_earnings[class_id]['amount_earned'] += base_amount_for_lesson
            total_salary += base_amount_for_lesson
        
        return {
            'total': total_salary,
            'class_earnings': class_earnings, # Детализация по классам
            'lessons_count': lessons_count, # Общее количество уникальных проведенных уроков
        }

    # Метод get_or_create_salary остается, но его логика обновления/создания должна быть адаптирована
    @staticmethod
    def get_or_create_salary(teacher, month=None, recalculate=False): # Добавил recalculate
        if month is None:
            month = TeacherSalary.get_current_month()
        
        salary, created = TeacherSalary.objects.get_or_create(
            teacher=teacher,
            month=month,
            defaults={'amount': Decimal('0.00')} # amount будет рассчитан ниже
        )
        
        # Пересчитываем начисленную сумму, если это новая запись или указан флаг recalculate
        # или если сумма начисления равна 0 (например, после ручного сброса)
        if created or recalculate or salary.amount == Decimal('0.00'):
            salary_data = TeacherSalary.calculate_teacher_salary(teacher, month)
            salary.amount = salary_data['total']
            salary.lessons_count = salary_data['lessons_count']
            # При пересчете начислений, статус может измениться, если paid_amount остается прежним
            salary.update_payment_status() 
            salary.save()
            
        return salary, created

    # Метод reset_current_salary больше не нужен в таком виде,
    # так как статус управляется через paid_amount и payment_status.
    # Вместо него будут функции для выплаты аванса и основной зарплаты.за указанный месяц
        attendances = Attendance.objects.filter(
            class_schedule__class_obj__teacher=teacher,
            date__gte=month,
            date__lt=last_day,
            reception_confirmed=True
        )
        
        # Группируем посещения по классам для подсчета количества проведенных занятий
        attendance_by_class = attendances.values('class_schedule__class_obj').annotate(
            attended_count=Count('id')
        )
        
        # Создаем словарь для быстрого доступа к количеству проведенных занятий по классу
        attended_counts = {}
        for item in attendance_by_class:
            class_id = item['class_schedule__class_obj']
            attended_counts[class_id] = item['attended_count']
        
        # Рассчитываем общее количество запланированных занятий по каждому классу за месяц
        # Для простоты предположим, что в месяце 4 недели
        scheduled_counts = {}
        for schedule in class_schedules:
            class_id = schedule.class_obj.id
            if class_id not in scheduled_counts:
                scheduled_counts[class_id] = 0
            # Каждый день недели в расписании означает 4 занятия в месяц
            scheduled_counts[class_id] += 4
        
        total_salary = Decimal('0.00')
        class_earnings = {}
        
        # Рассчитываем зарплату по каждому классу
        for attendance in attendances:
            class_obj = attendance.class_schedule.class_obj
            class_id = class_obj.id
            
            # Определяем базовую сумму в зависимости от типа оплаты
            base_amount = TeacherSalary.calculate_lesson_payment(class_obj)
            
            # Добавляем в статистику по классам
            if class_id not in class_earnings:
                class_earnings[class_id] = {
                    'class_name': class_obj.name,
                    'amount': 0,
                    'attendances': 0,
                    'scheduled': scheduled_counts.get(class_id, 0)
                }
            
            class_earnings[class_id]['amount'] += base_amount
            class_earnings[class_id]['attendances'] += 1
        
        # Рассчитываем итоговую зарплату на основе статистики по классам
        for class_id, data in class_earnings.items():
            total_salary += data['amount']
        
        return {
            'total': total_salary,
            'class_earnings': class_earnings,
            'attendances_count': attendances.count(),
            'lessons_count': attendances.count(),
            'scheduled_counts': scheduled_counts,
            'attended_counts': attended_counts
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
                payment_status='unpaid'
            )
            
            # Помечаем как выплаченную
            current_salary.payment_status = 'paid'
            current_salary.final_payment_date = timezone.now().date()
            current_salary.save()
            
            return True
        except TeacherSalary.DoesNotExist:
            return False


class BenchmarkSalary(models.Model):
    """
    Модель для хранения эталонных зарплат по должностям.
    Используется для сравнения и анализа зарплат сотрудников.
    """
    position = models.CharField(
        max_length=100,
        verbose_name="Должность",
        db_index=True
    )
    min_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Минимальная зарплата"
    )
    max_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Максимальная зарплата"
    )
    average_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Средняя зарплата"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Описание"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
        null=True,
        blank=True
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления"
    )
    
    class Meta:
        verbose_name = "Эталонная зарплата"
        verbose_name_plural = "Эталонные зарплаты"
        ordering = ['position']
    
    def __str__(self):
        return f"{self.position} ({self.min_salary} - {self.max_salary})"