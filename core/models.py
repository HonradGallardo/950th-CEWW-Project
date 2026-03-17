from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import models
from django.db.models import JSONField


class UserPasskey(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='passkeys')
    name = models.CharField(max_length=100, default="My Authenticator") # e.g. "iPhone 15 Pro"
    credential_id = models.CharField(max_length=255, unique=True)
    public_key = models.TextField()
    sign_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.name}"
    
class Asset(models.Model):
    ASSET_TYPES = [('PC', 'PC'), ('Laptop', 'Laptop'), ('Server', 'Server'), ('Router', 'Router')]
    STATUS_CHOICES = [('Active', 'Active'), ('Inactive', 'Inactive'), ('Maintenance', 'Under Maintenance')]

    assets_id = models.CharField(max_length=10, unique=True, editable=False)
    assets_name = models.CharField(max_length=100)
    # AUTOMATIC: Links to the User who created/updated it
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    assets_type = models.CharField(max_length=20, choices=ASSET_TYPES)
    location = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    maintenance_reason = models.TextField(blank=True, null=True)
    
    # AUTOMATIC: auto_now_add captures date AND time on creation
    date_added = models.DateTimeField(default=timezone.now)
    specifications = JSONField(default=dict, blank=True, help_text="Store hardware-specific specs here")
    processor = models.CharField(max_length=100, blank=True, null=True)
    ram_gb = models.IntegerField(blank=True, null=True)
    storage_capacity = models.CharField(max_length=50, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    mac_address = models.CharField(max_length=17, blank=True, null=True)
    firmware_version = models.CharField(max_length=50, blank=True, null=True)
    
    def save(self, *args, **kwargs):
        if not self.assets_id:
            last_asset = Asset.objects.all().order_by('id').last()
            if not last_asset:
                self.assets_id = 'AST-001'
            else:
                last_id = last_asset.assets_id
                try:
                    last_number = int(last_id.split('-')[1])
                    new_number = last_number + 1
                    self.assets_id = f'AST-{new_number:03d}'
                except (IndexError, ValueError):
                    self.assets_id = f'AST-{last_asset.id + 1:03d}'
        super(Asset, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.assets_id} - {self.assets_name}"

class Maintenance(models.Model):
    STATUS_CHOICES = [
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
    ]

    asset = models.ForeignKey('Asset', on_delete=models.CASCADE, related_name='maintenance_logs')
    technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    maintenance_type = models.CharField(max_length=100)
    notes = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='In Progress')
    date = models.DateTimeField(auto_now_add=True)  # Creation date
    last_modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.asset.assets_name} - {self.date.date()}"
    


class Incident(models.Model):
    SEVERITY_CHOICES = [('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High'), ('Critical', 'Critical')]
    STATUS_CHOICES = [('Open', 'Open'), ('Investigating', 'Investigating'), ('Resolved', 'Resolved')]

    title = models.CharField(max_length=100)
    asset = models.ForeignKey(Asset, on_delete=models.SET_NULL, null=True, related_name='incidents')
    
    # 1. ADD THIS FIELD to capture the data from your "Add Incident" form
    affected_area = models.CharField(max_length=255, blank=True, null=True) 

    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')
    description = models.TextField(blank=True)
    actions_taken = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)
    threat_actor = models.CharField(max_length=255, blank=True, null=True)

    # 2. ADD THIS FIELD to track when the incident is updated
    updated_at = models.DateTimeField(auto_now=True) 

    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reported_incidents')

    def __str__(self):
        return f"{self.severity} - {self.title}"
    
class IncidentComment(models.Model):
    # Use 'Incident' as a string instead of a direct reference
    incident = models.ForeignKey('Incident', on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.recipient.username}"
    

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # Changed from ImageField to FileField to bypass the Pillow requirement
    image = models.FileField(default='default.jpg', upload_to='profile_pics')
    rank = models.CharField(max_length=50, default='Airman') # Adjusted default to match your frontend
    
    # 🚨 NEW: Add the phone field with max_length 11
    phone = models.CharField(max_length=11, blank=True, null=True)

    def __str__(self):
        return f'{self.user.username} Profile'