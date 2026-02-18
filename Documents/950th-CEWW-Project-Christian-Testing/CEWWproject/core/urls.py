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
    path('api/', include(router.urls)),

    # --- CORE NAVIGATION ---
    path('', views.landing, name='landing'),
    path('role-redirect/', views.role_redirect, name='role_redirect'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # --- ASSETS ---
    path('assets/', views.asset_list, name='asset_list'),
    path('assets/add/', views.add_asset, name='add_asset'),
    path('assets/edit/<int:asset_id>/', views.edit_asset, name='edit_asset'),
    path('assets/delete/<int:asset_id>/', views.delete_asset, name='delete_asset'),

    # --- TICKETS & CHAT (FIXED SECTION) ---
    path("admin_tickets/", views.admin_ticket_dashboard, name="admin_tickets"),
    path('manage/ticket/<int:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path("submit_ticket/", views.submit_ticket, name="submit_ticket"),
    path('delete-ticket/<int:ticket_id>/', views.delete_ticket, name='delete_ticket'),
    
    # Status Update Path
    path('update-ticket-status/<int:ticket_id>/', views.update_ticket_status, name='update_ticket_status'),
    
    # Chat Paths - ONLY ONE 'SEND' PATH ALLOWED
    path('tickets/chat/<int:ticket_id>/', views.get_ticket_chat, name='get_ticket_chat'),
    path('tickets/chat/<int:ticket_id>/send/', views.send_ticket_message, name='send_ticket_message'),

    # --- MAINTENANCE ---
    path('maintenance/', views.maintenance_list, name='maintenance_list'),
    path('maintenance/add/', views.add_maintenance, name='add_maintenance'),
    path('maintenance/edit/<int:pk>/', views.edit_maintenance, name='edit_maintenance'),
    path('maintenance/delete/<int:pk>/', views.delete_maintenance, name='delete_maintenance'),

    # --- INCIDENTS ---
    path('incidents/', views.incident_list, name='incident_list'),
    path('incidents/add/', views.add_incident, name='add_incident'),
    path('incidents/edit/<int:incident_id>/', views.edit_incident, name='edit_incident'),
    path('incidents/delete/<int:incident_id>/', views.delete_incident, name='delete_incident'),
    path('incidents/<int:incident_id>/comments/', views.get_incident_comments, name='get_comments'),

    # --- ANALYTICS & USERS ---
    path('analytics_list/', views.analytics_list, name='analytics_list'),
    path('users/', views.user_list, name='user_list'),
    path('users/add/', views.add_user, name='add_user'),
    path('users/edit/<int:user_id>/', views.edit_user, name='edit_user'),
    path('users/delete/<int:user_id>/', views.delete_user, name='delete_user'),

    # --- REPORTS & PROFILE ---
    path('reports/', views.reports, name='reports'),
    path('notifications/read-all/', views.mark_all_as_read, name='mark_all_read'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/password/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('forgot_password/', views.forgot_password_view, name='forgot_password'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)