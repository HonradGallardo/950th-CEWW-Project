from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from django.views.generic import TemplateView
from . import views
from django.contrib.auth import views as auth_views
# Import modular viewsets
from core.api.viewsets import AssetViewSet, ChangePasswordAPI, IncidentCommentViewSet, MaintenanceViewSet, IncidentViewSet, MonitoringDataAPI, NotificationViewSet, UserViewSet, DashboardStatsAPI,ForgotPasswordAPI, APILoginView, VerifyMFAAPI, PersonnelStatsAPI, generate_authenticator_qr, verify_totp_setup

router = DefaultRouter()
router.register(r'assets', AssetViewSet)
router.register(r'maintenance', MaintenanceViewSet)
router.register(r'incidents', IncidentViewSet)
router.register(r'notifications', NotificationViewSet, basename='api-notifications')
router.register(r'incident-comments', IncidentCommentViewSet, basename='api-incident-comments')
router.register(r'users', UserViewSet, basename='api-users')

# --- FIX: ATTACH THE 3 CUSTOM REPORT ENDPOINTS TO THE ROUTER ---
router.register(r'report/it-asset', AssetViewSet, basename='report-it-asset')
router.register(r'report/maintenance', MaintenanceViewSet, basename='report-maintenance')
router.register(r'report/incident', IncidentViewSet, basename='report-incident')

urlpatterns = [
    # --- 1. CUSTOM API ENDPOINTS (MUST BE ABOVE THE ROUTER) ---
    path('api/verify-mfa/', VerifyMFAAPI.as_view(), name='api_verify_mfa'),
    path('api/dashboard-stats/', DashboardStatsAPI.as_view(), name='dashboard_stats_api'),
    path('api/personnel/stats/', PersonnelStatsAPI.as_view(), name='personnel_stats_api'),
    path('api/monitoring-data/', MonitoringDataAPI.as_view(), name='monitoring_data_api'),
    path('api/forgot-password/', ForgotPasswordAPI.as_view(), name='api_forgot_password'),
    path('api/change-password/', ChangePasswordAPI.as_view(), name='api_change_password'),
    path('api/totp/generate/', generate_authenticator_qr, name='api_generate_totp'),
    path('api/totp/verify-setup/', verify_totp_setup, name='api_verify_totp_setup'),
    # --- 2. API DATA HUB ---
    # Because of this line below, the router automatically adds "/api/" 
    # to "report/it-asset", making it exactly what your Javascript wants!
    path('api/', include(router.urls)),
    path('api/core/', include(router.urls)),

    # --- 3. CORE PAGES ---
    path('', views.landing, name='landing'),
    path('login/', APILoginView.as_view(), name='login'),
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
    path('settings/password/', TemplateView.as_view(template_name='core/Admin/password_change.html'), name='custom_password_change'),
    path('forgot_password/', views.forgot_password_view, name='forgot_password'),
    
    # Note: I left this duplicate login path as it was in your file, 
    # but normally you only want one 'login/' path!
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)