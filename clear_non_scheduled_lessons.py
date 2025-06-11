"""
Скрипт для удаления всех записей об уроках не по расписанию.
"""
import os
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')
django.setup()

# Импорт моделей
from classes.non_scheduled_lesson_models import NonScheduledLesson, NonScheduledLessonAttendance
from finance.models import Transaction

# Удаляем все записи о посещаемости уроков не по расписанию
print("Удаляем записи о посещаемости уроков не по расписанию...")
attendance_count = NonScheduledLessonAttendance.objects.all().count()
NonScheduledLessonAttendance.objects.all().delete()
print(f"Удалено {attendance_count} записей о посещаемости.")

# Удаляем все транзакции, связанные с уроками не по расписанию
print("Удаляем транзакции, связанные с уроками не по расписанию...")
transactions = Transaction.objects.filter(description__contains="не по расписанию")
transaction_count = transactions.count()
transactions.delete()
print(f"Удалено {transaction_count} транзакций.")

# Удаляем все уроки не по расписанию
print("Удаляем уроки не по расписанию...")
lesson_count = NonScheduledLesson.objects.all().count()
NonScheduledLesson.objects.all().delete()
print(f"Удалено {lesson_count} уроков не по расписанию.")

print("Очистка завершена успешно!")
