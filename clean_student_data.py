from django.db import transaction
from accounts.models import Student
from finance.models import Transaction
from attendance.models import Attendance

@transaction.atomic
def clean_student_data(username):
    """Удаляет все транзакции и записи о посещаемости для указанного студента и сбрасывает его баланс на 0."""
    student = Student.objects.filter(user__username=username).first()
    
    if not student:
        print(f"Студент с именем пользователя '{username}' не найден.")
        return
    
    print(f"Найден студент: {student.full_name}")
    print(f"Текущий баланс: {student.balance}")
    
    # Удаляем транзакции
    transactions = Transaction.objects.filter(student=student)
    transactions_count = transactions.count()
    transactions.delete()
    print(f"Удалено транзакций: {transactions_count}")
    
    # Удаляем записи о посещаемости
    attendances = Attendance.objects.filter(student=student)
    attendances_count = attendances.count()
    attendances.delete()
    print(f"Удалено записей о посещаемости: {attendances_count}")
    
    # Сбрасываем баланс
    student.balance = 0
    student.save()
    print(f"Баланс студента сброшен на 0")
    
    print("Данные успешно удалены.")

if __name__ == "__main__":
    clean_student_data('dulat')
