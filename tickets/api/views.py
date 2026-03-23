from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q
from ..models import Ticket, TicketMessage, TicketAttachment
from .serializers import TicketSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_ticket_chat(request, ticket_id):
    """API logic moved to the dedicated api folder"""
    ticket = get_object_or_404(Ticket, id=ticket_id)
    
    # Filtering logic for Admin vs User
    user_is_admin = request.user.is_staff or request.user.groups.filter(name='Admin').exists()
    chat_with_staff_username = request.GET.get('with_staff')

    if user_is_admin:
        all_messages = ticket.messages.all().select_related('sender', 'recipient').order_by('created_at')
        if chat_with_staff_username == 'SHOW_ALL':
            filtered_messages = all_messages
        else:
            target_staff = chat_with_staff_username if chat_with_staff_username else request.user.username
            filtered_messages = all_messages.filter(
                (Q(sender__username=target_staff) & (Q(recipient=ticket.user) | Q(recipient__isnull=True))) |
                (Q(sender=ticket.user) & (Q(recipient__username=target_staff) | Q(recipient__isnull=True)))
            )
    else:
        filtered_messages = ticket.messages.filter(
            Q(sender=request.user) | Q(recipient=request.user) | Q(recipient__isnull=True)
        ).select_related('sender', 'recipient').order_by('created_at')

    # Formatting data for the Frontend Assistant
    messages_data = [{
        'sender': msg.sender.username,
        'message': msg.message,
        'timestamp': msg.created_at.strftime('%b %d, %H:%M'),
        'is_me': msg.sender == request.user,
        'is_staff': msg.sender.is_staff,
        'recipient': msg.recipient.username if msg.recipient else "Everyone"
    } for msg in filtered_messages]

    attachments_data = [{
        'name': a.file.name.split('/')[-1],
        'url': a.file.url
    } for a in ticket.all_attachments.all()]

    return Response({
        'messages': messages_data,
        'attachments': attachments_data
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_ticket_message(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    content = request.data.get('message')
    recipient_username = request.data.get('recipient') 
    
    target_user = None
    if recipient_username and recipient_username != "Everyone":
        from django.contrib.auth.models import User
        target_user = User.objects.filter(username=recipient_username).first()

    if content:
        TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            recipient=target_user,
            message=content
        )
        return Response({'status': 'sent'})
            
    return Response({'status': 'error'}, status=400)