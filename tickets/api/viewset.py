from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny         # Added
from rest_framework.authentication import TokenAuthentication, SessionAuthentication  # Added
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from ..models import Ticket, TicketMessage, TicketAttachment

# --- SERIALIZERS ---

class AttachmentSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    # Ensure full URL is generated for frontend view/download
    url = serializers.FileField(source='file') 

    class Meta:
        model = TicketAttachment
        fields = ['id', 'url', 'name']

    def get_name(self, obj):
        return obj.file.name.split('/')[-1]

class TicketMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.ReadOnlyField(source='sender.username')
    recipient_name = serializers.ReadOnlyField(source='recipient.username', default="Everyone")
    timestamp = serializers.DateTimeField(source='created_at', format='%b %d, %H:%M', read_only=True)
    # This must be a nested serializer to provide the 'url' and 'name' for bubbles
    attachments = AttachmentSerializer(many=True, read_only=True)
    is_me = serializers.SerializerMethodField() # Add this to match your JS usage

    class Meta:
        model = TicketMessage
        fields = ['id', 'message', 'sender_name','recipient_name', 'attachments', 'timestamp', 'is_me']

    def get_is_me(self, obj):
        request = self.context.get('request')
        return obj.sender == request.user if request else False

class TicketSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    # These fields reach into the User model to get the names
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    
    technician_name = serializers.CharField(source='technician.username', read_only=True, default="Unassigned")
    
    # This maps the model field 'last_technician' to the frontend key 'previous_technician'
    previous_technician = serializers.CharField(source='last_technician', read_only=True, default="None")
    
    user_avatar = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(format='%b %d, %Y %H:%M', read_only=True)

    class Meta:
        model = Ticket
        fields = [
            'id', 'subject', 'user_name', 'first_name', 'last_name', 
            'status', 'priority', 'description', 'created_at', 'technician_name', 
            'previous_technician', 'updated_at', 'user_avatar'
        ]

    def get_user_avatar(self, obj):
        try:
            if obj.user.profile.image:
                return obj.user.profile.image.url
        except:
            pass
        return None


# --- VIEWSET ---

class TicketViewSet(viewsets.ModelViewSet):
    serializer_class = TicketSerializer
    pagination_class = None
    
    # 🔒 ENFORCE AUTHENTICATION HERE 
    #authentication_classes = [TokenAuthentication, SessionAuthentication]
    #permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # Allow anyone (even guests) to submit a ticket via POST
        if self.action == 'create':
            return [AllowAny()]
        # Require login for everything else (viewing, deleting, chatting)
        return [IsAuthenticated()]

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

        if chat_with_staff_username == 'GROUP_CHAT':
            # Logic: Group messages are those where recipient is null
            filtered_messages = all_messages.filter(recipient__isnull=True)
        elif user_is_admin:
            if chat_with_staff_username and chat_with_staff_username not in ['SHOW_ALL', 'Everyone', 'null']:
                filtered_messages = all_messages.filter(
                    (Q(sender__username=chat_with_staff_username) & Q(recipient=ticket.user)) |
                    (Q(sender=ticket.user) & Q(recipient__username=chat_with_staff_username))
                )
            else:
                filtered_messages = all_messages
        else:
            # For the regular user, show their private messages AND group messages
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
        is_group_chat = request.data.get('is_group_chat') == 'true'
        files = request.FILES.getlist('attachments') 

        if not text and not files:
            return Response({'status': 'error', 'message': 'Empty message'}, status=400)

        # Logic: If it's a group chat, recipient is None. 
        # Otherwise, find the target user.
        # In viewset.py -> send_reply method
        target_user = None
        if not is_group_chat:
            # Ensure "Everyone" sent from JS results in target_user = None
            if recipient_username and recipient_username not in ["Everyone", "null", "GROUP_CHAT"]:
                target_user = User.objects.filter(username=recipient_username).first()
            
            if not target_user:
                target_user = ticket.user if request.user.is_staff else ticket.technician

        new_msg = TicketMessage.objects.create(
            ticket=ticket, 
            sender=request.user, 
            recipient=target_user, # Will be None if is_group_chat is true
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
        
        # 1. Identity / New Account Fields
        if category == "Identity":
            details.append(f"👤 First Name: {data.get('first_name', 'N/A')}")
            details.append(f"👤 Last Name: {data.get('last_name', 'N/A')}")
            details.append(f"📧 Email: {data.get('email', 'N/A')}")
            details.append(f"🎖️ Rank: {data.get('rank', 'N/A')}")
            details.append(f"📞 Phone: {data.get('phone', 'N/A')}")

        # 2. Security / MFA Removal Fields
        elif category == "Security":
            details.append(f"🔐 Auth ID: {data.get('auth_id', 'N/A')}")
            details.append(f"⚠️ Request Type: {data.get('removal_type', 'N/A')}")

        # 3. Technical / Bug Report Fields (New)
        elif category == "Technical":
            details.append(f"📦 Impacted Module: {data.get('bug_module', 'N/A')}")
            details.append(f"🚫 Error Code: {data.get('error_code', 'None')}")
            details.append(f"🔄 Steps: {data.get('reproduce_steps', 'N/A')}")

        # 4. Access / Permission Fields (New)
        elif category == "Access":
            # Handles both Permission changes and Login/Lockout issues
            if data.get('target_resource'):
                details.append(f"🔑 Resource: {data.get('target_resource', 'N/A')}")
                details.append(f"📊 Level: {data.get('access_level', 'N/A')}")
                details.append(f"✍️ Approver: {data.get('approving_officer', 'N/A')}")
            else:
                details.append(f"🆔 Affected ID: {data.get('affected_id', 'N/A')}")
                details.append(f"📱 Alt Contact: {data.get('alt_contact', 'N/A')}")

        detail_text = "\n".join(details)
        full_body = f"{header}{detail_text}\n\n📝 USER CONCERN:\n{description}"

        if self.request.user.is_authenticated:
            ticket_owner = self.request.user
        else:
            ticket_owner, created = User.objects.get_or_create(
                username='PublicGuest',
                defaults={'first_name': 'Public', 'last_name': 'Guest', 'email': 'guest@system.local'}
            )

        ticket = serializer.save(
            user=ticket_owner, 
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

        # 1. Update status and priority first
        ticket.status = data.get('status', ticket.status)
        ticket.priority = data.get('priority', ticket.priority)
        
        # 2. Capture the tech_id from the frontend
        tech_id = data.get('technician_id')
        
        if tech_id and str(tech_id).strip() != "":
            new_tech = get_object_or_404(User, id=tech_id)
            if old_tech != new_tech:
                ticket.last_technician = old_tech.username if old_tech else "None"
                ticket.technician = new_tech
                
                # CRITICAL: If a tech is assigned, the ticket should no longer be 'Pending'
                if ticket.status == 'Pending':
                    ticket.status = 'Open'
                    
        else:
            # UNASSIGNED LOGIC: 
            # If no technician ID is sent (Unassigned), clear the tech and force status to Pending
            if ticket.technician:
                ticket.last_technician = ticket.technician.username
                ticket.technician = None
            
            # Force the status to Pending regardless of what the frontend sent
            ticket.status = 'Pending'

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