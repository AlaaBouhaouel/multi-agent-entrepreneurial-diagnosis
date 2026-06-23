from django.urls import path
from . import views

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='index'),
    path('api/session/start/',   views.session_start,   name='session_start'),
    path('api/session/message/', views.session_message, name='session_message'),
    path('api/analysis/start/',  views.analysis_start,  name='analysis_start'),
    path('api/analysis/ask/',    views.analysis_ask,    name='analysis_ask'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
