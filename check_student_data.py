from accounts.models import Student
from finance.models import Transaction
from attendance.models import Attendance

def check_student_data(username):
    """Проверяет данные студента и выводит информацию о балансе и транзакциях."""
    student = Student.objects.filter(user__username=username).first()
    
    if not student:
        print(f"Студент с именем пользователя '{username}' не найден.")
        return
    
    print(f"Студент: {student.full_name}")
    print(f"Текущий баланс: {student.balance}")
    
    # Получаем транзакции
    transactions = Transaction.objects.filter(student=student).order_by('-date')
    
    print(f"Количество транзакций: {transactions.count()}")
    
    # Суммы по типам транзакций
    deposits = transactions.filter(transaction_type='deposit').values_list('amount', flat=True)
    payments = transactions.filter(transaction_type='payment').values_list('amount', flat=True)
    refunds = transactions.filter(transaction_type='refund').values_list('amount', flat=True)
    
    print(f"Пополнения: {sum(deposits) if deposits else 0}")
    print(f"Списания: {sum(payments) if payments else 0}")
    print(f"Возвраты: {sum(refunds) if refunds else 0}")
    
    # Рассчитываем ожидаемый баланс
    expected_balance = (sum(deposits) if deposits else 0) - (sum(payments) if payments else 0) - (sum(refunds) if refunds else 0)
    print(f"Ожидаемый баланс: {expected_balance}")
    print(f"Соответствие балансов: {'Да' if abs(student.balance - expected_balance) < 0.01 else 'Нет'}")
    
    # Выводим детали транзакций
    print("\nДетали транзакций:")
    for t in transactions:
        print(f"{t.date} | {t.transaction_type} | {t.amount} | {t.description}")

if __name__ == "__main__":
    check_student_data('dulat')
