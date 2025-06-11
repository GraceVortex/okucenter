from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Sum, Count, Q
from datetime import datetime, timedelta

from accounts.models import Student, Teacher
from finance.models import Transaction, TeacherSalary
from finance.services import FinancialService


class FinancialDashboardAPI(APIView):
    """
    API для получения данных финансовой панели управления.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, format=None):
        """
        Возвращает данные для финансовой панели управления.
        """
        # Проверяем права доступа
        if not request.user.is_admin and not request.user.is_reception:
            return Response(
                {"detail": "У вас нет прав для просмотра финансовой информации."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Получаем период из запроса
        period = request.query_params.get('period', 'current_month')
        
        # Получаем данные
        data = FinancialService.get_financial_dashboard(period)
        
        return Response(data)


class TeacherSalaryAPI(APIView):
    """
    API для работы с зарплатами учителей.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, format=None):
        """
        Возвращает список зарплат учителей за указанный период.
        """
        # Проверяем права доступа
        if not request.user.is_admin and not request.user.is_reception:
            return Response(
                {"detail": "У вас нет прав для просмотра зарплат учителей."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Получаем параметры из запроса
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        teacher_id = request.query_params.get('teacher_id')
        
        # Если не указаны год и месяц, используем текущий месяц
        if not year or not month:
            today = timezone.now().date()
            year = today.year
            month = today.month
        else:
            year = int(year)
            month = int(month)
        
        # Определяем период
        first_day = datetime(year, month, 1).date()
        
        # Фильтруем зарплаты
        salaries = TeacherSalary.objects.filter(month=first_day)
        
        # Если указан ID учителя, фильтруем по нему
        if teacher_id:
            salaries = salaries.filter(teacher_id=teacher_id)
        
        # Формируем данные для ответа
        data = []
        for salary in salaries:
            # Пересчитываем зарплату, чтобы убедиться, что данные актуальны
            recalculated_salary = FinancialService.calculate_teacher_salary(salary.teacher, first_day)
            
            data.append({
                'id': salary.id,
                'teacher': {
                    'id': salary.teacher.id,
                    'full_name': salary.teacher.full_name,
                    'email': salary.teacher.email,
                    'phone': salary.teacher.phone
                },
                'month': salary.month.strftime('%B %Y'),
                'amount': recalculated_salary.amount,
                'paid_amount': recalculated_salary.paid_amount,
                'payment_status': recalculated_salary.payment_status,
                'payment_status_display': recalculated_salary.get_payment_status_display(),
                'lessons_count': recalculated_salary.lessons_count,
                'final_payment_date': recalculated_salary.final_payment_date
            })
        
        return Response(data)
    
    def post(self, request, format=None):
        """
        Отмечает зарплату учителя как выплаченную.
        """
        # Проверяем права доступа
        if not request.user.is_admin and not request.user.is_reception:
            return Response(
                {"detail": "У вас нет прав для выплаты зарплат учителям."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Получаем данные из запроса
        teacher_id = request.data.get('teacher_id')
        year = request.data.get('year')
        month = request.data.get('month')
        
        # Проверяем наличие обязательных параметров
        if not teacher_id or not year or not month:
            return Response(
                {"detail": "Необходимо указать ID учителя, год и месяц."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Получаем учителя
            teacher = Teacher.objects.get(id=teacher_id)
            
            # Определяем период
            first_day = datetime(int(year), int(month), 1).date()
            
            # Отмечаем зарплату как выплаченную
            salary = FinancialService.mark_salary_paid(teacher, first_day, request.user)
            
            return Response({
                'id': salary.id,
                'teacher': {
                    'id': salary.teacher.id,
                    'full_name': salary.teacher.full_name
                },
                'month': salary.month.strftime('%B %Y'),
                'amount': salary.amount,
                'paid_amount': salary.paid_amount,
                'payment_status': salary.payment_status,
                'payment_status_display': salary.get_payment_status_display(),
                'final_payment_date': salary.final_payment_date
            })
        
        except Teacher.DoesNotExist:
            return Response(
                {"detail": "Учитель не найден."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class TeacherSalaryDetailAPI(APIView):
    """
    API для получения детальной информации о зарплате учителя.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, teacher_id, year, month, format=None):
        """
        Возвращает детальную информацию о зарплате учителя за указанный месяц.
        """
        # Проверяем права доступа
        if not request.user.is_admin and not request.user.is_reception:
            return Response(
                {"detail": "У вас нет прав для просмотра детальной информации о зарплате учителя."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Получаем учителя
            teacher = Teacher.objects.get(id=teacher_id)
            
            # Получаем данные о заработке учителя
            data = FinancialService.get_teacher_earnings(teacher, int(year), int(month))
            
            # Преобразуем данные для ответа
            response_data = {
                'teacher': {
                    'id': teacher.id,
                    'full_name': teacher.full_name,
                    'email': teacher.email,
                    'phone': teacher.phone
                },
                'salary': {
                    'id': data['salary'].id,
                    'month': data['salary'].month.strftime('%B %Y'),
                    'amount': data['salary'].amount,
                    'paid_amount': data['salary'].paid_amount,
                    'payment_status': data['salary'].payment_status,
                    'payment_status_display': data['salary'].get_payment_status_display(),
                    'final_payment_date': data['salary'].final_payment_date
                },
                'attendance_days': [],
                'class_stats': [],
                'total_days': data['total_days'],
                'total_lessons': data['total_lessons'],
                'total_amount': data['total_amount']
            }
            
            # Добавляем информацию о днях
            for day in data['attendance_days']:
                day_data = {
                    'date': day['date'].strftime('%Y-%m-%d'),
                    'day_of_week': day['day_of_week'],
                    'classes': [],
                    'total_amount': day['total_amount']
                }
                
                for class_info in day['classes']:
                    class_data = {
                        'class_name': class_info['class_name'],
                        'time': class_info['time'],
                        'amount': class_info['amount'],
                        'is_scheduled': class_info['is_scheduled']
                    }
                    
                    if not class_info['is_scheduled'] and 'students_count' in class_info:
                        class_data['students_count'] = class_info['students_count']
                    
                    day_data['classes'].append(class_data)
                
                response_data['attendance_days'].append(day_data)
            
            # Добавляем информацию о классах
            for class_stat in data['class_stats']:
                class_data = {
                    'name': class_stat['name'],
                    'lessons_conducted': class_stat['lessons_conducted'],
                    'amount_per_lesson': class_stat['amount_per_lesson'],
                    'total_amount': class_stat['total_amount'],
                    'is_scheduled': class_stat['is_scheduled']
                }
                
                response_data['class_stats'].append(class_data)
            
            return Response(response_data)
        
        except Teacher.DoesNotExist:
            return Response(
                {"detail": "Учитель не найден."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class TransactionAPI(APIView):
    """
    API для работы с транзакциями.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, format=None):
        """
        Возвращает список транзакций с фильтрацией.
        """
        # Проверяем права доступа
        if not request.user.is_admin and not request.user.is_reception:
            return Response(
                {"detail": "У вас нет прав для просмотра транзакций."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Получаем параметры фильтрации из запроса
        student_id = request.query_params.get('student_id')
        transaction_type = request.query_params.get('transaction_type')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        period = request.query_params.get('period')
        
        # Базовый запрос
        transactions = Transaction.objects.all()
        
        # Применяем фильтры
        if student_id:
            transactions = transactions.filter(student_id=student_id)
        
        if transaction_type:
            transactions = transactions.filter(transaction_type=transaction_type)
        
        # Определяем даты начала и конца в зависимости от выбранного периода
        today = timezone.now().date()
        
        if not start_date and period:
            if period == 'current_month':
                # Текущий месяц
                start_date = today.replace(day=1)
                # Последний день текущего месяца
                if today.month == 12:
                    end_date = datetime(today.year + 1, 1, 1).date() - timedelta(days=1)
                else:
                    end_date = datetime(today.year, today.month + 1, 1).date() - timedelta(days=1)
            
            elif period == 'previous_month':
                # Предыдущий месяц
                if today.month == 1:
                    start_date = datetime(today.year - 1, 12, 1).date()
                    end_date = datetime(today.year, 1, 1).date() - timedelta(days=1)
                else:
                    start_date = datetime(today.year, today.month - 1, 1).date()
                    end_date = today.replace(day=1) - timedelta(days=1)
            
            elif period == 'last_3_months':
                # Последние 3 месяца
                start_date = (today - timedelta(days=90)).replace(day=1)
                end_date = today
            
            elif period == 'year':
                # Текущий год
                start_date = datetime(today.year, 1, 1).date()
                end_date = today
        
        # Применяем фильтры по датам
        if start_date:
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            transactions = transactions.filter(date__gte=start_date)
        
        if end_date:
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            transactions = transactions.filter(date__lte=end_date)
        
        # Сортируем по дате (от новых к старым)
        transactions = transactions.order_by('-date', '-created_at')
        
        # Формируем данные для ответа
        data = []
        for transaction in transactions:
            transaction_data = {
                'id': transaction.id,
                'student': {
                    'id': transaction.student.id,
                    'full_name': transaction.student.full_name
                },
                'amount': transaction.amount,
                'date': transaction.date.strftime('%Y-%m-%d'),
                'description': transaction.description,
                'transaction_type': transaction.transaction_type,
                'transaction_type_display': transaction.get_transaction_type_display()
            }
            
            if transaction.class_obj:
                transaction_data['class'] = {
                    'id': transaction.class_obj.id,
                    'name': transaction.class_obj.name
                }
            
            if transaction.scheduled_lesson:
                transaction_data['scheduled_lesson'] = {
                    'id': transaction.scheduled_lesson.id,
                    'date': transaction.scheduled_lesson.date.strftime('%Y-%m-%d')
                }
            
            if transaction.non_scheduled_lesson:
                transaction_data['non_scheduled_lesson'] = {
                    'id': transaction.non_scheduled_lesson.id,
                    'name': transaction.non_scheduled_lesson.name,
                    'date': transaction.non_scheduled_lesson.date.strftime('%Y-%m-%d')
                }
            
            data.append(transaction_data)
        
        return Response(data)
    
    def post(self, request, format=None):
        """
        Создает новую транзакцию.
        """
        # Проверяем права доступа
        if not request.user.is_admin and not request.user.is_reception:
            return Response(
                {"detail": "У вас нет прав для создания транзакций."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Получаем данные из запроса
        student_id = request.data.get('student_id')
        amount = request.data.get('amount')
        description = request.data.get('description')
        transaction_type = request.data.get('transaction_type')
        class_id = request.data.get('class_id')
        scheduled_lesson_id = request.data.get('scheduled_lesson_id')
        non_scheduled_lesson_id = request.data.get('non_scheduled_lesson_id')
        
        # Проверяем наличие обязательных параметров
        if not student_id or not amount or not description or not transaction_type:
            return Response(
                {"detail": "Необходимо указать ID студента, сумму, описание и тип транзакции."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Получаем студента
            student = Student.objects.get(id=student_id)
            
            # Получаем класс, если указан
            class_obj = None
            if class_id:
                class_obj = Class.objects.get(id=class_id)
            
            # Получаем урок по расписанию, если указан
            scheduled_lesson = None
            if scheduled_lesson_id:
                from attendance.models import Attendance
                scheduled_lesson = Attendance.objects.get(id=scheduled_lesson_id)
            
            # Получаем урок не по расписанию, если указан
            non_scheduled_lesson = None
            if non_scheduled_lesson_id:
                from classes.non_scheduled_lesson_models import NonScheduledLesson
                non_scheduled_lesson = NonScheduledLesson.objects.get(id=non_scheduled_lesson_id)
            
            # Создаем транзакцию
            transaction = FinancialService.create_student_payment(
                student=student,
                amount=float(amount),
                description=description,
                transaction_type=transaction_type,
                class_obj=class_obj,
                scheduled_lesson=scheduled_lesson,
                non_scheduled_lesson=non_scheduled_lesson,
                created_by=request.user
            )
            
            return Response({
                'id': transaction.id,
                'student': {
                    'id': transaction.student.id,
                    'full_name': transaction.student.full_name
                },
                'amount': transaction.amount,
                'date': transaction.date.strftime('%Y-%m-%d'),
                'description': transaction.description,
                'transaction_type': transaction.transaction_type,
                'transaction_type_display': transaction.get_transaction_type_display()
            }, status=status.HTTP_201_CREATED)
        
        except Student.DoesNotExist:
            return Response(
                {"detail": "Студент не найден."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Class.DoesNotExist:
            return Response(
                {"detail": "Класс не найден."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
