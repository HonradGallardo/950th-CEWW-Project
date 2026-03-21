from rest_framework import serializers
from django.contrib.auth.models import User
from ..models import Asset, IncidentComment, Maintenance, Incident, Notification, Profile
from django.contrib.auth.password_validation import validate_password

class AssetSerializer(serializers.ModelSerializer):
    """Converts Asset model instances into JSON."""

    assigned_to_name = serializers.ReadOnlyField(source='assigned_to.username')
    class Meta:
        model = Asset
        fields = '__all__'
        

class MaintenanceSerializer(serializers.ModelSerializer):
    """Includes helpful human-readable fields for the dashboard tables."""
    asset_name = serializers.ReadOnlyField(source='asset.assets_name')
    technician_name = serializers.ReadOnlyField(source='technician.username')
    asset_type = serializers.CharField(source='asset.assets_type', read_only=True)
    
    # 🚨 ADD THIS LINE: Fetch the string ID (e.g., AST-003)
    asset_string_id = serializers.ReadOnlyField(source='asset.assets_id')

    class Meta:
        model = Maintenance
        # 🚨 ADD 'asset_string_id' TO THE FIELDS LIST
        fields = ['id', 'asset_string_id', 'asset_name', 'asset_type', 'maintenance_type', 'technician_name', 'date', 'last_modified', 'status']

class IncidentSerializer(serializers.ModelSerializer):
    """Prepares incident data with formatted reporting information."""
    reported_by_name = serializers.ReadOnlyField(source='reported_by.username')
    
    # Include details from the related Asset
    asset_location = serializers.ReadOnlyField(source='asset.location')
    asset_id_display = serializers.ReadOnlyField(source='asset.assets_id')
    
    class Meta:
        model = Incident
        # List all fields explicitly to ensure the new SOC fields are exposed to the frontend
        fields = [
            'id', 'title', 'asset', 'asset_location', 'asset_id_display', 
            'affected_area', 'severity', 'status', 'description', 
            'date', 'updated_at', 'reported_by', 'reported_by_name',
            
            # --- NEW SOC FIELDS ADDED ---
            'category', 'detection_source', 'linked_asset', 'iocs', 'cve_id',
            'impact_confidentiality', 'impact_integrity', 'impact_availability',
            'root_cause', 'is_false_positive', 'problems_encountered', 'solutions_applied'
        ]

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
    # Map the nested profile fields
    rank = serializers.CharField(source='profile.rank', required=False, allow_blank=True, allow_null=True)
    image = serializers.ImageField(source='profile.image', required=False, allow_null=True)
    # 🚨 NEW: Added the phone mapping
    phone = serializers.CharField(source='profile.phone', required=False, allow_blank=True, allow_null=True)
    
    # Use write_only so the password is never sent back to the browser
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        # 🚨 ADDED 'phone' to the fields list
        fields = ['id', 'username', 'password', 'first_name', 'last_name', 'email', 'last_login', 'date_joined', 'rank', 'image', 'phone']

    def create(self, validated_data):
        """Hashes password automatically and handles nested Profile data."""
        # 1. Pop the nested profile data out of the validated dictionary FIRST
        profile_data = validated_data.pop('profile', {})
        password = validated_data.pop('password', None)
        
        # 2. Create the base User object
        user = User(**validated_data)
        if password:
            user.set_password(password) # This is the encryption step
        user.save()
        
        # 3. Save the nested Profile data
        # (Assuming a Django Signal automatically creates a blank Profile when a User is created)
        profile = user.profile
        if 'rank' in profile_data:
            profile.rank = profile_data['rank']
        if 'image' in profile_data:
            profile.image = profile_data['image']
        if 'phone' in profile_data:
            profile.phone = profile_data['phone']
        profile.save()
        
        return user

    def update(self, instance, validated_data):
        """Hashes password automatically and handles nested Profile data."""
        # 1. Pop the nested profile data out
        profile_data = validated_data.pop('profile', {})
        password = validated_data.pop('password', None)
        
        # 2. Update standard User fields
        instance.username = validated_data.get('username', instance.username)
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.email = validated_data.get('email', instance.email)

        if password:
            instance.set_password(password) # Encrypts the new password
        
        instance.save()
        
        # 3. Update the nested Profile fields
        profile = instance.profile
        if 'rank' in profile_data:
            profile.rank = profile_data['rank']
        if 'image' in profile_data:
            profile.image = profile_data['image']
        if 'phone' in profile_data:
            profile.phone = profile_data['phone']
        profile.save()
        
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