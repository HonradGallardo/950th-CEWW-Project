from rest_framework import viewsets
from ..models import Asset, Maintenance, Incident, Notification
from .serializers import AssetSerializer, MaintenanceSerializer, IncidentSerializer
from rest_framework.decorators import action
from django.contrib.auth.models import User
from rest_framework.response import Response
from django.db.models import Q

from core.api.serializers import (
    UserSerializer, 
    AssetSerializer, 
    MaintenanceSerializer, 
    IncidentSerializer
)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().prefetch_related('groups', 'profile').order_by('username')
    serializer_class = UserSerializer

    @action(detail=False, methods=['get'], url_path='live_search')
    def live_search(self, request):
        """Processes AJAX search and role filtering safely."""
        query = request.GET.get('q', '').strip()
        role = request.GET.get('role', 'ALL').upper()
        
        users = self.get_queryset()
        
        if query:
            users = users.filter(
                Q(username__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query)
            ).distinct()

        if role != 'ALL':
            users = users.filter(groups__name__iexact=role) if role != 'UNASSIGNED' else users.filter(groups__isnull=True)
        
        data = []
        for u in users[:20]:
            # SAFE PROFILE CHECK: Prevents the RelatedObjectDoesNotExist crash
            has_profile = hasattr(u, 'profile')
            
            data.append({
                'id': u.id,
                'username': u.username,
                'full_name': u.get_full_name() or u.username,
                'email': u.email,
                'role': u.groups.all()[0].name if u.groups.exists() else 'Unassigned',
                'last_login': u.last_login.strftime('%d-%m-%y') if u.last_login else 'Never',
                'date_joined': u.date_joined.strftime('%b %Y'),
                # Safely fall back to 'Airman' if profile is missing
                'rank': u.profile.rank if has_profile else 'Airman',
                'image_url': u.profile.image.url if has_profile and u.profile.image else None
            })
        
        return Response(data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Fixes the 404 for Directory Sync."""
        return Response({"status": "online", "count": User.objects.count()})
    
class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer

class MaintenanceViewSet(viewsets.ModelViewSet):
    queryset = Maintenance.objects.all()
    serializer_class = MaintenanceSerializer

class IncidentViewSet(viewsets.ModelViewSet):
    queryset = Incident.objects.all()
    serializer_class = IncidentSerializer

class NotificationViewSet(viewsets.ModelViewSet):
    """API for dynamic notification bell updates."""
    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by('-created_at')