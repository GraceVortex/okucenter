from django import forms
from .models import Class, ClassSchedule, Homework, HomeworkSubmission, Enrollment
from accounts.models import Student

class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ['name', 'teacher', 'price_per_lesson', 'teacher_payment_type', 'teacher_percentage', 'teacher_fixed_payment', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'teacher_percentage': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': 1, 'class': 'percentage-field'}),
            'teacher_fixed_payment': forms.NumberInput(attrs={'min': 0, 'step': 100, 'class': 'fixed-payment-field'}),
            'teacher_payment_type': forms.RadioSelect(),
        }
        labels = {
            'teacher_payment_type': 'Тип оплаты преподавателя',
            'teacher_percentage': 'Процент преподавателя (%)',
            'teacher_fixed_payment': 'Фиксированная оплата (₸)',
        }
        help_texts = {
            'teacher_percentage': 'Процент от стоимости занятия, который получает преподаватель',
            'teacher_fixed_payment': 'Фиксированная сумма за проведение одного занятия',
        }

class ClassScheduleForm(forms.ModelForm):
    # Добавляем множественный выбор дней недели
    DAYS_OF_WEEK = [
        (0, 'Понедельник'),
        (1, 'Вторник'),
        (2, 'Среда'),
        (3, 'Четверг'),
        (4, 'Пятница'),
        (5, 'Суббота'),
        (6, 'Воскресенье'),
    ]
    
    days_of_week = forms.MultipleChoiceField(
        choices=DAYS_OF_WEEK,
        widget=forms.CheckboxSelectMultiple,
        label='Дни недели'
    )
    
    # Фиксированные временные интервалы
    TIME_SLOTS = [
        ('08:00:00', '08:00 - 09:30'),
        ('09:30:00', '09:30 - 11:00'),
        ('11:00:00', '11:00 - 12:30'),
        ('14:30:00', '14:30 - 16:00'),
        ('16:00:00', '16:00 - 17:30'),
        ('17:30:00', '17:30 - 19:00'),
        ('19:00:00', '19:00 - 20:30'),
    ]
    
    time_slot = forms.ChoiceField(
        choices=TIME_SLOTS,
        label='Временной интервал'
    )
    
    class Meta:
        model = ClassSchedule
        fields = ['room']
        
    def clean_time_slot(self):
        """Разбивает выбранный временной интервал на время начала и окончания."""
        time_slot = self.cleaned_data['time_slot']
        # Время окончания вычисляется автоматически (начало + 1.5 часа)
        return time_slot

class HomeworkForm(forms.ModelForm):
    class Meta:
        model = Homework
        fields = ['date', 'description', 'file']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }

class HomeworkSubmissionForm(forms.ModelForm):
    class Meta:
        model = HomeworkSubmission
        fields = ['file']

class HomeworkGradeForm(forms.ModelForm):
    class Meta:
        model = HomeworkSubmission
        fields = ['completion_status', 'teacher_comment']
        widgets = {
            'teacher_comment': forms.Textarea(attrs={'rows': 3, 'maxlength': 150}),
        }

class AddStudentForm(forms.Form):
    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label='Выберите студентов'
    )
