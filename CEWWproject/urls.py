"""
URL configuration for CEWWproject project.

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
"""
URL configuration for CEWWproject project.
"""
from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from core import views  # <-- 1. This remains as 'views' for your core app
from django.conf.urls.static import static
from core.api import views as api_views
from rest_framework.authtoken import views as auth_views

from core.api.viewsets import PasskeyLoginOptionsAPI, PasskeyLoginVerifyAPI, PasskeyRegisterOptionsAPI, PasskeyRegisterVerifyAPI  # <-- 2. ALIASED to auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 1. Landing Page (Home)
    path('', TemplateView.as_view(template_name='core/landing.html'), name='home'),
    
    # 2. Login Page
    path('accounts/', include('django.contrib.auth.urls')), 
    
    # 3. Include Core URLs
    path('', include('core.urls')), 
    
    # 4. User Edit Path
    path('users/edit/<int:user_id>/', views.edit_user, name='edit_user'), # <-- Now uses core.views
    path('api/personnel/stats/', api_views.dashboard_stats_api, name='personnel-stats-api'),
    
    # --- TICKETS APP ---
    path('tickets/', include('tickets.urls')),

    # --- API PATHS ---
    path('api-token-auth/', auth_views.obtain_auth_token, name='api_token_auth'), # <-- 3. Uses the new alias
    
    # Give the API a unique namespace to distinguish it from standard views
    path('api/tickets/', include('tickets.api.urls', namespace='tickets-api')),
    path('api/core/', include('core.api.urls')),
    path('api/webauthn/login-options/', PasskeyLoginOptionsAPI.as_view(), name='passkey_options'),
    path('api/webauthn/login-verify/', PasskeyLoginVerifyAPI.as_view(), name='passkey_verify'),
    path('api/webauthn/register-options/', PasskeyRegisterOptionsAPI.as_view(), name='passkey_register_options'),
    path('api/webauthn/register-verify/', PasskeyRegisterVerifyAPI.as_view(), name='passkey_register_verify'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)