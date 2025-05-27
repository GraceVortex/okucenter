import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from .models_new import Contact, Company
from .forms import ContactForm, CompanyForm  # Формы нужно будет создать

logger = logging.getLogger(__name__)

# Представления для контактов
@login_required
def contact_list(request):
    """
    Отображение списка контактов с фильтрацией и поиском
    """
    # Получаем параметры фильтрации
    contact_type = request.GET.get('type', '')
    search_query = request.GET.get('q', '')
    
    # Базовый запрос
    contacts_query = Contact.objects.all()
    
    # Применяем фильтры
    if contact_type:
        contacts_query = contacts_query.filter(contact_type=contact_type)
    
    # Применяем поиск
    if search_query:
        contacts_query = contacts_query.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(middle_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    
    # Сортировка
    contacts_query = contacts_query.order_by('last_name', 'first_name')
    
    # Пагинация
    paginator = Paginator(contacts_query, 25)  # 25 контактов на страницу
    page_number = request.GET.get('page', 1)
    contacts = paginator.get_page(page_number)
    
    # Подготавливаем контекст
    context = {
        'contacts': contacts,
        'contact_type': contact_type,
        'search_query': search_query,
        'contact_type_choices': Contact.CONTACT_TYPE_CHOICES,
        'total_contacts': contacts_query.count(),
    }
    
    return render(request, 'crm/contact_list.html', context)

@login_required
def contact_detail(request, contact_id):
    """
    Отображение детальной информации о контакте
    """
    contact = get_object_or_404(Contact, id=contact_id)
    
    # Получаем связанные сделки
    deals = contact.deals.all().order_by('-created_at')
    
    # Получаем активности
    activities = []  # Здесь будут активности, связанные с контактом
    
    context = {
        'contact': contact,
        'deals': deals,
        'activities': activities,
    }
    
    return render(request, 'crm/contact_detail.html', context)

@login_required
def contact_create(request):
    """
    Создание нового контакта
    """
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            contact = form.save(commit=False)
            contact.responsible = request.user  # Устанавливаем текущего пользователя как ответственного
            contact.save()
            messages.success(request, f'Контакт "{contact.full_name}" успешно создан')
            return redirect('contact_detail', contact_id=contact.id)
    else:
        form = ContactForm()
    
    context = {
        'form': form,
        'title': 'Создание контакта',
    }
    
    return render(request, 'crm/contact_form.html', context)

@login_required
def contact_update(request, contact_id):
    """
    Обновление существующего контакта
    """
    contact = get_object_or_404(Contact, id=contact_id)
    
    if request.method == 'POST':
        form = ContactForm(request.POST, instance=contact)
        if form.is_valid():
            contact = form.save()
            messages.success(request, f'Контакт "{contact.full_name}" успешно обновлен')
            return redirect('contact_detail', contact_id=contact.id)
    else:
        form = ContactForm(instance=contact)
    
    context = {
        'form': form,
        'contact': contact,
        'title': 'Редактирование контакта',
    }
    
    return render(request, 'crm/contact_form.html', context)

@login_required
def contact_delete(request, contact_id):
    """
    Удаление контакта
    """
    contact = get_object_or_404(Contact, id=contact_id)
    
    if request.method == 'POST':
        contact_name = contact.full_name
        contact.delete()
        messages.success(request, f'Контакт "{contact_name}" успешно удален')
        return redirect('contact_list')
    
    context = {
        'contact': contact,
    }
    
    return render(request, 'crm/contact_confirm_delete.html', context)

# Представления для компаний
@login_required
def company_list(request):
    """
    Отображение списка компаний с фильтрацией и поиском
    """
    # Получаем параметры фильтрации
    company_type = request.GET.get('type', '')
    search_query = request.GET.get('q', '')
    
    # Базовый запрос
    companies_query = Company.objects.all()
    
    # Применяем фильтры
    if company_type:
        companies_query = companies_query.filter(company_type=company_type)
    
    # Применяем поиск
    if search_query:
        companies_query = companies_query.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(website__icontains=search_query)
        )
    
    # Добавляем аннотацию с количеством контактов
    companies_query = companies_query.annotate(contacts_count=Count('contacts'))
    
    # Сортировка
    companies_query = companies_query.order_by('name')
    
    # Пагинация
    paginator = Paginator(companies_query, 25)  # 25 компаний на страницу
    page_number = request.GET.get('page', 1)
    companies = paginator.get_page(page_number)
    
    # Подготавливаем контекст
    context = {
        'companies': companies,
        'company_type': company_type,
        'search_query': search_query,
        'company_type_choices': Company.COMPANY_TYPE_CHOICES,
        'total_companies': companies_query.count(),
    }
    
    return render(request, 'crm/company_list.html', context)

@login_required
def company_detail(request, company_id):
    """
    Отображение детальной информации о компании
    """
    company = get_object_or_404(Company, id=company_id)
    
    # Получаем связанные контакты
    contacts = company.contacts.all().order_by('last_name', 'first_name')
    
    # Получаем связанные сделки
    deals = company.deals.all().order_by('-created_at')
    
    # Получаем активности
    activities = []  # Здесь будут активности, связанные с компанией
    
    context = {
        'company': company,
        'contacts': contacts,
        'deals': deals,
        'activities': activities,
    }
    
    return render(request, 'crm/company_detail.html', context)

@login_required
def company_create(request):
    """
    Создание новой компании
    """
    if request.method == 'POST':
        form = CompanyForm(request.POST)
        if form.is_valid():
            company = form.save(commit=False)
            company.responsible = request.user  # Устанавливаем текущего пользователя как ответственного
            company.save()
            messages.success(request, f'Компания "{company.name}" успешно создана')
            return redirect('company_detail', company_id=company.id)
    else:
        form = CompanyForm()
    
    context = {
        'form': form,
        'title': 'Создание компании',
    }
    
    return render(request, 'crm/company_form.html', context)

@login_required
def company_update(request, company_id):
    """
    Обновление существующей компании
    """
    company = get_object_or_404(Company, id=company_id)
    
    if request.method == 'POST':
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            company = form.save()
            messages.success(request, f'Компания "{company.name}" успешно обновлена')
            return redirect('company_detail', company_id=company.id)
    else:
        form = CompanyForm(instance=company)
    
    context = {
        'form': form,
        'company': company,
        'title': 'Редактирование компании',
    }
    
    return render(request, 'crm/company_form.html', context)

@login_required
def company_delete(request, company_id):
    """
    Удаление компании
    """
    company = get_object_or_404(Company, id=company_id)
    
    if request.method == 'POST':
        company_name = company.name
        company.delete()
        messages.success(request, f'Компания "{company_name}" успешно удалена')
        return redirect('company_list')
    
    context = {
        'company': company,
    }
    
    return render(request, 'crm/company_confirm_delete.html', context)
