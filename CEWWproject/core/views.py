from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Asset, Maintenance, Incident
from django.db.models import Count

# 1. New Landing Page View
def landing(request):
    return render(request, 'core/landing.html')

@login_required
def asset_list(request):
    assets = Asset.objects.all()
    return render(request, 'core/asset_list.html', {'assets': assets})

@login_required
def maintenance_list(request):
    maintenances = Maintenance.objects.all()
    return render(request, 'core/maintenance_list.html', {'maintenances': maintenances})

@login_required
def incident_list(request):
    incidents = Incident.objects.all()
    return render(request, 'core/incident_list.html', {'incidents': incidents})

# Simple placeholders for Users and Reports
@login_required
def user_list(request):
    return render(request, 'core/user_list.html')

@login_required
def reports(request):
    return render(request, 'core/reports.html')

# 2. Secure Dashboard View
@login_required # Re-enable this so users must log in first
def dashboard(request):
    total_assets = Asset.objects.count()
    assigned_assets = Asset.objects.exclude(assigned_to=None).count()
    open_incidents = Incident.objects.filter(status='Open').count()

    asset_counts = Asset.objects.values('asset_type').annotate(total=Count('id'))
    incidents_by_severity = Incident.objects.values('severity').annotate(total=Count('id'))

    recent_maintenance = Maintenance.objects.order_by('-date')[:5]
    recent_incidents = Incident.objects.order_by('-date')[:5]

    context = {
        'total_assets': total_assets,
        'assigned_assets': assigned_assets,
        'open_incidents': open_incidents,
        'asset_counts': asset_counts,
        'incidents_by_severity': incidents_by_severity,
        'recent_maintenance': recent_maintenance,
        'recent_incidents': recent_incidents,
    }

    return render(request, 'core/dashboard.html', context)