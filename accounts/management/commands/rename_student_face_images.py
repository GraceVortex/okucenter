import os
from django.core.management.base import BaseCommand
from django.conf import settings
from accounts.models import Student

class Command(BaseCommand):
    help = 'Переименовать фото студентов в формат faceid_<student.id>.<ext> и обновить ссылки в базе.'

    def handle(self, *args, **options):
        media_root = settings.MEDIA_ROOT
        changed = 0
        for student in Student.objects.exclude(face_image=''):
            if not student.face_image:
                continue
            old_path = student.face_image.path
            ext = old_path.split('.')[-1]
            new_filename = f'faceid_{student.id}.{ext}'
            new_rel_path = os.path.join('face_images/students', new_filename)
            new_abs_path = os.path.join(media_root, new_rel_path)
            if os.path.abspath(old_path) == os.path.abspath(new_abs_path):
                continue
            try:
                os.rename(old_path, new_abs_path)
                student.face_image.name = new_rel_path.replace('\\','/')
                student.save()
                self.stdout.write(self.style.SUCCESS(f'Переименовано: {old_path} -> {new_abs_path}'))
                changed += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Ошибка при переименовании {old_path}: {e}'))
        self.stdout.write(self.style.SUCCESS(f'Всего переименовано: {changed}'))
