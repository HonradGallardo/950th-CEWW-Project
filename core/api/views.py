from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
from ..models import Asset, Maintenance, Incident

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats_api(request):
    # 1. Top Counters
    total_assets = Asset.objects.count()
    assigned_assets = Asset.objects.filter(status='Active').count() 
    maintenance_count = Asset.objects.filter(status='Maintenance').count()
    category_stats = Incident.objects.values('category').annotate(count=Count('id'))
    category_labels = [item['category'] for item in category_stats]
    category_totals = [item['count'] for item in category_stats]

    # 2. Chart Data: Asset Distribution 
    asset_stats = Asset.objects.values('assets_type').annotate(count=Count('id'))
    asset_labels = [item['assets_type'] for item in asset_stats]
    asset_totals = [item['count'] for item in asset_stats]

    # 3. Chart Data: Incident Severity
    severity_stats = Incident.objects.exclude(status='Resolved').values('severity').annotate(count=Count('id'))
    severity_labels = [item['severity'] for item in severity_stats]
    severity_totals = [item['count'] for item in severity_stats]

    # 4. Table Data: Recent Maintenance 
    recent_maintenance_qs = Maintenance.objects.select_related('asset', 'technician').order_by('-date')[:5]
    recent_maintenance = [{
        'id': m.id,
        'asset_name': m.asset.assets_name if m.asset else 'Unknown Asset',
        'technician_name': m.technician.username if m.technician else 'Unassigned',
        'status': m.status
    } for m in recent_maintenance_qs]

    # 5. Table Data: Open Incidents 
    open_incidents_qs = Incident.objects.exclude(status='Resolved').order_by('-date')[:5]
    open_incidents_list = [{
            'id': inc.id,
            'title': inc.title, 
            'category': inc.category,  # <--- THIS IS MISSING IN YOUR SCREENSHOT
            'severity': inc.severity,
            'status': inc.status
    } for inc in open_incidents_qs]

    # 6. Trend Data: Incidents over the last 7 days
    today = timezone.now().date()
    # Generates a list of the last 7 days ending with today
    days = [(today - timedelta(days=i)) for i in range(6, -1, -1)]
    trend_labels = [d.strftime('%a') for d in days] # Outputs ['Mon', 'Tue', etc.]
    trend_values = []
    
    # Loop through the days and count incidents. 
    # NOTE: Assuming your Incident model has a DateTime field named 'date'
    for day in days:
        count = Incident.objects.filter(date__date=day).count()
        trend_values.append(count)

    # 7. Maintenance Metrics: Chart Data
    # Provides static arrays for completed vs pending tasks for the chart
    m_labels = ['Work Orders']
    m_completed = [Maintenance.objects.filter(status='Completed').count()]
    m_pending = [Maintenance.objects.filter(status='Pending').count()]

    # 8. Final Response payload sent to AJAX
    return Response({
        'total_assets': total_assets,
        'assigned_assets': assigned_assets,
        'maintenance_count': maintenance_count,
        'category_labels': category_labels,
        'category_totals': category_totals,
        'asset_labels': asset_labels,
        'asset_totals': asset_totals,
        'severity_labels': severity_labels,
        'severity_totals': severity_totals,
        'recent_maintenance': recent_maintenance,
        'open_incidents_list': open_incidents_list,
        'trend_labels': trend_labels,
        'trend_values': trend_values,
        'm_labels': m_labels,
        'm_completed': m_completed,
        'm_pending': m_pending,
    })
    
