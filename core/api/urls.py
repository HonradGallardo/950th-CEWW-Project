from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.api import views
from .viewsets import AssetViewSet, DashboardStatsAPI, MaintenanceViewSet, IncidentViewSet, NotificationViewSet

router = DefaultRouter()
router.register(r'assets', AssetViewSet)
router.register(r'maintenance', MaintenanceViewSet)
router.register(r'incidents', IncidentViewSet)
router.register(r'notifications', NotificationViewSet, basename='api-notifications')

urlpatterns = [
    path('api/personnel/stats/', views.dashboard_stats_api, name='personnel-stats-api'),
    path('api/dashboard-stats/', DashboardStatsAPI.as_view(), name='dashboard_stats_api'),
    
    # EXACT matches for your frontend JavaScript
    path('api/report/it-asset/', AssetViewSet.as_view({'get': 'list'})),
    path('api/report/maintenance/', MaintenanceViewSet.as_view({'get': 'list'})),
    path('api/report/incident/', IncidentViewSet.as_view({'get': 'list'})),
    
    path('', include(router.urls)),
]