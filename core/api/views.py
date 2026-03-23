from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count
from ..models import Asset, Maintenance, Incident

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats_api(request):
    # 1. Top Counters
    total_assets = Asset.objects.count()
    assigned_assets = Asset.objects.filter(status='Active').count() 
    maintenance_count = Asset.objects.filter(status='Maintenance').count()
    
    # Assuming incidents have a status; if not, just use Incident.objects.count()
    open_incidents = Incident.objects.exclude(status='Resolved').count() 

    # 2. Chart Data: Asset Distribution (Groups assets by type and counts them)
    asset_stats = Asset.objects.values('assets_type').annotate(count=Count('id'))
    asset_labels = [item['assets_type'] for item in asset_stats]
    asset_totals = [item['count'] for item in asset_stats]

    # 3. Chart Data: Incident Severity
    severity_stats = Incident.objects.exclude(status='Resolved').values('severity').annotate(count=Count('id'))
    severity_labels = [item['severity'] for item in severity_stats]
    severity_totals = [item['count'] for item in severity_stats]

    # 4. Table Data: Recent Maintenance (Mapped perfectly for your JS)
    recent_maintenance_qs = Maintenance.objects.select_related('asset', 'technician').order_by('-date')[:5]
    recent_maintenance = [{
        'id': m.id,
        'asset_name': m.asset.assets_name if m.asset else 'Unknown Asset',
        'technician_name': m.technician.username if m.technician else 'Unassigned',
        'status': m.status
    } for m in recent_maintenance_qs]

    # 5. Table Data: Open Incidents (Mapped perfectly for your JS)
    open_incidents_qs = Incident.objects.exclude(status='Resolved').order_by('-date')[:5]
    open_incidents_list = [{
        'id': inc.id,
        'title': inc.title, # Or whatever your incident name field is
        'severity': inc.severity,
        'status': inc.status
    } for inc in open_incidents_qs]

    # 6. Send the perfectly formatted JSON back to the frontend
    return Response({
        'total_assets': total_assets,
        'assigned_assets': assigned_assets,
        'maintenance_count': maintenance_count,
        'open_incidents': open_incidents,
        'asset_labels': asset_labels,
        'asset_totals': asset_totals,
        'severity_labels': severity_labels,
        'severity_totals': severity_totals,
        'recent_maintenance': recent_maintenance,
        'open_incidents_list': open_incidents_list
    })