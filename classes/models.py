from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.models import Teacher, Student

class Class(models.Model):
    """
    Модель класса/курса.
    Хранит информацию о курсе, включая преподавателя, стоимость и тип оплаты.
    """
    PAYMENT_TYPE_CHOICES = (
        ('percentage', 'Процент от стоимости урока'),
        ('fixed', 'Фиксированная оплата'),
    )
    
    name = models.CharField(max_length=100, verbose_name="Название", db_index=True)
    teacher = models.ForeignKey(
        Teacher, 
        on_delete=models.CASCADE, 
        related_name='classes',
        verbose_name="Преподаватель",
        db_index=True
    )
    price_per_lesson = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Стоимость занятия"
    )
    teacher_payment_type = models.CharField(
        max_length=10, 
        choices=PAYMENT_TYPE_CHOICES, 
        default='percentage', 
        help_text="Тип оплаты преподавателя",
        verbose_name="Тип оплаты преподавателя"
    )
    teacher_percentage = models.IntegerField(
        default=0, 
        help_text="Процент от стоимости занятия, который получает преподаватель",
        verbose_name="Процент преподавателя"
    )
    teacher_fixed_payment = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0, 
        help_text="Фиксированная оплата преподавателя за занятие",
        verbose_name="Фиксированная оплата"
    )
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания", db_index=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    
    class Meta:
        verbose_name = "Класс"
        verbose_name_plural = "Классы"
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['teacher']),
        ]
    
    def clean(self):
        """Валидация на уровне модели"""
        if self.teacher_payment_type == 'percentage' and (self.teacher_percentage < 0 or self.teacher_percentage > 100):
            raise ValidationError({
                'teacher_percentage': "Процент должен быть в диапазоне от 0 до 100."
            })
        if self.teacher_payment_type == 'fixed' and self.teacher_fixed_payment <= 0:
            raise ValidationError({
                'teacher_fixed_payment': "Фиксированная оплата должна быть положительной."
            })
        if self.price_per_lesson <= 0:
            raise ValidationError({
                'price_per_lesson': "Стоимость занятия должна быть положительной."
            })
    
    def __str__(self):
        return self.name

class ClassSchedule(models.Model):
    """
    Модель расписания занятий.
    Хранит информацию о дне недели, времени и кабинете для каждого класса.
    """
    DAY_CHOICES = (
        (0, 'Понедельник'),
        (1, 'Вторник'),
        (2, 'Среда'),
        (3, 'Четверг'),
        (4, 'Пятница'),
        (5, 'Суббота'),
        (6, 'Воскресенье'),
    )
    
    class_obj = models.ForeignKey(
        Class, 
        on_delete=models.CASCADE, 
        related_name='schedules',
        verbose_name="Класс",
        db_index=True
    )
    day_of_week = models.IntegerField(
        choices=DAY_CHOICES,
        verbose_name="День недели",
        db_index=True
    )
    start_time = models.TimeField(verbose_name="Время начала", db_index=True)
    end_time = models.TimeField(verbose_name="Время окончания")
    room = models.IntegerField(
        verbose_name="Кабинет", 
        help_text="Номер кабинета",
        db_index=True
    )
    
    class Meta:
        verbose_name = "Расписание"
        verbose_name_plural = "Расписания"
        indexes = [
            models.Index(fields=['day_of_week', 'start_time']),
            models.Index(fields=['class_obj', 'day_of_week']),
            models.Index(fields=['room', 'day_of_week', 'start_time']),
        ]
    
    def clean(self):
        """Валидация на уровне модели"""
        # Временно отключаем валидацию
        return
        
        # Проверка на пересечение расписаний в одном кабинете
        overlapping_schedules = ClassSchedule.objects.filter(
            room=self.room,
            day_of_week=self.day_of_week
        ).exclude(pk=self.pk)
        
        for schedule in overlapping_schedules:
            # Проверяем, пересекаются ли временные интервалы
            if (self.start_time <= schedule.end_time and self.end_time >= schedule.start_time):
                raise ValidationError({
                    'start_time': f"В это время кабинет {self.room} занят другим классом.",
                    'end_time': f"В это время кабинет {self.room} занят другим классом."
                })
        
        # Проверка на пересечение расписаний для одного класса
        overlapping_class_schedules = ClassSchedule.objects.filter(
            class_obj=self.class_obj,
            day_of_week=self.day_of_week
        ).exclude(pk=self.pk)
        
        for schedule in overlapping_class_schedules:
            if (self.start_time <= schedule.end_time and self.end_time >= schedule.start_time):
                raise ValidationError({
                    'start_time': f"В это время у класса {self.class_obj.name} уже есть занятие.",
                    'end_time': f"В это время у класса {self.class_obj.name} уже есть занятие."
                })
    
    def __str__(self):
        return f"{self.class_obj.name} - {self.get_day_of_week_display()} {self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"

class Enrollment(models.Model):
    """
    Модель зачисления ученика на курс.
    Связывает ученика и класс, хранит дату зачисления.
    """
    student = models.ForeignKey(
        Student, 
        on_delete=models.CASCADE, 
        related_name='enrollments',
        verbose_name="Ученик",
        db_index=True
    )
    class_obj = models.ForeignKey(
        Class, 
        on_delete=models.CASCADE, 
        related_name='enrollments',
        verbose_name="Класс",
        db_index=True
    )
    enrollment_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата и время зачисления",
        db_index=True
    )
    deactivation_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата и время отчисления",
        help_text="Дата и время, когда ученик был отчислен из класса",
        db_index=True
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен",
        help_text="Активен ли ученик в данном классе",
        db_index=True
    )
    
    class Meta:
        unique_together = ('student', 'class_obj')
        verbose_name = "Зачисление"
        verbose_name_plural = "Зачисления"
        indexes = [
            models.Index(fields=['student', 'is_active']),
            models.Index(fields=['class_obj', 'is_active']),
            models.Index(fields=['enrollment_date']),
            models.Index(fields=['deactivation_date']),
        ]
    
    def clean(self):
        """Валидация на уровне модели"""
        if self.student.balance < 0:
            raise ValidationError({
                'student': "У ученика отрицательный баланс. Зачисление невозможно."
            })
    
    def __str__(self):
        return f"{self.student.full_name} - {self.class_obj.name}"

class ClassworkFile(models.Model):
    """
    Модель файла с материалами занятия.
    Хранит файлы, загруженные преподавателем для конкретного занятия.
    """
    MATERIAL_TYPE_CHOICES = (
        ('general', 'Общий материал'),
        ('lesson_specific', 'Материал к конкретному уроку'),
    )
    
    class_obj = models.ForeignKey(
        Class, 
        on_delete=models.CASCADE, 
        related_name='classwork_files',
        verbose_name="Класс",
        db_index=True
    )
    date = models.DateField(verbose_name="Дата", db_index=True)
    title = models.CharField(max_length=255, verbose_name="Название", default="Материал занятия")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    file = models.FileField(
        upload_to='classwork_files/', 
        verbose_name="Файл"
    )
    material_type = models.CharField(
        max_length=20,
        choices=MATERIAL_TYPE_CHOICES,
        default='general',
        verbose_name="Тип материала",
        db_index=True
    )
    schedule = models.ForeignKey(
        ClassSchedule,
        on_delete=models.SET_NULL,  # Если расписание удалено, материал сохраняется
        related_name='materials',
        verbose_name="Занятие по расписанию",
        null=True,
        blank=True,  # Поле необязательно для общих материалов
        db_index=True
    )
    
    class Meta:
        verbose_name = "Материал занятия"
        verbose_name_plural = "Материалы занятий"
        ordering = ['-date']
        indexes = [
            models.Index(fields=['class_obj', '-date']),
            models.Index(fields=['-date']),
            models.Index(fields=['material_type']),
            models.Index(fields=['schedule']),
        ]
    
    def clean(self):
        """Валидация на уровне модели"""
        if self.material_type == 'lesson_specific' and not self.schedule:
            raise ValidationError({
                'schedule': "Для материала к конкретному уроку необходимо указать занятие по расписанию."
            })
    
    def __str__(self):
        if self.material_type == 'general':
            return f"Общий материал: {self.title} - {self.class_obj.name} ({self.date})"
        else:
            return f"Материал к уроку: {self.title} - {self.class_obj.name} ({self.date})"

class Homework(models.Model):
    """
    Модель домашнего задания.
    Хранит информацию о домашнем задании, заданном преподавателем.
    """
    class_obj = models.ForeignKey(
        Class, 
        on_delete=models.CASCADE, 
        related_name='homework',
        verbose_name="Класс",
        db_index=True
    )
    date = models.DateField(verbose_name="Дата", db_index=True, null=True, blank=True)
    due_date = models.DateField(verbose_name="Дедлайн", db_index=True, default=timezone.now)
    title = models.CharField(max_length=255, verbose_name="Название")
    description = models.TextField(verbose_name="Описание", blank=True, default="")
    file = models.FileField(
        upload_to='homework_files/', 
        blank=True, 
        null=True,
        verbose_name="Файл"
    )

    
    class Meta:
        verbose_name = "Домашнее задание"
        verbose_name_plural = "Домашние задания"
        ordering = ['-due_date']
        indexes = [
            models.Index(fields=['class_obj', '-due_date']),
            models.Index(fields=['-due_date']),
        ]
    
    def clean(self):
        """Валидация на уровне модели"""
        # В новой версии мы используем только одну дату (дедлайн)
        pass
    
    def __str__(self):
        return f"{self.title} - {self.class_obj.name} ({self.date})"

class HomeworkSubmission(models.Model):
    """
    Модель выполненного домашнего задания.
    Хранит информацию о выполненном домашнем задании, включая файл, статус и комментарий преподавателя.
    """
    COMPLETION_CHOICES = (
        ('completed', 'Выполнено'),
        ('partially_completed', 'Частично выполнено'),
        ('not_completed', 'Не выполнено'),
    )
    
    homework = models.ForeignKey(
        Homework, 
        on_delete=models.CASCADE, 
        related_name='submissions',
        verbose_name="Домашнее задание",
        db_index=True
    )
    student = models.ForeignKey(
        Student, 
        on_delete=models.CASCADE, 
        related_name='homework_submissions',
        verbose_name="Ученик",
        db_index=True
    )
    file = models.FileField(
        upload_to='homework_submissions/',
        verbose_name="Файл"
    )
    submission_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата отправки",
        db_index=True
    )
    completion_status = models.CharField(
        max_length=20, 
        choices=COMPLETION_CHOICES, 
        blank=True, 
        null=True,
        verbose_name="Статус выполнения",
        db_index=True
    )
    teacher_comment = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Комментарий преподавателя"
    )
    grade = models.PositiveSmallIntegerField(
        blank=True, 
        null=True,
        verbose_name="Оценка",
        help_text="Оценка за выполненное домашнее задание"
    )

    
    class Meta:
        verbose_name = "Выполненное домашнее задание"
        verbose_name_plural = "Выполненные домашние задания"
        ordering = ['-submission_date']
        unique_together = ('homework', 'student')
        indexes = [
            models.Index(fields=['homework', 'student']),
            models.Index(fields=['student', '-submission_date']),
            models.Index(fields=['completion_status']),
        ]
    
    def clean(self):
        """Валидация на уровне модели"""
        if self.grade is not None and (self.grade < 0 or self.grade > 100):
            raise ValidationError({
                'grade': "Оценка должна быть в диапазоне от 0 до 100."
            })
    
    def __str__(self):
        return f"Работа {self.student.full_name} по заданию {self.homework}"


# Импортируем модели для уроков и материалов
from .models_lesson import LessonMaterial, StudentLessonGrade
