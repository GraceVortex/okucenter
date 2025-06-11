def language_context(request):
    """
    Контекстный процессор для добавления выбранного языка в контекст шаблона.
    Загружает переводы из файла translations_to_do.txt и делает их доступными в шаблонах.
    """
    # Получаем язык из сессии или cookie, по умолчанию русский
    user_language = request.session.get('user_language', request.COOKIES.get('user_language', 'ru'))
    
    # Базовые переводы для ключевых элементов интерфейса
    base_translations = {
        'ru': {
            'site_name': 'Образовательный центр',
            'home': 'Главная',
            'classes': 'Классы',
            'schedule': 'Расписание',
            'students': 'Студенты',
            'teachers': 'Преподаватели',
            'finances': 'Финансы',
            'profile': 'Профиль',
            'logout': 'Выйти',
            'my_children': 'Мои дети',
            'cancellation_requests': 'Запросы на отмену',
            'quick_access': 'Быстрый доступ',
            'face_recognition': 'Распознавание лиц',
        },
        'kk': {
            'site_name': 'Оқу орталығы',
            'home': 'Басты бет',
            'classes': 'Сыныптар',
            'schedule': 'Кесте',
            'students': 'Оқушылар',
            'teachers': 'Мұғалімдер',
            'finances': 'Қаржы',
            'profile': 'Профиль',
            'logout': 'Шығу',
            'my_children': 'Менің балаларым',
            'cancellation_requests': 'Болдырмау сұраулары',
            'quick_access': 'Жылдам кіру',
            'face_recognition': 'Бетті тану',
        }
    }
    
    # Словарь для всех текстов (ключ - русский текст, значение - перевод)
    all_translations = {
        'ru': {},
        'kk': {}
    }
    
    # Сначала добавляем базовые переводы
    for lang in ['ru', 'kk']:
        all_translations[lang].update(base_translations[lang])
    
    # Затем добавляем все переводы из файла translations_to_do.txt
    try:
        with open('translations_to_do.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '|' not in line:
                    continue
                    
                parts = line.split('|')
                if len(parts) == 2:
                    ru_text = parts[0].strip()
                    kk_text = parts[1].strip()
                    
                    if ru_text and kk_text and ru_text != 'Русский текст':
                        # Добавляем в словарь переводов
                        all_translations['ru'][ru_text] = ru_text
                        all_translations['kk'][ru_text] = kk_text
                        
                        # Также добавляем перевод для ключа в нижнем регистре (для удобства)
                        key = ru_text.lower().replace(' ', '_')
                        all_translations['ru'][key] = ru_text
                        all_translations['kk'][key] = kk_text
    except Exception as e:
        print(f"Ошибка при загрузке переводов: {e}")
    
    # Функция для перевода текста
    def translate_text(text, target_lang='ru'):
        if target_lang == 'ru':
            return text
        
        # Проверяем, есть ли прямой перевод
        if text in all_translations[target_lang]:
            return all_translations[target_lang][text]
        
        # Проверяем, есть ли перевод для ключа в нижнем регистре
        key = text.lower().replace(' ', '_')
        if key in all_translations[target_lang]:
            return all_translations[target_lang][key]
        
        # Если перевода нет, возвращаем исходный текст
        return text
    
    return {
        'user_language': user_language,
        'trans': all_translations.get(user_language, all_translations['ru']),
        'all_translations': all_translations,
        'translate': lambda text: translate_text(text, user_language),
        'LANGUAGE_CODE': user_language,
    }
