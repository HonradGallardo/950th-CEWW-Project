from multiprocessing import context
from urllib import request
import calendar
from django.db.models.functions import ExtractMonth, ExtractWeekDay
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count
from django.contrib import messages
from .models import Asset, IncidentComment, Maintenance, Incident
from .forms import AssetForm, MaintenanceForm, UserForm
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.functions import TruncDay
from django.db.models.functions import TruncMonth
from django.utils.timezone import localtime


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

    # Calculate Readiness Rate for Commander
    readiness_rate = (assigned_assets / total_assets * 100) if total_assets > 0 else 0

    # Base Context
    context = {
        'total_assets': total_assets,
        'assigned_assets': assigned_assets,
        'readiness_rate': readiness_rate,
        'open_incidents_count': open_incidents_count,
        'critical_threats': critical_threats,
        'asset_counts': Asset.objects.values('assets_type').annotate(total=Count('id')),
    }

    user_groups = request.user.groups.values_list('name', flat=True)

    if 'Commander' in user_groups:
        # 1. Severity Mapping
        severity_qs = Incident.objects.values('severity').annotate(total=Count('id'))
        context['severity_counts'] = {item['severity']: item['total'] for item in severity_qs}
        
        # 2. Maintenance Metrics (Fixing the March/April issue)
        maint_qs = Maintenance.objects.annotate(month_num=ExtractMonth('date')) \
            .values('month_num', 'status') \
            .annotate(total=Count('id')) \
            .order_by('month_num')

        m_labels, m_completed, m_pending = [], [], []
        unique_months = sorted(list(set(item['month_num'] for item in maint_qs)))
        
        for m in unique_months:
            m_labels.append(calendar.month_name[m][:3])
            m_completed.append(next((i['total'] for i in maint_qs if i['month_num'] == m and i['status'] == 'Completed'), 0))
            m_pending.append(next((i['total'] for i in maint_qs if i['month_num'] == m and i['status'] == 'In Progress'), 0))

        context.update({'m_labels': m_labels, 'm_completed': m_completed, 'm_pending': m_pending})

        # 3. Incident Trend (Last 7 Days)
        last_7_days = timezone.now() - timedelta(days=6)
        trend_qs = Incident.objects.filter(date__gte=last_7_days) \
            .annotate(day=ExtractWeekDay('date')) \
            .values('day') \
            .annotate(total=Count('id')) \
            .order_by('day')
        
        days_map = {1:'Sun', 2:'Mon', 3:'Tue', 4:'Wed', 5:'Thu', 6:'Fri', 7:'Sat'}
        context['trend_labels'] = [days_map[item['day']] for item in trend_qs]
        context['trend_data'] = [item['total'] for item in trend_qs]

        return render(request, 'core/Commander/commander_dashboard.html', context)
    
    
    elif 'Personnel' in user_groups:
        # --- GET SEARCH QUERIES ---
        q_incident = request.GET.get('q_incident', '').strip()
        q_asset = request.GET.get('q_asset', '').strip()
        q_task = request.GET.get('q_task', '').strip()

        # --- 1. INCIDENTS SEARCH ---
        incident_list = Incident.objects.all().order_by('-date')
        if q_incident:
            # If searching for status specifically, use exact match to avoid "Active" matching "Inactive"
            if q_incident.lower() in ['active', 'inactive', 'resolved', 'pending']:
                incident_list = incident_list.filter(
                    Q(status__iexact=q_incident) | Q(title__icontains=q_incident)
                )
            else:
                incident_list = incident_list.filter(
                    Q(title__icontains=q_incident) | Q(id__icontains=q_incident)
                )
        
        incident_paginator = Paginator(incident_list, 10)
        page_obj = incident_paginator.get_page(request.GET.get('page'))

        # --- 2. ASSETS SEARCH ---
        asset_list = Asset.objects.filter(assigned_to=request.user).order_by('-date_added')
        if q_asset:
            if q_asset.lower() in ['active', 'inactive', 'maintenance', 'retired']:
                asset_list = asset_list.filter(
                    Q(status__iexact=q_asset) | Q(assets_name__icontains=q_asset)
                )
            else:
                asset_list = asset_list.filter(assets_name__icontains=q_asset)

        asset_paginator = Paginator(asset_list, 10)
        asset_page_obj = asset_paginator.get_page(request.GET.get('asset_page'))

        # --- 3. MAINTENANCE SEARCH ---
        task_list = Maintenance.objects.filter(technician=request.user, status='In Progress').order_by('id')
        if q_task:
            # Maintenance tasks usually have statuses like "In Progress" or "Completed"
            if q_task.lower() in ['in progress', 'completed', 'pending']:
                task_list = task_list.filter(
                    Q(status__iexact=q_task) | Q(asset__assets_name__icontains=q_task)
                )
            else:
                task_list = task_list.filter(
                    Q(asset__assets_name__icontains=q_task) | Q(maintenance_type__icontains=q_task)
                )

        task_paginator = Paginator(task_list, 10)
        task_page_obj = task_paginator.get_page(request.GET.get('task_page'))

        personnel_context = {
            'total_assets': Asset.objects.filter(assigned_to=request.user).count(),
            'my_maintenance_count': Maintenance.objects.filter(technician=request.user, status='In Progress').count(),
            'reported_incidents_count': Incident.objects.count(), 
            
            'page_obj': page_obj,
            'asset_page_obj': asset_page_obj,
            'task_page_obj': task_page_obj,
            
            'q_incident': q_incident,
            'q_asset': q_asset,
            'q_task': q_task,
        }
        return render(request, 'core/Personnel/personnel_dashboard.html', personnel_context)
    
    elif 'Admin' in user_groups:
        asset_qs = Asset.objects.values('assets_type').annotate(total=Count('id'))
        context['asset_labels'] = [item['assets_type'] for item in asset_qs]
        context['asset_totals'] = [item['total'] for item in asset_qs]

        severity_qs = Incident.objects.values('severity').annotate(total=Count('id'))
        context['severity_labels'] = [item['severity'] for item in severity_qs]
        context['severity_totals'] = [item['total'] for item in severity_qs]

        context['recent_maintenance'] = Maintenance.objects.all().select_related('asset', 'technician').order_by('-date')[:5]
        context['open_incidents'] = Incident.objects.filter(status='Open').order_by('-date')[:5]
        
        return render(request, 'core/Admin/admin_dashboard.html', context)

    return render(request, 'core/landing.html', {'error': 'Unauthorized access.'})

# --- PERSONNEL CRUD ---
@login_required
def user_list(request):
    if not request.user.groups.filter(name__in=['Admin', 'Commander']).exists():
        return redirect('dashboard')
    all_users = User.objects.all().prefetch_related('groups')
    return render(request, 'core/Admin/user_list.html', {'users': all_users})

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
    return render(request, 'core/Admin/user_form.html', {'form': form, 'title': 'Add Personnel'})

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
    return render(request, 'core/Admin/user_form.html', {'form': form, 'title': 'Edit Personnel'})

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

    return render(request, 'core/Admin/maintenance_list.html', {
        'active_maintenance': active_maintenance,
        'maintenances': maintenances,
        'asset_types': asset_types,
    })

@login_required
def command_maintenance(request):
    maintenances = Maintenance.objects.all().order_by('-date')
    
    # Logic for active/queued stays the same as your snippet
    assets_under_active_repair = Maintenance.objects.filter(status='In Progress').values_list('asset_id', flat=True)
    active_maintenance = Asset.objects.filter(status='Maintenance').exclude(id__in=assets_under_active_repair)
    asset_types = Asset.objects.values_list('assets_type', flat=True).distinct()

    # CRUCIAL: Point to a specific 'command_maintenance.html' 
    # to avoid mixing it up with the admin 'maintenance_list.html'
    return render(request, 'core/Commander/command_maintenance.html', {
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

    return render(request, 'core/Admin/add_maintenance.html', {'form': form})

@login_required
def edit_maintenance(request, pk):
    log = get_object_or_404(Maintenance, pk=pk)
    
    if request.method == 'POST':
        form = MaintenanceForm(request.POST, instance=log)
        # We re-disable it here because POST data doesn't include disabled fields
        form.fields['asset'].disabled = True 
        
        if form.is_valid():
            updated_log = form.save()
            # Sync the Asset status with the Maintenance status
            asset = updated_log.asset
            asset.status = 'Active' if updated_log.status == 'Completed' else 'Maintenance'
            asset.save()
            
            messages.success(request, "Service log updated.")
            return redirect('maintenance_list')
    else:
        form = MaintenanceForm(instance=log)
        # Disable the field so it renders as read-only in the template
        form.fields['asset'].disabled = True

    return render(request, 'core/Admin/add_maintenance.html', {
        'form': form, 
        'maintenance': log, # Passing the object for the sidebar info
        'edit_mode': True
    })

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
    return render(request, 'core/Admin/asset_list.html', context)

@login_required
def command_asset(request):
    assets = Asset.objects.all() 
    
    # Add these lines to calculate the counts for the Pie Chart
    context = {
        'assets': assets,
        'active_assets_count': assets.filter(status='Active').count(),
        'inactive_assets_count': assets.filter(status='Inactive').count(),
        'maintenance_assets_count': assets.filter(status='Maintenance').count(),
    }
    
    return render(request, 'core/Commander/command_asset.html', context)


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
    return render(request, 'core/Admin/add_asset.html', {'form': form})

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
    return render(request, 'core/Admin/add_asset.html', {'form': form, 'title': f'Edit Asset: {asset.assets_id}'})

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
    # --- HANDLE COMMENT POST ---
    if request.method == 'POST' and 'message' in request.POST:
        incident_id = request.POST.get('incident_id')

        if not incident_id:
            messages.error(request, "Please select an incident first.")
            return redirect('incident_list')

        request.session['active_incident_id'] = incident_id

        incident = get_object_or_404(Incident, id=incident_id)
        message_text = request.POST.get('message', '').strip()

        if message_text:
            IncidentComment.objects.create(
                incident=incident,
                author=request.user,
                message=message_text
            )

        return redirect('incident_list')

    # --- HANDLE DELETE ---
    if request.method == 'POST' and request.POST.get('action') == 'delete':
        incident_id = request.POST.get('incident_id')
        incident = get_object_or_404(Incident, id=incident_id)
        incident.delete()
        messages.success(request, "Incident record removed.")
        return redirect('incident_list')

    # --- LOAD ACTIVE INCIDENT ---
    active_incident = None
    comments = []

    active_id = request.session.get('active_incident_id')
    if active_id:
        active_incident = get_object_or_404(Incident, id=active_id)
        comments = active_incident.comments.all().order_by('created_at')

    # --- FINAL CONTEXT ---
    context = {
        'incidents': Incident.objects.all().order_by('-date'),
        'incident': active_incident,
        'comments': comments,
    }

    return render(request, 'core/Admin/incident_list.html', context)


@login_required
def command_incident(request):
    # Purely retrieval for the Commander
    incidents = Incident.objects.all().order_by('-date')
    return render(request, 'core/Commander/command_incident.html', {
        'incidents': incidents
    })

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
    return render(request, 'core/Admin/add_incident.html')

@login_required
def edit_incident(request, incident_id):  # Make sure this matches the URL keyword
    incident = get_object_or_404(Incident, id=incident_id)
    
    if request.method == 'POST':
        incident.status = request.POST.get('status')
        incident.save()
        return redirect('incident_list')
        
    return render(request, 'core/Admin/edit_incident.html', {'incident': incident})

@login_required
def delete_incident(request, incident_id):
    incident = get_object_or_404(Incident, id=incident_id)
    incident.delete()
    return redirect('incident_list')

# views.py
@login_required
def incident_detail(request, incident_id):
    incident = get_object_or_404(Incident, id=incident_id)
    comments = incident.comments.all()

    if request.method == 'POST' and 'message' in request.POST:
        message_text = request.POST.get('message').strip()
        if message_text:
            IncidentComment.objects.create(
                incident=incident,
                author=request.user,
                message=message_text
            )
            messages.success(request, "Note added to log.")
            return redirect('incident_detail', incident_id=incident.id)

    return render(request, 'core/Admin/incident_detail.html', {
        'incident': incident,
        'comments': comments
    })

def get_incident_comments(request, incident_id):
    comments = IncidentComment.objects.filter(incident_id=incident_id).order_by('created_at')
    data = []
    for c in comments:
        data.append({
            'author': c.author.username,
            'message': c.message,
            'created_at': c.created_at.strftime("%b %d, %H:%M"),
            'is_current_user': c.author == request.user
        })
    return JsonResponse({'comments': data})


@login_required
def analytics_list(request):
    # 1. Setup Time Window using Local Time
    today = localtime(timezone.now()).date()
    date_list = [today - timedelta(days=i) for i in range(6, -1, -1)]
    labels = [d.strftime('%a') for d in date_list]
    date_to_idx = {d: i for i, d in enumerate(date_list)}

    # Initialize data arrays
    fixed_counts, pending_counts = [0]*7, [0]*7
    new_incidents, resolved_incidents = [0]*7, [0]*7

    # 2. Query Maintenance
    # We use date__date to capture the database's date part
    maint_qs = Maintenance.objects.filter(date__date__gte=date_list[0]) \
        .values('date__date', 'status') \
        .annotate(count=Count('id'))

    for item in maint_qs:
        d = item['date__date']
        if d in date_to_idx:
            idx = date_to_idx[d]
            if item['status'] == 'Completed': fixed_counts[idx] += item['count']
            else: pending_counts[idx] += item['count']

    # 3. Query Incidents
    inc_qs = Incident.objects.filter(date__date__gte=date_list[0]) \
        .values('date__date', 'status') \
        .annotate(count=Count('id'))

    for item in inc_qs:
        d = item['date__date']
        if d in date_to_idx:
            idx = date_to_idx[d]
            if item['status'] == 'Resolved':
                resolved_incidents[idx] += item['count']
            else:
                # This catches 'Open' and 'Investigating'
                new_incidents[idx] += item['count']

    context = {
        'labels': labels,
        'fixed_assets': fixed_counts,
        'pending_assets': pending_counts,
        'new_incidents': new_incidents,
        'resolved_incidents': resolved_incidents,
        'asset_types': Asset.objects.values('assets_type').annotate(total=Count('id')),
    }
    
    three_months_ago = timezone.now() - timedelta(days=90)
    monthly_trends = Incident.objects.filter(date__gte=three_months_ago) \
        .annotate(month=TruncMonth('date')) \
        .values('month') \
        .annotate(total=Count('id')) \
        .order_by('month')

    counts = [item['total'] for item in monthly_trends]
    
    # Default values
    predicted_incidents = 0
    confidence_level = "Low (Insufficient Data)"
    current_month_total = 0

    if len(counts) >= 2:
        # Calculate growth: (Latest - Oldest) / Number of gaps
        growth = (counts[-1] - counts[0]) / (len(counts) - 1)
        predicted_incidents = max(0, round(counts[-1] + growth))
        current_month_total = counts[-1]
        confidence_level = "High" if len(counts) >= 3 else "Medium"
    elif len(counts) == 1:
        predicted_incidents = counts[0]
        current_month_total = counts[0]
        confidence_level = "Low (Baseline Only)"

    context.update({
        'predicted_incidents': predicted_incidents,
        'confidence_level': confidence_level,
        'current_month_total': current_month_total,
    })
    
    return render(request, 'core/Admin/analytics_list.html', context)


@login_required
def commander_analytics(request):
    # 1. Setup Time Window using Local Time
    today = localtime(timezone.now()).date()
    date_list = [today - timedelta(days=i) for i in range(6, -1, -1)]
    labels = [d.strftime('%a') for d in date_list]
    date_to_idx = {d: i for i, d in enumerate(date_list)}

    # Initialize data arrays
    fixed_counts, pending_counts = [0]*7, [0]*7
    new_incidents, resolved_incidents = [0]*7, [0]*7

    # 2. Query Maintenance
    # We use date__date to capture the database's date part
    maint_qs = Maintenance.objects.filter(date__date__gte=date_list[0]) \
        .values('date__date', 'status') \
        .annotate(count=Count('id'))

    for item in maint_qs:
        d = item['date__date']
        if d in date_to_idx:
            idx = date_to_idx[d]
            if item['status'] == 'Completed': fixed_counts[idx] += item['count']
            else: pending_counts[idx] += item['count']

    # 3. Query Incidents
    inc_qs = Incident.objects.filter(date__date__gte=date_list[0]) \
        .values('date__date', 'status') \
        .annotate(count=Count('id'))

    for item in inc_qs:
        d = item['date__date']
        if d in date_to_idx:
            idx = date_to_idx[d]
            if item['status'] == 'Resolved':
                resolved_incidents[idx] += item['count']
            else:
                # This catches 'Open' and 'Investigating'
                new_incidents[idx] += item['count']

    context = {
        'labels': labels,
        'fixed_assets': fixed_counts,
        'pending_assets': pending_counts,
        'new_incidents': new_incidents,
        'resolved_incidents': resolved_incidents,
        'asset_types': Asset.objects.values('assets_type').annotate(total=Count('id')),
    }
    return render(request, 'core/Commander/command_analytics.html', context)

@login_required
def reports(request):
    return render(request, 'core/Admin/reports.html')

@login_required
def command_reports(request):
    return render(request, 'core/Commander/command_reports.html')