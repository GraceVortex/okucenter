import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission

User = get_user_model()

# Создаем суперпользователя
if not User.objects.filter(username='admin').exists():
    user = User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='admin123',
        is_staff=True,
        is_superuser=True
    )
    print(f"Суперпользователь 'admin' создан с паролем 'admin123'")
else:
    print("Пользователь 'admin' уже существует")
