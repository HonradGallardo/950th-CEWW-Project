from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from ..models import Ticket, TicketMessage, TicketAttachment

# --- SERIALIZER ---
class TicketSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    technician_name = serializers.CharField(source='technician.username', read_only=True, default="Unassigned")
    # Add this field
    user_avatar = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = ['id', 'subject', 'user_name', 'status', 'description', 'created_at', 'technician_name', 'updated_at', 'user_avatar']

    def get_user_avatar(self, obj):
        try:
            # Matches your user_list.html logic
            if obj.user.profile.image:
                return obj.user.profile.image.url
        except:
            pass
        return None

# --- VIEWSET ---
class TicketViewSet(viewsets.ModelViewSet):
    serializer_class = TicketSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.groups.filter(name='Admin').exists():
            return Ticket.objects.all().order_by('-updated_at')
        return Ticket.objects.filter(user=user).order_by('-created_at')

    @action(detail=True, methods=['get'])
    def chat_thread(self, request, pk=None):
        ticket = self.get_object()
        user_is_admin = request.user.is_staff or request.user.groups.filter(name='Admin').exists()
        chat_with_staff_username = request.GET.get('with_staff')

        # select_related avoids N+1 database hits
        all_messages = ticket.messages.all().select_related('sender', 'recipient').order_by('created_at')

        if user_is_admin:
            if chat_with_staff_username and chat_with_staff_username not in ['SHOW_ALL', 'Everyone', 'null']:
                filtered_messages = all_messages.filter(
                    (Q(sender__username=chat_with_staff_username) & Q(recipient=ticket.user)) |
                    (Q(sender=ticket.user) & Q(recipient__username=chat_with_staff_username)) |
                    (Q(recipient__isnull=True) & Q(sender__is_staff=True))
                )
            else:
                filtered_messages = all_messages
        else:
            filtered_messages = all_messages.filter(
                Q(sender=request.user) | Q(recipient=request.user) | Q(recipient__isnull=True)
            )

        # We provide both 'sender' and 'sender_name' to prevent JS undefined errors
        messages_data = [{
            'id': msg.id,
            'sender': msg.sender.username,
            'sender_name': msg.sender.username,
            'sender_avatar': msg.sender.profile.image.url if hasattr(msg.sender, 'profile') and msg.sender.profile.image else None,
            'recipient_name': msg.recipient.username if msg.recipient else "Everyone",
            'message': msg.message,
            'timestamp': msg.created_at.strftime('%b %d, %H:%M'),
            'is_me': msg.sender == request.user,
            'is_staff': msg.sender.is_staff,
            'attachments': [{
                'id': a.id,
                'name': a.file.name.split('/')[-1],
                'url': a.file.url
            } for a in msg.attachments.all()] 
        } for msg in filtered_messages]

        attachments_data = [{
            'id': a.id,
            'name': a.file.name.split('/')[-1],
            'url': a.file.url,
            'message_id': a.message.id if a.message else None 
        } for a in ticket.all_attachments.all()]

        return Response({
            'messages': messages_data,
            'attachments': attachments_data
        })

    @action(detail=True, methods=['post'])
    def send_reply(self, request, pk=None):
        ticket = self.get_object()
        text = request.data.get('message', '').strip()
        recipient_username = request.data.get('recipient')
        files = request.FILES.getlist('attachments') 

        if not text and not files:
            return Response({'status': 'error', 'message': 'Empty message'}, status=400)

        target_user = None
        if recipient_username and recipient_username not in ["Everyone", "null"]:
            target_user = User.objects.filter(username=recipient_username).first()
        
        if not target_user:
            if request.user.is_staff:
                target_user = ticket.user
            else:
                target_user = ticket.technician

        new_msg = TicketMessage.objects.create(
            ticket=ticket, 
            sender=request.user, 
            recipient=target_user, 
            message=text
        )

        for f in files:
            TicketAttachment.objects.create(
                ticket=ticket, 
                message=new_msg, 
                file=f
            )
            
        return Response({'status': 'success'})
    
    def perform_create(self, serializer):
        data = self.request.data
        category = data.get("category", "General")
        description = data.get("description", "")
        
        header = f"🎫 TICKET TYPE: {category.upper()}\n"
        header += "─" * 25 + "\n"
        details = []
        
        if category == "Identity":
            details.append(f"👤 First Name: {data.get('first_name', 'N/A')}")
            details.append(f"👤 Last Name: {data.get('last_name', 'N/A')}")
            details.append(f"📧 Email: {data.get('email', 'N/A')}")
            details.append(f"🎖️ Rank: {data.get('rank', 'N/A')}")
            details.append(f"📞 Phone: {data.get('phone', 'N/A')}")
        elif category == "Security":
            details.append(f"🔐 Auth ID: {data.get('auth_id', 'N/A')}")
            details.append(f"⚠️ Request Type: {data.get('removal_type', 'N/A')}")
            details.append(f"🖥️ System: {data.get('system_name', 'N/A')}")

        detail_text = "\n".join(details)
        full_body = f"{header}{detail_text}\n\n📝 USER CONCERN:\n{description}"

        ticket = serializer.save(
            user=self.request.user, 
            description=full_body, 
            status="Pending"
        )

        files = self.request.FILES.getlist('attachments')
        for f in files:
            TicketAttachment.objects.create(ticket=ticket, file=f)

    @action(detail=True, methods=['post'])
    def update_technical_details(self, request, pk=None):
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
    
    def destroy(self, request, pk=None):
        ticket = self.get_object()
        user_is_admin = request.user.is_staff or request.user.groups.filter(name='Admin').exists()
        if not user_is_admin and ticket.user != request.user:
            return Response(
                {'message': 'You do not have permission to delete this ticket.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        ticket.delete()
        return Response({'status': 'success', 'message': 'Ticket deleted'}, status=status.HTTP_204_NO_CONTENT)