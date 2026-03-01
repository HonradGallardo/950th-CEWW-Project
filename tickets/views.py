from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Ticket

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
    """
    Renders the conversation shell. 
    The co-developer's images will be rendered by the chat_thread API.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if not is_admin(request.user) and ticket.user != request.user:
        return redirect('dashboard')
    return render(request, 'tickets/Admin/ticket_detail.html', {'ticket': ticket})