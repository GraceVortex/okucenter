# Generated by Django 4.2.7 on 2025-04-22 11:42

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_alter_parent_options_alter_reception_options_and_more'),
        ('classes', '0009_auto_20250421_0116'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='class',
            options={'verbose_name': 'Класс', 'verbose_name_plural': 'Классы'},
        ),
        migrations.AlterModelOptions(
            name='classschedule',
            options={'verbose_name': 'Расписание', 'verbose_name_plural': 'Расписания'},
        ),
        migrations.AlterModelOptions(
            name='classworkfile',
            options={'ordering': ['-date'], 'verbose_name': 'Материал занятия', 'verbose_name_plural': 'Материалы занятий'},
        ),
        migrations.AlterModelOptions(
            name='enrollment',
            options={'verbose_name': 'Зачисление', 'verbose_name_plural': 'Зачисления'},
        ),
        migrations.AlterModelOptions(
            name='homework',
            options={'ordering': ['-due_date'], 'verbose_name': 'Домашнее задание', 'verbose_name_plural': 'Домашние задания'},
        ),
        migrations.AlterModelOptions(
            name='homeworksubmission',
            options={'ordering': ['-submission_date'], 'verbose_name': 'Выполненное домашнее задание', 'verbose_name_plural': 'Выполненные домашние задания'},
        ),
        migrations.AddField(
            model_name='classworkfile',
            name='title',
            field=models.CharField(default='Материал занятия', max_length=255, verbose_name='Название'),
        ),
        migrations.AlterField(
            model_name='class',
            name='description',
            field=models.TextField(blank=True, null=True, verbose_name='Описание'),
        ),
        migrations.AlterField(
            model_name='class',
            name='name',
            field=models.CharField(db_index=True, max_length=100, verbose_name='Название'),
        ),
        migrations.AlterField(
            model_name='class',
            name='price_per_lesson',
            field=models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Стоимость занятия'),
        ),
        migrations.AlterField(
            model_name='class',
            name='teacher',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='classes', to='accounts.teacher', verbose_name='Преподаватель'),
        ),
        migrations.AlterField(
            model_name='class',
            name='teacher_fixed_payment',
            field=models.DecimalField(decimal_places=2, default=0, help_text='Фиксированная оплата преподавателя за занятие', max_digits=10, verbose_name='Фиксированная оплата'),
        ),
        migrations.AlterField(
            model_name='class',
            name='teacher_payment_type',
            field=models.CharField(choices=[('percentage', 'Процент от стоимости урока'), ('fixed', 'Фиксированная оплата')], default='percentage', help_text='Тип оплаты преподавателя', max_length=10, verbose_name='Тип оплаты преподавателя'),
        ),
        migrations.AlterField(
            model_name='class',
            name='teacher_percentage',
            field=models.IntegerField(default=0, help_text='Процент от стоимости занятия, который получает преподаватель', verbose_name='Процент преподавателя'),
        ),
        migrations.AlterField(
            model_name='classschedule',
            name='class_obj',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='schedules', to='classes.class', verbose_name='Класс'),
        ),
        migrations.AlterField(
            model_name='classschedule',
            name='day_of_week',
            field=models.IntegerField(choices=[(0, 'Понедельник'), (1, 'Вторник'), (2, 'Среда'), (3, 'Четверг'), (4, 'Пятница'), (5, 'Суббота'), (6, 'Воскресенье')], db_index=True, verbose_name='День недели'),
        ),
        migrations.AlterField(
            model_name='classschedule',
            name='end_time',
            field=models.TimeField(verbose_name='Время окончания'),
        ),
        migrations.AlterField(
            model_name='classschedule',
            name='room',
            field=models.IntegerField(db_index=True, help_text='Номер кабинета', verbose_name='Кабинет'),
        ),
        migrations.AlterField(
            model_name='classschedule',
            name='start_time',
            field=models.TimeField(db_index=True, verbose_name='Время начала'),
        ),
        migrations.AlterField(
            model_name='classworkfile',
            name='class_obj',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='classwork_files', to='classes.class', verbose_name='Класс'),
        ),
        migrations.AlterField(
            model_name='classworkfile',
            name='date',
            field=models.DateField(db_index=True, verbose_name='Дата'),
        ),
        migrations.AlterField(
            model_name='classworkfile',
            name='description',
            field=models.TextField(blank=True, null=True, verbose_name='Описание'),
        ),
        migrations.AlterField(
            model_name='classworkfile',
            name='file',
            field=models.FileField(upload_to='classwork_files/', verbose_name='Файл'),
        ),
        migrations.AlterField(
            model_name='enrollment',
            name='class_obj',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='classes.class', verbose_name='Класс'),
        ),
        migrations.AlterField(
            model_name='enrollment',
            name='enrollment_date',
            field=models.DateField(auto_now_add=True, db_index=True, verbose_name='Дата зачисления'),
        ),
        migrations.AlterField(
            model_name='enrollment',
            name='student',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='accounts.student', verbose_name='Ученик'),
        ),
        migrations.AlterField(
            model_name='homework',
            name='class_obj',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='homework', to='classes.class', verbose_name='Класс'),
        ),
        migrations.AlterField(
            model_name='homework',
            name='description',
            field=models.TextField(blank=True, default='', verbose_name='Описание'),
        ),
        migrations.AlterField(
            model_name='homework',
            name='due_date',
            field=models.DateField(db_index=True, default=django.utils.timezone.now, verbose_name='Дедлайн'),
        ),
        migrations.AlterField(
            model_name='homework',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to='homework_files/', verbose_name='Файл'),
        ),
        migrations.AlterField(
            model_name='homework',
            name='title',
            field=models.CharField(max_length=255, verbose_name='Название'),
        ),
        migrations.AlterField(
            model_name='homeworksubmission',
            name='completion_status',
            field=models.CharField(blank=True, choices=[('completed', 'Выполнено'), ('partially_completed', 'Частично выполнено'), ('not_completed', 'Не выполнено')], db_index=True, max_length=20, null=True, verbose_name='Статус выполнения'),
        ),
        migrations.AlterField(
            model_name='homeworksubmission',
            name='file',
            field=models.FileField(upload_to='homework_submissions/', verbose_name='Файл'),
        ),
        migrations.AlterField(
            model_name='homeworksubmission',
            name='homework',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submissions', to='classes.homework', verbose_name='Домашнее задание'),
        ),
        migrations.AlterField(
            model_name='homeworksubmission',
            name='student',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='homework_submissions', to='accounts.student', verbose_name='Ученик'),
        ),
        migrations.AlterField(
            model_name='homeworksubmission',
            name='submission_date',
            field=models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Дата отправки'),
        ),
        migrations.AlterField(
            model_name='homeworksubmission',
            name='teacher_comment',
            field=models.TextField(blank=True, null=True, verbose_name='Комментарий преподавателя'),
        ),
        migrations.AlterUniqueTogether(
            name='homeworksubmission',
            unique_together={('homework', 'student')},
        ),
        migrations.AddIndex(
            model_name='class',
            index=models.Index(fields=['name'], name='classes_cla_name_397963_idx'),
        ),
        migrations.AddIndex(
            model_name='class',
            index=models.Index(fields=['teacher'], name='classes_cla_teacher_9fb511_idx'),
        ),
        migrations.AddIndex(
            model_name='classschedule',
            index=models.Index(fields=['day_of_week', 'start_time'], name='classes_cla_day_of__0fa227_idx'),
        ),
        migrations.AddIndex(
            model_name='classschedule',
            index=models.Index(fields=['class_obj', 'day_of_week'], name='classes_cla_class_o_c7608c_idx'),
        ),
        migrations.AddIndex(
            model_name='classschedule',
            index=models.Index(fields=['room', 'day_of_week', 'start_time'], name='classes_cla_room_fd691c_idx'),
        ),
        migrations.AddIndex(
            model_name='classworkfile',
            index=models.Index(fields=['class_obj', '-date'], name='classes_cla_class_o_b6fc0c_idx'),
        ),
        migrations.AddIndex(
            model_name='classworkfile',
            index=models.Index(fields=['-date'], name='classes_cla_date_697f94_idx'),
        ),
        migrations.AddIndex(
            model_name='enrollment',
            index=models.Index(fields=['student', 'is_active'], name='classes_enr_student_917800_idx'),
        ),
        migrations.AddIndex(
            model_name='enrollment',
            index=models.Index(fields=['class_obj', 'is_active'], name='classes_enr_class_o_a25c89_idx'),
        ),
        migrations.AddIndex(
            model_name='enrollment',
            index=models.Index(fields=['enrollment_date'], name='classes_enr_enrollm_262893_idx'),
        ),
        migrations.AddIndex(
            model_name='homework',
            index=models.Index(fields=['class_obj', '-due_date'], name='classes_hom_class_o_f53cb9_idx'),
        ),
        migrations.AddIndex(
            model_name='homework',
            index=models.Index(fields=['-due_date'], name='classes_hom_due_dat_b7bbbf_idx'),
        ),
        migrations.AddIndex(
            model_name='homeworksubmission',
            index=models.Index(fields=['homework', 'student'], name='classes_hom_homewor_c94ac5_idx'),
        ),
        migrations.AddIndex(
            model_name='homeworksubmission',
            index=models.Index(fields=['student', '-submission_date'], name='classes_hom_student_ece112_idx'),
        ),
        migrations.AddIndex(
            model_name='homeworksubmission',
            index=models.Index(fields=['completion_status'], name='classes_hom_complet_e78285_idx'),
        ),
    ]
