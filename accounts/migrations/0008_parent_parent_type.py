# Generated by Django 4.2.7 on 2025-04-17 13:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_alter_parent_phone_number_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='parent',
            name='parent_type',
            field=models.CharField(choices=[('parent', 'Родитель'), ('student', 'Ученик')], default='parent', max_length=10, verbose_name='Тип'),
        ),
    ]
