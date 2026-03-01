from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from . import views
# Import modular viewsets
from core.api.viewsets import AssetViewSet, MaintenanceViewSet, IncidentViewSet, NotificationViewSet, UserViewSet

router = DefaultRouter()
router.register(r'assets', AssetViewSet)
router.register(r'maintenance', MaintenanceViewSet)
router.register(r'incidents', IncidentViewSet)
router.register(r'notifications', NotificationViewSet, basename='api-notifications')
router.register(r'users', UserViewSet, basename='api-users')

urlpatterns = [
    # --- API DATA HUB ---
    path('api/', include(router.urls)),
    path('api/core/', include(router.urls)),

    # --- CORE PAGES ---
    path('', views.landing, name='landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('role-redirect/', views.role_redirect, name='role_redirect'),
    path('profile/', views.profile_view, name='profile'),
    
    # --- ASSETS ---
    path('assets/', views.asset_list, name='asset_list'),
    path('assets/add/', views.add_asset, name='add_asset'),
    path('assets/edit/<int:asset_id>/', views.edit_asset, name='edit_asset'),
    path('assets/delete/<int:asset_id>/', views.delete_asset, name='delete_asset'),

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

    # --- PERSONNEL & REPORTS ---
    path('users/', views.user_list, name='user_list'),
    path('users/add/', views.add_user, name='add_user'),
    path('users/edit/<int:user_id>/', views.edit_user, name='edit_user'),
    path('users/delete/<int:user_id>/', views.delete_user, name='delete_user'),
    path('analytics_list/', views.analytics_list, name='analytics_list'),
    path('reports/', views.reports, name='reports'),
    path('notifications/read-all/', views.mark_all_as_read, name='mark_all_read'),
    path('forgot_password/', views.forgot_password_view, name='forgot_password'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)