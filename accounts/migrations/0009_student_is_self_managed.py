from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_parent_parent_type'),  # Последняя существующая миграция
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='is_self_managed',
            field=models.BooleanField(default=False, help_text='Ученик сам управляет своим аккаунтом без родителя', verbose_name='Самоуправляемый'),
        ),
    ]
