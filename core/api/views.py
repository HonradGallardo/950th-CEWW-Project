from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..models import Asset, Maintenance, Incident
from .serializers import AssetSerializer, MaintenanceSerializer, IncidentSerializer, UserSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats_api(request):
    # Optimized: Use .count() instead of serializing everything for the counter
    total_assets_count = Asset.objects.count()
    
    # Select related fields to prevent N+1 queries in the serializer
    maintenance = Maintenance.objects.select_related('asset', 'technician').all().order_by('-date')[:5]
    incidents = Incident.objects.select_related('reported_by').all().order_by('-date')[:10]

    return Response({
        'total_assets_count': total_assets_count,
        'assets': AssetSerializer(Asset.objects.all()[:5], many=True).data, # Just recent 5 for the table
        'recent_maintenance': MaintenanceSerializer(maintenance, many=True).data,
        'recent_incidents': IncidentSerializer(incidents, many=True, context={'request': request}).data,
        'user_info': UserSerializer(request.user).data
    })