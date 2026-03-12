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
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    # Fields for Column 3 and 4
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    
    # Field for Column 6
    technician_name = serializers.CharField(source='technician.username', read_only=True, default="Unassigned")
    
    # Field for Column 7 (Previous Technician)
    previous_technician = serializers.CharField(source='last_technician', read_only=True, default="None")
    
    user_avatar = serializers.SerializerMethodField()
    
    # Field for Column 9
    created_at = serializers.DateTimeField(format='%b %d, %Y %I:%M %p', read_only=True)

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
            return None