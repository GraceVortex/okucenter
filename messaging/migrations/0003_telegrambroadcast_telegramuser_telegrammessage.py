# Generated by Django 4.2.7 on 2025-05-02 13:38

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_alter_student_face_image'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('classes', '0010_alter_class_options_alter_classschedule_options_and_more'),
        ('messaging', '0002_whatsappbroadcast_whatsappmessage'),
    ]

    operations = [
        migrations.CreateModel(
            name='TelegramBroadcast',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Название рассылки')),
                ('message', models.TextField(verbose_name='Текст сообщения')),
                ('recipient_type', models.CharField(choices=[('students', 'Студенты'), ('parents', 'Родители'), ('both', 'Родители и студенты'), ('teachers', 'Преподаватели'), ('all', 'Все')], default='both', max_length=20, verbose_name='Тип получателей')),
                ('target_day', models.IntegerField(blank=True, null=True, verbose_name='День недели')),
                ('media_file', models.FileField(blank=True, null=True, upload_to='telegram_media/', verbose_name='Медиа-файл')),
                ('media_type', models.CharField(blank=True, max_length=20, null=True, verbose_name='Тип медиа')),
                ('has_buttons', models.BooleanField(default=False, verbose_name='Есть кнопки')),
                ('buttons_json', models.TextField(blank=True, null=True, verbose_name='JSON кнопок')),
                ('status', models.CharField(choices=[('draft', 'Черновик'), ('scheduled', 'Запланировано'), ('in_progress', 'В процессе'), ('completed', 'Завершено'), ('failed', 'Ошибка')], default='draft', max_length=20, verbose_name='Статус')),
                ('scheduled_at', models.DateTimeField(blank=True, null=True, verbose_name='Запланировано на')),
                ('sent_at', models.DateTimeField(blank=True, null=True, verbose_name='Отправлено')),
                ('total_recipients', models.IntegerField(default=0, verbose_name='Всего получателей')),
                ('successful_sent', models.IntegerField(default=0, verbose_name='Успешно отправлено')),
                ('failed_sent', models.IntegerField(default=0, verbose_name='Ошибок при отправке')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='telegram_broadcasts', to=settings.AUTH_USER_MODEL, verbose_name='Создатель')),
                ('target_class', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='telegram_broadcasts', to='classes.class', verbose_name='Класс')),
                ('target_schedule', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='telegram_broadcasts', to='classes.classschedule', verbose_name='Расписание')),
            ],
            options={
                'verbose_name': 'Telegram рассылка',
                'verbose_name_plural': 'Telegram рассылки',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TelegramUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telegram_id', models.CharField(max_length=20, unique=True, verbose_name='Telegram ID')),
                ('username', models.CharField(blank=True, max_length=100, null=True, verbose_name='Username')),
                ('first_name', models.CharField(blank=True, max_length=100, null=True, verbose_name='Имя')),
                ('last_name', models.CharField(blank=True, max_length=100, null=True, verbose_name='Фамилия')),
                ('phone', models.CharField(blank=True, max_length=20, null=True, verbose_name='Телефон')),
                ('role', models.CharField(choices=[('student', 'Студент'), ('parent', 'Родитель'), ('teacher', 'Преподаватель'), ('admin', 'Администратор'), ('reception', 'Ресепшн'), ('unknown', 'Неизвестно')], default='unknown', max_length=20, verbose_name='Роль')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='telegram_accounts', to='accounts.parent', verbose_name='Родитель')),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='telegram_accounts', to='accounts.student', verbose_name='Студент')),
            ],
            options={
                'verbose_name': 'Пользователь Telegram',
                'verbose_name_plural': 'Пользователи Telegram',
            },
        ),
        migrations.CreateModel(
            name='TelegramMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recipient_type', models.CharField(max_length=20, verbose_name='Тип получателя')),
                ('status', models.CharField(choices=[('pending', 'Ожидает отправки'), ('sent', 'Отправлено'), ('delivered', 'Доставлено'), ('read', 'Прочитано'), ('failed', 'Ошибка')], default='pending', max_length=20, verbose_name='Статус')),
                ('telegram_message_id', models.CharField(blank=True, max_length=50, null=True, verbose_name='ID сообщения в Telegram')),
                ('sent_at', models.DateTimeField(blank=True, null=True, verbose_name='Время отправки')),
                ('delivered_at', models.DateTimeField(blank=True, null=True, verbose_name='Время доставки')),
                ('read_at', models.DateTimeField(blank=True, null=True, verbose_name='Время прочтения')),
                ('error_message', models.TextField(blank=True, null=True, verbose_name='Сообщение об ошибке')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('broadcast', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='messaging.telegrambroadcast', verbose_name='Рассылка')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='telegram_messages', to='accounts.parent', verbose_name='Родитель')),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='messaging.telegramuser', verbose_name='Получатель')),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='telegram_messages', to='accounts.student', verbose_name='Студент')),
            ],
            options={
                'verbose_name': 'Сообщение Telegram',
                'verbose_name_plural': 'Сообщения Telegram',
                'ordering': ['-created_at'],
            },
        ),
    ]
