from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import AssetViewSet, MaintenanceViewSet, IncidentViewSet, NotificationViewSet

router = DefaultRouter()
router.register(r'assets', AssetViewSet)
router.register(r'maintenance', MaintenanceViewSet)
router.register(r'incidents', IncidentViewSet)
router.register(r'notifications', NotificationViewSet, basename='api-notifications')

urlpatterns = [
    path('', include(router.urls)),
]