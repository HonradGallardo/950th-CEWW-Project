from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Asset(models.Model):
    ASSET_TYPES = [('PC', 'PC'), ('Laptop', 'Laptop'), ('Server', 'Server')]
    STATUS_CHOICES = [('Active', 'Active'), ('Inactive', 'Inactive'), ('Maintenance', 'Under Maintenance')]

    # Set editable=False so it is handled by the system, not the user
    assets_id = models.CharField(max_length=10, unique=True, editable=False)
    assets_name = models.CharField(max_length=100)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    assets_type = models.CharField(max_length=20, choices=ASSET_TYPES)
    location = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    date_added = models.DateField(default=timezone.now) # This allows the manual change

    def save(self, *args, **kwargs):
        if not self.assets_id:
            # Look for the last asset to determine the next number
            last_asset = Asset.objects.all().order_by('id').last()
            if not last_asset:
                self.assets_id = 'AST-001'
            else:
                last_id = last_asset.assets_id # e.g., "AST-005"
                try:
                    # Split at '-', take the number, increment, and re-format
                    last_number = int(last_id.split('-')[1])
                    new_number = last_number + 1
                    self.assets_id = f'AST-{new_number:03d}'
                except (IndexError, ValueError):
                    # Fallback if the last ID doesn't follow the format
                    self.assets_id = f'AST-{last_asset.id + 1:03d}'
        super(Asset, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.assets_id} - {self.assets_name}"

class Maintenance(models.Model):
    STATUS_CHOICES = [('Completed', 'Completed'), ('In Progress', 'In Progress')]

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='maintenances')
    maintenance_type = models.CharField(max_length=100)
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    def __str__(self):
        return f"Maintenance for {self.asset.assets_name}"

class Incident(models.Model):
    SEVERITY_CHOICES = [('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High'), ('Critical', 'Critical')]
    STATUS_CHOICES = [('Open', 'Open'), ('Investigating', 'Investigating'), ('Resolved', 'Resolved')]

    title = models.CharField(max_length=100)
    # Link incident to a specific asset as shown in your Project Architecture
    asset = models.ForeignKey(Asset, on_delete=models.SET_NULL, null=True, related_name='incidents')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')
    description = models.TextField(blank=True)
    actions_taken = models.TextField(blank=True)
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.severity} - {self.title}"