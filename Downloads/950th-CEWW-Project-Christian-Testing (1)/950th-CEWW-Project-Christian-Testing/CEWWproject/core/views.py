from urllib import request
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count
from django.contrib import messages
from .models import Asset, Maintenance, Incident
from .forms import AssetForm, MaintenanceForm, UserForm

# --- LANDING & REDIRECT ---
def landing(request):
    return render(request, 'core/landing.html')

@login_required
def role_redirect(request):
    user = request.user
    if user.groups.filter(name__in=['Admin', 'Commander', 'Personnel']).exists():
        return redirect('dashboard')
    return redirect('login')

# --- DASHBOARD ---
@login_required
def dashboard(request):
    # Global Metrics
    total_assets = Asset.objects.count()
    assigned_assets = Asset.objects.exclude(status='Inactive').count() 
    open_incidents_count = Incident.objects.filter(status='Open').count()
    critical_threats = Incident.objects.filter(severity='Critical', status='Open').count()

    context = {
        'total_assets': total_assets,
        'assigned_assets': assigned_assets,
        'open_incidents_count': open_incidents_count,
        'critical_threats': critical_threats,
        'asset_counts': Asset.objects.values('assets_type').annotate(total=Count('id')),
        'severity_counts': Incident.objects.values('severity').annotate(total=Count('id')),
    }

    user_groups = request.user.groups.values_list('name', flat=True)

    if 'Commander' in user_groups:
        return render(request, 'core/commander_dashboard.html', context)
    
    elif 'Personnel' in user_groups:
        personnel_context = {
            'total_assets': total_assets,
            'my_maintenance_count': Maintenance.objects.filter(status='In Progress').count(),
            'reported_incidents_count': Incident.objects.count(), 
            'recent_incidents': Incident.objects.all().order_by('-date')[:5],
        }
        return render(request, 'core/personnel_dashboard.html', personnel_context)
    
    elif 'Admin' in user_groups:
        asset_qs = Asset.objects.values('assets_type').annotate(total=Count('id'))
        context['asset_labels'] = [item['assets_type'] for item in asset_qs]
        context['asset_totals'] = [item['total'] for item in asset_qs]

        severity_qs = Incident.objects.values('severity').annotate(total=Count('id'))
        context['severity_labels'] = [item['severity'] for item in severity_qs]
        context['severity_totals'] = [item['total'] for item in severity_qs]

        context['recent_maintenance'] = Maintenance.objects.all().select_related('asset', 'technician').order_by('-date')[:5]
        context['open_incidents'] = Incident.objects.filter(status='Open').order_by('-date')[:5]
        
        return render(request, 'core/admin_dashboard.html', context)

    return render(request, 'core/landing.html', {'error': 'Unauthorized access.'})

# --- PERSONNEL CRUD ---
@login_required
def user_list(request):
    if not request.user.groups.filter(name__in=['Admin', 'Commander']).exists():
        return redirect('dashboard')
    all_users = User.objects.all().prefetch_related('groups')
    return render(request, 'core/user_list.html', {'users': all_users})

@login_required
def add_user(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            selected_group = form.cleaned_data.get('role')
            if selected_group:
                user.groups.add(selected_group)
            messages.success(request, f"User {user.username} created.")
            return redirect('user_list')
    else:
        form = UserForm()
    return render(request, 'core/user_form.html', {'form': form, 'title': 'Add Personnel'})

@login_required
def edit_user(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = UserForm(request.POST, instance=target_user)
        if form.is_valid():
            user = form.save(commit=False)
            if form.cleaned_data['password']:
                user.set_password(form.cleaned_data['password'])
            user.save()
            selected_group = form.cleaned_data.get('role')
            if selected_group:
                user.groups.clear()
                user.groups.add(selected_group)
            messages.success(request, "User updated successfully!")
            return redirect('user_list')
    else:
        form = UserForm(instance=target_user)
    return render(request, 'core/user_form.html', {'form': form, 'title': 'Edit Personnel'})

@login_required
def delete_user(request, user_id):
    if request.method == 'POST':
        target_user = get_object_or_404(User, id=user_id)
        target_user.delete()
        messages.success(request, "User deleted.")
    return redirect('user_list')

# --- MAINTENANCE MODULE ---
@login_required
def maintenance_list(request):
    # 1. HISTORY: Get all logs (In Progress & Completed)
    maintenances = Maintenance.objects.all().order_by('-date')
    
    # 2. ACTIVE WORK: Get asset IDs that are currently in a log marked 'In Progress'
    # This prevents an asset from being in "Queued" and "History" at the same time
    assets_under_active_repair = Maintenance.objects.filter(
        status='In Progress'
    ).values_list('asset_id', flat=True)

    # 3. QUEUED: Fetch Assets that have status='Maintenance' but no active log yet
    active_maintenance = Asset.objects.filter(
        status='Maintenance'
    ).exclude(
        id__in=assets_under_active_repair
    )

    asset_types = Asset.objects.values_list('assets_type', flat=True).distinct()

    return render(request, 'core/maintenance_list.html', {
        'active_maintenance': active_maintenance,
        'maintenances': maintenances,
        'asset_types': asset_types,
    })

@login_required
def add_maintenance(request):
    asset_id = request.GET.get('asset_id')
    initial_data = {}
    
    if asset_id:
        asset = get_object_or_404(Asset, assets_id=asset_id)
        initial_data['asset'] = asset
        initial_data['notes'] = asset.maintenance_reason

    if request.method == 'POST':
        form = MaintenanceForm(request.POST)
        if form.is_valid():
            log = form.save(commit=False)
            log.technician = request.user
            log.save()

            # PUSH TO ASSET: Update the Asset status based on this log
            asset = log.asset
            if log.status == 'Completed':
                asset.status = 'Active'
                asset.maintenance_reason = "" # Clear the problem description
            else:
                # If 'In Progress', ensure the asset is still marked as 'Maintenance'
                asset.status = 'Maintenance'
            
            asset.save()

            messages.success(request, f"Service log for {asset.assets_id} saved!")
            return redirect('maintenance_list')
    else:
        form = MaintenanceForm(initial=initial_data)

    return render(request, 'core/add_maintenance.html', {'form': form})

@login_required
def edit_maintenance(request, pk):
    log = get_object_or_404(Maintenance, pk=pk)
    if request.method == 'POST':
        form = MaintenanceForm(request.POST, instance=log)
        if form.is_valid():
            updated_log = form.save()
            asset = updated_log.asset
            asset.status = 'Active' if updated_log.status == 'Completed' else 'Maintenance'
            asset.save()
            messages.success(request, "Service log updated.")
            return redirect('maintenance_list')
    else:
        form = MaintenanceForm(instance=log)
    return render(request, 'core/add_maintenance.html', {'form': form, 'edit_mode': True})

@login_required
def delete_maintenance(request, pk):
    maintenance = get_object_or_404(Maintenance, pk=pk)
    asset = maintenance.asset
    if request.method == "POST":
        maintenance.delete()
        # Optional: Reset asset status so it's not 'stuck'
        asset.status = 'Active'
        asset.save()
        messages.success(request, "Service log removed and asset reset to Active.")
    return redirect('maintenance_list')

############################################################### --- ASSET MODULE ---########################################################
@login_required
def asset_list(request):
    assets = Asset.objects.all()
    context = {
        'assets': assets,
        'active_assets_count': assets.filter(status='Active').count(),
        'inactive_assets_count': assets.filter(status='Inactive').count(),
        'maintenance_assets_count': assets.filter(status='Maintenance').count(),
    }
    return render(request, 'core/asset_list.html', context)

@login_required
def add_asset(request):
    if request.method == 'POST':
        form = AssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.assigned_to = request.user 
            asset.save()
            messages.success(request, "Asset registered successfully.")
            return redirect('asset_list')
    else:
        form = AssetForm()
    return render(request, 'core/add_asset.html', {'form': form})

@login_required
def edit_asset(request, asset_id):
    asset = get_object_or_404(Asset, pk=asset_id)
    if request.method == "POST":
        form = AssetForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            messages.success(request, "Asset updated.")
            return redirect('asset_list')
    else:
        form = AssetForm(instance=asset)
    return render(request, 'core/add_asset.html', {'form': form, 'title': f'Edit Asset: {asset.assets_id}'})

@login_required
def delete_asset(request, asset_id):
    asset = get_object_or_404(Asset, pk=asset_id)
    if request.method == "POST":
        asset.delete()
        messages.success(request, "Asset removed.")
    return redirect('asset_list')

# --- OTHER ---
# --- INCIDENT MODULE ---
@login_required
def incident_list(request):
    # Optional: Delete logic if called from this page
    if request.method == 'POST' and request.POST.get('action') == 'delete':
        incident_id = request.POST.get('incident_id')
        incident = get_object_or_404(Incident, id=incident_id)
        incident.delete()
        messages.success(request, "Incident record removed.")
        return redirect('incident_list')

    context = {
        'incidents': Incident.objects.all().order_by('-date'),
        'assets': Asset.objects.all(),
    }
    return render(request, 'core/incident_list.html', context)

@login_required
def add_incident(request):
    if request.method == 'POST':
        # 1. Get the data from the POST request
        title = request.POST.get('title')
        severity = request.POST.get('severity')
        status = request.POST.get('status') # This captures "Investigating"
        description = request.POST.get('description')
        affected_area = request.POST.get('affected_area')

        # 2. Save it to the database
        Incident.objects.create(
            title=title,
            severity=severity,
            status=status,  # This ensures the choice is saved
            description=f"Area: {affected_area}\n\n{description}",
            # date is usually auto_now_add in models.py
        )
        
        messages.success(request, "Incident reported successfully!")
        return redirect('incident_list')

    # If GET, just show the form
    return render(request, 'core/add_incident.html')

@login_required
def edit_incident(request, incident_id):  # Make sure this matches the URL keyword
    incident = get_object_or_404(Incident, id=incident_id)
    
    if request.method == 'POST':
        incident.status = request.POST.get('status')
        incident.save()
        return redirect('incident_list')
        
    return render(request, 'core/edit_incident.html', {'incident': incident})

@login_required
def delete_incident(request, incident_id):
    incident = get_object_or_404(Incident, id=incident_id)
    incident.delete()
    return redirect('incident_list')

@login_required
def analytics(request):
    if request.user.groups.filter(name='Personnel').exists():
        messages.warning(request, "Access denied.")
        return redirect('dashboard')
    context = {
        'total_assets': Asset.objects.count(),
        'asset_counts': Asset.objects.values('assets_type').annotate(total=Count('id')),
        'severity_counts': Incident.objects.values('severity').annotate(total=Count('id')),
        'status_counts': Incident.objects.values('status').annotate(total=Count('id')),
    }
    return render(request, 'core/analytics.html', context)

@login_required
def reports(request):
    return render(request, 'core/reports.html')