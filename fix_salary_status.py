import os
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'okucenter.settings')
django.setup()

from finance.models import TeacherSalary
from decimal import Decimal

# Получаем все записи о зарплатах
salaries = TeacherSalary.objects.all()

# Счетчики для статистики
updated_count = 0
already_correct = 0

for salary in salaries:
    # Определяем правильный статус оплаты
    if salary.is_paid:
        correct_status = 'paid'
    elif salary.advance_amount > Decimal('0'):
        correct_status = 'partially_paid'
    else:
        correct_status = 'unpaid'
    
    # Если текущий статус не соответствует правильному, обновляем его
    if salary.payment_status != correct_status:
        print(f"Обновление записи #{salary.id}: {salary.teacher.full_name} - {salary.month}")
        print(f"  Статус: {salary.payment_status} -> {correct_status}")
        print(f"  Сумма: {salary.amount}, Аванс: {salary.advance_amount}, Остаток: {salary.balance}")
        
        salary.payment_status = correct_status
        
        # Если статус частично оплачен, обновляем остаток
        if correct_status == 'partially_paid':
            correct_balance = salary.amount - salary.advance_amount
            if salary.balance != correct_balance:
                print(f"  Исправление остатка: {salary.balance} -> {correct_balance}")
                salary.balance = correct_balance
        
        # Если статус полностью оплачен, остаток должен быть 0
        elif correct_status == 'paid' and salary.balance != 0:
            print(f"  Исправление остатка: {salary.balance} -> 0")
            salary.balance = Decimal('0')
        
        salary.save()
        updated_count += 1
    else:
        already_correct += 1

print(f"\nОбновлено записей: {updated_count}")
print(f"Уже корректных записей: {already_correct}")
print(f"Всего обработано: {updated_count + already_correct}")
