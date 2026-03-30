from rest_framework import viewsets, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.utils.html import escape # SECURITY: Neutralizes XSS attacks
import os # SECURITY: For checking file extensions

from ..models import Ticket, TicketMessage, TicketAttachment

# CRITICAL NEW IMPORT: Directly import Cloudinary to bypass strict image rules
import cloudinary.uploader  

# --- SECURITY: Allowed File Types ---
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx', '.txt', '.csv'}

# --- SERIALIZERS ---
# Note: Ensure the global `to_representation` from serializers.py is used if imported

class AttachmentSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
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
    attachments = AttachmentSerializer(many=True, read_only=True)
    is_me = serializers.SerializerMethodField() 

    class Meta:
        model = TicketMessage
        fields = ['id', 'message', 'sender_name','recipient_name', 'attachments', 'timestamp', 'is_me']

    def get_is_me(self, obj):
        request = self.context.get('request')
        return obj.sender == request.user if request else False
        
    # SECURITY FIX: Sanitize output
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('message'):
            data['message'] = escape(data['message'])
        return data

class TicketSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    technician_name = serializers.CharField(source='technician.username', read_only=True, default="Unassigned")
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
        
    # SECURITY FIX: Sanitize output globally
    def to_representation(self, instance):
        data = super().to_representation(instance)
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = escape(value)
        return data

# --- VIEWSET ---

class TicketViewSet(viewsets.ModelViewSet):
    serializer_class = TicketSerializer
    pagination_class = None

    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
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

        all_messages = ticket.messages.all().select_related('sender', 'recipient').order_by('created_at')

        if chat_with_staff_username == 'GROUP_CHAT':
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
            filtered_messages = all_messages.filter(
                Q(sender=request.user) | Q(recipient=request.user) | Q(recipient__isnull=True)
            )

        def get_safe_avatar(user):
            try:
                if hasattr(user, 'profile') and user.profile.image and hasattr(user.profile.image, 'url'):
                    return user.profile.image.url
            except Exception:
                pass
            return None

        # FIX: Safe extraction for raw URL strings
        def get_safe_filename(file_obj):
            try:
                if file_obj and hasattr(file_obj, 'name') and file_obj.name:
                    return file_obj.name.split('/')[-1]
            except Exception:
                pass
            return "Attachment"
            
        def get_safe_url(file_obj):
            try:
                # 1. Check if the raw string in the database is ALREADY a full URL!
                if file_obj and hasattr(file_obj, 'name') and file_obj.name and file_obj.name.startswith('http'):
                    return file_obj.name
                
                # 2. If it's a normal file path, let Django build the Cloudinary URL
                if file_obj and hasattr(file_obj, 'url'):
                    return file_obj.url
            except Exception:
                pass
            return ""

        # SECURITY FIX: Escape everything
        messages_data = [{
            'id': msg.id,
            'sender': escape(msg.sender.username),
            'sender_name': escape(msg.sender.username),
            'sender_avatar': get_safe_avatar(msg.sender),
            'recipient_name': escape(msg.recipient.username) if msg.recipient else "Everyone",
            'message': escape(msg.message), 
            'timestamp': msg.created_at.strftime('%b %d, %H:%M'),
            'is_me': msg.sender == request.user,
            'is_staff': msg.sender.is_staff,
            'attachments': [{
                'id': a.id,
                'name': get_safe_filename(a.file),
                'url': get_safe_url(a.file)
            } for a in msg.attachments.all()] 
        } for msg in filtered_messages]

        attachments_data = [{
            'id': a.id,
            'name': get_safe_filename(a.file),
            'url': get_safe_url(a.file),
            'message_id': a.message.id if hasattr(a, 'message') and a.message else None 
        } for a in ticket.all_attachments.all()]

        return Response({
            'messages': messages_data,
            'attachments': attachments_data
        })

    @action(detail=True, methods=['post'])
    def send_reply(self, request, pk=None):
        ticket = self.get_object()
        # SECURITY FIX: Escape the incoming chat message
        text = escape(request.data.get('message', '').strip())
        recipient_username = request.data.get('recipient')
        is_group_chat = request.data.get('is_group_chat') == 'true'
        files = request.FILES.getlist('attachments') 

        if not text and not files:
            return Response({'status': 'error', 'message': 'Empty message'}, status=400)

        target_user = None
        if not is_group_chat:
            if recipient_username and recipient_username not in ["Everyone", "null", "GROUP_CHAT"]:
                target_user = User.objects.filter(username=recipient_username).first()
            if not target_user:
                target_user = ticket.user if request.user.is_staff else ticket.technician

        new_msg = TicketMessage.objects.create(
            ticket=ticket, 
            sender=request.user, 
            recipient=target_user, 
            message=text
        )

        for f in files:
            # SECURITY FIX: Validate file extension
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue
            try:
                # FIX: Force 'auto' detection for video/pdf and save the raw URL string
                upload_result = cloudinary.uploader.upload(f, resource_type="auto")
                TicketAttachment.objects.create(
                    ticket=ticket, 
                    message=new_msg, 
                    file=upload_result['secure_url'] 
                )
            except Exception as e:
                print("File Upload Error:", e)
            
        return Response({'status': 'success'})
    
    def perform_create(self, serializer):
        data = self.request.data
        
        # SECURITY FIX: Escape EVERY piece of text inputted by the user
        category = escape(data.get("category", "General"))
        description = escape(data.get("description", ""))
        subject_val = escape(data.get("subject", "No Subject"))
        
        header = f"🎫 TICKET TYPE: {category.upper()}\n"
        header += "─" * 25 + "\n"
        details = []
        
        if category == "Identity":
            details.append(f"👤 First Name: {escape(data.get('first_name', 'N/A'))}")
            details.append(f"👤 Last Name: {escape(data.get('last_name', 'N/A'))}")
            details.append(f"📧 Email: {escape(data.get('email', 'N/A'))}")
            details.append(f"🎖️ Rank: {escape(data.get('rank', 'N/A'))}")
            details.append(f"📞 Phone: {escape(data.get('phone', 'N/A'))}")

        elif category == "Security":
            details.append(f"🔐 Auth ID: {escape(data.get('auth_id', 'N/A'))}")
            details.append(f"⚠️ Request Type: {escape(data.get('removal_type', 'N/A'))}")

        elif category == "Technical":
            details.append(f"📦 Impacted Module: {escape(data.get('bug_module', 'N/A'))}")
            details.append(f"🚫 Error Code: {escape(data.get('error_code', 'None'))}")
            details.append(f"🔄 Steps: {escape(data.get('reproduce_steps', 'N/A'))}")

        elif category == "Access":
            if data.get('target_resource'):
                details.append(f"🔑 Resource: {escape(data.get('target_resource', 'N/A'))}")
                details.append(f"📊 Level: {escape(data.get('access_level', 'N/A'))}")
                details.append(f"✍️ Approver: {escape(data.get('approving_officer', 'N/A'))}")
            else:
                details.append(f"🆔 Affected ID: {escape(data.get('affected_id', 'N/A'))}")
                details.append(f"📱 Alt Contact: {escape(data.get('alt_contact', 'N/A'))}")

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
            subject=subject_val,
            description=full_body, 
            status="Pending"
        )

        files = self.request.FILES.getlist('attachments')
        for f in files:
            # SECURITY FIX: Validate file extension
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue
            try:
                # FIX: Force 'auto' detection for video/pdf and save the raw URL string
                upload_result = cloudinary.uploader.upload(f, resource_type="auto")
                TicketAttachment.objects.create(
                    ticket=ticket, 
                    file=upload_result['secure_url']
                )
            except Exception as e:
                print("File Upload Error:", e)

    @action(detail=True, methods=['post'])
    def update_technical_details(self, request, pk=None):
        # SECURITY FIX: Prevent Privilege Escalation
        if not (request.user.is_staff or request.user.groups.filter(name='Admin').exists()):
            return Response({'error': 'Unauthorized. Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
            
        ticket = self.get_object()
        old_tech = ticket.technician
        data = request.data

        ticket.status = data.get('status', ticket.status)
        ticket.priority = data.get('priority', ticket.priority)
        tech_id = data.get('technician_id')
        
        if tech_id and str(tech_id).strip() != "":
            new_tech = get_object_or_404(User, id=tech_id)
            if old_tech != new_tech:
                ticket.last_technician = old_tech.username if old_tech else "None"
                ticket.technician = new_tech
                if ticket.status == 'Pending':
                    ticket.status = 'Open'
        else:
            if ticket.technician:
                ticket.last_technician = ticket.technician.username
                ticket.technician = None
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