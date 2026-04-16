from django.conf import settings
import openpyxl
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Count, Q
from .models import Asset, Maintenance, Incident, Notification, Profile
from .forms import AssetForm, MaintenanceForm, UserForm
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator

# --- NAVIGATION & DASHBOARD ---
def landing(request):
    return render(request, 'core/landing.html')

@login_required
def role_redirect(request):
    if request.user.is_superuser:
        return redirect('dashboard')
    user_groups = request.user.groups.values_list('name', flat=True)
    if any(role in user_groups for role in ['Admin', 'Commander', 'Personnel']):
        return redirect('dashboard')
    messages.warning(request, "Account active. Awaiting Wing role assignment.")
    return redirect('landing')

@login_required
def dashboard(request):
    # 1. Base Summary Metrics
    total_assets = Asset.objects.count()
    assigned_assets = Asset.objects.exclude(status='Inactive').count()
    open_incidents_qs = Incident.objects.filter(status='Open').order_by('-date')

    # 2. Chart Data: Asset Distribution (Bar Chart)
    asset_qs = Asset.objects.values('assets_type').annotate(total=Count('id'))
    asset_labels = [item['assets_type'] for item in asset_qs]
    asset_totals = [item['total'] for item in asset_qs]

    # 3. Chart Data: Incident Severity (Doughnut Chart)
    severity_qs = Incident.objects.values('severity').annotate(total=Count('id'))
    severity_labels = [item['severity'] for item in severity_qs]
    severity_totals = [item['total'] for item in severity_qs]

    # 4. Table Data: Recent Activity
    recent_maintenance = Maintenance.objects.all().select_related('asset', 'technician').order_by('-date')[:5]

    context = {
        'total_assets': total_assets,
        'assigned_assets': assigned_assets,
        'maintenance_assets_count': Maintenance.objects.filter(status='In Progress').count(),
        'open_incidents_count': open_incidents_qs.count(),
        
        # Lists for Chart.js
        'asset_labels': asset_labels,
        'asset_totals': asset_totals,
        'severity_labels': severity_labels,
        'severity_totals': severity_totals,

        # Recent Activity for Tables
        'recent_maintenance': recent_maintenance,
        'open_incidents': open_incidents_qs[:5],

        # Add these so the Commander charts don't render empty on first load!
        'chart_labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
        'chart_values': [0, 0, 0, 0, 0],
        'm_labels': ['Routine', 'Emergency'],
        'm_completed': [0, 0],
        'm_pending': [0, 0],
        
    }

    user_groups = request.user.groups.values_list('name', flat=True)

    # 5. Role-Based Routing with Fallback
    if 'Commander' in user_groups:
        return render(request, 'core/Commander/commander_dashboard.html', context)
    elif 'Personnel' in user_groups:
        return render(request, 'core/Personnel/personnel_dashboard.html', context)
    elif 'Admin' in user_groups or request.user.is_superuser:
        return render(request, 'core/Admin/admin_dashboard.html', context)

    # Final Fallback to prevent ValueError
    return render(request, 'core/Admin/admin_dashboard.html', context)

# --- ASSET MODULE ---
@login_required
def add_asset(request):
    # Only responsible for providing the form structure to the template
    form = AssetForm() 
    return render(request, 'core/Admin/add_asset.html', {'form': form})

@login_required
def asset_list(request):
    # Standard list rendering
    return render(request, 'core/Admin/asset_list.html', {'assets': Asset.objects.all()})

@login_required
def edit_asset(request, asset_id):
    asset = get_object_or_404(Asset, pk=asset_id)
    # Important: We keep the form and asset in context
    form = AssetForm(instance=asset) 
    return render(request, 'core/Admin/add_asset.html', {
        'form': form, 
        'asset': asset  # This allows us to check if asset exists in JS
    })
@login_required
def delete_asset(request, asset_id):
    asset = get_object_or_404(Asset, pk=asset_id)
    if request.method == 'POST':
        asset.delete()
    return redirect('asset_list')

# --- MAINTENANCE MODULE ---

@login_required
def maintenance_list(request):
    """
    Renders the shell for the service history. 
    API handles the data loading via /api/maintenance/
    """
    # Fetch asset types for the filter dropdown
    asset_types = Asset.objects.values_list('assets_type', flat=True).distinct()
    return render(request, 'core/Admin/maintenance_list.html', {
        'asset_types': asset_types
    })

@login_required
def add_maintenance(request):
    form = MaintenanceForm(request.POST or None)
    if form.is_valid():
        m = form.save(commit=False)
        m.technician = request.user
        m.save()
        return redirect('maintenance_list')
    return render(request, 'core/Admin/add_maintenance.html', {'form': form})

@login_required
def edit_maintenance(request, pk):
    log = get_object_or_404(Maintenance, pk=pk)
    
    # 1. Check if the user is submitting the form (POST request)
    if request.method == 'POST':
        # Bind the incoming POST data to the existing log instance
        form = MaintenanceForm(request.POST, instance=log)
        
        if form.is_valid():
            # 2. Save the updated progress/status and date
            updated_log = form.save()
            
            # 3. SMART LOGIC: If maintenance is completed, automatically activate the asset
            if updated_log.status == 'Completed':
                asset = updated_log.asset
                if asset.status != 'Active':
                    asset.status = 'Active'
                    asset.save()
                    
            # Redirect back to the service history page
            return redirect('maintenance_list')
    else:
        # If the user is just loading the page, populate the form with existing data
        form = MaintenanceForm(instance=log)

    return render(request, 'core/Admin/edit_maintenance.html', {
        'form': form,
        'log_id': pk  # Pass ID for API URL construction
    })

@login_required
def delete_maintenance(request, pk):
    get_object_or_404(Maintenance, pk=pk).delete()
    return redirect('maintenance_list')

# --- INCIDENT MODULE ---
@login_required
def incident_list(request):
    return render(request, 'core/Admin/incident_list.html', {'incidents': Incident.objects.all()})

@login_required
def add_incident(request):
    if request.method == 'POST':
        Incident.objects.create(title=request.POST.get('title'), severity=request.POST.get('severity'), affected_area=request.POST.get('affected_area'), reported_by=request.user)
        return redirect('incident_list')
    return render(request, 'core/Admin/add_incident.html')

@login_required
def edit_incident(request, incident_id):
    incident = get_object_or_404(Incident, id=incident_id)
    return render(request, 'core/Admin/edit_incident.html', {'incident': incident})

@login_required
def delete_incident(request, incident_id):
    get_object_or_404(Incident, id=incident_id).delete()
    return redirect('incident_list')

# --- USERS & PERSONNEL ---
@login_required
def user_list(request):
    """
    Serves the HTML shell with initial paginated data.
    JavaScript AJAX handles live search filtering.
    """
    # Fetch all users, order them (required for consistent pagination), and prefetch related data
    user_list_qs = User.objects.all().prefetch_related('groups', 'profile').order_by('-id')
    
    # Set up pagination: 10 users per page
    paginator = Paginator(user_list_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Pass 'page_obj' as 'users' to match the template variable
    return render(request, 'core/Admin/user_list.html', {'users': page_obj})

@login_required
def add_user(request):
    form = UserForm(request.POST or None, request.FILES or None)
    
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False) 
        
        raw_password = form.cleaned_data.get('password')
        if raw_password:
            user.set_password(raw_password)
        
        user.save() 
        form.save_m2m() 

        # 🚨 ROLE (GROUP) SAVING LOGIC 🚨
        # Check for either the Django 'role' or the custom 'role_name'
        submitted_role = request.POST.get('role') or request.POST.get('role_name') 
        if submitted_role:
            user.groups.clear() # Clear existing to avoid duplicates
            group = Group.objects.filter(name=submitted_role).first()
            if group:
                user.groups.add(group)

        # Handle Profile and extra fields
        profile, created = Profile.objects.get_or_create(user=user)
        profile.rank = request.POST.get('rank', profile.rank)
        profile.phone = request.POST.get('phone', profile.phone)
        
        if 'profile_picture' in request.FILES:
            profile.image = request.FILES['profile_picture']
        
        profile.save()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        return redirect('user_list')
    
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'errors': form.errors}, status=400)
        
    return render(request, 'core/Admin/user_form.html', {'form': form, 'title': 'Add Personnel'})

@login_required
def edit_user(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    
    if request.method in ['POST', 'PATCH']:
        data = request.POST if request.method == 'POST' else QueryDict(request.body)
        form = UserForm(data, request.FILES, instance=target_user)
        
        if form.is_valid():
            user = form.save(commit=False)
            
            raw_password = form.cleaned_data.get('password')
            if raw_password:
                user.set_password(raw_password)
                
            user.save()
            form.save_m2m()

            # 🚨 FIX: ROLE (GROUP) SAVING LOGIC 🚨
            # Check for either the Django 'role' or the custom 'role_name'
            submitted_role = request.POST.get('role') or request.POST.get('role_name') 
            if submitted_role:
                user.groups.clear() # Clear existing roles to prevent multiple assignments
                group = Group.objects.filter(name=submitted_role).first()
                if group:
                    user.groups.add(group)

            # Update Profile with the extra fields
            profile, created = Profile.objects.get_or_create(user=user)
            profile.rank = request.POST.get('rank', profile.rank)
            profile.phone = request.POST.get('phone', profile.phone)
            
            if 'profile_picture' in request.FILES:
                profile.image = request.FILES['profile_picture']
                
            profile.save()

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success'})
            return redirect('user_list')
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'errors': form.errors}, status=400)
    else:
        form = UserForm(instance=target_user)
                
    return render(request, 'core/Admin/user_form.html', {'form': form, 'title': 'Edit Personnel'})

@login_required
def delete_user(request, user_id):
    get_object_or_404(User, id=user_id).delete()
    return redirect('user_list')

# --- SYSTEM UTILITIES ---
@login_required
def analytics_list(request):
    today = timezone.now().date()
    # Create the date list as before
    date_list = [today - timedelta(days=i) for i in range(6, -1, -1)]
    
    # FIX 1: Convert date objects to strings for 100% matching reliability
    labels = [d.strftime('%a') for d in date_list]
    date_to_idx = {d.strftime('%Y-%m-%d'): i for i, d in enumerate(date_list)}

    fixed_assets, pending_assets = [0]*7, [0]*7
    new_incidents, resolved_incidents = [0]*7, [0]*7

    # Fetch Incidents
    inc_qs = Incident.objects.filter(date__date__gte=date_list[0]) \
        .values('date__date', 'status') \
        .annotate(count=Count('id'))

    for item in inc_qs:
        # FIX 2: Convert DB date to string and slice to ensure YYYY-MM-DD format
        db_date_str = str(item['date__date'])[:10]
        idx = date_to_idx.get(db_date_str)
        
        if idx is not None:
            # FIX 3: Use += so we don't overwrite multiple statuses on the same day
            if item['status'] == 'Resolved': 
                resolved_incidents[idx] += item['count']
            else: 
                # This catches 'Open', 'Investigating', etc.
                new_incidents[idx] += item['count']
    incident_data_qs = Incident.objects.values('severity').annotate(count=Count('id'))
    # 4. Final Context for Template
    context = {
        'labels': labels,
        'fixed_assets': fixed_assets,
        'pending_assets': pending_assets,
        'new_incidents': new_incidents,
        'resolved_incidents': resolved_incidents,
        'asset_types': Asset.objects.values('assets_type').annotate(total=Count('id')),
        'predicted_incidents': 5, # Placeholder for AI logic
        'current_month_total': 3,
        'confidence_level': 'High',
        'incident_summary': list(incident_data_qs), # Ready for Chart.js
    }
    return render(request, 'core/Admin/analytics_list.html', context)

@login_required
def monitoring_data_api(request):
    # (Insert the same calculation logic from Step 1 here)
    return JsonResponse(data)

@login_required
def reports(request):
    report_type = request.GET.get('report_type', 'it_asset')
    category = request.GET.get('category', 'All')
    export_format = request.GET.get('export')

    # 1. Filter Data based on selection
    if report_type == 'maintenance':
        data_qs = Maintenance.objects.all().select_related('asset', 'technician')
        status_field = 'status'
    elif report_type == 'incident':
        data_qs = Incident.objects.all().select_related('asset')
        status_field = 'status'
    else:  # it_asset
        data_qs = Asset.objects.all()
        status_field = 'status'

    if category != 'All' and category:
        if report_type == 'it_asset':
            data_qs = data_qs.filter(assets_type=category)
        else:
            data_qs = data_qs.filter(asset__assets_type=category)

    # 2. Handle Excel Export
    if export_format == 'excel':
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename={report_type}_report.xlsx'
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Report Data"

        # Define Headers based on Report Type
        if report_type == 'maintenance':
            headers = ['Asset Name', 'Technician', 'Status', 'Date']
            ws.append(headers)
            for item in data_qs:
                ws.append([item.asset.assets_name, item.technician.username, item.status, item.date.strftime('%Y-%m-%d')])
        elif report_type == 'incident':
            headers = ['Severity', 'Title', 'Asset', 'Status']
            ws.append(headers)
            for item in data_qs:
                ws.append([item.severity, item.title, str(item.asset), item.status])
        else: # it_asset
            headers = ['Asset ID', 'Asset Name', 'Type', 'Location', 'Status']
            ws.append(headers)
            for item in data_qs:
                ws.append([item.assets_id, item.assets_name, item.assets_type, item.location, item.status])

        wb.save(response)
        return response

    # 3. Chart Data: Status Distribution
    status_data = data_qs.values(status_field).annotate(total=Count('id'))
    status_labels = [item[status_field] for item in status_data]
    status_counts = [item['total'] for item in status_data]

    # 4. Pagination
    paginator = Paginator(data_qs.order_by('-id'), 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'report_type': report_type,
        'category': category,
        'data_list': page_obj,  # This replaces the empty table
        'page_obj': page_obj,
        'total_count': data_qs.count(),
        'status_labels': status_labels,
        'status_counts': status_counts,
        'asset_types': Asset.ASSET_TYPES, # Ensure your Model has this choices list
    }
    return render(request, 'core/Admin/reports.html', context)

@login_required
def profile_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # 1. Handle the Profile Image (FILES)
        # Match the 'name' attribute from your HTML input
        if 'image' in request.FILES:
            profile.image = request.FILES['image']
        
        # 2. Handle Profile Fields
        profile.rank = request.POST.get('rank', profile.rank)
        profile.phone = request.POST.get('phone', profile.phone)
        profile.save()

        # 3. Handle User Model Fields (Email, First Name, Last Name)
        user = request.user
        user.email = request.POST.get('email', user.email)
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.save()

        # If AJAX, return success response
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'image_url': profile.image.url if profile.image else None
            })

    return render(request, 'core/Admin/profile.html', {'profile': profile})

@login_required
def mark_all_as_read(request):
    """Restores the link for the notification bell"""
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

def forgot_password_view(request):
    return render(request, 'registration/forgot_password.html', {
        'recaptcha_site_key': getattr(settings, 'RECAPTCHA_SITE_KEY', '')
    })