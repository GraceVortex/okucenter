import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Проверяем, существует ли уже пользователь с именем admin
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='admin123',
        user_type='admin'
    )
    print('Суперпользователь успешно создан!')
else:
    print('Суперпользователь с именем admin уже существует.')
