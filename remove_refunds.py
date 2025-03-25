import os
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')
django.setup()

from django.db import transaction
from finance.models import Transaction

def convert_refunds_to_deposits():
    """
    Преобразует все транзакции типа 'refund' в транзакции типа 'deposit'.
    """
    with transaction.atomic():
        # Получаем все транзакции типа 'refund'
        refunds = Transaction.objects.filter(transaction_type='refund')
        
        # Выводим информацию о количестве найденных возвратов
        refunds_count = refunds.count()
        print(f"Найдено {refunds_count} транзакций типа 'refund'")
        
        # Преобразуем все возвраты в пополнения
        for refund in refunds:
            print(f"Преобразование транзакции #{refund.id}: {refund.description}")
            refund.transaction_type = 'deposit'
            refund.description = f"Пополнение (преобразовано из возврата): {refund.description}"
            refund.save()
        
        print(f"Успешно преобразовано {refunds_count} транзакций")

if __name__ == '__main__':
    convert_refunds_to_deposits()
