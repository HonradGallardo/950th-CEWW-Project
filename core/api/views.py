from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..models import Asset, Maintenance, Incident
from .serializers import AssetSerializer, MaintenanceSerializer, IncidentSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats_api(request):
    """Unified endpoint for dashboard statistics"""
    assets = Asset.objects.all()
    maintenance = Maintenance.objects.all().order_by('-date')[:5]
    incidents = Incident.objects.all().order_by('-date')[:5]

    return Response({
        'assets': AssetSerializer(assets, many=True).data,
        'recent_maintenance': MaintenanceSerializer(maintenance, many=True).data,
        'recent_incidents': IncidentSerializer(incidents, many=True).data
    })