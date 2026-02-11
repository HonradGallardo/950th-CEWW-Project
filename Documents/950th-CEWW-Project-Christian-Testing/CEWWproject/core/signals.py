from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Notification, Incident  # Ensure your model is named Incident


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