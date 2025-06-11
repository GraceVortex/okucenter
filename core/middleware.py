from django.utils import translation
from django.conf import settings

class LanguageMiddleware:
    """
    Middleware для автоматической активации языка для каждого запроса
    на основе значения в сессии или cookie.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Получаем язык из сессии или cookie, по умолчанию русский
        user_language = request.session.get(
            'user_language', 
            request.session.get(
                'django_language',
                request.COOKIES.get('user_language', 
                    request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME, 'ru')
                )
            )
        )
        
        # Активируем выбранный язык для текущего запроса
        translation.activate(user_language)
        request.LANGUAGE_CODE = user_language
        
        # Добавляем в сессию для контекстного процессора
        request.session['user_language'] = user_language
        
        response = self.get_response(request)
        
        # Устанавливаем язык для ответа
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, user_language)
        response.set_cookie('user_language', user_language, max_age=365 * 24 * 60 * 60)
        
        return response
