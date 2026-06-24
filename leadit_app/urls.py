from django.urls import path
from . import views

from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.index, name='index'),
    path(
        'login/',
        auth_views.LoginView.as_view(template_name='registration/login.html'),
        name='login',
    ),
    path('logout/', views.logout_view, name='logout'),
    path('logged-out/', views.logged_out, name='logged_out'),
    path('api/session/start/',   views.session_start,   name='session_start'),
    path('api/session/message/', views.session_message, name='session_message'),
    path('api/analysis/start/',  views.analysis_start,  name='analysis_start'),
    path('api/analysis/ask/',    views.analysis_ask,    name='analysis_ask'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
