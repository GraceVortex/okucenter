# Generated by Django 4.2.7 on 2025-05-02 13:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('face_recognition_app', '0002_remove_faceattendance_student'),
    ]

    operations = [
        migrations.AlterField(
            model_name='faceattendance',
            name='timestamp',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='facerecognitionlog',
            name='success',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddIndex(
            model_name='faceattendance',
            index=models.Index(fields=['-timestamp'], name='face_recogn_timesta_0068ab_idx'),
        ),
        migrations.AddIndex(
            model_name='facerecognitionlog',
            index=models.Index(fields=['success'], name='face_recogn_success_5a816e_idx'),
        ),
        migrations.AddIndex(
            model_name='facerecognitionlog',
            index=models.Index(fields=['user', '-timestamp'], name='face_recogn_user_id_b60463_idx'),
        ),
    ]
