from rest_framework import serializers
from ..models import Ticket, TicketMessage, TicketAttachment
from django.contrib.auth.models import User

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
    attachments = AttachmentSerializer(many=True, source='all_attachments', read_only=True)
    technician_name = serializers.ReadOnlyField(source='technician.username', default="Unassigned")
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'subject', 'category', 'priority', 'status', 
            'description', 'technician_name', 'last_technician', 
            'attachments', 'created_at'
        ]