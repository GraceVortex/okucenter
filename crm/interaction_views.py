import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from accounts.models import User
from .models import Lead, LeadStatusHistory, Interaction, SaleStage
from .views import marketer_required

logger = logging.getLogger(__name__)

@marketer_required
def add_interaction(request, lead_id):
    """Добавление нового взаимодействия с лидом"""
    lead = get_object_or_404(Lead, pk=lead_id)
    
    # Проверка прав доступа к лиду
    if not request.user.is_admin and request.user.is_marketer and lead.assigned_to != request.user:
        messages.error(request, 'У вас нет прав для добавления взаимодействий с этим лидом.')
        return redirect('crm:lead_detail', lead_id=lead.id)
    
    if request.method == 'POST':
        interaction_type = request.POST.get('interaction_type')
        date_time = request.POST.get('date_time')
        duration = request.POST.get('duration')
        result = request.POST.get('result')
        notes = request.POST.get('notes')
        
        # Проверка обязательных полей
        if not interaction_type or not date_time or not result:
            messages.error(request, 'Пожалуйста, заполните все обязательные поля.')
            return redirect('crm:add_interaction', lead_id=lead.id)
        
        # Обработка вложения, если есть
        attachment = None
        if 'attachment' in request.FILES:
            attachment = request.FILES['attachment']
        
        try:
            # Создаем новое взаимодействие
            interaction = Interaction(
                lead=lead,
                interaction_type=interaction_type,
                date_time=date_time,
                duration=duration if duration else None,
                result=result,
                notes=notes,
                performed_by=request.user,
                attachment=attachment
            )
            interaction.save()
            
            # Обновляем статус лида, если он был "новый"
            if lead.status == 'new':
                lead.status = 'in_progress'
                lead.save()
                
                # Запись в историю изменений статуса
                status_note = f'Статус изменен с "Новый" на "В работе" после добавления взаимодействия'
                LeadStatusHistory.objects.create(
                    lead=lead,
                    stage=lead.current_stage,
                    notes=status_note,
                    changed_by=request.user
                )
            
            messages.success(request, 'Взаимодействие успешно добавлено!')
            return redirect('crm:lead_detail', lead_id=lead.id)
            
        except Exception as e:
            logger.error(f'Ошибка при добавлении взаимодействия: {str(e)}')
            messages.error(request, f'Ошибка при добавлении взаимодействия: {str(e)}')
    
    context = {
        'lead': lead,
        'interaction_types': dict(Interaction.INTERACTION_TYPE_CHOICES),
        'interaction_results': dict(Interaction.INTERACTION_RESULT_CHOICES),
    }
    
    return render(request, 'crm/interaction_form.html', context)

@marketer_required
def update_lead_stage(request, lead_id):
    """Обновление этапа воронки продаж для лида"""
    lead = get_object_or_404(Lead, pk=lead_id)
    
    # Проверка прав доступа к лиду
    if not request.user.is_admin and request.user.is_marketer and lead.assigned_to != request.user:
        messages.error(request, 'У вас нет прав для изменения этапа этого лида.')
        return redirect('crm:lead_detail', lead_id=lead.id)
    
    if request.method == 'POST':
        stage_id = request.POST.get('stage_id')
        notes = request.POST.get('notes', '')
        
        if not stage_id:
            messages.error(request, 'Не указан этап воронки.')
            return redirect('crm:lead_detail', lead_id=lead.id)
        
        try:
            new_stage = SaleStage.objects.get(pk=stage_id)
            old_stage = lead.current_stage
            
            # Закрываем предыдущий этап в истории
            if old_stage:
                previous_history = lead.status_history.filter(stage=old_stage, exited_at__isnull=True).first()
                if previous_history:
                    previous_history.exited_at = timezone.now()
                    previous_history.save()
            
            # Обновляем текущий этап
            lead.current_stage = new_stage
            lead.save()
            
            # Создаем новую запись в истории
            stage_note = f'Перемещен на этап "{new_stage.name}"'
            if notes:
                stage_note += f": {notes}"
                
            LeadStatusHistory.objects.create(
                lead=lead,
                stage=new_stage,
                notes=stage_note,
                changed_by=request.user
            )
            
            messages.success(request, f'Лид перемещен на этап "{new_stage.name}"')
            
        except Exception as e:
            logger.error(f'Ошибка при обновлении этапа лида: {str(e)}')
            messages.error(request, f'Ошибка при обновлении этапа лида: {str(e)}')
    
    return redirect('crm:lead_detail', lead_id=lead.id)
