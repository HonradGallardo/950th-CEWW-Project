from multiprocessing import context
from urllib import request
import openpyxl
import json
import calendar
from django.http import HttpResponse
from django.db.models.functions import ExtractMonth, ExtractWeekDay
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required,user_passes_test
from django.contrib.auth.models import User
from django.db.models import Count
from django.contrib import messages
from .models import Asset, IncidentComment, Maintenance, Incident, Notification
from .forms import AssetForm, MaintenanceForm, UserForm
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.db.models.functions import TruncDay
from django.db.models.functions import TruncMonth
from django.utils.timezone import localtime
from .models import Ticket, TicketMessage
from django.db import models
from rest_framework import viewsets
from .serializers import AssetSerializer, MaintenanceSerializer, IncidentSerializer

# Add these classes at the bottom of your existing views.py
class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer

class MaintenanceViewSet(viewsets.ModelViewSet):
    queryset = Maintenance.objects.all()
    serializer_class = MaintenanceSerializer

class IncidentViewSet(viewsets.ModelViewSet):
    queryset = Incident.objects.all()
    serializer_class = IncidentSerializer

#################################################################### NOTIFICATION ####################################################################
def get_latest_notifications(request):
    notifications = request.user.notifications.all().order_by('-created_at')[:5]
    data = [{
        'message': n.message,
        'created_at': n.created_at.strftime('%b %d, %H:%M'),
        'is_read': n.is_read
    } for n in notifications]
    
    return JsonResponse({'notifications': data})

def mark_all_as_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))



####################################################################TICKETING MODULE####################################################################
@login_required
# In your personnel views.py
@login_required
def submit_ticket(request):
    """View for Personnel/Users to submit and see their own tickets"""
    if request.method == 'POST':
        subject = request.POST.get('subject')
        category = request.POST.get('category')
        priority = request.POST.get('priority', 'Low') # Default to Low if missing
        description = request.POST.get('description')
        
        # Create the ticket
        Ticket.objects.create(
            subject=subject,
            category=category,
            priority=priority,
            description=description,
            user=request.user
        )
        
        # For AJAX requests (from the chatbot), return JSON
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('ajax') == 'true':
            return JsonResponse({'status': 'success'})
            
        return redirect('submit_ticket')

    # Get tickets for the logged-in user
    user_tickets = Ticket.objects.filter(user=request.user).order_by('-created_at')
    
    return render(request, 'core/Personnel/submit_ticket.html', {
        'user_tickets': user_tickets
    })

@login_required
def command_submit_ticket(request):
    """View for Personnel/Users to submit and see their own tickets"""
    if request.method == 'POST':
        subject = request.POST.get('subject')
        category = request.POST.get('category')
        priority = request.POST.get('priority', 'Low') # Default to Low if missing
        description = request.POST.get('description')
        
        # Create the ticket
        Ticket.objects.create(
            subject=subject,
            category=category,
            priority=priority,
            description=description,
            user=request.user
        )
        
        # Check for AJAX (ensure lowercase 'x-requested-with' for compatibility)
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('ajax') == 'true'
        
        if is_ajax:
            return JsonResponse({'status': 'success', 'message': 'Ticket created successfully'})
            
        return redirect('command_submit_ticket') # Use the actual name of this view in urls.py

    # Get tickets for the logged-in user
    user_tickets = Ticket.objects.filter(user=request.user).order_by('-created_at')
    
    # Ensure this template path exists
    return render(request, 'core/Commander/command_tickets.html', {
        'user_tickets': user_tickets
    })

@login_required
def handle_ticket_submission(request, template_path):
    """
    A single view that handles ticket creation and display.
    The template_path is passed in from the URL configuration.
    """
    if request.method == 'POST':
        subject = request.POST.get('subject')
        category = request.POST.get('category')
        priority = request.POST.get('priority', 'Low')
        description = request.POST.get('description')
        
        Ticket.objects.create(
            subject=subject,
            category=category,
            priority=priority,
            description=description,
            user=request.user
        )
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('ajax') == 'true':
            return JsonResponse({'status': 'success', 'message': 'Ticket created successfully'})
            
        # Redirect back to whatever URL the user is currently on
        return redirect(request.path)

    user_tickets = Ticket.objects.filter(user=request.user).order_by('-created_at')
    
    return render(request, template_path, {
        'user_tickets': user_tickets
    })

def get_messages(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    messages = ticket.messages.all().order_by('created_at')
    
    data = []
    for msg in messages:
        data.append({
            "sender": msg.sender.username,
            "message": msg.message,  # This matches the model field 'message'
            "time": msg.created_at.strftime("%b %d, %H:%M")
        })
    return JsonResponse({"messages": data})

def send_message(request, ticket_id):
    if request.method == "POST":
        text = request.POST.get('text')
        if not text:
            return JsonResponse({"status": "error", "message": "Empty message"}, status=400)
            
        ticket = get_object_or_404(Ticket, id=ticket_id)
        
        # Use TicketMessage and set 'message=text' to match your model field
        msg = TicketMessage.objects.create(
            ticket=ticket, 
            sender=request.user, 
            message=text 
        )
        
        return JsonResponse({
            "status": "sent", 
            "text": msg.message,
            "sender": msg.sender.username,
            "created_at": msg.created_at.strftime("%b %d, %H:%M")
        })
    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)

@login_required
def get_ticket_chat(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    
    # IMPROVED CHECK: Use your existing is_admin logic
    user_is_admin = request.user.is_staff or request.user.groups.filter(name='Admin').exists()
    
    if not user_is_admin and ticket.user != request.user:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    messages = ticket.messages.all().select_related('sender').order_by('created_at')
    
    message_data = [{
        'sender': msg.sender.username,
        'message': msg.message,
        'is_me': msg.sender == request.user,
        'created_at': msg.created_at.strftime("%b %d, %H:%M"),
    } for msg in messages]

    return JsonResponse({'messages': message_data})

@login_required
def send_ticket_message(request, ticket_id):
    if request.method == "POST":
        ticket = get_object_or_404(Ticket, id=ticket_id)
        content = request.POST.get('message')
        
        if content:
            msg = TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                message=content
            )
            return JsonResponse({'status': 'sent'})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def update_ticket_status(request, ticket_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_status = data.get('status')
            
            ticket = Ticket.objects.get(id=ticket_id)
            ticket.status = new_status
            
            # This saves the current admin as the technician permanently
            ticket.technician = request.user 
            
            ticket.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def delete_ticket(request, ticket_id):
    try:
        ticket = get_object_or_404(Ticket, id=ticket_id)
        ticket.delete()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
# --- ADMIN VIEWS ---

def is_admin(user):
    return user.is_staff or user.groups.filter(name='Admin').exists()

@login_required
@user_passes_test(is_admin)
def admin_ticket_dashboard(request):
    """View for Admins to manage all system tickets"""
    tickets = Ticket.objects.all().order_by('-updated_at')
    pending_count = tickets.filter(status='Pending').count()
    ticket_detail_url = lambda ticket: redirect('ticket_detail', ticket_id=ticket.id)
    
    return render(request, 'core/Admin/admin_tickets.html', {
        'tickets': tickets,
        'pending_count': pending_count,
        'ticket_detail_url': ticket_detail_url
    })



@login_required
def ticket_detail(request, ticket_id):
    """View to see the conversation and update status (shared or admin only)"""
    ticket = get_object_or_404(Ticket, id=ticket_id)
    
    # Security: Only ticket owner or admin can see the detail
    if not request.user.is_staff and ticket.user != request.user:
        return redirect('submit_ticket')

    if request.method == 'POST':
        # Logic for adding a reply/message
        reply_text = request.POST.get('message')
        if reply_text:
            TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                message=reply_text
            )
            # If admin replies, automatically set to 'In Progress'
            if request.user.is_staff and ticket.status == 'Pending':
                ticket.status = 'In Progress'
                ticket.save()
                
        return redirect('ticket_detail', ticket_id=ticket.id)

    return render(request, 'core/Admin/ticket_detail.html', {'ticket': ticket})

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
        'incident_counts': Incident.objects.values('severity').annotate(total=Count('id')),
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
    # Check permissions
    if not request.user.groups.filter(name__in=['Admin', 'Commander']).exists():
        return redirect('dashboard')
    
    # Original query preserved: Get all users with groups prefetched
    all_users = User.objects.all().prefetch_related('groups').order_by('username')
    
    # Pagination Logic
    items_per_page = 10
    paginator = Paginator(all_users, items_per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Returning page_obj as 'users' so your existing template loop {% for person in users %} still works
    return render(request, 'core/Admin/user_list.html', {
        'users': page_obj,
        'page_obj': page_obj  # Optional: for additional pagination metadata
    })

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

def get_maintenance_initial(asset_id):
    """Helper to prep data from Asset to Maintenance"""
    from .models import Asset
    asset = get_object_or_404(Asset, assets_id=asset_id)
    return {
        'asset': asset,
        'notes': asset.maintenance_reason, # Transfers the 'Why' to the 'Notes'
        'status': 'In Progress'            # Default starting status
    }

@login_required
def add_maintenance(request):
    asset_id = request.GET.get('asset_id')
    initial_data = {}

    if asset_id:
        initial_data = get_maintenance_initial(asset_id)

    if request.method == 'POST':
        # Create form without disabling the field first so it can validate the asset_id
        form = MaintenanceForm(request.POST)
        
        if form.is_valid():
            maintenance = form.save(commit=False)
            maintenance.technician = request.user
            maintenance.save()
            
            asset = maintenance.asset
            asset.status = 'Maintenance'
            asset.save()
            return redirect('maintenance_list')
        else:
            # If invalid, print errors to your console to see what's wrong
            print(form.errors) 
    else:
        form = MaintenanceForm(initial=initial_data)
        
        # Filtering logic to prevent duplicates
        active_log_ids = Maintenance.objects.filter(status='In Progress').values_list('asset_id', flat=True)
        
        if asset_id:
            # If we have a specific asset, limit the queryset to ONLY that asset
            form.fields['asset'].queryset = Asset.objects.filter(assets_id=asset_id)
            # Use 'readonly' in the widget instead of .disabled = True 
            # so the data still sends with the POST
            form.fields['asset'].widget.attrs['readonly'] = True
        else:
            form.fields['asset'].queryset = Asset.objects.filter(status='Maintenance').exclude(id__in=active_log_ids)

    return render(request, 'core/Admin/add_maintenance.html', {'form': form})

@login_required
def edit_maintenance(request, pk):
    log = get_object_or_404(Maintenance, pk=pk)

    if request.method == 'POST':
        form = MaintenanceForm(request.POST, instance=log)
        # Lock Asset ID - it cannot be changed during edit
        form.fields['asset'].disabled = True 

        if form.is_valid():
            updated_log = form.save()
            
            # Update Asset Status based on the Maintenance Status
            asset = updated_log.asset
            if updated_log.status == 'Completed':
                asset.status = 'Active'
                asset.maintenance_reason = "" 
            else:
                asset.status = 'Maintenance'
            asset.save()

            messages.success(request, f"Maintenance for {asset.assets_id} updated successfully.")
            return redirect('maintenance_list')
    else:
        form = MaintenanceForm(instance=log)
        form.fields['asset'].disabled = True

    # Note: Pointing to edit_maintenance.html instead of add_maintenance.html
    return render(request, 'core/Admin/edit_maintenance.html', {
        'form': form,
        'maintenance': log
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
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Incident, IncidentComment # Ensure these imports match your project

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

    # --- PAGINATION LOGIC ---
    all_incidents = Incident.objects.all().order_by('-date')
    paginator = Paginator(all_incidents, 10) # Set to 10 entries per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # --- LOAD ACTIVE INCIDENT ---
    active_incident = None
    comments = []

    active_id = request.session.get('active_incident_id')
    if active_id:
        try:
            active_incident = Incident.objects.get(id=active_id)
            comments = active_incident.comments.all().order_by('created_at')
        except Incident.DoesNotExist:
            request.session['active_incident_id'] = None

    # --- FINAL CONTEXT ---
    context = {
        'incidents': page_obj, # Pass the page object
        'incident': active_incident,
        'comments': comments,
    }

    return render(request, 'core/Admin/incident_list.html', context)


@login_required
def command_incident(request):
    # Purely retrieval for the Commander
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

    # --- PAGINATION LOGIC ---
    all_incidents = Incident.objects.all().order_by('-date')
    paginator = Paginator(all_incidents, 10) # Set to 10 entries per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # --- LOAD ACTIVE INCIDENT ---
    active_incident = None
    comments = []

    active_id = request.session.get('active_incident_id')
    if active_id:
        try:
            active_incident = Incident.objects.get(id=active_id)
            comments = active_incident.comments.all().order_by('created_at')
        except Incident.DoesNotExist:
            request.session['active_incident_id'] = None

    # --- FINAL CONTEXT ---
    context = {
        'incidents': page_obj, # Pass the page object
        'incident': active_incident,
        'comments': comments,
    }

    return render(request, 'core/Commander/command_incident.html', context)

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
def edit_incident(request, incident_id):
    incident = get_object_or_404(Incident, id=incident_id)

    guides = {
        'Malware': 'documents/Guideline-on-Malware-Incident-Response2.pdf',
        'Phishing': 'documents/Phishing-Protocol.pdf',
        'Unauthorized Access': 'documents/Access-Control-SOP.pdf',
    }

    if request.method == 'POST':
        new_status = request.POST.get('status')
        new_actions = request.POST.get('actions_taken', '').strip()

        # Only log if something new was entered
        if new_actions:
            timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
            technician = request.user.username

            log_entry = f"[{timestamp}] {technician}: {new_actions}"

            if incident.actions_taken:
                incident.actions_taken += "\n" + log_entry
            else:
                incident.actions_taken = log_entry

        incident.status = new_status
        incident.save()

        return redirect('incident_list')

    selected_guide = guides.get(incident.severity, 'documents/General-SOP.pdf')

    return render(request, 'core/Admin/edit_incident.html', {
        'incident': incident,
        'guide_path': selected_guide
    })
    
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

def generate_ai_advisory(predicted, current, unresolved, severity_breakdown):
    advice = []

    if predicted > current:
        advice.append("Incident trend is rising. Increase proactive monitoring and vulnerability scanning frequency.")

    if unresolved > 5:
        advice.append("Multiple unresolved maintenance tasks detected. Prioritize patching and hardware diagnostics to reduce system failures.")

    if severity_breakdown.get('High', 0) + severity_breakdown.get('Critical', 0) > 3:
        advice.append("High severity incidents increasing. Implement stricter access control, MFA enforcement, and real-time endpoint protection.")

    if not advice:
        advice.append("Security posture remains stable. Maintain current defense strategies and continue continuous monitoring.")

    return " ".join(advice)



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
    report_type = request.GET.get('report_type', 'it_asset')
    category = request.GET.get('category', 'All')
    export_format = request.GET.get('export')
    page_number = request.GET.get('page', 1)
    
    # 1. FETCH DATA
    data_list = []
    status_labels, status_counts = [], []

    if report_type == 'maintenance':
        data_list = Maintenance.objects.all().select_related('asset', 'technician')
        stats = data_list.values('status').annotate(total=models.Count('id'))
        status_labels = [s['status'] for s in stats]
        status_counts = [s['total'] for s in stats]

    elif report_type == 'incident':
        data_list = Incident.objects.all().select_related('asset')
        stats = data_list.values('severity').annotate(total=models.Count('id'))
        status_labels = [s['severity'] for s in stats]
        status_counts = [s['total'] for s in stats]

    else: # it_asset
        data_list = Asset.objects.all()
        # Handle various "All" strings to ensure the filter doesn't break
        if category not in ['All', 'All Assets', '']:
            data_list = data_list.filter(assets_type=category)
        
        stats = data_list.values('status').annotate(total=models.Count('id'))
        status_labels = [s['status'] for s in stats]
        status_counts = [s['total'] for s in stats]

    # 2. EXCEL EXPORT BLOCK
    if export_format == 'excel':
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename={report_type}_report_{timezone.now().date()}.xlsx'
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Report Data"

        if report_type == 'it_asset':
            headers = ['Asset ID', 'Name', 'Type', 'Location', 'Status', 'Date Added']
            ws.append(headers)
            for obj in data_list:
                date_str = obj.date_added.strftime('%Y-%m-%d') if obj.date_added else ""
                ws.append([obj.assets_id, obj.assets_name, obj.assets_type, obj.location, obj.status, date_str])
        
        elif report_type == 'maintenance':
            headers = ['Asset', 'Technician', 'Type', 'Status', 'Date']
            ws.append(headers)
            for obj in data_list:
                date_str = obj.date.strftime('%Y-%m-%d') if obj.date else ""
                ws.append([obj.asset.assets_name, str(obj.technician), obj.maintenance_type, obj.status, date_str])
        
        elif report_type == 'incident':
            headers = ['Title', 'Asset', 'Severity', 'Status', 'Date']
            ws.append(headers)
            for obj in data_list:
                date_str = obj.date.strftime('%Y-%m-%d') if obj.date else ""
                ws.append([obj.title, str(obj.asset), obj.severity, obj.status, date_str])

        wb.save(response)
        return response

    # 3. RENDER HTML (Pagination)
    total_count = data_list.count() if hasattr(data_list, 'count') else len(data_list)
    paginator = Paginator(data_list, 6) # Show 6 per page
    page_obj = paginator.get_page(page_number)

    context = {
        'report_type': report_type,
        'category': category,      # ESSENTIAL: Pass this back to keep pagination links working
        'data_list': page_obj,     # Template loops over this
        'page_obj': page_obj,      # Controls use this
        'asset_types': Asset.ASSET_TYPES,
        'status_labels': status_labels,
        'status_counts': status_counts,
        'total_count': total_count,
    }
    return render(request, 'core/Admin/reports.html', context)

@login_required
def command_reports(request):
    return render(request, 'core/Commander/command_reports.html')