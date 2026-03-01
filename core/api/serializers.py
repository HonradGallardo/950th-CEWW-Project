from rest_framework import serializers
from django.contrib.auth.models import User
from ..models import Asset, Maintenance, Incident, Notification, Profile

class AssetSerializer(serializers.ModelSerializer):
    """Converts Asset model instances into JSON."""
    class Meta:
        model = Asset
        fields = '__all__'

class MaintenanceSerializer(serializers.ModelSerializer):
    """Includes helpful human-readable fields for the dashboard tables."""
    asset_name = serializers.ReadOnlyField(source='asset.assets_name')
    technician_name = serializers.ReadOnlyField(source='technician.username')

    class Meta:
        model = Maintenance
        fields = ['id', 'asset', 'asset_name', 'technician_name', 'maintenance_type', 'status', 'date', 'notes']

class IncidentSerializer(serializers.ModelSerializer):
    """Prepares incident data with formatted reporting information."""
    reported_by_name = serializers.ReadOnlyField(source='reported_by.username')
    
    class Meta:
        model = Incident
        fields = ['id', 'title', 'severity', 'status', 'description', 'reported_by_name', 'date']
        
class NotificationSerializer(serializers.ModelSerializer):
    """Formats timestamps for the notification bell UI."""
    timestamp = serializers.DateTimeField(source='created_at', format='%b %d, %H:%M', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'message', 'is_read', 'timestamp']

class UserProfileSerializer(serializers.ModelSerializer):
    """Combines User and Profile data into a single object for the API."""
    rank = serializers.ReadOnlyField(source='profile.rank')
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'rank']
        
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'last_login', 'date_joined']