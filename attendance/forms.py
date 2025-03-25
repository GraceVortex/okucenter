from django import forms
from django.utils import timezone
from .models import Attendance, Mark, CancellationRequest
from classes.models import Class
from accounts.models import Student, Teacher

class AttendanceForm(forms.ModelForm):
    """Форма для отметки посещаемости."""
    
    class Meta:
        model = Attendance
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

class MarkForm(forms.ModelForm):
    """Форма для добавления оценок и комментариев."""
    
    class Meta:
        model = Mark
        fields = ['homework_mark', 'activity_mark', 'teacher_comment']
        widgets = {
            'homework_mark': forms.Select(attrs={'class': 'form-select'}),
            'activity_mark': forms.Select(attrs={'class': 'form-select'}),
            'teacher_comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'maxlength': 150}),
        }
        
    def clean_teacher_comment(self):
        comment = self.cleaned_data.get('teacher_comment')
        if comment and len(comment) > 150:
            raise forms.ValidationError("Комментарий не может быть длиннее 150 символов.")
        return comment

class AttendanceFilterForm(forms.Form):
    """Форма для фильтрации списка посещаемости."""
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class_obj = forms.ModelChoiceField(
        queryset=Class.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    status = forms.ChoiceField(
        choices=[('', 'Все статусы')] + list(Attendance.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        # Если указана только одна дата, устанавливаем вторую
        if start_date and not end_date:
            cleaned_data['end_date'] = timezone.now().date()
        elif end_date and not start_date:
            cleaned_data['start_date'] = end_date - timezone.timedelta(days=30)
        
        # Проверяем, что начальная дата не позже конечной
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError("Начальная дата не может быть позже конечной.")
        
        return cleaned_data

class CancelAttendanceForm(forms.Form):
    """Форма для отмены подтвержденного посещения."""
    
    reason = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Укажите причину отмены посещения (макс. 50 слов)'
        }),
        help_text='Максимум 50 слов'
    )
    
    def clean_reason(self):
        reason = self.cleaned_data.get('reason')
        if reason:
            # Проверяем, что причина не превышает 50 слов
            words = reason.split()
            if len(words) > 50:
                raise forms.ValidationError("Причина не должна превышать 50 слов.")
        return reason

class CancellationRequestForm(forms.ModelForm):
    """Форма для запроса на отмену урока учителем."""
    
    needs_substitute = forms.BooleanField(
        required=False,
        label="Требуется заменяющий учитель",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'needs_substitute'})
    )
    
    substitute_teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.all(),
        required=False,
        label="Заменяющий учитель",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'substitute_teacher'})
    )
    
    class Meta:
        model = CancellationRequest
        fields = ['reason', 'needs_substitute', 'substitute_teacher']
        widgets = {
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Укажите причину отмены урока (макс. 50 слов)'
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        needs_substitute = cleaned_data.get('needs_substitute')
        substitute_teacher = cleaned_data.get('substitute_teacher')
        
        if needs_substitute and not substitute_teacher:
            self.add_error('substitute_teacher', "Выберите заменяющего учителя")
        
        return cleaned_data
    
    def clean_reason(self):
        reason = self.cleaned_data.get('reason')
        if reason:
            # Проверяем, что причина не превышает 50 слов
            words = reason.split()
            if len(words) > 50:
                raise forms.ValidationError("Причина не должна превышать 50 слов.")
        return reason

class ApproveCancellationForm(forms.Form):
    """Форма для подтверждения отмены урока администратором или ресепшн."""
    
    approve = forms.BooleanField(
        required=False,
        label="Подтвердить отмену",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    substitute_teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.all(),
        required=False,
        label="Заменяющий учитель",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        approve = cleaned_data.get('approve')
        substitute_teacher = cleaned_data.get('substitute_teacher')
        
        if not approve and not substitute_teacher:
            raise forms.ValidationError("Вы должны либо подтвердить отмену, либо назначить заменяющего учителя")
        
        return cleaned_data
