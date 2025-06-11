from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
import logging
import os

logger = logging.getLogger(__name__)



class User(AbstractUser):
    """
    Расширенная модель пользователя.
    Добавляет тип пользователя для разграничения прав и доступа к разным частям системы.
    """
    USER_TYPE_CHOICES = (
        ('admin', 'Admin'),
        ('reception', 'Reception'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
        ('parent', 'Parent'),
        ('marketer', 'Marketer'),
    )
    
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, db_index=True, verbose_name="Тип пользователя")
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Номер телефона", db_index=True)
    face_id_data = models.TextField(blank=True, null=True, help_text="Данные для распознавания лица")
    
    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        indexes = [
            models.Index(fields=['user_type']),
            models.Index(fields=['username']),
            models.Index(fields=['email']),
            models.Index(fields=['is_active']),
        ]
    
    @property
    def is_admin(self):
        return self.user_type == 'admin'
        
    @property
    def is_reception(self):
        return self.user_type == 'reception'
        
    @property
    def is_teacher(self):
        return self.user_type == 'teacher'
        
    @property
    def is_student(self):
        return self.user_type == 'student'
        
    @property
    def is_marketer(self):
        return self.user_type == 'marketer'
    
    @property
    def is_parent(self):
        # Проверяем, является ли пользователь родителем
        if self.user_type == 'parent':
            return True
        
        # Проверяем, является ли пользователь студентом, который выступает в роли родителя
        # (т.е. у него есть связанный родительский профиль с типом 'student')
        if self.user_type == 'student':
            try:
                student = self.student_profile
                if student and student.parent and student.parent.parent_type == 'student':
                    # Проверяем, что родительский профиль создан на основе данных этого же ученика
                    if student.parent.user.username == f"{self.username}_parent":
                        return True
            except:
                pass
        
        return False
    
    def get_parent_profile(self):
        """
        Возвращает родительский профиль пользователя, если он имеет права родителя.
        Работает как для настоящих родителей, так и для учеников, выступающих в роли родителей.
        """
        # Если это настоящий родитель
        if self.user_type == 'parent':
            try:
                return self.parent_profile
            except Exception as e:
                logger.error(f"Ошибка при получении профиля родителя для пользователя {self.username}: {e}")
                return None
        
        # Если это ученик, выступающий в роли родителя
        if self.user_type == 'student':
            try:
                student = self.student_profile
                if student and student.parent and student.parent.parent_type == 'student':
                    # Проверяем, что родительский профиль создан на основе данных этого же ученика
                    if student.parent.user.username == f"{self.username}_parent":
                        return student.parent
            except Exception as e:
                logger.error(f"Ошибка при получении профиля родителя через студента для пользователя {self.username}: {e}")
        
        return None
        
    def get_full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

class Teacher(models.Model):
    """
    Модель преподавателя.
    Хранит информацию о преподавателе, включая личные данные и документы.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    full_name = models.CharField(max_length=100, verbose_name="ФИО")
    birth_date = models.DateField(verbose_name="Дата рождения")
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Номер телефона")
    docs_link = models.URLField(blank=True, null=True, verbose_name="Ссылка на документы")
    face_image = models.ImageField(upload_to='face_images/teachers/', blank=True, null=True, verbose_name="Фото лица для FaceID")
    
    class Meta:
        verbose_name = "Преподаватель"
        verbose_name_plural = "Преподаватели"
        indexes = [
            models.Index(fields=['full_name']),
            models.Index(fields=['phone_number']),
        ]
        
    def __str__(self):
        return self.full_name

class Reception(models.Model):
    """
    Модель администратора рецепции.
    Хранит информацию об администраторе рецепции, включая личные данные и документы.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='reception_profile')
    full_name = models.CharField(max_length=100, verbose_name="ФИО")
    birth_date = models.DateField(verbose_name="Дата рождения")
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Номер телефона")
    docs_link = models.URLField(blank=True, null=True, verbose_name="Ссылка на документы")
    face_image = models.ImageField(upload_to='face_images/receptions/', blank=True, null=True, verbose_name="Фото лица для FaceID")
    
    class Meta:
        verbose_name = "Администратор рецепции"
        verbose_name_plural = "Администраторы рецепции"
        indexes = [
            models.Index(fields=['full_name']),
            models.Index(fields=['phone_number']),
        ]
        
    def __str__(self):
        return self.full_name

class Student(models.Model):
    """
    Модель ученика.
    Хранит информацию об ученике, включая личные данные и информацию о школе.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    full_name = models.CharField(max_length=100, verbose_name="ФИО", db_index=True)
    birth_date = models.DateField(verbose_name="Дата рождения")
    school = models.CharField(max_length=100, verbose_name="Школа")
    current_grade = models.IntegerField(verbose_name="Текущий класс", help_text="В каком классе сейчас учится ученик (1-11)", db_index=True, default=1)
    graduation_year = models.IntegerField(verbose_name="Год выпуска", db_index=True)
    school_start_year = models.IntegerField(verbose_name="Год начала обучения", blank=True, null=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Баланс", db_index=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Номер телефона", db_index=True)
    parent = models.ForeignKey(
        'Parent', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='children',
        verbose_name="Родитель",
        db_index=True
    )

def student_face_image_path(instance, filename):
    ext = filename.split('.')[-1]
    # Имя файла: faceid_<student.id>.<расширение>
    return f'face_images/students/faceid_{instance.id}.{ext}'

class Student(models.Model):
    """
    Модель ученика.
    Хранит информацию об ученике, включая личные данные и информацию о школе.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    full_name = models.CharField(max_length=100, verbose_name="ФИО", db_index=True)
    birth_date = models.DateField(verbose_name="Дата рождения")
    school = models.CharField(max_length=100, verbose_name="Школа")
    current_grade = models.IntegerField(verbose_name="Текущий класс", help_text="В каком классе сейчас учится ученик (1-11)", db_index=True, default=1)
    graduation_year = models.IntegerField(verbose_name="Год выпуска", db_index=True)
    school_start_year = models.IntegerField(verbose_name="Год начала обучения", blank=True, null=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Баланс", db_index=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Номер телефона", db_index=True)
    parent = models.ForeignKey(
        'Parent', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='children',
        verbose_name="Родитель",
        db_index=True
    )
    is_self_managed = models.BooleanField(default=False, verbose_name="Самоуправляемый", help_text="Ученик сам управляет своим аккаунтом без родителя")
    face_image = models.ImageField(upload_to=student_face_image_path, blank=True, null=True, verbose_name="Фото лица для FaceID")

    def save(self, *args, **kwargs):
        logger = logging.getLogger(__name__)
        try:
            old_instance = None
            if self.pk:
                old_instance = Student.objects.filter(pk=self.pk).first()
            if old_instance and old_instance.face_image and self.face_image and old_instance.face_image != self.face_image:
                old_path = old_instance.face_image.path
                if os.path.isfile(old_path):
                    try:
                        os.remove(old_path)
                        logger.info(f"Удалено старое фото лица: {old_path}")
                    except Exception as e:
                        logger.error(f"Ошибка при удалении старого фото лица: {old_path}: {e}")
            super().save(*args, **kwargs)
        except Exception as e:
            logger.error(f"Ошибка при сохранении студента: {str(e)}")
            raise
    
    class Meta:
        verbose_name = "Ученик"
        verbose_name_plural = "Ученики"
        indexes = [
            models.Index(fields=['full_name']),
            models.Index(fields=['current_grade']),
            models.Index(fields=['graduation_year']),
            models.Index(fields=['balance']),
        ]
        
    def clean(self):
        """Валидация на уровне модели
        
        Проверяет, что ученик либо имеет родителя, либо отмечен как самоуправляемый.
        Это обеспечивает наличие ответственного лица для каждого ученика.
        """
        if not self.parent and not self.is_self_managed:
            raise ValidationError({
                'parent': "Ученик должен иметь родителя или быть отмечен как самоуправляемый",
                'is_self_managed': "Ученик должен иметь родителя или быть отмечен как самоуправляемый"
            })
    
    def __str__(self):
        return self.full_name

class Parent(models.Model):
    """
    Модель родителя.
    Хранит информацию о родителе или ученике, выступающем в роли родителя.
    """
    PARENT_TYPE_CHOICES = (
        ('parent', 'Родитель'),
        ('student', 'Ученик'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parent_profile')
    full_name = models.CharField(max_length=100, verbose_name="ФИО")
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Номер телефона")
    parent_type = models.CharField(
        max_length=10, 
        choices=PARENT_TYPE_CHOICES, 
        default='parent', 
        verbose_name="Тип",
        db_index=True,
        help_text="Тип родителя: настоящий родитель или ученик в роли родителя"
    )
    
    class Meta:
        verbose_name = "Родитель"
        verbose_name_plural = "Родители"
        indexes = [
            models.Index(fields=['full_name']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['parent_type']),
        ]
        
    def __str__(self):
        parent_type_display = "(Ученик)" if self.parent_type == 'student' else ""
        return f"{self.full_name} {parent_type_display}"

class Marketer(models.Model):
    """
    Модель маркетолога.
    Хранит информацию о маркетологе, включая личные данные и профессиональные навыки.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='marketer_profile')
    full_name = models.CharField(max_length=100, verbose_name="ФИО")
    birth_date = models.DateField(verbose_name="Дата рождения")
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Номер телефона")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    docs_link = models.URLField(blank=True, null=True, verbose_name="Ссылка на документы")
    face_image = models.ImageField(upload_to='face_images/marketers/', blank=True, null=True, verbose_name="Фото лица для FaceID")
    
    # Профессиональные навыки и специализация
    specialization = models.CharField(max_length=100, blank=True, null=True, verbose_name="Специализация")
    skills = models.TextField(blank=True, null=True, verbose_name="Навыки")
    experience_years = models.PositiveSmallIntegerField(default=0, verbose_name="Опыт работы (в годах)")
    
    # Статистика и KPI
    leads_target = models.PositiveIntegerField(default=0, verbose_name="Цель по лидам (в месяц)")
    conversion_target = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Цель по конверсии (%)")
    
    class Meta:
        verbose_name = "Маркетолог"
        verbose_name_plural = "Маркетологи"
        indexes = [
            models.Index(fields=['full_name']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['specialization']),
        ]
        
    def __str__(self):
        return self.full_name