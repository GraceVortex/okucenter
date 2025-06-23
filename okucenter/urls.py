"""
URL configuration for okucenter project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from instagram_bot.views import instagram_webhook

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('classes/', include('classes.urls')),
    path('attendance/', include('attendance.urls')),
    path('finance/', include('finance.urls')),
    path('messaging/', include('messaging.urls')),
    path('face-recognition/', include('face_recognition_app.urls')),
    path('crm/', include('crm.urls')),
    path('rosetta/', include('rosetta.urls')),  # Интерфейс для управления переводами
    # Instagram bot URLs - includes webhook and admin dashboard
    path('instagram/', include('instagram_bot.urls')),
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
