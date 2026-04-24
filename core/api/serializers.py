from rest_framework import serializers
from django.contrib.auth.models import User
from ..models import Asset, IncidentComment, Maintenance, Incident, Notification, Profile
from django.contrib.auth.password_validation import validate_password

class AssetSerializer(serializers.ModelSerializer):
    """Converts Asset model instances into JSON with comprehensive hardware/maintenance logic."""
    assigned_to_name = serializers.ReadOnlyField(source='assigned_to.username')
    
    # Optional fields for dynamic frontend logic
    processor = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    ram_gb = serializers.IntegerField(required=False, allow_null=True)
    storage_capacity = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    os_version = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    attachment = serializers.FileField(required=False, allow_null=True)
    maintenance_attachment = serializers.FileField(required=False, allow_null=True)
    # Networking & Infrastructure
    ip_address = serializers.IPAddressField(required=False, allow_null=True)
    mac_address = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    firmware_version = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    total_ports = serializers.IntegerField(required=False, allow_null=True)
    rack_unit = serializers.IntegerField(required=False, allow_null=True)
    
    # Laptop specific
    battery_health = serializers.IntegerField(required=False, allow_null=True)

    # NEW: Maintenance Specifics
    faulty_hardware_part = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    software_issue_type = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Asset
        fields = '__all__'

    def validate(self, data):
        """
        Custom validation logic for IT assets.
        """
        status = data.get('status', '')
        
        # Logic: If status is 'Under Maintenance', ensure at least one diagnostic field or reason is present
        if status == 'Maintenance':
            reason = data.get('maintenance_reason')
            hw_part = data.get('faulty_hardware_part')
            sw_issue = data.get('software_issue_type')
            
            if not any([reason, hw_part, sw_issue]):
                raise serializers.ValidationError({
                    "maintenance_reason": "Maintenance requires a reason, hardware part, or software issue type."
                })
        
        # Logic: Ensure Battery Health is within 0-100 if provided
        battery = data.get('battery_health')
        if battery is not None and (battery < 0 or battery > 100):
            raise serializers.ValidationError({"battery_health": "Battery health must be between 0 and 100."})
            
        return data


class MaintenanceSerializer(serializers.ModelSerializer):
    asset_name = serializers.ReadOnlyField(source='asset.assets_name')
    technician_name = serializers.ReadOnlyField(source='technician.username')
    asset_type = serializers.CharField(source='asset.assets_type', read_only=True)
    asset_string_id = serializers.ReadOnlyField(source='asset.assets_id')

    processor = serializers.ReadOnlyField(source='asset.processor')
    ram_gb = serializers.ReadOnlyField(source='asset.ram_gb')
    ip_address = serializers.ReadOnlyField(source='asset.ip_address')
    storage = serializers.ReadOnlyField(source='asset.storage_capacity') 
    firmware_os = serializers.ReadOnlyField(source='asset.firmware_version')   
    mac_address = serializers.ReadOnlyField(source='asset.mac_address')   
    asset_category = serializers.ReadOnlyField(source='asset.assets_type') 

    faulty_hardware_part = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    software_issue_type = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    issue_description = serializers
    solution_description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    solved_description = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    formatted_maintenance_date = serializers.SerializerMethodField()

    class Meta:
        model = Maintenance
        fields = [
            'id', 'asset', 'asset_string_id', 'asset_name', 'asset_type', 
            'maintenance_type', 'technician_name', 'date', 
            'maintenance_date', 'formatted_maintenance_date', 
            'last_modified', 'status', 'notes',
            'processor', 'ram_gb', 'storage', 'ip_address', 
            'firmware_os', 'mac_address', 'asset_category',
            'faulty_hardware_part', 'software_issue_type',
            'attachment', 'maintenance_attachment', 'issue_description', 'solution_description', 'solved_description'
        ]

    def get_formatted_maintenance_date(self, obj):
        if obj.maintenance_date:
            return obj.maintenance_date.strftime('%b %d, %Y')
        return "Not Scheduled"

class IncidentSerializer(serializers.ModelSerializer):
    """Prepares incident data with formatted reporting information."""
    reported_by_name = serializers.ReadOnlyField(source='reported_by.username')
    assigned_to_name = serializers.ReadOnlyField(source='assigned_to.username') # Fetches the technician's name
    
    # Include details from the related Asset
    asset_location = serializers.ReadOnlyField(source='asset.location')
    asset_id_display = serializers.ReadOnlyField(source='asset.assets_id')

    problems_encountered = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    solutions_applied = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    class Meta:
        model = Incident
        # Preserved Honrad Branch SOC/Intel field mappings
        fields = [
            'id', 'title', 'asset', 'asset_location', 'asset_id_display', 
            'affected_area', 'severity', 'status', 'description', 
            'date', 'updated_at', 'reported_by', 'reported_by_name',
            
            # --- SOC & INTEL FIELDS ---
            'category', 'detection_source', 'linked_asset', 'iocs', 'cve_id',
            'impact_confidentiality', 'impact_integrity', 'impact_availability',
            'root_cause', 'is_false_positive', 'problems_encountered', 'solutions_applied',
            
            # --- NEW PERSONNEL & PROGRESS FIELDS ---
            'threat_actor', 'assigned_to', 'assigned_to_name', 'actions_taken'
        ]
    extra_kwargs = {'reported_by': {'required': False, 'allow_null': True}}

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
    # NEW: Added the phone mapping
    phone = serializers.CharField(source='profile.phone', required=False, allow_blank=True, allow_null=True)
    
    # Use write_only so the password is never sent back to the browser
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        # ADDED 'phone' to the fields list
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