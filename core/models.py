from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import JSONField
import pyotp


class UserTOTP(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='totp')
    # Automatically generates a secure 32-character base32 secret key when created
    secret = models.CharField(max_length=32, default=pyotp.random_base32)
    is_active = models.BooleanField(default=False) # Only true AFTER they scan the QR code


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
    ASSET_TYPES = [
        ('PC', 'PC'), 
        ('Laptop', 'Laptop'), 
        ('Server', 'Server'), 
        ('Router', 'Router'),
        ('Switch', 'Network Switch')
    ]
    
    STATUS_CHOICES = [
        ('Active', 'Active'), 
        ('Inactive', 'Inactive'), 
        ('Maintenance', 'Under Maintenance'),
        ('Decommissioned', 'Decommissioned')
    ]

    HARDWARE_PART_CHOICES = [
        ('Display', 'Screen/Display'),
        ('Battery', 'Battery'),
        ('Keyboard', 'Keyboard/Trackpad'),
        ('Storage', 'HDD/SSD/RAID Array'),
        ('RAM', 'Memory (RAM)'),
        ('Motherboard', 'Motherboard/Logic Board'),
        ('Power', 'PSU/Redundant Power Supply'), 
        ('Network', 'NIC/SFP/Fiber Ports'),      
        ('Cooling', 'Fan/Heatsink/Cooling Node'),
        ('Chassis', 'Physical Chassis/Rack Mount'),
        ('Other', 'Other Hardware Component'),
    ]

    SOFTWARE_ISSUE_CHOICES = [
        ('OS', 'Operating System Crash/Error'),
        ('Firmware', 'Firmware/BIOS Corruption'),  
        ('Driver', 'Driver Conflict/Missing'),
        ('Security', 'Malware/Virus Infection'),
        ('Update', 'Update/Patch Failure'),
        ('Config', 'Configuration/Registry Issue'),
        ('License', 'Software Licensing/Subscription'),
        ('ServicePack', 'Service Pack/Kernel Update'),
        ('Performance', 'Slow Performance/Bottleneck'),
        ('App', 'Third-Party Application Error'),
    ]

    # --- BASE IDENTIFICATION ---
    assets_id = models.CharField(max_length=15, unique=True, editable=False)
    assets_name = models.CharField(max_length=100)
    brand = models.CharField(max_length=50, blank=True, null=True, help_text="e.g. Dell, HP, Cisco, Juniper")
    model_number = models.CharField(max_length=100, blank=True, null=True)
    serial_number = models.CharField(max_length=100, unique=True, blank=True, null=True)
    attachment = models.FileField(upload_to='asset_attachments/', blank=True, null=True, help_text="Manuals, Invoices, Photos")
    maintenance_attachment = models.FileField(upload_to='maintenance_attachments/', blank=True, null=True, help_text="Maintenance Logs, Repair Photos")
    
    # --- ASSIGNMENT & STATUS ---
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    assets_type = models.CharField(max_length=20, choices=ASSET_TYPES)
    location = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    
    # --- TECHNICAL HARDWARE FIELDS ---
    # For PC/Laptop/Server
    processor = models.CharField(max_length=100, blank=True, null=True)
    ram_gb = models.IntegerField(help_text="RAM in GB", blank=True, null=True)
    storage_capacity = models.CharField(max_length=100, help_text="e.g., 512GB SSD", blank=True, null=True)
    os_version = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. Windows Server 2022, RHEL 9")
    
    # For Router/Server/Networking
    ip_address = models.GenericIPAddressField(protocol='both', unpack_ipv4=True, blank=True, null=True)
    mac_address = models.CharField(max_length=17, blank=True, null=True)
    firmware_version = models.CharField(max_length=50, blank=True, null=True)
    total_ports = models.IntegerField(blank=True, null=True, help_text="Copper/Fiber Port Count")
    is_redundant_power = models.BooleanField(default=False, help_text="Does it have Dual PSUs?")
    
    # --- PHYSICAL/ENVIRONMENTAL ---
    rack_unit = models.IntegerField(blank=True, null=True, help_text="Height in U (e.g. 1, 2, 4)")
    battery_health = models.IntegerField(blank=True, null=True, help_text="Laptop/UPS battery % health")

    # --- MAINTENANCE LOGGING ---
    maintenance_reason = models.TextField(blank=True, null=True)
    faulty_hardware_part = models.CharField(max_length=50, choices=HARDWARE_PART_CHOICES, blank=True, null=True)
    software_issue_type = models.CharField(max_length=50, choices=SOFTWARE_ISSUE_CHOICES, blank=True, null=True)
    
    # --- TIMESTAMPS ---
    date_added = models.DateTimeField(default=timezone.now)
    last_audit_date = models.DateField(blank=True, null=True)
    specifications = JSONField(default=dict, blank=True, help_text="Store hardware-specific specs here")
    
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
                    # Fallback to ID if string parsing fails
                    self.assets_id = f'AST-{self.id + 1:03d}' if self.id else f'AST-{Asset.objects.count() + 1:03d}'
        super(Asset, self).save(*args, **kwargs)

    def __str__(self):
        # Displays the brand if available, otherwise just ID and Name
        brand_display = f"{self.brand} " if self.brand else ""
        return f"[{self.assets_id}] {brand_display}{self.assets_name}"
    

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
    
    # --- DIAGNOSTICS & ATTACHMENTS ---
    maintenance_date = models.DateField(null=True, blank=True, help_text="The date the maintenance was or will be performed")
    attachment = models.FileField(upload_to='maintenance_attachments/', blank=True, null=True, help_text="Photos, Logs, Reports")
    maintenance_attachment = models.FileField(upload_to='maintenance_attachments/', blank=True, null=True, help_text="Additional files related to maintenance")
    faulty_hardware_part = models.CharField(max_length=50, choices=Asset.HARDWARE_PART_CHOICES, blank=True, null=True)
    software_issue_type = models.CharField(max_length=50, choices=Asset.SOFTWARE_ISSUE_CHOICES, blank=True, null=True)

    date = models.DateTimeField(auto_now_add=True)  # Creation date
    last_modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        display_date = self.maintenance_date if self.maintenance_date else self.date.date()
        return f"{self.asset.assets_name} - {display_date}"
    

class Incident(models.Model):
    SEVERITY_CHOICES = [('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High'), ('Critical', 'Critical')]
    STATUS_CHOICES = [('Open', 'Open'), ('Investigating', 'Investigating'), ('Resolved', 'Resolved')]
    
    # Preserving the granular Incident Categories from Code 1
    CATEGORY_CHOICES = [
        # Malicious Software
        ('Virus / Worm', 'Virus / Worm'),
        ('Ransomware', 'Ransomware'),
        ('Spyware / Trojan', 'Spyware / Trojan'),
        ('Rootkit / Bootkit', 'Rootkit / Bootkit'),
        ('Malware', 'Other Malware'),

        # Network & Web Attacks
        ('Phishing / Social Engineering', 'Phishing / Social Engineering'),
        ('Man-in-the-Middle (MitM)', 'Man-in-the-Middle (MitM)'),
        ('Cross-Site Scripting (XSS)', 'Cross-Site Scripting (XSS)'),
        ('SQL Injection (SQLi)', 'SQL Injection (SQLi)'),
        ('Denial of Service (DDoS)', 'Denial of Service (DDoS)'),
        ('Zero-Day Exploit', 'Zero-Day Exploit'),

        # Access & Infrastructure
        ('Unauthorized Access', 'Unauthorized Access'),
        ('Credential Compromise', 'Credential Compromise'),
        ('Insider Threat / Data Exfiltration', 'Insider Threat / Data Exfiltration'),
        ('System Misconfiguration', 'System Misconfiguration'),
        ('Hardware Loss / Physical Breach', 'Hardware Loss / Physical Breach'),

        # Other
        ('Other / Unclassified', 'Other / Unclassified'),
    ]
    
    IMPACT_CHOICES = [('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High')]

    title = models.CharField(max_length=100)
    asset = models.ForeignKey('Asset', on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents')
    
    # --- ASSIGNED TECHNICIAN & THREAT ACTOR ---
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_incidents')
    last_technician = models.CharField(max_length=255, blank=True, null=True)
    threat_actor = models.CharField(max_length=100, blank=True, null=True)
    
    # --- THREAT INTEL FIELDS ---
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Other / Unclassified')
    detection_source = models.CharField(max_length=50, blank=True, null=True)
    linked_asset = models.CharField(max_length=100, blank=True, null=True) 
    iocs = models.TextField(blank=True, null=True)
    cve_id = models.CharField(max_length=50, blank=True, null=True)
    
    # --- IMPACT ASSESSMENT (CIA Triad) ---
    impact_confidentiality = models.CharField(max_length=20, choices=IMPACT_CHOICES, blank=True, null=True)
    impact_integrity = models.CharField(max_length=20, choices=IMPACT_CHOICES, blank=True, null=True)
    impact_availability = models.CharField(max_length=20, choices=IMPACT_CHOICES, blank=True, null=True)

    # --- POST-INCIDENT WRAP-UP ---
    root_cause = models.CharField(max_length=100, blank=True, null=True)
    is_false_positive = models.BooleanField(default=False)
    problems_encountered = models.TextField(blank=True, null=True)
    solutions_applied = models.TextField(blank=True, null=True)

    # --- EXISTING FIELDS ---
    affected_area = models.CharField(max_length=255, blank=True, null=True) 
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')
    description = models.TextField(blank=True)
    actions_taken = models.TextField(blank=True)
    
    date = models.DateTimeField(auto_now_add=True) 
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
    rank = models.CharField(max_length=50, default='Airman') 
    
    # Add the phone field with max_length 11
    phone = models.CharField(max_length=11, blank=True, null=True)

    def __str__(self):
        return f'{self.user.username} Profile'