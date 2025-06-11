from django.db import transaction
from django.utils import timezone
from accounts.models import Student, User
from finance.models import Transaction
from datetime import datetime, timedelta

@transaction.atomic
def create_test_transactions(username):
    """Создает тестовые транзакции для указанного студента."""
    student = Student.objects.filter(user__username=username).first()
    
    if not student:
        print(f"Студент с именем пользователя '{username}' не найден.")
        return
    
    # Сбрасываем баланс студента
    student.balance = 0
    student.save()
    print(f"Баланс студента сброшен на 0")
    
    # Получаем пользователя-администратора для создания транзакций
    admin_user = User.objects.filter(is_staff=True).first()
    if not admin_user:
        print("Не найден пользователь-администратор для создания транзакций.")
        return
    
    # Создаем транзакцию пополнения
    deposit = Transaction.objects.create(
        student=student,
        amount=5000,
        date=timezone.now().date(),
        transaction_type='deposit',
        description='Тестовое пополнение баланса',
        created_by=admin_user
    )
    
    # Обновляем баланс студента
    student.balance += deposit.amount
    student.save()
    print(f"Создана транзакция пополнения на сумму {deposit.amount}. Новый баланс: {student.balance}")
    
    # Создаем транзакцию списания
    payment = Transaction.objects.create(
        student=student,
        amount=3000,
        date=timezone.now().date(),
        transaction_type='payment',
        description='Тестовая оплата за занятие',
        created_by=admin_user
    )
    
    # Обновляем баланс студента
    student.balance -= payment.amount
    student.save()
    print(f"Создана транзакция списания на сумму {payment.amount}. Новый баланс: {student.balance}")
    
    # Создаем транзакцию возврата (с отрицательной суммой)
    refund = Transaction.objects.create(
        student=student,
        amount=-1500,  # Отрицательная сумма для возврата
        date=timezone.now().date(),
        transaction_type='refund',
        description='Тестовый возврат средств',
        created_by=admin_user
    )
    
    # Обновляем баланс студента (вычитаем отрицательную сумму, что эквивалентно прибавлению положительной)
    student.balance -= refund.amount
    student.save()
    print(f"Создана транзакция возврата на сумму {refund.amount}. Новый баланс: {student.balance}")
    
    print("\nВсе тестовые транзакции успешно созданы.")
    print(f"Итоговый баланс студента: {student.balance}")
    
    # Рассчитываем ожидаемый баланс
    expected_balance = deposit.amount - payment.amount - refund.amount
    print(f"Ожидаемый баланс по формуле (пополнения - списания - возвраты): {expected_balance}")
    print(f"Соответствие балансов: {'Да' if abs(student.balance - expected_balance) < 0.01 else 'Нет'}")

if __name__ == "__main__":
    create_test_transactions('dulat')
