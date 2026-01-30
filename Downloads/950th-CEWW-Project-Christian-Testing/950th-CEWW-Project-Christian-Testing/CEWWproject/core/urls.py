from django.urls import path
from . import views

urlpatterns = [
    # Public Landing Page
    path('', views.landing, name='landing'),
    
    # Logic to decide which dashboard to show
    path('role-redirect/', views.role_redirect, name='role_redirect'),
    
    # The unified Dashboard URL
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Sidebar Functional Modules
    path('assets/', views.asset_list, name='asset_list'),
    path('maintenance/', views.maintenance_list, name='maintenance_list'),
    path('incidents/', views.incident_list, name='incident_list'),
    path('users/', views.user_list, name='user_list'),
    path('reports/', views.reports, name='reports'),
    
    #Crud for Personnel
    path('users/add/', views.add_user, name='add_user'),
    path('users/edit/<int:user_id>/', views.edit_user, name='edit_user'),
    path('users/delete/<int:user_id>/', views.delete_user, name='delete_user'),

]