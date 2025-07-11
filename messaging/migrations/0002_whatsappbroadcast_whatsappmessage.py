# Generated by Django 4.2.7 on 2025-05-02 11:23

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('classes', '0010_alter_class_options_alter_classschedule_options_and_more'),
        ('messaging', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='WhatsAppBroadcast',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Название рассылки')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('scheduled_at', models.DateTimeField(blank=True, null=True, verbose_name='Запланировано на')),
                ('message', models.TextField(verbose_name='Текст сообщения')),
                ('media_file', models.FileField(blank=True, null=True, upload_to='whatsapp_media/', verbose_name='Медиа-файл')),
                ('target_day', models.IntegerField(blank=True, choices=[(0, 'Понедельник'), (1, 'Вторник'), (2, 'Среда'), (3, 'Четверг'), (4, 'Пятница'), (5, 'Суббота'), (6, 'Воскресенье')], null=True, verbose_name='День недели')),
                ('recipient_type', models.CharField(choices=[('parents', 'Родители'), ('students', 'Студенты'), ('both', 'Родители и студенты')], default='parents', max_length=10, verbose_name='Тип получателей')),
                ('status', models.CharField(choices=[('draft', 'Черновик'), ('scheduled', 'Запланировано'), ('in_progress', 'В процессе'), ('completed', 'Завершено'), ('failed', 'Ошибка')], default='draft', max_length=15, verbose_name='Статус')),
                ('total_recipients', models.IntegerField(default=0, verbose_name='Всего получателей')),
                ('successful_sent', models.IntegerField(default=0, verbose_name='Успешно отправлено')),
                ('failed_sent', models.IntegerField(default=0, verbose_name='Ошибок отправки')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='whatsapp_broadcasts', to=settings.AUTH_USER_MODEL)),
                ('target_class', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='classes.class', verbose_name='Класс')),
                ('target_schedule', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='classes.classschedule', verbose_name='Расписание')),
            ],
            options={
                'verbose_name': 'Рассылка WhatsApp',
                'verbose_name_plural': 'Рассылки WhatsApp',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='WhatsAppMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recipient_type', models.CharField(choices=[('parent', 'Родитель'), ('student', 'Студент')], max_length=10)),
                ('recipient_id', models.IntegerField()),
                ('recipient_name', models.CharField(max_length=255)),
                ('recipient_phone', models.CharField(max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Ожидает отправки'), ('sent', 'Отправлено'), ('delivered', 'Доставлено'), ('read', 'Прочитано'), ('failed', 'Ошибка')], default='pending', max_length=15)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('whatsapp_message_id', models.CharField(blank=True, max_length=255, null=True)),
                ('broadcast', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='messaging.whatsappbroadcast')),
            ],
            options={
                'verbose_name': 'Сообщение WhatsApp',
                'verbose_name_plural': 'Сообщения WhatsApp',
                'ordering': ['-created_at'],
            },
        ),
    ]
