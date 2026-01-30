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
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from core import views
urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 1. Landing Page (Home)
    path('', TemplateView.as_view(template_name='core/landing.html'), name='home'),
    
    # 2. Login Page
    path('accounts/', include('django.contrib.auth.urls')), 
    
    # 3. Include Core URLs
    path('', include('core.urls')), # This connects the paths you made earlier
    
    # 4. User Edit Path
    path('users/edit/<int:user_id>/', views.edit_user, name='edit_user'),
]