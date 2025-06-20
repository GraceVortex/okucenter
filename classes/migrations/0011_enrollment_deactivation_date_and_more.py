# Generated by Django 4.2.7 on 2025-05-02 13:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classes', '0010_alter_class_options_alter_classschedule_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='enrollment',
            name='deactivation_date',
            field=models.DateTimeField(blank=True, db_index=True, help_text='Дата и время, когда ученик был отчислен из класса', null=True, verbose_name='Дата и время отчисления'),
        ),
        migrations.AlterField(
            model_name='enrollment',
            name='enrollment_date',
            field=models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Дата и время зачисления'),
        ),
        migrations.AddIndex(
            model_name='enrollment',
            index=models.Index(fields=['deactivation_date'], name='classes_enr_deactiv_c6b3fe_idx'),
        ),
    ]
