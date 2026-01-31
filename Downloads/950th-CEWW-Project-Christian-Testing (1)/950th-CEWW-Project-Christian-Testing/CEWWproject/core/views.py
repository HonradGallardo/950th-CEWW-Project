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
    # --- 1. GLOBAL METRICS (For Commander/Admin) ---
    total_assets = Asset.objects.count()
    
    # FIX: 'assigned_to' no longer exists. 
    # Let's count assets that are not 'Inactive' instead, 
    # or you can count based on 'location'
    assigned_assets = Asset.objects.exclude(status='Inactive').count() 
    
    open_incidents = Incident.objects.filter(status='Open').count()
    critical_threats = Incident.objects.filter(severity='Critical', status='Open').count()

    # Base context
    context = {
        'total_assets': total_assets,
        'assigned_assets': assigned_assets,
        'open_incidents': open_incidents,
        'critical_threats': critical_threats,
        'asset_counts': Asset.objects.values('assets_type').annotate(total=Count('id')), # Changed to assets_type
        'severity_counts': Incident.objects.values('severity').annotate(total=Count('id')),
    }

    # --- 2. ROLE-BASED LOGIC ---
    user_groups = request.user.groups.values_list('name', flat=True)

    if 'Commander' in user_groups:
        return render(request, 'core/commander_dashboard.html', context)
    
    elif 'Personnel' in user_groups:
        personnel_context = {
            'total_assets': total_assets,
            # FIX: Maintenance logic needs to reference existing fields.
            # If you no longer have a link between Asset and User, 
            # we'll just show all pending maintenance for now.
            'my_maintenance_count': Maintenance.objects.filter(status='In Progress').count(),
            'reported_incidents_count': Incident.objects.count(), 
            'recent_incidents': Incident.objects.all().order_by('-date')[:5],
        }
        return render(request, 'core/personnel_dashboard.html', personnel_context)
    
    elif 'Admin' in user_groups:
        context['recent_maintenance'] = Maintenance.objects.all().order_by('-date')[:5]
        context['recent_incidents'] = Incident.objects.all().order_by('-date')[:5]
        return render(request, 'core/admin_dashboard.html', context)

    return render(request, 'core/landing.html', {'error': 'Unauthorized access.'})

# --- PERSONNEL CRUD (CLEANED) ---
@login_required
def user_list(request):
    if not request.user.groups.filter(name__in=['Admin', 'Commander']).exists():
        return redirect('dashboard')
    
    # We use 'users' as the key to match your HTML {% for person in users %}
    all_users = User.objects.all().prefetch_related('groups')
    return render(request, 'core/user_list.html', {'users': all_users})

@login_required
def add_user(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save() # User must be saved before we can add groups
            
            # Now handle the Role/Group
            selected_group = form.cleaned_data.get('role')
            if selected_group:
                user.groups.add(selected_group)
            
            messages.success(request, f"User {user.username} created with role {selected_group.name}")
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
            
            # Update the Role/Group
            selected_group = form.cleaned_data.get('role')
            if selected_group:
                user.groups.clear() # Remove old roles first!
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
        messages.success(request, "User deleted successfully.")
    return redirect('user_list')

# --- OTHER MODULES ---
@login_required
def asset_list(request):
    return render(request, 'core/asset_list.html', {'assets': Asset.objects.all()})

################################################################## --- MAINTENANCE CRUD --- ##################################################################
@login_required
def maintenance_list(request):
    # Fetch assets currently set to 'Maintenance' status
    active_maintenance = Asset.objects.filter(status='Maintenance')
    
    # Fetch all completed service logs for the history
    history = Maintenance.objects.all().select_related('asset', 'technician').order_by('-date')

    return render(request, 'core/maintenance_list.html', {
        'active_maintenance': active_maintenance,
        'maintenances': history
    })

@login_required
def add_maintenance(request):
    if request.method == "POST":
        form = MaintenanceForm(request.POST)
        if form.is_valid():
            log = form.save(commit=False)
            log.technician = request.user
            log.save()

            # AUTOMATION: Update the Asset status to 'Maintenance' immediately
            asset = log.asset
            asset.status = 'Maintenance' 
            asset.save()

            return redirect('maintenance_list')
    else:
        form = MaintenanceForm()
    return render(request, 'core/add_maintenance.html', {'form': form})

@login_required
def edit_maintenance(request, pk):
    # Fetch the specific maintenance record
    maintenance = get_object_or_404(Maintenance, pk=pk)
    
    if request.method == 'POST':
        # Pass the instance so we update the existing record instead of creating a new one
        form = MaintenanceForm(request.POST, instance=maintenance)
        
        if form.is_valid():
            # Save the maintenance log details (notes, type, status, etc.)
            updated_maintenance = form.save()
            
            # Logic: Sync the Asset's status with the Maintenance Log's status
            # If the log is marked 'Completed', set the Asset to 'Active'
            asset = updated_maintenance.asset
            log_status = updated_maintenance.status
            
            if log_status == 'Completed':
                asset.status = 'Active' 
            else:
                # If still 'In Progress' or 'Pending', keep asset in 'Maintenance'
                asset.status = 'Maintenance'
            
            asset.save()
            
            messages.success(request, f"Service log for {asset.assets_id} has been updated.")
            return redirect('maintenance_list')
    else:
        form = MaintenanceForm(instance=maintenance)

    return render(request, 'core/edit_maintenance.html', {
        'form': form,
        'maintenance': maintenance,
    })
    
@login_required
def delete_maintenance(request, pk):
    maintenance = get_object_or_404(Maintenance, pk=pk)
    if request.method == "POST":
        maintenance.delete()
        messages.success(request, "Service log removed.")
    return redirect('maintenance_list')

@login_required
def incident_list(request):
    return render(request, 'core/incident_list.html', {'incidents': Incident.objects.all()})

@login_required
def analytics(request):
    # Security check: Only Admin and Commander should see the full analytics suite
    if request.user.groups.filter(name='Personnel').exists():
        messages.warning(request, "Personnel do not have access to the Analytics module.")
        return redirect('dashboard')

    context = {
        'total_assets': Asset.objects.count(),
        'asset_counts': Asset.objects.values('asset_type').annotate(total=Count('id')),
        'severity_counts': Incident.objects.values('severity').annotate(total=Count('id')),
        'status_counts': Incident.objects.values('status').annotate(total=Count('id')),
    }
    return render(request, 'core/analytics.html', context)

@login_required
def reports(request):
    return render(request, 'core/reports.html')


##################################################################ASSETS COMMANDS##################################################################
@login_required
def add_asset(request):
    if request.method == 'POST':
        form = AssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            # This captures the person currently logged in
            asset.assigned_to = request.user 
            asset.save()
            return redirect('asset_list')
    else:
        form = AssetForm()
    return render(request, 'core/add_asset.html', {'form': form})

@login_required
def edit_asset(request, asset_id):
    # Use the database 'pk' (ID) to find the specific asset
    asset = get_object_or_404(Asset, pk=asset_id)
    
    if request.method == "POST":
        # Passing 'instance=asset' is the secret—it tells Django 
        # to update the existing record instead of creating a new one.
        form = AssetForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            messages.success(request, f"Asset {asset.assets_id} updated successfully!")
            return redirect('asset_list')
    else:
        form = AssetForm(instance=asset)
    
    return render(request, 'core/add_asset.html', {
        'form': form, 
        'title': f'Edit Asset: {asset.assets_id}'
    })

@login_required
def delete_asset(request, asset_id):
    asset = get_object_or_404(Asset, pk=asset_id)
    if request.method == "POST":
        asset_id_display = asset.assets_id
        asset.delete()
        messages.success(request, f"Asset {asset_id_display} has been removed.")
    return redirect('asset_list')

def asset_list(request):
    assets = Asset.objects.all()
    
    context = {
        'assets': assets,
        'active_assets_count': assets.filter(status='Active').count(),
        'inactive_assets_count': assets.filter(status='Inactive').count(),
        'maintenance_assets_count': assets.filter(status='Maintenance').count(),
    }
    return render(request, 'core/asset_list.html', context)