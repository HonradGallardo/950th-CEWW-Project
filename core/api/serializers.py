from rest_framework import serializers
from django.contrib.auth.models import User
from ..models import Asset, IncidentComment, Maintenance, Incident, Notification, Profile
from django.contrib.auth.password_validation import validate_password

class AssetSerializer(serializers.ModelSerializer):
    """Converts Asset model instances into JSON."""
    class Meta:
        model = Asset
        fields = '__all__'
        

class MaintenanceSerializer(serializers.ModelSerializer):
    """Includes helpful human-readable fields for the dashboard tables."""
    asset_name = serializers.ReadOnlyField(source='asset.assets_name')
    technician_name = serializers.ReadOnlyField(source='technician.username')
    
    # 🚨 ADD THIS LINE: Fetch the string ID (e.g., AST-003)
    asset_string_id = serializers.ReadOnlyField(source='asset.assets_id')

    class Meta:
        model = Maintenance
        # 🚨 ADD 'asset_string_id' TO THE FIELDS LIST
        fields = ['id', 'asset', 'asset_string_id', 'asset_name', 'technician_name', 'maintenance_type', 'status', 'date', 'notes']

# 🚨 RESTORED: This is the missing IncidentSerializer
class IncidentSerializer(serializers.ModelSerializer):
    """Prepares incident data with formatted reporting information."""
    reported_by_name = serializers.ReadOnlyField(source='reported_by.username')
    
    class Meta:
        model = Incident
        fields = '__all__'

class IncidentCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.ReadOnlyField(source='author.username')
    formatted_time = serializers.DateTimeField(source='created_at', format='%b %d, %H:%M', read_only=True)
    is_current_user = serializers.SerializerMethodField()

    class Meta:
        model = IncidentComment
        fields = ['id', 'incident', 'author_name', 'message', 'formatted_time', 'is_current_user']

    def get_is_current_user(self, obj):
        # Checks if the person viewing the log is the person who wrote the comment
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            return obj.author == request.user
        return False
        return False
        
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
        
# core/api/serializers.py

class UserSerializer(serializers.ModelSerializer):
    rank = serializers.CharField(source='profile.rank', required=False)
    image = serializers.ImageField(source='profile.image', required=False) 
    # Use write_only so the password is never sent back to the browser
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'first_name', 'last_name', 'email', 'last_login', 'date_joined', 'rank', 'image']

    def create(self, validated_data):
        """Hashes password automatically when creating a new user."""
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password) # This is the encryption step
        user.save()
        return user

    def update(self, instance, validated_data):
        """Hashes password automatically when updating an existing user."""
        password = validated_data.pop('password', None)
        
        # Update standard fields
        instance.username = validated_data.get('username', instance.username)
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.email = validated_data.get('email', instance.email)

        if password:
            instance.set_password(password) # Encrypts the new password
        
        instance.save()
        return instance
        

class ChangePasswordSerializer(serializers.Serializer):
    """Handles the validation and updating of user passwords via API."""
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    confirm_password = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "The two password fields didn't match."})
        return attrs