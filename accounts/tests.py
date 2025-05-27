from django.test import TestCase

import os
from django.conf import settings
from accounts.models import Student

class StudentFaceImageTest(TestCase):
    def test_face_image_naming_and_existence(self):
        students = Student.objects.exclude(face_image='')
        for student in students:
            if not student.face_image:
                continue
            path = student.face_image.path
            self.assertTrue(os.path.exists(path), f"Файл не найден: {path}")
            fname = os.path.basename(path)
            self.assertTrue(fname.startswith(f"faceid_{student.id}"), f"Неверное имя файла: {fname}")

