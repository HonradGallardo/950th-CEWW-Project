from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Notification, Incident  # Ensure your model is named Incident
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Asset, Maintenance, Incident, Notification

# 1. Notify on New IT Asset
@receiver(post_save, sender=Asset)
def notify_new_asset(sender, instance, created, **kwargs):
    if created:  # Only trigger when a NEW asset is created
        users = User.objects.all()
        # FIXED: Changed 'user' to 'recipient'
        notifications = [
            Notification(
                recipient=u, 
                message=f"New IT Asset provisioned: {instance.assets_id} ({instance.assets_name})"
            ) for u in users
        ]
        Notification.objects.bulk_create(notifications)

# 2. Notify on New Maintenance Log
@receiver(post_save, sender=Maintenance)
def notify_new_maintenance(sender, instance, created, **kwargs):
    if created:
        users = User.objects.all()
        # FIXED: Changed 'user' to 'recipient'
        notifications = [
            Notification(
                recipient=u,
                message=f"Maintenance logged for {instance.asset.assets_id}: {instance.maintenance_type}"
            ) for u in users
        ]
        Notification.objects.bulk_create(notifications)

# 3. Notify on New Incident/Ticket
@receiver(post_save, sender=Incident)
def notify_new_incident(sender, instance, created, **kwargs):
    if created:
        all_users = User.objects.all()
        
        # Style the prefix based on severity
        severity = getattr(instance, 'severity', 'Medium')
        if severity == 'Critical':
            prefix = "🚨 [CRITICAL ALERT]"
        elif severity == 'High':
            prefix = "⚠️ [HIGH PRIORITY]"
        else:
            prefix = "ℹ️ [NEW INCIDENT]"

        # Build the message
        notification_message = f"{prefix} {instance.title} has been reported. Status: {getattr(instance, 'status', 'New')}"

        # FIXED: Changed 'user' to 'recipient'
        notifications = [
            Notification(
                recipient=u,
                message=notification_message
            ) for u in all_users
        ]
        Notification.objects.bulk_create(notifications)

# 4. Welcome Notification for New Users
@receiver(post_save, sender=User)
def welcome_notification(sender, instance, created, **kwargs):
    if created:
        Notification.objects.create(
            recipient=instance, # FIXED: Changed 'user' to 'recipient'
            message=f"Welcome to the 950th CEWW System, {instance.username}! We're glad you're here."
        )

@receiver(post_save, sender=Incident)
def broadcast_incident_notification(sender, instance, created, **kwargs):
    if created:
        # Get all users to notify (Admins/Personnel)
        all_users = User.objects.all()
        
        # Style the prefix based on severity
        if instance.severity == 'Critical':
            prefix = "🚨 [CRITICAL ALERT]\n"
        elif instance.severity == 'High':
            prefix = "⚠️ [HIGH PRIORITY]\n"
        else:
            prefix = "ℹ️ [NEW INCIDENT]\n"

        # Build the message using fields present in your Incident model
        notification_message = (
            f"{prefix} {instance.title} has been reported. "
            f"Status: {instance.status} | Severity: {instance.severity}"
        )

        # Create notifications for everyone
        notifications = [
            Notification(
                recipient=user,
                message=notification_message
            ) for user in all_users
        ]

        Notification.objects.bulk_create(notifications)

@receiver(post_save, sender=User)
def welcome_notification(sender, instance, created, **kwargs):
    if created:
        Notification.objects.create(
            recipient=instance,
            message=f"Welcome to the system, {instance.username}! We're glad you're here."
        )