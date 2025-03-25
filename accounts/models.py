from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('admin', 'Admin'),
        ('reception', 'Reception'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
        ('parent', 'Parent'),
    )
    
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    
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
    def is_parent(self):
        return self.user_type == 'parent'
        
    def get_full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    full_name = models.CharField(max_length=100)
    birth_date = models.DateField()
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    docs_link = models.URLField(blank=True, null=True, verbose_name="Ссылка на документы")
    
    def __str__(self):
        return self.full_name

class Reception(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='reception_profile')
    full_name = models.CharField(max_length=100)
    birth_date = models.DateField()
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    docs_link = models.URLField(blank=True, null=True, verbose_name="Ссылка на документы")
    
    def __str__(self):
        return self.full_name

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    full_name = models.CharField(max_length=100)
    birth_date = models.DateField()
    school = models.CharField(max_length=100)
    graduation_year = models.IntegerField()
    school_start_year = models.IntegerField()
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    parent = models.ForeignKey('Parent', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    
    def __str__(self):
        return self.full_name

class Parent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parent_profile')
    full_name = models.CharField(max_length=100, default="Родитель")
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    
    def __str__(self):
        return self.full_name