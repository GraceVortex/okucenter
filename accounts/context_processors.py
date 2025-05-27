from accounts.models import Parent, Student
from attendance.models import StudentCancellationRequest

def pending_cancellations(request):
    """
    Контекстный процессор для передачи количества ожидающих запросов на отмену занятий
    для родителей в шаблоны.
    """
    context = {
        'pending_cancellations': 0
    }
    
    if request.user.is_authenticated and hasattr(request.user, 'is_parent') and request.user.is_parent:
        try:
            parent = Parent.objects.get(user=request.user)
            children = Student.objects.filter(parent=parent)
            pending_cancellations = StudentCancellationRequest.objects.filter(
                student__in=children, 
                status='pending'
            ).count()
            context['pending_cancellations'] = pending_cancellations
        except Parent.DoesNotExist:
            pass
    
    return context
