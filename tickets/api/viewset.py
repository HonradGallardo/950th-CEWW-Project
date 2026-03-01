from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from ..models import Ticket, TicketMessage, TicketAttachment
from .serializers import AttachmentSerializer, TicketSerializer, TicketMessageSerializer

class TicketViewSet(viewsets.ModelViewSet):
    serializer_class = TicketSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.groups.filter(name='Admin').exists():
            return Ticket.objects.all().order_by('-updated_at')
        return Ticket.objects.filter(user=user).order_by('-created_at')

    def perform_create(self, serializer):
        """Initial ticket submission logic."""
        data = self.request.data
        category = data.get("category")
        description = data.get("description", "")
        extra_info = ""

        if category == "Identity":
            extra_info = f"\n\n--- Account Details ---\nName: {data.get('first_name', '')} {data.get('last_name', '')}\nRank: {data.get('rank', '')}"
        elif category == "Security":
            extra_info = f"\n\n--- Security Request ---\nAuth ID: {data.get('auth_id', '')}\nRemoval Type: {data.get('removal_type', '')}"

        ticket = serializer.save(user=self.request.user, description=f"{description}{extra_info}", status="Pending")

        # Save initial general attachments
        files = self.request.FILES.getlist('attachments')
        for f in files:
            TicketAttachment.objects.create(ticket=ticket, file=f)

    @action(detail=True, methods=['get'])
    def chat_thread(self, request, pk=None):
        """Fetches threaded chat with integrated image data for Messenger Grids."""
        ticket = self.get_object()
        user_is_admin = request.user.is_staff or request.user.groups.filter(name='Admin').exists()
        chat_with_staff = request.query_params.get('with_staff')

        if user_is_admin:
            all_msgs = ticket.messages.all().select_related('sender', 'recipient').order_by('created_at')
            if chat_with_staff == 'SHOW_ALL':
                filtered = all_msgs
            else:
                target_staff = chat_with_staff if chat_with_staff else request.user.username
                filtered = all_msgs.filter(
                    (Q(sender__username=target_staff) & (Q(recipient=ticket.user) | Q(recipient__isnull=True))) |
                    (Q(sender=ticket.user) & (Q(recipient__username=target_staff) | Q(recipient__isnull=True)))
                )
        else:
            filtered = ticket.messages.filter(
                Q(sender=request.user) | Q(recipient=request.user) | Q(recipient__isnull=True)
            ).order_by('created_at')

        # 'context' allows is_me calculation in Serializer
        msg_serializer = TicketMessageSerializer(filtered, many=True, context={'request': request})
        attach_serializer = AttachmentSerializer(ticket.all_attachments.all(), many=True)

        return Response({
            'messages': msg_serializer.data,
            'attachments': attach_serializer.data
        })

    @action(detail=True, methods=['post'])
    def send_reply(self, request, pk=None):
        """Processes responses and groups attachments specifically to the message bubble."""
        ticket = self.get_object()
        text = request.data.get('message', '').strip()
        recipient_username = request.data.get('recipient')
        
        # 1. Capture the list of files from the 'attachments' key
        files = request.FILES.getlist('attachments') 

        if not text and not files:
            return Response({'status': 'error', 'message': 'Empty message'}, status=400)

        target_user = User.objects.filter(username=recipient_username).first() if recipient_username != "Everyone" else None

        # 2. Create the message bubble FIRST
        new_msg = TicketMessage.objects.create(
            ticket=ticket, 
            sender=request.user, 
            recipient=target_user, 
            message=text
        )

        # 3. LINK files to the 'new_msg' to enable grouped grids
        for f in files:
            TicketAttachment.objects.create(
                ticket=ticket, 
                message=new_msg, # Links the file directly to the chat bubble
                file=f
            )
            
        return Response({'status': 'success'})

    @action(detail=True, methods=['post'])
    def update_technical_details(self, request, pk=None):
        """Technical updates with history logging."""
        ticket = self.get_object()
        old_tech = ticket.technician
        data = request.data

        ticket.status = data.get('status', ticket.status)
        ticket.priority = data.get('priority', ticket.priority)
        ticket.description = data.get('description', ticket.description)

        tech_id = data.get('technician_id')
        if tech_id:
            new_tech = get_object_or_404(User, id=tech_id)
            if old_tech != new_tech:
                ticket.last_technician = old_tech.username if old_tech else "None"
                ticket.technician = new_tech
        elif ticket.status == 'Pending' and ticket.technician:
            ticket.last_technician = ticket.technician.username
            ticket.technician = None

        ticket.save()
        return Response({'status': 'success'})