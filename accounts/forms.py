from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Teacher, Student, Parent, Reception

class TeacherForm(forms.ModelForm):
    """Форма для создания и редактирования преподавателя"""
    username = forms.CharField(label='Имя пользователя', max_length=150)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    email = forms.EmailField(label='Email', required=False)
    
    class Meta:
        model = Teacher
        fields = ['full_name', 'birth_date', 'phone_number', 'docs_link']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'full_name': 'ФИО',
            'birth_date': 'Дата рождения',
            'phone_number': 'Номер телефона',
            'docs_link': 'Ссылка на Google Docs',
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
        
        if commit:
            teacher.save()
        
        return teacher

class ReceptionForm(forms.ModelForm):
    """Форма для создания и редактирования ресепшениста"""
    username = forms.CharField(label='Имя пользователя', max_length=150)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    email = forms.EmailField(label='Email', required=False)
    
    class Meta:
        model = Reception
        fields = ['full_name', 'birth_date', 'phone_number', 'docs_link']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'full_name': 'ФИО',
            'birth_date': 'Дата рождения',
            'phone_number': 'Номер телефона',
            'docs_link': 'Ссылка на Google Docs',
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

class StudentForm(forms.ModelForm):
    """Форма для создания и редактирования студента"""
    username = forms.CharField(label='Имя пользователя', max_length=150)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput, required=False)
    email = forms.EmailField(label='Email', required=False)
    
    # Поля для создания нового родителя
    create_parent = forms.BooleanField(label='Создать нового родителя', required=False, initial=False)
    parent_full_name = forms.CharField(label='ФИО родителя', max_length=100, required=False)
    parent_phone_number = forms.CharField(label='Номер телефона родителя', max_length=20, required=False)
    parent_username = forms.CharField(label='Имя пользователя родителя', max_length=150, required=False)
    parent_password = forms.CharField(label='Пароль родителя', widget=forms.PasswordInput, required=False)
    parent_email = forms.EmailField(label='Email родителя', required=False)
    
    class Meta:
        model = Student
        fields = ['full_name', 'birth_date', 'school', 'graduation_year', 'school_start_year', 'phone_number', 'parent']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'full_name': 'ФИО',
            'birth_date': 'Дата рождения',
            'school': 'Школа',
            'graduation_year': 'Год выпуска',
            'school_start_year': 'Год начала обучения',
            'phone_number': 'Номер телефона',
            'parent': 'Родитель',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        create_parent = cleaned_data.get('create_parent')
        
        if create_parent:
            # Проверяем, что все необходимые поля для создания родителя заполнены
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
        else:
            # Редактируем существующего студента
            student = super().save(commit=False)
        
        # Если нужно создать нового родителя
        if self.cleaned_data.get('create_parent'):
            # Создаем пользователя для родителя
            parent_user = User.objects.create_user(
                username=self.cleaned_data['parent_username'],
                password=self.cleaned_data['parent_password'],
                email=self.cleaned_data.get('parent_email', ''),
                user_type='parent'
            )
            
            # Создаем родителя
            parent = Parent(
                user=parent_user,
                full_name=self.cleaned_data['parent_full_name'],
                phone_number=self.cleaned_data['parent_phone_number']
            )
            parent.save()
            
            # Привязываем родителя к студенту
            student.parent = parent
        
        if commit:
            student.save()
        
        return student
