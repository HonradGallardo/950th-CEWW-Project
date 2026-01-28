from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # New paths for the sidebar buttons
    path('assets/', views.asset_list, name='asset_list'),
    path('maintenance/', views.maintenance_list, name='maintenance_list'),
    path('incidents/', views.incident_list, name='incident_list'),
    path('users/', views.user_list, name='user_list'),
    path('reports/', views.reports, name='reports'),
]