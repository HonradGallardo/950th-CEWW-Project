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
    path('assets/add/', views.add_asset, name='add_asset'),
    path('assets/edit/<int:asset_id>/', views.edit_asset, name='edit_asset'),
    path('assets/delete/<int:asset_id>/', views.delete_asset, name='delete_asset'),
    path('maintenance/', views.maintenance_list, name='maintenance_list'),
    path('maintenance/add/', views.add_maintenance, name='add_maintenance'),
    path('maintenance/edit/<int:pk>/', views.edit_maintenance, name='edit_maintenance'),
    path('maintenance/delete/<int:pk>/', views.delete_maintenance, name='delete_maintenance'),
    path('maintenance/', views.maintenance_list, name='maintenance_list'),
    path('maintenance/add/', views.add_maintenance, name='add_maintenance'),
    path('maintenance/edit/<int:pk>/', views.edit_maintenance, name='edit_maintenance'),
    path('incidents/', views.incident_list, name='incident_list'),
    path('incidents/add/', views.add_incident, name='add_incident'),
    path('incidents/edit/<int:incident_id>/', views.edit_incident, name='edit_incident'),
    path('incidents/delete/<int:incident_id>/', views.delete_incident, name='delete_incident'),
    path('analytics/', views.analytics, name='analytics'),
    path('users/', views.user_list, name='user_list'),
    path('reports/', views.reports, name='reports'),
    
    #Crud for Personnel
    path('users/add/', views.add_user, name='add_user'),
    path('users/edit/<int:user_id>/', views.edit_user, name='edit_user'),
    path('users/delete/<int:user_id>/', views.delete_user, name='delete_user'),

]