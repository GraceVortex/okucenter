from django.urls import path
from . import views
from . import interaction_views
from . import funnel_views
from . import campaign_views
from . import social_views
from . import analytics_views

# Импортируем новые представления
from . import views_contacts
from . import views_deals
from . import views_activities
from . import views_integrations

app_name = 'crm'

urlpatterns = [
    # Дашборд и основные представления
    path('', views.crm_dashboard, name='dashboard'),
    
    # Лиды (старые представления)
    path('leads/', views.lead_list, name='lead_list'),
    path('leads/create/', views.lead_create, name='lead_create'),
    path('leads/<int:lead_id>/', views.lead_detail, name='lead_detail'),
    path('leads/<int:lead_id>/update/', views.lead_update, name='lead_update'),
    
    # Взаимодействия (старые представления)
    path('leads/<int:lead_id>/add-interaction/', interaction_views.add_interaction, name='add_interaction'),
    path('leads/<int:lead_id>/update-stage/', interaction_views.update_lead_stage, name='update_lead_stage'),
    
    # Воронка продаж (старые представления)
    path('funnel/', funnel_views.sales_funnel, name='sales_funnel'),
    path('funnel/statistics/', funnel_views.funnel_statistics, name='funnel_statistics'),
    
    # Кампании (старые представления)
    path('campaigns/', campaign_views.campaign_list, name='campaign_list'),
    path('campaigns/create/', campaign_views.campaign_create, name='campaign_create'),
    path('campaigns/<int:campaign_id>/', campaign_views.campaign_detail, name='campaign_detail'),
    path('campaigns/<int:campaign_id>/update/', campaign_views.campaign_update, name='campaign_update'),
    path('campaigns/<int:campaign_id>/leads/', campaign_views.campaign_leads, name='campaign_leads'),
    
    # Интеграция с Meta Business Suite (старые представления)
    path('meta/accounts/', social_views.meta_accounts_list, name='meta_accounts_list'),
    path('meta/accounts/create/', social_views.meta_account_create, name='meta_account_create'),
    path('meta/accounts/<int:account_id>/update/', social_views.meta_account_update, name='meta_account_update'),
    path('leads/<int:lead_id>/send-whatsapp/', social_views.send_whatsapp_message, name='send_whatsapp_message'),
    path('leads/<int:lead_id>/social-messages/', social_views.social_messages, name='social_messages'),
    path('webhook/meta/', social_views.webhook_handler, name='meta_webhook'),
    
    # Аналитика (старые представления)
    path('analytics/campaigns/', analytics_views.campaign_analytics, name='campaign_analytics'),
    path('analytics/lead-acquisition-cost/', analytics_views.lead_acquisition_cost, name='lead_acquisition_cost'),
    path('analytics/interactions/', analytics_views.interaction_analytics, name='interaction_analytics'),
    
    # НОВЫЕ ПРЕДСТАВЛЕНИЯ (amoCRM/Битрикс24 стиль)
    
    # Контакты
    path('contacts/', views_contacts.contact_list, name='contact_list'),
    path('contacts/create/', views_contacts.contact_create, name='contact_create'),
    path('contacts/<int:contact_id>/', views_contacts.contact_detail, name='contact_detail'),
    path('contacts/<int:contact_id>/update/', views_contacts.contact_update, name='contact_update'),
    path('contacts/<int:contact_id>/delete/', views_contacts.contact_delete, name='contact_delete'),
    
    # Компании
    path('companies/', views_contacts.company_list, name='company_list'),
    path('companies/create/', views_contacts.company_create, name='company_create'),
    path('companies/<int:company_id>/', views_contacts.company_detail, name='company_detail'),
    path('companies/<int:company_id>/update/', views_contacts.company_update, name='company_update'),
    path('companies/<int:company_id>/delete/', views_contacts.company_delete, name='company_delete'),
    
    # Сделки
    path('deals/', views_deals.deal_list, name='deal_list'),
    path('deals/kanban/', views_deals.deal_kanban, name='deal_kanban'),
    path('deals/create/', views_deals.deal_create, name='deal_create'),
    path('deals/<int:deal_id>/', views_deals.deal_detail, name='deal_detail'),
    path('deals/<int:deal_id>/update/', views_deals.deal_update, name='deal_update'),
    path('deals/<int:deal_id>/delete/', views_deals.deal_delete, name='deal_delete'),
    path('deals/change-stage/', views_deals.deal_change_stage, name='deal_change_stage'),
    
    # Воронки продаж
    path('pipelines/', views_deals.pipeline_list, name='pipeline_list'),
    path('pipelines/<int:pipeline_id>/', views_deals.pipeline_detail, name='pipeline_detail'),
    
    # Активности
    path('activities/', views_activities.activity_list, name='activity_list'),
    path('activities/calendar/', views_activities.activity_calendar, name='activity_calendar'),
    path('activities/<int:activity_id>/', views_activities.activity_detail, name='activity_detail'),
    path('activities/<int:activity_id>/update/', views_activities.activity_update, name='activity_update'),
    path('activities/<int:activity_id>/delete/', views_activities.activity_delete, name='activity_delete'),
    path('activities/<int:activity_id>/complete/', views_activities.activity_complete, name='activity_complete'),
    
    # Создание разных типов активностей
    path('tasks/create/', views_activities.task_create, name='task_create'),
    path('calls/create/', views_activities.call_create, name='call_create'),
    path('meetings/create/', views_activities.meeting_create, name='meeting_create'),
    
    # Интеграции
    path('integrations/', views_integrations.integration_list, name='integration_list'),
    path('integrations/create/', views_integrations.integration_create, name='integration_create'),
    path('integrations/<int:integration_id>/', views_integrations.integration_detail, name='integration_detail'),
    path('integrations/<int:integration_id>/setup/', views_integrations.integration_setup, name='integration_setup'),
    
    # Вебхуки
    path('integrations/<int:integration_id>/webhooks/create/', views_integrations.webhook_create, name='webhook_create'),
    path('webhooks/<int:webhook_id>/update/', views_integrations.webhook_update, name='webhook_update'),
    
    # Беседы
    path('conversations/', views_integrations.conversation_list, name='conversation_list'),
    path('conversations/<int:conversation_id>/', views_integrations.conversation_detail, name='conversation_detail'),
    path('conversations/<int:conversation_id>/send/', views_integrations.send_message, name='send_message'),
    
    # Вебхуки для внешних сервисов
    path('webhook/whatsapp/', views_integrations.whatsapp_webhook, name='whatsapp_webhook'),
    path('webhook/instagram/', views_integrations.instagram_webhook, name='instagram_webhook'),
]
