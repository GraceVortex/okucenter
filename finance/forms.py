from django import forms
from django.utils import timezone
from .models import Transaction
from accounts.models import Student
from classes.models import Class

class TransactionForm(forms.ModelForm):
    """Форма для добавления транзакций."""
    
    class Meta:
        model = Transaction
        fields = ['student', 'amount', 'description', 'transaction_type', 'class_obj']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'class_obj': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['class_obj'].required = False
        self.fields['class_obj'].label = "Класс (необязательно)"
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise forms.ValidationError("Сумма должна быть положительным числом.")
        return amount

class DepositForm(forms.Form):
    """Форма для пополнения баланса студента."""
    
    amount = forms.DecimalField(
        min_value=0.01,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
        label="Сумма пополнения"
    )
    
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        label="Описание",
        required=False,
        initial="Пополнение баланса"
    )
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise forms.ValidationError("Сумма пополнения должна быть положительным числом.")
        return amount

class TransactionFilterForm(forms.Form):
    """Форма для фильтрации списка транзакций."""
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Начальная дата"
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Конечная дата"
    )
    
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Студент"
    )
    
    class_obj = forms.ModelChoiceField(
        queryset=Class.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Класс"
    )
    
    transaction_type = forms.ChoiceField(
        choices=[('', '---------')] + list(Transaction.TRANSACTION_TYPES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Тип транзакции"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Установка начальных значений
        if not self.is_bound:  # Если форма не была отправлена
            self.fields['start_date'].initial = timezone.now().date() - timezone.timedelta(days=30)
            self.fields['end_date'].initial = timezone.now().date()

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
