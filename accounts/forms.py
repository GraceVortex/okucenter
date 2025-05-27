from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Teacher, Student, Parent, Reception, Marketer

class TeacherForm(forms.ModelForm):
    """Форма для создания и редактирования преподавателя"""
    username = forms.CharField(label='Имя пользователя', max_length=150)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    email = forms.EmailField(label='Email', required=False)
    face_image = forms.ImageField(label='Фото для FaceID', required=False)
    
    class Meta:
        model = Teacher
        fields = ['full_name', 'birth_date', 'phone_number', 'docs_link', 'face_image']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'full_name': 'ФИО',
            'birth_date': 'Дата рождения',
            'phone_number': 'Номер телефона',
            'docs_link': 'Ссылка на Google Docs',
            'face_image': 'Фото для FaceID',
        }
    
    def save(self, commit=True):
        # Создаем пользователя
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            password=self.cleaned_data['password'],
            email=self.cleaned_data.get('email', ''),
            user_type='teacher'
        )
        
        # Создаем преподавателя
        teacher = super().save(commit=False)
        teacher.user = user
        teacher.face_image = self.cleaned_data.get('face_image')
        if commit:
            teacher.save()
        return teacher

class ReceptionForm(forms.ModelForm):
    """Форма для создания и редактирования ресепшениста"""
    username = forms.CharField(label='Имя пользователя', max_length=150)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    email = forms.EmailField(label='Email', required=False)
    face_image = forms.ImageField(label='Фото для FaceID', required=False)
    
    class Meta:
        model = Reception
        fields = ['full_name', 'birth_date', 'phone_number', 'docs_link', 'face_image']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'full_name': 'ФИО',
            'birth_date': 'Дата рождения',
            'phone_number': 'Номер телефона',
            'docs_link': 'Ссылка на Google Docs',
            'face_image': 'Фото для FaceID',
        }
    
    def save(self, commit=True):
        # Создаем пользователя
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            password=self.cleaned_data['password'],
            email=self.cleaned_data.get('email', ''),
            user_type='reception'
        )
        
        # Создаем ресепшениста
        reception = super().save(commit=False)
        reception.user = user
        reception.face_image = self.cleaned_data.get('face_image')
        if commit:
            reception.save()
        return reception

class ParentForm(forms.ModelForm):
    """Форма для создания и редактирования родителя"""
    username = forms.CharField(label='Имя пользователя', max_length=150)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    email = forms.EmailField(label='Email', required=False)
    
    class Meta:
        model = Parent
        fields = ['full_name', 'phone_number']
        labels = {
            'full_name': 'ФИО',
            'phone_number': 'Номер телефона',
        }
    
    def save(self, commit=True):
        # Создаем пользователя
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            password=self.cleaned_data['password'],
            email=self.cleaned_data.get('email', ''),
            user_type='parent'
        )
        
        # Создаем родителя
        parent = super().save(commit=False)
        parent.user = user
        
        if commit:
            parent.save()
        
        return parent

class MarketerForm(forms.ModelForm):
    """Форма для создания и редактирования маркетолога"""
    username = forms.CharField(label='Имя пользователя', max_length=150)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    email = forms.EmailField(label='Email', required=False)
    
    class Meta:
        model = Marketer
        fields = ['full_name', 'birth_date', 'phone_number', 'email', 'docs_link']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'full_name': 'ФИО',
            'birth_date': 'Дата рождения',
            'phone_number': 'Номер телефона',
            'email': 'Email',
            'docs_link': 'Ссылка на документы',
        }
    
    def save(self, commit=True):
        # Создаем пользователя
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            password=self.cleaned_data['password'],
            email=self.cleaned_data.get('email', ''),
            user_type='marketer'
        )
        
        # Создаем маркетолога
        marketer = super().save(commit=False)
        marketer.user = user
        if commit:
            marketer.save()
        return marketer

class StudentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Показывать только уникальных настоящих родителей
        self.fields['parent'].queryset = Parent.objects.filter(parent_type='parent').distinct()

    """Форма для создания и редактирования студента"""
    face_image = forms.ImageField(label='Фото для FaceID', required=False, help_text='Загрузите фото лица для распознавания')
    username = forms.CharField(label='Имя пользователя', max_length=150)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput, required=False)
    email = forms.EmailField(label='Email', required=False)
    
    # Поле для указания, нужен ли родитель
    needs_parent = forms.BooleanField(label='Нужен родитель', required=False, initial=True)
    
    # Поля для создания нового родителя
    create_parent = forms.BooleanField(label='Создать нового родителя', required=False, initial=False)
    parent_full_name = forms.CharField(label='ФИО родителя', max_length=100, required=False)
    parent_phone_number = forms.CharField(label='Номер телефона родителя', max_length=20, required=False)
    parent_username = forms.CharField(label='Имя пользователя родителя', max_length=150, required=False)
    parent_password = forms.CharField(label='Пароль родителя', widget=forms.PasswordInput, required=False)
    parent_email = forms.EmailField(label='Email родителя', required=False)
    
    class Meta:
        model = Student
        fields = ['full_name', 'birth_date', 'school', 'current_grade', 'graduation_year', 'phone_number', 'parent', 'is_self_managed']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'current_grade': forms.Select(choices=[(i, f"{i} класс") for i in range(1, 12)]),
        }
        labels = {
            'full_name': 'ФИО',
            'birth_date': 'Дата рождения',
            'school': 'Школа',
            'current_grade': 'Текущий класс',
            'graduation_year': 'Год выпуска',
            'phone_number': 'Номер телефона',
            'parent': 'Родитель',
            'is_self_managed': 'Самоуправляемый',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        needs_parent = cleaned_data.get('needs_parent')
        create_parent = cleaned_data.get('create_parent')
        parent = cleaned_data.get('parent')
        is_self_managed = cleaned_data.get('is_self_managed')
        
        # Если ученик самоуправляемый, то родитель не нужен
        if is_self_managed:
            return cleaned_data
            
        # Если ученик не самоуправляемый и нужен родитель
        if needs_parent:
            # Если не выбран существующий родитель и не выбрано создание нового родителя
            if not parent and not create_parent:
                self.add_error('parent', 'Необходимо выбрать родителя или создать нового.')
        
        # Если выбрано создание нового родителя, проверяем, что все необходимые поля заполнены
        if create_parent:
            parent_full_name = cleaned_data.get('parent_full_name')
            parent_phone_number = cleaned_data.get('parent_phone_number')
            parent_username = cleaned_data.get('parent_username')
            parent_password = cleaned_data.get('parent_password')
            
            if not parent_full_name:
                self.add_error('parent_full_name', 'Это поле обязательно при создании нового родителя.')
            if not parent_phone_number:
                self.add_error('parent_phone_number', 'Это поле обязательно при создании нового родителя.')
            if not parent_username:
                self.add_error('parent_username', 'Это поле обязательно при создании нового родителя.')
            if not parent_password:
                self.add_error('parent_password', 'Это поле обязательно при создании нового родителя.')
        
        return cleaned_data
    
    def save(self, commit=True):
        # Проверяем, создаем нового студента или редактируем существующего
        if not self.instance.pk:  # Если это новый студент (нет primary key)
            # Создаем пользователя
            user = User.objects.create_user(
                username=self.cleaned_data['username'],
                password=self.cleaned_data['password'],
                email=self.cleaned_data.get('email', ''),
                user_type='student'
            )
            
            # Создаем студента
            student = super().save(commit=False)
            student.user = user
            student.face_image = self.cleaned_data.get('face_image')
        else:
            # Редактируем существующего студента
            student = super().save(commit=False)
            student.face_image = self.cleaned_data.get('face_image') or student.face_image
        
        # Проверяем, нужен ли родитель
        needs_parent = self.cleaned_data.get('needs_parent', False)
        is_self_managed = self.cleaned_data.get('is_self_managed', False)
        
        # Если ученик самоуправляемый, устанавливаем флаг
        if is_self_managed:
            student.is_self_managed = True
            student.parent = None
        # Если нужен родитель
        elif needs_parent:
            # Если выбран существующий родитель
            if self.cleaned_data.get('parent'):
                student.parent = self.cleaned_data['parent']
                student.is_self_managed = False
            # Если нужно создать нового родителя
            elif self.cleaned_data.get('create_parent'):
                try:
                    # Создаем пользователя для родителя
                    parent_user = User.objects.create_user(
                        username=self.cleaned_data['parent_username'],
                        password=self.cleaned_data['parent_password'],
                        email=self.cleaned_data.get('parent_email', ''),
                        user_type='parent'
                    )
                    
                    # Создаем родителя с типом 'parent'
                    parent = Parent(
                        user=parent_user,
                        full_name=self.cleaned_data['parent_full_name'],
                        phone_number=self.cleaned_data['parent_phone_number'],
                        parent_type='parent'  # Указываем, что это настоящий родитель
                    )
                    parent.save()
                    
                    # Привязываем родителя к студенту
                    student.parent = parent
                    student.is_self_managed = False
                except Exception as e:
                    # Если возникла ошибка, логируем её
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error creating parent for student: {str(e)}")
                    # Устанавливаем флаг самоуправляемости в случае ошибки
                    student.is_self_managed = True
        # Если не выбран ни родитель, ни самоуправляемость - устанавливаем самоуправляемость в False
        else:
            student.is_self_managed = False
        
        if commit:
            student.save()
        
        return student
