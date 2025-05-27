from django import forms
from accounts.models import User, Student

class FaceRegistrationForm(forms.Form):
    """Форма для регистрации лица пользователя"""
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        label="Пользователь"
    )
    
    # Это поле будет использоваться только для отображения предварительного просмотра камеры
    # и не будет отправлено на сервер
    face_image_preview = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    # Это поле будет содержать закодированные данные лица
    face_data = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        user_type = kwargs.pop('user_type', None)
        super().__init__(*args, **kwargs)
        
        # Фильтруем пользователей по типу, если указан
        if user_type:
            self.fields['user'].queryset = User.objects.filter(user_type=user_type)

class FaceAttendanceForm(forms.Form):
    """Форма для отметки посещаемости через распознавание лиц"""
    class_id = forms.IntegerField(widget=forms.HiddenInput())
    date = forms.DateField(widget=forms.HiddenInput())
    
    # Это поле будет использоваться только для отображения предварительного просмотра камеры
    face_image_preview = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
