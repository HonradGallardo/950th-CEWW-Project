from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Q # Needed for filtering
from .models import Ticket, TicketMessage

def is_admin(user):
    return user.is_staff or user.groups.filter(name='Admin').exists()

@login_required
def submit_ticket(request):
    if request.method == "POST":
        # 1. Logic to save the ticket via standard POST if not using the API directly
        # ... your saving logic ...
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        # Redirect to the same view to clear the POST data
        return redirect('tickets:submit_ticket') 

    # --- FETCH TICKETS FOR THE SIDEBAR ---
    # This ensures that whenever the page is loaded (GET), the sidebar has data.
    user_tickets = Ticket.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'user_tickets': user_tickets,
    }
    
    return render(request, "tickets/submit_ticket.html", context)
    
@login_required
@user_passes_test(is_admin)
def admin_ticket_dashboard(request):
    """Render the dashboard shell only."""
    return render(request, 'tickets/Admin/admin_tickets.html')

@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    
    # Permission check
    if not is_admin(request.user) and ticket.user != request.user:
        return redirect('dashboard')

    # --- 1. GET ALL POTENTIAL TECHNICIANS ---
    # This fetches every user who is staff or in the 'Admin' group 
    # so they appear in your assignment dropdown.
    all_admins = User.objects.filter(
        Q(is_staff=True) | Q(groups__name='Admin')
    ).distinct().order_by('username')

    # --- 2. DYNAMICALLY FIND ACTIVE CHAT PARTICIPANTS (Optional) ---
    # You can keep this if you use 'other_admins' specifically for a sidebar 
    # or "who is online" list, but for the dropdown, use 'all_admins'.
    active_staff_ids = TicketMessage.objects.filter(
        ticket=ticket
    ).filter(
        Q(sender__is_staff=True) | Q(sender__groups__name='Admin')
    ).values_list('sender_id', flat=True).distinct()

    other_admins = User.objects.filter(
        id__in=active_staff_ids
    ).exclude(id=request.user.id).distinct()

    return render(request, 'tickets/Admin/ticket_detail.html', {
        'ticket': ticket,
        'all_admins': all_admins,    # Use this for the Assign Dropdown
        'other_admins': other_admins # Use this for the chat participant list
    })