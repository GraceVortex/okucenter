# Финансовая система OkuCenter

## Обзор

Финансовая система OkuCenter предназначена для управления всеми финансовыми аспектами образовательного центра, включая:

- Отслеживание платежей студентов
- Расчет и выплату зарплат учителям
- Финансовую отчетность и статистику
- Учет уроков (как по расписанию, так и вне расписания)

## Модели данных

### Основные модели

1. **Transaction** - Транзакции студентов (платежи, депозиты, возвраты)
2. **TeacherSalary** - Зарплаты учителей
3. **LessonPayment** - Платежи за конкретные уроки
4. **TeacherPayment** - Выплаты учителям за проведенные уроки
5. **FinancialStatistics** - Ежедневная финансовая статистика
6. **MonthlyFinancialStatistics** - Месячная финансовая статистика

## API

### Финансовая панель управления

```
GET /finance/api/dashboard/
```

Параметры запроса:
- `period` - Период (current_month, previous_month, last_3_months, year)

Пример ответа:
```json
{
  "period": "01.09.2023 - 30.09.2023",
  "total_income": 1500000,
  "lesson_income": 1200000,
  "other_income": 300000,
  "teacher_payments": 600000,
  "refunds": 50000,
  "profit": 850000,
  "scheduled_lessons_count": 120,
  "non_scheduled_lessons_count": 30,
  "students_count": 50
}
```

### Зарплаты учителей

```
GET /finance/api/teacher-salaries/
```

Параметры запроса:
- `year` - Год (опционально)
- `month` - Месяц (опционально)
- `teacher_id` - ID учителя (опционально)

Пример ответа:
```json
[
  {
    "id": 1,
    "teacher": {
      "id": 5,
      "full_name": "Иванов Иван Иванович",
      "email": "ivanov@example.com",
      "phone": "+77771234567"
    },
    "month": "September 2023",
    "amount": 150000,
    "paid_amount": 150000,
    "payment_status": "paid",
    "payment_status_display": "Оплачено",
    "lessons_count": 25,
    "final_payment_date": "2023-09-30"
  }
]
```

### Отметка зарплаты как выплаченной

```
POST /finance/api/teacher-salaries/
```

Параметры запроса:
```json
{
  "teacher_id": 5,
  "year": 2023,
  "month": 9
}
```

### Детальная информация о зарплате учителя

```
GET /finance/api/teacher-salaries/{teacher_id}/{year}/{month}/
```

Пример ответа:
```json
{
  "teacher": {
    "id": 5,
    "full_name": "Иванов Иван Иванович",
    "email": "ivanov@example.com",
    "phone": "+77771234567"
  },
  "salary": {
    "id": 1,
    "month": "September 2023",
    "amount": 150000,
    "paid_amount": 150000,
    "payment_status": "paid",
    "payment_status_display": "Оплачено",
    "final_payment_date": "2023-09-30"
  },
  "attendance_days": [
    {
      "date": "2023-09-01",
      "day_of_week": "Friday",
      "classes": [
        {
          "class_name": "Математика 5 класс",
          "time": "14:00 - 15:30",
          "amount": 6000,
          "is_scheduled": true
        },
        {
          "class_name": "Индивидуальное занятие (Вне расписания)",
          "time": "16:00 - 17:00",
          "amount": 8000,
          "students_count": 1,
          "is_scheduled": false
        }
      ],
      "total_amount": 14000
    }
  ],
  "class_stats": [
    {
      "name": "Математика 5 класс",
      "lessons_conducted": 15,
      "amount_per_lesson": 6000,
      "total_amount": 90000,
      "is_scheduled": true
    },
    {
      "name": "Индивидуальное занятие (Вне расписания)",
      "lessons_conducted": 10,
      "amount_per_lesson": 8000,
      "total_amount": 80000,
      "is_scheduled": false
    }
  ],
  "total_days": 20,
  "total_lessons": 25,
  "total_amount": 150000
}
```

### Транзакции

```
GET /finance/api/transactions/
```

Параметры запроса:
- `student_id` - ID студента (опционально)
- `transaction_type` - Тип транзакции (payment, deposit, refund)
- `start_date` - Дата начала периода (YYYY-MM-DD)
- `end_date` - Дата окончания периода (YYYY-MM-DD)
- `period` - Предопределенный период (current_month, previous_month, last_3_months, year)

Пример ответа:
```json
[
  {
    "id": 1,
    "student": {
      "id": 10,
      "full_name": "Петров Петр Петрович"
    },
    "amount": 15000,
    "date": "2023-09-15",
    "description": "Оплата за урок математики",
    "transaction_type": "payment",
    "transaction_type_display": "Оплата",
    "class": {
      "id": 3,
      "name": "Математика 5 класс"
    },
    "scheduled_lesson": {
      "id": 25,
      "date": "2023-09-15"
    }
  }
]
```

### Создание транзакции

```
POST /finance/api/transactions/
```

Параметры запроса:
```json
{
  "student_id": 10,
  "amount": 15000,
  "description": "Оплата за урок математики",
  "transaction_type": "payment",
  "class_id": 3,
  "scheduled_lesson_id": 25
}
```

## Сервисный слой

Финансовая система использует сервисный слой (`FinancialService`) для инкапсуляции бизнес-логики:

1. `create_student_payment` - Создание платежа студента
2. `calculate_teacher_salary` - Расчет зарплаты учителя
3. `mark_salary_paid` - Отметка зарплаты как выплаченной
4. `update_daily_statistics` - Обновление ежедневной статистики
5. `update_monthly_statistics` - Обновление месячной статистики
6. `get_financial_dashboard` - Получение данных для финансовой панели
7. `get_teacher_earnings` - Получение данных о заработке учителя
8. `get_student_financial_summary` - Финансовая сводка по студенту
9. `get_class_financial_summary` - Финансовая сводка по классу
10. `get_transaction_statistics` - Статистика по транзакциям

## Особенности реализации

1. **Учет всех типов уроков** - Система учитывает как уроки по расписанию, так и уроки вне расписания при расчете зарплат и статистики.
2. **Согласованность данных** - Все финансовые операции выполняются в транзакциях для обеспечения согласованности данных.
3. **Автоматическое обновление статистики** - Статистика автоматически обновляется при создании транзакций и выплате зарплат.
4. **Детализация зарплат** - Система хранит детальную информацию о каждом уроке, за который учитель получает оплату.
5. **Гибкая система отчетности** - API поддерживает различные периоды для формирования отчетов и статистики.
