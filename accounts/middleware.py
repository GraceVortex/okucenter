class NoCacheMiddleware:
    """
    Middleware для предотвращения кэширования страниц для авторизованных пользователей.
    Это предотвращает возврат на страницу входа после авторизации через кнопку "Назад" в браузере.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Устанавливаем заголовки для предотвращения кэширования для авторизованных пользователей
        if request.user.is_authenticated:
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        return response
