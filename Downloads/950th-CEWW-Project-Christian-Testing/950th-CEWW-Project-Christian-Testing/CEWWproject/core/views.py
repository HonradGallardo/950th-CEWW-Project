from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count
from django.contrib import messages
from .models import Asset, Maintenance, Incident
from .forms import UserForm

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
    # Summary Metrics for charts
    total_assets = Asset.objects.count()
    assigned_assets = Asset.objects.exclude(assigned_to=None).count()
    open_incidents = Incident.objects.filter(status='Open').count()
    critical_threats = Incident.objects.filter(severity='Critical', status='Open').count()

    context = {
        'total_assets': total_assets,
        'assigned_assets': assigned_assets,
        'open_incidents': open_incidents,
        'critical_threats': critical_threats,
        'asset_counts': Asset.objects.values('asset_type').annotate(total=Count('id')),
        'severity_counts': Incident.objects.values('severity').annotate(total=Count('id')),
    }

    # 1. COMMANDER ACCESS
    if request.user.groups.filter(name='Commander').exists():
        return render(request, 'core/commander_dashboard.html', context)
    
    # 2. PERSONNEL ACCESS (The Fix)
    elif request.user.groups.filter(name='Personnel').exists():
        # Personnel should only see assets assigned to THEM
        context['user_assets'] = Asset.objects.filter(assigned_to=request.user)
        return render(request, 'core/personnel_dashboard.html', context)
    
    # 3. ADMIN ACCESS
    elif request.user.groups.filter(name='Admin').exists():
        context['recent_maintenance'] = Maintenance.objects.all().order_by('-date')[:5]
        context['recent_incidents'] = Incident.objects.all().order_by('-date')[:5]
        return render(request, 'core/admin_dashboard.html', context)

    # 4. FALLBACK: If user has no group
    return render(request, 'core/landing.html', {'error': 'Unauthorized access.'})

# --- PERSONNEL CRUD (CLEANED) ---
@login_required
def user_list(request):
    if not request.user.groups.filter(name__in=['Admin', 'Commander']).exists():
        return redirect('dashboard')
    
    # We use 'users' as the key to match your HTML {% for person in users %}
    all_users = User.objects.all().prefetch_related('asset_set')
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

@login_required
def maintenance_list(request):
    return render(request, 'core/maintenance_list.html', {'maintenances': Maintenance.objects.all()})

@login_required
def incident_list(request):
    return render(request, 'core/incident_list.html', {'incidents': Incident.objects.all()})

@login_required
def reports(request):
    return render(request, 'core/reports.html')