from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from django.conf import settings
from django.conf.urls.static import static

router = DefaultRouter()
router.register(r'assets', views.AssetViewSet)
router.register(r'maintenance', views.MaintenanceViewSet)
router.register(r'incidents', views.IncidentViewSet)

urlpatterns = [
    # --- API ENDPOINTS ---
    # This creates paths like /api/assets/ and /api/incidents/
    path('api/', include(router.urls)),

    # --- EXISTING VIEW PATHS ---
    path('', views.landing, name='landing'),
    path('role-redirect/', views.role_redirect, name='role_redirect'),
    path('dashboard/', views.dashboard, name='dashboard'),
    # Public Landing Page
    path('', views.landing, name='landing'),
    
    # Logic to decide which dashboard to show
    path('role-redirect/', views.role_redirect, name='role_redirect'),
    
    # The unified Dashboard URL
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Sidebar Functional Modules
    path('assets/', views.asset_list, name='asset_list'),
    path('command_asset/', views.command_asset, name='command_asset'),
    path('assets/add/', views.add_asset, name='add_asset'),
    path('assets/edit/<int:asset_id>/', views.edit_asset, name='edit_asset'),
    path('assets/delete/<int:asset_id>/', views.delete_asset, name='delete_asset'),
    path("admin_tickets/", views.admin_ticket_dashboard, name="admin_tickets"),
    path("submit_ticket/", views.submit_ticket, name="submit_ticket"),
    path("command_submit_ticket/", views.command_submit_ticket, name="command_submit_ticket"),
    # Admin views
    path("admin_tickets/", views.admin_ticket_dashboard, name="admin_tickets"),
    path('manage/ticket/<int:ticket_id>/', views.ticket_detail, name='ticket_detail'),




    path('maintenance/', views.maintenance_list, name='maintenance_list'),
    path('command_maintenance/', views.command_maintenance, name='command_maintenance'),
    path('maintenance/add/', views.add_maintenance, name='add_maintenance'),
    path('maintenance/edit/<int:pk>/', views.edit_maintenance, name='edit_maintenance'),
    path('maintenance/delete/<int:pk>/', views.delete_maintenance, name='delete_maintenance'),



    path('incidents/', views.incident_list, name='incident_list'),
    path('command_incidents/', views.command_incident, name='command_incident'),
    path('incidents/add/', views.add_incident, name='add_incident'),
    path('incidents/edit/<int:incident_id>/', views.edit_incident, name='edit_incident'),
    path('incidents/delete/<int:incident_id>/', views.delete_incident, name='delete_incident'),
    path('incidents/<int:incident_id>/comments/', views.get_incident_comments, name='get_comments'),



    path('command_analytics/', views.commander_analytics, name='command_analytics'),
    path('analytics_list/', views.analytics_list, name='analytics_list'),
    path('users/', views.user_list, name='user_list'),
    path('reports/', views.reports, name='reports'),
    path('command_reports/', views.command_reports, name='command_reports'),

    #Crud for Personnel
    path('users/add/', views.add_user, name='add_user'),
    path('users/edit/<int:user_id>/', views.edit_user, name='edit_user'),
    path('users/delete/<int:user_id>/', views.delete_user, name='delete_user'),

    path('tickets/chat/<int:ticket_id>/', views.get_ticket_chat, name='get_ticket_chat'),
    path('tickets/chat/<int:ticket_id>/send/', views.send_ticket_message, name='send_ticket_message'),
    path('send-message/<int:ticket_id>/', views.send_message, name='send_message'),
    path('update-ticket-status/<int:ticket_id>/', views.update_ticket_status, name='update_ticket_status'),
    path('delete-ticket/<int:ticket_id>/', views.delete_ticket, name='delete_ticket'),


    # Personnel URL
    path('personnel/submit-ticket/', views.handle_ticket_submission, 
         {'template_path': 'core/Personnel/submit_ticket.html'}, name='submit_ticket'),

    # Commander URL
    path('command_submit_ticket/', views.handle_ticket_submission, 
         {'template_path': 'core/Commander/command_tickets.html'}, name='command_submit_ticket'),

    path('commander/command_tickets/', views.command_submit_ticket, name='command_submit_ticket'),

    path('notifications/read-all/', views.mark_all_as_read, name='mark_all_read'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/password/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    
    

]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)